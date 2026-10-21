"""EV01 inventory only: pinned native T/V records; no engine, labels or fit."""
import bisect,collections,csv,datetime,gzip,hashlib,json,resource,time
from pathlib import Path
R=Path("reports/btc-sol-event-risk-20261021"); OLD=Path("reports/fast-rnd-20261020")
START=1725148800000000000; V=1762992000000000000; CUT=1775606400000000000; DAY=86400000000000
started=time.monotonic();manifest=json.loads((OLD/"s0-artifact-manifest.json").read_text());files=manifest["files"]
def path(s):return next(p for p in files if p.endswith(s))
def sha(p):
 h=hashlib.sha256()
 with open(p,"rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
 return h.hexdigest()
def split(t):return "T" if t<V else "V"
def stamp(s):
 if str(s).isdigit():return int(s)
 return int(datetime.datetime.fromisoformat(s.replace("Z","+00:00")).timestamp())*10**9
# Read JSON structure, but inspect only timestamp-filtered lifecycle records, never U monetary/outcome details.
raw=json.load(open(path("-raw-native.json")))
parents=[p for p in raw["entry_sizing_audit"] if START<=int(p["q0_ns"])<CUT]
parent_times=[int(p["q0_ns"]) for p in parents];parent_ids=[p["episode_id"] for p in parents]
def parent_at(t):
 i=bisect.bisect_right(parent_times,t)-1
 return parent_ids[i] if i>=0 else None
counts=collections.Counter();sol_parents=set();btc_parents=set();sol_rights=set();order_rows=[]
for oid,o in raw["native_order_events"].items():
 t=int(o["submit_ns"])
 if not START<=t<CUT:continue
 counts[(split(t),"orders",o["action"],o["reason"],o["level"])]+=1
 pid=parent_at(t)
 order_rows.append(dict(order_id=oid,submit_ns=t,split=split(t),parent_episode=pid,**{k:o[k] for k in ["action","reason","level","instrument"]}))
 if o["action"]=="SOL_ADD":sol_parents.add(pid);sol_rights.add((pid,o["level"]))
 if o["action"]=="BTC_REDUCE":btc_parents.add(pid)
for f in raw["fill_audit"]:
 t=int(f["fill_ns"])
 if START<=t<CUT:counts[(split(t),"fills",f["action"],f["reason"],f["level"])]+=1
orders={r["client_order_id"]:r for r in csv.DictReader(open(path("-orders.csv")))}
for r in order_rows:r["terminal_status"]=orders[r["order_id"]]["status"]
# One streaming pass, timestamps checked before position/monetary payload; retain only strict predecision snapshots.
daily=[];decision=START+DAY;previous=None;n=0;last=None
with gzip.open(path("minute-native-settled-receipts.csv.gz"),"rt") as f:
 for row in csv.DictReader(f):
  receipt=int(row["receipt_ns"]);source=int(row["source_quote_ns"])
  if receipt>=CUT or source>=CUT:break
  assert source<receipt and (last is None or receipt>last)
  while decision<=receipt:
   if previous is not None:
    ps=json.loads(previous["native_positions_and_mark_ohlc_json"])
    assets=[p["instrument_id"].split("USDT")[0] for p in ps]
    daily.append(dict(decision_ns=decision,split=split(decision),source_ns=int(previous["source_quote_ns"]),receipt_ns=int(previous["receipt_ns"]),assets=assets,parent_episode=parent_at(decision)))
   decision+=DAY
  previous=row;last=receipt;n+=1
assert decision==CUT and n==840958
states=collections.Counter((r["split"],"+".join(sorted(r["assets"])) or "FLAT") for r in daily)
btc_daily=[r for r in daily if "BTC" in r["assets"]]
result=dict(status="EV01_INVENTORY_ONLY_CONTRACT_PENDING",scope="T+V only; U timestamp boundary checked before payload; no outcomes/labels fit",inputs={p:{**files[p],"verified":sha(p)==files[p]["sha256"]} for p in [path("-raw-native.json"),path("-orders.csv"),path("-fills.csv"),path("minute-native-settled-receipts.csv.gz")]},parent_count=len(parents),parents_by_split=dict(collections.Counter(split(int(p["q0_ns"])) for p in parents)),order_fill_counts=[dict(split=s,kind=k,action=a,reason=r,level=l,count=n) for (s,k,a,r,l),n in sorted(counts.items())],daily_predecision_state_counts=[dict(split=s,assets=a,count=n) for (s,a),n in sorted(states.items())],daily_snapshots=len(daily),btc_open_daily=len(btc_daily),btc_open_daily_parent_count=len(set(r["parent_episode"] for r in btc_daily)),btc_reduce_order_parent_count=len(btc_parents),sol_add_order_parent_count=len(sol_parents),sol_unique_parent_levels=len(sol_rights),sol_order_terminal_statuses=dict(collections.Counter(r["terminal_status"] for r in order_rows if r["action"]=="SOL_ADD")),receipt_rows=n,resources=dict(wall_seconds=time.monotonic()-started,peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),missing=["no complete per-decision domain snapshot / pending-intent/right consumption trace", "native order audit omits intent_id and episode_id; parent association uses causal parent start interval", "no native per-asset close UPnL/realized position report", "no signed funding cash delta"],not_claimed=["daily open-position opportunity is not proof ordinary domain branch was reachable", "filled/submitted SOL intents are not every preintent qualifying state", "no perasset synthetic PnL", "no risk outcome is action value"])
assert all(v["verified"] for v in result["inputs"].values())
(R/"ev01-inventory-result.json").write_text(json.dumps(result,indent=2)+"\n")
with (R/"ev01-native-order-inventory.csv").open("w") as f:
 w=csv.DictWriter(f,fieldnames=list(order_rows[0]));w.writeheader();w.writerows(order_rows)
with (R/"ev01-daily-state-inventory.csv").open("w") as f:
 w=csv.DictWriter(f,fieldnames=list(daily[0]));w.writeheader();w.writerows(daily)
print(json.dumps({k:v for k,v in result.items() if k not in ["inputs","order_fill_counts"]},indent=2))
