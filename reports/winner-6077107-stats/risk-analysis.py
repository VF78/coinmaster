import csv,gzip,json,datetime,collections,heapq,hashlib,math
from decimal import Decimal as D
from pathlib import Path
P=Path("reports/winner-6077107-stats");P.mkdir(exist_ok=True)
ref=json.load(open("reports/carry-pair-run-113/control-reference.json"));raw=json.load(open(ref["raw_path"]))
trace=Path(raw["minute_risk_observations"]["trace_path"]); seed=D(10000); end=int(raw["minute_risk_observations"]["end_exclusive_ns"])
NSDAY=86400000000000
def utc(ns):return datetime.datetime.fromtimestamp(int(ns)/1e9,datetime.timezone.utc).isoformat()
def pack(ns,e,phase,cash=None,positions=None):
 d={"ns":str(ns),"utc":utc(ns),"equity":str(e),"phase":phase}
 if cash is not None:d["cash"]=str(cash);d["native_total_unrealized"]=str(e-cash)
 if positions is not None:d["positions"]=positions
 return d
def decdefault(o):
 if isinstance(o,D):return str(o)
 raise TypeError(type(o).__name__)
def writecsv(name,rows):
 rows=list(rows)
 with open(P/name,"w") as f:
  if not rows:return
  w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,default=decdefault) if isinstance(v,(dict,list)) else str(v) if isinstance(v,D) else v for k,v in r.items()})
def addperiod(state,key,ns,e,cash,prev):
 if key not in state:state[key]={"period":key,"start_equity":prev,"end_equity":e,"min_equity":e,"max_equity":e,"min_utc":utc(ns),"max_utc":utc(ns),"peak":prev,"dd":D(0),"samples":0,"end_cash":cash}
 s=state[key];s["end_equity"]=e;s["end_cash"]=cash;s["samples"]+=1
 if e<s["min_equity"]:s["min_equity"]=e;s["min_utc"]=utc(ns)
 if e>s["max_equity"]:s["max_equity"]=e;s["max_utc"]=utc(ns)
 s["peak"]=max(s["peak"],e);s["dd"]=max(s["dd"],1-e/s["peak"])
def finishperiod(state):
 rows=[]
 for k,s in state.items():
  rows.append({"period":k,"start_equity":s["start_equity"],"end_equity":s["end_equity"],"change":s["end_equity"]-s["start_equity"],"return_percent":(s["end_equity"]/s["start_equity"]-1)*100,"min_equity":s["min_equity"],"min_utc":s["min_utc"],"max_equity":s["max_equity"],"max_utc":s["max_utc"],"within_period_DD_percent":s["dd"]*100,"end_cash":s["end_cash"],"end_native_unrealized":s["end_equity"]-s["end_cash"],"samples":s["samples"]})
 return rows
start=1725148800000000000
peak=seed; peakrow=pack(start,seed,"INITIAL_SEED"); excursion=None; episodes=[]
minrow=None; maxrow=None; maxdd=D(0); count=0; excluded=[]; lastkey=None; lastns=None
levels=[10,20,30,40,50,60]
th={k:{"all_native_entries":0,"native_inside":False,"sampled_entries":0,"minutes":0,"max_contiguous_minutes":0,"current_minutes":0,"longest_start":None,"longest_end":None,"start":None} for k in levels}
day={};month={};hour={};week={};prevE=seed;minute_n=0;underwater=0;maxuw=0;uwrun=0;samplepeak=seed;uwstart=None;maxuwstart=None;maxuwend=None
exposure=collections.Counter(); extremes={}; horizons=[1,60,1440,10080,43200];history=collections.deque([(0,start,seed)]);worst={h:{"return":None,"change":None} for h in horizons}
# Ring buffer 43,201 observations, not a full minute list.
ring=[None]*43201;ring[0]=(start,seed)
def extremekey(key,value,ss):
 if key not in extremes or value>extremes[key]["value"]:extremes[key]={"value":value,"snapshot":ss}
phasecounts=collections.Counter(); dailyplot=[]
for idx,r in enumerate(csv.DictReader(gzip.open(trace,"rt"))):
 ns=int(r["close_available_ns"]);phase=r["phase"];bar=int(r["bar_open_ms"]);phasecounts[phase]+=1
 # Time is monotone; three ordered callbacks may share the same close time.
 if lastns is not None and ns<lastns:raise ValueError("nonmonotone timestamps")
 lastns=ns
 if "post_boundary" in phase:excluded.append({k:r[k] for k in ["close_available_ns","phase","cash","paired_close_equity"]});continue
 e=D(r["paired_close_equity"]);cash=D(r["cash"]);count+=1
 # All-native phase excursion. Equal highwater observations reset the peak timestamp to the latest attained HWM.
 if e>=peak:
  if excursion:
   excursion["recovery"]=pack(ns,e,phase);excursion["recovered"]=True;episodes.append(excursion);excursion=None
  peak=e;peakrow=pack(ns,e,phase)
 else:
  dd=1-e/peak
  if excursion is None:excursion={"peak":peakrow,"first_underwater":pack(ns,e,phase),"trough":pack(ns,e,phase),"drawdown_amount":peak-e,"drawdown_percent":dd*100,"recovered":False,"recovery":None}
  if dd*100>excursion["drawdown_percent"]:excursion["trough"]=pack(ns,e,phase);excursion["drawdown_percent"]=dd*100;excursion["drawdown_amount"]=peak-e
 maxdd=max(maxdd,1-e/peak)
 if minrow is None or e<D(minrow["equity"]):minrow=pack(ns,e,phase,cash,json.loads(r["native_positions_and_mark_ohlc_json"]))
 if maxrow is None or e>D(maxrow["equity"]):maxrow=pack(ns,e,phase,cash,json.loads(r["native_positions_and_mark_ohlc_json"]))
 for k in levels:
  inside=(1-e/peak)*100>=k
  if inside and not th[k]["native_inside"]:th[k]["all_native_entries"]+=1
  th[k]["native_inside"]=inside
 # Native paired post-SOL sample per source minute. End-exclusive minute has only a prequote left-limit sample.
 if phase!="post_quote_paired_close" and not (ns==end and phase=="pre_quote_paired_close"):continue
 if lastkey is not None and bar!=lastkey+60000:raise ValueError("noncontiguous source minutes")
 lastkey=bar;minute_n+=1
 dt=datetime.datetime.fromtimestamp(bar/1000,datetime.timezone.utc)
 datestr=dt.strftime("%Y-%m-%d");mon=datestr[:7];hr=dt.strftime("%Y-%m-%dT%H");wk=str((dt-datetime.timedelta(days=dt.weekday())).date())
 for st,key in [(day,datestr),(month,mon),(hour,hr),(week,wk)]:addperiod(st,key,ns,e,cash,prevE)
 samplepeak=max(samplepeak,e);sd=(1-e/samplepeak)*100
 if e<samplepeak:
  underwater+=1;uwrun+=1
  if uwrun==1:uwstart=ns
  if uwrun>maxuw:maxuw=uwrun;maxuwstart=uwstart;maxuwend=ns
 else:uwrun=0;uwstart=None
 for k in levels:
  s=th[k]
  if sd>=k:
   if s["current_minutes"]==0:s["sampled_entries"]+=1;s["start"]=ns
   s["minutes"]+=1;s["current_minutes"]+=1
   if s["current_minutes"]>s["max_contiguous_minutes"]:s["max_contiguous_minutes"]=s["current_minutes"];s["longest_start"]=utc(s["start"]);s["longest_end"]=utc(ns)
  else:s["current_minutes"]=0;s["start"]=None
 ss=None;ps=json.loads(r["native_positions_and_mark_ohlc_json"]);assets={}
 for p in ps:
  asset=p["instrument_id"][:3];sign=1 if p["side"]=="2" else -1;qty=D(p["quantity"]);mark=D(p["mark_ohlc"]["close"]);notional=qty*mark
  assets[asset]=(sign,notional);exposure[asset+("_long" if sign==1 else "_short")]+=1
 kind="both" if len(assets)==2 else "BTC_only" if "BTC" in assets else "SOL_only" if "SOL" in assets else "flat";exposure[kind]+=1
 if len(assets)==2:exposure["both_same_direction" if assets["BTC"][0]==assets["SOL"][0] else "both_opposite_direction"]+=1
 if assets:
  gross=sum(v[1] for v in assets.values());net=abs(sum(v[0]*v[1] for v in assets.values()));sol=assets.get("SOL",(0,D(0)))[1];btc=assets.get("BTC",(0,D(0)))[1]
  ss=pack(ns,e,phase,cash,ps)
  for k,v in [("gross_notional",gross),("gross_notional_to_equity",gross/e),("net_directional_notional_to_equity",net/e),("SOL_notional_to_equity",sol/e),("BTC_notional_to_equity",btc/e),("SOL_share_gross",sol/gross),("BTC_share_gross",btc/gross)]:extremekey(k,v,ss)
  if len(assets)==2:
   extremekey("paired_SOL_share_gross",sol/gross,ss);extremekey("paired_BTC_share_gross",btc/gross,ss)
 for h in horizons:
  if minute_n>=h:
   oldns,olde=ring[(minute_n-h)%43201];ret=e/olde-1;change=e-olde
   for key,val in [("return",ret),("change",change)]:
    if worst[h][key] is None or val<worst[h][key]["value"]:worst[h][key]={"value":val,"start":pack(oldns,olde,"SAMPLED_PAIRED_CLOSE"),"end":pack(ns,e,phase)}
 ring[minute_n%43201]=(ns,e);prevE=e
 finalrow=pack(ns,e,phase,cash,ps)
if excursion:excursion["end_observation"]=finalrow;episodes.append(excursion)
for i,ep in enumerate(episodes):
 ep["id"]=i+1;p=int(ep["peak"]["ns"]);t=int(ep["trough"]["ns"]);rec=int(ep["recovery"]["ns"]) if ep["recovery"] else end
 ep["peak_to_trough_days"]=D(t-p)/NSDAY;ep["trough_to_recovery_or_end_days"]=D(rec-t)/NSDAY;ep["peak_to_recovery_or_end_days"]=D(rec-p)/NSDAY
 # Strict underwater starts after attained peak; elapsed clock duration. Last-known-equal HWM is the peak timestamp.
 ep["underwater_clock_days"]=D(rec-p)/NSDAY
daily=finishperiod(day);monthly=finishperiod(month);hourly=finishperiod(hour);weekly=finishperiod(week)
for m in monthly:
 dd=[x for x in daily if x["period"].startswith(m["period"])];m["positive_days"]=sum(x["change"]>0 for x in dd);m["negative_days"]=sum(x["change"]<0 for x in dd);m["flat_days"]=sum(x["change"]==0 for x in dd)
settled=D(raw["terminal_total"]);bridge={"final_interval_marked":finalrow,"settled_total":settled,"marked_to_settled_delta":settled-D(finalrow["equity"]),"raw_settlement":raw["post_boundary_settlement"],"last_month_settled_return_percent":(settled/monthly[-1]["start_equity"]-1)*100,"product_monthly_gross":math.prod(float(x["end_equity"]/x["start_equity"]) for x in monthly),"marked_growth_exact":D(finalrow["equity"])/seed}
checks={"trace_sha256":hashlib.sha256(trace.read_bytes()).hexdigest(),"raw_sha256":hashlib.sha256(Path(ref["raw_path"]).read_bytes()).hexdigest(),"trace_rows":idx+1,"interval_native_rows":count,"interval_native_with_seed":count+1,"sampled_minutes":minute_n,"monotone_timestamps":True,"contiguous_bar_opens":True,"reproduced_all_native_DD_percent":maxdd*100,"expected_DD_percent":raw["minute_risk_observations"]["curves"]["all_native_close_samples"]["top3_distinct_excursions"][0]["drawdown_peak_percent"],"DD_exact_match":maxdd*100==D(raw["minute_risk_observations"]["curves"]["all_native_close_samples"]["top3_distinct_excursions"][0]["drawdown_peak_percent"]),"months":len(monthly),"days":len(daily),"daily_monthly_exact_chain":all(monthly[i]["start_equity"]==monthly[i-1]["end_equity"] for i in range(1,len(monthly)))}
res={"basis":{"all_native_DD":"Seed plus every interval native pre/postBTC/postSOL sample; final prequote at end-exclusive included; two post-boundary settlement rows excluded.","calendar":"One post_quote_paired_close per source minute, except finalminute uses final prequote left-limit. UTC period assigned by source bar_open_ms. Internal period ends include their boundary callbacks; finalend excludes settlement. Min/max and within-period DD in calendar CSV use this paired-minute sampling, not allphase DD.","elapsed_time":"Minutes sampled at one paired sample per source minute. Threshold sampled DD uses sampled runningpeak, with separate allnative threshold entry counts.","rolling":"Exact 1,60,1440,10080,43200-minute changes of paired native equity. 43200 is30days, not variablecalendar month.","exposure":"Actual native position quantity times same completed-bar close, divided bynativepaired equity; native side2LONG side3SHORT. Gross/share/net-directional not beta-adjusted. No realizedPnL inference.","OHLC":"67.54771031869252420136632742% is a separate conditional favorable-to-later-adverse bound. No samebar extremaordering or historicalpath assumption.","unknown":"Signedfunding, realized perasset PnL and detailed venue fidelity remain UNKNOWN; reportstatus NOT_FAITHFUL_DIAGNOSTIC and ranking_eligible false inherited."},"checks":checks,"phase_counts":phasecounts,"excluded_post_boundary":excluded,"all_native_max_DD_percent":maxdd*100,"initial_capital_minimum":minrow,"maximum_equity":maxrow,"initial_capital_loss_percent":(seed-D(minrow["equity"]))/seed*100,"drawdown_episodes_count":len(episodes),"unrecovered_episodes":sum(not x["recovered"] for x in episodes),"top10_percent":sorted(episodes,key=lambda x:x["drawdown_percent"],reverse=True)[:10],"top10_amount":sorted(episodes,key=lambda x:x["drawdown_amount"],reverse=True)[:10],"longest10_clock":sorted(episodes,key=lambda x:x["underwater_clock_days"],reverse=True)[:10],"time_underwater":{"minutes":underwater,"percent":D(underwater)/minute_n*100,"longest_minutes":maxuw,"longest_days":D(maxuw)/1440,"longest_start":utc(maxuwstart),"longest_end":utc(maxuwend)},"thresholds":th,"rolling_worst":worst,"calendar_worst":{"day":sorted(daily,key=lambda x:x["return_percent"])[:10],"hour":sorted(hourly,key=lambda x:x["return_percent"])[:10],"week":sorted(weekly,key=lambda x:x["return_percent"])[:10],"month":sorted(monthly,key=lambda x:x["return_percent"])[:10]},"exposure_minutes":exposure,"exposure_percent":{k:D(v)/minute_n*100 for k,v in exposure.items()},"exposure_extremes":extremes,"settlement_bridge":bridge,"monthly":monthly}
(P/"risk-statistics.json").write_text(json.dumps(res,indent=2,default=decdefault)+"\n")
writecsv("risk-daily.csv",daily);writecsv("risk-monthly.csv",monthly);writecsv("risk-weekly.csv",weekly)
writecsv("risk-drawdowns.csv",episodes)
# Compact plot source retains native paired daily end E, cash and marked U.
writecsv("risk-daily-curve.csv",[{k:r[k] for k in ["period","end_equity","end_cash","end_native_unrealized","return_percent"]} for r in daily])
print(json.dumps({"checks":checks,"top3":res["top10_percent"][:3],"time_underwater":res["time_underwater"],"thresholds":th,"exposure_minutes":exposure,"extremes":{k:{"value":v["value"],"utc":v["snapshot"]["utc"]} for k,v in extremes.items()},"bridge":bridge,"monthly":[{k:r[k] for k in ["period","start_equity","end_equity","return_percent","within_period_DD_percent","positive_days","negative_days","flat_days"]} for r in monthly]},default=decdefault))

