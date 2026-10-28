"""Prospective M3-CODE0 assertions. Stdlib validation only; launch NOT_READY."""
from decimal import Decimal as D
from pathlib import Path
import json,hashlib


def validate_data(path):
    case=json.loads(Path(path).read_text());rows=case['rows']
    assert case['native_authority']==0 and case['research_method_a_recovery_code0'] is True
    assert case['cancel_latency_ns']==2_000_000_000
    assert all(a['ns']<b['ns'] for a,b in zip(rows,rows[1:]))
    quotes=[];epochs={'BTC':0,'SOL':0}
    for row in rows:
        assert set(row.get('marks',{}))=={'BTC','SOL'}
        for q in row.get('quotes',[]):
            for k in ('bid','ask','bid_depth','ask_depth'):assert D(q[k])>0
            assert D(q['bid'])<=D(q['ask'])
            epochs[q['asset']]+=1
            quotes.append(dict(global_input_index=len(quotes)+1,native_input_epoch=epochs[q['asset']],asset=q['asset'],ns=row['ns'],quote=q))
    return dict(quote_universe=epochs,global_input_list=quotes,native_authority=0)


def assert_code0_partial_receipt(native_order,fill_events,expected_initial_qty):
    assert native_order['type']=='LIMIT' and native_order['time_in_force']=='IOC'
    assert native_order['is_reduce_only'] and native_order['side']=='BUY'
    assert D(native_order['price'])==D('133.03') and D(native_order['quantity'])==D(expected_initial_qty)
    assert native_order['status']=='CANCELED' and D(native_order['filled_qty'])==D('.1')
    assert sum((D(e['last_qty']) for e in fill_events),D(0))==D('.1')
    assert all(D(e['last_px'])<=D('133.03') for e in fill_events)


def assert_fresh_barrier(receipt,boundary,expected_input):
    raw=receipt['native_receipt_snapshot']
    assert boundary['event']=='SOL_NATIVE_BOUNDARY' and boundary['label']=='BEFORE_NATIVE_MATCHING_INPUT'
    assert boundary['timestamp_ns']==receipt['timestamp_ns']==expected_input['ns']
    assert boundary['parent']==raw['parent'] and boundary['risk_episode_id']==raw['risk_episode_id']
    assert int(receipt['sequence'])==int(raw['risk_sequence_before_receipt'])+1
    assert receipt['native_input_epoch']==expected_input['native_input_epoch']
    assert receipt['global_input_index']==expected_input['global_input_index']
    assert raw['raw_native_queue_visibility']=='NOT_EXPOSED_BY_PUBLIC_API'


def launch(*args,**kwargs):
    raise RuntimeError('NOT_READY_NATIVE0: exact original M3 adapter/second-parent sizing and new allocation require review; never call old root launch')

if __name__=='__main__':
    print(json.dumps(validate_data(Path(__file__).with_name('M3_CODE0_DATA_PROSPECTIVE.json')),indent=2))
