"""Frozen Kronos feature adapter and outcome-blind resource pilot. No labels loaded."""
from pathlib import Path
import hashlib,json,random,sys,time
import numpy as np
from .forecast_cycle_data import JointFeatures,ASSETS,ms
from .forecast_independent_data import HOUR,sha,write_json
GIT="67b630e67f6a18c9e9be918d9b4337c960db1e9a"
def sample_seed(asset,g,sample):
 return int.from_bytes(hashlib.sha256(f"7|{asset}|{int(g)}|{sample}".encode()).digest()[:4],"little")
def frame_input(panels,asset,g):
 import pandas as pd
 t,v=panels[asset][60];j=np.searchsorted(t+HOUR,g,side="right")-1
 if j<168 or t[j]+HOUR!=g:raise ValueError("INVALID_REAL_HOURLY_WARMUP")
 hist=v[j-168:j+1,3]
 sigma=float(np.std(np.diff(np.log(hist)),ddof=1)*np.sqrt(24))
 if sigma<=0 or not np.isfinite(sigma):raise ValueError("INVALID_SIGMA")
 frame=pd.DataFrame(v[j-79:j+1,:4],columns=["open","high","low","close"])
 frame["volume"]=0.;frame["amount"]=0.
 # Timestamps identify open times. Every input bar is closed by g.
 xt=pd.Series(pd.to_datetime(t[j-79:j+1],unit="ms",utc=True).tz_localize(None))
 yt=pd.Series(pd.to_datetime(g+np.arange(24)*HOUR,unit="ms",utc=True).tz_localize(None))
 return frame,xt,yt,float(hist[-1]),sigma
def sample_paths(predictor,panels,asset,g,set_seed):
 frame,xt,yt,ref,sigma=frame_input(panels,asset,g);paths=[];seeds=[]
 for sample in range(16):
  seed=sample_seed(asset,g,sample);seeds.append(seed);set_seed(seed)
  prediction=predictor.predict(frame,xt,yt,pred_len=24,T=1.,top_k=0,top_p=.9,sample_count=1,verbose=False)
  x=prediction[["open","high","low","close","volume","amount"]].to_numpy()
  if x.shape!=(24,6):raise ValueError("SAMPLE_AXIS_OR_HORIZON")
  paths.append(x)
 paths=np.asarray(paths)
 if paths.shape!=(16,24,6) or len(set(seeds))!=16:raise ValueError("INDEPENDENT_SAMPLE_AXIS")
 terminal=paths[:,-1,3];valid=bool(np.isfinite(paths).all() and np.all(terminal>0))
 z=np.log(terminal/ref)/sigma if valid else np.full(16,np.nan)
 features=np.r_[z.mean(),z.std(ddof=1),np.quantile(z,[.2,.5,.8]),np.mean(z>.25),np.mean(z<-.25)] if valid else np.full(7,np.nan)
 return dict(generation_origin=int(g),reference_close=ref,sigma=sigma,features=features.tolist(),valid=valid,seeds=seeds,distinct_terminal_values=len(np.unique(terminal))),paths
def asof(records,t):
 keys=np.array(sorted(records),np.int64);i=np.searchsorted(keys,int(t),side="right")-1
 if i<0:return None
 g=int(keys[i]);return dict(records[g],age_hours=(int(t)-g)/HOUR)
def verify(a):
 manifest=json.loads((a.report/"b-source-input-hashes.json").read_text())
 for name,rec in manifest.items():
  if sha(Path(name))!=rec["sha256"]:raise ValueError("B_FROZEN_INPUT_DRIFT "+name)
 auth=json.loads(a.fit_authorization.read_text())
 if "profile-B" not in auth.get("authorized_stages",[]):raise ValueError("B_PILOT_NOT_AUTHORIZED")
 if auth.get("b_protocol_sha256")!=sha(a.report/"b-protocol.json") or auth.get("b_source_input_manifest_sha256")!=sha(a.report/"b-source-input-hashes.json"):raise ValueError("B_AUTH_PIN_MISMATCH")
 return json.loads((a.report/"b-protocol.json").read_text())
def profile_B(a):
 recipe=verify(a);started=time.monotonic()
 import torch
 torch.set_num_threads(1);torch.set_num_interop_threads(1)
 vendor=a.report/"kronos-upstream";sys.path.insert(0,str(vendor.resolve()))
 from model import Kronos,KronosTokenizer,KronosPredictor
 from safetensors.torch import load_file
 def load(cls,kind):
  root=a.weights/kind;model=cls(**json.loads((root/"config.json").read_text()))
  model.load_state_dict(load_file(str(root/"model.safetensors"),device="cpu"),strict=True);model.eval();return model
 predictor=KronosPredictor(load(Kronos,"small"),load(KronosTokenizer,"tokenizer"),device="cpu",max_context=512)
 panel=JointFeatures(a.old_job/"prepared-v1",a.warmup)
 def seed(n):random.seed(n);np.random.seed(n);torch.manual_seed(n)
 a.output.mkdir(parents=True,exist_ok=False);records=[];load_wall=time.monotonic()-started
 early_stop=False
 with torch.inference_mode():
  for g in recipe["pilot_origins"]:
   for asset in ASSETS:
    begin=time.monotonic();rec,paths=sample_paths(predictor,panel.panels,asset,g,seed);rec.update(asset=asset,wall_seconds=time.monotonic()-begin)
    np.save(a.output/f"{asset}-{g}-paths.npy",paths);records.append(rec)
    write_json(a.output/"progress.json",dict(completed_asset_origins=len(records),planned_asset_origins=32,load_wall_seconds=load_wall,records=records,quality_accessed=False))
   pair_latencies=[sum(r["wall_seconds"] for r in records[i:i+2]) for i in range(0,len(records),2)]
   fastest_warmed=min(pair_latencies[1:]) if len(pair_latencies)>=3 else 0
   if fastest_warmed*recipe["generation_counts"]["all_unique_six_hour_origins"]>5400:
    early_stop=True;break
 elapsed=time.monotonic()-started
 generation_seconds=sum(r["wall_seconds"] for r in records);per_pair=generation_seconds/(len(records)/2)
 pair_latencies=[sum(r["wall_seconds"] for r in records[i:i+2]) for i in range(0,len(records),2)]
 fastest_warmed=min(pair_latencies[1:]) if len(pair_latencies)>=3 else None
 # Full source cache reused across development, final and quarterly heads; never regenerate per fold.
 all_count=recipe["generation_counts"]["all_unique_six_hour_origins"]
 generation_estimate=per_pair*all_count
 head_budget=recipe["head_budget_seconds"]
 estimate=recipe["preparation_budget_reserve_seconds"]+load_wall+generation_estimate+head_budget
 result=dict(status="RESOURCE_ADMITTED" if estimate*1.2<=5400 else "INCOMPLETE_RESOURCE",wall_seconds=elapsed,load_wall_seconds=load_wall,pilot_generations=len(records),pilot_independent_paths=len(records)*16,early_resource_stop=early_stop,planned_common_origins=16,completed_common_origins=len(records)//2,full_generations=all_count*2,full_independent_paths=all_count*32,generation_estimate_seconds=generation_estimate,paired_origin_latencies_seconds=pair_latencies,fastest_warmed_paired_seconds=fastest_warmed,fastest_warmed_generation_only_projection_seconds=(fastest_warmed*all_count if fastest_warmed is not None else None),head_budget_seconds=head_budget,complete_seconds_with20percent_margin=estimate*1.2,ceiling_seconds=5400,quality_accessed=False,records=records)
 write_json(a.output/"resource-result.json",result)
 from .forecast_cycle_run import ledger
 ledger(a.report,dict(stage="profile-B",fit=False,status=result["status"],wall_seconds=elapsed,independent_paths=len(records)*16,reason="outcomes-blind resource measurement; no head fitting"))
 print(json.dumps({k:v for k,v in result.items() if k!="records"}))
