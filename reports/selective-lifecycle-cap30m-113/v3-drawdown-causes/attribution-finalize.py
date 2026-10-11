"""Finalize cached report; reused average/proportional fill attribution, no trace scan."""
import csv,hashlib,json
from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path
p=Path('reports/selective-lifecycle-cap30m-113/v3-drawdown-causes');r=json.load((p/'attribution.json').open())
base=Path(r['provenance']['raw_path']);raw=json.load(base.open())
# Existing audit/economics.csv methodology: confirmed native fills only, weighted
# entry basis and proportional actual entry-fee allocation. Not economic replay.
import pickle
cache=pickle.load(open('/tmp/cm113-v3-attribution-scan-checkpoint.pkl','rb'))
fs=[x for rows in cache['fillgroups'].values() for x in rows];fs.sort(key=lambda x:int(x['fill_ns']))
state={s:{'qty':D(0),'basis':D(0),'entry_fee':D(0),'side':None} for s in ('BTC','SOL')};exits=[];episodecash=defaultdict(lambda:D(0))
for f in fs:
 s=f['symbol'];q=D(f['qty']);price=D(f['px']);fee=D(f['commission']);z=state[s];entry=f['action'] in ('BTC_ENTRY','SOL_ADD');episodecash[(s,f['episode'])]-=fee
 if entry:
  if z['qty']==0:z['side']=f['native_side']
  assert z['side']==f['native_side'];z['basis']+=q*price;z['qty']+=q;z['entry_fee']+=fee
 else:
  assert q<=z['qty'];vwap=z['basis']/z['qty'];allocated=z['entry_fee']*q/z['qty'];gross=(D(1) if z['side']=='BUY' else D(-1))*q*(price-vwap);episodecash[(s,f['episode'])]+=gross
  exits.append({'symbol':s,'episode':f['episode'],'ns':int(f['fill_ns']),'utc':f.get('utc',''),'reason':f['reason'],'quantity':str(q),'price':str(price),'gross_confirmed_fill_attribution':str(gross),'allocated_entry_fee':str(allocated),'exit_fee':str(fee),'net_ex_funding':str(gross-allocated-fee),'client_order_id':f['client_order_id']})
  z['qty']-=q;z['basis']-=q*vwap;z['entry_fee']-=allocated
  if z['qty']==0:z.update(basis=D(0),entry_fee=D(0),side=None)
assert all(z['qty']==0 for z in state.values())
r['callback_cash_timing_diagnostic']={'warning':'Native account callback/cache finalization is asynchronous. Cash at quote callback cannot be classified as realized perasset PnL. First classification guard matched fills, but2.83m cash remained outside fillcallbacks. All such attributed callbackgross/episode results superseded by confirmedfill attribution; native endpointcash/uPnL remains authoritative.','unclassified_callback_cash_residual':r.get('unallocated_cash_residual',r.get('callback_cash_timing_diagnostic',{}).get('unclassified_callback_cash_residual'))}
r.pop('native_callback_events',None);r.pop('unallocated_cash_events',None);r.pop('single_reason_callback_stats',None);r.pop('full_fill_callback_cash_net',None);r.pop('unallocated_cash_residual',None)
for s,eps in r['episodes'].items():
 for ep in eps:
  ep.pop('native_cash_net_ex_unallocated',None);ep.pop('callback_gross',None);ep['confirmed_fill_net_ex_funding']=str(episodecash[(s,ep['number'])])
for e in r['top3']+r['all_global_native_excursions_over50']:
 d=e['decomposition'];peak=e.get('peak',e.get('landmarks',{}).get('peak'));trough=e.get('trough',e.get('landmarks',{}).get('trough'));a,b=peak['ns'],trough['ns'];phase_rank={'pre_quote_paired_close':0,'post_btc_quote_paired_close':1,'post_quote_paired_close':2}
 def inwindow(ns,s):return (a,phase_rank[peak['phase']])<(int(ns),1 if s=='BTC' else 2)<=(b,phase_rank[trough['phase']])
 window=[x for x in exits if inwindow(x['ns'],x['symbol'])];fillwin=[f for f in fs if inwindow(f['fill_ns'],f['symbol'])]
 for s,z in d['assets'].items():
  u=z['native_endpoint_unrealized_change'];closed=[ep for ep in r['episodes'][s] if inwindow(ep['end_ns'],s)];gross=sum((D(f['gross_confirmed_fill_attribution']) for f in window if f['symbol']==s),D(0));fees=sum((D(f['commission']) for f in fillwin if f['symbol']==s),D(0))
  d['assets'][s]={'confirmed_native_fill_gross_attribution':str(gross),'actual_window_fill_fees':str(fees),'confirmed_fill_net_cash_attribution_ex_funding':str(gross-fees),'native_endpoint_unrealized_change':u,'sum_fill_net_and_unrealized_attribution':str(gross-fees+D(u)),'completed_episodes':closed}
 residual=D(d['native_cash_change'])-sum((D(v['confirmed_fill_net_cash_attribution_ex_funding']) for v in d['assets'].values()),D(0));d['unallocated_cash_residual_not_assigned_funding']=str(residual);d.pop('window_callbacks',None);d.pop('boundary_unknown_cash_events',None);d['window_closing_fill_attribution']=window
 assert abs(D(d['equity_change'])-sum((D(v['sum_fill_net_and_unrealized_attribution']) for v in d['assets'].values()),D(0))-residual-D(d['native_unrealized_attribution_residual_change']))<D('.00000001')
stats={}
for s,eps in r['episodes'].items():
 nets=[D(e['confirmed_fill_net_ex_funding']) for e in eps];streak=longest=0
 for n in nets:streak=streak+1 if n<0 else 0;longest=max(longest,streak)
 stats[s]={'episodes':len(eps),'wins':sum(n>0 for n in nets),'losses':sum(n<0 for n in nets),'max_consecutive_losses':longest,'winning_net_sum':str(sum((n for n in nets if n>0),D(0))),'losing_net_sum':str(sum((n for n in nets if n<0),D(0))),'confirmed_fill_net_ex_funding':str(sum(nets,D(0)))}
r['episode_stats']=stats;r['full_confirmed_fill_net_ex_funding']=str(sum(episodecash.values(),D(0)));r['unallocated_native_cash_residual_not_funding']=str(D(r['full_native_cash_gain'])-D(r['full_confirmed_fill_net_ex_funding']))
reasonstats=[]
for s,reason in sorted({(f['symbol'],f['reason']) for f in exits}):
 rows=[f for f in exits if (f['symbol'],f['reason'])==(s,reason)]
 reasonstats.append({'symbol':s,'reason':reason,'closing_fill_rows':len(rows),'gross_confirmed_fill_attribution':str(sum((D(f['gross_confirmed_fill_attribution']) for f in rows),D(0))),'net_ex_funding':str(sum((D(f['net_ex_funding']) for f in rows),D(0))),'allocated_entry_plus_exit_fees':str(sum((D(f['allocated_entry_fee'])+D(f['exit_fee']) for f in rows),D(0))),'net_losing_fill_rows':sum(D(f['net_ex_funding'])<0 for f in rows)})
r['exit_reason_stats']=reasonstats
btcstarts=[e['start_ns'] for e in r['episodes']['BTC']]
import bisect
cohorts=defaultdict(list)
for f in exits:cohorts[(bisect.bisect_right(btcstarts,f['ns']),f['symbol'],f['reason'])].append(f)
r['trail_closing_cohorts']=[{'parent_btc_entry_number':k[0],'symbol':k[1],'reason':k[2],'first_fill_ns':min(x['ns'] for x in vs),'last_fill_ns':max(x['ns'] for x in vs),'orders':len(vs),'net_ex_funding':str(sum((D(x['net_ex_funding']) for x in vs),D(0)))} for k,vs in cohorts.items() if k[2]=='TRAIL']
r['provenance']['method']='Exact native CASH/uPnL endpoints primary. Perasset close-uPnL interpolates native endpoint PnL at instrument-rounded close and reconciles cents. Realized perasset gross/episodes reuse prior audit/economics.csv confirmed-native-fill weighted-entry/proportional-entry-fee attribution; not authoritative native settled pertrade PnL, economic simulation, engine or counterfactual. Native callbackcash classification was discarded due asynchronous account/cache finalization. Signed cash residual remains unallocated, not assigned funding.'
r['checks']['confirmed_fill_quantity_terminal_flat']=True;r['checks']['reconstructed_native_fill_fees_reconciled']=str(sum((D(f['allocated_entry_fee'])+D(f['exit_fee']) for f in exits),D(0)));assert abs(D(r['checks']['reconstructed_native_fill_fees_reconciled'])-D(raw['native_fees']))<D('.00000001')
r['checks']['native_callback_cash_not_used_for_asset_PnL']=True;r['checks']['native_equity_decomposition_with_explicit_residual_exact']=True;r['checks']['window_fill_bounds_use_phase_order_at_same_timestamp']=True
def annotate_sides(value):
 if isinstance(value,dict):
  if 'positions' in value:
   for z in value['positions']:z['side_name']={'2':'LONG','3':'SHORT'}[z['side']]
  for child in value.values():annotate_sides(child)
 elif isinstance(value,list):
  for child in value:annotate_sides(child)
annotate_sides(r)
(p/'attribution.json').write_text(json.dumps(r,indent=2)+'\n');(p/'attribution-checks.json').write_text(json.dumps(r['checks'],indent=2)+'\n')
with (p/'attribution-closing-fills.csv').open('w') as f:
 w=csv.DictWriter(f,lineterminator='\n',fieldnames=list(exits[0]));w.writeheader();w.writerows(exits)
with (p/'attribution-episodes.csv').open('w') as f:
 allrows=r['episodes']['BTC']+r['episodes']['SOL'];w=csv.DictWriter(f,lineterminator='\n',fieldnames=list(allrows[0]));w.writeheader();w.writerows(allrows)
# Preserve the rejected cash-callback method evidence; never delete it.
with (p/'attribution-rejected-callback-method.csv').open('w') as f:
 rows=cache['callbacks'];fields=list(rows[0])+['validity'];w=csv.DictWriter(f,lineterminator='\n',fieldnames=fields);w.writeheader();w.writerows(dict(x,validity='INVALID_PER_ASSET_ATTRIBUTION_CACHE_TIMING') for x in rows)
print(json.dumps({'top3':[{**{k:v for k,v in e['decomposition'].items() if k not in ('assets','window_closing_fill_attribution')},'rank':e['rank'],'assets':{s:{k:v for k,v in a.items() if k!='completed_episodes'} for s,a in e['decomposition']['assets'].items()}} for e in r['top3']],'stats':stats,'trail_cohorts':r['trail_closing_cohorts'],'full_residual':r['unallocated_native_cash_residual_not_funding']},indent=2))
