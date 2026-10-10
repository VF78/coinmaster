"""Small cached episode aggregates; never reads the minute trace."""
import csv,json
from pathlib import Path
from decimal import Decimal as D
p=Path('reports/selective-lifecycle-cap30m-113/asset-risk-audit');a=json.loads((p/'asset-risk.json').read_text());rows=list(csv.DictReader((p/'episode-paths.csv').open()));buckets=[];extra=[]
for s in ['BTC','SOL']:
 rr=[x for x in rows if x['sym']==s]
 for period in ['FIRST12M','SECOND12M']:
  for side in ['BUY','SELL']:
   sub=[x for x in rr if ('FIRST12M' if x['start']<'2025-09-01' else 'SECOND12M')==period and x['side']==side]
   buckets.append({'asset':s,'period_by_entry':period,'side':side,'episodes':len(sub),'losers':sum(D(x['net'])<0 for x in sub),'net_ex_funding':str(sum((D(x['net']) for x in sub),D(0))),'negative_net_sum':str(sum((D(x['net']) for x in sub if D(x['net'])<0),D(0))),'winners_touching20pct_asset_budget':sum(D(x['net'])>0 and D(x['close_loss_percent_entry_equity'])>=20 for x in sub),'losers_touching20pct_asset_budget':sum(D(x['net'])<0 and D(x['close_loss_percent_entry_equity'])>=20 for x in sub)})
 for k in [1,2]:
  hit=[x for i,x in enumerate(rr) if i>=k and all(D(y['net'])<0 for y in rr[i-k:i])]
  extra.append({'asset':s,'entry_known_screen':f'previous_{k}_completed_asset_episodes_losing','touched':len(hit),'losers':sum(D(x['net'])<0 for x in hit),'winners':sum(D(x['net'])>0 for x in hit),'loser_final_net':str(sum((D(x['net']) for x in hit if D(x['net'])<0),D(0))),'winner_final_net_at_risk':str(sum((D(x['net']) for x in hit if D(x['net'])>0),D(0)))})
a['chronology_side_buckets']=buckets;a['entry_known_cooldown_screens']=extra;a['profitable_adverse_path_examples']={s:sorted([x for x in rows if x['sym']==s and D(x['net'])>0],key=lambda x:D(x['close_loss_percent_entry_equity']),reverse=True)[:3] for s in ['BTC','SOL']}
(p/'asset-risk.json').write_text(json.dumps(a,indent=2)+'\n')
with (p/'chronology-direction.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(buckets[0]),lineterminator='\n');w.writeheader();w.writerows(buckets)
print(json.dumps({'buckets':buckets,'cooldown':extra,'winning_adverse':a['profitable_adverse_path_examples']},indent=2))
