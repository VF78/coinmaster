"""Engine-free real frozen report→native call regression, including old R3 path.

The native runner is intercepted BEFORE any engine. Synthetic control metadata
exists only to exercise the old wrapper's existing validation/call boundary.
No account/fill/report/economic result is simulated or asserted here.
"""
from copy import deepcopy
from dataclasses import asdict,replace
from datetime import datetime,timezone
from decimal import Decimal as D
from inspect import signature
from pathlib import Path
import hashlib,json
import pytest
from coinmaster.domain.wave_overlay import Candidate
from coinmaster.research import native_baseline as native
from coinmaster.research.paired_prefix_run import build_native_kwargs,execute_prepared_call,START_MS,END_MS

FIXTURE=Path(__file__).parent/'fixtures/paired-r3-expected-config.json'


def frozen_config():return json.loads(FIXTURE.read_text())


def test_actual_frozen_report_complete_call_matches_original_r3_entrypoint(tmp_path,monkeypatch):
    config=frozen_config();actual_signature=signature(native.run_native_diagnostic)
    kwargs=build_native_kwargs(config,tmp_path,tmp_path/'new','OFF',())
    captured=[]
    def strict_capture(*args,**values):
        bound=actual_signature.bind(*args,**values);bound.apply_defaults()
        call=dict(bound.arguments)
        assert type(call['research_btc_direction_sizing']) is bool and call['research_btc_direction_sizing'] is True
        assert type(call['research_wait_4h']) is bool and call['research_wait_4h'] is True
        assert isinstance(call['candidate'],Candidate)
        assert isinstance(call['execution_policy'],native.ExecutionPolicy)
        assert isinstance(call['fixed_base_fee_policy'],native.FixedBaseFeePolicy)
        # The old native body applies SOL-OFF before any strategy/engine state.
        if call['research_sol_off']:
            call['candidate']=replace(call['candidate'],sol_overlay_enabled=False)
        captured.append(call)
        return {}
    monkeypatch.setattr(native,'run_native_diagnostic',strict_capture)
    execute_prepared_call(kwargs)
    assert len(captured)==1
    assert config['research_btc_direction_sizing']=={'freeze':'GENUINE_EPISODE_CREATION','long':'5.5','short':'7.875'}
    manifest=tmp_path/'bybit-1m/manifest.json';manifest.parent.mkdir();manifest.write_text('{}')
    control_config={**native.BASELINE_CONFIG,'candidate':asdict(replace(Candidate(**config['candidate']),sol_overlay_enabled=True)),
        'execution_policy':config['execution_policy'],'fixed_base_fee_policy':config['fixed_base_fee_policy'],
        'fee_policy_hash':config['fee_policy_hash'],'tp_fee_floor_v1':False,
        'run_interval':{'start':datetime.fromtimestamp(native.TRADING_START_MS/1000,tz=timezone.utc).isoformat(),
            'end_exclusive':datetime.fromtimestamp(native.TRADING_END_MS/1000,tz=timezone.utc).isoformat(),'initial_active_seed':'10000'}}
    control={'status':'NOT_FAITHFUL_DIAGNOSTIC','config':control_config,'policy':config['execution_policy'],
        'summary':{'terminal_total':'3386491.65211338'},'data_hash':hashlib.sha256(b'{}').hexdigest()}
    path=tmp_path/'control-metadata.json';path.write_text(json.dumps(control))
    monkeypatch.setattr(native,'save_diagnostic_report',lambda *args:tmp_path/'not-a-native-result.json')
    # Exact original R3 CLI option semantics, not values taken from the new resolver.
    native.run_research_v0_repairs_cli(tmp_path,tmp_path/'old',path,
        zero_tp_netting=False,deferred_selective_zero_tp=True,selective_lifecycle_repairs=True,
        observe_minute_risk=True,research_btc_direction_sizing=True,research_btc_split50=True,
        research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,research_btc_split_discount='0.005',
        research_btc_real_u=True,research_btc_q_mode='CLEAN_Q',research_sol_off=True,
        research_wait_4h=True,research_regime_reentry_band='0.5')
    assert len(captured)==2
    new,old=captured
    declared_changes={'artifact_dir','artifact_label','trading_end_ms','research_paired_policy'}
    assert {k for k in new if new[k]!=old[k]}==declared_changes
    assert new['trading_start_ms']==old['trading_start_ms']==START_MS
    assert new['trading_end_ms']==END_MS and old['trading_end_ms']==native.TRADING_END_MS
    assert new['research_paired_policy'] is True and old['research_paired_policy'] is False
    assert new['candidate']==old['candidate']
    assert new['fixed_base_fee_policy'].rates()==(D('.00020'),D('.00055'))


@pytest.mark.parametrize('key',['research_v0_execution_repairs','research_v0_zero_tp_netting',
    'research_v0_deferred_selective_zero_tp','research_v0_selective_lifecycle_repairs',
    'research_btc_split50','research_btc_split_planref_v1','research_btc_split_tp_ioc',
    'research_btc_real_u','research_sol_off'])
def test_all_report_boolean_arguments_reject_descriptors_instead_of_truthiness(tmp_path,key):
    config=frozen_config();config[key]={'enabled':True}
    with pytest.raises(ValueError,match='R3_REPORT_FLAG_NOT_BOOL'):
        build_native_kwargs(config,tmp_path,tmp_path/'out','OFF',())


@pytest.mark.parametrize('descriptor',[True,{'freeze':'GENUINE_EPISODE_CREATION','long':'5.6','short':'7.875'},
    {'freeze':'LATER_RESIZE','long':'5.5','short':'7.875'}])
def test_direction_descriptor_must_preserve_exact_archived_units_and_freeze(tmp_path,descriptor):
    config=frozen_config();config['research_btc_direction_sizing']=descriptor
    with pytest.raises(ValueError,match='EXACT_R3_DIRECTION_DESCRIPTOR'):
        build_native_kwargs(config,tmp_path,tmp_path/'out','OFF',())


def test_full_call_optional_scalar_and_constructor_errors_fail_before_native_dispatch(tmp_path):
    config=frozen_config();config['hedge_band_research']['regime_reentry_band']={'atr':'.5'}
    with pytest.raises(ValueError,match='NATIVE_CALL_ARGUMENT_TYPE:research_regime_reentry_band'):
        build_native_kwargs(config,tmp_path,tmp_path/'out','OFF',())
    config=frozen_config();config['candidate']['unknown_new_parameter']=1
    with pytest.raises(TypeError):build_native_kwargs(config,tmp_path,tmp_path/'out','OFF',())
