"""Single positive synthetic and synchronous TRAIN14day block-shuffle controls."""
from pathlib import Path
import json,time,pickle
import numpy as np
from .forecast_cycle_train import approve,inputs,getx,y_for,catfit,predict,loss,block_ci,record,TAU
from .forecast_independent_data import ms,DAY,write_json,sha
def run(a):
 approve(a,"controls");a.output.mkdir(parents=True,exist_ok=False);rng=np.random.default_rng(7);outputs=[]
 # Synthetic rows only. A deterministic nonlinear relation, held fixed across temporal parts.
 x=rng.normal(size=(1024,8)).astype(np.float32);z=x[:,0]*x[:,1]
 dy=np.where(z>.35,0,np.where(z<-.35,1,2));qy=(2*(x[:,0]>.2)+.2*np.abs(x[:,1])).astype(np.float32)
 for head in ("D","Q-long","Q-short"):
  y=dy if head=="D" else qy;fitid="positive-"+head;record(a,dict(stage="controls",fit=True,fit_id=fitid,seed=7,reason="one fixed known synthetic relationship;100iterations"))
  model=catfit(head,4,x[:768],y[:768],iterations=100);p=predict(model,head,x[768:])
  prior=np.bincount(y[:768].astype(int),minlength=3)/768 if head=="D" else np.quantile(y[:768],TAU)
  prior=np.tile(prior,(256,1));model_loss=float(loss(head,y[768:],p).mean());prior_loss=float(loss(head,y[768:],prior).mean())
  path=a.output/f"{fitid}.cbm";model.save_model(str(path));restored=type(model)();restored.load_model(str(path));np.testing.assert_allclose(predict(restored,head,x[768:]),p,rtol=0,atol=1e-12)
  outputs.append(dict(control="positive",head=head,N_fit=768,N_validation=256,loss=model_loss,prior_loss=prior_loss,learned_known_relation=model_loss<prior_loss,roundtrip="PASS"))
 ds,joint,valid=inputs(a);cut=ms("2025-03-01");start=ms("2024-09-01")
 # Twelve entire14-day blocks. Both assets use the SAME block permutation.
 width=14*24;count=(cut-start)//(14*DAY);perm=np.random.default_rng(7).permutation(count)
 origins=np.arange(start,start+count*14*DAY,3600000,dtype=np.int64);rows=(origins-start)//3600000*2
 mapping=np.concatenate([np.arange(b*width,(b+1)*width) for b in perm]);write_json(a.output/"block-permutation.json",{"seed":7,"block_days":14,"blocks":int(count),"permutation":perm.tolist(),"same_for_both_assets":True,"validation_shuffled":False,"partial_fit_tail":"excluded from negative control only"})
 for asset in (0,1):
  ids=rows+asset;shuffle_ids=rows[mapping]+asset
  if not valid[ids].all() or np.any(ds.meta["expiry"][shuffle_ids]>cut):raise ValueError("NEGATIVE_CONTROL_NONCAUSAL_OR_INVALID_INPUT")
  val=ds.rows("2025-03-01","2025-06-01");val=val[(ds.meta["asset"][val]==asset)&valid[val]]
  for head in ("D","Q-long","Q-short"):
   fitid=f"block-shuffle-{asset}-{head}";y=y_for(ds,shuffle_ids,head);truth=y_for(ds,val,head);record(a,dict(stage="controls",fit=True,fit_id=fitid,seed=7,reason="single synchronous14dayTRAIN labelshuffle;unshuffledtemporalvalidation;100iterations"))
   model=catfit(head,4,getx(ds,joint,ids,"joint"),y,iterations=100);p=predict(model,head,getx(ds,joint,val,"joint"))
   prior=np.bincount(y.astype(int),minlength=3).astype(float) if head=="D" else np.quantile(y,TAU)
   if head=="D":prior=np.maximum(prior,1e-12);prior/=prior.sum()
   delta=loss(head,truth,p)-loss(head,truth,np.tile(prior,(len(val),1)));ci,blocks=block_ci(delta,ds.meta["origin"][val])
   outputs.append(dict(control="TRAIN_block_shuffle",asset=asset,head=head,N_fit=len(ids),N_validation=len(val),mean_loss_difference=float(delta.mean()),CI95=ci,blocks=blocks,advantage_detected=ci[1]<0))
 write_json(a.output/"controls.json",{"status":"DIAGNOSTIC_ONLY_NOT_TRADING","fits":9,"results":outputs,"positive_pass":all(r["learned_known_relation"] for r in outputs if r["control"]=="positive"),"shuffle_no_robust_advantage":not any(r["advantage_detected"] for r in outputs if r["control"]=="TRAIN_block_shuffle"),"interpretation":"No shuffled advantage plus explicit causality checks supports pipeline diagnostic; it does not prove no leakage or trading signal."})
 print(json.dumps({"status":"CONTROLS_COMPLETE","fits":9,"positive_pass":all(r["learned_known_relation"] for r in outputs if r["control"]=="positive"),"shuffle_no_robust_advantage":not any(r["advantage_detected"] for r in outputs if r["control"]=="TRAIN_block_shuffle")}))
