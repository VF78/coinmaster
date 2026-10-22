"""DESCRIPTIVE D1 context, bounded local minutes, saved losses only. No forecast or fit."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,csv
import numpy as np
B=Path(__file__).resolve().parent;R=B.parent/'event-e1-20261022';W=B.parents[2];P=W/'runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/prepared'
def ms(s):return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp()*1000)
def iso(t):return datetime.fromtimestamp(t/1000,timezone.utc).isoformat()
D=86400000;warm=ms('2024-05-15');start=ms('2024-06-01');end=ms('2026-05-01');m=json.load(open(P/'manifest.json'));raw=np.load(P/'minutes.npy',mmap_mode='r');a=(warm-m['minute_start'])//60000;b=(end-m['minute_start'])//60000
v=raw[a:b];assert len(v)==(end-warm)//60000
bars=v.reshape(-1,1440,5);assert np.isfinite(bars).all() and (bars[:,:,:4]>0).all();cl=np.array(bars[:,-1,3]);times=np.arange(warm+D,end+D,D);assert times[-1]==end
ema=np.empty(len(cl));ema[0]=cl[0]
for i in range(1,len(cl)):ema[i]=2/35*cl[i]+33/35*ema[i-1]
sign=np.where(cl>ema,1,-1);logc=np.log(cl);vol=np.full(len(cl),np.nan)
for i in range(34,len(cl)):vol[i]=np.std(np.diff(logc[i-34:i+1]),ddof=1)
# Episodes are observable sign runs, not fitted waves; complete episode end only for retrospective duration stats.
epid=np.zeros(len(cl),int);age=np.ones(len(cl),int)
for i in range(1,len(cl)):
 epid[i]=epid[i-1]+int(sign[i]!=sign[i-1]);age[i]=age[i-1]+1 if sign[i]==sign[i-1] else 1
period=(times>start)&(times<=end);episodes=[]
for e in sorted(set(epid[period])):
 ix=np.where((epid==e)&period)[0];allix=np.where(epid==e)[0]
 episodes.append({'id':int(e),'sign':int(sign[ix[0]]),'first_close':iso(int(times[ix[0]])),'last_close':iso(int(times[ix[-1]])),'days_observed':len(ix),'left_truncated':bool(allix[0]<np.where(period)[0][0]),'right_censored':bool(allix[-1]==len(cl)-1),'warmup_provisional':bool(allix[0]<33)})
r=json.load(open(R/'RESULTS.json'));cat=json.load(open(R/'catalogue.json'))['events'];ev={e['id']:e for e in cat};rows=[]
for c in r['cases']:
 i=int(np.searchsorted(times,c['origin'],side='right')-1);assert times[i]<=c['origin'];e=ev[c['id']]
 row={'id':c['id'],'fold':c['fold'],'origin':c['origin'],'daily_close_time':int(times[i]),'daily_close':float(cl[i]),'EMA34':float(ema[i]),'macro_sign':int(sign[i]),'macro_episode':int(epid[i]),'macro_age_days':int(age[i]),'daily_observations':i+1,'EMA34_mature':i>=33,'EMA_logdistance':float(logc[i]-np.log(ema[i])),'EMA_distance_vol34':float((logc[i]-np.log(ema[i]))/vol[i]) if np.isfinite(vol[i]) else None,'event_direction':e['direction'],'ratio_frozen_to_current_vol':e['delta']/e['sigma24'],'event_macro_aligned':e['direction']==sign[i]}
 for window in [90,180]:
  row[f'return{window}d']=float(logc[i]-logc[i-window]) if i>=window else None
  row[f'drawdown{window}d']=float(logc[i]-max(logc[i-window+1:i+1])) if i>=window-1 else None
 for target in ['TP','SL']:
  row[f'prior_{target}']=c['forecasts']['prior']['loss'][target];row[f'phase_excess_{target}']=c['forecasts']['phase']['loss'][target]-row[f'prior_{target}']
 row['cell']=f"direction{e['direction']}_ratio_{'le1' if row['ratio_frozen_to_current_vol']<=1 else 'gt1'}"
 rows.append(row)
def agg(mask):
 rr=[x for x,take in zip(rows,mask) if take]
 if not rr:return {'n':0}
 out={'n':len(rr),'episodes':len(set(x['macro_episode'] for x in rr)),'TP_excess':float(np.mean([x['phase_excess_TP'] for x in rr])),'SL_excess':float(np.mean([x['phase_excess_SL'] for x in rr])),'prior_TP':float(np.mean([x['prior_TP'] for x in rr])),'prior_SL':float(np.mean([x['prior_SL'] for x in rr]))}
 selected=[c for c,take in zip(r['cases'],mask) if take];z=np.array([c['truth']['touch'] for c in selected]);p=np.array([c['forecasts']['prior']['touch'] for c in selected]);y=np.array([c['truth']['Q'] for c in selected])[...,0,None];q=np.array([c['forecasts']['prior']['Q'] for c in selected]);out['SL_residual']=(z-p).mean(0).tolist();out['TP_coverage_minus_tau']=((y<=q).mean(0)-np.array([.2,.5,.8])).tolist();return out
out={'classification':'DESCRIPTIVE_POSTHOC_D1_CONTEXT_NO_FORECAST_FIT_TARGETS_OR_MODEL_RUN','source':{'minute_manifest_sha256':hashlib.sha256((P/'manifest.json').read_bytes()).hexdigest(),'minute_slice_indices':[int(a),int(b)],'slice_start':iso(warm),'slice_end_exclusive':iso(end),'read_minute_columns':'OHLCV validity and D1 last minute CLOSE column3 only','no_after_end_values_read':True},'reference':'sign(close−EMA34), first-close seed, alpha2/35, from existing wave_overlay side convention; not fullwave ground truth','warmup':{'genuine_days_before_june1':17,'EMA34_min34_observations_first_close':iso(int(times[33])),'return90_first_available_close':iso(int(times[90])),'return180_first_available_close':iso(int(times[180])),'period_days_without_EMA34_min34':int(np.sum(period&(np.arange(len(cl))<33))),'period_days_without_return90':int(np.sum(period&(np.arange(len(cl))<90))),'period_days_without_return180':int(np.sum(period&(np.arange(len(cl))<180)))},'period_days':int(period.sum()),'episodes':episodes,'query_count':len(rows),'groups':{},'four_cell_by_macro':{},'fold_macro':{}}
for field in ['macro_sign','event_macro_aligned']:
 out['groups'][field]={str(val):agg([x[field]==val for x in rows]) for val in sorted(set(x[field] for x in rows))}
for label,mask in [('age_le34',[x['macro_age_days']<=34 for x in rows]),('age_gt34',[x['macro_age_days']>34 for x in rows])]:out['groups'][label]=agg(mask)
for cell in sorted(set(x['cell'] for x in rows)):
 out['four_cell_by_macro'][cell]={str(s):agg([x['cell']==cell and x['macro_sign']==s for x in rows]) for s in [-1,1]}
for f in ['F1','F2','F3']:
 out['fold_macro'][f]={str(s):agg([x['fold']==f and x['macro_sign']==s for x in rows]) for s in [-1,1]}
for e in episodes:
 e['all_catalogue_events']=sum(int(np.searchsorted(times,c['origin'],side='right')-1)>=0 and epid[int(np.searchsorted(times,c['origin'],side='right')-1)]==e['id'] for c in cat)
 e['eval_events']=sum(x['macro_episode']==e['id'] for x in rows)
 e['eval_TP_excess_sum']=sum(x['phase_excess_TP'] for x in rows if x['macro_episode']==e['id']);e['eval_SL_excess_sum']=sum(x['phase_excess_SL'] for x in rows if x['macro_episode']==e['id'])
complete=[e['days_observed'] for e in episodes if not e['left_truncated'] and not e['right_censored']]
out['episode_summary']={'count':len(episodes),'complete_count':len(complete),'complete_duration_min':min(complete),'complete_duration_median':float(np.median(complete)),'complete_duration_p90':float(np.quantile(complete,.9)),'complete_duration_max':max(complete),'complete_100_to_200_days':sum(100<=x<=200 for x in complete),'all_catalogue_events_per_episode_median':float(np.median([e['all_catalogue_events'] for e in episodes])),'all_catalogue_events_per_episode_max':max(e['all_catalogue_events'] for e in episodes),'eval_episodes':len(set(x['macro_episode'] for x in rows)),'eval_events_per_occupied_episode_median':float(np.median([e['eval_events'] for e in episodes if e['eval_events']])),'eval_events_per_episode_max':max(e['eval_events'] for e in episodes)}
for name,data in [('queries',rows),('episodes',episodes)]:
 with open(B/f'stats-daily-{name}.csv','w') as f:
  w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
out['query_context_availability']={key:sum(x[key] is not None for x in rows) for key in ['EMA_distance_vol34','return90d','return180d','drawdown90d','drawdown180d']}
out['fixed_90d_return_sign_diagnostic']={'definition':'sign log(last fully closed D1 close / D1 close90days earlier), zero assigneddown; posthoc existingforecasts only','pooled':{},'folds':{},'four_cell':{}}
for s in [-1,1]:out['fixed_90d_return_sign_diagnostic']['pooled'][str(s)]=agg([(1 if x['return90d']>0 else -1)==s for x in rows])
for f in ['F1','F2','F3']:
 out['fixed_90d_return_sign_diagnostic']['folds'][f]={str(s):agg([x['fold']==f and (1 if x['return90d']>0 else -1)==s for x in rows]) for s in [-1,1]}
for cell in sorted(set(x['cell'] for x in rows)):
 out['fixed_90d_return_sign_diagnostic']['four_cell'][cell]={str(s):agg([x['cell']==cell and (1 if x['return90d']>0 else -1)==s for x in rows]) for s in [-1,1]}
supp=[]
for c,x in zip(r['cases'],rows):
 # Conservative rawdailybar dependency: earliest daily close90d ago has barstart91d ago.
 earliest=x['daily_close_time']-91*D
 ids=[]
 for j in c['forecasts']['prior']['pool_ids']:
  e=ev[j];li=int(np.searchsorted(times,e['origin'],side='right')-1)
  if li>=90 and e['label_end']<=min(earliest,c['input_start']):ids.append(j)
 querysign=1 if x['return90d']>0 else -1
 matching=0
 for j in ids:
  li=int(np.searchsorted(times,ev[j]['origin'],side='right')-1);libs=1 if cl[li]>cl[li-90] else -1;matching+=int(libs==querysign)
 supp.append({'id':c['id'],'fold':c['fold'],'raw_daily_support_start':earliest,'eligible_pool_with_90d_features_and_disjoint_labels_count':len(ids),'same_90d_sign_cell_count':matching})
out['fixed_90d_support_audit']={'definition':'Saved originalpool filtered only descriptively: library has real90dfeature, labelend<=min(queryexistinginputstart, lastD1close−91d). No neighborhood/forecast generated. EMArecursive doesNOThavefinite34dinput.','folds':{f:{'minimum':min(x['eligible_pool_with_90d_features_and_disjoint_labels_count'] for x in supp if x['fold']==f),'median':float(np.median([x['eligible_pool_with_90d_features_and_disjoint_labels_count'] for x in supp if x['fold']==f])),'maximum':max(x['eligible_pool_with_90d_features_and_disjoint_labels_count'] for x in supp if x['fold']==f),'zero_count':sum(x['eligible_pool_with_90d_features_and_disjoint_labels_count']==0 for x in supp if x['fold']==f)} for f in ['F1','F2','F3']},'queries':supp}
out['descriptive_context_loss_correlations']={key:{target:float(np.corrcoef([x[key] for x in rows],[x[f'phase_excess_{target}'] for x in rows])[0,1]) for target in ['TP','SL']} for key in ['EMA_distance_vol34','return90d','return180d','drawdown90d','drawdown180d']}
out['positive_excess_concentration']={}
for target in ['TP','SL']:
 es=np.array([max(e[f'eval_{target}_excess_sum'],0) for e in episodes]);order=np.argsort(es)[::-1]
 out['positive_excess_concentration'][target]={'top3_episodes_share_positive_episode_excess':float(es[order[:3]].sum()/es.sum()),'top3_episodes':[episodes[i] for i in order[:3]]}
with open(B/'stats-daily-closes.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=['close_time','close','EMA34','sign','episode','age_days','EMA34_min34_observations']);w.writeheader()
 for i in range(len(cl)):w.writerow(dict(close_time=iso(int(times[i])),close=cl[i],EMA34=ema[i],sign=sign[i],episode=epid[i],age_days=age[i],EMA34_min34_observations=i>=33))
assert len(rows)==198 and all(x['daily_close_time']<=x['origin'] for x in rows)
(B/'stats-daily-results.json').write_text(json.dumps(out,indent=2,allow_nan=False,default=lambda x:x.item())+'\n')
print('Descriptive D1 context saved; 198 events retained; no forecast, model, targets or backtest run.')
