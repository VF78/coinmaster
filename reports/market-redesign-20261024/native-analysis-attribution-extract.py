#!/usr/bin/env python3
"""Actual native export attribution only. No engine, simulator or launcher imports."""
import argparse,bisect,collections,csv,gzip,hashlib,json,math,sqlite3
from pathlib import Path
from decimal import Decimal as D,localcontext
from datetime import datetime,timezone
OUT=Path(__file__).resolve().parent;MIN=60_000_000_000
UTC=timezone.utc

def read(p):return json.loads(Path(p).read_text())
def csvread(p):
 with Path(p).open(newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ns(s):return int(datetime.fromisoformat(s).timestamp())*10**9
def iso(t):return datetime.fromtimestamp(int(t)/1e9,UTC).isoformat()
def csvwrite(path,rs):
 if not rs:return
 fields=list(dict.fromkeys(k for r in rs for k in r))
 with path.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rs)
def key(a):return str(a['submit_ns']),a['instrument'],str(a.get('reason','')),str(a.get('level',''))
def sidesigned(side):
 if str(side) in ['BUY','LONG','2']:return D(1)
 if str(side) in ['SELL','SHORT','3']:return D(-1)
 raise ValueError('Unknown actual native side '+str(side))
def main(args):
 accepted=read(args.acceptance or OUT/f'native-analysis-{args.variant}.json')
 assert accepted['row']['status']=='VALIDATED_FULL_NATIVE' and accepted['row']['mechanical_and_cash_acceptance'] is True,'Require root-accepted completed native outputs first'
 ap=Path(args.artifact).resolve();rawp=Path(args.raw).resolve() if args.raw else ap.with_name(ap.stem+'-raw-native.json');x=read(ap);raw=read(rawp)
 assert accepted['input_sha256'].get(str(ap))==sha(ap) and accepted['input_sha256'].get(str(rawp))==sha(rawp)
 inputs={str(ap):sha(ap),str(rawp):sha(rawp)}
 orderspath=Path(x['execution_artifacts']['orders']['path']);assert sha(orderspath)==accepted['input_sha256'][str(orderspath)]==x['execution_artifacts']['orders']['sha256'];inputs[str(orderspath)]=sha(orderspath)
 orders=csvread(orderspath);events=raw['native_order_events'];aud=raw['fill_audit'];parents=sorted(x['split_cover_audit']['parents'],key=lambda p:int(p['start_ns']));starts=[int(p['start_ns']) for p in parents];assert len(set(starts))==len(starts)
 grouped=collections.defaultdict(list)
 for o in orders:
  if D(o['filled_qty'])>0:grouped[key(events[o['client_order_id']])].append(o)
 fills=[]
 for a in aud:
  os=grouped[key(a)];ss={o['side'] for o in os};assert len(ss)==1,'Ambiguous order-side group'
  v=dict(a);v['sign']=sidesigned(next(iter(ss)));v['quantity']=D(a['qty']);v['pricecash']=-v['sign']*D(a['qty'])*D(a['px']);v['fee']=D(a['commission']);v['t']=int(a['fill_ns']);fills.append(v)
 assert all(a['t']<=b['t'] for a,b in zip(fills,fills[1:])),'Actual fill_epoch needs original chronological audit order'
 for k,os in grouped.items():assert sum((D(o['filled_qty']) for o in os),D(0))==sum((D(a['qty']) for a in aud if key(a)==k),D(0))
 journal=Path(x['funding_journal']);assert sha(journal)==accepted['input_sha256'][str(journal)];assert not (Path(str(journal)+'-wal').exists() and Path(str(journal)+'-wal').stat().st_size)
 c=sqlite3.connect(journal.as_uri()+'?mode=ro&immutable=1',uri=True);fd=c.execute('SELECT event_id,instrument_id,ts_event,before_total,after_total,signed_delta FROM funding_cash ORDER BY ts_event,event_id').fetchall();c.close()
 assert collections.Counter(fd)==collections.Counter(tuple(v) for v in raw['funding']['signed_native_cash_deltas']);inputs[str(journal)]=sha(journal)
 fundtimes=[r[2] for r in fd];assets=sorted({a['instrument'] for a in fills}|{r[1] for r in fd});start=ns(x['run_interval']['start']);end=ns(x['run_interval']['end_exclusive']);cut=ns('2025-09-01T00:00:00+00:00');seed=D(x['run_interval']['initial_active_seed']);total=D(x['terminal_total']);assert D(x['terminal_reserve'])==0,'Nonzero reserve requires separately observed per-receipt reserve path; do not infer'
 # Prefixes are actual observations, not hypothetical order/position simulation.
 fp=[{s:{'qty':D(0),'pricecash':D(0),'fees':D(0)} for s in assets}]
 for a in fills:
  p={s:dict(v) for s,v in fp[-1].items()};v=p[a['instrument']];v['qty']+=a['sign']*a['quantity'];v['pricecash']+=a['pricecash'];v['fees']+=a['fee'];fp.append(p)
 fundprefix=[{s:D(0) for s in assets}]
 for r in fd:
  assert D(r[4])-D(r[3])==D(r[5]);p=dict(fundprefix[-1]);p[r[1]]+=D(r[5]);fundprefix.append(p)
 cycles=[];cyclefund=collections.defaultdict(lambda:D(0));unallocatedfund=[]
 for r in fd:
  i=bisect.bisect_right(starts,r[2])-1
  if i<0:unallocatedfund.append(r);continue
  cyclefund[i]+=D(r[5])
 for i,parent in enumerate(parents):
  lo=starts[i];hi=starts[i+1] if i+1<len(starts) else end+1;fs=[a for a in fills if lo<=a['t']<hi];q=collections.defaultdict(lambda:D(0));sign=int(parent['side']);entries=[a for a in fs if a['action']=='BTC_ENTRY'];assert entries
  firstsubmit=min(int(a['submit_ns']) for a in entries);first=[a for a in entries if int(a['submit_ns'])==firstsubmit];second=[a for a in entries if int(a['submit_ns'])!=firstsubmit]
  for a in fs:
   q[a['instrument']]+=a['sign']*a['quantity']
   if a['instrument'].startswith('BTC'):assert not q[a['instrument']] or (q[a['instrument']]>0)==(sign>0),'Inventory overlaps/flips parent'
  assert all(v==0 for v in q.values()),'Nonflat cycle boundary; attribution would require explicit inventory endpoints'
  notional=sum((a['quantity']*D(a['px']) for a in entries),D(0));price=sum((a['pricecash'] for a in fs),D(0));fee=sum((a['fee'] for a in fs),D(0));fund=cyclefund[i];net=price-fee+fund
  exits=collections.Counter(a['reason'] for a in fs if a['action']!='BTC_ENTRY');entryorderids=[o['client_order_id'] for o in orders if events[o['client_order_id']]['action']=='BTC_ENTRY' and lo<=int(events[o['client_order_id']]['submit_ns'])<hi and D(o['filled_qty'])>0]
  v={'variant':args.variant,'cycle':i+1,'episode_id':parent['episode_id'],'start_ns':lo,'start_utc':iso(lo),'native_last_fill_ns':max(a['t'] for a in fs),'side':sign,'year_cohort':'first_year' if lo<cut else 'second_year','actual_entry_notional':str(notional),'actual_entry_qty':str(sum((a['quantity'] for a in entries),D(0))),'first_qty':str(sum((a['quantity'] for a in first),D(0))),'second_qty':str(sum((a['quantity'] for a in second),D(0))),'entry_fill_events':len(entries),'actual_filled_entry_orders':len(entryorderids),'first_fill_events':len(first),'second_fill_events':len(second),'price_PNL_actual_flat_cashflows':str(price),'native_fees':str(fee),'price_fill_net_ex_funding':str(price-fee),'signed_funding':str(fund),'net_including_funding':str(net),'net_bp_actual_entry_notional':str(net/notional*10000),'exit_reasons_json':json.dumps(exits,sort_keys=True),'parent_completion_reason':parent.get('completion_reason',''),'parent_fallback_observed':parent.get('fallback'),'actual_TP1_qty':str(sum((a['quantity'] for a in fs if a['reason']=='BTC_TP1'),D(0))),'actual_TP2_qty':str(sum((a['quantity'] for a in fs if a['reason']=='BTC_TP2'),D(0))),'actual_TP3_qty':str(sum((a['quantity'] for a in fs if a['reason']=='BTC_TP3'),D(0)))}
  for s in assets:
   z=[a for a in fs if a['instrument']==s];v[s+'_price_PNL']=str(sum((a['pricecash'] for a in z),D(0)));v[s+'_fees']=str(sum((a['fee'] for a in z),D(0)))
  cycles.append(v)
 assert not unallocatedfund and sum(len([a for a in fills if starts[i]<=a['t']<(starts[i+1] if i+1<len(starts) else end+1)]) for i in range(len(starts)))==len(fills)
 # Predeclared reporting windows, never online trading rules. Ends include requested full final date.
 windows=[('FULL_PERIOD',start,end,'full'),('YEAR_1_MARKED',start,cut,'year'),('YEAR_2_MARKED',cut,end,'year')]
 owner=[('OWNER_03OCT2024','2024-10-03','2024-10-04'),('OWNER_13JAN2025','2025-01-13','2025-01-14'),('OWNER_11APR_06JUN2025','2025-04-11','2025-06-07'),('OWNER_22OCT_28NOV2025','2025-10-22','2025-11-29'),('OWNER_08FEB2026','2026-02-08','2026-02-09'),('OWNER_JUL_AUG2026','2026-07-01','2026-09-01')]
 for label,a,b in owner:windows.append((label,ns(a+'T00:00:00+00:00'),ns(b+'T00:00:00+00:00'),'owner_fixed'))
 catalog=OUT.parent/'b-50-90-next-20261023/verifier-E4-DD-ge30-episodes.csv';inputs[str(catalog)]=sha(catalog)
 for i,r in enumerate(csvread(catalog),1):
  windows.append((f'E4_REFERENCE_DD{i}_PEAK_TROUGH',ns(r['peak_utc']),ns(r['trough_utc']),'old_E4_fixed'))
  if r['recovery_utc']:windows.append((f'E4_REFERENCE_DD{i}_PEAK_RECOVERY',ns(r['peak_utc']),ns(r['recovery_utc']),'old_E4_fixed'))
 targets=sorted({t for _,a,b,_ in windows for t in [a,b]});selected={};ti=0
 initial={'source_quote_ns':str(start),'receipt_ns':str(start),'fill_epoch':'0','cash':str(seed),'paired_close_equity':str(seed),'native_positions_and_mark_ohlc_json':'[]','endpoint_kind':'ACTUAL_INITIAL_SEED'}
 terminal={'source_quote_ns':str(end),'receipt_ns':str(end),'fill_epoch':str(len(fills)),'cash':str(total),'paired_close_equity':str(total),'native_positions_and_mark_ohlc_json':'[]','endpoint_kind':'ACTUAL_TERMINAL_FLAT_CASH'}
 prev=initial;peak=initial;trough=initial;dd=D(0);excursions=[];count=0;lastsource=None;last_epoch=0;max_epoch=0;filltimes=[a['t'] for a in fills]
 def consume(r):
  nonlocal peak,trough,dd
  eq=D(r['paired_close_equity']);pe=D(peak['paired_close_equity'])
  if eq>=pe:
   if dd>=30:excursions.append({'peak':peak,'trough':trough,'recovery':r,'DD_percent':str(dd)})
   peak=r;trough=r;dd=D(0)
  else:
   d=(pe-eq)/pe*100
   if d>dd:dd=d;trough=r
 trace=Path(x['minute_risk_observations']['settled_native_close_receipts']['trace_path']);inputs[str(trace)]=sha(trace);assert sha(trace)==accepted['input_sha256'][str(trace)]
 with gzip.open(trace,'rt') as f:
  for r in csv.DictReader(f):
   count+=1;rt=int(r['receipt_ns']);st=int(r['source_quote_ns']);assert st==start+count*MIN;lastsource=st
   epoch=int(r['fill_epoch']);assert last_epoch<=epoch<=len(fills) and epoch==bisect.bisect_right(filltimes,st),'fill_epoch not equal to actual audit fill count through causal source timestamp';last_epoch=epoch;max_epoch=max(max_epoch,epoch)
   while ti<len(targets) and targets[ti]<rt:selected[targets[ti]]=prev;ti+=1
   while ti<len(targets) and targets[ti]==rt:selected[targets[ti]]=r;ti+=1
   consume(r);prev=r
 assert count==1051199 and lastsource==end-MIN
 consume(terminal)
 if dd>=30:excursions.append({'peak':peak,'trough':trough,'recovery':None,'DD_percent':str(dd)})
 while ti<len(targets):selected[targets[ti]]=terminal if targets[ti]==end else prev;ti+=1
 selected[start]=initial;selected[end]=terminal
 def snapshot(r):
  epoch=int(r['fill_epoch']);assert 0<=epoch<=len(fills);mv={s:D(0) for s in assets};qty={s:D(0) for s in assets}
  for p in json.loads(r['native_positions_and_mark_ohlc_json']):
   sym=p['instrument_id'];q=sidesigned(p['side'])*D(p['quantity']);qty[sym]=qty.get(sym,D(0))+q;mv[sym]=mv.get(sym,D(0))+q*D(p['mark_ohlc']['close'])
  assert all(qty.get(s,D(0))==v['qty'] for s,v in fp[epoch].items()),'Native snapshot inventory disagrees with actual observed fill_epoch prefix'
  rt=int(r['receipt_ns']);terminalpoint=r.get('endpoint_kind')=='ACTUAL_TERMINAL_FLAT_CASH';fi=len(fd) if terminalpoint else bisect.bisect_left(fundtimes,rt);ties=[] if terminalpoint else [v[0] for v in fd if v[2]==rt]
  return {'r':r,'epoch':epoch,'mv':mv,'qty':qty,'fund':fundprefix[fi],'fund_ties':ties}
 def attribute(label,a,b,kind,requested_a=None,requested_b=None):
  A=snapshot(a);B=snapshot(b);change=D(b['paired_close_equity'])-D(a['paired_close_equity']);pred=D(0);v={'variant':args.variant,'window':label,'kind':kind,'requested_start_utc':iso(requested_a) if requested_a is not None else iso(a['receipt_ns']),'requested_end_utc':iso(requested_b) if requested_b is not None else iso(b['receipt_ns']),'actual_start_source_quote_ns':a['source_quote_ns'],'actual_start_receipt_ns':a['receipt_ns'],'actual_end_source_quote_ns':b['source_quote_ns'],'actual_end_receipt_ns':b['receipt_ns'],'start_fill_epoch':A['epoch'],'end_fill_epoch':B['epoch'],'start_marked_TOTAL':a['paired_close_equity'],'end_marked_TOTAL':b['paired_close_equity'],'marked_TOTAL_change':str(change),'marked_return_percent':str((D(b['paired_close_equity'])/D(a['paired_close_equity'])-1)*100),'endpoint_funding_exact_timestamp_ties':json.dumps(A['fund_ties']+B['fund_ties'])}
  for s in assets:
   flow=fp[B['epoch']][s]['pricecash']-fp[A['epoch']][s]['pricecash'];mvd=B['mv'].get(s,D(0))-A['mv'].get(s,D(0));fees=fp[B['epoch']][s]['fees']-fp[A['epoch']][s]['fees'];fund=B['fund'][s]-A['fund'][s];price=flow+mvd;pred+=price-fees+fund
   for k,val in [('signed_mark_inventory_value_change',mvd),('executed_fill_price_cashflow',flow),('marked_price_PNL',price),('native_fees',fees),('signed_funding',fund)]:v[s+'_'+k]=str(val)
  residual=change-pred;v['independent_sum_price_minus_fees_plus_funding']=str(pred);v['rounding_timing_residual_observed_minus_components']=str(residual)
  # Native observer rounds raw close through actual instrument.make_price;
  # native-rounded close itself is not exported. Retain raw mark arithmetic.
  ticks={s:D('.1') if s.startswith('BTCUSDT') else D('.01') if s.startswith('SOLUSDT') else None for s in assets}
  rounding_bound=sum(((abs(A['qty'].get(s,D(0)))+abs(B['qty'].get(s,D(0))))*tick for s,tick in ticks.items() if tick is not None),D(0))+D('.00000001')*(B['epoch']-A['epoch']+1)
  v['conservative_unexported_native_mark_rounding_bound_USDT']=str(rounding_bound)
  v['attribution_status']='ENDPOINT_FUNDING_ORDER_UNKNOWN_STRICT_LT_CONVENTION' if A['fund_ties'] or B['fund_ties'] else 'RECONCILED_WITH_EXPLICIT_NATIVE_ROUNDING' if abs(residual)<=D('.00001') else 'CONSISTENT_WITH_UNEXPORTED_NATIVE_MARK_ROUNDING_NOT_EXACTLY_RECONCILED' if all(t is not None for t in ticks.values()) and abs(residual)<=rounding_bound else 'UNEXPLAINED_ROUNDING_TIMING_RESIDUAL'
  return v
 windowrows=[attribute(label,selected[a],selected[b],kind,a,b) for label,a,b,kind in windows];ddrows=[]
 for i,e in enumerate(excursions,1):
  v=attribute(f'ACTUAL_DD{i}_PEAK_TROUGH',e['peak'],e['trough'],'actual_DD_ge30');v['DD_percent']=e['DD_percent'];v['recovery_receipt_ns']=e['recovery']['receipt_ns'] if e['recovery'] else '';ddrows.append(v)
 cohort=[]
 for period in ['all','first_year','second_year']:
  z=[c for c in cycles if period=='all' or c['year_cohort']==period];ordered=sorted(z,key=lambda c:D(c['net_bp_actual_entry_notional']));k=math.ceil(len(z)*.1)
  for name,zz in [('all_cycles',z),('worst_ceil10pct',ordered[:k]),('worst_cycle',ordered[:1])]:
   if not zz:continue
   cohort.append({'variant':args.variant,'cohort':period,'selection':name,'n_cycles':len(zz),'cycle_ids':','.join(str(c['cycle']) for c in zz),'equal_notional_mean_net_bp':str(sum((D(c['net_bp_actual_entry_notional']) for c in zz),D(0))/len(zz)),'actual_net_USDT':str(sum((D(c['net_including_funding']) for c in zz),D(0))),'actual_price_fill_net_ex_funding':str(sum((D(c['price_fill_net_ex_funding']) for c in zz),D(0))),'signed_funding':str(sum((D(c['signed_funding']) for c in zz),D(0)))})
 matches=[]
 if args.reference_cycles:
  inputs[str(Path(args.reference_cycles).resolve())]=sha(args.reference_cycles);ref=csvread(args.reference_cycles);refby={(c['start_ns'],c['side']):c for c in ref};used=set()
  for c in cycles:
   r=refby.get((str(c['start_ns']),str(c['side'])));v={'variant':args.variant,'cycle':c['cycle'],'start_ns':c['start_ns'],'side':c['side'],'match':'COMMON_START_SIDE' if r else 'CANDIDATE_ONLY'}
   if r:
    used.add((r['start_ns'],r['side']));v['reference_cycle']=r['cycle']
    for k in ['actual_entry_notional','actual_entry_qty','first_qty','second_qty','actual_TP1_qty','actual_TP2_qty','actual_TP3_qty','net_including_funding','net_bp_actual_entry_notional']:v[k+'_observed_delta']=str(D(c[k])-D(r[k]))
    v['candidate_exit_reasons']=c['exit_reasons_json'];v['reference_exit_reasons']=r['exit_reasons_json']
   matches.append(v)
  for r in ref:
   if (r['start_ns'],r['side']) not in used:matches.append({'variant':args.variant,'reference_cycle':r['cycle'],'start_ns':r['start_ns'],'side':r['side'],'match':'REFERENCE_ONLY'})
 archivepath=OUT.parent/'b-50-90-next-20261023/owner-E4-events/split-parent-audit.csv';inputs[str(archivepath)]=sha(archivepath);archived=csvread(archivepath);archby={(r['start_ns'],r['side']):r for r in archived}
 for c in cycles:
  r=archby.get((str(c['start_ns']),str(c['side'])));c['archived_E4_common_start_side']=bool(r)
  if r:
   c['archived_E4_planned_qty']=r['quantity'];c['archived_E4_actual_filled_qty']=r['filled'];c['archived_E4_first_qty']=r['first_filled'];c['archived_E4_completion_reason']=r['completion_reason'];c['candidate_vs_archived_E4_actual_entry_qty_ratio']=str(D(c['actual_entry_qty'])/D(r['filled']))
 net=sum((D(c['net_including_funding']) for c in cycles),D(0));residual=(total-seed)-net;full=next(w for w in windowrows if w['window']=='FULL_PERIOD');tol=max(D('.000001'),D('.00000001')*(len(aud)+1));assert abs(residual)<=tol and abs(D(full['rounding_timing_residual_observed_minus_components']))<=tol
 prefix=OUT/args.output_prefix;assert args.output_prefix.startswith('native-analysis-attribution-') and Path(args.output_prefix).name==args.output_prefix
 for suffix,data in [('cycles',cycles),('cohorts',cohort),('windows',windowrows),('DDge30',ddrows),('common-parent-observations',matches)]:csvwrite(Path(str(prefix)+'-'+suffix+'.csv'),data)
 meta={'variant':args.variant,'status':'ACTUAL_NATIVE_FACTS_WITH_EXPLICIT_RESIDUALS_NO_COUNTERFACTUAL_DECOMPOSITION','actual_parent_cycles':len(cycles),'cycle_boundary_flat_no_overlap':True,'actual_fill_events':len(fills),'maximum_trace_fill_epoch':max_epoch,'actual_terminal_fill_epoch':len(fills),'fill_epoch_verified_each_receipt':'equals count(actual_fill_audit timestamps<=source_quote_ns),monotonic,bounded; endpoint inventory exact','cycle_net_sum':str(net),'native_TOTAL_minus_seed':str(total-seed),'native_minus_cycle_sum_rounding_residual':str(residual),'reconciliation_tolerance_USDT':str(tol),'full_window_residual':full['rounding_timing_residual_observed_minus_components'],'settled_receipts':count,'actual_DDge30_excursions':len(ddrows),'fixed_reporting_windows':len(windowrows),'window_attribution_status_counts':dict(collections.Counter(w['attribution_status'] for w in windowrows+ddrows)),'archived_E4_common_parent_start_side':sum(c['archived_E4_common_start_side'] for c in cycles),'reference_observed_matches':dict(collections.Counter(r['match'] for r in matches)),'input_sha256':inputs,'engine_launches':0,'funding_endpoint_convention':'Actual terminal includes all persisted actual cash deltas; interior snapshots include funding events timestamp strictly<actualreceipt_ns, exact ties explicit UNKNOWNtiming; never residual-assigned','bounds':'As-of actual receipt<=requested UTC boundary, source_quote_ns retained; window fillflow exact observed fill_epoch prefix difference','limitations':['No counterfactual PNL or causal decomposition of compounding/TP/second entry/size; common timing deltas are observed comparisons only.','Year marked returns and entry-year cycle cohorts are different measurements; cycles spanning year are not force-split into trade cohorts.','Actual DD excursions use complete settled-grid highwater/maximumtrough/untilrecovery; intraminute and L2 unknown.','All reported prices/quantities/nativecash/funding are actual archived outputs; no new simulator.','Nonzero reserve path not supported without actual per-receipt reserve; script stops.','E4 timing/size reference only; old signed funding remains UNKNOWN, no rerun or optional invented attribution.','Interior asset marked pricePNL uses exported raw markclose; native observer uses instrument.make_price(close). Unexported native-rounded close can leave a bounded explicitly retained attribution residual, not funding/cash bridge; BTCtick0.1/SOLtick0.01 from frozen native_fixture.py.']}
 Path(str(prefix)+'.json').write_text(json.dumps(meta,indent=2)+'\n');print(json.dumps(meta,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--artifact',required=True);p.add_argument('--raw');p.add_argument('--variant',choices=['R1','R2','R3'],required=True);p.add_argument('--acceptance');p.add_argument('--reference-cycles');p.add_argument('--output-prefix',required=True);a=p.parse_args()
 with localcontext() as ctx:ctx.prec=60;main(a)
