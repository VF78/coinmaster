"""Tiny invented observer records test verifier predicates only; no engine/PnL data."""
from pathlib import Path
import runpy,copy,json
validate=runpy.run_path(str(Path(__file__).with_name('verifier-c1-witness-adjudicated.py')))['validate_c1']
base=dict(btc_targets={'0':10},btc_filled={'0':0},btc_retired={'0':0},sol_rights=[0],sol_right_fraction={'0':1},sol_held_lots={},sol_consumed={},PLANREF='100',H='1000')
retired=copy.deepcopy(base);retired['btc_retired']['0']=5
rows=[]
def add(event,ns,**kw):rows.append(dict(event=event,timestamp_ns=ns,group='g',sequence=len(rows)+1,**kw))
add('PROPOSED_DECISION',1,source_quote_ns=0,receipt_ns=1,fill_epoch=0,E='60',H='100',DD='.4',cushion='10',selected='BTCUSDT-PERP.P1SIM',selected_loss='20',positions=[dict(instrument_id='BTCUSDT-PERP.P1SIM',side='2')],gates=dict.fromkeys(['parent_complete','no_competing_owner','checkpoint_epoch','open_loss_dominates','native_half_exists'],True))
add('CLAIM',1,frozen_held_lots=10,frozen_target_lots=5)
common=dict(instrument='BTCUSDT-PERP.P1SIM',side=-1,original_side=1,step='.001',bid='100',ask='100',quote_ns=2,E='60',H='100',DD='.4',source_quote_ns=0,receipt_ns=1,fill_epoch=0,current_fill_epoch=0,account_event_ns=0,pending_ids=[],native_open_orders=0,native_inflight_orders=0,queued_intents=0,native_admission='REDUCE_ONLY_BYPASS')
add('ATTEMPT_SUBMIT',2,kind='CUT',intent_id='i1',lots=5,**common)
add('NATIVE_ORDER_SUBMITTED',2,kind='CUT',intent_id='i1',order_id='o1')
add('NATIVE_FILL_RECEIPT',2,intent_id='i1',order_id='o1',trade_id='t1',quantity='.005',price='100',commission='.0001 USDT')
add('ACTUAL_FILL',2,kind='CUT',intent_id='i1',lots=5,price='100',credit_before=0,credit=5,bucket={'0':5},rights_before=base,rights_after=retired,cut_attempts=1,restore_attempts=0)
add('ATTEMPT_TERMINAL',2,kind='CUT',intent_id='i1',credit=5)
add('SUBMIT_OUTCOME',2,intent_id='i1',native_submitted=True,order_id='o1')
close=14_400_000_000_003
add('CLOSED_4H_RECLAIM',close,open_ns=3,close='101',DD='.3')
common.update(side=1,bid='101',ask='101',quote_ns=close+1,E='70',DD='.3',source_quote_ns=close-1,receipt_ns=close,fill_epoch=1,current_fill_epoch=1,account_event_ns=close-1,native_admission='PASSED_EXISTING_INCREASE_GATES',cut_actual_vwap='100')
add('ATTEMPT_SUBMIT',close+1,kind='RESTORE',intent_id='i2',lots=5,confirmation=dict(close_ns=close),**common)
add('NATIVE_ORDER_SUBMITTED',close+1,kind='RESTORE',intent_id='i2',order_id='o2')
add('NATIVE_FILL_RECEIPT',close+1,intent_id='i2',order_id='o2',trade_id='t2',quantity='.005',price='101',commission='.0002 USDT')
add('ACTUAL_FILL',close+1,kind='RESTORE',intent_id='i2',lots=5,price='101',credit_before=5,credit=0,bucket={'0':0},rights_before=retired,rights_after=base,cut_attempts=1,restore_attempts=1)
add('ATTEMPT_TERMINAL',close+1,kind='RESTORE',intent_id='i2',credit=0)
add('SUBMIT_OUTCOME',close+1,intent_id='i2',native_submitted=True,order_id='o2')
add('TERMINAL_FLAT_CONFIRMED',close+2,native_positions=0,native_orders=0,native_inflight=0,pending=0,queued=0)
d={'c1_audit':rows,'c1_terminal_state':dict(native_positions=0,native_orders=0,native_inflight=0,pending=0,queued=0,credit=0,active_hold=False)}
orders=[dict(client_order_id='o1',filled_qty='.005',commissions="['.0001 USDT']",is_reduce_only='True'),dict(client_order_id='o2',filled_qty='.005',commissions="['.0002 USDT']",is_reduce_only='False')]
checks={};r=validate(d,orders);checks['synthetic_cut_restore_PASS']=r['status']=='PASS'
for name,index,key,val in [('wrong_credit',5,'credit',6),('stale_epoch',9,'current_fill_epoch',2),('bad_current_reclaim',9,'ask','99'),('repeat_native_attempt',10,'kind','CUT')]:
 bad=copy.deepcopy(d);bad['c1_audit'][index][key]=val;got=validate(bad,orders);checks[name+'_rejected']=got['status']=='FAIL'
bad=copy.deepcopy(d);bad['c1_audit'][9].pop('bid');checks['missing_currentquote_NOT_PROVEN']=validate(bad,orders)['status']=='NOT_PROVEN'
assert all(checks.values()),(checks,r)
print(json.dumps({'status':'PASS','synthetic_verifier_only':True,'native_engines':0,'old_traces':0,'checks':checks},indent=2))

helper=runpy.run_path(str(Path(__file__).with_name('verifier-c1-witness-adjudicated.py')))['exact_native_domain_price']
assert helper('103604.09999999999','103604.1')
assert helper('64840.19999999999','64840.2')
assert not helper('103604.0999999999','103604.1')
print('Exact pinned native float transform cases PASS; arbitrary price perturbation rejected')
