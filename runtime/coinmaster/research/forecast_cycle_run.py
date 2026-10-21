"""Single entry point for AI-CYCLE-20261021-01. No engine or service actions."""
from __future__ import annotations
import argparse,csv,datetime,hashlib,json,os,platform,resource,subprocess,time
from pathlib import Path
import numpy as np
from .forecast_cycle_data import JointFeatures,feature_names,ASSETS
from .forecast_independent_data import sha,write_json
from .forecast_cycle_data import Dataset,ms
from .forecast_independent_models import scores,softmax,pinball
TASK="AI-CYCLE-20261021-01"
BASE="31dc0a6b5380ee60ea5cfa3f9189a1d830e352d8"
AUDIT="85fdd78ce248e56d35dc62563a7cdf4f2c100cca"
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def ledger(report,entry):
 p=Path(report)/"selection-ledger.json";data=json.loads(p.read_text()) if p.exists() else {"task":TASK,"entries":[]}
 data["entries"].append({"utc":now(),**entry});write_json(p,data)
def freeze(a):
 r=a.report;r.mkdir(parents=True,exist_ok=True)
 if (r/"protocol.json").exists():raise ValueError("FREEZE_ALREADY_EXISTS")
 protocol={
 "task":TASK,"frozen_at":now(),"stage0_accounting_start_utc":"2026-10-21T16:28:00Z","source_HEAD":BASE,"audit_base":AUDIT,
 "task_contract_sha256":sha(r/"task-contract.txt"),"task_contract":"task-contract.txt (all sections binding; no omitted section is waived)",
 "train":["2024-09-01","2026-04-01"],"folds":[["2025-03-01","2025-06-01"],["2025-06-01","2025-09-01"],["2025-09-01","2025-12-01"]],
 "final_fit_end":"2026-03-01","march_validation":["2026-03-01","2026-04-01"],"historically_studied_check":["2026-04-01","2026-10-21"],
 "causality":{"bar_end_lte_origin":True,"entry_delay_seconds":60,"horizon_seconds":86400,"label_expiry_lte_fit_end":True,"same_timestamp_assets_same_partition":True,"sigma":"std(last168 completed1h logreturns,ddof1)*sqrt24"},
 "labels":{"reuse":"forecast_independent_data.targets/target_batch unmodified","classes":["UP","DOWN","NEUTRAL"],"terminal_bound_sigma":0.25,"SL_sigma":1,"quantiles":[0.2,0.5,0.8],"train":"lower MFE only; upper truth retained","censored":"never zero","ties":"retain strict and nonstrict coverage"},
 "selection":{"calibration":False,"evaluation_order":["development","frozen shortlist","March once","historical CHECK once","native only gated"],"D":"logloss independently","Q-long":"lower pinball independently","Q-short":"lower pinball independently","tie":"smaller depth, then X_joint before augmentation","bootstrap":{"block_days":14,"sensitivity_days":[7,28],"draws":1000,"seed":7,"common_blocks_both_assets":True}},
 "A":{"assets_separate":True,"heads":["D","Q-long","Q-short"],"joint_depths":[4,6],"shape_depths":[4],"learning_rate":0.03,"iterations":500,"l2_leaf_reg":10,"random_seed":7,"thread_count":1,"task_type":"CPU","class_weights":None,"D_loss":"MultiClass","Q_loss":"MultiQuantile:alpha=0.2,0.5,0.8","ES":{"last_fit_days":28,"patience":50,"purge_full_horizon":True,"refit_full_prefix":True},"linear_D":{"StandardScaler":True,"C":1,"solver":"lbfgs","max_iter":1000,"class_weight":None},"linear_Q":{"Adam_lr":0.001,"L2":0.001,"batch":256,"max_epochs":80,"patience":5,"heads_independent":True},"prior":"asset-specific full TRAIN-prefix class frequencies/quantiles","pilot":{"asset":"BTCUSDT","first_prefix_last_rows":4096,"ES_validation_days":28,"heads":["D","Q-long","Q-short"],"depths":[4,6],"max_iterations":50,"quality_hidden":True,"drop_depth6_only_on_resources_before_metrics":True}},
 "fit_counts":{"A_development_CatBoost_ES_plus_refit":108,"A_development_linear_D":6,"A_development_linear_Q_ES_plus_refit":24,"A_final_CatBoost_max":12,"A_quarterly_CatBoost_max":96,"A_final_linear_D":2,"A_final_linear_Q_ES_plus_refit":8,"A_quarterly_linear_D_max":16,"A_quarterly_linear_Q_ES_plus_refit_max":64,"pilot_CatBoost_max":6,"final_and_quarterly_only_for_admitted_heads":True,"note":"Eight quarterly cutoffs; earliest may be insufficient real fit data. Counts are upper bounds, not permission."},
 "quarterly_cutoffs":["2024-09-01","2024-12-01","2025-03-01","2025-06-01","2025-09-01","2025-12-01","2026-03-01","2026-06-01"],
 "coverage":{"invalid":"abstain on either asset insufficient history/nonpositive denominator/nonfinite; do not change per method","overlay_insufficient_early_fit":"S0; preexisting early DD>50 excludes overlay","new_strategy_insufficient_early_fit":"flat on its OWN equity","timeout":"INCOMPLETE, no silent substitution"},
 "controls":{"old_models_sample":"first256 chronological mature final-fit IDs and first256 mature March IDs, both assets; ensemble oldCNN seeds7/42","synthetic":"fixed seed7,1024 rows known nonlinear direction/quantile dependency; same independent heads","negative":"TRAIN14day block permutation synchronizedBTC/SOL; unpermuted temporal validation; one fixed seed7"},
 "mechanisms":{"H-BTC":"executed price-profitable TP then favorable movement then return to current native average; no SOL; reduce50% once per parent; mandatory exits priority; no new rights/reopen","H-SOL":"skip next add-right once when existingSOL_UPnL<0,BTC_UPnL>0,-SOL_UPnL>BTC_UPnL,equity<priorHWM; never block initialSOL or hourly retry","action_value":"ACTION_VALUE_UNIDENTIFIED: no restorable paired branches/complete domain-right state found; no MLoverlay training","screen":"all saved eligible states and profitable counterexamples, no counterfactual ROI claim"},
 "B":{"conditional":"only A has no applicable predictive+policy candidate","model":"original Kronos-small with compatible tokenizer; provenance June2024 cutoff must verify","lookback":80,"horizon":24,"max_context":512,"price_only_zero_volume_amount":True,"paths":16,"temperature":1,"top_k":0,"top_p":0.9,"generation_every_hours":6,"features":"terminal normalized returns mean/std/q20/q50/q80/freq+-0.25 perasset; frozen asof age","sample_axis":"save before upstream mean or16 independent sample_count1 calls","pilot_origins":16,"new_depth_search":False},
 "C":{"conditional":"only no A/B applicable candidate","model":"TS2Vec","output_dims":32,"hidden_dims":32,"depth":6,"batch_size":16,"lr":0.001,"max_train_length":256,"n_iters":600,"seed":7,"causal":True,"sliding_length":1,"sliding_padding":255,"prefix_invariance_required":True},
 "gates":{"predictive":"primary loss below both prior+linear on mean and>=2/3folds; upper95pairedCI<0 for both","rank_only_D":"UP andDOWN AUROC beat linear and0.5 with positive blocked bounds; ordinalonly","Q_rank_only":False,"policy":"taskcontract section8 full support/cost/lifecycle gates binding","shortlist_max":2,"native_max":4,"no_native_without_early_applicability":True},
 "resources":{"one_heavy_process":True,"threads":1,"process_tree_RSS_bytes":3221225472,"wall_minutes":{"stage0":30,"A":120,"B":90,"C":90,"policy":30},"include":"pilots,allfits,ES,refits,inference","RSS_units":"Darwin ru_maxrss bytes; LinuxKiB*1024; external time/ps authoritative","old_CNN480min_override_not_inherited":True},
 "forward":{"trading":False,"first_future_origin":"first UTC wholehour strictly after freeze","log_fields":["origin","model_id","fit_cutoff","max_fit_label_expiry","feature_end","forecast_age","prediction","abstain_reason"],"history_is_not_forward":True},
 "economics":{"seed":10000,"S0_TOTAL":6077107.23887483,"TOTAL_min":5470396.514987347,"native_phase_DD":66.3187802497,"money_projection_DD":66.2569148647,"DD_max_percent":50,"observer_unchanged":True,"S0_rerun":False,"deploy_merge_live":False}}
 write_json(r/"protocol.json",protocol)
 write_json(r/"feature-schema.json",{"dtype":"float32","X_shape":{"view":"60x20","width":124,"definition":"unchanged flatten old normalized OHLCV/SMA20 + sigma/reference_close_ratio/panel_age/asset"},"X_joint":{"width":len(feature_names()),"columns":feature_names(),"bar_lags":"oldest19 to newest0","price_normalization":"first5 / (current causal sigma * sqrt(TF_hours/24))","volume":"log1pV minus preceding20 completedTF bars excluding currentbar","sma_distance":"(C/SMA20-1)/sigma","rv":"sample std hourly logreturns,ddof1","TF_age_unit":"hours","same_joint_vector_both_assets":True,"invalid_flag":"valid.npy false; XNaN; common coverage; no imputation"}})
 write_json(r/"selection-ledger.json",{"task":TASK,"entries":[{"utc":now(),"stage":"freeze","fit":False,"seed":7,"reason":"user fixed research contract; no real fits authorized"}]})
 sources=list(Path(__file__).parent.glob("forecast_cycle_*.py"))+list(Path(__file__).parent.glob("forecast_independent_*.py"))
 inputs=[r/"task-contract.txt",r/"protocol.json",r/"feature-schema.json"]+sources
 repo=Path.cwd();inputs += [repo/"reports/btc-split-sol-cover-20261018"/f"data-warmup-{a}-1h.csv" for a in ASSETS]
 write_json(r/"source-input-hashes.json",{str(p.resolve().relative_to(repo)):{"sha256":sha(p),"bytes":p.stat().st_size} for p in inputs})
 print(json.dumps({"status":"FROZEN_AWAIT_FIT_GO","protocol_sha256":sha(r/"protocol.json"),"features":750}))
def verify_freeze(a):
 r=a.report;manifest=json.loads((r/"source-input-hashes.json").read_text())
 for path,rec in manifest.items():
  p=Path(path)
  if not p.exists():p=r/path if not Path(path).is_absolute() else p
  if sha(p)!=rec["sha256"]:raise ValueError("FROZEN_SOURCE_OR_INPUT_DRIFT "+str(p))
 return json.loads((r/"protocol.json").read_text())
def diagnose(a):
 verify_freeze(a);old=a.old_job;ds=Dataset(old/"prepared-v1",old/"reports/forecast-independent-20261021/protocol.json",allow_check=True)
 from sklearn.metrics import roc_auc_score
 output={}
 for family in ("control","stumpy","minirocket","rdst","cnn"):
  base=old/"final-results-v2"/family
  with np.load(base/"predictions.npz") as z:
   ids=z["ids"];groups={}
   for mode,qk,lk in (("raw","q","logits"),("calibrated","calibrated_q","calibrated_logits")):
    q=z[qk];logits=z[lk];p=softmax(logits);detail=scores(q,logits,ds.targets[ids],ds.direction[ids])
    for asset in (0,1):
     mask=ds.meta["asset"][ids]==asset;truth=ds.direction[ids][mask];pp=p[mask]
     detail[ASSETS[asset]]={"N":int(mask.sum()),"AUROC":[float(roc_auc_score(truth==k,pp[:,k])) if len(np.unique(truth==k))==2 else None for k in range(3)],"confidence_quantiles":np.quantile(pp.max(1),[0,.1,.5,.9,1]).tolist(),"confidence_bins":np.histogram(pp.max(1),bins=[0,.4,.5,.6,.7,.8,.9,1.0000001])[0].tolist(),"strict_coverage":(ds.targets[ids][mask,:,:,None]>q[mask]).mean(0).tolist(),"nonstrict_coverage":(ds.targets[ids][mask,:,:,None]>=q[mask]).mean(0).tolist()}
    expected=json.loads((base/"result.json").read_text())[mode]["all"]
    for k in ("lower_pinball","direction_logloss","direction_brier"):
     if abs(detail[k]-expected[k])>1e-10:raise ValueError("METRIC_REPRODUCTION_MISMATCH "+family+":"+mode+":"+k)
    groups[mode]=detail
   output[family]=groups
 write_json(a.report/"old-metrics-reproduced.json",output);ledger(a.report,{"stage":"diagnose","fit":False,"reason":"same savedIDs raw/cal loss,Brier,coverage,perassetAUROC/confidence","status":"PASS"})
 print(json.dumps({"status":"OLD_METRICS_REPRODUCED","families":len(output)}))
def prepare(a):
 verify_freeze(a);t=time.monotonic();j=JointFeatures(a.old_job/"prepared-v1",a.warmup)
 result=j.build(a.output,a.limit);result["wall_seconds"]=time.monotonic()-t
 write_json(a.output/"receipt.json",result);ledger(a.report,{"stage":"prepare","fit":False,**result});print(json.dumps(result))
def fitset_diagnose(a):
 verify_freeze(a)
 from .forecast_independent_run import _load_model,_predict,average
 from .forecast_independent_models import Budget
 ds=Dataset(a.old_job/"prepared-v1",a.old_job/"reports/forecast-independent-20261021/protocol.json")
 fit=ds.rows("2024-09-01","2026-03-01")[:256];val=ds.rows("2026-03-01","2026-04-01")[:256]
 result_path=a.report/("old-fit-validation-utc.json" if a.reuse_inference else "old-fit-validation.json")
 registry=json.loads((a.old_job/"all-method-seals.json").read_text());output=json.loads(result_path.read_text()) if result_path.exists() else {}
 if a.family: registry={a.family:registry[a.family]}
 for family,rec in registry.items():
  sp=Path(rec["path"]);seal=json.loads(sp.read_text())
  if sha(sp)!=rec["sha256"]:raise ValueError("OLD_SEAL_DRIFT")
  allids=np.r_[fit,val];oldids={};oldq=None;oldl=None
  if a.reuse_inference:
   with np.load(a.reuse_inference/f"{family}-fit-validation.npz") as z:oldids={int(row):i for i,row in enumerate(z["ids"])};oldq=z["q"].copy();oldl=z["logits"].copy()
  missing=np.array([int(row) for row in allids if int(row) not in oldids],np.int64)
  predictions=[];budget=Budget(10)
  for k,record in enumerate(seal["models"]):
   path=sp.parent/record["path"]
   if sha(path)!=record["sha256"]:raise ValueError("OLD_MODEL_DRIFT")
   model=_load_model(ds,path,a.output/family/str(k))
   prediction=_predict(model,missing,budget);predictions.append(prediction)
   del model
  newq,newl=average(predictions);newids={int(row):i for i,row in enumerate(missing)}
  q=np.stack([oldq[oldids[int(row)]] if int(row) in oldids else newq[newids[int(row)]] for row in allids])
  l=np.stack([oldl[oldids[int(row)]] if int(row) in oldids else newl[newids[int(row)]] for row in allids])
  output[family]={"sample_rule":"first256 mature chronological fitIDs + first256 mature MarchIDs; fixed before inference; no fit","fit":scores(q[:len(fit)],l[:len(fit)],ds.targets[fit],ds.direction[fit]),"validation":scores(q[len(fit):],l[len(fit):],ds.targets[val],ds.direction[val]),"learning_curves":"UNKNOWN_NOT_SAVED","cached_rows_reused":len(allids)-len(missing),"new_inference_rows":len(missing),"fit_sample_ids":fit.tolist(),"validation_sample_ids":val.tolist()}
  a.output.mkdir(parents=True,exist_ok=True);np.savez(a.output/f"{family}-fit-validation.npz",ids=np.r_[fit,val],q=q,logits=l)
  write_json(result_path,output)
 ledger(a.report,{"stage":"fitset-diagnose","fit":False,"status":"PASS","families":len(output)})
 print(json.dumps({"status":"OLD_FIT_VALIDATION_DIAGNOSED","families":len(output)}))

def profile_A(a):
 verify_freeze(a)
 from .forecast_cycle_train import profile_A as run
 run(a)
def stage_A(a):
 verify_freeze(a)
 from .forecast_cycle_train import stage_A as run
 run(a)
def controls(a):
 verify_freeze(a)
 from .forecast_cycle_controls import run
 run(a)
def controls_utc(a):
 a.negative_only=True
 controls(a)
def profile_baseline(a):
 verify_freeze(a)
 from .forecast_cycle_train import profile_baseline as run
 run(a)
def resource_estimate(a):
 from .forecast_cycle_train import resource_estimate as run
 run(a)
def mechanism_screen(a):
 from .forecast_cycle_mechanism import run
 run(a.inputs,a.report)
def profile_scaling(a):
 verify_freeze(a)
 from .forecast_cycle_train import profile_scaling as run
 run(a)
def profile_B(a):
 from .forecast_cycle_kronos import profile_B as run
 run(a)
def main():
 p=argparse.ArgumentParser();p.add_argument("stage",choices=["freeze","diagnose","prepare","fitset-diagnose","profile-A","stage-A","controls","controls-utc","profile-baseline","resource-estimate","mechanism-screen","profile-scaling","profile-B"]);p.add_argument("--report",type=Path,required=True);p.add_argument("--old-job",type=Path);p.add_argument("--warmup",type=Path);p.add_argument("--output",type=Path);p.add_argument("--limit",type=int);p.add_argument("--family",choices=["control","stumpy","minirocket","rdst","cnn"])
 p.add_argument("--weights",type=Path);p.add_argument("--reuse-inference",type=Path);p.add_argument("--reuse-controls",type=Path);p.add_argument("--negative-only",action="store_true");p.add_argument("--prepared",type=Path);p.add_argument("--fit-authorization",type=Path);p.add_argument("--resource-decision",type=Path);p.add_argument("--profile",type=Path);p.add_argument("--baseline-profile",type=Path);p.add_argument("--scaling-profile",type=Path);p.add_argument("--inputs",type=Path)
 a=p.parse_args();globals()[a.stage.replace("-","_")](a)
if __name__=="__main__":main()
