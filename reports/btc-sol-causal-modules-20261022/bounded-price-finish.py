"""Summarize saved collector output only; never computes alternative PnL/equity."""
import json,csv,collections,hashlib,statistics,os
from decimal import Decimal
B=os.path.dirname(os.path.abspath(__file__))+'/'
x=json.load(open(B+'h1-precheck.bounded-result.json'))
ledger={int(r['trade_number']):r for r in csv.DictReader(open(B+'../winner-6077107-stats/trades-ledger.csv')) if r['asset']=='BTC'}
first50=json.load(open(B+'../s0-weekly-postmortem-20261022/candidate-precheck.json'))['first_global_DD50']['receipt_ns']
script=B+'bounded-price-collector.py'
def quant(v):
 s=sorted(v)
 if not s:return {'n':0}
 def q(p):
  a=(len(s)-1)*p;i=int(a);return s[i]+(s[min(i+1,len(s)-1)]-s[i])*(a-i)
 return dict(n=len(s),median=q(.5),p75=q(.75),p90=q(.9),max=s[-1],min=s[0])
def output(name,data,md):
 with open(B+name+'.json','w') as f:json.dump(data,f,indent=2,ensure_ascii=False)
 rows=data['rows'];fields=list(dict.fromkeys(k for r in rows for k in r))
 with open(B+name+'.csv','w') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 open(B+name+'.md','w').write(md+'\n')
common={k:x[k] for k in ['status','native_runs_added','alternative_TOTAL_DD_PnL','market_source','native_source','timestamp_contract','elapsed_seconds','peak_RSS_bytes']}
common.update({'collector_sha256':hashlib.sha256(open(script,'rb').read()).hexdigest(),'S0_TOTAL_control':'6077107.23887483','outcome_labels':'Original actual-fill diagnostic net ex funding, not native per-asset cash or prospective outcome.','limitations':['All candidate action prices are historical close references, not guaranteed fills or executable quotes.','Actual original ordinary fill is only an upperbound; prior intent/orderbusy eligibility UNKNOWN.','After a candidate entry/trim, native capital, quantities, TP and SOL rights change; no alternative equity/PnL/DD computed.','No threshold grid, fit, engine, replay or native run.']})
h1=x['h1_rows']
for r in h1:
 l=ledger[r['trade_number']];r['winner_ex_funding']=Decimal(l['net_ex_funding'])>0;r['month']=l['entry_utc'][:7]
sum1={'intervals':len(h1),'touch_order':dict(collections.Counter(r['touch_order'] for r in h1)),'conditional_add_reference':sum(r['next_close_within_4h'] for r in h1),'half_only_due_no_valid_add':sum(not r['next_close_within_4h'] for r in h1),'ordinary_fill_censors_before_deadline':sum(r['ordinary_fill_before_native_deadline'] for r in h1),'conditional_add_delay_minutes':quant([r['add_delay_minutes'] for r in h1 if r['next_close_within_4h']]),'price_cost_vs_passive_target_percent_second_half':quant([100*r['directional_price_cost_vs_passive_target_fraction_of_P0'] for r in h1 if r['next_close_within_4h']]),'price_cost_vs_original_second_fill_percent':quant([100*r['directional_price_cost_vs_original_second_fill_fraction_of_P0'] for r in h1 if r['next_close_within_4h']]),'fee_premium_taker_minus_maker_second_notional_fraction':.00035}
for label in [True,False]:
 z=[r for r in h1 if r['winner_ex_funding']==label];sum1['winner' if label else 'loser']={'intervals':len(z),'conditional_add':sum(r['next_close_within_4h'] for r in z),'touch_order':dict(collections.Counter(r['touch_order'] for r in z))}
dead=[r for r in h1 if r['original_completion_reason']=='DEADLINE'];winningdead=[r for r in dead if r['winner_ex_funding']];sum1['original_deadline']={'intervals':len(dead),'winners':len(winningdead),'winning_conditional_add':sum(r['next_close_within_4h'] for r in winningdead)}
months=[]
for month in sorted(set(r['month'] for r in h1)):
 z=[r for r in h1 if r['month']==month];months.append({'month':month,'entries':len(z),'conditional_add':sum(r['next_close_within_4h'] for r in z),'winning_add':sum(r['next_close_within_4h'] and r['winner_ex_funding'] for r in z),'losing_add':sum(r['next_close_within_4h'] and not r['winner_ex_funding'] for r in z)})
a={**common,'hypothesis':'H1 favorable .25% secondhalf confirmation within EXACT original native parentdeadline; expirywins at equality; firsthalf unchanged; no add=finalizepartial','summary':sum1,'months':months,'BTC97_103':[r for r in h1 if 97<=r['trade_number']<=103],'winning_deadline_counterexamples':winningdead,'half_only_control':'105 unchanged firsthalves, noadd; pathselectioncontrol only, economics UNKNOWN','rows':h1}
md='# H1: bounded saved-price precheck\n\nAnalysis only; native runs0; alternative TOTAL/DD/PnL not computed.\n\n'+json.dumps(sum1,indent=2)+'\n\nExact parentdeadline, expiry equalityexcluded; close triggers strictly after first-half terminal. Ordinary actual fill truncates window; intent eligibilityUNKNOWN. All reference prices are next1mclose, not guaranteed fills. Original winner labels are diagnostic ex funding. BTC97–103 and all winning deadline cases are retained individually in JSON/CSV. Half-only control is selection only, not alternative equity.\n'
output('h1-precheck',a,md)
h3=x['h3_rows']
for r in h3:
 l=ledger[r['trade_number']];r['winner_ex_funding']=Decimal(l['net_ex_funding'])>0;r['activation_after_first_original_DD50']=r['activation_fill_ns']>=first50;r['trigger_after_first_original_DD50']=r['trigger_ns']>=first50 if r['trigger_ns'] is not None else None;r['current_portfolio_DD_at_trigger']='UNKNOWN_NO_TRACE_RESCAN'
sum3={'actual_positive_TP2_activations':len(h3),'trades':len(set(r['trade_number'] for r in h3)),'triggers':sum(r['trigger_ns'] is not None for r in h3),'strict_next_close_before_original_exit':sum(r.get('strict_next_close_before_original_exit',False) for r in h3),'activated_after_first_historical_DD50':sum(r['activation_after_first_original_DD50'] for r in h3),'activation_to_trigger_hours':quant([r['activation_to_trigger_hours'] for r in h3 if r['trigger_ns'] is not None])}
for label in [True,False]:
 z=[r for r in h3 if r['winner_ex_funding']==label];sum3['winner' if label else 'loser']={'activations':len(z),'triggers':sum(r['trigger_ns'] is not None for r in z)}
a={**common,'hypothesis':'H3 feasibility ONLY','contract':x['h3_contract'],'first_historical_DD50_receipt_ns':first50,'historical_DD50_caveat':'After first historical DD50 does not imply current DD>=50; no receipt scan to infer contemporaneous DD. H3 cannot affect losses before activation.','summary':sum3,'BTC35_43_67':[r for r in h3 if r['trade_number'] in [35,43,67]],'rows':h3}
md='# H3: actual-positive-TP2 feasibility\n\nAnalysis only; native0; no alternative portfolio PnL.\n\n'+json.dumps(sum3,indent=2)+'\n\n'+x['h3_contract']+'\n\nActual remaining quantity is read from saved native fills at trigger; half is theoretical request, not candidate fill. Closed4h close maxima exclude preactivation bars. Next1mclose conditional prices do not guarantee execution. Current DD at action isUNKNOWN; comparison to first historical DD50 only establishes chronology, not contemporaneous DD. Generic BTC_REDUCE is not imputed as positive TP2.\n'
output('h3-feasibility',a,md)
print(json.dumps({'H1':sum1,'H3':sum3},indent=2))
