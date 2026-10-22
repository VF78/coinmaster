"""Frozen, causal in-app packet preparation and post-seal scoring. No model calls."""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
import numpy as np
from .btc_pattern_data import CONTEXT, DAY, HOUR, MINUTE, FOLDS, ms, path_targets

SL=(.75,1.,1.5)
KEYS=('sl_075','sl_100','sl_150')
TAGS={'compression','trend','failed_breakout','rejection','reversal','mixed','unclear'}
PROMPT='''You are being evaluated as a probabilistic BTC pattern forecaster. Use only the supplied packet and its matured historical exemplars. Detailed sequences/charts may be withheld by design; a packet with 12 valid context fields remains valid input and is not a reason by itself to abstain. The current query contains no future bars. Read only the explicitly supplied packet/image; do not browse, open repository/history/results, retrieve memory or call another model. Predict the next 72 hours after the stipulated next-minute entry. Distances are log-return/sigma72; the actual future entry fill is unknown and must not be inferred from hidden data.
Return probabilities D for first +1sigma, first -1sigma or neither; for LONG and SHORT and SL distances 0.75/1/1.5, return MFE-before-that-SL quantiles 0.2/0.5/0.8 and P(adverse barrier touched anywhere in 72h). Adverse-touch ignores TP exits. Quantiles may be zero/tied, must be nonnegative and nondecreasing; adverse-touch probabilities must not increase for farther stops. Do not choose hindsight-best TP/SL or calculate EV from quantiles. Describe at most 3 tags from the fixed vocabulary and evidence in at most 80 words.
Output only JSON with keys window_id, status, reason, D (three numbers in UP/DOWN/NONE order), forecasts (long/short; each containing sl_075/sl_100/sl_150 with q20/q50/q80/p_adverse_touch), tags and evidence. Status is OK or ABSTAIN; if input is unusable, abstain explicitly rather than inventing values. Do not use current real-world BTC information or absolute calendar identity.'''
SCHEMA={'required':['window_id','status','reason','D','forecasts','tags','evidence'],'status':['OK','ABSTAIN'],'D_order':['UP','DOWN','NONE'],'sides':['long','short'],'SL_keys':dict(zip(KEYS,SL)),'row_required':['q20','q50','q80','p_adverse_touch'],'tags':sorted(TAGS),'max_tags':3,'max_evidence_words':80,'probability_sum_tolerance':1e-3,'boundary_order_tolerance':1e-6,'cross_SL_quantile_decrease':'record, score without repair','ABSTAIN_or_invalid':'frozen prior fallback; covered-only separately'}

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def write(path,obj):
    Path(path).write_text(json.dumps(obj,separators=(',',':'),allow_nan=False)+'\n')

def opaque(i):return hashlib.sha256(('cm-inapp-v1:'+str(int(i))).encode()).hexdigest()[:16]

def select(meta):
    valid=meta['valid']&meta['observed']&(meta['origin']>=ms('2024-06-01'))&(meta['origin']<ms('2026-05-01'))
    selected=[];total=0
    for fold,cut,end in FOLDS:
        a,b=ms(cut),ms(end);ids=np.flatnonzero(valid&(meta['origin']>=a)&(meta['origin']<b)&(meta['label_end']<=b));total+=len(ids)
        used=[]
        for slot in range(8):
            center=a+(b-a)*(2*slot+1)//16
            rank=sorted(ids,key=lambda i:(abs(int(meta['origin'][i])-center),int(i)))
            found=next((int(i) for i in rank if all(meta['entry_time'][i]>meta['label_end'][j] or meta['entry_time'][j]>meta['label_end'][i] for j in used)),None)
            if found is None:raise ValueError('UNDERFILLED')
            used.append(found);selected.append(dict(id=found,fold=fold,phase='evaluation',slot=slot,fit_cutoff=a))
    if total!=8496:raise ValueError(f'OOF_UNIVERSE_MISMATCH:{total}')
    for month in range(7,13):
        a=ms(f'2024-{month:02d}-01');ids=np.flatnonzero(valid&(meta['origin']>=a)&(meta['origin']<a+DAY)&(meta['label_end']<=ms('2025-01-01')))
        if not len(ids):raise ValueError('UNDERFILLED_DEBUG')
        i=int(min(ids,key=lambda i:(abs(int(meta['origin'][i])-a),int(i))))
        selected.append(dict(id=i,fold='F1',phase='debug',slot=month-7,fit_cutoff=ms('2025-01-01')))
    return selected

def support(meta,i):
    # 64 closed 4h bars + 20 preceding bars for volume = 336h + closed-bar age.
    age=(int(meta['origin'][i])//HOUR)%4
    stored=meta['engineered_input_start'][i] if 'engineered_input_start' in meta.dtype.names else meta['input_start'][i]
    return min(int(stored),int(meta['origin'][i])-336*HOUR-age*HOUR)

def targets(values,sigma):
    d=path_targets(values,sigma)
    q=np.stack([path_targets(values,sigma*s)['mfe']*s for s in SL],axis=1) # side, SL, bound
    entry=values[0,0]
    touch=np.array([[bool(np.min(values[:,2])<=entry*np.exp(-s*sigma)) for s in SL],[bool(np.max(values[:,1])>=entry*np.exp(s*sigma)) for s in SL]],dtype=float)
    return dict(D=int(d['direction']),Q=q.tolist(),touch=touch.tolist())

def response_arrays(obj,window_id):
    errors=[];cross=False
    try:
        if set(obj)!=set(SCHEMA['required']) or obj['window_id']!=window_id:raise ValueError('keys/window_id')
        if obj['status']!='OK':raise ValueError('ABSTAIN')
        if not isinstance(obj['reason'],str) or not isinstance(obj['evidence'],str) or len(obj['evidence'].split())>80:raise ValueError('text')
        if not isinstance(obj['tags'],list) or len(obj['tags'])>3 or any(x not in TAGS for x in obj['tags']):raise ValueError('tags')
        def numeric(v):
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v):raise ValueError('numeric')
            return v
        p=np.array([numeric(x) for x in obj['D']]);q=[];touch=[]
        if p.shape!=(3,) or np.any(p< -1e-6) or np.any(p>1+1e-6) or abs(p.sum()-1)>1e-3:raise ValueError('D')
        if set(obj['forecasts'])!={'long','short'}:raise ValueError('sides')
        for side in ('long','short'):
            rows=obj['forecasts'][side]
            if set(rows)!=set(KEYS):raise ValueError('SL keys')
            qq=[];tt=[]
            for key in KEYS:
                r=rows[key]
                if set(r)!=set(SCHEMA['row_required']):raise ValueError('row keys')
                qq.append([numeric(r[k]) for k in ('q20','q50','q80')]);tt.append(numeric(r['p_adverse_touch']))
            q.append(qq);touch.append(tt)
        q=np.array(q);touch=np.array(touch)
        if np.any(q< -1e-6) or np.any(np.diff(q,axis=2)< -1e-6):raise ValueError('quantile order')
        if np.any(touch< -1e-6) or np.any(touch>1+1e-6) or np.any(np.diff(touch,axis=1)>1e-6):raise ValueError('touch order')
        cross=bool(np.any(np.diff(q,axis=1)< -1e-6))
        return p,q,touch,[],cross
    except (ValueError,TypeError,KeyError,IndexError) as e:errors.append(str(e))
    return None,None,None,errors,cross

def display(p,q,touch,entry=None,sigma=None):
    if np.sum(p==max(p))!=1 or np.argmax(p)==2:return {'status':'NO_TRADE','reason':'D_NONE_OR_TIE'}
    side=int(np.argmax(p));j=next((j for j in range(3) if touch[side,j]<=.25),None)
    if j is None:return {'status':'NO_TRADE','reason':'NO_SL_WITHIN_TOUCH_LIMIT'}
    tp=q[side,j]
    if tp[0]<=0 or np.any(np.diff(tp)<=0):return {'status':'NO_TRADE','reason':'TP_NOT_STRICT_POSITIVE_INCREASING'}
    out=dict(status='DISPLAY',side=('long','short')[side],SL=SL[j],TP=tp.tolist())
    if entry is not None:
        sign=1 if side==0 else -1
        out.update(entry=float(entry),TP_prices=(entry*np.exp(sign*tp*sigma)).tolist(),SL_price=float(entry*np.exp(-sign*SL[j]*sigma)))
    return out

def chart(packet,path):
    from PIL import Image,ImageDraw,ImageFont
    image=Image.new('RGB',(1600,1000),'white');draw=ImageDraw.Draw(image);font=ImageFont.load_default(size=18)
    for k,seq in enumerate(packet['query']['windows']):
        a=np.asarray(seq['rows']);top=45+k*485;left,right=125,1550;bottom=top+310;vtop,vbottom=top+335,top+405
        xmin=float(a[0,0]);lo=float(a[:,4].min());hi=float(a[:,3].max());pad=max((hi-lo)*.06,.001);lo-=pad;hi+=pad
        x=lambda v:left+(v-xmin)/(0-xmin)*(right-left)
        y=lambda v:bottom-(v-lo)/(hi-lo)*(bottom-top)
        draw.text((left,top-28),f"{seq['timeframe_hours']}h closed candles; log(price/reference) / sigma72",fill='#202938',font=font)
        for value in np.linspace(lo,hi,6):
            yy=y(value);draw.line((left,yy,right,yy),fill='#e3e7ed');draw.text((15,yy-9),f'{value:.3f}',fill='#526b89',font=font)
        for value in np.linspace(xmin,0,9):
            xx=x(value);draw.line((xx,top,xx,bottom),fill='#eef0f4');draw.text((xx-18,vbottom+8),f'{value:g}',fill='#526b89',font=font)
        vmax=max(float(np.max(np.abs(a[:,6]))),1e-6);mid=(vtop+vbottom)/2
        draw.line((left,mid,right,mid),fill='#cbd2dc');draw.text((10,vtop),'Volume',fill='#526b89',font=font);draw.text((10,vtop+22),'anomaly',fill='#526b89',font=font)
        width=(right-left)/(-xmin)*seq['timeframe_hours']*.65
        for start,end,o,h,l,c,v in a:
            xx=x((start+end)/2);color='#16836d' if c>=o else '#c34d57'
            draw.line((xx,y(l),xx,y(h)),fill=color,width=2);ya,yb=sorted((y(o),y(c)));draw.rectangle((xx-width/2,ya,xx+width/2,max(ya+1,yb)),fill=color)
            vy=mid-v/vmax*(vbottom-vtop)/2;draw.rectangle((xx-width/2,min(mid,vy),xx+width/2,max(mid,vy)),fill='#526b89')
        draw.text((610,vbottom+35),'Hours relative to origin',fill='#202938',font=font)
    image.save(path,format='PNG',optimize=False)

def prepare(prepared,output,packets):
    prepared,output,packets=map(Path,(prepared,output,packets));output.mkdir(parents=True,exist_ok=False);packets.mkdir(parents=True,exist_ok=False)
    if digest(prepared/'manifest.json')!='bc660056af9117a246a1334837b7e42c9bb2d0635945a0346a4b088a459685ff':raise ValueError('PREPARED_MANIFEST_MISMATCH')
    manifest=json.loads((prepared/'manifest.json').read_text())
    names=['metadata.npy','context.npy','raw.npy','features.npy','stamps.npy','minutes.npy']
    hashes={name:digest(prepared/name) for name in names}
    if any(hashes[n]!=manifest['artifacts'][n]['sha256'] for n in names):raise ValueError('SOURCE_HASH_MISMATCH')
    meta=np.load(prepared/'metadata.npy',mmap_mode='r');c=np.load(prepared/'context.npy',mmap_mode='r');raw=np.load(prepared/'raw.npy',mmap_mode='r');features=np.load(prepared/'features.npy',mmap_mode='r');stamps=np.load(prepared/'stamps.npy',mmap_mode='r');minutes=np.load(prepared/'minutes.npy',mmap_mode='r')
    rows=select(meta);write(output/'prompt.json',{'prompt':PROMPT});write(output/'response-schema.json',SCHEMA)
    def view(i,full):
        out=dict(window_id=opaque(i),context=np.round(c[i].astype(float),6).tolist())
        if full:
            out['windows']=[]
            for k,tf in enumerate((4,1)):
                times=(stamps[i,k]-int(meta['origin'][i]))/HOUR;ohlc=np.log(raw[i,k,:,:4].astype(float)/float(meta['reference'][i]))/float(meta['sigma72'][i]);table=np.column_stack((times,times+tf,ohlc,features[i,k,:,5]))
                out['windows'].append(dict(timeframe_hours=tf,rows=np.round(table,6).tolist()))
        return out
    cache={};freeze=[]
    for row in rows:
        i=row['id'];dep=support(meta,i);cut=min(row['fit_cutoff'],dep)
        eligible=np.flatnonzero(meta['valid']&meta['observed']&(meta['origin']>=ms('2024-06-01'))&(meta['origin']<ms('2026-05-01'))&(meta['label_end']<=cut))
        mu=np.asarray(c[eligible],float).mean(0);sd=np.maximum(np.asarray(c[eligible],float).std(0),1e-6);z=(np.asarray(c[eligible],float)-mu)/sd;z/=np.maximum(np.linalg.norm(z,axis=1,keepdims=True),1e-12);query=(np.asarray(c[i],float)-mu)/sd;query/=max(np.linalg.norm(query),1e-12);dist=1-z@query;rank=np.lexsort((eligible,dist));examples=[]
        for j in eligible[rank]:
            if all(abs(int(meta['origin'][j])-int(meta['origin'][k]))>=72*HOUR for k in examples):examples.append(int(j))
            if len(examples)==4:break
        if len(examples)<4:
            if row['phase']=='evaluation':raise ValueError('LOW_SUPPORT_EVALUATION')
            freeze.append(dict(**row,window_id=opaque(i),origin=int(meta['origin'][i]),dependency_start=dep,status='LOW_SUPPORT',eligible_count=len(eligible),examples=examples,packets={},arm_order=[]))
            continue
        # Only mature fit-prefix paths enter cache. Query paths never read here.
        for j in eligible:
            j=int(j)
            if j not in cache:
                pos=int(meta['entry_index'][j]);cache[j]=targets(minutes[pos:pos+4320],float(meta['sigma72'][j]))
        tt=[cache[int(j)] for j in eligible];dd=np.array([t['D'] for t in tt]);qq=np.array([t['Q'] for t in tt]);touch=np.array([t['touch'] for t in tt]);prior=dict(D=(np.bincount(dd[dd>=0],minlength=3)/np.sum(dd>=0)).tolist(),Q=np.quantile(qq[:,:,:,0],[.2,.5,.8],axis=0,method='linear').transpose(1,2,0).tolist(),touch=touch.mean(0).tolist())
        paired={}
        for arm in ('C','P'):
            packet=dict(window_id=opaque(i),horizon_hours=72,context_fields=CONTEXT,context_units=['log return']*4+['hourly log-return std']*2+['ratio','ratio','log1p volume anomaly','hours','log-return sigma24','log-return sigma72'],window_columns=['start_hours','end_hours','open','high','low','close','volume_anomaly'],query=view(i,arm=='P'),examples=[dict(**view(j,arm=='P'),outcome=cache[j]) for j in examples],outcome_definitions={'D':'UP=0 DOWN=1 NONE=2 ambiguous=-1','Q':'[long,short] x [SL .75,1,1.5] x [conservative lower,upper], sigma72 units; stop minute extrema excluded from lower except known open','touch':'[long,short] x [SL .75,1,1.5]; full 72h adverse barrier touched, inclusive equality'},tag_vocabulary=sorted(TAGS))
            folder=packets/(opaque(i)+arm);folder.mkdir();write(folder/'packet.json',packet)
            if (folder/'packet.json').stat().st_size>250000:raise ValueError('PACKET_TOO_LARGE')
            if arm=='P':chart(packet,folder/'chart.png')
            paired[arm]={str(p.name):digest(p) for p in folder.iterdir()}
        freeze.append(dict(**row,window_id=opaque(i),origin=int(meta['origin'][i]),entry_time=int(meta['entry_time'][i]),label_end=int(meta['label_end'][i]),dependency_start=dep,eligible_count=len(eligible),eligible_ids=eligible.tolist(),examples=examples,scaler_mean=mu.tolist(),scaler_std=sd.tolist(),prior=prior,packets=paired,arm_order=['C','P'] if i%2==0 else ['P','C']))
    write(output/'freeze.json',dict(schema='cm-inapp.freeze.v1',status='READY_REQUIRES_ROOT_LAUNCH_GO',model='gpt-6.1-sol',reasoning='high',max_responses=60,actual_planned_responses=58,debug_status='UNDERFILLED_JULY_LOW_SUPPORT_NO_REPLACEMENT',development_days=699,original_oof_ids=8496,source_hashes=hashes,prepared=str(prepared),packet_root=str(packets),prompt_sha256=digest(output/'prompt.json'),schema_sha256=digest(output/'response-schema.json'),source_sha256=digest(__file__),query_truth_revealed=False,temporal_clarification='Mature earlier selected evaluation IDs may belong to later whole eligible fit prefixes; no current query truth or pointwise evaluation report is revealed during setup.',rows=freeze))
    return dict(status='READY_REQUIRES_ROOT_LAUNCH_GO',rows=len(rows),packets=sum(len(r['arm_order']) for r in freeze),freeze_sha256=digest(output/'freeze.json'))

def validate_structure(freeze_path,phase='evaluation',seal=False):
    f=json.loads(Path(freeze_path).read_text());root=Path(f['packet_root']);records=[]
    if digest(__file__)!=f['source_sha256']:raise ValueError('SOURCE_CHANGED')
    for r in f['rows']:
        if r['phase']!=phase:continue
        for arm in r['arm_order']:
            folder=root/(r['window_id']+arm)
            for name,h in r['packets'][arm].items():
                if digest(folder/name)!=h:raise ValueError('PACKET_CHANGED')
            path=folder/'response.json'
            if not path.exists():raise ValueError('RESPONSE_MISSING:'+str(path))
            try:obj=json.loads(path.read_text());p,q,t,errors,cross=response_arrays(obj,r['window_id'])
            except (ValueError,TypeError):errors=['JSON_PARSE'];cross=False
            records.append(dict(window_id=r['window_id'],arm=arm,response_path=str(path),sha256=digest(path),valid=not errors,errors=errors,cross_SL_incoherent=cross))
    expected=48 if phase=='evaluation' else 10
    if len(records)!=expected:raise ValueError('PAIR_COUNT')
    receipt=dict(phase=phase,count=len(records),valid=sum(x['valid'] for x in records),freeze_sha256=digest(freeze_path),records=records)
    if seal:
        dest=Path(freeze_path).with_name(phase+'-sealed.json')
        if dest.exists():raise ValueError('ALREADY_SEALED')
        write(dest,receipt)
    return receipt

def block_ci(delta,origins,folds,days=14):
    delta=np.asarray(delta);origins=np.asarray(origins);folds=np.asarray(folds);rng=np.random.default_rng(7);boot=np.zeros(1000);den=np.zeros(1000);counts={};means={}
    for fold in sorted(set(folds)):
        take=(folds==fold)&np.isfinite(delta);x=delta[take];blocks=origins[take]//(days*DAY);u,inv=np.unique(blocks,return_inverse=True);counts[str(fold)]=len(u);means[str(fold)]=float(x.mean()) if len(x) else None
        if not len(u):continue
        sums=np.bincount(inv,weights=x);n=np.bincount(inv);draw=rng.integers(0,len(u),(1000,len(u)));boot+=sums[draw].sum(1);den+=n[draw].sum(1)
    values=boot/np.maximum(den,1);lo,hi=np.quantile(values,[.025,.975]);finite=delta[np.isfinite(delta)];inconclusive=any(n<2 for n in counts.values()) or not len(finite) or np.ptp(finite)<=1e-15 or hi<=lo
    mean=float(finite.mean()) if len(finite) else None
    return dict(mean=mean,lower=float(lo),upper=float(hi),blocks_by_fold=counts,pooled_blocks=sum(counts.values()),fold_means=means,status='INCONCLUSIVE' if inconclusive else 'DESCRIPTIVE',pass_rule=bool(not inconclusive and mean<0 and hi<0 and sum(v is not None and v<0 for v in means.values())>=2),days=days,draws=1000,seed=7)

def forecast_scores(p,q,touch,truth,bound=0):
    y=np.array(truth['Q'])[:,:,bound];target=np.array(truth['touch']);err=y[:,:,None]-q;pin=np.maximum(err*np.array([.2,.5,.8]),err*(np.array([.2,.5,.8])-1));d=truth['D'];prob=np.clip(p,1e-6,1-1e-6);prob/=prob.sum()
    return dict(TP=float(pin.mean()),SL=float(((touch-target)**2).mean()),TP_rows=pin.mean(2).tolist(),SL_rows=((touch-target)**2).tolist(),quantile_hit=(y[:,:,None]<=q).astype(int).tolist(),quantile_error=(q-y[:,:,None]).tolist(),D_logloss=float(-np.log(prob[d])) if d>=0 else None,D_correct=bool(np.argmax(prob)==d) if d>=0 else None)

def calibration(pred,truth):
    pred=np.asarray(pred);truth=np.asarray(truth);out=[]
    for left,right in zip(np.arange(0,1,.2),np.arange(.2,1.01,.2)):
        take=(pred>=left)&((pred<=right) if right>.999 else (pred<right));out.append(dict(left=float(left),right=float(right),count=int(take.sum()),predicted=float(pred[take].mean()) if take.any() else None,observed=float(truth[take].mean()) if take.any() else None))
    return out

def score(freeze_path):
    freeze_path=Path(freeze_path);f=json.loads(freeze_path.read_text());sealed_path=freeze_path.with_name('evaluation-sealed.json');seal=json.loads(sealed_path.read_text())
    if seal['freeze_sha256']!=digest(freeze_path) or seal['count']!=48 or len(seal['records'])!=48:raise ValueError('ALL_48_SEALED_REQUIRED')
    if digest(__file__)!=f['source_sha256']:raise ValueError('SOURCE_CHANGED')
    records={(r['window_id'],r['arm']):r for r in seal['records']}
    if any(digest(r['response_path'])!=r['sha256'] for r in records.values()):raise ValueError('SEALED_RESPONSE_CHANGED')
    prepared=Path(f['prepared']);meta=np.load(prepared/'metadata.npy',mmap_mode='r');minutes=np.load(prepared/'minutes.npy',mmap_mode='r');cases=[];preds={k:[] for k in ('P','C','prior')};alltruth=[]
    for row in f['rows']:
        if row['phase']!='evaluation':continue
        i=row['id'];j=int(meta['entry_index'][i]);truth=targets(minutes[j:j+4320],float(meta['sigma72'][i]));alltruth.append(truth);prior=row['prior'];pp=np.array(prior['D']);pq=np.array(prior['Q']);pt=np.array(prior['touch']);case=dict(id=i,window_id=row['window_id'],fold=row['fold'],origin=row['origin'],truth=truth,forecasts={})
        for arm in ('prior','C','P'):
            valid=True;errors=[];cross=False
            if arm=='prior':p,q,t=pp,pq,pt
            else:
                rec=records[(row['window_id'],arm)];obj=json.loads(Path(rec['response_path']).read_text()) if rec['valid'] else {};p,q,t,errors,cross=response_arrays(obj,row['window_id']);valid=not errors
                if not valid:p,q,t=pp,pq,pt
            preds[arm].append((p,q,t,valid));case['forecasts'][arm]=dict(valid=valid,errors=errors,cross_SL_incoherent=cross,loss=forecast_scores(p,q,t,truth),upper_sensitivity=forecast_scores(p,q,t,truth,1),display=display(p,q,t,float(meta['entry'][i]),float(meta['sigma72'][i])))
        cases.append(case)
    if len(cases)!=24:raise ValueError('24_CASES_REQUIRED')
    metrics={};comparisons={};origins=[r['origin'] for r in cases];folds=[r['fold'] for r in cases]
    for arm in ('P','C','prior'):
        valid=np.array([x[3] for x in preds[arm]]);touch=np.stack([x[2] for x in preds[arm]]);target=np.array([x['touch'] for x in alltruth]);q=np.stack([x[1] for x in preds[arm]]);y=np.array([x['Q'] for x in alltruth])[:,:,:,0];loss=[r['forecasts'][arm]['loss'] for r in cases]
        metrics[arm]=dict(coverage=float(valid.mean()),failures=int((~valid).sum()),all_ID={k:float(np.mean([x[k] for x in loss])) for k in ('TP','SL')},covered_only={k:float(np.mean([x[k] for x,v in zip(loss,valid) if v])) if valid.any() else None for k in ('TP','SL')},TP_rows=np.mean([x['TP_rows'] for x in loss],axis=0).tolist(),SL_rows=np.mean([x['SL_rows'] for x in loss],axis=0).tolist(),TP_quantile_hit_rates=(y[:,:,:,None]<=q).mean(0).tolist(),TP_coverage_strict=(y[:,:,:,None]<q).mean(0).tolist(),TP_zero_counts=(q==0).sum(0).tolist(),TP_attained_lower=((y[:,:,:,None]>=q)&(q>0)).sum(0).tolist(),TP_attained_upper=((np.array([x['Q'] for x in alltruth])[:,:,:,1,None]>=q)&(q>0)).sum(0).tolist(),TP_positive_denominators=(q>0).sum(0).tolist(),TP_mean_errors=(q-y[:,:,:,None]).mean(0).tolist(),SL_calibration=[[calibration(touch[:,s,j],target[:,s,j]) for j in range(3)] for s in range(2)],D_logloss=float(np.mean([x['D_logloss'] for x in loss if x['D_logloss'] is not None])),D_accuracy=float(np.mean([x['D_correct'] for x in loss if x['D_correct'] is not None])),NO_TRADE=sum(r['forecasts'][arm]['display']['status']=='NO_TRADE' for r in cases),cross_SL_count=sum(r['forecasts'][arm]['cross_SL_incoherent'] for r in cases))
    for arm in ('P','C','prior'):
        selected=[]
        for case,truth,(p,q,t,valid) in zip(cases,alltruth,preds[arm]):
            d=case['forecasts'][arm]['display']
            if d['status']!='DISPLAY':continue
            si=0 if d['side']=='long' else 1;sj=SL.index(d['SL']);bounds=np.array(truth['Q'])[si,sj];tp=np.array(d['TP'])
            selected.append(dict(valid=valid,attained_lower=(bounds[0]>=tp).astype(int).tolist(),attained_upper=(bounds[1]>=tp).astype(int).tolist(),predicted_full_horizon_adverse_touch=float(t[si,sj]),observed_full_horizon_adverse_touch=float(np.array(truth['touch'])[si,sj])))
        metrics[arm]['selected_display_ladder']=dict(n=len(selected),NO_TRADE=24-len(selected),TP_attained_lower_rates=np.mean([x['attained_lower'] for x in selected],axis=0).tolist() if selected else None,TP_attained_upper_rates=np.mean([x['attained_upper'] for x in selected],axis=0).tolist() if selected else None,predicted_full_horizon_adverse_touch=float(np.mean([x['predicted_full_horizon_adverse_touch'] for x in selected])) if selected else None,observed_full_horizon_adverse_touch=float(np.mean([x['observed_full_horizon_adverse_touch'] for x in selected])) if selected else None,interpretation='Descriptive forecast distances; positive TP only. Full-horizon adverse touch is not realized strategy stopout after partial TPs. Higher TP hit rate alone is not forecast skill.')
    for reference in ('prior','C'):
        comparisons[reference]={}
        for task in ('TP','SL'):
            delta=np.array([r['forecasts']['P']['loss'][task]-r['forecasts'][reference]['loss'][task] for r in cases]);comparisons[reference][task]={'primary_14d':block_ci(delta,origins,folds),'sensitivity_28d':block_ci(delta,origins,folds,28)}
    coverage=all(metrics[a]['coverage']>=.9 for a in ('P','C'));out=dict(status='FEASIBILITY_PASS' if coverage else 'INCOMPLETE_FORMAT_FAIL',exploratory_signal=coverage and all(comparisons['prior'][k]['primary_14d']['pass_rule'] for k in ('TP','SL')),window_bundle_incremental=coverage and all(comparisons['C'][k]['primary_14d']['pass_rule'] for k in ('TP','SL')),metrics=metrics,comparisons=comparisons,ambiguous_D=sum(t['D']<0 for t in alltruth),cases=cases,query_truth_revealed=True,secondary_original_controls='NOT_JOINED; no variable-SL forecasts invented',economic_evaluation=False)
    dest=freeze_path.with_name('evaluation-results.json')
    if dest.exists():raise ValueError('RESULT_ALREADY_EXISTS')
    write(dest,out);return dict(status=out['status'],result=str(dest),sha256=digest(dest))

def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('--prepared',required=True);a.add_argument('--output',required=True);a.add_argument('--packets',required=True)
    for name in ('validate-structure','seal','score-after-seal'):
        a=sub.add_parser(name);a.add_argument('--freeze',required=True)
        if name!='score-after-seal':a.add_argument('--phase',choices=['debug','evaluation'],default='evaluation')
    a=p.parse_args()
    if a.command=='prepare':out=prepare(a.prepared,a.output,a.packets)
    elif a.command=='score-after-seal':out=score(a.freeze)
    else:
        out=validate_structure(a.freeze,a.phase,a.command=='seal');out={k:v for k,v in out.items() if k!='records'}
    print(json.dumps(out))

if __name__=='__main__':main()
