"""Deterministic CPU-only source-contract audit: zero fits/optimizer steps/market predictions."""
import hashlib,json,time
from pathlib import Path
import numpy as np
import pandas as pd
import torch
from coinmaster.research.btc_pattern_models import soft_metric,Residual,render
from coinmaster.research.btc_pattern_data import neighbors,HOUR,folds
root=Path(__file__).resolve().parents[4];out=Path(__file__).parent
start=time.monotonic();torch.set_num_threads(1);torch.manual_seed(7);rng=np.random.default_rng(7);result={}
n=7;z=torch.nn.functional.normalize(torch.randn(n,64,dtype=torch.float64),dim=1).requires_grad_();y=torch.tensor(rng.normal(size=(n,12)),dtype=torch.float64);orig=torch.tensor(np.arange(n)*48*HOUR);end=orig+72*HOUR+60000;sc=torch.ones(6,dtype=torch.float64);tau=.7
loss,stats=soft_metric(z,y,orig,end,sc,tau);zz=z.detach().numpy();yy=y.numpy();dist=.5*np.abs(yy[:,None,:6]-yy[None,:,:6]).mean(2)+.5*np.abs(yy[:,None,6:]-yy[None,:,6:]).mean(2);mask=(orig.numpy()[:,None]>=end.numpy()[None,:])|(end.numpy()[:,None]<=orig.numpy()[None,:]);np.fill_diagonal(mask,False)
expected=[]
for i in range(n):
 if not mask[i].any():continue
 def sm(v):v=v-v.max();return np.exp(v)/np.exp(v).sum()
 q=sm(-dist[i,mask[i]]/tau);p=sm((zz@zz.T)[i,mask[i]]/.1);expected.append((q*np.log(q/p)).sum())
loss.backward();zero,_=soft_metric(z.detach(),y,torch.zeros(n,dtype=torch.long),torch.ones(n,dtype=torch.long),sc,tau)
result['metric']={'torch_loss':float(loss.detach()),'numpy_loss':float(np.mean(expected)),'absolute_error':abs(float(loss.detach())-float(np.mean(expected))),'finite_gradient':bool(torch.isfinite(z.grad).all()),'all_masked_loss':float(zero),'self_exclusion':not bool(np.diag(mask).any()),'stats':stats}
block=Residual(6,32,4).eval();x=torch.randn(2,6,64);xp=x.clone();xp[:,:,32:]+=100
with torch.inference_mode():a=block(x);b=block(xp)
result['TCN']={'prefix_perturbation_max_abs_before_32':float((a[:,:,:32]-b[:,:,:32]).abs().max()),'receptive_field':1+4*sum(2**k for k in range(6)),'bars':64,'future_padding':0}
raw=np.empty((2,64,5));base=100*np.exp(np.linspace(0,.3,64));
for i in range(2):raw[i]=np.column_stack((base,base*1.01,base*.99,base*1.003,np.arange(1,65)*100))
changed=raw.copy();changed[:,20,0]*=1+1e-8
result['CNN']={'microprice_change_input_abs':float(abs(raw-changed).max()),'identical_raster':bool(np.array_equal(render(raw),render(changed))),'price_vertical_steps':78,'volume_vertical_steps':20}
# Deliberately closest row is ineligible; remaining candidates are 72h-separated.
origins=np.arange(6)*72*HOUR;ends=origins+72*HOUR+60000;iz=np.array([[0,1],[.6,.8],[1,0],[1,0],[1,0],[1,0]],float);qz=np.array([1.,0]);cut=int(ends[4]);input_start=int(ends[1]);chosen=neighbors(iz,qz,origins,ends,cut,input_start)
result['neighbors_toy']={'chosen':chosen.tolist(),'all_eligible':bool(((ends[chosen]<=cut)&(ends[chosen]<=input_start)).all()),'no_ineligible_nearest':2 not in chosen}
p=root/'reports/btc-pattern-pilot-m2-20261021/neighbors.parquet';df=pd.read_parquet(p);summ=[]
for (fold,method),g in df.groupby(['fold','method']):
 sizes=g.groupby('query').size();mins=[]
 for _,h in g.groupby('query',sort=False):
  origins=np.sort(h.neighbor_origin.to_numpy());mins.extend(np.diff(origins))
 summ.append({'fold':fold,'method':method,'neighbor_rows':len(g),'queries':len(sizes),'min_support':int(sizes.min()),'max_support':int(sizes.max()),'min_neighbor_spacing_hours':float(min(mins)/HOUR) if mins else None,'input_exclusion_violations':int((g.neighbor_label_end>g.query_input_start).sum()),'self_matches':int((g['query']==g.neighbor).sum()),'cosine_distance_min':float(g.cosine_distance.min()),'cosine_distance_max':float(g.cosine_distance.max())})
result['archived_neighbors']=summ
meta=np.load(root/'runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/prepared/metadata.npy',mmap_mode='r');windows=[]
for fold in folds(meta):
 qi=fold['outer'][0];index=fold['refit'];excluded=int((meta['label_end'][index]>meta['input_start'][qi]).sum());windows.append({'fold':fold['name'],'first_query':int(qi),'refit_index_rows':len(index),'query_window_excluded_neighbor_rows_still_in_global_prior':excluded})
result['exclusion_scope']=windows
result['execution']={'wall_seconds':time.monotonic()-start,'fits':0,'optimizer_steps':0,'market_predictions':0,'device':'CPU','threads':1}
(out/'probe-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
