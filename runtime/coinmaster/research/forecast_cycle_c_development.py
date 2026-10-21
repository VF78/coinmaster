"""Resumed fixed TS2Vec development only. No economic or future-check paths."""
from pathlib import Path
import csv,gzip,hashlib,json,pickle,time
import numpy as np
from .forecast_cycle_data import ASSETS,early_split,project_quantiles,ms
from .forecast_independent_data import HOUR,DAY,sha,write_json
from .forecast_cycle_ts2vec import channels,new_model,encode
from .forecast_cycle_train import inputs,getx,y_for,catfit,predict,curve_rows,loss,block_ci,rank_gate
METHOD="joint-ts2vec-d4"
def verify(a):
 r=a.report;m=json.loads((r/"c-resume-source-input-hashes.json").read_text())
 for name,rec in m.items():
  if sha(Path(name))!=rec["sha256"]:raise ValueError("C_RESUME_PIN_DRIFT "+name)
 auth=json.loads(a.fit_authorization.read_text())
 if "stage-C-development" not in auth.get("authorized_stages",[]):raise ValueError("C_DEV_NOT_AUTHORIZED")
 checks={"c_resume_protocol_sha256":r/"c-resume-protocol.json","c_resume_manifest_sha256":r/"c-resume-source-input-hashes.json","resource_admission_sha256":r/"c-resume-resource-admission.json"}
 for key,p in checks.items():
  if auth.get(key)!=sha(p):raise ValueError("C_DEV_AUTH_PIN "+key)
 decision=json.loads((r/"c-resume-resource-admission.json").read_text())
 if decision["status"]!="ADMITTED" or decision["budget_wall_seconds"]!=7200:raise ValueError("C_RESUME_RESOURCE_NOT_ADMITTED")
 return json.loads((r/"protocol.json").read_text())
def prefix_scale(t,x,end):
 from sklearn.preprocessing import StandardScaler
 fit=(t>=ms("2024-09-01"))&(t<end)
 if not fit.any() or not np.isfinite(x[fit]).all():raise ValueError("INVALID_TRAIN_CHANNEL_PREFIX")
 if np.any(np.diff(t[fit])!=HOUR):raise ValueError("GAPPED_TRAIN_CHANNEL_PREFIX")
 return StandardScaler().fit(x[fit]),fit
def rows_embedding(meta,ids,t,z):
 wanted=meta["origin"][ids];j=np.searchsorted(t,wanted)
 if np.any(j>=len(t)) or not np.array_equal(t[j],wanted):raise ValueError("EMBEDDING_ID_ALIGNMENT")
 if not np.isfinite(z[j]).all():raise ValueError("INVALID_EMBEDDING_COVERAGE")
 return z[j]
def encoder_cache(a,t,x,fitend,valend,role):
 from .forecast_cycle_run import ledger
 end=ms(fitend)-(28*DAY if role=="ES" else 0);infer_end=ms(fitend if role=="ES" else valend)
 cache=a.output/"encoders"/(fitend+"-"+role);cache.mkdir(parents=True,exist_ok=False)
 scale,fit=prefix_scale(t,x,end);curves=[];start=time.monotonic();fitstart=None
 def callback(model,value):
  g=[p.grad.detach().norm().item()**2 for p in model._net.parameters() if p.grad is not None]
  curves.append(dict(fit_id=fitend+"-"+role,iteration=model.n_iters,fit_contrastive_loss=value,gradient_norm=float(np.sqrt(sum(g))),N_train_timestamps=int(fit.sum()),max_train_feature_end=int(t[fit][-1]),validation_loss="UNKNOWN_NO_FORECAST_LABELS",wall_seconds=time.monotonic()-fitstart))
 model=new_model(a.report,callback);fitstart=time.monotonic()
 ledger(a.report,dict(stage="C",fit=True,fit_id="encoder-"+fitend+"-"+role,seed=7,iterations=600,encoder_training_end=end,reason="fixed prefix-only contrastiveencoder; ES/full isolated"))
 model.fit(scale.transform(x[fit]).astype(np.float32)[None],n_iters=600,verbose=False)
 fitwall=time.monotonic()-fitstart;model.save(cache/"encoder.pt");(cache/"scaler.pkl").write_bytes(pickle.dumps(scale))
 write_json(cache/"fit-curves.json",curves)
 with (cache/"fit-curves.csv").open("w") as f:
  w=csv.DictWriter(f,fieldnames=list(curves[0]));w.writeheader();w.writerows(curves)
 # Exact255 real context bars precede first eligible market origin. API adds only older padding.
 first=ms("2024-09-01")-255*HOUR;selected=(t>=first)&(t<infer_end)
 tt=t[selected];xx=scale.transform(x[selected]).astype(np.float32)
 if not np.isfinite(xx).all() or tt[0]!=first:raise ValueError("INVALID_REAL_ENCODER_CONTEXT")
 istart=time.monotonic();z=encode(model,xx);inferwall=time.monotonic()-istart
 np.save(cache/"origins.npy",tt);np.save(cache/"embedding.npy",z)
 # Saved averaged weights must reconstruct actual fixed endpoint prediction.
 restored=new_model(a.report);restored.load(cache/"encoder.pt")
 np.testing.assert_array_equal(encode(model,xx[-256:])[-1],encode(restored,xx[-256:])[-1])
 receipt=dict(role=role,fit_cutoff=fitend,encoder_training_end=end,max_train_feature_end=int(t[fit][-1]),N_train_timestamps=int(fit.sum()),iterations=600,fit_wall_seconds=fitwall,inference_wall_seconds=inferwall,wall_seconds=time.monotonic()-start,inference_end_exclusive=infer_end,causal=True,sliding_length=1,sliding_padding=255,output_dims=32,encoder_sha256=sha(cache/"encoder.pt"),scaler_sha256=sha(cache/"scaler.pkl"),embedding_sha256=sha(cache/"embedding.npy"),roundtrip="PASS",quality_selection=False)
 write_json(cache/"receipt.json",receipt)
 del model,restored
 return tt,z,receipt
def load_reference(path):
 grouped={}
 with gzip.open(path,"rt") as f:
  for row in csv.DictReader(f):
   if row["method"] not in ("prior","linear","joint-d4"):continue
   key=(ASSETS.index(row["asset"]),int(row["fold"]),row["head"],row["method"])
   grouped.setdefault(key,[]).append(row)
 result={}
 for key,rows in grouped.items():
  ids=np.array([int(r["row"]) for r in rows],np.int64)
  if len(np.unique(ids))!=len(ids) or np.any(np.diff(ids)<=0):raise ValueError("A_REFERENCE_IDS")
  result[key]=(ids,np.array([json.loads(r["raw"]) for r in rows]),np.array([float(r["loss"]) for r in rows]),rows)
 if len(result)!=54:raise ValueError("A_REFERENCE_GROUP_COUNT")
 return result
def development(a):
 protocol=verify(a);start=time.monotonic()
 import torch
 torch.set_num_threads(1);torch.set_num_interop_threads(1)
 from .forecast_cycle_data import JointFeatures
 from .forecast_cycle_metrics import detail,monthly_records,reliability_rows
 from .forecast_cycle_run import ledger
 ds,joint,valid=inputs(a);references=load_reference(a.reuse_inference/"forecasts.csv.gz")
 a.output.mkdir(parents=True,exist_ok=False)
 panel=JointFeatures(a.old_job/"prepared-v1",a.warmup);t,x=channels(panel.panels)
 curves=[];metrics=[];monthly=[];reliability=[];forecasts=[];allpred={};models={}
 for fold,(fitend,valend) in enumerate(protocol["folds"]):
  et,ez,er=encoder_cache(a,t,x,fitend,valend,"ES");ft,fz,fr=encoder_cache(a,t,x,fitend,valend,"full")
  for asset in (0,1):
   train=ds.rows("2024-09-01",fitend);train=train[(ds.meta["asset"][train]==asset)&valid[train]]
   val=ds.rows(fitend,valend);val=val[(ds.meta["asset"][val]==asset)&valid[val]]
   tr,es=early_split(ds.meta,train,fitend)
   def features(ids,role):
    tt,zz=(et,ez) if role=="ES" else (ft,fz)
    z=rows_embedding(ds.meta,ids,tt,zz)
    return np.column_stack([getx(ds,joint,ids,"joint"),z]).astype(np.float32)
   for head in ("D","Q-long","Q-short"):
    fid=f"{METHOD}-{asset}-{fold}-{head}"
    ledger(a.report,dict(stage="C",fit=True,fit_id=fid+"-ES",seed=7,reason="fixedAdepth4 recipe; independent ESencoder/scaler before28dayboundary"))
    model=catfit(head,4,features(tr,"ES"),y_for(ds,tr,head),features(es,"ES"),y_for(ds,es,head));curves.extend(curve_rows(model,fid,len(tr),len(es),head,"ES"));iterations=model.get_best_iteration()+1
    del model
    ledger(a.report,dict(stage="C",fit=True,fit_id=fid+"-refit",seed=7,iterations=iterations,reason="fixedselectediterationcount; independentfullprefixencoder"))
    model=catfit(head,4,features(train,"full"),y_for(ds,train,head),iterations=iterations)
    curves.extend(curve_rows(model,fid,len(train),0,head,"refit"))
    vx=features(val,"full");raw=predict(model,head,vx);logits=model.predict(vx,prediction_type="RawFormulaVal") if head=="D" else None
    path=a.output/(fid+".cbm");model.save_model(str(path));restored=type(model)();restored.load_model(str(path));np.testing.assert_allclose(predict(restored,head,vx[:16]),raw[:16],rtol=0,atol=1e-12)
    models[path.name]=dict(sha256=sha(path),fit_cutoff=fitend,max_fit_label_expiry=int(ds.meta["expiry"][train].max()),ES_encoder=er["encoder_sha256"],full_encoder=fr["encoder_sha256"],selected_iterations=iterations,class_mapping=[0,1,2] if head=="D" else None,roundtrip="PASS")
    del model,restored
    y=y_for(ds,val,head);predictions={METHOD:(raw,logits)}
    for baseline in ("prior","linear","joint-d4"):
     ids,rr,ll,original=references[(asset,fold,head,baseline)];np.testing.assert_array_equal(ids,val)
     np.testing.assert_allclose(loss(head,y,rr),ll,rtol=0,atol=1e-12)
     lp=np.array([json.loads(row["raw_logits"]) for row in original]) if head=="D" else None
     predictions[baseline]=(rr,lp)
    for method,(rr,lg) in predictions.items():
     pp=rr if head=="D" else project_quantiles(rr);ll=loss(head,y,pp);base=dict(asset=ASSETS[asset],fold=fold,head=head,method=method)
     metrics.append(dict(**base,N=len(val),unique_days=len(np.unique(ds.meta["origin"][val]//DAY)),loss=float(ll.mean()),crossing=float((np.diff(rr,axis=1)<0).any(1).mean()) if head!="D" else None,clipping=float((rr<0).any(1).mean()) if head!="D" else None,**detail(head,y,rr)))
     monthly.extend(monthly_records(ds.meta,val,y,rr,head,base))
     if head=="D":reliability.extend(reliability_rows(y,pp,base))
     allpred[(asset,fold,head,method)]=(val,ll,pp)
     for i,row in enumerate(val):
      forecasts.append(dict(row=int(row),model_id=f"{method}-{asset}-{fold}-{head}",**base,origin=int(ds.meta["origin"][row]),fit_cutoff=fitend,max_fit_label_expiry=int(ds.meta["expiry"][train].max()),feature_end=int(ds.meta["origin"][row]),forecast_age=0,truth=y[i].item(),upper_truth="" if head=="D" else float(ds.targets[row,1,0 if head=="Q-long" else 1]),raw=json.dumps(rr[i].tolist()),raw_logits=json.dumps(lg[i].tolist()) if head=="D" else "",projected=json.dumps(pp[i].tolist()),loss=float(ll[i]),coverage="eligible",reference_reused=method!=METHOD))
    write_json(a.output/"model-manifest.json",models);write_json(a.output/"fit-curves.json",curves);write_json(a.output/"fold-metrics.json",metrics)
    write_json(a.output/"progress.json",dict(completed_head_refits=len(models),planned_head_refits=18,fold=fold,asset=ASSETS[asset],head=head,wall_seconds=time.monotonic()-start,March_CHECK="UNOPENED"))
  del ez,fz
 gates=[]
 for asset in (0,1):
  for head in ("D","Q-long","Q-short"):
   checks={};passed=True
   for baseline in ("prior","linear","joint-d4"):
    delta=[];origins=[];wins=0
    for fold in range(3):
     ids,lc,_=allpred[(asset,fold,head,METHOD)];ii,lb,_=allpred[(asset,fold,head,baseline)];np.testing.assert_array_equal(ids,ii)
     dd=lc-lb;wins+=dd.mean()<0;delta.extend(dd);origins.extend(ds.meta["origin"][ids])
    dd=np.array(delta);tt=np.array(origins);ci,blocks=block_ci(dd,tt)
    checks[baseline]=dict(mean_difference=float(dd.mean()),folds_better=int(wins),CI95=ci,blocks=blocks,sensitivity={str(days):block_ci(dd,tt,days)[0] for days in (7,28)})
    if baseline in ("prior","linear"):passed &= dd.mean()<0 and wins>=2 and ci[1]<0
   status="PREDICTIVE_PASS" if passed else "NO_SKILL"
   if head=="D" and not passed:
    rankpass,rankchecks=rank_gate(asset,METHOD,allpred,ds);checks["rank_only"]=rankchecks
    if rankpass:status="RANK_ONLY"
   gates.append(dict(asset=ASSETS[asset],head=head,chosen=METHOD,status=status,comparisons=checks,joint_comparison="paired ablation, original admission gate remains prior+linear"))
 def csvout(name,data):
  if not data:return
  fields=list(dict.fromkeys(k for row in data for k in row))
  opener=gzip.open if name.endswith(".gz") else open
  with opener(a.output/name,"wt",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
 for name,data in [("fold-metrics.csv",metrics),("fit-curves.csv",curves),("monthly-metrics.csv",monthly),("reliability-bins.csv",reliability),("forecasts.csv.gz",forecasts)]:csvout(name,data)
 write_json(a.output/"gates.json",gates);write_json(a.output/"completion.json",dict(status="C_DEVELOPMENT_COMPLETE",wall_seconds=time.monotonic()-start,encoder_fits=6,CatBoost_fits=36,reused_A_reference_groups=54,March_CHECK="UNOPENED",gates=gates))
 ledger(a.report,dict(stage="C",fit=False,status="DEVELOPMENT_COMPLETE",reason="fixedindependentheads; Acontrolsreused; originalgates; noMarch/CHECK"))
 print(json.dumps(dict(status="C_DEVELOPMENT_COMPLETE",gates=gates)))
