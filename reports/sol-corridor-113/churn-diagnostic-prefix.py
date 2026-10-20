"""ONE partial-prefix decode, observed inventory churn only; no engines or PnL replay."""
import json,csv,zlib,hashlib,time,collections,heapq,resource
from decimal import Decimal as D
from pathlib import Path
P=Path("reports/sol-corridor-113");C=json.load(open(P/"r2-completion.json"));F=Path(next(x["path"] for x in C["surviving_files"] if x["path"].endswith("minute-native-risk.csv.gz")))
T=time.monotonic();dec=zlib.decompressobj(16+zlib.MAX_WBITS);buf="";header=None;rows=0;compressed=0;h=hashlib.sha256();phase=collections.Counter();kinds=collections.Counter();equitytypes=collections.Counter();counts={a:collections.Counter() for a in ["BTC","SOL"]};days=collections.defaultdict(lambda:collections.Counter());intervals=collections.Counter()
scales={"BTC":1000,"SOL":10};prevq={"BTC":0,"SOL":0};prevbasis={"BTC":None,"SOL":None};lastsign={"BTC":None,"SOL":None};openep={};episodes={a:{"started":0,"closed":0,"last":None} for a in scales};prevE=None;prevCash=None;prevmark=None;prevns=None;prevbar=None;unique_ns=0;unique_bar=0;btcrev=0;prevsol=None;examples=[];alternations=[];largest=[];seq=0;group=None;same=collections.Counter()
def utc(t):return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(t/1e9))
def flushgroup(g):
 if not g:return
 for a,events in g["events"].items():
  if len(events)>1:same[a+"_multi_transition_timestamps"]+=1;same[a+"_transitions_in_multi_timestamps"]+=len(events)
  if any(x*y<0 for x,y in zip(events,events[1:])):same[a+"_opposite_delta_same_timestamp"]+=1
  if events and g["start"][a]==g["end"][a]:same[a+"_net_zero_observed_roundtrip_timestamp"]+=1
def consume(text):
 global buf,header,rows,prevq,prevbasis,prevE,prevCash,prevmark,prevns,prevbar,unique_ns,unique_bar,btcrev,prevsol,group,seq,ph
 buf+=text
 assert len(buf)<4*1024*1024
 lines=buf.split("\n");buf=lines.pop()
 for line in lines:
  if not line.strip():continue
  rr=next(csv.reader([line]))
  if header is None:header=rr;continue
  assert len(rr)==len(header)
  r=dict(zip(header,rr));rows+=1;ns=int(r["close_available_ns"]);bar=int(r["bar_open_ms"]);ph=r["phase"];phase[ph]+=1
  assert prevns is None or ns>=prevns
  if ns!=prevns:
   flushgroup(group);unique_ns+=1;group={"start":dict(prevq),"end":None,"events":{"BTC":[],"SOL":[]}}
  if bar!=prevbar:unique_bar+=1
  q={"BTC":0,"SOL":0};basis={"BTC":None,"SOL":None};marks={}
  for p in json.loads(r["native_positions_and_mark_ohlc_json"]):
   a=p["instrument_id"][:3];units=D(p["quantity"])*scales[a];assert units==int(units);q[a]=int(units)*(1 if p["side"]=="2" else -1);basis[a]=p["avg_px_open"];marks[a]=p["mark_ohlc"]["close"]
  changed=[a for a in scales if q[a]!=prevq[a]];bchange=any(basis[a]!=prevbasis[a] for a in scales if q[a]==prevq[a] and q[a])
  if "BTC" in changed:btcrev+=1
  for a in changed:
   old=prevq[a];new=q[a];du=new-old;ad=abs(du);counts[a]["qty_transitions"]+=1;group["events"][a].append(du);day=utc(ns)[:10];days[day][a+"_transitions"]+=1
   action="OPEN" if old==0 else "CLOSE" if new==0 else "REVERSE" if old*new<0 else "ADD" if abs(new)>abs(old) else "REDUCE"
   counts[a][action]+=1
   if ad==1:counts[a]["one_native_step_delta"]+=1
   if ad<=scales[a]:counts[a]["delta_at_most_1_coin"]+=1
   if ad<=10*scales[a]:counts[a]["delta_at_most_10_coins"]+=1
   if a=="SOL" and ad==1000*scales[a]:counts[a]["delta_exact_1000_SOL"]+=1
   e={"utc":utc(ns),"phase":ph,"asset":a,"action":action,"old_qty":old/scales[a],"new_qty":new/scales[a],"delta_qty":du/scales[a],"BTC_qty":q["BTC"]/1000,"cash":r["cash"],"paired_equity":r["paired_close_equity"]}
   if len(examples)<16:examples.append(e)
   seq+=1
   if len(largest)<12:heapq.heappush(largest,(ad/scales[a],seq,e))
   elif ad/scales[a]>largest[0][0]:heapq.heapreplace(largest,(ad/scales[a],seq,e))
   if old==0 or old*new<0:
    if old*new<0:episodes[a]["closed"]+=1
    episodes[a]["started"]+=1;openep[a]={"start":utc(ns),"side":"LONG" if new>0 else "SHORT"}
   elif new==0:
    episodes[a]["closed"]+=1;episodes[a]["last"]={**openep.get(a,{}),"end":utc(ns)};openep.pop(a,None)
   if a=="SOL":
    if prevsol:
     dt=(ns-prevsol["ns"])/1e9;bucket="same_timestamp" if dt==0 else "1_to_60s" if dt<=60 else "61_to_300s" if dt<=300 else "301_to_900s" if dt<=900 else "901_to_3600s" if dt<=3600 else "over_1h";intervals[bucket]+=1
     continuous=old and new and prevsol["old"] and prevsol["new"] and (old>0)==(new>0)==(prevsol["old"]>0)==(prevsol["new"]>0)
     if du*prevsol["delta"]<0:
      counts[a]["adjacent_change_opposite_delta"]+=1
      if dt<=60 and continuous and btcrev==prevsol["btcrev"]:
       counts[a]["opposite_delta_within60s_same_side_BTC_unchanged"]+=1
       if len(alternations)<12:alternations.append({"previous":prevsol["event"],"current":e,"seconds":dt})
    prevsol={"ns":ns,"delta":du,"old":old,"new":new,"btcrev":btcrev,"event":e}
  for a in scales:
   if q[a]==prevq[a] and q[a] and basis[a]!=prevbasis[a]:counts[a]["basis_only_changes_same_qty"]+=1
  E=r["paired_close_equity"];cash=r["cash"]
  if prevE is not None:
   if changed:equitytypes["qty_change_intervals"]+=1
   elif bchange:equitytypes["same_qty_basis_change_intervals"]+=1
   elif D(cash)!=D(prevCash):equitytypes["same_inventory_cash_change_intervals"]+=1
   elif D(E)!=D(prevE):equitytypes["same_inventory_cash_unchanged_equity_changed_mark_consistent"]+=1
   else:equitytypes["same_inventory_cash_equity_unchanged"]+=1
  if len(q)==2:
   kind="both" if q["BTC"] and q["SOL"] else "BTC_only" if q["BTC"] else "SOL_only" if q["SOL"] else "flat"
   if ph=="post_quote_paired_close":kinds[kind]+=1
  group["end"]=dict(q);prevq=q;prevbasis=basis;prevE=E;prevCash=cash;prevmark=marks;prevns=ns;prevbar=bar
  if rows==100000:print(json.dumps({"INTERIM":rows,"counts":counts,"same_timestamp":same}),flush=True)
with F.open("rb") as f:
 while True:
  chunk=f.read(65536)
  if not chunk:break
  compressed+=len(chunk);h.update(chunk)
  while chunk:
   out=dec.decompress(chunk,1024*1024);chunk=dec.unconsumed_tail;consume(out.decode("utf-8"))
flushgroup(group)
assert rows==392240 and compressed==11436420 and h.hexdigest()=="51da0e4405e7031960e0668395a78a4dfe902c37bfca8f843bfdd29728b1f052"
assert phase["post_quote_paired_close"]==130746
for a in scales:episodes[a]["open_at_prefix_end"]=openep.get(a)
res={"status":"OBSERVED_PARTIAL_INVENTORY_TRANSITIONS_NOT_FILL_COUNTS","actual_order_counts":"UNKNOWN_NO_DURABLE_ORDER_EXPORT_OR_LOG_ROWS","actual_fill_counts":"UNKNOWN_NO_DURABLE_FILL_EXPORT_OR_LOG_ROWS","synthetic_30000_fixture":"NOT_THIS_RUN_NOT_USED","control_reference":{"native_fill_report_rows":621,"interval":"full24m; not comparable directly to partial transition counts"},"trace":{"rows":rows,"source_timestamps":unique_bar,"quote_observation_timestamps":unique_ns,"phases":phase,"complete_post_SOL_observations":sum(kinds.values()),"gzip_complete":dec.eof,"last_observed_UTC":utc(prevns),"last_phase":ph,"compressed_bytes":compressed,"sha256":h.hexdigest(),"additional_unterminated_text_bytes_not_counted":len(buf)},"observed_transitions":counts,"observed_exposure_episodes":episodes,"same_timestamp_patterns":same,"SOL_inter_transition_seconds":intervals,"observed_step_categories":equitytypes,"post_SOL_exposure_minutes":kinds,"by_day":days,"first_examples":examples,"adjacent_alternation_examples":alternations,"largest_observed_qty_changes":[x[2] for x in sorted(largest,reverse=True)],"limits":["Quantity transitions are stored native-cache observations, not order submissions or actual fills; multiple fills and same-quote net-zero cycles can be hidden between samples.","Mark-consistent changes with observed qty/basis/cash unchanged are not fill counts or realized-PnL attribution. Cash changes can be funding, fees, realized settlement or bookkeeping; finality is uncertified.","No actual turnover/fees/action causes can be reconstructed from this trace alone; no counterfactual PnL engine or control rescan.","Exposure episodes are observed zero/nonzero signed-inventory spells, not domain/alpha/hedge episodes."],"resources":{"seconds":time.monotonic()-T,"max_RSS_KiB":resource.getrusage(resource.RUSAGE_SELF).ru_maxrss},"diagnostic_prefix_decode_passes":2,"first_pass_serializer_failure":"NameError ph after full decode;100k interim preserved; root explicitly authorized one corrected read-only repeat; no nativeengine"}
(P/"churn-diagnostic-statistics.json").write_text(json.dumps(res,indent=2)+"\n")
print(json.dumps({"FINAL":True,"counts":counts,"episodes":episodes,"same_timestamp":same,"SOL_timing":intervals,"step_categories":equitytypes,"resources":res["resources"]}),flush=True)

