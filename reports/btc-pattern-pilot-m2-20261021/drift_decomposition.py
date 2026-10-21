"""Frozen one-pass descriptive within-fold fixed-model Kitagawa, no fits/CHECK."""
import json,hashlib,time,resource
from pathlib import Path
import numpy as np,pandas as pd
from coinmaster.research.btc_pattern_data import folds,DAY
r=Path('reports/btc-pattern-pilot-m2-20261021');job=Path('runtime/var/research-jobs/btc-pattern-pilot-m2-20261021');base=job/'development';out=job/'fixed-model-drift-decomposition';out.mkdir(exist_ok=False);sha=lambda p:hashlib.file_digest(open(p,'rb'),'sha256').hexdigest();meta=np.load(job/'prepared/metadata.npy',mmap_mode='r');paths=[r/'drift-decomposition-protocol.json',r/'causal-regimes.csv',job/'prepared/metadata.npy']+[p for fold in ['F1','F2','F3'] for p in [base/fold/'CNN-refit.pt',base/fold/'CNN-direct.npz',base/fold/'prior.npz']];manifest=dict(source_sha256=sha(Path(__file__)),files={str(p.resolve()):sha(p) for p in paths},fits=0,CHECK_used=False,forecast_IDs={str(p.resolve()):dict(N=len(np.load(p)['ids']),ids_sha256=hashlib.sha256(np.load(p)['ids'].tobytes()).hexdigest()) for p in paths if p.suffix=='.npz'});(r/'drift-decomposition-pre-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');began=time.monotonic();regimes=pd.read_csv(r/'causal-regimes.csv');mapping={(x.fold,int(x.id)):x.regime for x in regimes.itertuples()};records=[];populations=[]

def guard():
 if time.monotonic()-began>180 or resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>6*1024**3:raise RuntimeError('DECOMPOSITION_LIMIT')

def observations(z):
 y=z['truth_Q'];q=z['q_projected'];error=y[:,:,None]-q;levels=np.array([.2,.5,.8]);pin=np.maximum(levels*error,(levels-1)*error);cdf=(y[:,:,None]<=q).astype(float);cols=[];names=[]
 for side,label in enumerate(['long','short']):
  cols.append(pin[:,side].mean(1));names.append('Q_'+label+'_mean_pinball')
  for k,level in enumerate(levels):
   cols.extend([pin[:,side,k],cdf[:,side,k]]);names.extend(['Q_'+label+'_pinball_'+str(level),'Q_'+label+'_CDF_le_'+str(level)])
 return np.stack(cols,axis=1),names

for fold in folds(meta):
 guard();name=fold['name'];cnn=dict(np.load(base/name/'CNN-direct.npz'));prior=dict(np.load(base/name/'prior.npz'));ids=cnn['ids'];assert np.array_equal(ids,prior['ids']) and np.array_equal(ids,fold['outer']);assert np.array_equal(cnn['truth_Q'],prior['truth_Q']);origins=meta['origin'][ids];split=(fold['fit_cutoff']+fold['outer_end'])//2;half=origins>=split;labels=np.array([mapping[(name,int(i))] for i in ids]);categories=['DOWN_HIGH','DOWN_LOW','UP_HIGH','UP_LOW']+sorted(set(labels)-{'DOWN_HIGH','DOWN_LOW','UP_HIGH','UP_LOW'});reg=np.array([categories.index(x) for x in labels]);R=len(categories);counts=np.stack([np.bincount(reg[half==h],minlength=R) for h in [False,True]]);common=(counts>0).all(axis=0);assert common.any();coverage=counts[:,common].sum(1)/counts.sum(1);status='IDENTIFIED' if common.all() else 'UNIDENTIFIED_FULL_SUPPORT';ids_digest=hashlib.sha256(ids.tobytes()).hexdigest();blocks=[np.unique((origins[half==h]//(14*DAY))) for h in [False,True]];rng=np.random.default_rng(7);draws=[rng.integers(0,len(b),(1000,len(b))) for b in blocks];cv,names=observations(cnn);pv,_=observations(prior)
 populations.append(dict(fold=name,midpoint_UTC=str(pd.to_datetime(split,unit='ms',utc=True)),N=len(ids),early_N=int(counts[0].sum()),late_N=int(counts[1].sum()),early_excluded_N=int(counts[0,~common].sum()),late_excluded_N=int(counts[1,~common].sum()),early_common_coverage=float(coverage[0]),late_common_coverage=float(coverage[1]),regime_counts_early=dict(zip(categories,counts[0].tolist())),regime_counts_late=dict(zip(categories,counts[1].tolist())),common_regimes=np.array(categories)[common].tolist(),full_decomposition_status=status,ids_sha256=ids_digest,early_blocks=len(blocks[0]),late_blocks=len(blocks[1]),all_months=sorted(set(pd.to_datetime(origins,unit='ms',utc=True).strftime('%Y-%m')))))
 for model,values in [('original_CNN',cv),('prior',pv),('CNN_minus_prior',cv-pv)]:
  sums=np.stack([np.array([values[(half==h)&(reg==k)].sum(0) for k in range(R)]) for h in [False,True]]);p=counts[:,common]/counts[:,common].sum(1)[:,None];mu=sums[:,common]/counts[:,common,None];mix=((p[1]-p[0])[:,None]*(mu[1]+mu[0])/2).sum(0);within=((mu[1]-mu[0])*(p[1]+p[0])[:,None]/2).sum(0);delta=(p[1,:,None]*mu[1]).sum(0)-(p[0,:,None]*mu[0]).sum(0);assert np.max(abs(delta-mix-within))<1e-10;bc=[];bs=[]
  for h in [False,True]:
   bcounts=[];bsums=[]
   for b in blocks[int(h)]:
    selected=(half==h)&(origins//(14*DAY)==b);bcounts.append(np.bincount(reg[selected],minlength=R));bsums.append(np.array([values[selected&(reg==k)].sum(0) for k in range(R)]))
   bc.append(np.array(bcounts)[draws[int(h)]].sum(1)[:,common]);bs.append(np.array(bsums)[draws[int(h)]].sum(1)[:,common])
  valid=(bc[0]>0).all(1)&(bc[1]>0).all(1);validN=int(valid.sum());bp=[x[valid]/x[valid].sum(1)[:,None] for x in bc];bm=[s[valid]/c[valid,:,None] for s,c in zip(bs,bc)];mixdraw=((bp[1]-bp[0])[:,:,None]*(bm[1]+bm[0])/2).sum(1);withindraw=((bm[1]-bm[0])*(bp[1]+bp[0])[:,:,None]/2).sum(1);deltadraw=mixdraw+withindraw
  for k,metric in enumerate(names):
   row=dict(fold=name,model=model,metric=metric,N=len(ids),early_mean_full=float(values[~half,k].mean()),late_mean_full=float(values[half,k].mean()),observed_delta_full=float(values[half,k].mean()-values[~half,k].mean()),common_delta=float(delta[k]),common_mix=float(mix[k]),common_within=float(within[k]),identity_residual=float(delta[k]-mix[k]-within[k]),full_decomposition_status=status,early_excluded_N=int(counts[0,~common].sum()),late_excluded_N=int(counts[1,~common].sum()),early_common_coverage=float(coverage[0]),late_common_coverage=float(coverage[1]),CI_status='CONDITIONAL_FIXED_COMMON_SUPPORT_DESCRIPTIVE' if validN>=800 else 'UNIDENTIFIED_MISSING_SUPPORT_IN_BOOTSTRAP',bootstrap_valid_draws=validN,bootstrap_requested_draws=1000)
   for label,array in [('delta',deltadraw),('mix',mixdraw),('within',withindraw)]:
    row[label+'_CI_lower']=float(np.quantile(array[:,k],.025)) if validN>=800 else None;row[label+'_CI_upper']=float(np.quantile(array[:,k],.975)) if validN>=800 else None
   records.append(row)
 guard()
pd.DataFrame(records).to_csv(out/'decomposition.csv',index=False);(out/'populations.json').write_text(json.dumps(populations,indent=2)+'\n');receipt=dict(status='COMPLETE_DESCRIPTIVE_NO_CAUSALITY',fits=0,optimizer_steps=0,new_predictions=0,CHECK_used=False,wall_seconds=time.monotonic()-began,rows=len(records),N_original_outer=sum(x['N'] for x in populations),source_sha256=sha(Path(__file__)),protocol_sha256=sha(r/'drift-decomposition-protocol.json'));(out/'completion.json').write_text(json.dumps(receipt,indent=2)+'\n')
for p in out.glob('*'):(r/('drift-'+p.name)).write_bytes(p.read_bytes())
print(json.dumps(receipt))
