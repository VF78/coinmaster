"""BTC pattern pilot: causal multiscale inputs and genuine minute-path labels.

No strategy imports. UTC milliseconds, half-open intervals throughout.
"""
from __future__ import annotations
import json, time, urllib.request
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from .forecast_independent_data import aggregate, validate, sha, write_json, MINUTE, HOUR, DAY


def ms(value):
    d=datetime.fromisoformat(value.replace('Z','+00:00'))
    if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
    return int(d.timestamp()*1000)

FOLDS=[('F1','2025-01-01','2025-05-01'),('F2','2025-07-01','2025-11-01'),('F3','2026-01-01','2026-05-01')]
CONTEXT=['return1h','return4h','return24h','return168h','volatility24h','volatility168h','ATR14/price','current_range/price','relative_volume20','closed4h_age_hours','sigma24','sigma72']
META=np.dtype([('origin','<i8'),('entry_time','<i8'),('label_end','<i8'),('input_start','<i8'),('raw_input_start','<i8'),('engineered_input_start','<i8'),('entry_index','<i8'),('reference','<f8'),('entry','<f8'),('sigma24','<f8'),('sigma72','<f8'),('valid','?'),('observed','?')])


def folds(meta):
    """All shared learned transformations receive these same purged IDs."""
    start=ms('2024-06-01')
    for name,cut,end in FOLDS:
        cut,end=ms(cut),ms(end); inner=cut-28*DAY
        eligible=meta['valid']&meta['observed']
        select=lambda a,b: np.flatnonzero(eligible&(meta['origin']>=a)&(meta['origin']<b)&(meta['label_end']<=b))
        yield dict(name=name,inner_cutoff=inner,fit_cutoff=cut,outer_end=end,
                   subfit=select(start,inner),early_stop=select(inner,cut),refit=select(start,cut),outer=select(cut,end))


def method_input_start(meta, method):
    """Earliest actual observed bar per representation; legacy v1 input_start was raw."""
    raw = meta['raw_input_start'] if 'raw_input_start' in meta.dtype.names else meta['input_start']
    engineered = meta['engineered_input_start'] if 'engineered_input_start' in meta.dtype.names else raw - 80*HOUR
    if method in ('TCN', 'numeric-knn', 'CatBoost', 'flat-knn'):
        return engineered
    if method == 'random-context':
        return raw # preserve the original conservative256h control exclusion
    if method == 'Context':
        return meta['origin'] - 169*HOUR
    if method in ('CNN', 'CNNSpatial', 'Kronos'):
        return np.minimum(raw, meta['origin'] - 169*HOUR)
    raise ValueError('UNKNOWN_METHOD_SUPPORT: '+method)


def features_at(panels,origin):
    """Every calculation uses completed bars only; no entry price is accepted."""
    ht,hv=panels[1];hj=np.searchsorted(ht+HOUR,origin,side='right')
    if hj<169: return None
    hist=hv[hj-169:hj]; r=np.diff(np.log(hist[:,3])); vol=np.std(r,ddof=1)
    if not np.isfinite(vol) or vol<=0: return None
    ctx=[]; ref=hist[-1,3]
    ctx.extend([np.log(ref/hist[-1-k,3]) for k in (1,4,24,168)])
    ctx.extend([np.std(r[-24:],ddof=1),vol])
    tr=np.maximum(hist[-14:,1]-hist[-14:,2],np.maximum(abs(hist[-14:,1]-hist[-15:-1,3]),abs(hist[-14:,2]-hist[-15:-1,3])))
    ctx.extend([tr.mean()/ref,(hist[-1,1]-hist[-1,2])/ref,np.log1p(hist[-1,4])-np.log1p(hist[-21:-1,4]).mean()])
    views=[];raw=[];stamps=[];starts=[];last4=None
    for tf in (4,1):
        t,v=panels[tf]; j=np.searchsorted(t+tf*HOUR,origin,side='right')
        if j<85: return None
        a=v[j-64:j]; prev=v[j-65:j-1,3]
        logv=np.log1p(v[j-84:j,4]); relv=np.array([logv[k]-logv[k-20:k].mean() for k in range(20,84)])
        o,h,l,c,_=a.T
        x=np.column_stack((np.log(c/prev),np.log(c/o),np.log(h/np.maximum(o,c)),np.log(np.minimum(o,c)/l),np.log(h/l),relv))
        x[:,:5]/=vol*np.sqrt(tf)
        views.append(x.astype('float32')); raw.append(a.astype('float32')); stamps.append(t[j-64:j]);starts.append(t[j-64])
        if tf==4: last4=t[j-1]+4*HOUR
    ctx.extend([(origin-last4)/HOUR,vol*np.sqrt(24),vol*np.sqrt(72)])
    return np.stack(views),np.asarray(ctx,'float32'),np.stack(raw),np.stack(stamps),int(min(starts)),ref


def path_targets(values,sigma,hours=72):
    """First-passage D and conservative MFE; within-minute order stays unknown.

    Timestamp of sample u is entry+u hours: close of minute u*60-1.
    A gap at a minute open establishes order before that minute's extrema.
    """
    n=hours*60
    if len(values)!=n: raise ValueError('WHOLE_HORIZON_REQUIRED')
    if not np.isfinite(sigma) or sigma<=0: raise ValueError('INVALID_SCALE')
    o,h,l,c=values[:,:4].T; entry=o[0]; zhi=np.log(h/entry)/sigma; zlo=np.log(l/entry)/sigma; zop=np.log(o/entry)/sigma
    first=lambda hit: int(np.flatnonzero(hit)[0]) if hit.any() else n
    up,dn=first(zhi>=1),first(zlo<=-1)
    ambiguous=up==dn and up<n and abs(zop[up])<1
    direction=-1 if ambiguous else (0 if up<dn or (up==dn and up<n and zop[up]>=1) else 1 if dn<n else 2)
    mfe=np.zeros((2,2)); stops=[]
    for side in (1,-1):
        fav=zhi if side==1 else -zlo; adverse=zlo if side==1 else -zhi
        stop=first(adverse<=-1); before=max(0.,float(fav[:stop].max())) if stop else 0.
        lower=max(before,max(0.,side*zop[stop])) if stop<n else before
        gap=stop<n and side*zop[stop]<=-1
        upper=lower if stop==n or gap else max(lower,float(fav[stop]))
        mfe[0 if side==1 else 1]=lower,upper; stops.append(stop)
    signature=np.zeros(12)
    for k,u in enumerate((1,4,12,24,48,72)):
        signature[k]=np.log(c[min(u*60,n)-1]/entry)/sigma
    for k,(side,level) in enumerate([(s,b) for s in (1,-1) for b in (.5,1,2)]):
        touch=first(zhi>=level if side==1 else zlo<=-level)
        signature[6+k]=touch/n if touch<n else 2.
    return dict(direction=direction,ambiguous=ambiguous,mfe=mfe,signature=signature,stop_indices=stops)


def neighbors(index_z,query_z,origins,label_end,cutoff,input_start,k=32):
    """Filter before ranking; greedy 72h separation, deterministic ties by row."""
    eligible=np.flatnonzero((label_end<=cutoff)&(label_end<=input_start))
    distance=1-index_z[eligible]@query_z
    rank=eligible[np.argsort(distance,kind='stable')]; chosen=[]
    for i in rank:
        if all(abs(int(origins[i])-int(origins[j]))>=72*HOUR for j in chosen):
            chosen.append(int(i))
            if len(chosen)==k: break
    return np.array(chosen,dtype='int64')


def download_prefix(output,start,end):
    """Resumable public Bybit linear-perpetual REST kline pages, raw retained."""
    output=Path(output); output.mkdir(parents=True,exist_ok=True); pieces=[];receipts=[]
    for a in range(start,end,1000*MINUTE):
        b=min(end,a+1000*MINUTE);p=output/f'{a}.json'
        url=f'https://api.bybit.com/v5/market/kline?category=linear&symbol=BTCUSDT&interval=1&start={a}&end={b-1}&limit=1000'
        if not p.exists():
            for attempt in range(4):
                try:
                    payload=urllib.request.urlopen(url,timeout=30).read();obj=json.loads(payload)
                    if obj.get('retCode')!=0: raise ValueError(str(obj))
                    p.write_bytes(payload);break
                except Exception:
                    if attempt==3: raise
                    time.sleep(2**attempt)
        obj=json.loads(p.read_bytes()); rows=sorted(obj['result']['list'],key=lambda x:int(x[0]))
        if obj['result']['category']!='linear' or obj['result']['symbol']!='BTCUSDT':raise ValueError('VENUE_INSTRUMENT_DRIFT')
        x=np.array(rows,dtype='float64');expected=np.arange(a,b,MINUTE)
        if not np.array_equal(x[:,0].astype('int64'),expected):raise ValueError('PUBLIC_PAGE_COVERAGE_GAP')
        pieces.append(x[:,1:6]); receipts.append(dict(path=str(p),url=url,sha256=sha(p),rows=len(x),first=int(x[0,0]),end=int(x[-1,0])+MINUTE))
    write_json(output/'receipt.json',dict(venue='Bybit',market='linear perpetual',symbol='BTCUSDT',start=start,end=end,pages=receipts))
    return np.vstack(pieces)


def prepare(args):
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    lock=json.loads(args.protocol.read_text());src=Path(args.old_prepared); old=json.loads((src/'manifest.json').read_text())
    source=src/'minutes-BTCUSDT.npy'; rec=old['artifacts'][source.name]
    if sha(source)!=rec['sha256']:raise ValueError('IMMUTABLE_SOURCE_HASH_MISMATCH')
    old_values=np.load(source,mmap_mode='r'); start=ms('2024-05-15');old_start=old['minute_start_ms'];end=min(old['minute_end_exclusive_ms'],ms(lock['eval_end']))
    prefix=download_prefix(output/'public-prefix',start,old_start)
    v=np.lib.format.open_memmap(output/'minutes.npy',mode='w+',dtype='float64',shape=((end-start)//MINUTE,5));v[:len(prefix)]=prefix;v[len(prefix):]=old_values[:(end-old_start)//MINUTE];v.flush();del prefix
    t=np.arange(start,end,MINUTE);validate(t,v,MINUTE)
    panels={tf:aggregate(t,v,tf*HOUR) for tf in (1,4)}
    origins=np.arange(ms('2024-06-01'),end,HOUR);n=len(origins)
    meta=np.zeros(n,dtype=META);meta['origin']=origins;meta['entry_time']=origins+MINUTE;meta['label_end']=origins+MINUTE+72*HOUR
    meta['entry_index']=(meta['entry_time']-start)//MINUTE;meta['entry']=np.nan;meta['reference']=np.nan
    arrays={name:np.lib.format.open_memmap(output/f'{name}.npy',mode='w+',dtype=dtype,shape=(n,*shape)) for name,shape,dtype in [('features',(2,64,6),'float32'),('context',(12,),'float32'),('raw',(2,64,5),'float32'),('stamps',(2,64),'int64')]}
    y=np.full((n,2,2),np.nan,'float32'); sig=np.full((n,12),np.nan,'float32'); d=np.full(n,-1,'int8'); ambiguous=np.zeros(n,bool);policy=np.full((n,2,3,2,2),np.nan,'float32')
    for i,origin in enumerate(origins):
        f=features_at(panels,int(origin))
        if f is None:continue
        x,c,raw,stamps,ins,ref=f
        for key,value in [('features',x),('context',c),('raw',raw),('stamps',stamps)]:arrays[key][i]=value
        meta['valid'][i]=True;meta['raw_input_start'][i]=ins;meta['engineered_input_start'][i]=ins-80*HOUR;meta['input_start'][i]=ins-80*HOUR;meta['reference'][i]=ref;meta['sigma24'][i]=c[-2];meta['sigma72'][i]=c[-1]
        j=meta['entry_index'][i]
        if j<len(v):meta['entry'][i]=v[j,0]
        if meta['label_end'][i]>end:continue
        meta['observed'][i]=True
        result=path_targets(v[j:j+4320],float(c[-1]));y[i]=result['mfe'];d[i]=result['direction'];sig[i]=result['signature'];ambiguous[i]=result['ambiguous']
        for hi,h in enumerate((24,72)):
            for si,sl in enumerate((.75,1,1.5)):
                result2=path_targets(v[j:j+h*60],float(c[-2 if h==24 else -1])*sl,h)
                policy[i,hi,si]=result2['mfe']*sl
        if i%2000==0:print(json.dumps(dict(event='prepare_progress',rows=i,total=n)),flush=True)
    for a in arrays.values():a.flush()
    np.save(output/'entry-gap.npy',np.column_stack((np.log(meta['entry']/meta['reference'])/meta['sigma24'],np.log(meta['entry']/meta['reference'])/meta['sigma72'])));np.save(output/'path-reference-indices.npy',np.column_stack(((meta['origin']-start)//MINUTE-1,meta['entry_index'])));np.save(output/'metadata.npy',meta);np.savez(output/'labels.npz',direction=d,mfe=y,signature=sig,ambiguous=ambiguous,policy_mfe=policy)
    receipt=dict(source_code_sha256=sha(__file__),schema='btc-pattern.data.v2',protocol_sha256=sha(args.protocol),minute_start=start,minute_end=end,requested_development_start=ms('2024-06-01'),genuine_june_coverage=True,origins=n,valid=int(meta['valid'].sum()),mature=int(meta['observed'].sum()),source=dict(path=str(source),sha256=sha(source)),prefix_receipt_sha256=sha(output/'public-prefix/receipt.json'),amount='proxy volume*mean(OHLC); no real quote turnover in reused source')
    receipt['artifacts']={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in output.glob('*') if p.is_file() and p.name!='manifest.json'}
    write_json(output/'manifest.json',receipt)
    return receipt
