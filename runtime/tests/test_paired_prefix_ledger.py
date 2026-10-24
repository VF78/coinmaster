"""Engine-free durable physical/logical budget tests; never the live ledger."""
import json
import pytest
from coinmaster.research.paired_prefix_run import PROTOCOL_SHA,SLOTS,claim_attempt,finish_attempt


def new_ledger(tmp_path):
    p=tmp_path/'ledger.json'
    p.write_text(json.dumps(dict(physical_prefix_max=4,full_max=0,protocol_sha256=PROTOCOL_SHA,
        physical_started=0,physical_completed=0,slots=[dict(slot=n,name=v,status='NOT_STARTED') for n,v in SLOTS.items()])))
    return p


def freeze(slot,source='a'):
    return dict(internal_go=True,independent_review='PASS',launch_gates='PASS',protocol_sha256=PROTOCOL_SHA,
        full_max=0,source_commit=source,monetary_source_identity=source,logical_slot=slot,
        concrete_correction_reserve_reason='single concrete correction after failed OFF' if slot==4 else None)


def test_failed_off_reserve_immediate_then_matched_b2_combined_max_four(tmp_path):
    p=new_ledger(tmp_path)
    first=claim_attempt(p,freeze(1),'OFF',tmp_path/'first')
    finish_attempt(p,first,'FAILED',{'error':'preserved launch failure'})
    reserve=claim_attempt(p,freeze(4,'b'),'OFF',tmp_path/'reserve')
    finish_attempt(p,reserve,'COMPLETED',{})
    b2=claim_attempt(p,freeze(2,'b'),'B2',tmp_path/'b2')
    finish_attempt(p,b2,'COMPLETED',{})
    combined=claim_attempt(p,freeze(3,'b'),'B2_F0',tmp_path/'combined')
    finish_attempt(p,combined,'FAILED',{'error':'export failure also counts'})
    r=json.loads(p.read_text())
    assert r['physical_started']==4 and r['physical_completed']==2
    assert [a['physical_index'] for a in r['attempts']]==[1,2,3,4]
    assert [a['logical_slot'] for a in r['attempts']]==[1,4,2,3]
    assert r['attempts'][0]['detail']['error']=='preserved launch failure'
    with pytest.raises(ValueError,match='BUDGET_EXHAUSTED'):
        claim_attempt(p,freeze(4,'b'),'B2_F0',tmp_path/'extra')


def test_missing_root_go_unmatched_source_and_concurrent_owner_block_before_count(tmp_path):
    p=new_ledger(tmp_path);f=freeze(1);f['internal_go']=False
    with pytest.raises(ValueError,match='ROOT_INTERNAL_GO'):
        claim_attempt(p,f,'OFF',tmp_path/'no-go')
    a=claim_attempt(p,freeze(1),'OFF',tmp_path/'off')
    with pytest.raises(ValueError,match='ALREADY_RUNNING'):
        claim_attempt(p,freeze(2),'B2',tmp_path/'busy')
    finish_attempt(p,a,'COMPLETED',{})
    with pytest.raises(ValueError,match='MATCHED_COMPLETED_OFF'):
        claim_attempt(p,freeze(2,'different-money'),'B2',tmp_path/'unmatched')
    assert json.loads(p.read_text())['physical_started']==1
