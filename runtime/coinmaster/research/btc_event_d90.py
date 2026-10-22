"""One preregistered retrospective D90 conditional-prior experiment."""
from __future__ import annotations
import argparse, copy, csv, hashlib, json, os, signal, time
from collections import Counter
from pathlib import Path
import numpy as np
from . import btc_event_research as e

ARMS=('prior','phase','daily90')

def daily_context(minutes, origins):
    """Completed UTC D1 endpoints only; validate the complete finite raw prefix."""
    bars=minutes.reshape(-1,1440,5)
    bad=(~np.isfinite(bars).all((1,2)) | (bars[:,:,:4].min((1,2))<=0)
         | (bars[:,:,4].min(1)<0) | (bars[:,:,2]>np.minimum(bars[:,:,0],bars[:,:,3])).any(1)
         | (bars[:,:,1]<np.maximum(bars[:,:,0],bars[:,:,3])).any(1))
    closes=bars[:,-1,3]; endpoints=e.WARM+np.arange(1,len(bars)+1)*e.DAY
    out=[]
    for origin in origins:
        j=int(np.searchsorted(endpoints,origin,side='right')-1)
        endpoint=(origin//e.DAY)*e.DAY
        support=int(endpoint-91*e.DAY)
        state=None;ret=None
        if j>=90 and not bad[j-90:j+1].any():
            ret=float(np.log(closes[j])-np.log(closes[j-90]))
            state=1 if ret>0 else -1 if ret<0 else None
        out.append(dict(state=state,logreturn90=ret,endpoint=int(endpoint),input_start=support))
    return out

def revised_events(events,contexts):
    rows=copy.deepcopy(events)
    for row,ctx in zip(rows,contexts):
        row['original_input_start']=row['input_start']
        row['input_start']=min(e.direct_input_start(row,row['input_start']),ctx['input_start'])
        row['daily90']=ctx
    return rows

def query_indices(events):
    return [i for fold,a,b in e.FOLDS for i,r in enumerate(events)
            if e.ms(a)<=r['origin']<e.ms(b) and r['label_end']<=e.ms(b)]

def validate_truth(truth):
    q=np.asarray(truth['Q']);t=np.asarray(truth['touch'])
    if q.shape!=(2,3,2) or t.shape!=(2,3) or not np.isfinite(q).all() or not np.isfinite(t).all() or (q<0).any() or (q[:,:,1]<q[:,:,0]).any() or not np.isin(t,[0,1]).all() or truth['D'] not in (-1,0,1,2):
        raise ValueError('INVALID_TRUTH_NO_FORECAST')

def weighted_empirical(truths,pool,cell):
    # One weight vector for every outcome, including duplicate global/cell labels.
    ids=list(cell)+list(pool)
    if not len(pool):raise ValueError('EMPTY_EVENT_PRIOR_INFEASIBLE')
    for i in ids:validate_truth(truths[i])
    w=np.r_[np.ones(len(cell)),np.full(len(pool),32/len(pool))]
    q=np.asarray([truths[i]['Q'] for i in ids])[:,:,:,0]
    touch=np.asarray([truths[i]['touch'] for i in ids]);d=np.asarray([truths[i]['D'] for i in ids])
    prob=np.array([w[d==j].sum() for j in range(3)])
    if not prob.sum():raise ValueError('EMPTY_UNAMBIGUOUS_DIRECTION_PRIOR')
    return prob/prob.sum(),e.weighted_quantiles(q,w),np.average(touch,axis=0,weights=w)

def predict(events,inputs,truths,i,cutoff):
    pool=e.eligible(events,i,cutoff)
    for j in pool:validate_truth(truths[int(j)])
    for arm in ('state','phase'):
        if not np.isfinite(inputs[arm][np.r_[pool,i]]).all():raise ValueError('INVALID_FEATURE_NO_FORECAST')
    prior=e.empirical(truths,pool)
    st=inputs['state'];scale=st[pool].std(0);scale[scale<=1e-12]=1
    ds=np.mean(((st[pool]-st[i])/scale)**2,axis=1)
    distance=.5*ds+.5*np.mean((inputs['phase'][pool]-inputs['phase'][i])**2,axis=1)
    chosen=e.choose(distance,pool,events);ok=len(chosen)>=8
    state=events[i]['daily90']['state']
    cell=[int(j) for j in pool if state in (-1,1) and events[j]['daily90']['state']==state]
    return dict(prior=dict(arrays=prior,supported=True,neighbors=[],pool=pool.tolist()),
                phase=dict(arrays=e.empirical(truths,pool,chosen) if ok else prior,supported=ok,neighbors=chosen,pool=pool.tolist()),
                daily90=dict(arrays=weighted_empirical(truths,pool,cell) if cell else prior,supported=bool(cell),neighbors=cell,pool=pool.tolist(),state=state,cell_count=len(cell),global_count=len(pool),conditional_weight=len(cell)/(len(cell)+32),global_only_missing_state=sum(events[j]['daily90']['state'] is None for j in pool)))

def pins(prepared,reference):
    paths=[Path(__file__),Path(e.__file__),Path(e.targets.__code__.co_filename),Path(e.features_at.__code__.co_filename),prepared/'manifest.json']
    paths += [reference/n for n in ('PROTOCOL.json','catalogue.json','inputs.npz','RESULTS.json')]
    return {str(p.resolve()):e.digest(p) for p in paths}

MUTABLE_OUTPUTS=('catalogue.json','PREFLIGHT.json','ATTEMPT.json','labels.json','RESULTS.json','REPORT.md','case_arm_forecasts.csv','accuracy.csv')

def check_outputs(prepared,reference,output,stage):
    out=output.resolve()
    for source in (prepared.resolve(),reference.resolve()):
        if out==source or out in source.parents or source in out.parents:
            raise ValueError('OUTPUT_SOURCE_OVERLAP')
    names=MUTABLE_OUTPUTS if stage=='prepare' else MUTABLE_OUTPUTS[2:]
    for name in names:
        if (output/name).exists() or (output/name).is_symlink():
            raise ValueError('OUTPUT_ALREADY_EXISTS:'+name)

def prepare(prepared,reference,output,protocol):
    check_outputs(prepared,reference,output,'prepare')
    started=time.monotonic();manifest,minutes,_,bad=e.load_market(prepared)
    events=json.loads((reference/'catalogue.json').read_text())['events']
    ctx=daily_context(minutes,[r['origin'] for r in events]);rows=revised_events(events,ctx)
    saved=json.loads((reference/'RESULTS.json').read_text());ids=[rows[i]['id'] for i in query_indices(rows)]
    if ids!=[r['id'] for r in saved['cases']] or len(ids)!=198 or len(rows)!=372:raise ValueError('ORIGINAL_IDS_REQUIRED')
    frozen=pins(prepared,reference);support=[]
    for i in query_indices(rows):
        r=rows[i];cut=next(e.ms(a) for f,a,b in e.FOLDS if f==r['fold']);pool=e.eligible(rows,i,cut)
        cell=[int(j) for j in pool if ctx[i]['state'] in (-1,1) and ctx[j]['state']==ctx[i]['state']]
        support.append(dict(id=r['id'],fold=r['fold'],state=ctx[i]['state'],global_count=len(pool),cell_count=len(cell),conditional_weight=len(cell)/(len(cell)+32),missing_historical_states=sum(ctx[j]['state'] is None for j in pool)))
    # Hash only the authorized bounded minute view; no CHECK/post-May1 values read.
    bounded_sha=hashlib.sha256(np.ascontiguousarray(minutes).tobytes()).hexdigest()
    e.write(output/'catalogue.json',dict(events=rows,registry=json.loads((reference/'catalogue.json').read_text())['registry']))
    receipt=dict(status='IMPLEMENTED_NOT_EVALUATED',protocol_sha256=e.digest(protocol),pins=frozen,bounded_minutes_sha256=bounded_sha,catalogue_sha256=e.digest(output/'catalogue.json'),period_days=699,event_count=len(rows),query_ids=ids,query_count=len(ids),fold_counts=dict(Counter(r['fold'] for r in saved['cases'])),support=support,bad_minutes=bad,resource_estimate=dict(threads=4,max_rss_gib=6,hard_wall_seconds=1800,expected_wall_seconds=180,expected_rss_gib=1),labels_recomputed=False,new_forecasts=False,elapsed_seconds=time.monotonic()-started)
    e.guard(started);e.write(output/'PREFLIGHT.json',receipt);return {k:receipt[k] for k in ('status','query_count','elapsed_seconds')}

def gate(comparisons):
    prior=all(comparisons['prior'][k]['primary_14d']['pass_rule'] for k in ('TP','SL'))
    phase=all(comparisons['phase'][k]['primary_14d']['mean']<=0 for k in ('TP','SL'))
    return dict(pass_rule=bool(prior and phase),prior_both_paired_14d_pass=prior,phase_both_mean_nonworse=phase,phase_noninferiority='descriptive mean only; no equivalence claim')

def evaluate(prepared,reference,output,protocol,go_protocol_sha):
    check_outputs(prepared,reference,output,'evaluate')
    started=time.monotonic();qa=json.loads((output/'PREFLIGHT.json').read_text())
    if go_protocol_sha!=e.digest(protocol) or go_protocol_sha!=qa['protocol_sha256']:raise ValueError('ROOT_GO_PROTOCOL_IDENTITY_REQUIRED')
    if pins(prepared,reference)!=qa['pins'] or e.digest(output/'catalogue.json')!=qa['catalogue_sha256']:raise ValueError('PREFLIGHT_PIN_DRIFT')
    # Exclusive attempt receipt prevents all automatic retries, including partial failures.
    with (output/'ATTEMPT.json').open('x') as f:json.dump(dict(protocol_sha256=go_protocol_sha,started_utc=e.datetime.now(e.timezone.utc).isoformat()),f)
    _,minutes,_,_=e.load_market(prepared)
    if hashlib.sha256(np.ascontiguousarray(minutes).tobytes()).hexdigest()!=qa['bounded_minutes_sha256']:raise ValueError('BOUNDED_INPUT_DRIFT')
    events=json.loads((output/'catalogue.json').read_text())['events'];inputs=dict(np.load(reference/'inputs.npz'))
    saved=json.loads((reference/'RESULTS.json').read_text());savedtruth={r['id']:r['truth'] for r in saved['cases']};truths={}
    for i,r in enumerate(events):
        if r['label_end']>e.END:continue
        j=(r['entry_time']-e.WARM)//e.MINUTE;computed=e.targets(minutes[j:j+4320],r['sigma72'])
        if r['id'] in savedtruth:
            if computed!=savedtruth[r['id']]:raise ValueError('SAVED_TARGET_SEMANTICS_DRIFT')
            truths[i]=savedtruth[r['id']]
        else:truths[i]=computed
        validate_truth(truths[i]);e.guard(started)
    e.write(output/'labels.json',{events[i]['id']:v for i,v in truths.items()})
    cases=[]
    for i in query_indices(events):
        r=events[i];cut=next(e.ms(a) for f,a,b in e.FOLDS if f==r['fold']);forecast=predict(events,inputs,truths,i,cut);case=dict(id=r['id'],origin=r['origin'],fold=r['fold'],input_start=r['input_start'],daily90=r['daily90'],truth=truths[i],forecasts={})
        for arm,f in forecast.items():
            p,q,t=f.pop('arrays');case['forecasts'][arm]=dict(**f,D=p.tolist(),Q=q.tolist(),touch=t.tolist(),loss=e.forecast_scores(p,q,t,truths[i]),upper_sensitivity=e.forecast_scores(p,q,t,truths[i],1),display=e.display(p,q,t))
        cases.append(case);e.guard(started)
    if [c['id'] for c in cases]!=qa['query_ids']:raise ValueError('ALL_198_IDS_REQUIRED')
    origins=[c['origin'] for c in cases];foldids=[c['fold'] for c in cases];metrics={}
    y=np.asarray([c['truth']['Q'] for c in cases]);ty=np.asarray([c['truth']['touch'] for c in cases])
    for arm in ARMS:
        fs=[c['forecasts'][arm] for c in cases];q=np.asarray([f['Q'] for f in fs]);t=np.asarray([f['touch'] for f in fs]);pos=q>0;den=pos.sum(0)
        def avg(field,mask=None):
            selected=fs if mask is None else [f for f,m in zip(fs,mask) if m]
            return {k:float(np.mean([f[field][k] for f in selected])) if selected else None for k in ('TP','SL')}
        metrics[arm]=dict(query_count=len(cases),all_ID=avg('loss'),upper_sensitivity=avg('upper_sensitivity'),coverage=sum(f['supported'] for f in fs)/len(fs),fallbacks=sum(not f['supported'] for f in fs),by_fold={fold:avg('loss',[c['fold']==fold for c in cases]) for fold in sorted(set(foldids))},by_state={str(s):dict(count=sum(c['daily90']['state']==s for c in cases),loss=avg('loss',[c['daily90']['state']==s for c in cases])) for s in (-1,1,None)},TP_pinball_coordinates=None,TP_zero_counts=(~pos).sum(0).tolist(),TP_positive_denominators=den.tolist(),TP_attained_lower=((y[:,:,:,0,None]>=q)&pos).sum(0).tolist(),TP_attained_upper=((y[:,:,:,1,None]>=q)&pos).sum(0).tolist(),TP_quantile_hit_rates=(y[:,:,:,0,None]<=q).mean(0).tolist(),SL_rows=np.mean([f['loss']['SL_rows'] for f in fs],axis=0).tolist(),SL_calibration=[[e.calibration(t[:,s,j],ty[:,s,j]) for j in range(3)] for s in range(2)])
        err=y[:,:,:,0,None]-q;metrics[arm]['TP_pinball_coordinates']=np.maximum(err*np.array([.2,.5,.8]),err*(np.array([.2,.5,.8])-1)).mean(0).tolist()
    comparisons={}
    for control in ('prior','phase'):
        comparisons[control]={}
        for task in ('TP','SL'):
            delta=[c['forecasts']['daily90']['loss'][task]-c['forecasts'][control]['loss'][task] for c in cases]
            comparisons[control][task]=dict(primary_14d=e.block_ci(delta,origins,foldids,14),sensitivity_28d=e.block_ci(delta,origins,foldids,28))
    result=dict(schema='btc-event-d90.results.v1',status='D90_DEFINED_IMPROVEMENT' if gate(comparisons)['pass_rule'] else 'D90_NO_DEFINED_IMPROVEMENT',gate=gate(comparisons),query_count=len(cases),fold_counts=dict(Counter(foldids)),metrics=metrics,comparisons=comparisons,cases=cases,protocol_sha256=go_protocol_sha,pins=qa['pins'],labels_reused=len(savedtruth),labels_computed_missing=len(truths)-len(savedtruth),labels_overlap_verified=len(savedtruth),target_paths_computed=len(truths),elapsed_seconds=time.monotonic()-started,economic_evaluation=False,limitations=['Retrospective selected hypothesis after E1 postmortem; not independent confirmation','Daily state is fold-confounded; F3 has no positive90 state','14/28d bootstrap cannot establish 100–200d cycle robustness','Adverse touch is not traded stopout; no ROI/DD evaluation'])
    e.guard(started);e.write(output/'RESULTS.json',result)
    export_csv(output,cases,metrics)
    lines=['# D90 bounded retrospective research','',result['status'],'','All198 original IDs,372-event699-day catalogue; corrected common library support.','', '| Arm | TP pinball | SL Brier | Fallbacks |','|---|---:|---:|---:|']
    for arm in ARMS:
        m=metrics[arm];lines.append(f"| {arm} | {m['all_ID']['TP']:.9f} | {m['all_ID']['SL']:.9f} | {m['fallbacks']} |")
    lines+=['']+result['limitations']+['','All24 coordinates, positive/zero denominators, support counts, paired14/28d intervals and every query forecast are in RESULTS.json. No automatic follow-up experiment.']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n');return {k:result[k] for k in ('status','gate','query_count','elapsed_seconds')}

def export_csv(output,cases,metrics):
    rows=[]
    for c in cases:
        for arm in ARMS:
            f=c['forecasts'][arm];row=dict(id=c['id'],fold=c['fold'],origin=c['origin'],arm=arm,state=c['daily90']['state'],fallback=not f['supported'],TP_loss=f['loss']['TP'],SL_loss=f['loss']['SL'],pool_count=len(f['pool']),cell_count=len(f['neighbors']))
            for side in range(2):
                for sl in range(3):
                    key=f'side{side}_sl{sl}'
                    row[key+'_touch_probability']=f['touch'][side][sl];row[key+'_touch_actual']=c['truth']['touch'][side][sl]
                    row[key+'_truth_lower']=c['truth']['Q'][side][sl][0];row[key+'_truth_upper']=c['truth']['Q'][side][sl][1]
                    for k in range(3):row[key+f'_q{k}']=f['Q'][side][sl][k]
            rows.append(row)
    with (output/'case_arm_forecasts.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    rows=[]
    for arm in ARMS:
        m=metrics[arm]
        for side in range(2):
            for sl in range(3):
                for k in range(3):
                    den=m['TP_positive_denominators'][side][sl][k]
                    rows.append(dict(arm=arm,side=('long','short')[side],SL=(.75,1,1.5)[sl],quantile=(.2,.5,.8)[k],all_ID_count=len(cases),pinball=m['TP_pinball_coordinates'][side][sl][k],quantile_hit_rate=m['TP_quantile_hit_rates'][side][sl][k],TP_zero_count=m['TP_zero_counts'][side][sl][k],TP_positive_count=den,reach_lower=m['TP_attained_lower'][side][sl][k]/den if den else None,reach_upper=m['TP_attained_upper'][side][sl][k]/den if den else None,SL_Brier=m['SL_rows'][side][sl],SL_mean_probability=float(np.mean([c['forecasts'][arm]['touch'][side][sl] for c in cases])),SL_actual_touch_rate=float(np.mean([c['truth']['touch'][side][sl] for c in cases]))))
    with (output/'accuracy.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)

def main():
    def timeout(signum,frame):raise RuntimeError('TIME_BUDGET_EXCEEDED')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(1800)
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','evaluate']);p.add_argument('--prepared',type=Path,required=True);p.add_argument('--reference',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--go-protocol-sha');a=p.parse_args()
    if any(int(os.environ.get(v,'1'))>4 for v in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS','NUMEXPR_NUM_THREADS')):raise ValueError('THREAD_LIMIT')
    result=prepare(a.prepared,a.reference,a.output,a.protocol) if a.stage=='prepare' else evaluate(a.prepared,a.reference,a.output,a.protocol,a.go_protocol_sha)
    print(json.dumps(result))
if __name__=='__main__':main()
