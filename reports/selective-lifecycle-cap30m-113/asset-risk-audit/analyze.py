"""One read-only native observation pass; no price-path or counterfactual simulation."""
import bisect,csv,gzip,json,hashlib
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
b=Path('reports/selective-lifecycle-cap30m-113');o=b/'asset-risk-audit'
a=json.loads((b/'audit/findings.json').read_text())['variant']
r=json.load(gzip.open(b/'native-result.json.gz','rt'))
trace=Path('/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-minute-extrema-risk-20261010/result/minute-native-risk.csv.gz')
exits=list(csv.DictReader((b/'audit/economics.csv').open()))
eps={s:[dict(e,events=[],cash_component=D(0),minimum_close=D(0),minimum_adverse=D(0),samples=0,max_exposure=D(0),entry_equity=None,maximum_close=D(0),maximum_adverse=D(0),peak_giveback_close=D(0),peak_giveback_adverse=D(0),crossings={},age_snapshots={}) for e in a['episodes'][s]] for s in ['BTC','SOL']}
starts={s:[int(e['start_ns']) for e in v] for s,v in eps.items()}
for x in exits:
 e=eps[x['sym']][int(x['episode'])-1];e['events'].append((int(x['ns']),D(x['gross'])-D(x['exit_fee'])))
for f in r['fill_audit']:
 if f['action'] not in ['BTC_ENTRY','SOL_ADD']:continue
 s='BTC' if f['action']=='BTC_ENTRY' else 'SOL';i=bisect.bisect_right(starts[s],int(f['fill_ns']))-1;e=eps[s][i]
 assert int(e['start_ns'])<=int(f['fill_ns'])<=int(e['end_ns'])
 e['events'].append((int(f['fill_ns']),-D(f['commission'])))
for v in eps.values():
 for e in v:
  e['events'].sort();e['event_index']=0
  assert sum((x[1] for x in e['events']),D(0))==D(e['net'])
count=0;paired={'both_minutes':0,'opposite_signed_pnl_minutes':0,'both_negative_minutes':0,'net_positive_minutes':0,'net_negative_minutes':0}
for row in csv.DictReader(gzip.open(trace,'rt')):
 if row['phase']!='pre_quote_paired_close':continue
 count+=1;ns=int(row['close_available_ns']);eq=D(row['paired_close_equity']);parts=json.loads(row['native_positions_and_mark_ohlc_json']);pnlparts=[]
 for p in parts:
  s='BTC' if p['instrument_id'].startswith('BTC') else 'SOL';i=bisect.bisect_left(starts[s],ns)-1
  if i<0:continue
  e=eps[s][i]
  if not int(e['start_ns'])<ns<=int(e['end_ns']):continue
  while e['event_index']<len(e['events']) and e['events'][e['event_index']][0]<ns:
   e['cash_component']+=e['events'][e['event_index']][1];e['event_index']+=1
  # Instrument price precision equals observed native endpoints: BTC 0.1 SOL 0.01.
  step=D('0.1' if s=='BTC' else '0.01');bar=p['mark_ohlc'];lo,hi,cl=[(D(bar[k])/step).quantize(D(1))*step for k in ['low','high','close']]
  lp,hp=D(p['low_native_pnl']),D(p['high_native_pnl']);close=lp if lo==hi else lp+(cl-lo)/(hi-lo)*(hp-lp)
  adverse=min(lp,hp);pathclose=e['cash_component']+close;pathadverse=e['cash_component']+adverse
  if e['entry_equity'] is None:e['entry_equity']=eq;e['entry_snapshot_ns']=ns;e['entry_gross_exposure']=D(p['quantity'])*cl/eq
  exposure=D(p['quantity'])*cl/eq;e['max_exposure']=max(e['max_exposure'],exposure);e['samples']+=1;pnlparts.append(close)
  e['maximum_close']=max(e['maximum_close'],pathclose);e['maximum_adverse']=max(e['maximum_adverse'],pathadverse)
  for typ,val in [('close',pathclose),('adverse',pathadverse)]:
   giveback=e['maximum_'+typ]-val
   if giveback>e['peak_giveback_'+typ]:e['peak_giveback_'+typ]=giveback;e['peak_giveback_'+typ+'_ns']=ns;e['peak_giveback_'+typ+'_from']=e['maximum_'+typ];e['peak_giveback_'+typ+'_to']=val
   for threshold in [20,30,40]:
    key=typ+'_'+str(threshold)
    if key not in e['crossings'] and val<=-e['entry_equity']*D(threshold)/100:
     e['crossings'][key]={'timestamp_ns':ns,'utc':datetime.fromtimestamp(ns/1e9,timezone.utc).isoformat(),'current_episode_pnl':str(val),'current_native_equity':str(eq),'subsequent_observed_outcome_difference':str(D(e['net'])-val)}
  if s=='SOL':
   for day in [3,5,7,10]:
    if str(day) not in e['age_snapshots'] and ns-int(e['start_ns'])>=day*86400*10**9:
     e['age_snapshots'][str(day)]={'timestamp_ns':ns,'utc':datetime.fromtimestamp(ns/1e9,timezone.utc).isoformat(),'current_episode_pnl':str(pathclose),'current_native_equity':str(eq),'adverse_episode_pnl':str(pathadverse),'subsequent_observed_outcome_difference':str(D(e['net'])-pathclose)}

  for name,value in [('close',pathclose),('adverse',pathadverse)]:
   if value<e['minimum_'+name]:
    e['minimum_'+name]=value;e['minimum_'+name+'_ns']=ns;e['minimum_'+name+'_equity']=eq;e['minimum_'+name+'_held_pnl']=close if name=='close' else adverse;e['minimum_'+name+'_cash_component']=e['cash_component']
 if len(pnlparts)==2:
  paired['both_minutes']+=1
  paired['opposite_signed_pnl_minutes']+=int(pnlparts[0]*pnlparts[1]<0);paired['both_negative_minutes']+=int(all(x<0 for x in pnlparts));paired['net_positive_minutes']+=int(sum(pnlparts)>0);paired['net_negative_minutes']+=int(sum(pnlparts)<0)
assert count==1051200
rows=[]
for s,v in eps.items():
 for e in v:
  assert e['samples']>0
  x={k:e[k] for k in ['sym','episode','start','end','side','net','gross','fees','entry_notional','entry_count','exit_count','samples']}
  for k in ['entry_equity','entry_gross_exposure','max_exposure','minimum_close','minimum_adverse']:x[k]=str(e[k])
  for k in ['close','adverse']:
   x[k+'_loss_percent_entry_equity']=str(max(D(0),-e['minimum_'+k])/e['entry_equity']*100)
   x[k+'_trough_utc']=datetime.fromtimestamp(e.get('minimum_'+k+'_ns',int(e['start_ns']))/1e9,timezone.utc).isoformat()
  x['minimum_close_cash_component']=str(e.get('minimum_close_cash_component',0));x['minimum_close_held_pnl']=str(e.get('minimum_close_held_pnl',0))
  for k in ['maximum_close','maximum_adverse','peak_giveback_close','peak_giveback_adverse']:x[k]=str(e[k])
  x['maximum_cumulative_including_final_net']=str(max(e['maximum_close'],D(e['net'])))
  for typ in ['close','adverse']:
   x['giveback_'+typ+'_utc']=datetime.fromtimestamp(e.get('peak_giveback_'+typ+'_ns',int(e['start_ns']))/1e9,timezone.utc).isoformat()
   x['giveback_'+typ+'_from']=str(e.get('peak_giveback_'+typ+'_from',0));x['giveback_'+typ+'_to']=str(e.get('peak_giveback_'+typ+'_to',0))
  x['crossings_json']=json.dumps(e['crossings'],separators=(',',':'));x['age_snapshots_json']=json.dumps(e['age_snapshots'],separators=(',',':'));rows.append(x)
with (o/'episode-paths.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
screens=[];stats={}
for s in eps:
 rr=[x for x in rows if x['sym']==s];loss=[x for x in rr if D(x['net'])<0];win=[x for x in rr if D(x['net'])>0]
 streak=longest=0
 for x in rr:streak=streak+1 if D(x['net'])<0 else 0;longest=max(longest,streak)
 loss_sum=sum((D(x['net']) for x in loss),D(0));worst=sorted(loss,key=lambda x:D(x['net']))
 stats[s]={'episodes':len(rr),'losers':len(loss),'winners':len(win),'negative_net_sum':str(loss_sum),'positive_net_sum':str(sum((D(x['net']) for x in win),D(0))),'worst3_loss_share_percent':str(sum((D(x['net']) for x in worst[:3]),D(0))/loss_sum*100),'longest_consecutive_losing_episodes':longest,'worst3':worst[:3]}
 for typ,thresholds in [('close_loss_percent_entry_equity',[20,30,40]),('adverse_loss_percent_entry_equity',[20,30,40]),('entry_gross_exposure',[6,9,12])]:
  for t in thresholds:
   hit=[x for x in rr if D(x[typ])>=t];hl=[x for x in hit if D(x['net'])<0];hw=[x for x in hit if D(x['net'])>0]
   screens.append({'symbol':s,'screen':typ,'threshold':t,'hit_episodes':len(hit),'losers_covered':len(hl),'loser_count':len(loss),'winning_false_positive_episodes':len(hw),'winner_count':len(win),'hit_loser_final_net_sum':str(sum((D(x['net']) for x in hl),D(0))),'hit_winner_final_net_at_risk':str(sum((D(x['net']) for x in hw),D(0)))})
with (o/'threshold-screens.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(screens[0]),lineterminator='\n');w.writeheader();w.writerows(screens)
result={'asset_stats':stats,'screens':screens,'paired_exposure':paired,'basis':'Confirmed-fill gross minus actual incurred native fees plus native held-PnL endpoint interpolation. Prequote snapshots apply fills strictly earlier than timestamp. First held native snapshot equity is denominator, not exact decision equity. Conditional adverse uses perasset OHLC endpoint; no synchronized joint path. Excludes unallocated signed funding. Descriptive screens are not stop execution or counterfactual ROI. Winner final net at risk includes full completed episode, not future PnL after trigger.','trace':str(trace),'trace_prequote_rows':count,'reconciliation':{s:str(sum((D(e['net']) for e in eps[s]),D(0))) for s in eps}}
result={**json.loads((o/'asset-risk.json').read_text()),**result};result['trace_pass_count']=2;result['basis']+=' First-held exposure can be tiny first partial fill and is not full intended admission or add-time exposure.';(o/'asset-risk.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'stats':stats,'screens':screens,'paired':paired},indent=2))
