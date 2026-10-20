import csv,json,math,statistics,hashlib
from pathlib import Path
from decimal import Decimal as D
P=Path("reports/winner-6077107-stats")
d=json.load(open(P/"risk-statistics.json"))
days=list(csv.DictReader(open(P/"risk-daily.csv")));rs=[float(r["return_percent"])/100 for r in days]
def q(v,p):
 a=sorted(v);i=(len(a)-1)*p;lo=int(i);hi=min(lo+1,len(a)-1);return a[lo]+(a[hi]-a[lo])*(i-lo)
avg=statistics.mean(rs);vol=statistics.stdev(rs);down=math.sqrt(sum(min(x,0)**2 for x in rs)/len(rs))
settled=float(d["settlement_bridge"]["settled_total"]);growth=settled/10000;years=len(rs)/365;cagr=growth**(1/years)-1
dailyVaR=q(rs,.05);tail=[x for x in rs if x<=dailyVaR]
st={"basis":"UTC paired native daily equity returns, 730observations, 365days/year, zero risk-free andzero MAR. Historical distribution only, no forecast/normality claim. CAGR uses actualsettledTOTAL, daily return distribution excludes terminalsettlement.","count":len(rs),"mean_daily_return_percent":avg*100,"median_daily_return_percent":statistics.median(rs)*100,"std_daily_return_percent":vol*100,"annualized_volatility_percent":vol*math.sqrt(365)*100,"annualized_sharpe_zero_rf":avg/vol*math.sqrt(365),"annualized_sortino_zero_MAR":avg/down*math.sqrt(365),"settled_CAGR_percent":cagr*100,"settled_Calmar_all_native_DD":cagr/(float(d["all_native_max_DD_percent"])/100),"daily_quantile_percent":{str(p):q(rs,p)*100 for p in [0,.01,.05,.25,.5,.75,.95,.99,1]},"historical_daily_5pct_quantile_percent":dailyVaR*100,"historical_daily_lower_tail_mean_percent":statistics.mean(tail)*100,"lower_tail_observations":len(tail),"positive_days":sum(x>0 for x in rs),"negative_days":sum(x<0 for x in rs),"flat_days":sum(x==0 for x in rs),"best10_days":sorted(days,key=lambda x:float(x["return_percent"]),reverse=True)[:10],"worst10_days":sorted(days,key=lambda x:float(x["return_percent"]))[:10],"day_of_week":[],"year":[]}
for wd in range(7):
 import datetime
 rows=[r for r in days if datetime.date.fromisoformat(r["period"]).weekday()==wd];vals=[float(r["return_percent"]) for r in rows];st["day_of_week"].append({"weekday":wd,"count":len(vals),"mean_return_percent":statistics.mean(vals),"positive_days":sum(x>0 for x in vals),"negative_days":sum(x<0 for x in vals),"flat_days":sum(x==0 for x in vals)})
for yr in ["2024","2025","2026"]:
 rows=[r for r in days if r["period"].startswith(yr)];s=D(rows[0]["start_equity"]);e=D(rows[-1]["end_equity"]);st["year"].append({"year":yr,"first_day":rows[0]["period"],"last_day":rows[-1]["period"],"days":len(rows),"start_equity":str(s),"end_equity":str(e),"return_percent":str((e/s-1)*100)})
# Longest sign runs in calendar daily marks, ties break streaks.
for name,fn in [("positive",lambda x:x>0),("negative",lambda x:x<0),("flat",lambda x:x==0)]:
 best=0;run=0;start=None;record=None
 for r,x in zip(days,rs):
  if fn(x):
   if run==0:start=r["period"]
   run+=1
   if run>best:best=run;record={"days":run,"start":start,"end":r["period"]}
  else:run=0
 st["longest_"+name+"_day_run"]=record
(P/"risk-return-distribution.json").write_text(json.dumps(st,indent=2)+"\n")
with open(P/"risk-native-dd-excursion-points.csv","w") as f:
 w=csv.writer(f);w.writerow(["id","peak_utc","peak_equity","trough_utc","trough_equity","native_DD_percent","DD_amount","recovery_utc","recovered"])
 for r in csv.DictReader(open(P/"risk-drawdowns.csv")):
  peak=json.loads(r["peak"]);trough=json.loads(r["trough"]);rec=json.loads(r["recovery"]) if r["recovery"] not in ["", "None", "null"] else None
  w.writerow([r["id"],peak["utc"],peak["equity"],trough["utc"],trough["equity"],r["drawdown_percent"],r["drawdown_amount"],rec["utc"] if rec else "",r["recovered"]])
with open(P/"risk-statistics.md","a") as f:
 f.write("\n## Daily-return distribution and annualized diagnostics\n\nThese use 730 UTC paired native daily returns, 365 days/year, zero risk-free rate and zero minimum acceptable return. Sharpe uses arithmetic daily mean/sample standard deviation; Sortino uses square root of mean squared negative daily returns, including zero contribution from nonnegative days. Historical quantiles use linear interpolation; lower-tail mean averages actual observations at/below the 5% quantile. These are descriptive, not a normality assumption or forecast. Settled CAGR/Calmar use actual terminal TOTAL, while daily return statistics exclude terminal settlement.\n\n| Metric | Value |\n|---|---|\n")
 for k,v in st.items():
  if not isinstance(v,(list,dict)):f.write("| "+k+" | "+str(v)+" |\n")
 f.write("\nPartial calendar years, with native interval endpoints:\n\n| Year | First day | Last day | Days | Start equity | End equity | Return % |\n|---|---|---|---|---|---|---|\n")
 for r in st["year"]:f.write("| "+" | ".join(str(r[k]) for k in ["year","first_day","last_day","days","start_equity","end_equity","return_percent"])+" |\n")
 f.write("\nExact native excursion-minimum markers are provided in risk-native-dd-excursion-points.csv. These are exact trough points, not a daily all-phase drawdown envelope. Full daily sign runs, quantiles, weekday descriptors and best/worst days are in risk-return-distribution.json; apparent weekday differences have no significance test and are not an optimization recommendation.\n")
manifest={p.name:{"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()} for p in P.glob("risk-*") if p.is_file() and p.name!="risk-manifest.json"}
(P/"risk-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
print(json.dumps({k:v for k,v in st.items() if not isinstance(v,(list,dict))}))

