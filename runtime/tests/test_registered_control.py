"""Engine-free admission tests; native instances are counted by separate harness."""
from copy import deepcopy
from dataclasses import asdict
from decimal import Decimal as D
from inspect import signature
import json
from pathlib import Path
import pytest
from coinmaster.research.registered_control import config_for, validate_config, build_registered_control_kwargs, validate_native_control
from coinmaster.research.paired_prefix_run import build_native_kwargs
from coinmaster.research.native_baseline import run_native_diagnostic
from coinmaster.research.paired_signal_feed import PairedSignal
from coinmaster.research.qualified_warmup import atr_rows,aggregate,H4_MS

@pytest.mark.parametrize('family',['R2','R3'])
def test_exact_actual_kwargs_json_roundtrip_and_native_call_validation(family,tmp_path):
    config=json.loads(json.dumps(config_for(family)))
    kwargs=build_registered_control_kwargs(config,family,tmp_path,tmp_path/'out',(),1725249600000,1725336000000)
    assert kwargs['research_btc_q_mode']==('LEGACY_Q_CONTROL' if family=='R2' else 'CLEAN_Q')
    assert kwargs['research_btc_direction_sizing'] is True
    assert kwargs['fixed_base_fee_policy'].rates()==(D('.00020'),D('.00055'))
    # Serialize the actual constructed native payload, not a descriptor schema.
    from coinmaster.research.registered_control import native_kwargs_json_roundtrip
    serialized,restored=native_kwargs_json_roundtrip(kwargs)
    assert restored==kwargs
    payload=json.loads(serialized)
    assert payload['research_btc_direction_sizing'] is True
    bound=signature(run_native_diagnostic).bind(**kwargs);bound.apply_defaults()
    validate_native_control(bound.arguments)
    changed=dict(bound.arguments);changed['research_btc_split_discount']='0.006'
    with pytest.raises(ValueError,match='ARGUMENT_MISMATCH'):validate_native_control(changed)
    changed=dict(bound.arguments);changed['research_sol_off']=1
    with pytest.raises(ValueError,match='ARGUMENT_MISMATCH'):validate_native_control(changed)

@pytest.mark.parametrize('family',['R2','R3'])
@pytest.mark.parametrize('key,value',[('research_btc_real_u',1),('research_btc_direction_sizing',True),('research_btc_q_mode','ARBITRARY'),('research_btc_split_discount','0.006')])
def test_unregistered_config_changes_rejected(family,key,value,tmp_path):
    config=deepcopy(config_for(family));config[key]=value
    with pytest.raises(ValueError,match='EXACT_REGISTERED'):build_registered_control_kwargs(config,family,tmp_path,tmp_path,(),1,2)

def test_only_q_mode_differs_and_old_wrapper_still_r3_only(tmp_path):
    r2=config_for('R2');r3=config_for('R3')
    assert [k for k in r2 if r2[k]!=r3[k]]==['research_btc_q_mode']
    with pytest.raises(ValueError,match='EXACT_APPROVED_R3'):build_native_kwargs(r2,tmp_path,tmp_path,'OFF',())
    assert 'research_registered_control' not in build_native_kwargs(r3,tmp_path,tmp_path,'OFF',())
    with pytest.raises(ValueError):validate_config(r3,'R4')
    with pytest.raises(ValueError,match='48_HOURS'):build_registered_control_kwargs(r3,'R3',tmp_path,tmp_path,(),0,48*3600000+1)

def test_atr_nonfinite_duplicate_gap_and_missing_h4_rejected():
    bar=dict(start_ms=0,closed_at_ms=H4_MS,open='100',high='102',low='99',close='101')
    for bad in ([bar,bar],[bar,{**bar,'closed_at_ms':3*H4_MS}],[{**bar,'high':'NaN'}]):
        with pytest.raises(ValueError):atr_rows(bad)
    with pytest.raises(ValueError):aggregate([dict(open_time_ms=0,open=100,high=101,low=99,close=100)],60000,240)
