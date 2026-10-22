"""Retrospective exploratory arithmetic on SAVED E1 only; no forecasting/training/market reads."""
import json, csv, hashlib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
BASE=Path(__file__).resolve().parent; SRC=BASE.parent/'event-e1-20261022'
r=json.load(open(SRC/'RESULTS.json')); cat=json.load(open(SRC/'catalogue.json'))['events']; inp=np.load(SRC/'inputs.npz')
cases=r['cases']; ev={e['id']:e for e in cat}; idx={e['id']:i for i,e in enumerate(cat)}; n=len(cases); arms=['prior','state','clock','phase']
y=np.array([c['truth']['Q'] for c in cases])[...,0,None]; z=np.array([c['truth']['touch'] for c in cases]); taus=np.array([.2,.5,.8]);
q={a:np.array([c['forecasts'][a]['Q'] for c in cases]) for a in arms}; p={a:np.array([c['forecasts'][a]['touch'] for c in cases]) for a in arms}
p['fixed_shrink25']=.75*p['prior']+.25*p['phase'];q['fixed_shrink25']=.75*q['prior']+.25*q['phase']; arms+=['fixed_shrink25']
def pin(pred):
 e=y-pred;return np.maximum(taus*e,(taus-1)*e)
lp={a:pin(q[a]) for a in arms}; ls={a:(p[a]-z)**2 for a in arms};d=p['phase']-p['prior'];res=z-p['prior']
fold=np.array([c['fold'] for c in cases]);month=np.array([datetime.fromtimestamp(c['origin']/1000,timezone.utc).strftime('%Y-%m') for c in cases]);rows=[]
def avg(x):return float(np.mean(x))
def summary(mask):
 return {a:{'TP':avg(lp[a][mask]),'SL':avg(ls[a][mask]),'TP_delta_prior':avg(lp[a][mask]-lp['prior'][mask]),'SL_delta_prior':avg(ls[a][mask]-ls['prior'][mask]),'TP_quantile_hit':np.mean(y[mask]<=q[a][mask],axis=(0,1,2)).tolist(),'SL_prediction_mean':avg(p[a][mask]),'SL_observed_mean':avg(z[mask]),'SL_prediction_bias':avg(p[a][mask]-z[mask])} for a in arms}
S={'classification':'RETROSPECTIVE_EXPLORATORY_NO_NEW_MODEL_OR_MARKET_RUN','source_sha256':{name:hashlib.sha256((SRC/name).read_bytes()).hexdigest() for name in ['RESULTS.json','PROTOCOL.json','catalogue.json','inputs.npz']},'n':n,'overall':summary(np.ones(n,bool)),'folds':{},'months':{}}
for key,vals in [('fold',fold),('month',month)]:
 for v in sorted(set(vals)):
  mask=vals==v;S[key+'s'][v]={'n':int(mask.sum()),'metrics':summary(mask),'brier_adjustment':{'variance_cost':avg(d[mask]**2),'alignment_credit':avg(2*d[mask]*res[mask]),'net':avg(d[mask]**2-2*d[mask]*res[mask])}}
  for a in arms:
   for side in range(2):
    for sl in range(3):
     rows.append(dict(group=key,value=v,n=int(mask.sum()),arm=a,side=['long','short'][side],SL=[.75,1,1.5][sl],quantile='all',TP=avg(lp[a][mask,side,sl]),SL_Brier=avg(ls[a][mask,side,sl]),deltaTP=avg(lp[a][mask,side,sl]-lp['prior'][mask,side,sl]),deltaSL=avg(ls[a][mask,side,sl]-ls['prior'][mask,side,sl])))
S['brier_decomposition']={'variance_cost':avg(d*d),'alignment_credit':avg(2*d*res),'net':avg(d*d-2*d*res),'adjustment_rms':float(np.sqrt(avg(d*d))),'residual_adjustment_correlation':float(np.corrcoef(d.ravel(),res.ravel())[0,1]),'fixed_shrink25_cost':avg((.25*d)**2),'fixed_shrink25_credit':avg(2*.25*d*res)}
S['dimensions']={}
for dimension,ax,labels in [('side',1,['long','short']),('SL',2,[.75,1,1.5]),('quantile',3,[.2,.5,.8])]:
 S['dimensions'][dimension]={}
 for j,label in enumerate(labels):
  sel=[slice(None)]*4;sel[ax]=j;sel=tuple(sel)
  S['dimensions'][dimension][str(label)]={a:{'TP':avg(lp[a][sel]),'TP_delta_prior':avg(lp[a][sel]-lp['prior'][sel]),**({'SL':avg(np.take(ls[a],j,axis=ax)),'SL_delta_prior':avg(np.take(ls[a]-ls['prior'],j,axis=ax))} if ax<3 else {})} for a in arms}
S['concentration']={}
for target,loss in [('TP',lp),('SL',ls)]:
 delta=np.mean(loss['phase']-loss['prior'],axis=tuple(range(1,loss['prior'].ndim))); ordered=np.argsort(delta)[::-1]; pos=np.maximum(delta,0)
 S['concentration'][target]={'event_worsen_count':int((delta>0).sum()),'event_improve_count':int((delta<0).sum()),'top10_share_positive_excess':float(pos[ordered[:10]].sum()/pos.sum()),'mean_delta_excluding_worst10':avg(np.delete(delta,ordered[:10])),'worst10':[{'id':cases[i]['id'],'fold':cases[i]['fold'],'delta':float(delta[i])} for i in ordered[:10]]}
S['event_relationships']={}
E=[ev[c['id']] for c in cases];features={'direction':np.array([e['direction'] for e in E]),'correction_depth_sigma24':np.array([-e['direction']*(e['confirmation_log']-e['extreme_log'])/e['sigma24'] for e in E]),'correction_delay_hours':np.array([e['confirmation_delay_hours'] for e in E]),'impulse_duration_hours':np.array([(e['extreme']-e['anchor'])/3600000 for e in E]),'vol_ratio_frozen_delta_to_query_sigma24':np.array([e['delta']/e['sigma24'] for e in E])}
for name,x in features.items():
 # Descriptive median split, no parameter search or derived forecasting rule.
 cut=float(np.median(x));S['event_relationships'][name]={'median':cut,'groups':{}}
 for label,mask in ([('down',x==-1),('up',x==1)] if name=='direction' else [('low',x<=cut),('high',x>cut)]):
  S['event_relationships'][name]['groups'][label]={'n':int(mask.sum()),'metrics':summary(mask),'prior_SL_residual_by_side_SL':np.mean(res[mask],0).tolist(),'prior_TP_mean_residual_by_side_SL':np.mean((y-q['prior'])[mask],0).tolist(),'actual_MFE_mean':avg(y[mask]),'brier_cost':avg(d[mask]**2),'brier_credit':avg(2*d[mask]*res[mask])}
S['neighbors']={}
for a in ['state','clock','phase']:
 counts=[];matches=[];shape=[];outcomes=[];reuse=Counter(); overlaps=[]
 for i,c in enumerate(cases):
  ids=c['forecasts'][a]['neighbor_ids'];counts.append(len(ids));reuse.update(ids);ei=ev[c['id']]
  matches.append(avg([ev[j]['direction']==ei['direction'] for j in ids]));shape.append(avg([np.mean((inp['phase'][idx[j]]-inp['phase'][idx[c['id']]])**2) for j in ids]))
  old={cc['id']:cc for cc in cases if cc['id'] in ids}
  for cc in old.values():
   outcomes.append(avg(np.abs(np.array(cc['truth']['Q'])[...,0]-y[i,...,0])));overlaps.append((i,cc['id']))
 S['neighbors'][a]={'count_min':min(counts),'count_median':float(np.median(counts)),'count_max':max(counts),'unique':len(reuse),'max_reuse':max(reuse.values()),'top10_share':sum(x for _,x in reuse.most_common(10))/sum(counts),'same_direction_mean':avg(matches),'phase_shape_MSE_mean':avg(shape),'outcome_MFE_MAE_only_saved_eval_overlap':avg(outcomes) if outcomes else None,'eval_overlap_pairs':len(overlaps),'shape_MSE_correlation_TP_excess':float(np.corrcoef(shape,np.mean(lp[a]-lp['prior'],axis=(1,2,3)))[0,1]),'shape_MSE_correlation_SL_excess':float(np.corrcoef(shape,np.mean(ls[a]-ls['prior'],axis=(1,2)))[0,1])}
# Pinball deltas partition: fixed arithmetic blend improves/worsens per forecast cell and event.
S['pinball_adjustment']={}
for a in ['phase','fixed_shrink25']:
 delta=lp[a]-lp['prior'];S['pinball_adjustment'][a]={'mean_delta':avg(delta),'improving_cells':int((delta<0).sum()),'worsening_cells':int((delta>0).sum()),'improvement_credit':avg(np.minimum(delta,0)),'worsening_cost':avg(np.maximum(delta,0))}
S['distance_balance']={}
def diststats(v):
 return dict(mean=avg(v),median=float(np.median(v)),p90=float(np.quantile(v,.9)),maximum=float(np.max(v)))
for a in ['clock','phase']:
 shares=[];dsall=[];dhall=[];pooldh=[];poolshares=[];fractions=[]
 for c in cases:
  f=c['forecasts'][a];pool=np.array([idx[j] for j in f['pool_ids']]);nei=np.array([idx[j] for j in f['neighbor_ids']]);i=idx[c['id']]
  mu=inp['state'][pool].mean(0);sd=inp['state'][pool].std(0);sd[sd<=1e-12]=1
  ds=np.mean(((inp['state'][nei]-inp['state'][i])/sd)**2,1);dh=np.mean((inp[a][nei]-inp[a][i])**2,1)
  pds=np.mean(((inp['state'][pool]-inp['state'][i])/sd)**2,1);pdh=np.mean((inp[a][pool]-inp[a][i])**2,1)
  shares.extend(dh/(ds+dh));dsall.extend(ds);dhall.extend(dh);pooldh.extend(pdh);poolshares.extend(pdh/(pds+pdh));fractions.append(len(nei)/len(pool))
 S['distance_balance'][a]={'selected_shape_contribution_share':diststats(shares),'pool_shape_contribution_share':diststats(poolshares),'selected_state_MSE':diststats(dsall),'selected_shape_MSE':diststats(dhall),'pool_shape_MSE':diststats(pooldh),'selected_fraction_of_pool':diststats(fractions)}
viol=[]
for c in cases:
 e=ev[c['id']];start=e['activation']-168*3600000
 if start<c['input_start']:
  bad=[j for j in c['forecasts']['phase']['pool_ids'] if ev[j]['label_end']>start]
  viol.append({'id':c['id'],'fold':c['fold'],'missing_dependency_hours':(c['input_start']-start)/3600000,'pool_labels_beyond_dependency':len(bad),'pool_ids_beyond_dependency':bad,'selected_ids_beyond_dependency':{a:[j for j in bad if j in c['forecasts'][a]['neighbor_ids']] for a in ['state','clock','phase']},'pool_count':len(c['forecasts']['phase']['pool_ids'])})
S['frozen_delta_dependency_check']={'activation_minus_168h_precedes_recorded_input_start_count':len(viol),'with_pool_labels_after_dependency_count':sum(v['pool_labels_beyond_dependency']>0 for v in viol),'events':viol}
raw_viol=[]
for c in cases:
 e=ev[c['id']];start=min(e['activation']-169*3600000,e['anchor']-3600000)
 if start<c['input_start']:
  bad=[j for j in c['forecasts']['phase']['pool_ids'] if ev[j]['label_end']>start]
  raw_viol.append({'id':c['id'],'fold':c['fold'],'missing_dependency_hours':(c['input_start']-start)/3600000,'pool_ids_beyond_dependency':bad,'selected_ids_beyond_dependency':{a:[j for j in bad if j in c['forecasts'][a]['neighbor_ids']] for a in ['state','clock','phase']}})
S['raw_bar_start_dependency_sensitivity']={'definition':'min(activation−169h, anchor−1h), versus close-endpoint activation−168h','count':len(raw_viol),'with_pool_labels_after_dependency_count':sum(bool(v['pool_ids_beyond_dependency']) for v in raw_viol),'events':raw_viol}
for a in ['prior','state','clock','phase']:
 assert np.isclose(avg(lp[a]),r['metrics'][a]['all_ID']['TP'])
 assert np.isclose(avg(ls[a]),r['metrics'][a]['all_ID']['SL'])
assert np.isclose(avg(d*d-2*d*res),avg(ls['phase']-ls['prior']))
def saved_block_ci(delta,days):
 # Exact occupied UTC-block bootstrap arithmetic from frozen scoring method; no forecast calls.
 origins=np.array([c['origin'] for c in cases]);rng=np.random.default_rng(7);boot=np.zeros(1000);den=np.zeros(1000);counts={}
 for f in sorted(set(fold)):
  take=fold==f;x=delta[take];blocks=origins[take]//(days*86400000);u,inv=np.unique(blocks,return_inverse=True);counts[str(f)]=len(u)
  sums=np.bincount(inv,weights=x);ns=np.bincount(inv);draw=rng.integers(0,len(u),(1000,len(u)));boot+=sums[draw].sum(1);den+=ns[draw].sum(1)
 lo,hi=np.quantile(boot/den,[.025,.975])
 return {'mean':avg(delta),'lower':float(lo),'upper':float(hi),'days':days,'draws':1000,'seed':7,'blocks_by_fold':counts,'classification':'EXPLORATORY_POSTHOC_NOT_NEW_CONFIRMATORY_TEST'}
S['fixed_shrink25_uncertainty']={target:{str(days):saved_block_ci(np.mean(loss['fixed_shrink25']-loss['prior'],axis=tuple(range(1,loss['prior'].ndim))),days) for days in [14,28]} for target,loss in [('TP',lp),('SL',ls)]}
A=avg(d*d);B=avg(2*d*res)
S['hindsight_analytic_brier_bound']={'definition':'min_lambda A*lambda²−B*lambda along this SAVED phase adjustment; not a selected or evaluated new candidate','lambda_star':B/(2*A),'maximum_in_sample_brier_reduction':B*B/(4*A),'relative_to_prior_Brier':B*B/(4*A)/avg(ls['prior'])}
S['physical_four_cell_prior_diagnostic']={'classification':'POSTHOC_DESCRIPTIVE_EXISTING_FORECASTS_ONLY_NO_FUTURE_EXPERIMENT_RUN','boundary':1,'definition':'completed direction +/-1 crossed with frozen_delta/query_sigma24 <=1 versus >1; <=1 means confirmation sigma24 >= frozen activation delta','groups':{}}
directions=features['direction'];ratios=features['vol_ratio_frozen_delta_to_query_sigma24']
for f in ['pooled','F1','F2','F3']:
 group={}
 for direction in [-1,1]:
  for label,volmask in [('ratio_le1',ratios<=1),('ratio_gt1',ratios>1)]:
   mask=(directions==direction)&volmask&((fold==f) if f!='pooled' else np.ones(n,bool));count=int(mask.sum())
   group[f'direction{direction}_{label}']={'n':count,'ids':[c['id'] for c,m in zip(cases,mask) if m],'SL_predicted':np.mean(p['prior'][mask],0).tolist() if count else None,'SL_observed':np.mean(z[mask],0).tolist() if count else None,'SL_observed_minus_predicted':np.mean(res[mask],0).tolist() if count else None,'TP_quantile_coverage':np.mean(y[mask]<=q['prior'][mask],0).tolist() if count else None,'TP_quantile_coverage_minus_tau':(np.mean(y[mask]<=q['prior'][mask],0)-taus).tolist() if count else None}
 S['physical_four_cell_prior_diagnostic']['groups'][f]=group
 assert sum(g['n'] for g in group.values())==(n if f=='pooled' else int((fold==f).sum()))
fourrows=[]
for f,group in S['physical_four_cell_prior_diagnostic']['groups'].items():
 for cell,g in group.items():
  for side in range(2):
   for sl in range(3):
    for ti,tau in enumerate(taus):
     fourrows.append({'fold':f,'cell':cell,'n':g['n'],'side':['long','short'][side],'SL':[.75,1,1.5][sl],'tau':tau,'SL_predicted':g['SL_predicted'][side][sl],'SL_observed':g['SL_observed'][side][sl],'SL_observed_minus_predicted':g['SL_observed_minus_predicted'][side][sl],'TP_coverage':g['TP_quantile_coverage'][side][sl][ti],'TP_coverage_minus_tau':g['TP_quantile_coverage_minus_tau'][side][sl][ti]})
with open(BASE/'stats-four-cell.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(fourrows[0]));w.writeheader();w.writerows(fourrows)
S['physical_four_cell_prior_diagnostic']['boundary_equal_count']=int((ratios==1).sum())
(BASE/'stats-results.json').write_text(json.dumps(S,indent=2)+'\n')
with open(BASE/'stats-breakdown.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(json.dumps({k:S[k] for k in ['overall','brier_decomposition','dimensions','concentration','neighbors','pinball_adjustment']},indent=2))
