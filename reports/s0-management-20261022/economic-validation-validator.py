"""Report-only saved-output validator. No strategy, fills, PnL ledger or engine."""
import argparse,ast,collections,csv,datetime,gzip,hashlib,json,resource,time
from decimal import Decimal as D
from pathlib import Path
START=1725148800000000000
END=1788220800000000000
SEED=D('10000')
S0=D('6077107.23887483')
RETENTION_FLOOR=SEED+D('.9')*(S0-SEED)
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def scalar(v):
 if isinstance(v,D):return str(v)
 raise TypeError(type(v).__name__)
def validate(result,label):
 began=time.monotonic();trace=result/'minute-native-settled-receipts.csv.gz'
 reports=list(result.glob('*direction*.json'));reports=[p for p in reports if not p.name.endswith('-raw-native.json')]
 if len(reports)!=1:raise ValueError('EXACTLY_ONE_COMPLETED_DIRECTION_REPORT_REQUIRED')
 report=reports[0];rawpath=report.with_name(report.stem+'-raw-native.json')
 metadata={'input_pins':json.load((result.parent/'input-hashes.json').open()),'file_hashes':{n:sha(result.parent/n) for n in ['input-hashes.json','immutable-source-hashes.json','source-input-hashes.sha256','launch.sh','launch-command.json']}}
 final=json.load(report.open());raw=json.load(rawpath.open());peak=SEED;peak_ns=START;maxdd=D(0);worst=None;prev_quote=None;prev_receipt=None;prev_epoch=None;n=0;issues=collections.Counter();states=collections.Counter();months={};last_w=SEED;lag=collections.Counter();last=None
 with gzip.open(trace,'rt') as f:
  for row in csv.DictReader(f):
   q=int(row['source_quote_ns']);t=int(row['receipt_ns']);epoch=int(row['fill_epoch']);w=D(row['paired_close_equity']);cash=D(row['cash']);n+=1
   if not(START<q<END):issues['source_quote_outside_interval']+=1
   if prev_quote is not None and q-prev_quote!=60000000000:issues['non_60second_source_step']+=1
   if prev_receipt is not None and t<=prev_receipt:issues['nonmonotone_receipt']+=1
   if prev_epoch is not None and epoch<prev_epoch:issues['decreasing_fill_epoch']+=1
   if t<q:issues['receipt_before_source_quote']+=1
   lag[t-q]+=1
   if w>peak:peak=w;peak_ns=t
   dd=(peak-w)/peak*100
   if dd>maxdd:maxdd=dd;worst={'peak_receipt_ns':peak_ns,'peak_equity':peak,'trough_receipt_ns':t,'trough_equity':w,'DD_percent':dd,'trough_source_quote_ns':q,'trough_cash':cash,'trough_native_positions':json.loads(row['native_positions_and_mark_ohlc_json'])}
   month=datetime.datetime.fromtimestamp(q/1e9,datetime.timezone.utc).strftime('%Y-%m')
   if month not in months:months[month]={'month':month,'start_equity':last_w,'end_equity':w,'minimum':w,'maximum':w,'within_month_peak':last_w,'within_month_DD_percent':D(0),'maximum_global_DD_percent':D(0),'receipts':0,'gross_native_notional_to_equity_sum':0.,'gross_native_notional_to_equity_max':0.,'states':collections.Counter(),'asset_open_samples':collections.Counter()}
   m=months[month];m['receipts']+=1;m['end_equity']=w;m['minimum']=min(m['minimum'],w);m['maximum']=max(m['maximum'],w);m['within_month_peak']=max(m['within_month_peak'],w);m['within_month_DD_percent']=max(m['within_month_DD_percent'],(m['within_month_peak']-w)/m['within_month_peak']*100);m['maximum_global_DD_percent']=max(m['maximum_global_DD_percent'],dd)
   positions=json.loads(row['native_positions_and_mark_ohlc_json']);book=[];gross=0.
   for p in positions:
    asset=p['instrument_id'].split('USDT')[0];book.append(asset);m['asset_open_samples'][asset]+=1
    gross+=abs(float(p['quantity']))*float(p['mark_ohlc']['close'])
   state='+'.join(sorted(book)) or 'FLAT';states[state]+=1;m['states'][state]+=1
   if w>0:
    lev=gross/float(w);m['gross_native_notional_to_equity_sum']+=lev;m['gross_native_notional_to_equity_max']=max(m['gross_native_notional_to_equity_max'],lev)
   else:issues['nonpositive_equity']+=1
   last={'source_quote_ns':q,'receipt_ns':t,'cash':cash,'equity':w,'native_positions':positions};last_w=w;prev_quote=q;prev_receipt=t;prev_epoch=epoch
 for m in months.values():
  m['return_percent']=(m['end_equity']/m['start_equity']-1)*100;m['gross_native_notional_to_equity_mean']=m.pop('gross_native_notional_to_equity_sum')/m['receipts'];m.pop('within_month_peak')
 fee_groups=collections.defaultdict(lambda:{'count':0,'fees':D(0),'notional':D(0)});actions=collections.Counter();asset_fills=collections.Counter();asset_costs=collections.defaultdict(lambda:{'fills':0,'fees':D(0),'notional':D(0),'management_fills':0,'management_fees':D(0),'management_notional':D(0)});monthly_costs=collections.defaultdict(lambda:{'fills':0,'fees':D(0),'notional':D(0),'asset_fees':collections.defaultdict(D),'fill_actions':collections.Counter()})
 for key in ['maker','taker','unknown']:fee_groups[key]
 for f in raw['fill_audit']:
  side=f.get('native_liquidity_side','').lower();side=side if side in ['maker','taker'] else 'unknown'
  g=fee_groups[side];g['count']+=1;g['fees']+=D(f['commission']);g['notional']+=D(f['notional']);actions[f['action']]+=1;asset=f['instrument'].split('USDT')[0];asset_fills[asset]+=1;g=asset_costs[asset];g['fills']+=1;g['fees']+=D(f['commission']);g['notional']+=D(f['notional'])
  month=datetime.datetime.fromtimestamp(int(f['fill_ns'])/1e9,datetime.timezone.utc).strftime('%Y-%m');mg=monthly_costs[month];mg['fills']+=1;mg['fees']+=D(f['commission']);mg['notional']+=D(f['notional']);mg['asset_fees'][asset]+=D(f['commission']);mg['fill_actions'][f['action']]+=1
  if f['action']=='PROTECTIVE_REDUCTION':g['management_fills']+=1;g['management_fees']+=D(f['commission']);g['management_notional']+=D(f['notional'])
 fee_sum=sum((g['fees'] for g in fee_groups.values()),D(0));fee_checks={k:{'count_matches':v['count']==raw['fee_attribution'][k]['count'],'fees_match':v['fees']==D(raw['fee_attribution'][k]['fees']),'notional_matches':v['notional']==D(raw['fee_attribution'][k]['notional'])} for k,v in fee_groups.items()}
 csv_fill=Path(raw['execution_artifacts']['fills']['path']);csv_fee=D(0);csv_count=0
 for f in csv.DictReader(csv_fill.open()):
  csv_count+=1
  for commission in ast.literal_eval(f['commissions']):
   amount,currency=commission.split();
   if currency!='USDT':raise ValueError('UNEXPECTED_COMMISSION_CURRENCY')
   csv_fee+=D(amount)
 order_statuses=collections.Counter(f['status'] for f in csv.DictReader(Path(raw['execution_artifacts']['orders']['path']).open()))
 total=D(final['terminal_total']);active=D(final['terminal_active']);reserve=D(final['terminal_reserve']);cash_tail=raw['cash_account_series'][-1];settled=final['minute_risk_observations']['settled_native_close_receipts'];reported_dd=D(settled['curve']['top3_distinct_excursions'][0]['drawdown_peak_percent'])
 native_artifacts={k:{'path':v['path'],'sha256':sha(Path(v['path'])),'reported_sha256':v.get('sha256'),'matches_reported_sha256':sha(Path(v['path']))==v.get('sha256'),'reported_rows':v.get('rows')} for k,v in raw['execution_artifacts'].items() if k in ['fills','orders']}
 checks={'receipt_DD_equals_reported_within_1e-20pp':abs(maxdd-reported_dd)<=D('1e-20'),'coverage_receipts_matches_report':n==settled['receipts'],'coverage_report_samples_includes_seed':settled['curve']['samples']==n+1,'24_calendar_months':len(months)==24,'expected_1051199_receipts':n==1051199,'final_TOTAL_equals_ACTIVE_plus_RESERVE':total==active+reserve,'raw_wrapper_terminal_TOTAL_equal':D(raw['terminal_total'])==total,'native_cash_tail_total_equals_TOTAL':D(cash_tail['total'])==total,'native_cash_tail_active_equals_ACTIVE':D(cash_tail['active'])==active,'native_cash_tail_reserve_equals_RESERVE':D(cash_tail['reserve'])==reserve,'native_final_position_count_zero':raw['terminal_open_positions']==final['terminal_open_positions']==0,'native_lifecycle_FLAT':raw['terminal_lifecycle'].get('status')==final['terminal_lifecycle'].get('status')=='FLAT','fee_audit_sum_equals_native_fees':fee_sum==D(raw['native_fees'])==D(final['native_fees']),'native_fill_report_rows_equal_audit':csv_count==len(raw['fill_audit'])==raw['fills'],'native_fill_report_commissions_equal_audit':csv_fee==fee_sum,'no_intervening_native_mutation_unavailable':settled['unavailable_intervening_native_mutation']==0,'no_stream_coverage_issues':not issues}
 return {'label':label,'job_metadata':metadata,'status':'SAVED_NATIVE_OUTPUT_VALIDATION','native_report_status':final['status'],'ranking_eligible':final.get('ranking_eligible'),'inputs':{'report':str(report),'report_sha256':sha(report),'raw':str(rawpath),'raw_sha256':sha(rawpath),'receipts':str(trace),'receipts_sha256':sha(trace)},'native_artifacts':native_artifacts,'checks':checks,'stream_issues':dict(issues),'receipt_rows':n,'receipt_source_quote_step_ns':60000000000,'receipt_lag_counts_ns':dict(lag),'months':list(months.values()),'book_state_receipts':dict(states),'recomputed_money_DD_percent':maxdd,'reported_money_DD_percent':reported_dd,'terminal_boundary_endpoint_DD_percent':max(D(0),(peak-total)/peak*100),'receipt_DD_with_terminal_native_cash_endpoint_percent':max(maxdd,max(D(0),(peak-total)/peak*100)),'native_receipt_running_peak_equity':peak,'worst_receipt_excursion':worst,'native_top3_settled_excursions':settled['curve']['top3_distinct_excursions'],'last_interval_receipt':last,'terminal_TOTAL':total,'terminal_ACTIVE':active,'terminal_RESERVE':reserve,'native_cash_tail':cash_tail,'native_terminal_lifecycle':raw['terminal_lifecycle'],'post_boundary_settlement':raw['post_boundary_settlement'],'fee_groups':dict(fee_groups),'fee_group_checks':fee_checks,'native_fill_audit_count':len(raw['fill_audit']),'native_order_report_fill_rows':csv_count,'native_fill_report_commissions':csv_fee,'fill_action_counts':dict(actions),'asset_fill_counts':dict(asset_fills),'per_asset_native_fill_costs':dict(asset_costs),'native_fill_costs_by_actual_UTC_fill_month':dict(monthly_costs),'native_realized_unrealized':raw['realized_unrealized'],'native_final_order_report_status_counts':dict(order_statuses),'native_funding':raw['funding'],'source_hashes':raw.get('source_hashes'),'config_hash':raw['config_hash'],'conditional_OHLC_upper_to_later_lower':raw['minute_risk_observations'].get('conditional_upper_to_later_lower_bound'),'conditional_OHLC_verification':'Saved native conditional bound only; not independently restreamed; actual tick DD UNKNOWN; no intrabar extrema ordering inferred.','retention':{'formula':'(candidate terminal TOTAL -10000)/(6077107.23887483-10000)','net_profit_retention_fraction':(total-SEED)/(S0-SEED),'minimum_TOTAL_for_90_percent_net_profit':RETENTION_FLOOR,'money_DD_le_50':maxdd<=50,'money_DD_with_terminal_endpoint_le_50':max(maxdd,max(D(0),(peak-total)/peak*100))<=50,'net_profit_retention_ge_90_percent':total>=RETENTION_FLOOR},'native_economic_runs_added':0,'limitations':['Receipt equity and native fill costs are observations, not an alternative equity/fill/PnL engine.','Last interval receipt marked equity may differ from final boundary-settled native cash/TOTAL.','Monthly returns use consecutive source-quote UTC month-end receipt equity, with seed10000; post-boundary final cash is separate.','Exposure is recorded native quantity times same-source recorded native close mark over saved equity; receipt sample statistics are not tick statistics.','Signed funding remains native-report UNKNOWN where no cash-delta audit exists.'],'elapsed_seconds':time.monotonic()-began,'maxrss_native_units':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--result',type=Path,required=True);p.add_argument('--label',required=True);a=p.parse_args();print(json.dumps(validate(a.result,a.label),default=scalar,separators=(',',':')))
