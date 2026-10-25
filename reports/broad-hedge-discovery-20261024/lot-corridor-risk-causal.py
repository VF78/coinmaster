import json,csv,hashlib,sys,collections
from pathlib import Path
from decimal import Decimal as D
r=Path(__file__).parent; variant=sys.argv[1]; name=sys.argv[2]
p=Path('/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/paired-lot-corridor-20261025')/name/'result'
a=json.loads((p/f'paired-prefix-{variant}.json').read_text()); x=json.loads((r/f'lot-corridor-risk-{variant}.json').read_text());off=json.loads((r/'lot-corridor-risk-OFF.json').read_text())
events=a['paired_prefix_audit']['events'];orders={v['client_order_id']:v for v in csv.DictReader((p/f'paired-prefix-{variant}-orders.csv').open())}
snap={(v['native_id'],v['kind']):v for v in x['mutation_snapshots']}
def qty(row,asset):return sum((D(v['quantity']) for v in row['positions'] if asset in v['instrument_id']),D(0))
proof=[];caps=[];debts=[];activation=None; pending_debt=None;last_cap=None;unexpected=[]; native_matches=[]; csv_price_metadata_residuals=[]
for i,e in enumerate(events):
 if e['event']=='ACTIVATION_SELECTED':
  activation=e; pending_debt=None;last_cap=None
 if e['event']=='ACTUAL_BTC_DEBT_OPEN':pending_debt=e
 if e['event']!='ACTUAL_FILL':continue
 o=orders[e['order_id']]; tid=o['last_trade_id']; pre=snap[(tid,'PRE_FILL_LAST_COMMITTED_NATIVE_COPY')];post=snap[(tid,'POST_FILL_COMMITTED_NATIVE')]
 actual_price_matches=[z for z in a['fill_audit'] if z['fill_ns']==e['timestamp_ns'] and z['action']=='PAIRED_'+e['kind'] and D(z['qty'])==D(e['qty']) and D(z['px'])==D(e['price'])]
 native_matches.append(D(e['qty'])==D(o['filled_qty']) and len(actual_price_matches)==1 and int(e['timestamp_ns'])==int(pre['event_ns'])==int(post['event_ns']))
 if D(e['price'])!=D(o['avg_px']):csv_price_metadata_residuals.append({'order_id':e['order_id'],'native_fill_px':e['price'],'csv_order_avg_px':o['avg_px'],'difference':str(D(o['avg_px'])-D(e['price'])),'actual_fill_audit_exact_match_count':len(actual_price_matches)})
 u=int(D(activation['intended_sol'])/D('.1'));v=int(D(activation['qref'])/D('.001')); bpre=qty(pre,'BTC');bpost=qty(post,'BTC');spre=qty(pre,'SOL');spost=qty(post,'SOL'); bmax=D(e['bmax']); bcoverage=D((int(spost/D('.1'))*v)//u)*D('.001')
 if e['kind']=='BTC_DEBT':
  cause=[z for z in events[:i] if z['event']=='ACTUAL_FILL' and z['kind'] in ['TP','STOP','SOL_CAP','SOL_CLOSE'] and int(z['timestamp_ns'])>=int(activation['timestamp_ns'])][-1:]
  z={'order_id':e['order_id'],'trade_id':tid,'cause_order_id':cause[0]['order_id'] if cause else None,'cause_kind':cause[0]['kind'] if cause else None,'native_pre_btc':str(bpre),'native_post_btc':str(bpost),'actual_fill_qty':e['qty'],'bmax':e['bmax'],'matches_true_debt':bpre-bmax==D(e['qty']) and bpost==bmax,'debt_obligation_logged':pending_debt is not None,'latency_ns':int(e['timestamp_ns'])-int(pending_debt['timestamp_ns']) if pending_debt else None}
  debts.append(z)
  if last_cap is not None and z['cause_kind']=='SOL_CAP':unexpected.append(z)
  pending_debt=None
 if e['kind']=='SOL_CAP':
  solceil=D((int(bpost/D('.001'))*u+v-1)//v)*D('.1')
  z={'order_id':e['order_id'],'trade_id':tid,'u':u,'v':v,'native_pre_sol':str(spre),'native_post_sol':str(spost),'native_btc':str(bpost),'bmax':str(bmax),'sol_cap_ceil':str(solceil),'btc_coverage_floor_after':str(bcoverage),'actual_fill_qty':e['qty'],'correct_full_excess_fill':spre-solceil==D(e['qty']) and spost==solceil,'no_new_btc_debt_from_filled_cap':bcoverage>=bmax and bpost<=bmax}
  caps.append(z);last_cap=e
 if e['kind'] not in ['SOL_CAP','BTC_DEBT']:last_cap=None
checks={'actual_audit_fill_matches_native_order_trade_snapshot':all(native_matches),'all_debt_obligations_and_full_real_fills':all(z['matches_true_debt'] and z['debt_obligation_logged'] and 0<=z['latency_ns']<=60000000000 for z in debts),'all_sol_caps_exact_ceil_stable':all(z['correct_full_excess_fill'] and z['no_new_btc_debt_from_filled_cap'] for z in caps),'no_spurious_debt_after_sol_cap':not unexpected,'all_actual_activations_closed':sum(e['event']=='ACTIVATION_SELECTED' for e in events)==sum(e['event']=='PARENT_NATIVE_TERMINAL_FLAT' for e in events),'no_failures_or_open_owner':not a['paired_prefix_audit']['failures'] and not a['paired_prefix_audit']['open_owner']}
fees=sum((D(z['commission']) for z in a['fill_audit'] if z['instrument'].startswith('SOL') or z['action']=='PAIRED_BTC_DEBT'),D(0));gain=D(x['terminal_total'])-D(off['terminal_total'])
out={'variant':variant,'status':'NO_GO_ACTUAL_QUALIFICATION_FAILURE' if a['paired_prefix_audit']['failures'] else 'PASS' if all(checks.values()) else 'UNKNOWN','checks':checks,'csv_order_avg_px_metadata_residuals':csv_price_metadata_residuals,'actual_paired_fill_counts':dict(collections.Counter(e['kind'] for e in events if e['event']=='ACTUAL_FILL')),'actual_debt_obligations':sum(e['event']=='ACTUAL_BTC_DEBT_OPEN' for e in events),'debts':debts,'caps':caps,'economic_attribution':{'ratio_to_matched_OFF':str(D(x['terminal_total'])/D(off['terminal_total'])),'incremental_gain':str(gain),'actual_SOL_plus_BTC_paired_trim_fees':str(fees),'cost_gate':gain>2*fees,'capital_2x_gate':D(x['terminal_total'])>=2*D(off['terminal_total']),'settled_DD_gate':D(x['settled_DD_percent'])<=50 and D(off['settled_DD_percent'])-D(x['settled_DD_percent'])>=5,'event_DD_gate':D(x['event_DD_percent'])<=50,'daily_tail_gate':D(x['daily_ES20'])<=D(off['daily_ES20']),'parent_tail_gate':D(x['parent_ES20'])<=D(off['parent_ES20'])},'engine_instances_created':0,'additional_stream_reads':0,'basis':'Actual native cache snapshots linked by order last_trade_id/native_id; quantities never replayed/reconstructed. Single-fill order totals checked against actual audit fill. Partial/late fills would require separate native fill proof and cannot be blanket ignored.'}
(r/f'lot-corridor-risk-{variant}-causal.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ['debts','caps']},indent=2))
