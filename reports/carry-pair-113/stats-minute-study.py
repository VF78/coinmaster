"""Bounded descriptive fixed-quantity price marks only. No fill/cash/portfolio simulation."""
import os,csv,json,hashlib,resource,time,pathlib
os.environ.update(OPENBLAS_NUM_THREADS="1",OMP_NUM_THREADS="1")
import numpy as np
import pyarrow.parquet as pq
P=pathlib.Path("reports/carry-pair-113");rr=list(csv.DictReader(open(P/"stats-opportunities.csv")));bars={};sources={};start=time.time()
for sym in ["BTC","SOL"]:
 p=f"runtime/var/data/normalized/bybit-{sym}USDT-execution-1m.parquet";h=hashlib.sha256()
 with open(p,"rb") as z:
  for chunk in iter(lambda:z.read(1048576),b""):h.update(chunk)
 sources[p]=h.hexdigest();aa=[]
 for b in pq.ParquetFile(p).iter_batches(batch_size=8192,columns=["open_time_ms","close"],use_threads=False):aa.append(np.column_stack([np.asarray(b.column(i).to_pylist(),dtype=float) for i in range(2)]))
 bars[sym]=np.concatenate(aa);del aa
assert np.array_equal(bars["BTC"][:,0],bars["SOL"][:,0]);ts=bars["BTC"][:,0].astype("int64")+60000;b=bars["BTC"][:,1];s=bars["SOL"][:,1]
assert len(ts)==1051200 and ts[0]==1725148860000 and ts[-1]==1788220800000
# Calibration-only SOL1D inverse80/50/20 reach levels from fixed18admissible contexts.
train=[]
for r in rr:
 ix=int(np.searchsorted(ts,int(r["ms"])));nb=float(r["BTC_qty"])*b[ix];ns=float(r["SOL_qty"])*s[ix]
 if r["period"]=="calibration" and r["CHOP_raw_flips2_near"]=="True" and ns<=nb/float(r["beta_at_flip"])+1e-7 and int(r["ms"])+86400000<1756684800000:
  z=int(np.searchsorted(ts,int(r["ms"])+86400000,side="right"));train.append(max(0,max(-int(r["BTC_side"])*(s[ix+1:z]/s[ix]-1))))
assert len(train)==18
solLevels=np.quantile(train,[.2,.5,.8]).tolist()
out=[];tpout=[]
for r in rr:
 ms=int(r["ms"]);ix=int(np.searchsorted(ts,ms));assert ts[ix]==ms
 sd=int(r["BTC_side"]);bq=float(r["BTC_qty"]);basisB=float(r["BTC_basis"]);sq=float(r["SOL_qty"]);basisS=float(r["SOL_basis"]);beta=float(r["beta_at_flip"]);rho2=float(r["rho_squared_at_flip"]);nb=bq*b[ix];existingNS=sq*s[ix];abovefull=existingNS>nb/beta+1e-7;primary=r["CHOP_raw_flips2_near"]=="True" and not abovefull;knownFee=bq*float(r["BTC_entry_fee_per_q"])+sq*float(r["SOL_entry_fee_per_q"])
 # Nativeexecution quote differs from completedclose observation; preserve and export gap, never shiftbar to fit.
 for model,factor in [("original_inventory",existingNS/nb),("half_factor",.5/beta),("factor_neutral",1/beta),("minimum_variance",rho2/beta)]:
  # Exclude originalSOL above model ceiling, never trim it to manufacture desiredratio.
  eligible=not abovefull or model=="original_inventory"
  if not eligible:continue
  addq=max(0,(nb*factor-existingNS)/s[ix]);totalq=sq+addq;entryFee=knownFee+.00055*addq*s[ix]
  for days in [1,3,7]:
   end=min(ms+days*86400000,1788220800000);z=int(np.searchsorted(ts,end,side="right"));idx=np.arange(ix+1,z)
   if not len(idx):continue
   gross=sd*bq*(b[idx]-basisB)-sd*(sq*(s[idx]-basisS)+addq*(s[idx]-s[ix]));exitFee=.00055*(bq*b[idx]+totalq*s[idx]);mark=(gross-entryFee-exitFee)/nb;raw=sd*(b[idx]/basisB-1)
   rec=np.flatnonzero(raw>=0);be=np.flatnonzero(mark>=0);buffer=np.flatnonzero(mark>=.001)
   row=dict(event=r["event"],period=r["period"],utc=r["utc"],primary=primary,model=model,days=days,observed_minutes=len(idx),censored=end<ms+days*86400000,beta=beta,SOL_original_NS_per_NB=existingNS/nb,SOL_target_NS_per_NB=factor,SOL_actual_NS_per_NB=max(factor,existingNS/nb),SOL_new_NS_per_NB=addq*s[ix]/nb,BTC_original_basis=basisB,BTC_flip_close=b[ix],SOL_original_basis=basisS,SOL_flip_close=s[ix],initial_whole_mark=(sd*bq*(b[ix]-basisB)-sd*sq*(s[ix]-basisS)-entryFee-.00055*(nb+totalq*s[ix]))/nb,terminal_whole_mark=mark[-1],whole_MAE=min(mark),whole_MFE=max(mark),whole_zero_recovery_min=int(be[0]+1) if len(be) else "",whole_buffer001_recovery_min=int(buffer[0]+1) if len(buffer) else "",BTC_original_basis_recovery_min=int(rec[0]+1) if len(rec) else "",original_next_BTC_displacement_ms=r["next_BTC_entry_ms"])
   nativeB=float(r["BTC_regime_close_px"]);nativeS=float(r["SOL_regime_close_px"]) if r["SOL_regime_close_px"] else None
   row.update(observation_ms=int(ts[ix]),BTC_native_regime_close_px=nativeB,BTC_observed_close=float(b[ix]),BTC_native_observation_gap_absolute=abs(nativeB-b[ix]),BTC_native_observation_gap_bps=(b[ix]/nativeB-1)*10000,BTC_gap_outlier_over10bps=abs(b[ix]/nativeB-1)>.001,SOL_native_regime_close_px=nativeS if nativeS else "",SOL_observed_close=float(s[ix]),SOL_native_observation_gap_absolute=abs(nativeS-s[ix]) if nativeS else "",SOL_native_observation_gap_bps=(s[ix]/nativeS-1)*10000 if nativeS else "",SOL_gap_outlier_over10bps=abs(s[ix]/nativeS-1)>.001 if nativeS else "")
   out.append(row)
   # Selected TP snapshots do not change qty and are never strategyprofit labels.
   for leg,prices,basis,sign,levels in [("BTC",b,basisB,sd,[0.005317322747766129,.01208176843868225,.02104124963852716]),("SOL",s,s[ix],-sd,solLevels),("SOL_prior_comparison",s,s[ix],-sd,[.010408780588485867,.024237629459148535,.04224760887589967])]:
    for k,level in enumerate(levels,1):
     hits=np.flatnonzero(sign*(prices[idx]/basis-1)>=level)
     if len(hits):n=int(hits[0]);tpout.append(dict(event=r["event"],period=r["period"],primary=primary,model=model,days=days,leg=leg,TP=k,threshold=level,basis="actual_original_BTC_basis" if leg=="BTC" else "SOL_flip_close",first_min=n+1,BTC_basis_recovery_after_trigger_min=(int(np.flatnonzero(raw[n:]>=0)[0]+n+1) if len(np.flatnonzero(raw[n:]>=0)) else ""),whole_UNREDUCED_mark_at_TP=mark[n],terminal_whole_mark=mark[-1]))
for name,rows in [("stats-minute-windows.csv",out),("stats-minute-TP.csv",tpout)]:
 with open(P/name,"w") as z:w=csv.DictWriter(z,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
res={"status":"DESCRIPTIVE_FIXED_Q_PRICE_MARKS_NO_ECONOMIC_ENGINE","sources":sources,"peak_RSS_KiB":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,"elapsed_sec":time.time()-start,"calibration_SOL1D_TP_train_n":len(train),"calibration_SOL1D_TP_levels":solLevels,"rows":len(out),"TP_snapshot_rows":len(tpout),"timestamp_semantics":"native_baseline.py:856 close_available=(open_time_ms+60000)*1e6; minute_risk.py:115 same. Firstcompletedclose>=nativeREGIMEtimestamp via searchsortedleft, nooffsetfit. Dailycontextcompletedatsameobservation, nofuturebar. Nativeexecutionspreservedseparately; hypotheticalnewSOLbasisatobservedcloseisnotactualfill.","scope":"Native48residual snapshots; primaryrawflips2near frozenbeforeminute. AboveexistingSOLceilingexcluded. Noquantityreductions,sequencedtrades,reentry,cash,compounding,margin,TOTAL,ROI,DD. Funding/slippage/impact/actualfilluncertaintyunknown; grossandfeepricearithmeticonly."}
(P/"stats-minute-result.json").write_text(json.dumps(res,indent=2)+"\n");print(json.dumps(res,indent=2))
