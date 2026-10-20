import csv,json,pathlib,statistics,hashlib
P=pathlib.Path("reports/carry-pair-113");rs=list(csv.DictReader(open(P/"stats-minute-windows.csv")));tp=list(csv.DictReader(open(P/"stats-minute-TP.csv")));summary=[];tps=[]
med=lambda a:statistics.median(a) if a else None
def q10(a):
 a=sorted(a);p=(len(a)-1)*.1;i=int(p);return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(p-i)
for per in ["calibration","later"]:
 for m in ["original_inventory","half_factor","factor_neutral","minimum_variance"]:
  for d in [1,3,7]:
   a=[r for r in rs if r["period"]==per and r["primary"]=="True" and r["model"]==m and int(r["days"])==d];n=len(a);initial=[float(r["initial_whole_mark"]) for r in a];terminal=[float(r["terminal_whole_mark"]) for r in a];delta=[b-a for a,b in zip(initial,terminal)]
   row=dict(period=per,coverage=m,days=d,n=n,censored=sum(r["censored"]=="True" for r in a),remaining_pair_initial_mark_median=med(initial),remaining_pair_terminal_mark_median=med(terminal),remaining_pair_terminal_mark_mean=statistics.mean(terminal),terminal_minus_initial_mark_median=med(delta),terminal_minus_initial_mark_mean=statistics.mean(delta),terminal_above_initial=sum(x>0 for x in delta),remaining_pair_MAE_median=med([float(r["whole_MAE"]) for r in a]),remaining_pair_MFE_median=med([float(r["whole_MFE"]) for r in a]),remaining_pair_BE_reach=sum(r["whole_zero_recovery_min"]!="" for r in a),remaining_pair_BE_plus10bp_reach=sum(r["whole_buffer001_recovery_min"]!="" for r in a),BTC_basis_reach=sum(r["BTC_original_basis_recovery_min"]!="" for r in a),remaining_pair_path_MAE_worst=min(float(r["whole_MAE"]) for r in a),remaining_pair_path_MAE_q10=q10([float(r["whole_MAE"]) for r in a]),remaining_pair_BE_latency_minutes_median=med([float(r["whole_zero_recovery_min"]) for r in a if r["whole_zero_recovery_min"]]),new_SOL_notional_per_NB_median=med([float(r["SOL_new_NS_per_NB"]) for r in a]));summary.append(row)
   if d==1:
    for leg in ["SOL","SOL_prior_comparison","BTC"]:
     for k in [1,2,3]:
      t=[r for r in tp if r["period"]==per and r["primary"]=="True" and r["model"]==m and int(r["days"])==d and r["leg"]==leg and int(r["TP"])==k];mark=[float(r["whole_UNREDUCED_mark_at_TP"]) for r in t];tps.append(dict(period=per,coverage=m,leg=leg,TP=k,total_contexts=n,hits=len(t),remaining_pair_mark_positive_at_TP=sum(x>0 for x in mark),remaining_pair_mark_at_TP_median=med(mark),trigger_then_BTC_basis_recovery_by1D=sum(r["BTC_basis_recovery_after_trigger_min"]!="" for r in t)))
for name,a in [("stats-summary.csv",summary),("stats-TP-summary.csv",tps)]:
 with open(P/name,"w") as z:w=csv.DictWriter(z,fieldnames=list(a[0]));w.writeheader();w.writerows(a)
res=json.load(open(P/"stats-minute-result.json"));res.update(remaining_inventory_scope="ALL whole_* labels mean both CURRENTREMAININGLEGS only. Not wholeoriginalepisode/account. NativeearlierrealizedTPcash/funding NOTavailableattributedhere=>UNKNOWN notzero; remainingpairBE isnotepisodeBE/equity/DD.",summary=summary,TP_summary=tps)
(P/"stats-summary.json").write_text(json.dumps(res,indent=2)+"\n")
print("SOL1DfixedcallevelsTPs half/full:")
for r in tps:
 if r["coverage"] in ["half_factor","factor_neutral"] and r["leg"]=="SOL":print(r)
print("7Ddelta:")
for r in summary:
 if r["days"]==7:print(r["period"],r["coverage"],r["terminal_minus_initial_mark_mean"],r["terminal_minus_initial_mark_median"],r["terminal_above_initial"])
