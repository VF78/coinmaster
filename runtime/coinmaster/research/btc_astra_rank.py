"""Frozen bounded Astra rank screen. Prepare is outcome blind; score requires seal."""
from __future__ import annotations
import argparse, csv, hashlib, json, os, signal, time
from collections import Counter
from pathlib import Path
import numpy as np
from . import btc_event_research as e
from . import btc_event_d90 as d90

ARMS=('prior','daily90','phase32','numeric8','numericD1_8','astra8')
PROMPT='''Rank the eight anonymized candidate prefixes by structural similarity to the query. You are gpt-6-astra with reasoning=max. Read ONLY the exact packet.json path supplied by the coordinator; write ONLY one response.json to the supplied response path. No browsing, other files, repository, outcomes, agents or models. All data are observed prefixes; future C/D and historical candidate outcomes are deliberately absent. Signed normalized log prices preserve direction. H1/H4 arrays are oldest first [relative close hours, open, high, low, close, relative volume]; volume is log1p(volume) minus own preceding20 mean log1p(volume). Phase arrays use own last known H1 close and sigma72. D1 includes the then-confirmed A/B, observed A→B→P path and physical elapsed durations; missing context is explicit and provisional structure is not a completed future wave. Compare structure, scale, duration and context using the numeric packet. Do not infer calendar identity. Return ONLY JSON with exactly {"query_id":string,"ranked_candidate_ids":[8 unique allowed IDs, most similar first],"no_match":boolean,"evidence":string}. Even if no_match=true return all eight IDs. Evidence <=1500 characters, cite concrete relative coordinates/segments, no forecasts/probabilities/TP/SL. One response only; do not retry or create alternatives.'''
SCHEMA={'type':'object','additionalProperties':False,'required':['query_id','ranked_candidate_ids','no_match','evidence'],'properties':{'query_id':{'type':'string'},'ranked_candidate_ids':{'type':'array','minItems':8,'maxItems':8,'uniqueItems':True,'items':{'type':'string'}},'no_match':{'type':'boolean'},'evidence':{'type':'string','maxLength':1500}}}

def read(p):return json.loads(Path(p).read_text())
def write(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);e.write(p,obj)
def exclusive(p,obj):
    with Path(p).open('x') as f:json.dump(obj,f,indent=2,allow_nan=False)
def anon(domain,value):return hashlib.sha256((domain+':'+str(value)).encode()).hexdigest()[:12]
def cutoff(row):return next(e.ms(a) for f,a,b in e.FOLDS if f==row['fold'])
def pool_for(events,i,fit,strict=False):
    q=events[i]
    if fit>q['origin']:raise ValueError('FIT_AFTER_QUERY')
    return np.asarray([j for j,r in enumerate(events) if r['label_end']<=min(fit,q['input_start']) and r['origin']<q['input_start']] if strict else [j for j,r in enumerate(events) if r['label_end']<=fit and r['origin']<fit],dtype=int)

def select(events):
    rows=[];under=[]
    for fold,a,b in e.FOLDS:
        a,b=e.ms(a),e.ms(b);eligible=[i for i,r in enumerate(events) if r['fold']==fold and r['label_end']<=b];used=[]
        for slot in range(8):
            center=a+(b-a)*(2*slot+1)//16
            order=sorted(eligible,key=lambda i:(abs(events[i]['origin']-center),events[i]['origin']))
            found=next((i for i in order if all(events[i]['entry_time']>=events[j]['label_end'] or events[j]['entry_time']>=events[i]['label_end'] for j in used)),None)
            if found is None:under.append(dict(fold=fold,slot=slot,status='UNDERFILLED'));continue
            used.append(found);rows.append(dict(index=found,fold=fold,slot=slot,fit_cutoff=a,phase='evaluation'))
    # Two fixed F1 fit-only calendar slots; no selection using truth or support.
    for slot,(a,b) in enumerate((('2024-11-01','2024-12-01'),('2024-12-01','2025-01-01'))):
        a,b=e.ms(a),e.ms(b);ids=[i for i,r in enumerate(events) if a<=r['origin'] and r['label_end']<=b]
        if not ids:raise ValueError('DEBUG_SLOT_EMPTY')
        i=min(ids,key=lambda i:(abs(events[i]['origin']-(a+b)//2),events[i]['origin']))
        rows.append(dict(index=i,fold='F1',slot=slot,fit_cutoff=a,phase='debug'))
    return rows,under

def d1_context(row,snapshot,panels):
    """Only Stage-A saved causal A/B; own past daily path, no final wave lookup."""
    missing=dict(status='MISSING_CONTEXT',mode=None,phase32_32=None,durations_hours=None,confirmation_lags_days=None,confirmed_age_hours=None)
    if snapshot is None:return missing
    if snapshot['asof']>row['origin'] or snapshot.get('C') is not None or snapshot.get('D') is not None:raise ValueError('D1_FUTURE_STATE')
    missing['mode']=snapshot['mode']
    a,b=snapshot['A'],snapshot['B']
    if a is None or b is None:return missing
    if max(a['confirmation'],b['confirmation'])>row['origin']:raise ValueError('UNCONFIRMED_D1_PIVOT')
    ht,hv=panels[1];j=np.searchsorted(ht+e.HOUR,row['origin'],side='right');last=float(hv[j-1,3]);sig=row['sigma72']
    # A/B bar timestamps denote D1 starts; their close coordinate is +24h.
    at,bt=a['bar']+e.DAY,b['bar']+e.DAY
    daily=hv[:j-j%24,3].reshape(-1,24)[:,-1];t=e.WARM+np.arange(1,len(daily)+1)*e.DAY
    tx=np.r_[t[t<=row['origin']],row['origin']];px=np.r_[np.log(daily[t<=row['origin']]),np.log(last)]
    coords=np.r_[np.linspace(at,bt,32),np.linspace(bt,row['origin'],32)]
    phase=(np.interp(coords,tx,px)-np.log(last))/sig
    return dict(status=snapshot['status'],mode=snapshot['mode'],phase32_32=phase.tolist(),durations_hours=[(bt-at)/e.HOUR,(row['origin']-bt)/e.HOUR],confirmation_lags_days=[a['lag_days'],b['lag_days']],confirmed_age_hours=[(row['origin']-a['confirmation'])/e.HOUR,(row['origin']-b['confirmation'])/e.HOUR],A=(a['log']-np.log(last))/sig,B=(b['log']-np.log(last))/sig,P=0.,orientation=1 if b['log']>a['log'] else -1,left_truncated=a['bar']<e.START)

def geometry(ctx):
    # 64 signed path values +2 log1p durations +2 log1p confirmation lags.
    if ctx['phase32_32'] is None:return np.zeros(68),False
    return np.r_[ctx['phase32_32'],np.log1p(ctx['durations_hours']),np.log1p(ctx['confirmation_lags_days'])],True

def distances(events,inputs,contexts,i,pool):
    st=inputs['state'];sd=st[pool].std(0);sd[sd<=1e-12]=1
    original=.5*np.mean(((st[pool]-st[i])/sd)**2,axis=1)+.5*np.mean((inputs['phase'][pool]-inputs['phase'][i])**2,axis=1)
    g=np.asarray([geometry(c)[0] for c in contexts]);valid=np.asarray([geometry(c)[1] for c in contexts]);fit=pool[valid[pool]]
    scale=g[fit].std(0) if len(fit) else np.ones(68);scale[scale<=1e-12]=1
    gd=np.zeros(len(pool))
    # Missing context never removes candidates: same missingness=0; mismatch=1.
    both=valid[pool]&valid[i];gd[both]=np.mean(((g[pool[both]]-g[i])/scale)**2,axis=1);gd[valid[pool]!=valid[i]]=1
    # Two scales are fitted on eligible past pool distances to its mean, not query distances.
    ost=st[pool];oph=inputs['phase'][pool]
    oscale=float(.5*np.mean(((ost-ost.mean(0))/sd)**2)+.5*np.mean((oph-oph.mean(0))**2));oscale=max(oscale,1e-12)
    gscale=float(np.mean(((g[fit]-g[fit].mean(0))/scale)**2)) if len(fit) else 1.;gscale=max(gscale,1e-12)
    return original,.5*original/oscale+.5*gd/gscale

def episode(row,panels,ctx):
    ht,hv=panels[1];j=np.searchsorted(ht+e.HOUR,row['origin'],side='right');last=float(hv[j-1,3]);sig=row['sigma72'];out={}
    for tf in (1,4):
        t,v=panels[tf];n=np.searchsorted(t+tf*e.HOUR,row['origin'],side='right')
        if n<84:raise ValueError('INCOMPLETE_PACKET_PREFIX')
        bars=v[n-64:n];logv=np.log1p(v[n-84:n,4]);rel=np.asarray([logv[k]-logv[k-20:k].mean() for k in range(20,84)])
        z=np.log(bars[:,:4]/last)/sig
        out[f'h{tf}']=np.column_stack(((t[n-64:n]+tf*e.HOUR-row['origin'])/e.HOUR,z,rel)).tolist()
        # Numeric roundtrip assertion checks all four price columns; no absolute values emitted.
        if not np.allclose(last*np.exp(z*sig),bars[:,:4],rtol=2e-14,atol=1e-9):raise ValueError('OHLC_ROUNDTRIP')
    _,ph,_=e.shapes(ht+e.HOUR,np.log(hv[:,3]),row,sig)
    out.update(phase32_32=(ph+(row['anchor_log']-np.log(last))/sig).tolist(),durations_hours=[(row['extreme']-row['anchor'])/e.HOUR,(row['origin']-row['extreme'])/e.HOUR],direction=row['direction'],daily90_state=row['daily90']['state'],d1=ctx)
    return out

def paths(base):
    base=Path(base);return dict(prepared=Path('runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/prepared'),reference=base/'event-e1-20261022',labels=base/'event-d90-20261022/labels.json',d90=base/'event-d90-20261022',stagea=base/'fullwave-stage-a-20261022/run/catalogue.json')

def preflight(base,output,protocol):
    if (output/'freeze.json').exists() or (output/'PREPARE_ATTEMPT.json').exists():raise ValueError('PREFLIGHT_AFTER_START_FORBIDDEN')
    output.mkdir(parents=True,exist_ok=True)
    p=paths(base);
    for source in p.values():
        if output.resolve()==source.resolve() or output.resolve() in source.resolve().parents or source.resolve() in output.resolve().parents:raise ValueError('OUTPUT_SOURCE_OVERLAP')
    p=paths(base);manifest=read(p['prepared']/'manifest.json');pins={};began=time.monotonic()
    files=[Path(__file__),Path(e.__file__),Path(d90.__file__),Path(e.targets.__code__.co_filename),Path(e.features_at.__code__.co_filename),Path(e.__file__).with_name('research_rss.py'),Path(protocol),p['prepared']/'manifest.json',p['reference']/'catalogue.json',p['reference']/'inputs.npz',p['reference']/'RESULTS.json',p['labels'],p['d90']/'PREFLIGHT.json',p['stagea']]
    if e.digest(p['prepared']/'manifest.json')!='bc660056af9117a246a1334837b7e42c9bb2d0635945a0346a4b088a459685ff':raise ValueError('MANIFEST_DRIFT')
    for name in ('minutes.npy','metadata.npy','context.npy','raw.npy','features.npy','stamps.npy'):
        f=p['prepared']/name
        if not f.is_file() or f.is_symlink() and not f.resolve().is_file():raise ValueError('MISSING_REAL_SOURCE:'+str(f))
        if f.stat().st_size!=manifest['artifacts'][name]['bytes'] or e.digest(f)!=manifest['artifacts'][name]['sha256']:raise ValueError('INPUT_DRIFT:'+name)
        arr=np.load(f,mmap_mode='r')
        if not len(arr):raise ValueError('EMPTY_INPUT:'+name)
        files.append(f)
    for f in files:pins[str(f.resolve())]=e.digest(f)
    qa=dict(status='IMPLEMENTED_NOT_PREPARED_NOT_EVALUATED',pins=pins,protocol_sha256=e.digest(protocol),resource=dict(threads=4,rss_gib=6,hard_wall_seconds=1800,expected_wall_seconds=180,expected_rss_gib=1),model='gpt-6-astra',reasoning='max',responses_cap=26,quality_computed=False,elapsed_seconds=time.monotonic()-began)
    write(output/'PREFLIGHT.json',qa);return qa

def verify_pins(output,protocol):
    qa=read(output/'PREFLIGHT.json')
    if qa['protocol_sha256']!=e.digest(protocol):raise ValueError('PROTOCOL_DRIFT')
    for f,h in qa['pins'].items():
        if e.digest(f)!=h:raise ValueError('PIN_DRIFT:'+f)
    return qa

def prepare(base,output,protocol,go):
    qa=verify_pins(output,protocol)
    if go!=qa['protocol_sha256']:raise ValueError('ROOT_GO_PROTOCOL_REQUIRED')
    exclusive(output/'PREPARE_ATTEMPT.json',dict(protocol_sha256=go,no_retry=True));began=time.monotonic();p=paths(base)
    _,minutes,panels,bad=e.load_market(p['prepared']);events=read(p['reference']/'catalogue.json')['events']
    ctx90=d90.daily_context(minutes,[r['origin'] for r in events]);events=d90.revised_events(events,ctx90)
    expected=read(p['d90']/'PREFLIGHT.json')['query_ids'];qids=d90.query_indices(events)
    if [events[i]['id'] for i in qids]!=expected or len(expected)!=198:raise ValueError('ORIGINAL_198_DRIFT')
    snapshots={m['old_id']:m['prefix'] for m in read(p['stagea'])['old_h1_mapping']}
    contexts=[d1_context(r,snapshots[r['id']],panels) for r in events];inputs=dict(np.load(p['reference']/'inputs.npz'))
    availability=[]
    for i in qids:
        row=events[i];states={}
        for contract,strict in [('OLD_STRICT',True),('CAUSAL_WALK_FORWARD',False)]:
            pool=pool_for(events,i,cutoff(row),strict);state=row['daily90']['state']
            states[contract]=dict(events=len(pool),states=dict(Counter(str(events[j]['daily90']['state']) for j in pool)),same_daily90=sum(state in (-1,1) and events[j]['daily90']['state']==state for j in pool),d1_present=sum(contexts[j]['phase32_32'] is not None for j in pool),greedy72_count=len(e.choose(np.zeros(len(pool)),pool,events)))
        availability.append(dict(id=row['id'],fold=row['fold'],**states))
    # The metadata comparison is persisted before packet creation or any forecast.
    write(output/'availability.json',dict(quality_computed=False,rows=availability))
    selected,under=select(events);rows=[]
    for s in selected:
        i=s['index'];r=events[i];pool=pool_for(events,i,s['fit_cutoff']);dist,distd1=distances(events,inputs,contexts,i,pool);chosen=e.choose(dist,pool,events);candidates=chosen[:8]
        ranks={int(j):float(x) for j,x in zip(pool,distd1)};d1order=sorted(candidates,key=lambda j:(ranks[j],j));qid=anon('query',r['id'])
        # IDs and display order depend on catalogue identity, never numeric rank.
        hidden={anon('candidate:'+qid,events[j]['id']):j for j in candidates};order=sorted(hidden,key=lambda x:anon('display:'+qid,x))
        packet=dict(schema='btc-astra-prefix.v1',query_id=qid,units='signed log(price/own last-known H1 close)/own sigma72; physical hours; no calendar; no future C/D',query=episode(r,panels,contexts[i]),candidates=[dict(candidate_id=x,prefix=episode(events[hidden[x]],panels,contexts[hidden[x]])) for x in order])
        rel=Path('packets')/s['phase']/qid/'packet.json';(output/rel).parent.mkdir(parents=True,exist_ok=True)
        (output/rel).write_text(json.dumps(packet,separators=(',',':'),allow_nan=False)+'\n')
        if (output/rel).stat().st_size>250000:raise ValueError('PACKET_250KB_CAP_NO_TRUNCATION')
        parent=next((m['parent_query_id'] for m in read(p['stagea'])['old_h1_mapping'] if m['old_id']==r['id']),None)
        rows.append(dict(**s,id=r['id'],query_id=qid,origin=r['origin'],label_end=r['label_end'],pool=pool.tolist(),phase32=chosen,numeric8=candidates,numericD1_8=d1order,hidden_mapping=hidden,packet=str(rel),packet_sha256=e.digest(output/rel),packet_bytes=(output/rel).stat().st_size,insufficient_support=len(candidates)<8,wave_cluster=parent,d1_missing=contexts[i]['phase32_32'] is None,candidate_d1_missing=sum(contexts[j]['phase32_32'] is None for j in candidates)))
        e.guard(began)
    write(output/'prompt.json',dict(prompt=PROMPT,model='gpt-6-astra',reasoning='max'));write(output/'response-schema.json',SCHEMA)
    freeze=dict(schema='btc-astra-rank.freeze.v1',protocol_sha256=go,pins=qa['pins'],rows=rows,underfilled=under,model='gpt-6-astra',reasoning='max',query_truth_joined=False,labels_read=False,source_sha256=e.digest(__file__),prompt_sha256=e.digest(output/'prompt.json'),schema_sha256=e.digest(output/'response-schema.json'),bad_minutes=bad,elapsed_seconds=time.monotonic()-began)
    write(output/'freeze.json',freeze);return dict(status='PACKETS_FROZEN',evaluation=sum(r['phase']=='evaluation' for r in rows),debug=2,underfilled=under,max_packet_bytes=max(r['packet_bytes'] for r in rows))

def response(obj,row):
    if set(obj)!=set(SCHEMA['required']) or obj['query_id']!=row['query_id'] or type(obj['no_match']) is not bool or not isinstance(obj['evidence'],str) or len(obj['evidence'])>1500:raise ValueError('RESPONSE_SCHEMA')
    ids=obj['ranked_candidate_ids']
    if not isinstance(ids,list) or len(ids)!=8 or any(not isinstance(x,str) for x in ids) or len(set(ids))!=8 or set(ids)!=set(row['hidden_mapping']):raise ValueError('RANK_IDS')
    return [row['hidden_mapping'][x] for x in ids]

def check_freeze(output,protocol):
    verify_pins(output,protocol);fr=read(output/'freeze.json')
    if fr['source_sha256']!=e.digest(__file__) or fr['prompt_sha256']!=e.digest(output/'prompt.json') or fr['schema_sha256']!=e.digest(output/'response-schema.json'):raise ValueError('FROZEN_SOURCE_PROMPT_DRIFT')
    for r in fr['rows']:
        if e.digest(output/r['packet'])!=r['packet_sha256']:raise ValueError('PACKET_DRIFT')
    return fr

def seal(output,protocol,phase):
    fr=check_freeze(output,protocol);records=[]
    ledger=read(output/'DISPATCH_ATTEMPTS.json');attempts=ledger['attempts']
    expected={(r['phase'],r['query_id']) for r in fr['rows']}
    keys=[(r['phase'],r['query_id']) for r in attempts]
    if len(keys)>26 or len(set(keys))!=len(keys) or any(k not in expected for k in keys) or any(r['model']!='gpt-6-astra' or r['reasoning']!='max' for r in attempts):raise ValueError('DISPATCH_CAP_OR_MODEL_DRIFT')
    if any((r['phase'],r['query_id']) not in keys for r in fr['rows'] if r['phase']==phase):raise ValueError('MISSING_DISPATCH_ATTEMPT_RECEIPT')
    if phase=='evaluation' and not (output/'debug-sealed.json').exists():raise ValueError('DEBUG_SEAL_REQUIRED_BEFORE_EVALUATION')
    files=list((output/'responses').glob('*/*.json')) if (output/'responses').exists() else []
    if len(files)>26:raise ValueError('RESPONSE_CAP26')
    for r in fr['rows']:
        if r['phase']!=phase:continue
        f=output/'responses'/phase/(r['query_id']+'.json');rec=dict(query_id=r['query_id'],response_sha256=e.digest(f) if f.exists() else None,valid=False,rank=[],no_match=True)
        try:
            obj=read(f);rec.update(rank=response(obj,r),valid=True,no_match=obj['no_match'])
        except (OSError,ValueError,KeyError,TypeError) as exc:rec['error']=type(exc).__name__+':'+str(exc)[:300]
        records.append(rec)
    receipt=dict(phase=phase,freeze_sha256=e.digest(output/'freeze.json'),records=records,count=len(records),valid=sum(r['valid'] for r in records),actual_response_files=len(files),actual_dispatch_attempts=len(attempts),dispatch_ledger_sha256=e.digest(output/'DISPATCH_ATTEMPTS.json'),model=fr['model'],reasoning=fr['reasoning'])
    exclusive(output/(phase+'-sealed.json'),receipt)
    if phase=='debug':write(output/'EVAL_PROMPT_FREEZE.json',dict(prompt_sha256=fr['prompt_sha256'],source_sha256=fr['source_sha256'],debug_seal_sha256=e.digest(output/'debug-sealed.json'),quality_reviewed=False))
    return {k:v for k,v in receipt.items() if k!='records'}

def weights(pool,local=(),kind='prior'):
    pool=list(pool)
    if not pool:raise ValueError('EMPTY_PAST_POOL')
    w={int(i):1. if kind=='prior' else (32. if kind=='daily90' else 8.)/len(pool) for i in pool}
    if kind=='rank':
        if len(local)!=8:raise ValueError('EIGHT_REQUIRED')
        localweights=8/(np.arange(1,9)*np.sum(1/np.arange(1,9)))
    else:localweights=np.ones(len(local))
    for i,x in zip(local,localweights):w[int(i)]+=float(x)
    return w

def empirical(truths,w):
    ids=list(w);ww=np.asarray(list(w.values()));qq=np.asarray([truths[i]['Q'] for i in ids])[:,:,:,0];tt=np.asarray([truths[i]['touch'] for i in ids]);dd=np.asarray([truths[i]['D'] for i in ids]);dp=np.asarray([ww[dd==j].sum() for j in range(3)])
    if dp.sum()==0:raise ValueError('NO_UNAMBIGUOUS_D')
    return dp/dp.sum(),e.weighted_quantiles(qq,ww),np.average(tt,axis=0,weights=ww)

def compare(cases,arm,control):
    return {task:dict(primary_14d=e.block_ci([c['forecasts'][arm]['loss'][task]-c['forecasts'][control]['loss'][task] for c in cases],[c['origin'] for c in cases],[c['fold'] for c in cases],14),sensitivity_28d=e.block_ci([c['forecasts'][arm]['loss'][task]-c['forecasts'][control]['loss'][task] for c in cases],[c['origin'] for c in cases],[c['fold'] for c in cases],28)) for task in ('TP','SL')}

def summarize(cases,arms):
    metrics={}
    for arm in arms:
        fs=[c['forecasts'][arm] for c in cases];truth=np.asarray([c['truth']['Q'] for c in cases]);q=np.asarray([f['Q'] for f in fs]);t=np.asarray([f['touch'] for f in fs]);yt=np.asarray([c['truth']['touch'] for c in cases]);err=truth[:,:,:,0,None]-q;pos=q>0;den=pos.sum(0)
        avg=lambda rows:{k:float(np.mean([f['loss'][k] for f in rows])) for k in ('TP','SL')}
        metrics[arm]=dict(query_count=len(cases),all_ID=avg(fs),by_fold={fold:avg([f for c,f in zip(cases,fs) if c['fold']==fold]) for fold in sorted(set(c['fold'] for c in cases))},fallbacks=sum(f['fallback'] for f in fs),n_eff=[f['n_eff'] for f in fs],reuse=dict(Counter(j for f in fs for j in f['local_ids'])),TP_pinball_coordinates=np.maximum(err*np.array([.2,.5,.8]),err*(np.array([.2,.5,.8])-1)).mean(0).tolist(),TP_zero_counts=(~pos).sum(0).tolist(),TP_positive_denominators=den.tolist(),TP_attained_lower=((truth[:,:,:,0,None]>=q)&pos).sum(0).tolist(),TP_attained_upper=((truth[:,:,:,1,None]>=q)&pos).sum(0).tolist(),TP_quantile_hit_rates=(truth[:,:,:,0,None]<=q).mean(0).tolist(),SL_rows=((t-yt)**2).mean(0).tolist(),SL_calibration=[[e.calibration(t[:,s,j],yt[:,s,j]) for j in range(3)] for s in range(2)])
    return metrics

def rank_specs(row,rec):
    """All selected IDs survive invalid/missing/no_match as exact prior fallback."""
    supported=not row['insufficient_support'];valid=supported and rec['valid'] and not rec['no_match']
    return dict(numeric8=(row['numeric8'] if supported else [],'rank' if supported else 'prior',not supported),numericD1_8=(row['numericD1_8'] if supported else [],'rank' if supported else 'prior',not supported),astra8=(rec['rank'] if valid else [],'rank' if valid else 'prior',not valid))

def score(base,output,protocol):
    began=time.monotonic();fr=check_freeze(output,protocol);sealed=read(output/'evaluation-sealed.json')
    if sealed['freeze_sha256']!=e.digest(output/'freeze.json'):raise ValueError('SEAL_FREEZE_DRIFT')
    evalfreeze=read(output/'EVAL_PROMPT_FREEZE.json')
    if evalfreeze['source_sha256']!=fr['source_sha256'] or evalfreeze['prompt_sha256']!=fr['prompt_sha256']:raise ValueError('EVALUATION_PROMPT_CHANGED')
    for rec in sealed['records']:
        f=output/'responses/evaluation'/(rec['query_id']+'.json')
        if (e.digest(f) if f.exists() else None)!=rec['response_sha256']:raise ValueError('SEALED_RESPONSE_DRIFT')
    exclusive(output/'SCORE_ATTEMPT.json',dict(no_retry=True,seal_sha256=e.digest(output/'evaluation-sealed.json')))
    p=paths(base);events=read(p['reference']/'catalogue.json')['events'];labels=read(p['labels']);truths={i:labels[r['id']] for i,r in enumerate(events) if r['label_end']<=e.END}
    if len(truths)!=370:raise ValueError('ALL370_SAVED_LABELS_REQUIRED_NO_RECOMPUTE')
    for truth in truths.values():d90.validate_truth(truth)
    saved={c['id']:c['truth'] for c in read(p['reference']/'RESULTS.json')['cases']}
    if any(labels[k]!=v for k,v in saved.items()):raise ValueError('SAVED_LABEL_IDENTITY_DRIFT')
    _,minutes,_,_=e.load_market(p['prepared']);ctx=d90.daily_context(minutes,[r['origin'] for r in events]);events=d90.revised_events(events,ctx);inputs=dict(np.load(p['reference']/'inputs.npz'));rmap={r['index']:r for r in fr['rows'] if r['phase']=='evaluation'};smap={r['query_id']:r for r in sealed['records']};cases=[];all198=[]
    for i in d90.query_indices(events):
        r=events[i];pool=pool_for(events,i,cutoff(r));state=r['daily90']['state'];cell=[int(j) for j in pool if state in (-1,1) and events[j]['daily90']['state']==state]
        st=inputs['state'];sd=st[pool].std(0);sd[sd<=1e-12]=1;dist=.5*np.mean(((st[pool]-st[i])/sd)**2,axis=1)+.5*np.mean((inputs['phase'][pool]-inputs['phase'][i])**2,axis=1);phase=e.choose(dist,pool,events)
        specs=dict(prior=([], 'prior',False),daily90=(cell,'daily90' if cell else 'prior',not bool(cell)),phase32=(phase if len(phase)>=8 else [],'phase' if len(phase)>=8 else 'prior',len(phase)<8))
        row=rmap.get(i);diagnostic=None
        if row:
            if pool.tolist()!=row['pool']:raise ValueError('ELIGIBLE_POOL_DRIFT')
            rec=smap[row['query_id']];specs.update(rank_specs(row,rec))
            # Outcome-nearness post-seal only, evaluated without reselecting candidates.
            tq=np.asarray(truths[i]['Q'])[:,:,0];tt=np.asarray(truths[i]['touch']);distout={j:float(np.mean(abs(np.asarray(truths[j]['Q'])[:,:,0]-tq))+np.mean(abs(np.asarray(truths[j]['touch'])-tt))) for j in row['numeric8']}
            diagnostic={arm:dict(candidate_ids=[events[j]['id'] for j in order],outcome_distances=[distout[j] for j in order],rank_weighted_outcome_distance=float(np.average([distout[j] for j in order],weights=1/np.arange(1,len(order)+1))) if order else None) for arm,order in [('numeric8',row['numeric8']),('numericD1_8',row['numericD1_8']),('astra8',rec['rank'] if rec['valid'] else [])]}
        case=dict(id=r['id'],fold=r['fold'],origin=r['origin'],truth=truths[i],daily90=r['daily90'],forecasts={},wave_cluster=row['wave_cluster'] if row else None,candidate_outcome_rank_diagnostic=diagnostic)
        for arm,(local,kind,fallback) in specs.items():
            w=weights(pool,local,kind);dp,q,t=empirical(truths,w);ww=np.asarray(list(w.values()));case['forecasts'][arm]=dict(D=dp.tolist(),Q=q.tolist(),touch=t.tolist(),loss=e.forecast_scores(dp,q,t,truths[i]),upper_sensitivity=e.forecast_scores(dp,q,t,truths[i],1),fallback=fallback,pool_count=len(pool),local_ids=[events[j]['id'] for j in local],n_eff=float(ww.sum()**2/np.sum(ww**2)),daily90_cell_count=len(cell),daily90_conditional_weight=len(cell)/(len(cell)+32),weights={events[j]['id']:v for j,v in w.items()})
        all198.append(case)
        if row:cases.append(case)
        e.guard(began)
    if len(cases)!=sum(r['phase']=='evaluation' for r in fr['rows']):raise ValueError('ALL_SELECTED_IDS_REQUIRED')
    comp={control:compare(cases,'astra8',control) for control in ('numeric8','numericD1_8')};dailycomp={control:compare(all198,'daily90',control) for control in ('prior','phase32')};gate=all(dailycomp['prior'][k]['primary_14d']['pass_rule'] and dailycomp['phase32'][k]['primary_14d']['mean']<=0 for k in ('TP','SL'));improved=all(comp['numeric8'][k]['primary_14d']['mean']<0 for k in ('TP','SL'))
    result=dict(status='EXPLORATORY_RANK_IMPROVEMENT' if improved else 'NO_SKILL_THIS_CONFIGURATION',population='EXPLORATORY_DEVELOPMENT_SEEN_HISTORY',query_count=len(cases),fold_counts=dict(Counter(c['fold'] for c in cases)),metrics=summarize(cases,ARMS),comparisons=comp,daily90_all198=dict(metrics=summarize(all198,('prior','daily90','phase32')),comparisons=dailycomp,formal_gate=gate),daily90_selected24_comparisons={control:compare(cases,'daily90',control) for control in ('prior','phase32')},cases=cases,all198_cases=all198,labels_reused=370,target_paths_computed=0,label_source_sha256=e.digest(p['labels']),wave_clusters=dict(Counter(str(c['wave_cluster']) for c in cases)),d1_missing_queries=sum(r['d1_missing'] for r in fr['rows'] if r['phase']=='evaluation'),model=fr['model'],reasoning=fr['reasoning'],actual_response_files=sealed['actual_response_files'],actual_dispatch_attempts=sealed['actual_dispatch_attempts'],valid_evaluation_responses=sealed['valid'],protocol_sha256=e.digest(protocol),seal_sha256=e.digest(output/'evaluation-sealed.json'),elapsed_seconds=time.monotonic()-began,economic_evaluation=False,automatic_expansion=False,limitations=['24 selected H1 reversal events are dependent within wave clusters; no large-wave forecast validation','14/28d intervals are descriptive, cannot establish 100–200d cycle robustness','All history previously studied; no independent holdout or unseen-data claim','No ROI/DD/execution or trading inference; no automatic recipe rescue or expansion'])
    write(output/'RESULTS.json',result);export(output,cases,result['metrics']);export(output,all198,result['daily90_all198']['metrics'],'all198_')
    lines=['# Astra bounded rank screen','',result['status'],'','| Arm | TP pinball18 | SL Brier6 | Fallback |','|---|---:|---:|---:|']
    for arm,m in result['metrics'].items():lines.append(f"| {arm} | {m['all_ID']['TP']:.9f} | {m['all_ID']['SL']:.9f} | {m['fallbacks']} |")
    lines+=['',f"Actual response files: {sealed['actual_response_files']}/26; model gpt-6-astra/max. All370 saved labels reused; zero target recomputations. DAILY90 all198 formal gate: {gate}.",'',*result['limitations'],'','All24 IDs, paired co-primary14/28d CIs, folds, actual forecasts/truth, n_eff, reuse, frequencies, quantiles and post-seal candidate outcome ordering are retained in RESULTS.json and CSV. No automatic expansion within or beyond cap26.']
    (output/'findings.md').write_text('\n'.join(lines)+'\n');return {k:result[k] for k in ('status','query_count','actual_response_files','elapsed_seconds')}

def export(output,cases,metrics,prefix=''):
    rows=[]
    for c in cases:
        for arm,f in c['forecasts'].items():
            row=dict(id=c['id'],fold=c['fold'],origin=c['origin'],arm=arm,TP=f['loss']['TP'],SL=f['loss']['SL'],fallback=f['fallback'],pool_count=f['pool_count'],n_eff=f['n_eff'],cell_count=f['daily90_cell_count'],wave_cluster=c['wave_cluster'])
            for s in range(2):
                for j in range(3):
                    k=f's{s}_sl{j}';row[k+'_touch']=f['touch'][s][j];row[k+'_actual']=c['truth']['touch'][s][j];row[k+'_truth_low']=c['truth']['Q'][s][j][0];row[k+'_truth_up']=c['truth']['Q'][s][j][1]
                    for a in range(3):row[k+f'_q{a}']=f['Q'][s][j][a]
            rows.append(row)
    with (output/(prefix+'forecasts.csv')).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    rows=[]
    for arm,m in metrics.items():
        for s in range(2):
            for j in range(3):
                for k in range(3):rows.append(dict(arm=arm,side=('long','short')[s],SL=(.75,1,1.5)[j],quantile=(.2,.5,.8)[k],pinball=m['TP_pinball_coordinates'][s][j][k],quantile_hit_rate=m['TP_quantile_hit_rates'][s][j][k],positive_count=m['TP_positive_denominators'][s][j][k],zero_count=m['TP_zero_counts'][s][j][k],attained_lower=m['TP_attained_lower'][s][j][k],attained_upper=m['TP_attained_upper'][s][j][k],Brier=m['SL_rows'][s][j]))
    with (output/(prefix+'accuracy.csv')).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(RuntimeError('WALL_LIMIT')));signal.alarm(1800)
    if any(int(os.environ.get(v,'1'))>4 for v in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS')):raise ValueError('THREAD_LIMIT')
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('preflight','prepare','seal','score'));p.add_argument('--base',type=Path,default=Path('reports/btc-pattern-pilot-m2-20261021'));p.add_argument('--output',type=Path,required=True);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--go-protocol-sha');p.add_argument('--phase',choices=('debug','evaluation'),default='evaluation');a=p.parse_args()
    if a.stage=='preflight':res=preflight(a.base,a.output,a.protocol);res={k:v for k,v in res.items() if k!='pins'}
    elif a.stage=='prepare':res=prepare(a.base,a.output,a.protocol,a.go_protocol_sha)
    elif a.stage=='seal':res=seal(a.output,a.protocol,a.phase)
    else:res=score(a.base,a.output,a.protocol)
    print(json.dumps(res))
if __name__=='__main__':main()
