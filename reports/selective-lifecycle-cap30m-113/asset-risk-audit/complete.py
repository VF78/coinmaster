"""Cached pass-two aggregates and documentation; no trace read or engine."""
import csv,json,hashlib
from pathlib import Path
from decimal import Decimal as D
p=Path('reports/selective-lifecycle-cap30m-113/asset-risk-audit');rows=list(csv.DictReader((p/'episode-paths.csv').open()));a=json.loads((p/'asset-risk.json').read_text());cross=[];ages=[];gs=[]
for x in rows:
 for k,v in json.loads(x['crossings_json']).items():cross.append({'asset':x['sym'],'episode':x['episode'],'sample':k,'final_net_ex_funding':x['net'],**v})
 if x['sym']=='SOL':
  for day,v in json.loads(x['age_snapshots_json']).items():ages.append({'episode':x['episode'],'age_days':day,'final_net_ex_funding':x['net'],**v})
for s in ['BTC','SOL']:
 rr=[x for x in rows if x['sym']==s]
 for t in [20,30,40]:
  hit=[x for x in rr if D(x['peak_giveback_close'])/D(x['entry_equity'])*100>=t]
  gs.append({'asset':s,'profit_peak_giveback_percent_firstheld_equity':t,'hit':len(hit),'losers':sum(D(x['net'])<0 for x in hit),'winners':sum(D(x['net'])>0 for x in hit),'loser_final_net':str(sum((D(x['net']) for x in hit if D(x['net'])<0),D(0))),'winner_full_final_net_at_risk':str(sum((D(x['net']) for x in hit if D(x['net'])>0),D(0)))})
ags=[]
for day in ['3','5','7','10']:
 held=[x for x in ages if x['age_days']==day];negative=[x for x in held if D(x['current_episode_pnl'])<0]
 ags.append({'day':int(day),'still_held_episodes':len(held),'negative_now':len(negative),'negative_now_eventual_losers':sum(D(x['final_net_ex_funding'])<0 for x in negative),'negative_now_eventual_winners':sum(D(x['final_net_ex_funding'])>0 for x in negative),'negative_now_loser_final_net':str(sum((D(x['final_net_ex_funding']) for x in negative if D(x['final_net_ex_funding'])<0),D(0))),'negative_now_winner_final_net_at_risk':str(sum((D(x['final_net_ex_funding']) for x in negative if D(x['final_net_ex_funding'])>0),D(0))),'negative_now_subsequent_outcome_difference':str(sum((D(x['subsequent_observed_outcome_difference']) for x in negative),D(0)))})
for name,rr in [('crossing-events.csv',cross),('SOL-age-snapshots.csv',ages),('profit-giveback-screens.csv',gs),('SOL-age-screens.csv',ags)]:
 with (p/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]),lineterminator='\n');w.writeheader();w.writerows(rr)
a['profit_giveback_screens']=gs;a['SOL_age_screens']=ags;a['running_episode_profit_peak_giveback']='MEASURED cumulative native attributed episode close peak minus later held-close path; peak timestamp not retained, trough UTC retained; denominator first-held portfolio equity, not profit-peak return.';a['first_loss_budget_crossings']=cross;a['SOL_age_snapshots']=ages
# Replace older case snapshots with pass-two fields, preserving archived exit semantics.
byid={(x['sym'],x['episode']):x for x in rows}
for x in a['SOL_losing_episode_cases']:
 x.update(byid[('SOL',x['episode'])]);x['MFE']=x['maximum_close'];x['first_weakness']='UNKNOWN_undefined';x.pop('first_weakness',None)
(p/'asset-risk.json').write_text(json.dumps(a,indent=2)+'\n')
f=p/'README.md';text=f.read_text();text+='\n## Pass-two profit giveback and chronological crossing evidence\n\n| Asset / giveback budget as % first-held equity | Losing episodes touched | Winning episodes touched | Loser final net | Winner full final net at risk |\n| --- | ---: | ---: | ---: | ---: |\n'
for x in gs:text+=f"| {x['asset']} / {x['profit_peak_giveback_percent_firstheld_equity']}% | {x['losers']} | {x['winners']} | {D(x['loser_final_net']):,.2f} | {D(x['winner_full_final_net_at_risk']):,.2f} |\n"
text+='\nGiveback tracks cumulative episode realized-minus-fees plus held PnL running maximum, then its later drop. It differs from loss below entry and from global portfolio drawdown. Peak value and trough UTC are retained; exact peak timestamp is not. Close MFE, maximum including completed final net, conditional adverse-series extrema and giveback are in episode-paths.csv. First20/30/40% entry-loss crossings include UTC/current attributed episode PnL/current native portfolio equity and final-minus-current observed outcome differences in crossing-events.csv. These differences include subsequent realized/held evolution and fees, exclude unallocated funding, and do NOT represent a stop counterfactual.\n\n| SOL held-age / negative cumulative episode path | Still held | Negative now | Eventual losers / winners | Loser final net | Winner full final net at risk | Observed subsequent outcome difference |\n| --- | ---: | ---: | ---: | ---: | ---: | ---: |\n'
for x in ags:text+=f"| {x['day']} days | {x['still_held_episodes']} | {x['negative_now']} | {x['negative_now_eventual_losers']} / {x['negative_now_eventual_winners']} | {D(x['negative_now_loser_final_net']):,.2f} | {D(x['negative_now_winner_final_net_at_risk']):,.2f} | {D(x['negative_now_subsequent_outcome_difference']):,.2f} |\n"
text+='\nAge starts at the first actual SOL fill, not signal/order submission. Snapshot is the first prequote at or after each age while native exposure remains; intervening adds and partial exits remain represented. The negative-now screen is entry-age and current-native-PnL observable, but is selected in sample. It is not a hypothetical exit fill or avoided loss. All survivors/positive snapshots are separately retained, not silently discarded.\n'
f.write_text(text)
print(json.dumps({'giveback':gs,'age':ags,'BTC_largest_giveback':sorted([x for x in rows if x['sym']=='BTC'],key=lambda x:D(x['peak_giveback_close']),reverse=True)[:2],'SOL_cases':a['SOL_losing_episode_cases']},indent=2))
