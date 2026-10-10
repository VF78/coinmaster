"""Read-only native overlap/profit-split observation. No hypothetical execution."""
import bisect,csv,gzip,json,hashlib
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
b=Path('reports/selective-lifecycle-cap30m-113');o=b/'hedge-risk-audit';previous=json.loads((b/'audit/findings.json').read_text())['variant'];r=json.load(gzip.open(b/'native-result.json.gz','rt'));exits=list(csv.DictReader((b/'audit/economics.csv').open()))
trace=Path('/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-minute-extrema-risk-20261010/result/minute-native-risk.csv.gz')
def utc(ns):return datetime.fromtimestamp(int(ns)/1e9,timezone.utc).isoformat()
eps={s:[dict(e,events=[],cash_component=D(0),event_index=0) for e in previous['episodes'][s]] for s in ['BTC','SOL']};starts={s:[int(e['start_ns']) for e in v] for s,v in eps.items()}
for x in exits:eps[x['sym']][int(x['episode'])-1]['events'].append((int(x['ns']),D(x['gross'])-D(x['exit_fee'])))
for f in r['fill_audit']:
 if f['action'] in ['BTC_ENTRY','SOL_ADD']:
  s='BTC' if f['action']=='BTC_ENTRY' else 'SOL';eps[s][bisect.bisect_right(starts[s],int(f['fill_ns']))-1]['events'].append((int(f['fill_ns']),-D(f['commission'])))
for v in eps.values():
 for e in v:e['events'].sort();assert sum((x[1] for x in e['events']),D(0))==D(e['net'])
dds=[]
for e in json.loads((b/'drawdown-causes/drawdown-causes.json').read_text())['drawdown_episodes']:
 dds.append({'rank':e['rank'],'peak_ns':e['peak_ns'],'trough_ns':e['trough_ns'],'peak_equity':e['drawdown']['peak']['equity'],'trough_equity':e['drawdown']['trough']['equity'],'drawdown_amount':e['drawdown']['drawdown_amount'],'started':False,'done':False,'bucket_equity_changes':{},'bucket_sample_intervals':{}})
ratios=[];counts={'BTC_ONLY':0,'SOL_ONLY':0,'BOTH':0,'FLAT':0};cases={};overlap_worst=[];paired_sides={};both_equity_min=None;totalrows=prequotes=0
for row in csv.DictReader(gzip.open(trace,'rt')):
 totalrows+=1
 if row['phase'].startswith('post_boundary_'):continue
 ns=int(row['close_available_ns']);eq=D(row['paired_close_equity']);parts=None
 active=[d for d in dds if d['peak_ns']<=ns<=d['trough_ns'] and not d['done']]
 if active:
  parts=json.loads(row['native_positions_and_mark_ohlc_json']);symbols={('BTC' if x['instrument_id'].startswith('BTC') else 'SOL') for x in parts};state='BOTH' if len(symbols)==2 else 'BTC_ONLY' if 'BTC' in symbols else 'SOL_ONLY' if 'SOL' in symbols else 'FLAT'
  for d in active:
   if not d['started']:
    if ns!=d['peak_ns'] or eq!=D(d['peak_equity']):continue
    d['started']=True;d['prev_eq']=eq;d['prev_state']=state
   else:
    key=state if state==d['prev_state'] else 'TRANSITION_'+d['prev_state']+'_TO_'+state
    d['bucket_equity_changes'][key]=d['bucket_equity_changes'].get(key,D(0))+eq-d['prev_eq'];d['bucket_sample_intervals'][key]=d['bucket_sample_intervals'].get(key,0)+1;d['prev_eq']=eq;d['prev_state']=state
   if ns==d['trough_ns'] and eq==D(d['trough_equity']):d['done']=True
 if row['phase']!='pre_quote_paired_close':continue
 prequotes+=1
 if parts is None:parts=json.loads(row['native_positions_and_mark_ohlc_json'])
 points={}
 for p in parts:
  s='BTC' if p['instrument_id'].startswith('BTC') else 'SOL';i=bisect.bisect_left(starts[s],ns)-1
  if i<0 or not int(eps[s][i]['start_ns'])<ns<=int(eps[s][i]['end_ns']):continue
  e=eps[s][i]
  while e['event_index']<len(e['events']) and e['events'][e['event_index']][0]<ns:e['cash_component']+=e['events'][e['event_index']][1];e['event_index']+=1
  step=D('0.1' if s=='BTC' else '0.01');bar=p['mark_ohlc'];lo,hi,cl=[(D(bar[k])/step).quantize(D(1))*step for k in ['low','high','close']];lp,hp=D(p['low_native_pnl']),D(p['high_native_pnl']);held=lp if lo==hi else lp+(cl-lo)/(hi-lo)*(hp-lp);notional=D(p['quantity'])*cl;reserve=notional*D('0.00055')
  points[s]={'episode':i+1,'side':p['side'],'qty':p['quantity'],'notional':notional,'held_native_pnl':held,'realized_minus_incurred_fees':e['cash_component'],'cumulative_pnl':e['cash_component']+held,'prospective_mark_exit_fee_reserve':reserve,'fee_reserved_pnl':e['cash_component']+held-reserve,'conditional_adverse_fee_reserved_pnl':e['cash_component']+min(lp,hp)-reserve}
 state='BOTH' if len(points)==2 else 'BTC_ONLY' if 'BTC' in points else 'SOL_ONLY' if 'SOL' in points else 'FLAT';counts[state]+=1
 if state=='BOTH':
  ratio=points['BTC']['notional']/points['SOL']['notional'];ratios.append(ratio);k=points['BTC']['side']+'_'+points['SOL']['side'];paired_sides[k]=paired_sides.get(k,0)+1
  comb=sum((x['cumulative_pnl'] for x in points.values()),D(0));snap={'utc':utc(ns),'timestamp_ns':ns,'native_equity':str(eq),'combined_active_episode_realized_plus_held_ex_funding':str(comb),'BTC_to_SOL_gross_ratio':str(ratio),'legs':{s:{k:str(v) for k,v in x.items()} for s,x in points.items()}}
  if both_equity_min is None or eq<D(both_equity_min['native_equity']):both_equity_min=snap
  overlap_worst.append(snap);overlap_worst.sort(key=lambda x:D(x['combined_active_episode_realized_plus_held_ex_funding']));overlap_worst=overlap_worst[:3]
  key=str(points['BTC']['episode'])+'_'+str(points['SOL']['episode'])
  if key not in cases:
   winners=[s for s,x in points.items() if x['fee_reserved_pnl']>0];losers=[s for s,x in points.items() if x['fee_reserved_pnl']<0]
   if len(winners)==len(losers)==1:
    winner,loser=winners[0],losers[0];le=eps[loser][points[loser]['episode']-1]
    cases[key]={'pair':key,'trigger_ns':ns,'trigger_utc':utc(ns),'winner':winner,'loser':loser,'loser_episode':points[loser]['episode'],'winner_episode':points[winner]['episode'],'initial_snapshot':snap,'first_original_held_fee_reserved_break_even':None,'loser_min_after_trigger':points[loser]['fee_reserved_pnl'],'loser_conditional_min_after_trigger':points[loser]['conditional_adverse_fee_reserved_pnl'],'loser_min_after_trigger_ns':ns,'end_ns':int(le['end_ns']),'loser_final_actual_net_ex_funding':le['net'],'winner_final_actual_net_ex_funding':eps[winner][points[winner]['episode']-1]['net']}
 for c in cases.values():
  if ns<c['trigger_ns'] or ns>c['end_ns']:continue
  x=points.get(c['loser'])
  if x is None or x['episode']!=c['loser_episode']:continue
  if c['first_original_held_fee_reserved_break_even'] is None and x['fee_reserved_pnl']>=0:c['first_original_held_fee_reserved_break_even']={'utc':utc(ns),'timestamp_ns':ns,'fee_reserved_pnl':str(x['fee_reserved_pnl'])}
  if x['fee_reserved_pnl']<c['loser_min_after_trigger']:c['loser_min_after_trigger']=x['fee_reserved_pnl'];c['loser_min_after_trigger_ns']=ns
  c['loser_conditional_min_after_trigger']=min(c['loser_conditional_min_after_trigger'],x['conditional_adverse_fee_reserved_pnl'])
assert totalrows==3153600 and prequotes==1051200
for d in dds:
 assert d['done'] and sum(d['bucket_equity_changes'].values())==-D(d['drawdown_amount'])
 d['bucket_equity_changes']={k:str(v) for k,v in d['bucket_equity_changes'].items()};d.pop('prev_eq');d.pop('prev_state')
for c in cases.values():
 fs=[f for f in r['fill_audit'] if c['trigger_ns']<int(f['fill_ns'])<=c['end_ns'] and f['instrument'].startswith(c['loser'])];c['subsequent_actual_opening_fill_rows']=sum(f['action'] in ['BTC_ENTRY','SOL_ADD'] for f in fs);c['subsequent_actual_exit_fill_rows']=sum(f['action'] not in ['BTC_ENTRY','SOL_ADD'] for f in fs);c['subsequent_actual_exit_reasons']=sorted({f['reason'] for f in fs if f['action'] not in ['BTC_ENTRY','SOL_ADD']});c['loser_min_after_trigger_utc']=utc(c['loser_min_after_trigger_ns']);c['additional_close_adversity_after_trigger']=str(c['loser_min_after_trigger']-D(c['initial_snapshot']['legs'][c['loser']]['fee_reserved_pnl']));c['loser_min_after_trigger']=str(c['loser_min_after_trigger']);c['loser_conditional_min_after_trigger']=str(c['loser_conditional_min_after_trigger']);c['actual_closed_break_even']=D(c['loser_final_actual_net_ex_funding'])>=0
ratios.sort()
def q(fr):return str(ratios[int((len(ratios)-1)*fr)])
summary={'counts':counts,'paired_native_sides':paired_sides,'gross_ratio_BTC_over_SOL':{'min':q(0),'p10':q(.1),'median':q(.5),'p90':q(.9),'max':q(1)},'global_TOP3_state_account_changes':dds,'overlap_min_native_equity':both_equity_min,'worst_overlap_active_episode_contribution':overlap_worst,'profit_split_cases':list(cases.values()),'case_counts':{'total':len(cases),'original_loser_held_fee_reserved_break_even':sum(c['first_original_held_fee_reserved_break_even'] is not None for c in cases.values()),'original_loser_final_net_nonnegative':sum(c['actual_closed_break_even'] for c in cases.values()),'cases_with_subsequent_loser_add_fills':sum(c['subsequent_actual_opening_fill_rows']>0 for c in cases.values())},'trace_rows':totalrows,'prequote_rows':prequotes,'trace':str(trace),'prospective_taker_fee_rate':'0.00055','decision_beta':'UNKNOWN_not_archived','signed_funding':'UNKNOWN_unallocated','reversal_screen':'FIRST_PROFIT_SPLIT_PER_OVERLAPPING_ASSET_EPISODE_PAIR; NOT_REVERSAL','basis':'Existing confirmed native fill gross/actual fees plus native position PnL endpoint interpolation. Fee reserve uses mark notional, not an executed close. Continued loser paths are original strategy with adds/exits, not hypothetical winning-leg closure paths. State account changes are observational bookkeeping including native funding/cash, not causal hedge contribution.'}
(o/'hedge-risk.json').write_text(json.dumps(summary,indent=2)+'\n')
flat=[{k:v for k,v in c.items() if k!='initial_snapshot'} for c in cases.values()]
with (o/'profit-split-cases.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(flat[0]),lineterminator='\n');w.writeheader();w.writerows(flat)
print(json.dumps({k:v for k,v in summary.items() if k not in ['profit_split_cases','worst_overlap_active_episode_contribution']},indent=2))
