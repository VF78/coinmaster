import json,csv,hashlib,statistics,collections,os
from decimal import Decimal as D
b='/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021/reports/btc-sol-causal-modules-20261022/'
p='/tmp/btc-audit-exact-s0-direction.json';digest=hashlib.sha256(open(p,'rb').read()).hexdigest();assert digest=='e7854784dce9bcf27e77d45ebe12873d78a42a0ecb43b3686f2a0da810fb2bfa'
n=json.load(open(p));h=json.load(open(b+'h3-feasibility.json'));parents=sorted(n['split_cover_audit']['parents'],key=lambda z:int(z['start_ns']));rows=[]
for r in h['rows']:
 num=r['trade_number'];st=int(parents[num-1]['start_ns']);stop=int(parents[num]['start_ns']) if num<105 else 10**30;act=bool(r.get('strict_next_close_before_original_exit',False));rr={'trade_number':num,'side':r['side'],'activation_ns':r['activation_fill_ns'],'winner_ex_funding':r['winner_ex_funding'],'H3_action':act,'P0':str(r['P0']),'conditional_trim_reference_ns':r.get('conditional_trim_reference_ns'),'conditional_trim_reference_price':r.get('conditional_trim_reference_price'),'trigger_status':r['trigger_status']}
 if act:
  ref_ns=int(r['conditional_trim_reference_ns']);price=D(str(r['conditional_trim_reference_price']));p0=D(str(r['P0']));side=D(1 if r['side']=='LONG' else -1)
  allouts=[z for z in n['fill_audit'] if z['instrument'].startswith('BTC') and z['action']!='BTC_ENTRY' and st<=int(z['fill_ns'])<stop];outs=sorted([z for z in allouts if int(z['fill_ns'])>ref_ns],key=lambda z:int(z['fill_ns']));assert outs
  rr['ordinary_fills_at_conditional_trim_timestamp']=sum(int(z['fill_ns'])==ref_ns for z in allouts)
  for label,z in [('primary_next_ordinary',outs[0]),('secondary_final_original',outs[-1])]:
   px=D(z['px']);fee=D(z['commission'])/D(z['qty']);benefit=(side*(price-px)+fee-D('.00055')*price)/p0
   rr.update({label+'_ns':int(z['fill_ns']),label+'_reason':z['reason'],label+'_endpoint_px':str(px),label+'_endpoint_native_fee_per_unit':str(fee),label+'_native_fill_qty':z['qty'],label+'_same_timestamp_fill_count':sum(int(v['fill_ns'])==int(z['fill_ns']) for v in outs),label+'_benefit_percent':float(benefit*100)})
 else:
  for label in ['primary_next_ordinary','secondary_final_original']:rr[label+'_benefit_percent']=0.
 rows.append(rr)
def summ(rs,label):
 v=[r[label+'_benefit_percent'] for r in rs]
 return {'opportunities':len(v),'event_weighted_mean_percent':sum(v)/len(v) if v else None,'median_percent':statistics.median(v) if v else None,'positive':sum(z>0 for z in v),'negative':sum(z<0 for z in v),'zero':sum(z==0 for z in v)}
summary={}
for label in ['primary_next_ordinary','secondary_final_original']:
 summary[label]={'all28':summ(rows,label),'actions10':summ([r for r in rows if r['H3_action']],label),'original_winning_actions2':summ([r for r in rows if r['H3_action'] and r['winner_ex_funding']],label),'original_losing_actions8':summ([r for r in rows if r['H3_action'] and not r['winner_ex_funding']],label)}
mean=summary['primary_next_ordinary']['all28']['event_weighted_mean_percent'];status='POSITIVE_ENDPOINT_PRICE_COST_PROXY_FEASIBILITY_ONLY_NOT_NATIVE_GO' if mean>0 else 'PRECHECK_NO_ECONOMIC_GO'
x={'status':status,'primary_endpoint':'NEXT original actual ordinary BTC fill STRICTLY AFTER conditional trim next1mclose reference; original fills at same timestamp separatelyflagged; audit stable order breaks ties','secondary_endpoint':'FINAL original actual exitfill after conditionaltrim, sensitivity ONLY; cannot rescue failedprimary','formula':'Per theoretical reducedunit normalizedP0: [side*(conditional_trim_reference_px-original_endpoint_px)+original_endpoint_native_commission/qty-.00055*conditional_trim_reference_px]/P0. Common entryfees cancel. Noaction=0. All28activation opportunities equallyweighted; no qty/notional/capital weights or compounding.','source_pins':{'h3_feasibility_sha256':hashlib.sha256(open(b+'h3-feasibility.json','rb').read()).hexdigest(),'native_sha256':digest},'summary':summary,'original_winning_counterexamples':[r for r in rows if r['H3_action'] and r['winner_ex_funding']],'rows':rows,'native_runs_added':0,'additional_price_scans':0,'alternative_TOTAL_DD_PnL':'NOT_COMPUTED','limitations':['Benefit is a normalized historical price-cost proxy, not candidate PnL or realizedportfolio effect.','Conditional trim close is not actualcandidatefill, quote or guaranteedexecution; spread/slippage/impact/fundingUNKNOWN.','Original nextfill may applyto a smaller actualnativequantity than hypotheticaltrim; future candidatepartialTPquantities and residualpathUNKNOWN.','Candidatechangescapital/SOLrights/nextpositions; no alternative TOTAL/DD or ROI claim.','H3 cannot actbeforepositive actualTP2; currentDDatcandidateactionUNKNOWN.','Endpointnativecommission perunit included directly; no invented pricepath or extra pricescan.']}
json.dump(x,open(b+'h3-action-cost.json','w'),indent=2,ensure_ascii=False)
fields=list(dict.fromkeys(k for r in rows for k in r))
with open(b+'h3-action-cost.csv','w') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
md=['# H3: endpoint action cost diagnostic','',status,'',x['formula'],'','| Original endpoint |All28 mean %|Actions10 mean %|Positive/negative actions|','|---|---:|---:|---|']
for label,z in summary.items():md.append(f"|{label}|{z['all28']['event_weighted_mean_percent']:.6f}|{z['actions10']['event_weighted_mean_percent']:.6f}|{z['actions10']['positive']}/{z['actions10']['negative']}|")
md+=['','Original winning action counterexamples: '+json.dumps(x['original_winning_counterexamples'],ensure_ascii=False),'','No alternative TOTAL/DD/PnL, no quantity/dollar compounding, no newfills claimed. All28 opportunities retained (18noaction=0), primary original nextfill is not candidateexitfill. Entryfees cancel; actualendpointcommission/qty minus hypotheticaltakerfee used. CurrentDD/intents/futurecandidatequantity/path/funding UNKNOWN. No pricescan/native/replay.']
open(b+'h3-action-cost.md','w').write('\n'.join(md)+'\n');print(json.dumps({'status':status,'summary':summary,'winning_counterexamples':x['original_winning_counterexamples']},indent=2))
