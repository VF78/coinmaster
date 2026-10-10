"""Bounded read-only attribution from saved native observations; no simulation."""
import bisect,csv,gzip,json,sys
from collections import defaultdict
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
sys.path.insert(0,str(Path('runtime').resolve()))
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
base=Path('reports/selective-lifecycle-cap30m-113');out=base/'drawdown-causes'
r=json.load(gzip.open(base/'native-result.json.gz','rt'))
previous=json.load((base/'audit/findings.json').open())['variant']
risk=json.load((base/'minute-risk-audit/replay-analysis.json').open())
trace=Path(risk['trace_artifact']['path'])
exits=list(csv.DictReader((base/'audit/economics.csv').open()))
nativefills=list(csv.DictReader(Path(r['execution_artifacts']['fills']['path']).open()))
native_by_id={x['client_order_id']:x for x in nativefills}
entries=[f for f in r['fill_audit'] if f['action']=='BTC_ENTRY'];parentstarts=[int(f['fill_ns']) for f in entries]
def utc(ns):return datetime.fromtimestamp(int(ns)//1_000_000_000,timezone.utc).isoformat()
def total(rows,key):return sum((D(x[key]) for x in rows),D(0))
def pid(ns):return bisect.bisect_right(parentstarts,int(ns))
fees=total(r['fill_audit'],'commission'); assert fees==D(r['native_fees']); assert abs(fees-total(exits,'fees'))<D('0.00000001')
assert abs(total(exits,'net')-D(previous['fill_attribution_net']))<D('0.00000001')
assert len(previous['episodes']['BTC'])==len(entries)
assert all(int(e['start_ns'])==parentstarts[i] for i,e in enumerate(previous['episodes']['BTC']))
by_reason=defaultdict(list); groups=defaultdict(list)
for x in exits:
 by_reason[(x['sym'],x['reason'])].append(x)
 groups[(pid(x['ns']),x['reason'])].append(x)
reason_stats=[]
for (sym,reason),rows in sorted(by_reason.items()):
 losses=[x for x in rows if D(x['net'])<0]; grossloss=[x for x in rows if D(x['gross'])<0]
 reason_stats.append({'symbol':sym,'reason':reason,'closing_fill_rows':len(rows),'unique_native_orders':len({x['id'] for x in rows}),'logical_parent_reason_groups':len({pid(x['ns']) for x in rows}),'gross':str(total(rows,'gross')),'allocated_entry_fees':str(total(rows,'entry_fee_alloc')),'exit_fees':str(total(rows,'exit_fee')),'net_ex_funding':str(total(rows,'net')),'net_losing_fill_rows':len(losses),'net_winning_fill_rows':sum(D(x['net'])>0 for x in rows),'gross_losing_fill_rows':len(grossloss),'gross_losses_sum':str(total(grossloss,'gross')),'net_losses_sum':str(total(losses,'net')),'fee_negative_positive_gross_rows':sum(D(x['gross'])>0 and D(x['net'])<0 for x in rows)})
logical=[]
for (parent,reason),rows in sorted(groups.items()):
 legstats={}
 for sym in ('BTC','SOL'):
  leg=[x for x in rows if x['sym']==sym]
  if leg:legstats[sym]={'fill_rows':len(leg),'unique_native_orders':len({x['id'] for x in leg}),'qty':str(total(leg,'qty')),'gross':str(total(leg,'gross')),'allocated_entry_fees':str(total(leg,'entry_fee_alloc')),'exit_fees':str(total(leg,'exit_fee')),'net_ex_funding':str(total(leg,'net')),'order_ids':[x['id'] for x in leg]}
 logical.append({'parent_entry_number':parent,'parent_entry_utc':utc(parentstarts[parent-1]),'reason':reason,'first_fill_utc':utc(min(int(x['ns']) for x in rows)),'last_fill_utc':utc(max(int(x['ns']) for x in rows)),'net_ex_funding':str(total(rows,'net')),'gross':str(total(rows,'gross')),'fees':str(total(rows,'fees')),'legs':legstats})
# Preserve native PnL endpoints. Close contributions are an explicitly labeled
# interpolation attribution at native instrument-rounded marks, not trade PnL.
def snapshot(row):
 details=json.loads(row['native_positions_and_mark_ohlc_json']); parts=[]
 for item in details:
  symbol='BTC' if item['instrument_id'].startswith('BTC') else 'SOL';inst=BTC_PERP if symbol=='BTC' else SOL_PERP
  bar=item['mark_ohlc']; lo,hi,cl=(inst.make_price(D(bar[k])).as_decimal() for k in ('low','high','close'))
  lp,hp=D(item['low_native_pnl']),D(item['high_native_pnl'])
  pnl=lp if hi==lo else lp+(cl-lo)/(hi-lo)*(hp-lp)
  qty=D(item['quantity']);notional=qty*cl
  parts.append({'symbol':symbol,'side':item['side'],'quantity':item['quantity'],'avg_entry_price':item['avg_px_open'],'native_rounded_mark_close':str(cl),'marked_notional':str(notional),'native_endpoint_interpolated_close_pnl':str(pnl),'effective_gross_notional_to_equity':str(notional/D(row['paired_close_equity'])),'low_native_pnl':item['low_native_pnl'],'high_native_pnl':item['high_native_pnl']})
 unrl=D(row['paired_close_equity'])-D(row['cash']);attributed=sum((D(x['native_endpoint_interpolated_close_pnl']) for x in parts),D(0));notional=sum((D(x['marked_notional']) for x in parts),D(0))
 assert abs(unrl-attributed)<D('0.01'),(row['close_available_ns'],unrl,attributed)
 return {'utc':utc(row['close_available_ns']),'ns':int(row['close_available_ns']),'phase':row['phase'],'cash':row['cash'],'native_marked_equity':row['paired_close_equity'],'native_unrealized_total':str(unrl),'native_endpoint_attribution_residual':str(unrl-attributed),'marked_gross_notional':str(notional),'effective_gross_notional_to_equity':str(notional/D(row['paired_close_equity'])),'positions':parts}
episodes=[]
for n,e in enumerate(risk['curves']['all_native_close_samples']['top3_distinct_excursions'],1):
 a,b,c=(int(e[k]['timestamp_ns']) for k in ('peak','trough','recovery'))
 episodes.append({'rank':n,'drawdown':e,'peak_ns':a,'trough_ns':b,'recovery_ns':c,'landmarks':{},'first_50_percent_breach':None,'max_pre_quote_effective_gross_leverage':None,'post_breach_max':None})
phasecount=defaultdict(int)
for row in csv.DictReader(gzip.open(trace,'rt')):
 phase=row['phase'];phasecount[phase]+=1
 if phase.startswith('post_boundary_'):continue
 ns=int(row['close_available_ns']);equity=D(row['paired_close_equity'])
 for ep in episodes:
  if not ep['peak_ns']<=ns<=ep['recovery_ns']:continue
  for key in ('peak','trough','recovery'):
   if ns==ep[key+'_ns'] and key not in ep['landmarks'] and equity==D(ep['drawdown'][key]['equity']):ep['landmarks'][key]=snapshot(row)
  if ep['first_50_percent_breach'] is None and ns>ep['peak_ns'] and equity<=D(ep['drawdown']['peak']['equity'])/2:
   ep['first_50_percent_breach']=snapshot(row)
  if phase=='pre_quote_paired_close' and ns<=ep['trough_ns']:
   point=snapshot(row)
   if ep['max_pre_quote_effective_gross_leverage'] is None or D(point['effective_gross_notional_to_equity'])>D(ep['max_pre_quote_effective_gross_leverage']['effective_gross_notional_to_equity']):ep['max_pre_quote_effective_gross_leverage']=point
  if ep['first_50_percent_breach'] and (ep['post_breach_max'] is None or equity>D(ep['post_breach_max']['equity'])):ep['post_breach_max']={'utc':utc(ns),'ns':ns,'equity':str(equity)}
for ep in episodes:
 assert len(ep['landmarks'])==3 and ep['first_50_percent_breach']
 peak,trough,recovery=(ep['landmarks'][k] for k in ('peak','trough','recovery'))
 cash_delta=D(trough['cash'])-D(peak['cash']);unrealized_delta=D(trough['native_unrealized_total'])-D(peak['native_unrealized_total'])
 assert cash_delta+unrealized_delta==-D(ep['drawdown']['drawdown_amount'])
 window=[x for x in exits if ep['peak_ns']<int(x['ns'])<=ep['trough_ns']]
 fillwindow=[x for x in r['fill_audit'] if ep['peak_ns']<int(x['fill_ns'])<=ep['trough_ns']]
 gross=total(window,'gross');fee=total(fillwindow,'commission')
 ep['peak_to_trough_cash_decomposition']={'native_cash_change':str(cash_delta),'native_unrealized_change':str(unrealized_delta),'confirmed_exit_gross_attribution':str(gross),'all_actual_fill_fees_in_window':str(fee),'gross_minus_actual_window_fees':str(gross-fee),'unallocated_cash_residual_not_assigned_to_funding':str(cash_delta-(gross-fee))}
 ep['window_exit_stats']=[{'symbol':sym,'reason':reason,'rows':len(rows),'gross':str(total(rows,'gross')),'net_ex_funding':str(total(rows,'net'))} for (sym,reason),rows in ((key,[x for x in window if (x['sym'],x['reason'])==key]) for key in sorted({(x['sym'],x['reason']) for x in window}))]
 ep['largest_loss_exit_fills']=sorted(window,key=lambda x:D(x['net']))[:8]
 ep['largest_loss_closed_episodes']={sym:sorted([x for x in previous['episodes'][sym] if ep['peak_ns']<int(x['end_ns'])<=ep['trough_ns']],key=lambda x:D(x['net']))[:4] for sym in ('BTC','SOL')}
 ep['parent_entries_until_trough']=[{'entry_number':i+1,'utc':utc(t),'price':entries[i]['px'],'qty':entries[i]['qty'],'notional':entries[i]['notional'],'native_side':previous['episodes']['BTC'][i]['side'],'branch':r['entry_sizing_audit'][i]['branch'],'reference_btc_qty':r['entry_sizing_audit'][i]['reference_btc_qty'],'admitted_actual_qty':r['entry_sizing_audit'][i]['confirmed_native_entry_qty']} for i,t in enumerate(parentstarts) if ep['peak_ns']<=t<=ep['trough_ns']]
 ep['time_underwater_days']=str(D(ep['recovery_ns']-ep['peak_ns'])/D(86400_000_000_000));ep['peak_to_trough_days']=str(D(ep['trough_ns']-ep['peak_ns'])/D(86400_000_000_000))
 breach=ep['first_50_percent_breach'];ep['path_after_50_percent_breach']={'further_loss_to_trough':str(D(breach['native_marked_equity'])-D(trough['native_marked_equity'])),'subsequent_rise_to_observed_recovery':str(D(recovery['native_marked_equity'])-D(breach['native_marked_equity'])),'interpretation':'Observed original path, not stop-loss counterfactual profit or avoided loss. Closing changes fees, exposure, rights and all subsequent compounding.'}
full={'provenance':{'head':'64faa21b20df694108b60b85280d2e13a1a7dcde','winner_result_sha256':'8e4a387260688729563258b84befe34b0bef2479f2fbe369c621fab9cc3281e2','trace':risk['trace_artifact'],'economics_source':str(base/'audit/economics.csv'),'attribution':'Reuse existing confirmed-fill average/proportional entry-fee attribution; not native per-trade settled PnL. Native cash/equity authoritative. Perasset close-PnL is native endpoint interpolation at native-rounded marks; residual reported. Signed funding unallocated.'},'stop_configuration':{'true_fixed_stop_loss_exit_count':0,'btc_close_stop_fraction':r['config']['btc_close_stop_fraction'],'sol_z_stop':r['config']['sol_z_stop'],'portfolio_loss_limit_fraction':r['config']['portfolio_loss_limit_fraction'],'deposit_protection':r['config']['deposit_protection'],'liquidation_count':r['liquidation_count'],'btc_trailing_formula':'f=side*(daily_close/entry_vwap−1); best_f=max(best_f,f,0); trigger if best_f>0.03 and f<=best_f−0.03. Daily signal then executablequote; 3 percentage points of entry-return retrace, not a fixed loss stop or portfolio50% stop.'},'all_exit_reason_stats':reason_stats,'logical_exits':logical,'trail_logical_exits':[x for x in logical if x['reason']=='TRAIL'],'closed_episode_stats':previous['episode_stats'],'native_fees_reconciled':str(fees),'fill_net_total':str(total(exits,'net')),'native_cash_gain':previous['native_cash_gain'],'unallocated_cash_residual':previous['native_minus_fill_attribution_residual'],'trace_phase_counts':dict(phasecount),'drawdown_episodes':episodes}
(out/'drawdown-causes.json').write_text(json.dumps(full,indent=2)+'\n')
print(json.dumps({'episodes':[{k:ep[k] for k in ('rank','landmarks','first_50_percent_breach','max_pre_quote_effective_gross_leverage','peak_to_trough_cash_decomposition','window_exit_stats','time_underwater_days','path_after_50_percent_breach')} for ep in episodes],'reason_stats':reason_stats,'trail_groups':[x for x in logical if x['reason']=='TRAIL']},indent=2))
