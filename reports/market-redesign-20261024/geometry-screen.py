#!/usr/bin/env python3
"""Cheap frozen-E4 sizing and U price-proxy screen; never computes candidate PnL."""
import csv, json, hashlib, collections, subprocess
from pathlib import Path
from decimal import Decimal as D, ROUND_FLOOR, ROUND_CEILING
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
BASE=ROOT/'reports/b-50-90-next-20261023'
FILES=[BASE/'owner-E4-events'/f'{n}.csv' for n in ['entry-sizing-audit','split-parent-audit','native-fills','native-orders','native-order-events','next-band-audit']]+[BASE/'owner-closed-bars.csv']
SPEC=OUT/'task-source.txt'
def read(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
def dumpcsv(path, rows):
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def floor(x,step=D('.001')):return (x/step).to_integral_value(rounding=ROUND_FLOOR)*step
def tick(x,side):return (x/D('.1')).to_integral_value(rounding=ROUND_CEILING if side==1 else ROUND_FLOOR)*D('.1')
def iso(ns):return datetime.fromtimestamp(int(ns)/1e9,timezone.utc).isoformat()
a=read(FILES[0]); split=read(FILES[1]); fills=read(FILES[2]);orders={r['client_order_id']:r for r in read(FILES[3])};events=read(FILES[4]); bars=read(FILES[6])
assert len(a)==len(split)==83
assert len({x['episode_id'] for x in a})==83
byid={x['episode_id']:x for x in a}
phi={1:D('.8551535379805835'),-1:D('.7977111237672364')}
cut=int(datetime(2025,9,1,tzinfo=timezone.utc).timestamp()*1e9)
rows=[]
for i,s in enumerate(split):
 r=byid[s['episode_id']]; side=int(s['side']);lo=int(s['start_ns']); hi=int(split[i+1]['start_ns']) if i+1<len(split) else 2**63
 gross=D(r['reference_btc_qty']);old=D(r['admitted_net_quantity']);qclean=phi[side]*gross;lotclean=floor(qclean);p=D(s['first_vwap']);q0p=D(r['reference_wire_price'])
 tps=[e for e in events if e['reason']=='BTC_TP3' and lo<=int(e['submit_ns'])<hi and orders[e['client_order_id']]['type']=='LIMIT']
 assert len(tps)<=1
 v={'cycle':i+1,'episode_id':s['episode_id'],'entry_utc':iso(lo),'period':'first_year' if lo<cut else 'second_year','side':'LONG' if side==1 else 'SHORT','branch':r['branch'],'omitted_zero_levels':r['omitted_zero_levels'],'archived_q0_wire_price':q0p,'archived_gross_q0':gross,'archived_net_q1':old,'old_net_fraction':old/gross,'phi':phi[side],'clean_q_proxy_pre_lot':qclean,'clean_q_proxy_lot':lotclean,'old_first_q':s['first_quantity'],'clean_first_q_proxy':floor(lotclean/D(2)),'clean_old_ratio_pre_lot':qclean/old,'clean_old_ratio_lot':lotclean/old,'old_plan_notional_at_q0_wire':old*q0p,'clean_plan_notional_proxy_at_q0_wire':lotclean*q0p,'P0_archived_first_vwap':p,'second_limit_005':floor(p*D('.995'),D('.1')) if side==1 else (p*D('1.005')/D('.1')).to_integral_value(rounding=ROUND_CEILING)*D('.1'),'raw_entry_d3':'NOT_EXPORTED','TP3_order_id':'','TP3_submit_utc':'','TP3_accept_utc':'','TP3_archived_price':'','TP3_order_status':'','d3_native_price_proxy':'','U_TP1_proxy':'','U_TP2_proxy':'','U_TP3_proxy':'','U_proxy_ordered':'','U_proxy_all_fee_positive':'','U_min_fee_surplus_USDT_per_BTC':''}
 if tps:
  e=tps[0];o=orders[e['client_order_id']];tp3=D(o['price']);d3=D(side)*(tp3/p-D(1));assert d3>0
  prices=[tick(p+(tp3-p)*f,side) for f in [D(1)/3,D(2)/3]]+[tp3]
  assert prices[2]==tp3
  ds=[D(side)*(x/p-1) for x in prices];net=[D(side)*(x-p)-p*D('.00055')-x*D('.0002') for x in prices]
  v.update(TP3_order_id=o['client_order_id'],TP3_submit_utc=iso(e['submit_ns']),TP3_accept_utc=iso(e['accept_ns']) if e['accept_ns'] else 'NOT_EXPORTED',TP3_archived_price=tp3,TP3_order_status=o['status'],d3_native_price_proxy=d3,U_TP1_proxy=prices[0],U_TP2_proxy=prices[1],U_TP3_proxy=prices[2],U_proxy_ordered=0<ds[0]<ds[1]<ds[2],U_proxy_all_fee_positive=min(net)>0,U_min_fee_surplus_USDT_per_BTC=min(net))
 rows.append(v)
dumpcsv(OUT/'geometry-cycles.csv',rows)
groups=[]
for period in ['all','first_year','second_year']:
 for side in ['ALL','LONG','SHORT']:
  z=[r for r in rows if (period=='all' or r['period']==period) and (side=='ALL' or r['side']==side)]
  cnt=collections.Counter((r['branch'],r['omitted_zero_levels']) for r in z)
  oldsum=sum(r['old_plan_notional_at_q0_wire'] for r in z);newsum=sum(r['clean_plan_notional_proxy_at_q0_wire'] for r in z)
  groups.append({'period':period,'side':side,'n':len(z),'full_fallback':cnt[('MARKETABLE_FULL_ENTRY_FALLBACK','[]')],'omit_01':cnt[('PASSIVE_NET_ZERO_LEVELS','[0,1]')],'omit_0':cnt[('PASSIVE_NET_ZERO_LEVELS','[0]')],'mean_old_net_fraction':sum(r['old_net_fraction'] for r in z)/len(z),'mean_clean_old_ratio_pre_lot':sum(r['clean_old_ratio_pre_lot'] for r in z)/len(z),'min_clean_old_ratio_lot':min(r['clean_old_ratio_lot'] for r in z),'max_clean_old_ratio_lot':max(r['clean_old_ratio_lot'] for r in z),'old_plan_notional_sum_q0_wire':oldsum,'clean_plan_notional_proxy_sum_q0_wire':newsum,'clean_old_sum_notional_ratio':newsum/oldsum,'proxy_tp3_available':sum(bool(r['TP3_order_id']) for r in z),'U_proxy_ordered':sum(r['U_proxy_ordered'] is True for r in z),'U_proxy_fee_positive':sum(r['U_proxy_all_fee_positive'] is True for r in z)})
dumpcsv(OUT/'geometry-groups.csv',groups)
branch=[]
for side in ['LONG','SHORT']:
 for omitted in ['[]','[0]','[0,1]']:
  z=[r for r in rows if r['side']==side and r['omitted_zero_levels']==omitted]
  if z:branch.append({'side':side,'omitted_zero_levels':omitted,'n':len(z),'min_change_pct':min((r['clean_old_ratio_lot']-1)*100 for r in z),'max_change_pct':max((r['clean_old_ratio_lot']-1)*100 for r in z)})
dumpcsv(OUT/'geometry-branches.csv',branch)
known=[r for r in rows if r['TP3_order_id']]
summary={'kind':'FROZEN_ARCHIVED_ROW_DIAGNOSTIC_NOT_CANDIDATE_ECONOMICS','method':{'sizing':'floor_to_0.001(phi_side * archived_reference_btc_qty); archived q0 already quantity-rounded; exact native-equity N_plan unavailable','price_geometry':'side*(first archived TP3 LIMIT price / archived first-child VWAP - 1); TP3 submitted later than entry; raw d3 NOT_EXPORTED; this is rounded native-price proxy, not exact causal-d3 reconstruction','fees':'hypothetical first-entry taker .00055, TP maker .0002; positive-side tick rounding .1; no funding/slippage/queue/admission proof','year_split':'[2024-09-01,2025-09-01), [2025-09-01,2026-09-01), by first entry timestamp'},'n':len(rows),'groups':groups,'branch_groups':branch,'native_tp3_proxy_n':len(known),'missing_native_tp3_cycles':[r['cycle'] for r in rows if not r['TP3_order_id']],'U_proxy_min_d3':min(r['d3_native_price_proxy'] for r in known),'U_proxy_max_d3':max(r['d3_native_price_proxy'] for r in known),'U_proxy_min_fee_surplus_USDT_per_BTC':min(r['U_min_fee_surplus_USDT_per_BTC'] for r in known),'U_proxy_fee_positive_n':sum(r['U_proxy_all_fee_positive'] for r in known),'U_proxy_ordered_n':sum(r['U_proxy_ordered'] for r in known),'source_pins':{'reports_commit_requested':'f7587cd8e70609f71d95c38934dee490f4497cb4','E4_source_requested':'bd04c9b3858bcda40060a08eff488849c69af5d8','E4_config_requested':'ce7c101ace5d8c21f0a912a0cd3221659591e5d56b744d3f8dc5ecb7c01d2ef6','bars_blob_requested':'f2aafb8c784177e2606ed13cb11c409164f9aa9b'},'inputs':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in FILES+[SPEC]],'physical_full_runs':0,'missing_precheck_zip':'NOT_PRESENT_PER_PARENT; its stated metrics are unverified specification, not reproduced evidence','limitations':['No candidate TOTAL, PnL, DD or ROI computed. No native engine instantiated.','Clean quantity is proxy on archived gross Q and quotes: not a candidate replay, no endogenous equity/margin/admission, no exact pre-round N_plan.','Raw entry d3 is absent. 82 accepted TP3 LIMIT prices are used only as a proxy; 81 absent, no invented geometry.','Outward tick rounding assumption specified here is conservative for fees but execution implications untested.','No source/data/quote pins modified. No H1/M1 replay or target-crossing undertaken.','Archived full fallback does not alone imply nonzero raw TP1/TP2; branch count is distinct from old zero-target-distance count.']}
summary['manager_HEAD_at_analysis']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
summary['bars_current_git_blob']=subprocess.check_output(['git','hash-object',str(FILES[-1])],cwd=ROOT,text=True).strip()
summary['pin_comparison']=[]
for item in summary['inputs'][:-1]:
 rel=str(Path(item['path']).relative_to(ROOT))
 original=subprocess.run(['git','show',summary['source_pins']['reports_commit_requested']+':'+rel],cwd=ROOT,capture_output=True)
 original_sha=hashlib.sha256(original.stdout).hexdigest() if original.returncode==0 else None
 summary['pin_comparison'].append({'path':rel,'archive_commit':summary['source_pins']['reports_commit_requested'],'exists_in_archive_commit':original.returncode==0,'current_sha256':item['sha256'],'archive_sha256':original_sha,'equal_to_requested_report_pin':original_sha==item['sha256']})
assert all(x['equal_to_requested_report_pin'] for x in summary['pin_comparison'])
assert summary['bars_current_git_blob']==summary['source_pins']['bars_blob_requested']
(OUT/'geometry-summary.json').write_text(json.dumps(summary,indent=2,default=str)+'\n')
print(json.dumps({k:summary[k] for k in ['n','native_tp3_proxy_n','missing_native_tp3_cycles','U_proxy_min_d3','U_proxy_max_d3','U_proxy_min_fee_surplus_USDT_per_BTC','U_proxy_fee_positive_n','U_proxy_ordered_n']},indent=2,default=str)); print(json.dumps(groups,indent=2,default=str))
