"""Small native-artifact aggregates only; does not scan minute trace."""
import csv,gzip,json,bisect,hashlib
from pathlib import Path
from decimal import Decimal as D
b=Path('reports/selective-lifecycle-cap30m-113');p=b/'hedge-risk-audit';a=json.loads((p/'hedge-risk.json').read_text());r=json.load(gzip.open(b/'native-result.json.gz','rt'));prev=json.loads((b/'audit/findings.json').read_text())['variant'];exits=list(csv.DictReader((b/'audit/economics.csv').open()));starts={s:[int(e['start_ns']) for e in prev['episodes'][s]] for s in ['BTC','SOL']}
fees={}
for f in r['fill_audit']:
 if f['action'] in ['BTC_ENTRY','SOL_ADD']:
  s='BTC' if f['action']=='BTC_ENTRY' else 'SOL';i=bisect.bisect_right(starts[s],int(f['fill_ns']));fees.setdefault((s,i),[]).append((int(f['fill_ns']),D(f['commission'])))
for c in a['profit_split_cases']:
 n=c['trigger_ns'];legnet={}
 for s,x in c['initial_snapshot']['legs'].items():
  i=int(x['episode']);inc=sum((f for ns,f in fees.get((s,i),[]) if ns<n),D(0));alloc=sum((D(z['entry_fee_alloc']) for z in exits if z['sym']==s and int(z['episode'])==i and int(z['ns'])<n),D(0));remain=inc-alloc;assert remain>=D('-0.00000001');remain=max(remain,D(0));x['remaining_allocated_entry_fee']=str(remain);legnet[s]=D(x['held_native_pnl'])-D(x['prospective_mark_exit_fee_reserve'])-remain;x['held_pnl_after_allocated_entry_fee_and_exit_reserve']=str(legnet[s])
 c['cumulative_winner_current_held_net_positive']=legnet[c['winner']]>0;c['cumulative_loser_current_held_net_negative']=legnet[c['loser']]<0
 initial=D(c['initial_snapshot']['legs'][c['loser']]['fee_reserved_pnl']);c['original_final_minus_initial_fee_reserved_pnl']=str(D(c['loser_final_actual_net_ex_funding'])-initial)
 for s,label in [(c['loser'],'loser'),(c['winner'],'winner')]:
  i=c[label+'_episode'];legs=[z for z in exits if z['sym']==s and int(z['episode'])==i and n<int(z['ns'])];c[label+'_subsequent_original_exit_reasons']=sorted({z['reason'] for z in legs})
cc=a['case_counts'];cc['cumulative_winner_but_current_held_net_not_positive']=sum(not c['cumulative_winner_current_held_net_positive'] for c in a['profit_split_cases']);cc['genuine_winner_positive_loser_negative_held_fee_net_at_initial_split']=sum(c['cumulative_winner_current_held_net_positive'] and c['cumulative_loser_current_held_net_negative'] for c in a['profit_split_cases'])
groups=[]
for loser in ['BTC','SOL']:
 cs=[c for c in a['profit_split_cases'] if c['loser']==loser];unique={c['loser_episode']:c for c in cs};groups.append({'original_loser_asset':loser,'cases':len(cs),'unique_loser_episodes':len(unique),'original_fee_reserved_held_break_even':sum(c['first_original_held_fee_reserved_break_even'] is not None for c in cs),'original_final_nonnegative':sum(c['actual_closed_break_even'] for c in cs),'final_negative_net_sum':str(sum((D(c['loser_final_actual_net_ex_funding']) for c in unique.values() if D(c['loser_final_actual_net_ex_funding'])<0),D(0))),'cases_with_new_loser_adds':sum(c['subsequent_actual_opening_fill_rows']>0 for c in cs),'worst_additional_close_adversity':str(min((D(c['additional_close_adversity_after_trigger']) for c in cs),default=D(0)))})
a['outcomes_by_loser_asset']=groups;a['entry_beta_current_beta_sigma_optimized_hedge_weights']='UNKNOWN_not_archived';a['first_winning_leg_profit_cross_timestamp']='UNKNOWN_before_initial_profit_split_not_recorded';a['prospective_fee_basis']='Actual control taker0.00055×remaining native quantity×rounded MARK close; not actual book executable close/fee.';(p/'hedge-risk.json').write_text(json.dumps(a,indent=2)+'\n')
rows=[]
for d in a['global_TOP3_state_account_changes']:
 for k,v in d['bucket_equity_changes'].items():rows.append({'DD_rank':d['rank'],'state_or_transition':k,'native_equity_change':v,'loss_share_of_peak_to_trough_percent':str(-D(v)/D(d['drawdown_amount'])*100),'sample_intervals':d['bucket_sample_intervals'][k]})
with (p/'global-DD-exposure-states.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
flat=[]
for c in a['profit_split_cases']:
 x={k:v for k,v in c.items() if k!='initial_snapshot'}
 for s,leg in c['initial_snapshot']['legs'].items():
  for k in ['notional','held_native_pnl','cumulative_pnl','fee_reserved_pnl','remaining_allocated_entry_fee','held_pnl_after_allocated_entry_fee_and_exit_reserve']:x[s+'_'+k]=leg[k]
 flat.append(x)
with (p/'profit-split-cases.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(flat[0]),lineterminator='\n');w.writeheader();w.writerows(flat)
print(json.dumps({'counts':cc,'groups':groups,'ratios':a['gross_ratio_BTC_over_SOL'],'DD':[{'rank':d['rank'],'changes':d['bucket_equity_changes']} for d in a['global_TOP3_state_account_changes']]},indent=2))
