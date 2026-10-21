"""Independent CatBoost/linear heads for the single bounded stage A."""
from pathlib import Path
import csv,json,pickle,time,hashlib
import numpy as np
from .forecast_cycle_data import early_split,project_quantiles,ASSETS
from .forecast_independent_data import DAY,sha,write_json
from .forecast_cycle_data import Dataset,ms
TAU=np.array([.2,.5,.8])
def pin(y,q):return np.maximum(TAU*(y[:,None]-q),(TAU-1)*(y[:,None]-q)).mean(1)
def loss(head,y,p):
 return -np.log(np.maximum(p[np.arange(len(y)),y.astype(int)],1e-12)) if head=="D" else pin(y,project_quantiles(p))
def approve(a,stage):
 auth=json.loads(a.fit_authorization.read_text());r=a.report
 if stage not in auth.get("authorized_stages",[]):raise ValueError("FIT_STAGE_NOT_AUTHORIZED")
 if auth.get("protocol_sha256")!=sha(r/"protocol.json") or auth.get("source_input_manifest_sha256")!=sha(r/"source-input-hashes.json"):raise ValueError("FIT_AUTHORIZATION_NOT_CURRENT_SOURCE_PROTOCOL")
 return auth
def record(a,event):
 from .forecast_cycle_run import ledger
 ledger(a.report,event)
def catfit(head,depth,x,y,vx=None,vy=None,iterations=500):
 from catboost import CatBoostClassifier,CatBoostRegressor
 cls=CatBoostClassifier if head=="D" else CatBoostRegressor
 model=cls(loss_function="MultiClass" if head=="D" else "MultiQuantile:alpha=0.2,0.5,0.8",depth=depth,learning_rate=.03,iterations=iterations,l2_leaf_reg=10,random_seed=7,thread_count=1,task_type="CPU",allow_writing_files=False,verbose=False)
 kwargs={}
 if vx is not None:kwargs=dict(eval_set=(vx,vy),early_stopping_rounds=50,use_best_model=True)
 model.fit(x,y,**kwargs)
 if head=="D":np.testing.assert_array_equal(model.classes_,[0,1,2])
 return model
def predict(model,head,x):
 return model.predict_proba(x) if head=="D" else model.predict(x)
def curve_rows(model,fitid,nfit,nval,head,phase):
 rows=[]
 for part,metrics in model.get_evals_result().items():
  values=next(iter(metrics.values()))
  rows += [dict(fit_id=fitid,phase=phase,head=head,partition=part,iteration=i+1,loss=float(v),N=nfit if part=="learn" else nval,gradient_norm="",logit_min="",logit_max="") for i,v in enumerate(values)]
 return rows
def linear_q_fit(x,y,vx=None,vy=None,epochs=80):
 import torch
 torch.set_num_threads(1);torch.manual_seed(7)
 from sklearn.preprocessing import StandardScaler
 scale=StandardScaler().fit(x);tx=torch.from_numpy(scale.transform(x).astype(np.float32));ty=torch.from_numpy(y.astype(np.float32));model=torch.nn.Linear(x.shape[1],3)
 opt=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=.001);rng=np.random.default_rng(7);best=None;bestloss=np.inf;stale=0;curves=[]
 tau=torch.tensor(TAU,dtype=torch.float32)
 def objective(raw,truth):
  err=truth[:,None]-raw
  return torch.maximum(tau*err,(tau-1)*err).mean()
 for epoch in range(epochs):
  model.train();gn=0.
  for chunk in np.array_split(rng.permutation(len(x)),max(1,int(np.ceil(len(x)/256)))):
   opt.zero_grad();raw=model(tx[chunk]);value=objective(raw,ty[chunk]);value.backward()
   gn=max(gn,float(torch.sqrt(sum((p.grad**2).sum() for p in model.parameters())).detach()));opt.step()
  with torch.no_grad():
   raw=model(tx);fitloss=float(objective(raw,ty));vl=None
   if vx is not None:
    vr=model(torch.from_numpy(scale.transform(vx).astype(np.float32)));vl=float(objective(vr,torch.from_numpy(vy.astype(np.float32))))
  curves.append(dict(iteration=epoch+1,fit_loss=fitloss,validation_loss=vl,gradient_norm=gn,raw_min=float(raw.min()),raw_max=float(raw.max()),N_fit=len(x),N_validation=0 if vx is None else len(vx),fit_quantile_crossing=float((torch.diff(raw,dim=1)<0).any(1).float().mean()),fit_quantile_clipping=float((raw<0).any(1).float().mean()),validation_quantile_crossing=None if vx is None else float((torch.diff(vr,dim=1)<0).any(1).float().mean()),validation_quantile_clipping=None if vx is None else float((vr<0).any(1).float().mean())))
  if vl is not None:
   if vl<bestloss-1e-9:bestloss=vl;best={k:v.clone() for k,v in model.state_dict().items()};chosen=epoch+1;stale=0
   else:stale+=1
   if stale>=5:break
 if vx is not None:model.load_state_dict(best)
 else:chosen=len(curves)
 return {"scale":scale,"state":model.state_dict(),"width":x.shape[1]},chosen,curves
def linear_q_predict(obj,x):
 import torch
 model=torch.nn.Linear(obj["width"],3);model.load_state_dict(obj["state"])
 with torch.no_grad():return model(torch.from_numpy(obj["scale"].transform(x).astype(np.float32))).numpy()
def inputs(a):
 ds=Dataset(a.old_job/"prepared-v1",a.old_job/"reports/forecast-independent-20261021/protocol.json")
 valid=np.load(a.prepared/"valid.npy");origins=np.load(a.prepared/"origins.npy");joint=np.load(a.prepared/"X_joint.npy",mmap_mode="r")
 if not np.array_equal(origins,np.unique(ds.meta["origin"])):raise ValueError("JOINT_ORIGIN_ID_MISMATCH")
 return ds,joint,np.repeat(valid,2)
def y_for(ds,ids,head):return ds.direction[ids] if head=="D" else ds.targets[ids,0,0 if head=="Q-long" else 1]
def getx(ds,joint,ids,kind):return np.asarray(joint[ids//2],np.float32) if kind=="joint" else ds.x(ids,"60x20")
def profile_A(a):
 approve(a,"profile-A");ds,joint,valid=inputs(a);protocol=json.loads((a.report/"protocol.json").read_text());end=protocol["folds"][0][0]
 allids=ds.rows("2024-09-01",end);allids=allids[(ds.meta["asset"][allids]==0)&valid[allids]]
 tr,va=early_split(ds.meta,allids,end);tr=tr[-4096:];result=[]
 for depth in (4,6):
  for head in ("D","Q-long","Q-short"):
   fitid=f"pilot-joint-BTC-d{depth}-{head}";record(a,dict(stage="profile-A",fit=True,fit_id=fitid,seed=7,reason="outcome-blind resource profile; quality is not exported"))
   t=time.monotonic();model=catfit(head,depth,getx(ds,joint,tr,"joint"),y_for(ds,tr,head),getx(ds,joint,va,"joint"),y_for(ds,va,head),iterations=50)
   result.append(dict(fit_id=fitid,depth=depth,head=head,N_fit=len(tr),N_validation=len(va),iterations=model.tree_count_,wall_seconds=time.monotonic()-t))
   del model
 a.output.mkdir(parents=True,exist_ok=False);write_json(a.output/"profile.json",{"status":"PROFILE_ONLY_NO_QUALITY_SELECTION","fits":result,"all_fits_counted":6,"recipe":protocol["A"]["pilot"]})
 print(json.dumps({"status":"PROFILE_A_COMPLETE","fits":6,"wall_seconds":sum(r["wall_seconds"] for r in result)}))
def block_ci(delta,origins,days=14):
 b=(origins-ms("2024-09-01"))//(days*DAY);u=np.unique(b);s=np.array([delta[b==v].sum() for v in u]);n=np.array([(b==v).sum() for v in u]);rng=np.random.default_rng(7);sample=rng.integers(len(u),size=(1000,len(u)));boot=s[sample].sum(1)/n[sample].sum(1)
 return np.quantile(boot,[.025,.975]).tolist(),len(u)
def rank_gate(asset,chosen,allpred,ds):
 from sklearn.metrics import roc_auc_score
 checks={};passed=True
 for cls in (0,1):
  truth=[];candidate=[];linear=[];origins=[];wins=0
  for fold in range(3):
   ids,_,p=allpred[(asset,fold,"D",chosen)];bi,_,base=allpred[(asset,fold,"D","linear")]
   np.testing.assert_array_equal(ids,bi);y=(ds.direction[ids]==cls)
   ac=roc_auc_score(y,p[:,cls]);ab=roc_auc_score(y,base[:,cls]);wins+=ac>ab and ac>.5
   truth.extend(y);candidate.extend(p[:,cls]);linear.extend(base[:,cls]);origins.extend(ds.meta["origin"][ids])
  y=np.array(truth);p=np.array(candidate);b=np.array(linear);ts=np.array(origins);block=(ts-ms("2024-09-01"))//(14*DAY);u=np.unique(block);indices=[np.flatnonzero(block==v) for v in u];rng=np.random.default_rng(7);diff=[];chance=[]
  for _ in range(1000):
   ids=np.concatenate([indices[k] for k in rng.integers(len(u),size=len(u))])
   if len(np.unique(y[ids]))<2:continue
   ac=roc_auc_score(y[ids],p[ids]);diff.append(ac-roc_auc_score(y[ids],b[ids]));chance.append(ac-.5)
  dc=np.quantile(diff,[.025,.975]).tolist();cc=np.quantile(chance,[.025,.975]).tolist();passed &= wins>=2 and dc[0]>0 and cc[0]>0
  checks[("UP","DOWN")[cls]]=dict(folds_better_than_both=int(wins),candidate_AUROC=float(roc_auc_score(y,p)),linear_AUROC=float(roc_auc_score(y,b)),vs_linear_CI95=dc,vs_chance_CI95=cc)
 return passed,checks

def stage_A(a):
 approve(a,"stage-A");protocol=json.loads((a.report/"protocol.json").read_text());ds,joint,valid=inputs(a)
 resource=json.loads(a.resource_decision.read_text())
 if resource.get("status")!="ADMITTED" or resource.get("profile_sha256")!=sha(a.profile):raise ValueError("RESOURCE_PROFILE_DECISION_NOT_SEALED")
 depths=resource["depths"]
 if depths not in ([4],[4,6]):raise ValueError("UNFROZEN_DEPTH_RECIPE")
 from .forecast_cycle_metrics import detail,monthly_records,reliability_rows
 a.output.mkdir(parents=True,exist_ok=False);curves=[];metrics=[];monthly=[];reliability=[];forecast=[];allpred={}
 def savecurves():
  with (a.output/"fit-curves.json").open("w") as f:json.dump(curves,f)
 for asset in (0,1):
  for fold,(fitend,valend) in enumerate(protocol["folds"]):
   train=ds.rows("2024-09-01",fitend);train=train[(ds.meta["asset"][train]==asset)&valid[train]]
   val=ds.rows(fitend,valend);val=val[(ds.meta["asset"][val]==asset)&valid[val]];tr,es=early_split(ds.meta,train,fitend)
   for head in ("D","Q-long","Q-short"):
    yt=y_for(ds,train,head);yv=y_for(ds,val,head)
    if head=="D":prior=np.bincount(yt.astype(int),minlength=3).astype(float);prior=np.maximum(prior,1e-12);prior/=prior.sum()
    else:prior=np.quantile(yt,TAU)
    predictions={"prior":np.tile(prior,(len(val),1))};direction_logits={"prior":np.tile(np.log(np.maximum(prior,1e-12)),(len(val),1))} if head=="D" else {}
    x=getx(ds,joint,train,"joint");vx=getx(ds,joint,val,"joint")
    if head=="D":
     from sklearn.pipeline import make_pipeline
     from sklearn.preprocessing import StandardScaler
     from sklearn.linear_model import LogisticRegression
     fitid=f"linear-{asset}-{fold}-{head}";record(a,dict(stage="A",fit=True,fit_id=fitid,seed=7,reason="fixed logistic baseline"))
     model=make_pipeline(StandardScaler(),LogisticRegression(C=1,solver="lbfgs",max_iter=1000))
     model.fit(x,yt);np.testing.assert_array_equal(model.classes_,[0,1,2]);predictions["linear"]=model.predict_proba(vx);direction_logits["linear"]=model.decision_function(vx)
     with (a.output/f"{fitid}.pkl").open("wb") as f:pickle.dump(model,f)
    else:
     fitid=f"linear-{asset}-{fold}-{head}"
     record(a,dict(stage="A",fit=True,fit_id=fitid+"-ES",seed=7,reason="fixed independent pinball baseline earlystop"))
     _,epochs,c=linear_q_fit(getx(ds,joint,tr,"joint"),y_for(ds,tr,head),getx(ds,joint,es,"joint"),y_for(ds,es,head))
     curves += [dict(fit_id=fitid,phase="ES",head=head,**r) for r in c]
     record(a,dict(stage="A",fit=True,fit_id=fitid+"-refit",seed=7,reason="full prefix selectedepochs",epochs=epochs))
     model,_,c=linear_q_fit(x,yt,epochs=epochs);curves += [dict(fit_id=fitid,phase="refit",head=head,**r) for r in c]
     predictions["linear"]=linear_q_predict(model,vx)
     with (a.output/f"{fitid}.pkl").open("wb") as f:pickle.dump(model,f)
    for kind,depth in [("joint",d) for d in depths]+[("shape",4)]:
     label=f"{kind}-d{depth}";fitid=f"{label}-{asset}-{fold}-{head}"
     record(a,dict(stage="A",fit=True,fit_id=fitid+"-ES",seed=7,reason="purged last28d earlystop independenthead"))
     esmodel=catfit(head,depth,getx(ds,joint,tr,kind),y_for(ds,tr,head),getx(ds,joint,es,kind),y_for(ds,es,head))
     curves.extend(curve_rows(esmodel,fitid,len(tr),len(es),head,"ES"));iterations=esmodel.get_best_iteration()+1
     record(a,dict(stage="A",fit=True,fit_id=fitid+"-refit",seed=7,reason="fullprefix refit",iterations=iterations))
     model=catfit(head,depth,getx(ds,joint,train,kind),yt,iterations=iterations)
     curves.extend(curve_rows(model,fitid,len(train),0,head,"refit"));predictions[label]=predict(model,head,getx(ds,joint,val,kind))
     if head=="D":direction_logits[label]=model.predict(getx(ds,joint,val,kind),prediction_type="RawFormulaVal")
     path=a.output/f"{fitid}.cbm";model.save_model(str(path))
     cls=type(model);restored=cls();restored.load_model(str(path))
     np.testing.assert_allclose(predict(restored,head,getx(ds,joint,val[:16],kind)),predictions[label][:16],rtol=0,atol=1e-12)
    for method,raw in predictions.items():
     p=raw if head=="D" else project_quantiles(raw);losses=loss(head,yv,p)
     metrics.append(dict(asset=ASSETS[asset],fold=fold,head=head,method=method,N=len(val),loss=float(losses.mean()),zero_truth=float((yv==0).mean()) if head!="D" else None,crossing=float((np.diff(raw,axis=1)<0).any(1).mean()) if head!="D" else None,clipping=float((raw<0).any(1).mean()) if head!="D" else None))
     metrics[-1].update(detail(head,yv,raw))
     meta_base=dict(asset=ASSETS[asset],fold=fold,head=head,method=method)
     monthly.extend(monthly_records(ds.meta,val,yv,raw,head,meta_base))
     if head=="D":reliability.extend(reliability_rows(yv,p,meta_base))
     for i,row in enumerate(val):forecast.append(dict(row=int(row),model_id=f"{method}-{asset}-{fold}-{head}",asset=ASSETS[asset],fold=fold,head=head,method=method,origin=int(ds.meta["origin"][row]),fit_cutoff=fitend,max_fit_label_expiry=int(ds.meta["expiry"][train].max()),feature_end=int(ds.meta["origin"][row]),forecast_age=0,truth=yv[i].item(),upper_truth="" if head=="D" else float(ds.targets[row,1,0 if head=="Q-long" else 1]),raw=json.dumps(raw[i].tolist()),raw_logits="" if head!="D" else json.dumps(direction_logits[method][i].tolist()),projected=json.dumps(p[i].tolist()),loss=float(losses[i]),coverage="eligible"))
     allpred[(asset,fold,head,method)]=(val,losses,p)
    savecurves();write_json(a.output/"fold-metrics.json",metrics)
 import gzip
 with gzip.open(a.output/"forecasts.csv.gz","wt",newline="") as f:w=csv.DictWriter(f,fieldnames=list(forecast[0]));w.writeheader();w.writerows(forecast)
 with (a.output/"fold-metrics.csv").open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=list(metrics[0]));w.writeheader();w.writerows(metrics)
 for name,data in (("monthly-metrics.csv",monthly),("reliability-bins.csv",reliability)):
  if data:
   with (a.output/name).open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 write_json(a.output/"model-manifest.json",{p.name:{"sha256":sha(p),"bytes":p.stat().st_size} for p in a.output.iterdir() if p.suffix in (".cbm",".pkl")})
 gates=[]
 for asset in (0,1):
  for head in ("D","Q-long","Q-short"):
   candidates=[f"joint-d{d}" for d in depths]
   chosen=min(candidates,key=lambda m:(np.mean([r["loss"] for r in metrics if r["asset"]==ASSETS[asset] and r["head"]==head and r["method"]==m]),m))
   checks={};passed=True
   for baseline in ("prior","linear"):
    deltas=[];origins=[];foldwins=0
    for fold in range(3):
     ids,lp,_=allpred[(asset,fold,head,chosen)];bi,lb,_=allpred[(asset,fold,head,baseline)]
     np.testing.assert_array_equal(ids,bi);d=lp-lb;foldwins+=d.mean()<0;deltas.extend(d);origins.extend(ds.meta["origin"][ids])
    ci,blocks=block_ci(np.array(deltas),np.array(origins));ok=np.mean(deltas)<0 and foldwins>=2 and ci[1]<0;passed &= ok
    checks[baseline]=dict(mean_difference=float(np.mean(deltas)),folds_better=int(foldwins),CI95=ci,blocks=blocks,sensitivity={str(days):block_ci(np.array(deltas),np.array(origins),days)[0] for days in (7,28)})
   status="PREDICTIVE_PASS" if passed else "NO_SKILL"
   if not passed and head=="D":
    rank_ok,rank_checks=rank_gate(asset,chosen,allpred,ds);checks["rank_only"]=rank_checks
    if rank_ok:status="RANK_ONLY"
   gates.append(dict(asset=ASSETS[asset],head=head,chosen=chosen,status=status,comparisons=checks))
 if curves:
  fields=list(dict.fromkeys(k for row in curves for k in row))
  with (a.output/"fit-curves.csv").open("w",newline="") as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(curves)
 write_json(a.output/"gates.json",gates);record(a,dict(stage="A",fit=False,status="DEVELOPMENT_COMPLETE",reason="fixed heads gate evaluated; March/CHECK unopened"))
 print(json.dumps({"status":"A_DEVELOPMENT_COMPLETE","gates":gates}))

def profile_baseline(a):
 approve(a,"profile-baseline");ds,joint,valid=inputs(a);ids=ds.rows("2024-09-01","2025-03-01");ids=ids[(ds.meta["asset"][ids]==0)&valid[ids]];tr,va=early_split(ds.meta,ids,"2025-03-01");tr=tr[-4096:];rows=[]
 from sklearn.pipeline import make_pipeline
 from sklearn.preprocessing import StandardScaler
 from sklearn.linear_model import LogisticRegression
 for head in ("D","Q-long","Q-short"):
  fitid="baseline-pilot-"+head;record(a,dict(stage="profile-baseline",fit=True,fit_id=fitid,seed=7,reason="fixed resource measurement only; no quality export"))
  x=getx(ds,joint,tr,"joint");vx=getx(ds,joint,va,"joint");y=y_for(ds,tr,head);vy=y_for(ds,va,head);t=time.monotonic()
  if head=="D":
   model=make_pipeline(StandardScaler(),LogisticRegression(C=1,solver="lbfgs",max_iter=1000));model.fit(x,y);iterations=int(model[-1].n_iter_.max())
  else:
   _,_,curves=linear_q_fit(x,y,vx,vy);iterations=len(curves)
  wall=time.monotonic()-t
  rows.append(dict(head=head,N_fit=len(tr),N_validation=len(va),computed_iterations=iterations,wall_seconds=wall,seconds_per_iteration=wall/iterations))
 a.output.mkdir(parents=True,exist_ok=False);write_json(a.output/"profile.json",dict(status="RESOURCE_PROFILE_ONLY",fits=rows))
 print(json.dumps({"status":"BASELINE_PROFILE_COMPLETE","fits":3,"wall_seconds":sum(r["wall_seconds"] for r in rows)}))

def resource_estimate(a):
 ds,joint,valid=inputs(a);profile=json.loads(a.profile.read_text());baseline=json.loads(a.baseline_profile.read_text());protocol=json.loads((a.report/"protocol.json").read_text())
 scaling=json.loads(a.scaling_profile.read_text()) if a.scaling_profile else None
 cb={r["head"]:r["wall_seconds"] for r in profile["fits"] if r["depth"]==4};b={r["head"]:r["seconds_per_iteration"] for r in baseline["fits"]};n0=3645+648
 def counts(end,asset=0):
  ids=np.flatnonzero((ds.meta["origin"]>=ms("2024-09-01"))&(ds.meta["origin"]<ms(end))&(ds.meta["expiry"]<=ms(end))&ds.meta["observed"]&(ds.meta["asset"]==asset)&valid)
  if not len(ids):return (0,0,0)
  tr,es=early_split(ds.meta,ids,end);return len(tr),len(es),len(ids)
 def catcost(end,head,kind="joint"):
  tr,es,full=counts(end)
  if not full:return 0
  if scaling:
   # Largest measured realTRAIN500 fit already includes quantization. Keep shape at750-feature cost.
   head_safety=max(cb.values())/cb["Q-short"]
   return scaling["wall_seconds"]*head_safety*(tr+es+full)/scaling["N_fit"]
  factor=1 if kind=="joint" else 124/750
  return cb[head]*10*((tr+es+full)/n0)*factor
 def linearcost(end,head):
  tr,es,full=counts(end)
  if head=="D":return b[head]*1000*full/3645
  return b[head]*80*(tr+es+full)/3645
 dev_cb=sum(catcost(f[0],h,k) for f in protocol["folds"] for h in ("D","Q-long","Q-short") for k in ("joint","shape"))*2
 dev_linear=sum(linearcost(f[0],h) for f in protocol["folds"] for h in ("D","Q-long","Q-short"))*2
 final=sum(catcost("2026-03-01",h) for h in ("D","Q-long","Q-short"));final_linear=sum(linearcost("2026-03-01",h) for h in ("D","Q-long","Q-short"))
 quarterly=sum(catcost(c,h) for c in protocol["quarterly_cutoffs"] for h in ("D","Q-long","Q-short"))
 already=sum(r["wall_seconds"] for r in profile["fits"])+sum(r["wall_seconds"] for r in baseline["fits"])
 # Explicit allowances are separate, never omitted from admission.
 inference_allowance=180;metric_bootstrap_allowance=120;serialization_allowance=60
 if scaling:already+=scaling["wall_seconds"]
 prior_waste=537.5391515409574
 profile_external_overhead=121.2936317496933-117.71713816653937
 subtotal=dev_cb+dev_linear+final+final_linear+quarterly+already+prior_waste+profile_external_overhead+inference_allowance+metric_bootstrap_allowance+serialization_allowance
 margin=subtotal*.20
 total=subtotal+margin
 result={"status":"ADMITTED" if total<=7200 else "INCOMPLETE_RESOURCE","budget_wall_seconds":7200,"depths":[4],"depth6_decision":"DROP_RESOURCE_ONLY_ROOT_BEFORE_CONTROLS_OR_DEVELOPMENT_QUALITY","profile_sha256":sha(a.profile),"baseline_profile_sha256":sha(a.baseline_profile),"scaling_profile_sha256":sha(a.scaling_profile) if a.scaling_profile else None,"measured_scaling_500":scaling,"cost_safety_head_factor":max(cb.values())/cb["Q-short"],"safety_margin_seconds":margin,"safety_margin_percent":20,"conservative_shape_feature_discount":False if scaling else True,"measured_profile_iterations_computed":50,"selected_tree_count_not_used":True,"measured_profile_N_fit":3645,"measured_profile_N_validation":648,"structural_original_all_heads_upper_fits":342,"structural_after_depth6drop_plus_baselinepilots_and_scaling_upper_fits":310,"necessary_conditional_BTCfallback_counts":{"development_CatBoost_ES_refit":72,"development_logistic":6,"development_linearQ_ES_refit":24,"final_BTC_CatBoost_ES_refit_max":6,"final_BTC_logistic":1,"final_BTC_linearQ_ES_refit":4,"quarterly_BTC_CatBoost_ES_refit_max":42,"quarterly_Sep2024_skipped_zero_mature_rows":True,"purged_prefix_counts":{c:counts(c) for c in protocol["quarterly_cutoffs"]},"SOL_quarterly":0,"quarterly_linear_baselines":0,"pilot_CatBoost":6,"pilot_baselines":3,"pilot_scaling":1,"stage0_controls_separate":9},"estimated_seconds":{"development_CatBoost":dev_cb,"development_linear":dev_linear,"conditional_final_BTC3heads":final,"conditional_final_BTClinear_controls":final_linear,"conditional_quarterly_BTC3heads":quarterly,"measured_profiles_already_spent":already,"profile_external_overhead":profile_external_overhead,"quarantined_original_A_wall_seconds":prior_waste,"inference_allowance":inference_allowance,"metric_bootstrap_allowance":metric_bootstrap_allowance,"serialization_allowance":serialization_allowance},"total_projected_seconds":total,"total_projected_minutes":total/60,"needed_additional_minutes_over_ceiling":max(0,total/60-120),"projection_assumptions":(["measured500fullprefix fit; purgedinputrow scaling for earlier/laterprefixes, allheads raised by largest50iteration head timingratio","shape chargedfull750feature cost","20percent whole-stage safety margin","no quality-driven earlystop assumed"] if scaling else [])+["50-to500iteration fallback extrapolation only if no full500probe; never assume earlystop from unseenquality","perfit inputrow scaling using actual purgedprefix counts","linearD1000iterations andQ80epochs; Qlong includes firstTorchimport and conservatively repeats overhead","all REQUIRED conditional BTC3heads final+7nonemptyquarterly caches reserved, not unusedSOL/linearquarterlyfits","five-minute total inference/bootstrap/model-I/O allowances stated separately"],"uncertainty":"Projection not measured full-stage time; earlystopping may reduce actual cost, data/feature scaling and setup costs may differ. No quality-driven faststop assumed.","development_only_projected_minutes":(dev_cb+dev_linear+already+inference_allowance+metric_bootstrap_allowance+serialization_allowance)/60,"cannot_substitute":"A passing development recipe without causal prefix cache is INCOMPLETE, no economic run","fit_counts_not_instructions":"Do not execute unused conditional fits"}
 a.output.mkdir(parents=True,exist_ok=False);write_json(a.output/"resource-admission.json",result);print(json.dumps(result))

def profile_scaling(a):
 approve(a,"profile-scaling");ds,joint,valid=inputs(a);ids=ds.rows("2024-09-01","2026-03-01");ids=ids[(ds.meta["asset"][ids]==0)&valid[ids]]
 fitid="scaling-BTC-Q-short-joint-d4-500";record(a,dict(stage="profile-scaling",fit=True,fit_id=fitid,seed=7,reason="one fullprefix fixed500iteration resource measurement;noES/noqualityexport"))
 t=time.monotonic();model=catfit("Q-short",4,getx(ds,joint,ids,"joint"),y_for(ds,ids,"Q-short"),iterations=500);wall=time.monotonic()-t
 computed=len(next(iter(model.get_evals_result()["learn"].values())))
 if computed!=500:raise ValueError("RESOURCE_PROBE_NOT500COMPUTED")
 result=dict(status="RESOURCE_SCALING_ONLY",fit_id=fitid,N_fit=len(ids),feature_width=750,depth=4,computed_iterations=500,early_stopping=False,validation_rows=0,fit_cutoff="2026-03-01",max_fit_label_expiry=int(ds.meta["expiry"][ids].max()),wall_seconds=wall,quality_export=False,model_saved=False)
 del model
 a.output.mkdir(parents=True,exist_ok=False);write_json(a.output/"profile.json",result);print(json.dumps(result))
