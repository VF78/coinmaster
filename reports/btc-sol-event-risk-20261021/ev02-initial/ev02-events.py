"""Frozen EV02: native portfolio-risk labels; stdlib bounded one-pass reader.
No strategy execution, per-asset PnL reconstruction, model or U payload inspection.
"""
import bisect,collections,csv,gzip,hashlib,json,math,resource,time
from decimal import Decimal as D
from pathlib import Path
R=Path("reports/btc-sol-event-risk-20261021");OLD=Path("reports/fast-rnd-20261020")
START=1725148800000000000;SPLIT=1744070400000000000;CUT=1775606400000000000
HORIZON=72*3600*10**9;MINUTE=60*10**9
CONTRACT="349b7eee60dac275a481187e747a932b1b50bf62bb23018ac3dad891c949ff49"
def digest(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()
def union_components(events):
 """Union by same parent OR temporal overlap, cross-asset and cross-parent."""
 parent=list(range(len(events)))
 def find(i):
  while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
  return i
 def join(i,j):
  a,b=find(i),find(j)
  if a!=b:parent[b]=a
 by_parent={}
 for i,e in enumerate(events):
  if e["parent_id"] in by_parent:join(i,by_parent[e["parent_id"]])
  else:by_parent[e["parent_id"]]=i
 # Equal endpoints are considered overlapping conservatively.
 order=sorted(range(len(events)),key=lambda i:events[i]["decision_ns"])
 active=[]
 for i in order:
  t=events[i]["decision_ns"];active=[j for j in active if events[j]["horizon_end_ns"]>=t]
  for j in active:join(i,j)
  active.append(i)
 groups=collections.defaultdict(list)
 for i,e in enumerate(events):groups[find(i)].append(e)
 return sorted(groups.values(),key=lambda g:min(e["decision_ns"] for e in g))
def allocation(blocks,minimum):
 purepos=[];pureneg=[];mixed=[]
 for b in blocks:
  labels=set(b["labels"])
  (purepos if labels=={1} else pureneg if labels=={0} else mixed).append(b["block_id"])
 dp=max(0,minimum-len(purepos));dn=max(0,minimum-len(pureneg));feasible=dp+dn<=len(mixed)
 assignments={b:"positive" for b in purepos};assignments.update({b:"negative" for b in pureneg})
 for b in mixed:
  if dp:assignments[b]="positive";dp-=1
  elif dn:assignments[b]="negative";dn-=1
  else:assignments[b]="unused_mixed"
 return dict(pure_positive=len(purepos),pure_negative=len(pureneg),mixed=len(mixed),disjoint_allocation=assignments,remaining_positive_deficit=dp,remaining_negative_deficit=dn,class_minimum=minimum,disjoint_class_minimum_pass=feasible)
def focused_tests():
 # OR, different parents/assets and transitive temporal overlap.
 a=[dict(parent_id="p1",decision_ns=0,horizon_end_ns=10),dict(parent_id="p2",decision_ns=9,horizon_end_ns=20),dict(parent_id="p3",decision_ns=19,horizon_end_ns=30),dict(parent_id="p1",decision_ns=100,horizon_end_ns=110)]
 assert len(union_components(a))==1
 assert len(union_components([a[0],dict(parent_id="p4",decision_ns=11,horizon_end_ns=12)]))==2
 b=[dict(block_id="m1",labels=[0,1]),dict(block_id="m2",labels=[0,1])]
 assert allocation(b,1)["disjoint_allocation"]=={"m1":"positive","m2":"negative"}
 assert not allocation(b[:1],1)["disjoint_class_minimum_pass"]
 assert D("89.999")<=D("100")*D("0.9") and not D("90.001")<=D("100")*D("0.9")
 return ["OR_components_cross_parent_transitive", "same_parent_disjoint_time_union", "nonoverlap_stays_separate", "mixed_blocks_not_double_counted", "nativeW_threshold_exact_decimal"]
def main():
 started=time.monotonic();tests=focused_tests()
 assert digest(R/"ev01-contract.md")==CONTRACT
 freeze=json.loads((R/"ev01-freeze.json").read_text()); assert freeze["contract_sha256"]==CONTRACT and freeze["status"]=="GO_EV02_LABELS_AND_SUFFICIENCY_ONLY"
 manifest=json.loads((OLD/"s0-artifact-manifest.json").read_text());files=manifest["files"]
 def path(s):return next(p for p in files if p.endswith(s))
 input_paths=[path("-raw-native.json"),path("minute-native-settled-receipts.csv.gz"),str(R/"ev01-daily-state-inventory.csv"),str(R/"ev01-native-order-inventory.csv")]
 inputs={p:digest(p) for p in input_paths}
 for p in input_paths[:2]:assert inputs[p]==files[p]["sha256"]
 raw=json.load(open(input_paths[0]))
 parents=sorted([p for p in raw["entry_sizing_audit"] if START<=int(p["q0_ns"])<CUT],key=lambda p:int(p["q0_ns"]))
 parent_times=[int(p["q0_ns"]) for p in parents];parent_ids=[p["episode_id"] for p in parents]
 bounds={p["episode_id"]:(int(p["q0_ns"]),parent_times[i+1] if i+1<len(parents) else CUT) for i,p in enumerate(parents)}
 sides={p["episode_id"]:p["side"] for p in raw["btc_sizing_audit"] if START<=int(p["timestamp_ns"])<CUT}
 def pid_at(t):
  i=bisect.bisect_right(parent_times,t)-1
  return parent_ids[i] if i>=0 else None
 fills=[]
 for f in raw["fill_audit"]:
  t=int(f["fill_ns"])
  if START<=t<CUT:fills.append(dict(t=t,parent_id=pid_at(t),instrument=f["instrument"],action=f["action"],level=f["level"]))
 fills.sort(key=lambda f:f["t"]);filltimes=[f["t"] for f in fills]
 entries={}
 for f in fills:
  if f["action"]=="BTC_ENTRY":entries.setdefault(f["parent_id"],f["t"])
 daily=list(csv.DictReader(open(R/"ev01-daily-state-inventory.csv")))
 orders=list(csv.DictReader(open(R/"ev01-native-order-inventory.csv")))
 events=[]
 def event(kind,t,pid,level=""):
  return dict(event_id=f"{kind}:{pid}:{t}:{level}",hypothesis=kind,parent_id=pid,level=level,decision_ns=t,horizon_end_ns=t+HORIZON,split="TRAIN" if t<SPLIT else "CHECK",exclusion_reasons=[],reachability="UNKNOWN_NATIVE_DOMAIN_SNAPSHOT_MISSING" if kind=="BTC" else "OBSERVED_NATIVE_SUBMISSION",source_state_ns=None,receipt_ns=None,feature_missing_flags=[],future_min_W=None,label=None,future_receipt_count=0)
 for r in daily:
  if "BTC" in r["assets"]:events.append(event("BTC",int(r["decision_ns"]),r["parent_episode"]))
 seen=set()
 for r in orders:
  if r["action"]!="SOL_ADD":continue
  key=(r["parent_episode"],r["level"])
  if key in seen:continue
  seen.add(key);events.append(event("SOL",int(r["submit_ns"]),*key))
 assert len(seen)==26 and len([e for e in events if e["hypothesis"]=="BTC"])==222
 assert len(set(e["event_id"] for e in events))==len(events)
 assert len({(e["parent_id"],e["level"]) for e in events if e["hypothesis"]=="SOL"})==26
 for e in events:
  t=e["decision_ns"];start,end=bounds[e["parent_id"]]
  if start<SPLIT<end:e["exclusion_reasons"].append("CONSERVATIVE_PARENT_INTERVAL_CROSSES_SPLIT")
  if e["horizon_end_ns"]>=(SPLIT if t<SPLIT else CUT):e["exclusion_reasons"].append("FULL72H_HORIZON_NOT_INSIDE_PARTITION")
 events.sort(key=lambda e:(e["decision_ns"],e["hypothesis"],e["event_id"]))
 current=0;active=[];previous=None;last=None;peak=D(10000);n=0;boundary_filtered=False
 def prepare(e,prior,priorpeak):
  t=e["decision_ns"]
  if prior is None:e["exclusion_reasons"].append("NO_PRIOR_NATIVE_RECEIPT");return
  source=int(prior["source_quote_ns"]);receipt=int(prior["receipt_ns"])
  assert source<receipt<t
  e.update(source_state_ns=source,receipt_ns=receipt)
  if t-receipt>2*MINUTE:e["exclusion_reasons"].append("PRIOR_RECEIPT_STALE_OVER2MIN")
  if bisect.bisect_right(filltimes,t)>bisect.bisect_right(filltimes,receipt):e["exclusion_reasons"].append("UNSETTLED_OR_SAME_BOUNDARY_NATIVE_FILL")
  ps=json.loads(prior["native_positions_and_mark_ohlc_json"]);W=D(prior["paired_close_equity"]);cash=D(prior["cash"])
  e.update(W=str(W),cash=str(cash),total_native_UPnL=str(W-cash),UPnL_to_equity=str((W-cash)/W),causal_native_drawdown=str(1-W/priorpeak),parent_side=sides[e["parent_id"]])
  by_asset={p["instrument_id"].split("USDT")[0]:p for p in ps}
  for a in ["BTC","SOL"]:e[a+"_present"]=a in by_asset;e[a+"_quantity"]=by_asset[a]["quantity"] if a in by_asset else "0"
  first=entries.get(e["parent_id"])
  if first is None or first>=t:e["first_confirmed_BTC_entry_ns"]=None;e["parent_age_seconds"]=None;e["feature_missing_flags"].append("NO_STRICT_PRIOR_CONFIRMED_BTC_ENTRY")
  else:e["first_confirmed_BTC_entry_ns"]=first;e["parent_age_seconds"]=(t-first)/1e9
  prior_levels={f["level"] for f in fills[:bisect.bisect_left(filltimes,t)] if f["parent_id"]==e["parent_id"] and f["action"]=="BTC_REDUCE" and f["level"]!=""}
  e["prior_confirmed_BTC_TP_levels"]=len(prior_levels)
  if e["hypothesis"]=="BTC":e["feature_missing_flags"].append("ORDINARY_BRANCH_REACHABILITY_PENDING_RIGHT_STATE_UNKNOWN")
  if not e["exclusion_reasons"]:active.append(e)
 with gzip.open(input_paths[1],"rt") as f:
  for row in csv.DictReader(f):
   receipt=int(row["receipt_ns"]);source=int(row["source_quote_ns"])
   if receipt>=CUT or source>=CUT:boundary_filtered=True;break
   assert source<receipt and (last is None or receipt>last)
   while current<len(events) and events[current]["decision_ns"]<=receipt:
    prepare(events[current],previous,peak);current+=1
   W=D(row["paired_close_equity"])
   continuing=[]
   for e in active:
    if receipt>e["horizon_end_ns"]:
     e["label"]=int(D(e["future_min_W"])<=D(e["W"])*D("0.9")) if e["future_min_W"] is not None else None
     if e["label"] is None:e["exclusion_reasons"].append("NO_FUTURE_NATIVE_W")
     continue
    if receipt>e["decision_ns"] and source>=e["decision_ns"]:
     e["future_receipt_count"]+=1
     if e["future_min_W"] is None or W<D(e["future_min_W"]):e["future_min_W"]=str(W)
    continuing.append(e)
   active=continuing;peak=max(peak,W);previous=row;last=receipt;n+=1
 assert boundary_filtered and n==840958 and current==len(events) and not active
 for e in events:
  if e["label"] is not None:
   assert e["horizon_end_ns"]<(SPLIT if e["split"]=="TRAIN" else CUT)
   assert e["source_state_ns"]<e["receipt_ns"]<e["decision_ns"]
   assert not e["exclusion_reasons"]
   e["native_W_adverse_fraction"]=str(1-D(e["future_min_W"])/D(e["W"]))
 # Cross-hypothesis union, then summarize each branch by the same global block IDs.
 valid=[e for e in events if e["label"] is not None];components=union_components(valid);blocks=[]
 for i,g in enumerate(components):
  splits=set(e["split"] for e in g);assert len(splits)==1,"CROSS_PARTITION_COMPONENT"
  bid=f"block-{i:04d}"
  for e in g:e["block_id"]=bid
  blocks.append(dict(block_id=bid,split=g[0]["split"],first_event_ns=min(e["decision_ns"] for e in g),last_event_ns=max(e["decision_ns"] for e in g),horizon_end_ns=max(e["horizon_end_ns"] for e in g),parent_ids=sorted(set(e["parent_id"] for e in g)),hypotheses=sorted(set(e["hypothesis"] for e in g)),event_count=len(g),labels=[e["label"] for e in g]))
 summary={}
 for kind in ["BTC","SOL"]:
  summary[kind]={}
  for split in ["TRAIN","CHECK"]:
   es=[e for e in events if e["hypothesis"]==kind and e["split"]==split];vs=[e for e in es if e["label"] is not None]
   selected=[]
   for b in blocks:
    g=[e for e in vs if e.get("block_id")==b["block_id"]]
    if g:selected.append(dict(block_id=b["block_id"],labels=[e["label"] for e in g]))
   a=allocation(selected,5 if split=="TRAIN" else 3);minimum=10 if split=="TRAIN" else 6
   summary[kind][split]=dict(events=len(es),parents_before_exclusion=len(set(e["parent_id"] for e in es)),valid_labeled_events=len(vs),valid_parents=len(set(e["parent_id"] for e in vs)),labels=dict(collections.Counter(e["label"] for e in vs)),excluded_events=len(es)-len(vs),exclusion_reason_counts=dict(collections.Counter(r for e in es for r in e["exclusion_reasons"])),connected_blocks=len(selected),total_blocks_minimum=minimum,total_blocks_minimum_pass=len(selected)>=minimum,**a,sufficiency_pass=len(selected)>=minimum and a["disjoint_class_minimum_pass"])
  summary[kind]["eligible_for_method_comparison"]=all(summary[kind][s]["sufficiency_pass"] for s in ["TRAIN","CHECK"])
 outputs={}
 for name,data in [("ev02-events.json",events),("ev02-connected-blocks.json",blocks)]:
  p=R/name;p.write_text(json.dumps(data,indent=2)+"\n");outputs[str(p)]=digest(p)
 with (R/"ev02-events.csv").open("w") as f:
  fields=sorted(set(k for e in events for k in e));w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for e in events:w.writerow({k:json.dumps(v) if isinstance(v,(list,dict)) else v for k,v in e.items()})
 outputs[str(R/"ev02-events.csv")]=digest(R/"ev02-events.csv")
 tests += ["4_EV01_input_hashes_previously_frozen_2_reread_here", "26_unique_SOL_first_rights", "222_complete_BTC_opportunity_universe", "source_receipt_strictly_before_event", "stale_and_unsettled_fill_exclusions", "full72h_partition_purge", "conservative_wholeparent_purge", "no_component_across_partition", "U_boundary_before_payload", "840958_native_receipts_monotone"]
 result=dict(status="EV02_COMPLETE_NO_FITS",contract_sha256=CONTRACT,freeze_sha256=digest(R/"ev01-freeze.json"),inputs=inputs,outputs=outputs,counts=dict(all_events=len(events),labeled_events=len(valid),connected_blocks=len(blocks),native_receipts=n),summary=summary,checks=dict(status="PASS",names=tests),resources=dict(wall_seconds=time.monotonic()-started,peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),limitations=["BTC daily events are opportunity risk samples; action reachability remains UNKNOWN", "parent association uses entry-start intervals; full-parent purge conservative", "risk of original S0 continuation is not reduce/skip actionvalue", "small counts exploratory only; no statistical/economic guarantee", "native signed funding and perasset PnL remain UNKNOWN"],U_payloads_inspected=0,engine_launches=0,model_fits=0)
 assert result["resources"]["peak_RSS_bytes"]<100*1024**2
 (R/"ev02-sufficiency.json").write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result,indent=2))
if __name__=="__main__":main()
