"""Bounded TS2Vec resource pilot with prefix-only scaler and causal endpoint API."""
from pathlib import Path
import csv,hashlib,json,random,sys,time
import numpy as np
from .forecast_cycle_data import JointFeatures,ASSETS,ms
from .forecast_independent_data import HOUR,DAY,sha,write_json
def channels(panels):
 t=panels[ASSETS[0]][60][0];ends=t+HOUR;allx=[]
 for asset in ASSETS:
  tt,v=panels[asset][60]
  if not np.array_equal(tt,t):raise ValueError("JOINT_HOURLY_ALIGNMENT")
  x=np.full((len(t),6),np.nan,np.float32)
  for j in range(168,len(t)):
   o,h,l,c,vol=v[j];prev=v[j-1,3];sigma=np.std(np.diff(np.log(v[j-168:j+1,3])),ddof=1)*np.sqrt(24)
   if sigma<=0 or not np.isfinite(sigma) or min(o,h,l,c,prev)<=0:continue
   x[j]=[np.log(c/prev)/(sigma*np.sqrt(1/24)),np.log(c/o)/(sigma*np.sqrt(1/24)),np.log(h/max(o,c))/(sigma*np.sqrt(1/24)),np.log(min(o,c)/l)/(sigma*np.sqrt(1/24)),np.log(h/l)/(sigma*np.sqrt(1/24)),np.log1p(vol)-np.log1p(v[j-20:j,4]).mean()]
  allx.append(x)
 return ends,np.column_stack(allx)
def model_class(report):
 sys.path.insert(0,str((report/"ts2vec-upstream").resolve()))
 from ts2vec import TS2Vec
 return TS2Vec
def new_model(report,callback=None):
 import torch
 random.seed(7);np.random.seed(7);torch.manual_seed(7)
 return model_class(report)(input_dims=12,output_dims=32,hidden_dims=32,depth=6,device="cpu",lr=.001,batch_size=16,max_train_length=256,after_iter_callback=callback)
def encode(model,x):
 out=model.encode(np.asarray(x,np.float32)[None],causal=True,sliding_length=1,sliding_padding=255,encoding_window=None,batch_size=16)
 if out.shape!=(1,len(x),32):raise ValueError("CAUSAL_ENDPOINT_SHAPE")
 return out[0]
def verify(a):
 m=json.loads((a.report/"c-source-input-hashes.json").read_text())
 for name,rec in m.items():
  if sha(Path(name))!=rec["sha256"]:raise ValueError("C_FROZEN_INPUT_DRIFT "+name)
 auth=json.loads(a.fit_authorization.read_text())
 if "profile-C" not in auth.get("authorized_stages",[]):raise ValueError("C_PILOT_NOT_AUTHORIZED")
 if auth.get("c_protocol_sha256")!=sha(a.report/"c-protocol.json") or auth.get("c_source_input_manifest_sha256")!=sha(a.report/"c-source-input-hashes.json"):raise ValueError("C_AUTH_PIN_MISMATCH")
 return json.loads((a.report/"c-protocol.json").read_text())
def profile_C(a):
 recipe=verify(a);started=time.monotonic()
 import torch,pickle
 from sklearn.preprocessing import StandardScaler
 torch.set_num_threads(1);torch.set_num_interop_threads(1)
 panel=JointFeatures(a.old_job/"prepared-v1",a.warmup);t,x=channels(panel.panels)
 fit=(t>=ms("2024-09-01"))&(t<ms("2026-03-01"))&np.isfinite(x).all(1)
 scaler=StandardScaler().fit(x[fit]);train=scaler.transform(x[fit]).astype(np.float32)[None]
 a.output.mkdir(parents=True,exist_ok=False);curves=[];fit_start=None
 def callback(model,value):
  gradients=[p.grad.detach().norm().item()**2 for p in model._net.parameters() if p.grad is not None]
  row=dict(iteration=model.n_iters,fit_contrastive_loss=value,gradient_norm=float(np.sqrt(sum(gradients))),N_train_timestamps=int(fit.sum()),batch_size=16,validation_loss="UNKNOWN_NO_LABEL_EVALUATION",elapsed_seconds=time.monotonic()-fit_start)
  curves.append(row)
  if model.n_iters%20==0:write_json(a.output/"progress.json",dict(encoder_iterations=model.n_iters,planned_iterations=600,wall_seconds=time.monotonic()-started,quality_accessed=False))
 model=new_model(a.report,callback);fit_start=time.monotonic();model.fit(train,n_iters=600,verbose=False);fit_seconds=time.monotonic()-fit_start
 model.save(a.output/"encoder.pt");(a.output/"scaler.pkl").write_bytes(pickle.dumps(scaler));write_json(a.output/"encoder-curves.json",curves)
 with (a.output/"encoder-curves.csv").open("w") as f:
  w=csv.DictWriter(f,fieldnames=list(curves[0]));w.writeheader();w.writerows(curves)
 # Fixed real prefix input, 255 initial context plus1024 timed endpoints. No label arrays opened.
 indices=np.flatnonzero(fit)[-1279:];sample=scaler.transform(x[indices]).astype(np.float32);infer_start=time.monotonic();pred=encode(model,sample);inference_seconds=time.monotonic()-infer_start
 np.save(a.output/"pilot-embeddings.npy",pred[255:]);np.save(a.output/"pilot-origins.npy",t[indices][255:])
 # Saved averaged model roundtrip on fixed last256 input; no extra fitting.
 restored=new_model(a.report);restored.load(a.output/"encoder.pt");r1=encode(model,sample[-256:])[-1];r2=encode(restored,sample[-256:])[-1];np.testing.assert_array_equal(r1,r2)
 necessary=recipe["cost_counts"];encoder_projected=fit_seconds*necessary["unique_encoder_fits"]
 inference_projected=inference_seconds/len(sample)*necessary["total_causal_encoder_inference_timestamps"]
 estimate=recipe["preparation_budget_reserve_seconds"]+encoder_projected+inference_projected+recipe["head_budget_seconds"]
 result=dict(status="RESOURCE_ADMITTED" if estimate*1.2<=5400 else "INCOMPLETE_RESOURCE",wall_seconds=time.monotonic()-started,encoder_iterations=600,encoder_fit_seconds=fit_seconds,pilot_inference_input_timestamps=len(sample),pilot_endpoint_embeddings=1024,pilot_inference_seconds=inference_seconds,N_train_timestamps=int(fit.sum()),max_train_feature_end=int(t[fit][-1]),scaler_mean=scaler.mean_.tolist(),encoder_fit_id="full-prefix-2026-03-01",encoder_sha256=sha(a.output/"encoder.pt"),scaler_sha256=sha(a.output/"scaler.pkl"),roundtrip="PASS",cost_counts=necessary,encoder_fit_projection_seconds=encoder_projected,inference_projection_seconds=inference_projected,head_budget_seconds=recipe["head_budget_seconds"],complete_seconds_with20percent_margin=estimate*1.2,ceiling_seconds=5400,quality_accessed=False,model_reusable_only_if_same_frozen_recipe_and_pastcutoff=True)
 write_json(a.output/"resource-result.json",result)
 from .forecast_cycle_run import ledger
 ledger(a.report,dict(stage="profile-C",fit=True,seed=7,encoder_iterations=600,wall_seconds=result["wall_seconds"],status=result["status"],reason="outcomes-blind contrastive encoder cost + causal inference only"))
 print(json.dumps(result))
