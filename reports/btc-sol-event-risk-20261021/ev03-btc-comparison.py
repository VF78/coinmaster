"""One frozen BTC probability comparison. No economic engine or U outcomes."""
import argparse,collections,csv,datetime,hashlib,importlib.metadata,json,math,resource,time,warnings
from pathlib import Path
import numpy as np
R=Path(__file__).resolve().parent;OUT=R/"ev03-output";ROOT=R.parent.parent
RECIPE="eb21d1eea69b51847c81efb9a6736a24e80958c125190ad21af5fee0b7cb43e5"
SPLIT=1744070400000000000;CUT=1775606400000000000;HOUR=3600*10**9
F=["native_UPnL_over_W","native_drawdown","log_parent_days","parent_side","prior_TP_fraction","SOL_present"]
def digest(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()
def weights(rows,normalize=False):
 c=collections.Counter(r["block_id"] for r in rows);w=np.array([1/c[r["block_id"]] for r in rows],dtype=float)
 return w/w.mean() if normalize else w
def features(rows):
 x=np.array([[float(r["UPnL_to_equity"]),float(r["causal_native_drawdown"]),math.log1p(float(r["parent_age_seconds"])/86400),float(r["parent_side"]),float(r["prior_confirmed_BTC_TP_levels"])/3,float(r["SOL_present"])] for r in rows])
 assert x.shape==(len(rows),6) and np.isfinite(x).all()
 return x
def laplace(y,w):return float((np.dot(y,w)+1)/(w.sum()+2))
def flags(x):return (x[:,1]>=.1)&(x[:,0]<=0)
def bin_predictions(y,w,trainflag,queryflag):
 prior=laplace(y,w);ps={}
 for b in [False,True]:
  ix=trainflag==b;ps[b]=laplace(y[ix],w[ix]) if ix.any() else prior
 return np.array([ps[bool(b)] for b in queryflag]),ps

def ll(y,p):
 p=np.clip(p,1e-6,1-1e-6)
 return -(y*np.log(p)+(1-y)*np.log1p(-p))
def block_scores(rows,loss):
 by=collections.defaultdict(list)
 for r,v in zip(rows,loss):by[r["block_id"]].append(float(v))
 return {k:float(np.mean(v)) for k,v in sorted(by.items())}
def bootdiff(candidate,control):
 assert candidate.keys()==control.keys();d=np.array([candidate[k]-control[k] for k in candidate])
 rng=np.random.default_rng(7);means=d[rng.integers(0,len(d),size=(10000,len(d)))].mean(axis=1)
 return dict(mean_difference=float(d.mean()),ci95=[float(v) for v in np.percentile(means,[2.5,97.5])],component_count=len(d),resamples=10000,seed=7)
def quarter(t):
 edges=[SPLIT,1751932800000000000,1759881600000000000,1767830400000000000,CUT]
 # 2025-04-08,07-08,10-08,2026-01-08,04-08 UTC.
 assert edges[0]<=t<edges[-1]
 return next(i for i in range(4) if edges[i]<=t<edges[i+1])
def window_index(available,t):
 j=int(np.searchsorted(available,t,side="left"))-1
 return j if j>=19 else None

def selftest():
 from sklearn.preprocessing import StandardScaler
 from sklearn.linear_model import LogisticRegression
 import stumpy
 rows=[dict(block_id="a"),dict(block_id="a"),dict(block_id="b")]
 assert np.allclose(weights(rows),[.5,.5,1])
 assert abs(laplace(np.array([1,0,0]),weights(rows))-.375)<1e-12
 av=np.arange(30)*HOUR
 assert window_index(av,20*HOUR)==19
 assert window_index(av,19*HOUR) is None
 assert window_index(av,20*HOUR+1)==20
 a=block_scores(rows,np.array([1.,3.,6.]));assert a=={"a":2.,"b":6.}
 assert bootdiff(a,{"a":3.,"b":7.})["ci95"]==[-1.,-1.]
 assert quarter(SPLIT)==0 and quarter(CUT-1)==3
 x=np.array([[-.01,.10,1,1,0,0],[.01,.2,1,1,0,0],[-.02,.09,1,-1,1,0]])
 assert flags(x).tolist()==[True,False,False]
 # Genuine STUMPY API on synthetic data only; not a market model fit.
 q=np.sin(np.arange(20)*.3);z=stumpy.mass(q,q,normalize=True)
 assert z.shape==(1,) and abs(float(z[0]))<1e-5
 result=dict(status="PASS_SYNTHETIC_ONLY_NO_REAL_FIT",checks=["component_weights","Laplace_prior","strict_prior_panel_clock","20contiguous_window_boundary","block_equal_scores","paired_bootstrap","fixed_quarter_boundaries","fixed_rule","genuine_STUMPY_mass_API"],versions={p:importlib.metadata.version(p) for p in ["numpy","scipy","scikit-learn","stumpy","numba"]},peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
 (OUT/"synthetic-checks.json").write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result))

def run():
 started=time.monotonic();assert not (OUT/"real-fit-started.json").exists(),"NO_REAL_FIT_RETRIES"
 manifest=json.loads((R/"ev03-input-source-manifest.json").read_text());assert manifest["status"]=="FROZEN_BEFORE_REAL_FIT"
 for p,h in manifest["sha256"].items():assert digest(ROOT/p)==h,p
 assert digest(R/"ev03-btc-recipes-proposed.md")==RECIPE
 freeze=json.loads((R/"ev03-freeze.json").read_text());assert freeze["recipe_sha256"]==RECIPE
 rows=[r for r in json.loads((R/"ev02-events.json").read_text()) if r["hypothesis"]=="BTC" and r["label"] is not None]
 train=[r for r in rows if r["split"]=="TRAIN"];check=[r for r in rows if r["split"]=="CHECK"]
 assert (len(train),len(check))==(50,80)
 assert (len(set(r["block_id"] for r in train)),len(set(r["block_id"] for r in check)))==(15,21)
 assert all(r["horizon_end_ns"]<SPLIT for r in train)
 assert all(r["source_state_ns"]<r["receipt_ns"]<r["decision_ns"]<CUT for r in rows)
 xt=features(train);xc=features(check);yt=np.array([r["label"] for r in train]);yc=np.array([r["label"] for r in check]);w=weights(train)
 prior=laplace(yt,w);pred={"prior":np.full(len(check),prior)}
 pred["rule"],bins=bin_predictions(yt,w,flags(xt),flags(xc))
 from sklearn.preprocessing import StandardScaler
 from sklearn.linear_model import LogisticRegression
 from sklearn.exceptions import ConvergenceWarning
 (OUT/"real-fit-started.json").write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),recipe_sha256=RECIPE,train_events=50,check_events=80,model_fits_planned=1,automatic_retries=False),indent=2)+"\n")
 scaler=StandardScaler();wn=weights(train,normalize=True);zt=scaler.fit_transform(xt,sample_weight=wn);zc=scaler.transform(xc)
 model=LogisticRegression(C=.1,solver="lbfgs",fit_intercept=True,max_iter=500,tol=1e-8,class_weight=None,random_state=7)
 with warnings.catch_warnings():
  warnings.simplefilter("error",ConvergenceWarning);model.fit(zt,yt,sample_weight=wn)
 assert model.n_iter_.max()<500,"CONVERGENCE_STOP_NO_RETRY"
 pred["numeric"]=model.predict_proba(zc)[:,list(model.classes_).index(1)]
 (OUT/"numeric-model.json").write_text(json.dumps(dict(features=F,scaler_mean=scaler.mean_.tolist(),scaler_scale=scaler.scale_.tolist(),coefficients=model.coef_.tolist(),intercept=model.intercept_.tolist(),classes=model.classes_.tolist(),iterations=model.n_iter_.tolist(),C=.1,solver="lbfgs",max_iter=500,tol=1e-8),indent=2)+"\n")
 import stumpy
 panel=ROOT/"runtime/var/research-datasets/fast-rnd-20261020-v1/panels.npz"
 with np.load(panel) as p:
  available=p["p0_available_ns"]
  # Timestamp mask applied before loading/slicing any panel payload beyond cutoff.
  stop=int(np.searchsorted(available,CUT,side="left"));available=available[:stop]
  # Archive p0_values is numeric historical features only; no outcome fields.
  closes=p["p0_values"][:stop,3].copy()
 def win(r):
  j=window_index(available,r["decision_ns"])
  if j is None:return None
  av=available[j-19:j+1];v=closes[j-19:j+1]
  assert av[-1]<r["decision_ns"] and np.all(np.diff(av)==HOUR)
  return v if np.isfinite(v).all() and np.std(v)>0 else None
 tw=[win(r) for r in train];cw=[win(r) for r in check];analogs=[];analogue_p=[];fallback=0
 for r,q in zip(check,cw):
  candidates=[]
  if q is not None:
   for old,h in zip(train,tw):
    if h is None or old["horizon_end_ns"]>=r["decision_ns"]:continue
    if old["parent_side"]!=r["parent_side"]:continue
    if (old["prior_confirmed_BTC_TP_levels"]==0)!=(r["prior_confirmed_BTC_TP_levels"]==0):continue
    distance=float(stumpy.mass(q,h,normalize=True)[0])
    if np.isfinite(distance):candidates.append((distance,old["decision_ns"],old["event_id"],old))
  kept=[];used=set()
  for distance,t,eid,old in sorted(candidates,key=lambda a:a[:3]):
   if old["block_id"] in used:continue
   used.add(old["block_id"]);kept.append(dict(event_id=eid,block_id=old["block_id"],distance=distance,label=old["label"],horizon_end_ns=old["horizon_end_ns"]))
   if len(kept)==5:break
  fb=len(kept)<3
  p=prior if fb else (sum(k["label"] for k in kept)+1)/(len(kept)+2)
  fallback+=fb;analogue_p.append(p);analogs.append(dict(query_event_id=r["event_id"],fallback=fb,neighbors=kept,probability=p))
 pred["stumpy"]=np.array(analogue_p)
 (OUT/"stumpy-matches.json").write_text(json.dumps(analogs,indent=2)+"\n")
 allscores={};losses={};briers={}
 for name,p in pred.items():
  assert p.shape==(80,) and np.isfinite(p).all() and np.all((p>=0)&(p<=1))
  losses[name]=block_scores(check,ll(yc,p));briers[name]=block_scores(check,(p-yc)**2)
  allscores[name]=dict(log_loss=float(np.mean(list(losses[name].values()))),Brier=float(np.mean(list(briers[name].values()))))
 first={}
 for r in check:first[r["block_id"]]=min(r["decision_ns"],first.get(r["block_id"],r["decision_ns"]))
 quarter_blocks={str(i):[b for b,t in first.items() if quarter(t)==i] for i in range(4)}
 comparisons={};qualification={}
 for method in ["rule","numeric","stumpy"]:
  controls=["prior"] if method=="rule" else ["prior","rule"]
  comparisons[method]={};passed=True
  for control in controls:
   bd=bootdiff(losses[method],losses[control]);improvement=1-allscores[method]["log_loss"]/allscores[control]["log_loss"]
   quarters={}
   for q,bs in quarter_blocks.items():
    quarters[q]=None if not bs else float(np.mean([losses[method][b]-losses[control][b] for b in bs]))
   winning=sum(v is not None and v<0 for v in quarters.values())
   ok=improvement>=.05 and bd["ci95"][1]<0 and allscores[method]["Brier"]<=allscores[control]["Brier"] and winning>=3 and all(quarter_blocks.values())
   comparisons[method][control]=dict(relative_LL_improvement=improvement,paired_component_bootstrap=bd,quarter_differences=quarters,improving_quarters=winning,gate_pass=bool(ok));passed=passed and ok
  qualification[method]=bool(passed)
 qualified=[n for n,ok in qualification.items() if ok]
 complexity={"rule":0,"numeric":1,"stumpy":2};selected=None
 if qualified:
  best=min(allscores[n]["log_loss"] for n in qualified);selected=min([n for n in qualified if allscores[n]["log_loss"]<=best+1e-6],key=lambda n:complexity[n])
 with (OUT/"check-predictions.csv").open("w") as f:
  writer=csv.DictWriter(f,fieldnames=["event_id","decision_ns","block_id","label",*pred]);writer.writeheader()
  for i,r in enumerate(check):writer.writerow({**{k:r[k] for k in ["event_id","decision_ns","block_id","label"]},**{k:float(p[i]) for k,p in pred.items()}})
 result=dict(status="EV03_FIXED_COMPARISON_COMPLETE",recipe_sha256=RECIPE,manifest_sha256=digest(R/"ev03-input-source-manifest.json"),metrics=allscores,comparisons=comparisons,qualifying_methods=qualified,selected_method=selected,decision="INFORMATION_GATE_PASS_POLICY_NOT_YET_ADMITTED" if selected else "NO_ADDED_INFORMATION_STOP_NO_ECONOMIC_RUN",stumpy=dict(fallback_queries=fallback,queries=80,invalid_train_windows=sum(v is None for v in tw),invalid_check_windows=sum(v is None for v in cw)),constant_probability=prior,rule_bin_probabilities={str(k):v for k,v in bins.items()},check_quarter_block_counts={q:len(bs) for q,bs in quarter_blocks.items()},weights="equal BTC dependence-component weight; no IID event bootstrap",resources=dict(wall_seconds=time.monotonic()-started,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),new_fits=1,U_outcomes_inspected=0,economic_runs=0,limitations=["CHECK development, not untouched holdout", "S0 risk forecast is not actionvalue", "BTC action reachability UNKNOWN until sourcegate", "no TRAIN weights backwards and no S0 timestamp forecast replay"])
 assert result["resources"]["peak_RSS_bytes"]<400*1024**2
 result["outputs"]={p.name:digest(p) for p in OUT.iterdir() if p.is_file() and p.name not in ["result.json"]}
 (OUT/"result.json").write_text(json.dumps(result,indent=2)+"\n");print(json.dumps(result,indent=2))
if __name__=="__main__":
 ap=argparse.ArgumentParser();ap.add_argument("--selftest",action="store_true");args=ap.parse_args();selftest() if args.selftest else run()
