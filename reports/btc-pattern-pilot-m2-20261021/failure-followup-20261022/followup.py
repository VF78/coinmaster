"""One bounded descriptive saved-forecast pass. No fitting or new prediction."""
import json,hashlib,time,resource
from pathlib import Path
import numpy as np,pandas as pd
from coinmaster.research.btc_pattern_data import folds,DAY
HERE=Path(__file__).resolve().parent

def sha(p):
 with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def ratio_at(minutes,origin_index):
 first=origin_index-1-168*60
 if first<0:return np.nan
 close=minutes[origin_index-1-60*np.arange(168,-1,-1),3];ret=np.diff(np.log(close));week=np.std(ret,ddof=1)
 return np.std(ret[-24:],ddof=1)/week if week>0 else np.nan

def feature_edges(ratio,fit_ids,meta,cutoff):
 if np.any(meta['label_end'][fit_ids]>cutoff):raise ValueError('UNPURGED_FIT_FEATURES')
 return np.quantile(ratio[fit_ids],[1/3,2/3])
def bins(ratio,edges):return np.digitize(ratio,edges,right=False)
def survival_bounds(q,threshold=1.):
 levels=np.array([.2,.5,.8]);lo=np.where(q>threshold+1e-6,1-levels,0).max(-1);hi=np.where(q<threshold-1e-6,1-levels,1).min(-1)
 return lo,hi

def run(root):
 began=time.monotonic();prepared=root/'prepared';baseline=root/'development';report=HERE.parent;meta=np.load(prepared/'metadata.npy',mmap_mode='r');ctx=np.load(prepared/'context.npy',mmap_mode='r');minutes=np.load(prepared/'minutes.npy',mmap_mode='r');ratio=ctx[:,4]/ctx[:,5];source_paths=[HERE/'protocol.json',Path(__file__),prepared/'manifest.json',prepared/'metadata.npy',prepared/'context.npy',prepared/'labels.npz',report/'causal-regimes.csv']+[baseline/f/fn for f in ['F1','F2','F3'] for fn in ['CNN-direct.npz','prior.npz']];freeze=dict(source_hashes={str(p):sha(p) for p in source_paths},strata=[],feature_already_present=True,feature_proof=[])
 for i in np.linspace(0,len(meta)-1,128).astype(int):
  actual=ratio_at(minutes,int(meta['entry_index'][i])-1);assert abs(actual-ratio[i])<1e-5;freeze['feature_proof'].append(dict(id=int(i),ratio=float(ratio[i]),minute_ratio=float(actual),last_known_minute=int(meta['entry_index'][i])-2))
 for f in folds(meta):
  e=feature_edges(ratio,f['refit'],meta,f['fit_cutoff']);freeze['strata'].append(dict(fold=f['name'],edges=e.tolist(),fit_N=len(f['refit']),max_label_end=int(meta['label_end'][f['refit']].max()),fit_cutoff=f['fit_cutoff'],fit_ids_sha256=hashlib.sha256(f['refit'].tobytes()).hexdigest(),feature_source='existingcontext4/5; nopredictivetargetused'))
 (HERE/'feature-strata-freeze.json').write_text(json.dumps(freeze,indent=2)+'\n')
 # Only AFTER features/thresholds/source hashes freeze, load target/prediction values.
 labels=dict(np.load(prepared/'labels.npz'));rg=pd.read_csv(report/'causal-regimes.csv');regmap={(x.fold,int(x.id)):x.regime for x in rg.itertuples()};cells=[];contrasts=[];sensitivity=[];coherence=[];pop=[];levels=np.array([.2,.5,.8]);categories=['DOWN_HIGH','DOWN_LOW','UP_HIGH','UP_LOW']
 def guard():
  if time.monotonic()-began>180 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>6*1024**3:raise RuntimeError('FOLLOWUP_LIMIT')
 for f,fr in zip(folds(meta),freeze['strata']):
  guard();name=f['name'];z=dict(np.load(baseline/name/'CNN-direct.npz'));prior=dict(np.load(baseline/name/'prior.npz'));ids=z['ids'];assert np.array_equal(ids,f['outer']) and np.array_equal(ids,prior['ids']);states=bins(ratio[ids],fr['edges']);reg=np.array([categories.index(regmap[(name,int(i))]) for i in ids]);origins=meta['origin'][ids];outcomes={};y=z['truth_Q'];upper=z['truth_Q_upper'];assert np.array_equal(y,labels['mfe'][ids,:,0]);assert np.allclose(labels['policy_mfe'][ids,1,1,:,0],y);adverse=np.empty((len(ids),2))
  for n,i in enumerate(ids):
   j=int(meta['entry_index'][i]);v=minutes[j:j+4320];assert len(v)==4320;adverse[n]=[-np.log(v[:,2].min()/meta['entry'][i])/meta['sigma72'][i],np.log(v[:,1].max()/meta['entry'][i])/meta['sigma72'][i]]
  for model,d in [('CNN',z),('prior',prior)]:
   error=y[:,:,None]-d['q_projected'];pin=np.maximum(levels*error,(levels-1)*error)
   for s,side in enumerate(['long','short']):
    outcomes[model+'_'+side+'_mean_pinball']=pin[:,s].mean(1)
    for k,level in enumerate(levels):outcomes[model+'_'+side+'_CDFresidual_'+str(level)]=(y[:,s]<=d['q_projected'][:,s,k]).astype(float)-level;outcomes[model+'_'+side+'_pinball_'+str(level)]=pin[:,s,k]
  lo,hi=survival_bounds(z['q_projected'])
  for s,side in enumerate(['long','short']):
   outcomes['SL1_'+side+'_touch']=(adverse[:,s]>=1).astype(float);outcomes['CNN_minus_prior_'+side+'_mean_pinball']=outcomes['CNN_'+side+'_mean_pinball']-outcomes['prior_'+side+'_mean_pinball'];p=z['probabilities'][:,s];excess=np.maximum.reduce((lo[:,s]-p,p-hi[:,s],np.zeros(len(ids))));outcomes['coherence_'+side+'_violation']=(excess>1e-7).astype(float);outcomes['coherence_'+side+'_material_gt05']=(excess>.05).astype(float);valid=z['truth_D']>=0;identity=((y[:,s]>=1)!=(z['truth_D']==s))&valid
   coherence.append(dict(fold=name,side=side,N=len(ids),label_identity_mismatches=int(identity.sum()),D_ambiguity=int((~valid).sum()),violation_fraction=float((excess>1e-7).mean()),material_gt05_fraction=float((excess>.05).mean()),mean_excess=float(excess.mean()),maximum_excess=float(excess.max())))
  keys=list(outcomes);values=np.stack(list(outcomes.values()),axis=1);count=np.zeros((4,3),int);sums=np.zeros((4,3,len(keys)));np.add.at(count,(reg,states),1);np.add.at(sums,(reg,states),values);common=(count[:,0]>0)&(count[:,2]>0);pop.append(dict(fold=name,edges=fr['edges'],N=len(ids),state_counts=np.bincount(states,minlength=3).tolist(),regime_state_counts=count.tolist(),common_low_high_regimes=np.array(categories)[common].tolist(),all_months=sorted(set(pd.to_datetime(origins,unit='ms',utc=True).strftime('%Y-%m'))),ids_sha256=hashlib.sha256(ids.tobytes()).hexdigest()))
  for r in range(-1,4):
   for s in range(3):
    selected=(states==s)&((reg==r) if r>=0 else True);N=int(selected.sum());blockN=len(np.unique(origins[selected]//(14*DAY)))
    for k,metric in enumerate(keys):cells.append(dict(fold=name,regime='ALL' if r<0 else categories[r],state=['LOW','MID','HIGH'][s],metric=metric,N=N,blocks14d=blockN,mean=float(values[selected,k].mean()) if N else None,support='EMPTY' if N==0 else 'THIN' if N<30 or blockN<2 else 'OBSERVED'))
  bunique=np.unique(origins//(14*DAY));bc=[];bs=[]
  for block in bunique:
   sel=origins//(14*DAY)==block;c=np.zeros((4,3),int);sm=np.zeros((4,3,len(keys)));np.add.at(c,(reg[sel],states[sel]),1);np.add.at(sm,(reg[sel],states[sel]),values[sel]);bc.append(c);bs.append(sm)
  draws=np.random.default_rng(7).integers(0,len(bunique),(1000,len(bunique)));bootc=np.array(bc)[draws].sum(1);boots=np.array(bs)[draws].sum(1)
  for kind in ['RAW_HIGH_MINUS_LOW','EQUAL_REGIME_COMMON_SUPPORT']:
   if kind.startswith('RAW'):
    c=count.sum(0);sm=sums.sum(0);point=sm[2]/c[2]-sm[0]/c[0];bcount=bootc.sum(1);bsum=boots.sum(1);valid=(bcount[:,0]>0)&(bcount[:,2]>0);rep=bsum[valid,2]/bcount[valid,2,None]-bsum[valid,0]/bcount[valid,0,None];coverage=[1.,1.];commonN=4
   else:
    commonN=int(common.sum());point=(sums[common,2]/count[common,2,None]-sums[common,0]/count[common,0,None]).mean(0) if commonN else np.full(len(keys),np.nan);valid=(bootc[:,common,0]>0).all(1)&(bootc[:,common,2]>0).all(1) if commonN else np.zeros(1000,bool);rep=(boots[valid][:,common,2]/bootc[valid][:,common,2,None]-boots[valid][:,common,0]/bootc[valid][:,common,0,None]).mean(1) if commonN else np.empty((0,len(keys)));coverage=[float(count[common,s].sum()/count[:,s].sum()) for s in [0,2]]
   validN=int(valid.sum())
   for k,metric in enumerate(keys):contrasts.append(dict(fold=name,contrast=kind,metric=metric,high_minus_low=float(point[k]),CI_lower=float(np.quantile(rep[:,k],.025)) if validN>=800 else None,CI_upper=float(np.quantile(rep[:,k],.975)) if validN>=800 else None,valid_bootstrap=validN,requested_bootstrap=1000,common_regimes=commonN,low_population_coverage=coverage[0],high_population_coverage=coverage[1],CI_status='DESCRIPTIVE_BLOCK' if validN>=800 else 'UNIDENTIFIED_SUPPORT',period='FULL_OUTER'))
  midpoint=(f['fit_cutoff']+f['outer_end'])//2
  for half,selected in [('EARLY',origins<midpoint),('LATE',origins>=midpoint)]:
   c=np.zeros((4,3),int);sm=np.zeros((4,3,len(keys)));np.add.at(c,(reg[selected],states[selected]),1);np.add.at(sm,(reg[selected],states[selected]),values[selected]);co=(c[:,0]>0)&(c[:,2]>0);pt=(sm[co,2]/c[co,2,None]-sm[co,0]/c[co,0,None]).mean(0) if co.any() else np.full(len(keys),np.nan)
   for k,metric in enumerate(keys):contrasts.append(dict(fold=name,contrast='EQUAL_REGIME_COMMON_SUPPORT',metric=metric,high_minus_low=float(pt[k]),common_regimes=int(co.sum()),low_population_coverage=float(c[co,0].sum()/c[:,0].sum()) if c[:,0].sum() else None,high_population_coverage=float(c[co,2].sum()/c[:,2].sum()) if c[:,2].sum() else None,CI_status='HALF_POINT_ONLY_THIN_BLOCKS',period=half))
  for state in [-1,0,1,2]:
   sel=np.ones(len(ids),bool) if state<0 else states==state
   for si,sl in enumerate([.75,1.,1.5]):
    for s,side in enumerate(['long','short']):
     lower=labels['policy_mfe'][ids,1,si,s,0];upp=labels['policy_mfe'][ids,1,si,s,1];hit=adverse[:,s]>=sl;row=dict(fold=name,state='ALL' if state<0 else ['LOW','MID','HIGH'][state],side=side,SL_sigma72=sl,N=int(sel.sum()),SL_touch=float(hit[sel].mean()),mean_attainable_MFE_lower_original_sigma72=float(lower[sel].mean()),mean_attainable_MFE_upper_original_sigma72=float(upp[sel].mean()),SL_physical_distance_mean_pct=float(((1-np.exp(-sl*meta['sigma72'][ids])) if s==0 else np.expm1(sl*meta['sigma72'][ids]))[sel].mean()*100),contract='DIFFERENT_PHYSICAL_SL_NOT_SCORE_GAIN')
     for k,level in enumerate(levels):target=z['q_projected'][:,s,k];lh=lower>=target;uh=upp>=target;row['TP'+str(level)+'_before_SL_lower']=float(lh[sel].mean());row['TP'+str(level)+'_before_SL_upper']=float(uh[sel].mean());row['SL_before_TP'+str(level)+'_lower']=float((hit&~uh)[sel].mean());row['SL_before_TP'+str(level)+'_upper']=float((hit&~lh)[sel].mean())
     sensitivity.append(row)
  guard()
 for filename,rows in [('state-regime-cells.csv',cells),('state-contrasts.csv',contrasts),('stop-sensitivity.csv',sensitivity),('DQ-coherence.csv',coherence)]:pd.DataFrame(rows).to_csv(HERE/filename,index=False)
 (HERE/'populations.json').write_text(json.dumps(pop,indent=2)+'\n');receipt=dict(status='COMPLETE_ZERO_FIT_DESCRIPTIVE',fits=0,optimizer_steps=0,new_predictions=0,CHECK=False,wall_seconds=time.monotonic()-began,origins=sum(p['N'] for p in pop),source_sha256=sha(__file__),protocol_sha256=sha(HERE/'protocol.json'),freeze_sha256=sha(HERE/'feature-strata-freeze.json'),statistics_are_evaluation_not_conditional_calibration=True);(HERE/'completion.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
if __name__=='__main__':run(Path('runtime/var/research-jobs/btc-pattern-pilot-m2-20261021'))
