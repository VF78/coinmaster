"""Preregistered causal BTC event catalogue and bounded E1; no execution engine."""
from __future__ import annotations
import argparse, hashlib, json, os, time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from .research_rss import peak_rss_bytes
from .btc_pattern_data import HOUR, MINUTE, DAY, FOLDS, ms, features_at
from .btc_pattern_inapp import targets, forecast_scores, block_ci, display, calibration, digest

START=ms('2024-06-01'); END=ms('2026-05-01'); WARM=ms('2024-05-15')

def write(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')

def guard(started):
    import resource
    rss=peak_rss_bytes(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    if time.monotonic()-started>1800: raise RuntimeError('TIME_BUDGET_EXCEEDED')
    if rss>6*1024**3: raise RuntimeError('RSS_BUDGET_EXCEEDED')

class Detector:
    """Incremental state; no hindsight relabelling of emitted queries."""
    def __init__(self):
        self.state=None; self.history=[]; self.events=[]; self.registry=[]; self.previous=None; self.sequence=0
    def feed(self,t,price,sigma):
        if self.previous is not None and t-self.previous!=HOUR:
            self.reset(t,'GAP_RESET')
        self.previous=t
        if not np.isfinite(price) or price<=0 or not np.isfinite(sigma) or sigma<=0:
            self.reset(t,'INVALID_OR_SCALE_WARMUP'); return
        p=float(np.log(price))
        if self.state is None:
            self.state=dict(direction=0,activation=t,anchor=t,anchor_log=p,extreme=t,extreme_log=p,low=t,low_log=p,delta=float(sigma),left=True)
            self.registry.append(dict(kind='UNKNOWN_INITIAL',time=t));return
        s=self.state; d=s['direction']
        if d==0:
            if p>s['extreme_log']:s.update(extreme=t,extreme_log=p)
            if p<s['low_log']:s.update(low=t,low_log=p)
            if p-s['low_log']>=s['delta']:
                s.update(direction=1,anchor=s['low'],anchor_log=s['low_log'],extreme=t,extreme_log=p)
            elif s['extreme_log']-p>=s['delta']:
                s.update(direction=-1,anchor=s['extreme'],anchor_log=s['extreme_log'],extreme=t,extreme_log=p)
            return
        if d*(p-s['extreme_log'])>0:s.update(extreme=t,extreme_log=p)
        if d*(s['extreme_log']-p)<s['delta']:return
        row=dict(id=f'E{self.sequence:05d}',origin=t,anchor=s['anchor'],anchor_log=s['anchor_log'],extreme=s['extreme'],extreme_log=s['extreme_log'],confirmation_log=p,direction=d,activation=s['activation'],delta=s['delta'],left_truncated=s['left'])
        self.sequence+=1
        if s['left']:self.registry.append(dict(kind='LEFT_TRUNCATED',**row))
        elif START<=t<END:self.events.append(row)
        self.state=dict(direction=-d,activation=t,anchor=s['extreme'],anchor_log=s['extreme_log'],extreme=t,extreme_log=p,delta=float(sigma),left=False)
    def reset(self,t,kind):
        if self.state is not None:self.registry.append(dict(kind=kind,time=t,state=self.state.copy()))
        self.state=None
    def finish(self,end):
        return self.registry+[dict(kind='RIGHT_CENSORED',time=end,state=self.state.copy())] if self.state else list(self.registry)

def shapes(t,logp,row,sigma):
    a,b,c=row['anchor'],row['extreme'],row['origin']
    keep=(t>=a)&(t<=c); tx=t[keep];px=logp[keep]
    clock=np.linspace(a,c,64);phase=np.r_[np.linspace(a,b,32),np.linspace(b,c,32)]
    interp=lambda x:(np.interp(x,tx,px)-row['anchor_log'])/sigma
    return interp(clock),interp(phase),[int(tx[0]),int(tx[-1])]

def direct_input_start(row, context_start):
    """Raw-bar support of anchor, context and frozen 168-return threshold."""
    return min(row['anchor']-HOUR, row['activation']-169*HOUR, context_start)

def eligible(events,i,cutoff):
    q=events[i]
    return np.array([j for j,r in enumerate(events) if r['label_end']<=min(cutoff,q['input_start']) and r['origin']<q['input_start']],dtype=int)

def choose(distance,ids,events):
    rank=ids[np.argsort(distance,kind='stable')];chosen=[]
    for j in rank:
        if all(abs(events[int(j)]['origin']-events[k]['origin'])>=72*HOUR for k in chosen):
            chosen.append(int(j))
            if len(chosen)==32:break
    return chosen

def load_market(prepared):
    manifest=json.loads((prepared/'manifest.json').read_text())
    if digest(prepared/'manifest.json')!='bc660056af9117a246a1334837b7e42c9bb2d0635945a0346a4b088a459685ff':
        raise ValueError('MANIFEST_IDENTITY_DRIFT')
    raw=np.load(prepared/'minutes.npy',mmap_mode='r')
    a=(WARM-manifest['minute_start'])//MINUTE;b=(END-manifest['minute_start'])//MINUTE
    v=raw[a:b];t=np.arange(WARM,END,MINUTE)
    if len(v)!=len(t):raise ValueError('SOURCE_RANGE')
    panels={};bad=~np.isfinite(v).all(1)|(v[:,:4].min(1)<=0)|(v[:,4]<0)|(v[:,2]>np.minimum(v[:,0],v[:,3]))|(v[:,1]<np.maximum(v[:,0],v[:,3]))
    for tf in (1,4):
        n=tf*60;bars=v.reshape(-1,n,5)
        x=np.column_stack((bars[:,0,0],bars[:,:,1].max(1),bars[:,:,2].min(1),bars[:,-1,3],bars[:,:,4].sum(1)))
        x[bad.reshape(-1,n).any(1)]=np.nan;panels[tf]=(t[::n],x)
    return manifest,v,panels,int(bad.sum())

def catalogue(prepared,output,protocol):
    began=time.monotonic();manifest,v,panels,bad=load_market(prepared)
    ht,hv=panels[1];ct=ht+HOUR;cl=hv[:,3];sigma=np.full(len(cl),np.nan)
    for j in range(168,len(cl)):
        r=np.diff(np.log(cl[j-168:j+1]));sigma[j]=np.std(r,ddof=1)*np.sqrt(24)
    detector=Detector()
    for t,p,s in zip(ct,cl,sigma):
        if t<END:detector.feed(int(t),float(p),float(s))
    events=detector.events;states=[];clock=[];phase=[];invalid=[]
    for r in events:
        f=features_at(panels,r['origin'])
        if f is None:invalid.append(r['id']);r['feature_valid']=False;continue
        _,ctx,_,_,ins,_=f;s=float(ctx[-2]);r['sigma24']=s;r['sigma72']=float(ctx[-1]);r['feature_valid']=True
        r['input_start']=direct_input_start(r, int(ins)-80*HOUR);r['entry_time']=r['origin']+MINUTE;r['label_end']=r['entry_time']+72*HOUR
        r['horizon_status']='MATURE' if r['label_end']<=END else 'RIGHT_CENSORED_HORIZON'
        r['fold']=next((name for name,a,b in FOLDS if ms(a)<=r['origin']<ms(b)),None)
        st=[r['direction'],r['direction']*(r['extreme_log']-r['anchor_log'])/s,np.log1p((r['extreme']-r['anchor'])/HOUR),np.log1p((r['origin']-r['extreme'])/HOUR),r['direction']*(r['confirmation_log']-r['extreme_log'])/s,r['delta']/s]
        c,p,support=shapes(ct,np.log(cl),r,s);r['shape_support']=support;r['confirmation_delay_hours']=(r['origin']-r['extreme'])/HOUR
        states.append(np.r_[ctx,st]);clock.append(c);phase.append(p)
        guard(began)
    if invalid:raise ValueError('INVALID_QUERY_FEATURES:'+','.join(invalid))
    output.mkdir(parents=True,exist_ok=True)
    np.savez(output/'inputs.npz',state=np.asarray(states),clock=np.asarray(clock),phase=np.asarray(phase))
    write(output/'catalogue.json',dict(events=events,registry=detector.finish(END)))
    support={}
    for name,a,b in FOLDS:
        ids=[i for i,r in enumerate(events) if r['fold']==name]
        counts=[len(choose(np.zeros(len(pool)),pool,events)) for i in ids for pool in [eligible(events,i,ms(a))]]
        support[name]=dict(queries=len(ids),mature_in_fold=sum(events[i]['label_end']<=ms(b) for i in ids),neighbor_count_min=min(counts,default=0),neighbor_count_median=float(np.median(counts)) if counts else 0,at_least8=sum(x>=8 for x in counts))
    summary=dict(period_days=(END-START)//DAY,events=len(events),by_month=dict(Counter(datetime.fromtimestamp(r['origin']/1000,timezone.utc).strftime('%Y-%m') for r in events)),by_direction=dict(Counter(str(r['direction']) for r in events)),registry=dict(Counter(r['kind'] for r in detector.finish(END))),bad_minutes=bad,horizon_censored=sum(r['horizon_status']!='MATURE' for r in events),fold_support=support,confirmation_delay_hours=dict(median=float(np.median([r['confirmation_delay_hours'] for r in events])),maximum=max(r['confirmation_delay_hours'] for r in events)),max_prefix_hours=max((r['origin']-r['anchor'])/HOUR for r in events),protocol_sha256=digest(protocol),manifest_sha256=digest(prepared/'manifest.json'),catalogue_sha256=digest(output/'catalogue.json'),input_sha256=digest(output/'inputs.npz'),quality_labels_read=False,elapsed_seconds=time.monotonic()-began)
    write(output/'CATALOGUE_QA.json',summary);return summary

def weighted_quantiles(values,weights,levels=(.2,.5,.8)):
    """Fixed weighted empirical inverse CDF, independently on each side/SL."""
    values=np.asarray(values);weights=np.asarray(weights,dtype=float)
    out=np.empty((*values.shape[1:],len(levels)))
    for ix in np.ndindex(values.shape[1:]):
        x=values[(slice(None),)+ix];order=np.argsort(x,kind='stable')
        cw=np.cumsum(weights[order]);cw/=cw[-1]
        out[ix]=x[order[np.minimum(np.searchsorted(cw,levels,side='left'),len(order)-1)]]
    return out

def empirical(truths,pool,neighbors=None):
    if not len(pool):raise ValueError('EMPTY_EVENT_PRIOR_INFEASIBLE')
    if neighbors is None:
        ids=list(pool);w=np.ones(len(ids))
    else:
        ids=list(neighbors)+list(pool);w=np.r_[np.ones(len(neighbors)),np.full(len(pool),8/len(pool))]
    q=np.asarray([truths[i]['Q'] for i in ids])[:,:,:,0]
    touch=np.asarray([truths[i]['touch'] for i in ids]);d=np.asarray([truths[i]['D'] for i in ids])
    prob=np.array([w[d==j].sum() for j in range(3)])
    if prob.sum()==0:raise ValueError('EMPTY_UNAMBIGUOUS_DIRECTION_PRIOR')
    return prob/prob.sum(),weighted_quantiles(q,w),np.average(touch,axis=0,weights=w)

def predict(events,inputs,truths,i,cutoff):
    pool=eligible(events,i,cutoff)
    prior=empirical(truths,pool);out={'prior':dict(arrays=prior,supported=True,neighbors=[],pool=pool.tolist())}
    # These are the exact same purged IDs used for every transformation and arm.
    st=inputs['state'];mu=st[pool].mean(0);scale=st[pool].std(0);scale[scale<=1e-12]=1
    ds=np.mean(((st[pool]-st[i])/scale)**2,axis=1)
    for arm in ('state','clock','phase'):
        distance=ds if arm=='state' else .5*ds+.5*np.mean((inputs[arm][pool]-inputs[arm][i])**2,axis=1)
        chosen=choose(distance,pool,events);supported=len(chosen)>=8
        out[arm]=dict(arrays=empirical(truths,pool,chosen) if supported else prior,supported=supported,neighbors=chosen,pool=pool.tolist())
    return out

def gate(metrics,comparisons):
    coverage=all(metrics[a]['coverage']>=.9 for a in ('state','clock','phase'))
    comparisons_ok=all(comparisons[control][task]['primary_14d']['pass_rule'] for control in ('prior','state','clock') for task in ('TP','SL'))
    return dict(pass_rule=bool(coverage and comparisons_ok),supported_coverage_pass=coverage,all_comparisons_pass=comparisons_ok,required='phase BOTH co-primary versus EACH prior/state/clock;14d upper95CI<0, >=2/3foldwins,>=2occupiedblocks/fold; state/clock/phase supportedcoverage>=.9')

def evaluate(prepared,output,protocol,go_protocol_sha):
    began=time.monotonic();qa=json.loads((output/'CATALOGUE_QA.json').read_text())
    if go_protocol_sha!=qa['protocol_sha256'] or digest(protocol)!=go_protocol_sha:raise ValueError('ROOT_GO_PROTOCOL_IDENTITY_REQUIRED')
    if digest(output/'catalogue.json')!=qa['catalogue_sha256'] or digest(output/'inputs.npz')!=qa['input_sha256']:raise ValueError('FROZEN_CATALOGUE_DRIFT')
    if (output/'RESULTS.json').exists():raise ValueError('SINGLE_E1_EVALUATION_ALREADY_EXISTS')
    # Only this explicit stage reads genuine target paths. No source labels.npz access.
    _,minutes,_,_=load_market(prepared)
    events=json.loads((output/'catalogue.json').read_text())['events'];inputs=dict(np.load(output/'inputs.npz'))
    truths={};registry=[]
    for i,r in enumerate(events):
        if r['label_end']>END:
            registry.append(dict(id=r['id'],status='RIGHT_CENSORED_HORIZON'));continue
        j=(r['entry_time']-WARM)//MINUTE;path=minutes[j:j+4320]
        if len(path)!=4320:raise ValueError('MATURE_LABEL_INCOMPLETE')
        truths[i]=targets(path,r['sigma72'])
        if truths[i]['D']==2:registry.append(dict(id=r['id'],status='OBSERVED_D_TIMEOUT_NO_FIRST_BARRIER'))
        guard(began)
    arms=('prior','state','clock','phase');cases=[];origins=[];foldids=[];loss={a:[] for a in arms};upper={a:[] for a in arms};preds={a:[] for a in arms};supported={a:[] for a in arms}
    for fold,cut,end in FOLDS:
        for i,r in enumerate(events):
            if not ms(cut)<=r['origin']<ms(end):continue
            if r['label_end']>ms(end):
                registry.append(dict(id=r['id'],status='FOLD_HORIZON_CENSORED',fold=fold));continue
            forecast=predict(events,inputs,truths,i,ms(cut));truth=truths[i]
            case=dict(id=r['id'],origin=r['origin'],fold=fold,input_start=r['input_start'],label_end=r['label_end'],truth=truth,forecasts={})
            for a in arms:
                f=forecast[a];p,q,t=f['arrays'];scores=forecast_scores(p,q,t,truth);sensitivity=forecast_scores(p,q,t,truth,1)
                # No query is dropped because a learned arm lacks support or displays NO_TRADE.
                loss[a].append(scores);upper[a].append(sensitivity);preds[a].append((p,q,t));supported[a].append(f['supported'])
                case['forecasts'][a]=dict(supported=f['supported'],fallback=not f['supported'],neighbor_ids=[events[j]['id'] for j in f['neighbors']],pool_ids=[events[j]['id'] for j in f['pool']],D=p.tolist(),Q=q.tolist(),touch=t.tolist(),loss=scores,upper_sensitivity=sensitivity,display=display(p,q,t))
            cases.append(case);origins.append(r['origin']);foldids.append(fold);guard(began)
    if not cases or set(foldids)!=set(x[0] for x in FOLDS):raise ValueError('MISSING_OUTER_FOLD')
    y=np.asarray([c['truth']['Q'] for c in cases]);touch_y=np.asarray([c['truth']['touch'] for c in cases]);metrics={}
    for a in arms:
        ps=np.asarray([x[0] for x in preds[a]]);qs=np.asarray([x[1] for x in preds[a]]);ts=np.asarray([x[2] for x in preds[a]]);valid=np.asarray(supported[a]);reuse=Counter(j for c in cases for j in c['forecasts'][a]['neighbor_ids'])
        metrics[a]=dict(query_count=len(cases),coverage=float(valid.mean()),fallbacks=int((~valid).sum()),all_ID={k:float(np.mean([x[k] for x in loss[a]])) for k in ('TP','SL')},upper_sensitivity={k:float(np.mean([x[k] for x in upper[a]])) for k in ('TP','SL')},covered_only={k:float(np.mean([x[k] for x,v in zip(loss[a],valid) if v])) if valid.any() else None for k in ('TP','SL')},TP_rows=np.mean([x['TP_rows'] for x in loss[a]],axis=0).tolist(),SL_rows=np.mean([x['SL_rows'] for x in loss[a]],axis=0).tolist(),TP_zero_counts=(qs==0).sum(0).tolist(),TP_positive_denominators=(qs>0).sum(0).tolist(),TP_attained_lower=((y[:,:,:,0,None]>=qs)&(qs>0)).sum(0).tolist(),TP_attained_upper=((y[:,:,:,1,None]>=qs)&(qs>0)).sum(0).tolist(),TP_quantile_hit_rates=(y[:,:,:,0,None]<=qs).mean(0).tolist(),TP_mean_errors=(qs-y[:,:,:,0,None]).mean(0).tolist(),SL_calibration=[[calibration(ts[:,s,j],touch_y[:,s,j]) for j in range(3)] for s in range(2)],D_logloss=float(np.mean([x['D_logloss'] for x in loss[a] if x['D_logloss'] is not None])),D_accuracy=float(np.mean([x['D_correct'] for x in loss[a] if x['D_correct'] is not None])),NO_TRADE=sum(c['forecasts'][a]['display']['status']=='NO_TRADE' for c in cases),neighbor_unique_events=len(reuse),neighbor_max_reuse=max(reuse.values(),default=0),neighbor_top10_share=sum(x for _,x in reuse.most_common(10))/max(sum(reuse.values()),1))
    # Secondary TP1/2/3 reach bounds at every common side/SL; zeros are explicit.
    for a in arms:
        m=metrics[a];den=np.asarray(m['TP_positive_denominators']);lo=np.asarray(m['TP_attained_lower']);hi=np.asarray(m['TP_attained_upper'])
        m['TP_reach_before_SL']=dict(axes=['side:long,short','SL:.75,1,1.5','TP1:q20,TP2:q50,TP3:q80'],positive_denominators=den.tolist(),zero_level_mass=(np.asarray(m['TP_zero_counts'])/len(cases)).tolist(),lower_rate=np.divide(lo,den,out=np.zeros_like(lo,dtype=float),where=den>0).tolist(),upper_rate=np.divide(hi,den,out=np.zeros_like(hi,dtype=float),where=den>0).tolist(),zero_denominator='rate0 means unavailable; inspect denominator; zero-level TP excluded from positive reach denominator',all_query_ID_count=len(cases))
    comparisons={}
    for control in ('prior','state','clock'):
        comparisons[control]={}
        for task in ('TP','SL'):
            delta=np.asarray([x[task] for x in loss['phase']])-np.asarray([x[task] for x in loss[control]])
            comparisons[control][task]=dict(primary_14d=block_ci(delta,origins,foldids,14),sensitivity_28d=block_ci(delta,origins,foldids,28))
    result=dict(schema='btc-event-e1.results.v1',status='E1_IMPROVEMENT' if gate(metrics,comparisons)['pass_rule'] else 'E1_NO_DEFINED_IMPROVEMENT',protocol_sha256=go_protocol_sha,catalogue_sha256=qa['catalogue_sha256'],source_sha256=digest(__file__),gate=gate(metrics,comparisons),query_count=len(cases),fold_counts=dict(Counter(foldids)),metrics=metrics,comparisons=comparisons,ambiguous_D=sum(c['truth']['D']<0 for c in cases),registry=registry,cases=cases,quality_labels_read=True,economic_evaluation=False,adverse_touch_is_traded_stopout=False,elapsed_seconds=time.monotonic()-began)
    write(output/'RESULTS.json',result)
    text=['# E1 frozen event analogue verification','',result['status'],f"{len(cases)} outer queries; folds {result['fold_counts']}. All IDs including fallback and NO_TRADE are scored.",'','| Arm | TP pinball | SL touch Brier | Supported | Fallback | NO_TRADE |','|---|---:|---:|---:|---:|---:|']
    for a in arms:
        m=metrics[a];text.append(f"| {a} | {m['all_ID']['TP']:.6f} | {m['all_ID']['SL']:.6f} | {m['coverage']:.1%} | {m['fallbacks']} | {m['NO_TRADE']} |")
    for a in arms:
        m=metrics[a];z=m['TP_reach_before_SL'];text+=['',f'## {a}: TP reaches before SL, positive levels only','', '| Side | SL | TP1 lower–upper (N) | TP2 lower–upper (N) | TP3 lower–upper (N) |','|---|---:|---:|---:|---:|']
        for side in range(2):
            for j,sl in enumerate((.75,1,1.5)):
                vals=[f"{z['lower_rate'][side][j][k]:.1%}–{z['upper_rate'][side][j][k]:.1%} ({z['positive_denominators'][side][j][k]})" for k in range(3)]
                text.append('| '+('long' if side==0 else 'short')+' | '+str(sl)+' | '+' | '.join(vals)+' |')
        text+=['', 'Zero-level TP counts (same side/SL/TP order): '+json.dumps(m['TP_zero_counts'])+'. Every arm scores the same full query population; zero levels remain in proper losses and are disclosed separately from positive-level reach denominators.']
    text+=['','Primary gate requires phase improvement for both metrics against all three controls. Paired14d and28d1000-draw within-fold block intervals, row-level calibration, positive TP denominators/bounds, event-neighbor concentration and all predictions are in RESULTS.json.','', 'Adverse touch is a full72h path target, not an actual traded stopout. No ROI, native execution or live inference is established.']
    (output/'REPORT.md').write_text('\n'.join(text)+'\n')
    return {k:result[k] for k in ('status','query_count','fold_counts','gate','elapsed_seconds')}

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['catalogue','evaluate']);p.add_argument('--prepared',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--protocol',type=Path,required=True);p.add_argument('--go-protocol-sha');a=p.parse_args()
    if a.stage=='catalogue': print(json.dumps(catalogue(a.prepared,a.output,a.protocol)))
    else: print(json.dumps(evaluate(a.prepared,a.output,a.protocol,a.go_protocol_sha)))

if __name__=='__main__':main()
