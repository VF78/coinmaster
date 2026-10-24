#!/usr/bin/env python3
"""One saved native export/receipt pass; no new strategy or execution model."""
import csv,json,hashlib,gzip,subprocess,bisect,collections,statistics
from pathlib import Path
from decimal import Decimal as D,getcontext
from datetime import datetime,timezone
import pyarrow.parquet as pq
getcontext().prec=60
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent; B=ROOT/'reports/market-redesign-20261024';OLD=ROOT/'reports/b-50-90-next-20261023';INPUTS={}
def hashed(p,expected=None):
 p=Path(p);h=hashlib.sha256(p.read_bytes()).hexdigest();assert not expected or h==expected;INPUTS[str(p)]=h;return p
def load(p):return json.loads(hashed(p).read_text())
def read(p):
 with hashed(p).open() as f:return list(csv.DictReader(f))
def ns(s):return int(datetime.fromisoformat(s).timestamp())*10**9
def iso(t):return datetime.fromtimestamp(t/1e9,timezone.utc).isoformat()
def write(name,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with (OUT/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
freeze=load(B/'full-freeze.json');receipts={};raws={};fills={};tracepaths={};cycles={};sourcechecks={}
e=load(OLD/'owner-E4-receipt.json');receipts['E4']=e;raws['E4']=json.loads(hashed(e['raw_artifact'],e['raw_sha256']).read_text());fills['E4']=read(hashed(e['exports']['fills']['path'],e['exports']['fills']['sha256']));tracepaths['E4']=Path(e['settled_observer_coverage']['trace_path'])
for v in ['R1','R2','R3']:
 a=load(B/f'native-analysis-{v}.json');receipts[v]=a
 for p,h in a['input_sha256'].items():
  if p.endswith('-raw-native.json'):raws[v]=json.loads(hashed(p,h).read_text())
  elif p.endswith('-fills.csv'):fills[v]=read(hashed(p,h))
  elif p.endswith('receipts.csv.gz'):tracepaths[v]=hashed(p,h)
 cycles[v]=read(B/f'native-analysis-attribution-{v}-cycles.csv')
 assert len(cycles[v])==83
# Source + daily-history provenance only, no strategy import or recomputation.
for v,r in raws.items():
 assert r['config']['candidate']['wave_history_days']==730 and r['config']['candidate']['wave_min_count']==8 and r['config']['candidate']['wave_quantiles']==[.1,.3,.6]
 assert '2022-09-02' in r['warmup'];assert len(r['split_cover_audit']['parents'])==83
 rev=e['source_commit'] if v=='E4' else receipts[v]['source_commit_expected']
 for label,path in [('wave_domain','runtime/coinmaster/domain/wave_overlay.py'),('wave_strategy','runtime/coinmaster/strategy/wave_overlay.py')]:
  blob=subprocess.check_output(['git','show',f'{rev}:{path}']);assert hashlib.sha256(blob).hexdigest()==r['source_hashes'][label];sourcechecks[f'{rev}:{path}']=hashlib.sha256(blob).hexdigest()
for rel in ['normalized/bybit-BTCUSDT-daily.parquet','normalized/bybit-SOLUSDT-daily.parquet']:
 f=freeze['inputs'][rel];p=hashed(f['path'],f['sha256']);q=pq.ParquetFile(p);assert q.metadata.num_rows==1460
src=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/market-redesign-20261024/source-ec2a958')
md=hashed(src/'runtime/coinmaster/strategy/market_redesign.py');baseline=hashed(src/'runtime/coinmaster/research/native_baseline.py');domain=hashed(src/'runtime/coinmaster/domain/wave_overlay.py')
assert 'd3 = D(str(ep.wave_levels[2]))' in md.read_text() and 'P0_FROZEN_FIRST_TERMINAL' in md.read_text()
assert 'trading_start_ms - warmup_start_ms < 730 * DAY_MS' in baseline.read_text()
# Actual fills grouped into native BTC flat cycles. E4 needs its own table; R* table is cross-checked.
rows=[];sums=[];early=[]
for v in ['E4','R1','R2','R3']:
 r=raws[v];parents=r['split_cover_audit']['parents'];bytime=collections.defaultdict(list)
 for f in fills[v]:
  if f['instrument_id'].startswith('BTC'):bytime[ns(f['ts_last'])].append(f)
 q=D(0);observed=[];cur=None
 for t,fs in sorted(bytime.items()):
  for f in fs:
   signed=D(f['filled_qty'])*(1 if f['side']=='BUY' else -1)
   fee=sum((D(z.split()[0]) for z in __import__('ast').literal_eval(f['commissions'])),D(0));px=D(f['avg_px']).quantize(D('.1'))
   if not q:cur={'start_ns':t,'entry_qty':D(0),'entry_notional':D(0),'fill_cash':D(0),'fees':D(0),'first_exit_ns':None,'last_entry_ns':None,'last_fill_ns':None,'add_times':[],'entry_events':0,'exit_events':0};observed.append(cur)
   entry=q==0 or q*signed>0
   if entry:
    cur['entry_qty']+=abs(signed);cur['entry_notional']+=abs(signed)*px;cur['last_entry_ns']=t;cur['entry_events']+=1
    if t>cur['start_ns']:cur['add_times'].append(t)
   else:
    cur['first_exit_ns']=cur['first_exit_ns'] or t;cur['exit_events']+=1
   cur['fill_cash']-=signed*px;cur['fees']+=fee;cur['last_fill_ns']=t;old=q;q+=signed
   assert not old or not q or old*q>0
 assert q==0 and len(observed)==83
 assert [x['start_ns'] for x in observed]==[int(p['start_ns']) for p in parents]
 sizing={z['episode_id']:z for z in r['btc_sizing_audit'] if z['event']=='EPISODE_ENTRY_SIZING'};entrys={z['episode_id']:z for z in r['entry_sizing_audit']}
 md_events=r.get('market_redesign_audit',{}).get('events',[]);plans={z['episode_id']:z for z in md_events if z['event']=='PLAN'};p0events={z['episode_id']:z for z in md_events if z['event']=='P0_FROZEN_FIRST_TERMINAL'}
 vrows=[];q0lookup={}
 for i,(o,p) in enumerate(zip(observed,parents),1):
  s=sizing.get(p['episode_id'],{});a=entrys[p['episode_id']];q0=int(s['timestamp_ns'] if s else a['q0_ns']);planned=D(str(p['quantity']));firstplanned=D(str(p['first_quantity']));filled=D(str(p['filled']));ref=D(str(a.get('reference_btc_qty',p.get('planref_v1_gross_reference_qty'))));req=D(str(s['requested_notional'])) if s else None;m=D(str(s['frozen_multiplier'])) if s else None
  row={'variant':v,'cycle':i,'start_ns':o['start_ns'],'start_utc':iso(o['start_ns']),'side':int(p['side']),'decision_ns':q0,'requested_gross_budget':req if req is not None else 'UNKNOWN_NOT_EXPORTED_H4_REENTRY','multiplier':m if m is not None else 'UNKNOWN_NOT_EXPORTED_H4_REENTRY','own_equity_implied_by_uncapped_request':req/m if req is not None and req<D('30000000') else 'UNKNOWN_CAP_OR_UNEXPORTED_REQUEST','own_settled_equity_at_decision':'UNKNOWN','own_equity_first_fill_receipt':'UNKNOWN','planned_parent_qty':planned,'initial_child_planned_qty':firstplanned,'first_actual_qty':D(str(p['first_filled'])),'actual_filled_entry_qty':filled,'initial_planned_second_qty':planned-firstplanned,'terminal_parent_cancelled_qty':D(str(p.get('cancelled',0))),'pending_qty_time_series':'UNKNOWN_NOT_EXPORTED','reference_gross_qty':ref,'actual_filled_over_reference_qty':filled/ref,'actual_filled_over_parent_qty':filled/planned,'actual_entry_notional':o['entry_notional'],'actual_entry_notional_over_requested_gross':o['entry_notional']/req if req is not None else 'UNKNOWN_NOT_EXPORTED_H4_REENTRY','actual_fill_net_ex_funding':o['fill_cash']-o['fees'],'actual_fees':o['fees'],'signed_BTC_funding':'UNKNOWN_OLD_SIGNED_ASSET' if v=='E4' else D(cycles[v][i-1]['signed_funding']),'last_entry_ns':o['last_entry_ns'],'first_exit_ns':o['first_exit_ns'],'last_fill_ns':o['last_fill_ns'],'first_to_last_fill_hours':D(o['last_fill_ns']-o['start_ns'])/D('3600000000000'),'first_to_first_exit_hours':D(o['first_exit_ns']-o['start_ns'])/D('3600000000000'),'entry_events':o['entry_events'],'exit_events':o['exit_events'],'add_times_json':json.dumps(o['add_times']),'peak_BTC_mark_notional':D(0),'peak_portfolio_gross_mark_notional':D(0),'peak_BTC_mark_leverage_own_equity':D(0),'peak_portfolio_gross_leverage_own_equity':D(0),'sum_BTC_mark_notional_minutes':D(0),'actual_BTC_held_minutes':0,'raw_causal_d3':plans[p['episode_id']]['raw_causal_d3'] if p['episode_id'] in plans else 'UNKNOWN_NOT_EXPORTED','firstP0':str(p.get('planref_v1_p0',p.get('management_reference_v1','UNKNOWN'))),'completed_blended_VWAP':str(p.get('planref_v1_actual_blended_vwap','UNKNOWN')),'P0_frozen_event':p0events.get(p['episode_id'],{}).get('timestamp_ns','LEGACY_PARENT_METADATA')}
  if v!='E4':
   c=cycles[v][i-1];assert D(c['actual_entry_qty'])==filled and D(c['actual_entry_notional'])==o['entry_notional'];assert D(c['price_fill_net_ex_funding'])==row['actual_fill_net_ex_funding'];assert D(c['native_fees'])==o['fees']
  vrows.append(row);q0lookup[q0]=row
 # Single streaming trace pass, all peaks observed from native positions and own marked equity.
 starts=[x['start_ns'] for x in vrows];trace=hashed(tracepaths[v]);count=0
 with gzip.open(trace,'rt') as f:
  for z in csv.DictReader(f):
   t=int(z['source_quote_ns']);eq=D(z['paired_close_equity']);count+=1
   if t in q0lookup:q0lookup[t]['own_settled_equity_at_decision']=eq
   i=bisect.bisect_right(starts,t)-1
   if i<0:continue
   row=vrows[i]
   if t==row['start_ns']:row['own_equity_first_fill_receipt']=eq
   if t>=row['last_fill_ns'] or z['native_positions_and_mark_ohlc_json']=='[]':continue
   ps=json.loads(z['native_positions_and_mark_ohlc_json']);btc=D(0);gross=D(0)
   for p in ps:
    notional=abs(D(p['quantity']))*D(p['mark_ohlc']['close']);gross+=notional
    if p['instrument_id'].startswith('BTC'):btc+=notional
   if btc:
    row['actual_BTC_held_minutes']+=1;row['sum_BTC_mark_notional_minutes']+=btc;row['peak_BTC_mark_notional']=max(row['peak_BTC_mark_notional'],btc);row['peak_portfolio_gross_mark_notional']=max(row['peak_portfolio_gross_mark_notional'],gross)
    if eq>0:row['peak_BTC_mark_leverage_own_equity']=max(row['peak_BTC_mark_leverage_own_equity'],btc/eq);row['peak_portfolio_gross_leverage_own_equity']=max(row['peak_portfolio_gross_leverage_own_equity'],gross/eq)
 assert count==1051199
 for row in vrows:
  if row['actual_BTC_held_minutes']:row['mean_BTC_mark_notional_while_held']=row['sum_BTC_mark_notional_minutes']/row['actual_BTC_held_minutes']
  eq=row['own_settled_equity_at_decision'];row['actual_entry_notional_over_own_decision_equity']=row['actual_entry_notional']/eq if isinstance(eq,D) and eq else 'UNKNOWN'
 rows+=vrows
 for cohort in ['all','first_year','second_year']:
  cr=[x for x in vrows if cohort=='all' or (x['start_ns']<1756684800000000000)==(cohort=='first_year')]
  sums.append({'variant':v,'cohort':cohort,'parents':len(cr),'BTC_fill_net_ex_funding':sum(x['actual_fill_net_ex_funding'] for x in cr),'BTC_fees':sum(x['actual_fees'] for x in cr),'BTC_signed_funding':'UNKNOWN' if v=='E4' else sum(x['signed_BTC_funding'] for x in cr),'entry_notional_sum':sum(x['actual_entry_notional'] for x in cr),'requested_gross_known_parents':sum(isinstance(x['requested_gross_budget'],D) for x in cr),'mean_entered_over_requested_gross_known_only':sum(x['actual_entry_notional_over_requested_gross'] for x in cr if isinstance(x['actual_entry_notional_over_requested_gross'],D))/sum(isinstance(x['actual_entry_notional_over_requested_gross'],D) for x in cr),'mean_filled_over_reference_qty':sum(x['actual_filled_over_reference_qty'] for x in cr)/len(cr),'mean_entry_notional_over_own_equity':sum(x['actual_entry_notional_over_own_decision_equity'] for x in cr)/len(cr),'equal_parent_mean_net_bp':sum(x['actual_fill_net_ex_funding']/x['actual_entry_notional']*10000 for x in cr)/len(cr),'BTC_held_minutes':sum(x['actual_BTC_held_minutes'] for x in cr),'mean_cycle_hours':sum(x['first_to_last_fill_hours'] for x in cr)/len(cr),'peak_BTC_leverage':max(x['peak_BTC_mark_leverage_own_equity'] for x in cr)})
 for row in vrows[:20]:early.append({k:row[k] for k in ['variant','cycle','start_utc','own_settled_equity_at_decision','own_equity_implied_by_uncapped_request','requested_gross_budget','actual_entry_notional','actual_fill_net_ex_funding','actual_fees','signed_BTC_funding']})
 print(v,'83 parents trace PASS',flush=True)
# Matched outcomes diagnostic only, no selection gate.
byv={v:[r for r in rows if r['variant']==v] for v in ['E4','R1','R2','R3']};comparison=[]
for i in range(83):
 ref=byv['E4'][i]
 for v in ['R1','R2','R3']:
  z=byv[v][i];assert z['start_ns']==ref['start_ns'] and z['side']==ref['side']
  comparison.append({'cycle':i+1,'variant':v,'E4_outcome_diagnostic':'WIN' if ref['actual_fill_net_ex_funding']>0 else 'LOSS','actual_qty_ratio_to_E4':z['actual_filled_entry_qty']/ref['actual_filled_entry_qty'],'own_equity_ratio_to_E4':z['own_settled_equity_at_decision']/ref['own_settled_equity_at_decision'],'entry_notional_over_gross_delta':z['actual_entry_notional_over_requested_gross']-ref['actual_entry_notional_over_requested_gross'] if isinstance(z['actual_entry_notional_over_requested_gross'],D) and isinstance(ref['actual_entry_notional_over_requested_gross'],D) else 'UNKNOWN_H4_REQUEST_NOT_EXPORTED','net_bp_delta':10000*(z['actual_fill_net_ex_funding']/z['actual_entry_notional']-ref['actual_fill_net_ex_funding']/ref['actual_entry_notional']),'actual_fillnet_USDT_delta':z['actual_fill_net_ex_funding']-ref['actual_fill_net_ex_funding']})
for i in range(83):assert byv['R2'][i]['raw_causal_d3']==byv['R3'][i]['raw_causal_d3']
write('btc-participation-parents.csv',rows);write('btc-participation-summary.csv',sums);write('btc-participation-early-capital.csv',early);write('btc-participation-matched-diagnostics.csv',comparison)
meta={'status':'A_NO_GO_NO_NEW_SUPPORTED_PARTICIPATION_MECHANISM','H_PAIR_EXIT_admitted':False,'engine_attempts':0,'simulator_reruns':0,'training':0,'trace_passes':4,'metadata_correction_before_first_trace_pass':'29 H4 reentries per variant lack EPISODE_ENTRY_SIZING audit; requested gross/multiplier remain UNKNOWN, q0 from actual entry audit; no invented exact request','physical_attempt_budget':0,'matched_parents_each':83,'decision_equity_known':sum(isinstance(x['own_settled_equity_at_decision'],D) for x in rows),'R2_R3_d3_equal_count':83,'native_history':'730 feature-only days2022-09-02..2024-09-01,1460dailyrows, wavehistory730/min8/q60; no demonstrated short warmup','native_TP_anchor':'first-child actual VWAP frozen at firstterminal, later second-child blended VWAP not TP anchor; no demonstrated substitution','pending_timeline':'UNKNOWN_NOT_EXPORTED; initial planned second and terminal cancelled quantities actual metadata','input_sha256':INPUTS,'pinned_source_sha256':sourcechecks,'verdict':'No new supported restoration source. Reverting native warmup/P0 or restoring zeroTP gross-Q selector is not a new admissible hypothesis. Strict-hedge early capital restoration remains unproven.','limitations':['Own decision equity is coherent settled source quote, not presumed exact callback-instant sizing equity; uncapped requested/M is independently recorded, cap-bound exact sizing equity UNKNOWN.','Peak leverage/notional uses observed raw minute markclose and native equity, not intraminute/native-price-rounded guarantee. E4 portfolio gross peak here only while BTCheld.','No pending-order timeline reconstructed from terminal snapshots.','E4 perasset signed funding UNKNOWN; do not infer from cash residual.','Winner/loser matching only ex-post outcome diagnostics; no old qty/equity imported or counterfactual TOTAL constructed.']}
(OUT/'btc-participation-verification.json').write_text(json.dumps(meta,indent=2,default=str)+'\n')
print(json.dumps({'summary':sums,'metadata':{k:v for k,v in meta.items() if k not in ['input_sha256','pinned_source_sha256']}},indent=2,default=str))
