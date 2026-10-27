"""Pinned exact-E4 P0/P1 native call decoder, engine-free until caller dispatch."""
from pathlib import Path
from decimal import Decimal as D
from inspect import signature
import hashlib, json

E4_SHA = 'ce7c101ace5d8c21f0a912a0cd3221659591e5d56b744d3f8dc5ecb7c01d2ef6'
START_MS = 1725148800000
PREFIX_END_MS = 1736899200000


def archived_e4():
    config = json.loads((Path(__file__).parent/'control_configs/METHOD_A_E4.json').read_text())
    payload = json.dumps(config,sort_keys=True,separators=(',',':')).encode()
    if hashlib.sha256(payload).hexdigest() != E4_SHA:
        raise ValueError('METHOD_A_EXACT_E4_PIN_MISMATCH')
    return config


def build_method_a_kwargs(data_root, artifact_dir, variant, *, start_ms=START_MS, end_ms=PREFIX_END_MS):
    if variant not in ('P0','P1'):
        raise ValueError('METHOD_A_TP_STAGE_ONLY_P0_P1')
    if type(start_ms) is not int or type(end_ms) is not int or end_ms <= start_ms:
        raise ValueError('METHOD_A_INVALID_INTERVAL')
    from coinmaster.domain.wave_overlay import Candidate
    from coinmaster.research.native_baseline import run_native_diagnostic, ExecutionPolicy, FixedBaseFeePolicy
    from coinmaster.research.registered_control import native_kwargs_json_roundtrip
    c = archived_e4()
    flags = {k:c[k] for k in ('tp_fee_floor_v1','research_v0_execution_repairs',
        'research_v0_zero_tp_netting','research_v0_deferred_selective_zero_tp',
        'research_v0_selective_lifecycle_repairs','research_btc_split50',
        'research_btc_split_planref_v1','research_btc_split_tp_ioc','research_conditional_sol')}
    assert all(type(v) is bool for v in flags.values())
    fee=FixedBaseFeePolicy(**c['fixed_base_fee_policy'])
    if fee.hash != c['fee_policy_hash']:
        raise ValueError('METHOD_A_EXACT_E4_FEE_PIN_MISMATCH')
    kwargs=dict(data_root=Path(data_root),artifact_dir=Path(artifact_dir),
        artifact_label='method-a-'+variant,include_funding=True,
        trading_start_ms=start_ms,trading_end_ms=end_ms,initial_active_seed=D('10000'),
        candidate=Candidate(**c['candidate']),execution_policy=ExecutionPolicy(**c['execution_policy']),
        fixed_base_fee_policy=fee,observe_minute_risk=True,
        research_method_a_observer=True,research_method_a_tp=variant=='P1',
        research_btc_direction_sizing=True,research_btc_split_discount=c['research_btc_split_discount'],
        research_regime_reentry_band=c['hedge_band_research']['regime_reentry_band'],
        research_wait_4h=c['next_band_research']['wait_4h'],
        research_wait_persist=c['next_band_research']['wait_persist'],
        research_zero_retrace=c['next_band_research']['zero_retrace'],
        research_sol_dominant=c['next_band_research']['sol_dominant'],**flags)
    bound=signature(run_native_diagnostic).bind(**kwargs);bound.apply_defaults()
    assert not bound.arguments['research_paired_policy']
    assert not bound.arguments['research_btc_real_u'] and bound.arguments['research_btc_q_mode'] is None
    assert not bound.arguments['research_sol_off'] and kwargs['candidate'].sol_overlay_enabled
    _,restored=native_kwargs_json_roundtrip(kwargs)
    if restored != kwargs:
        raise ValueError('METHOD_A_NATIVE_KWARGS_ROUNDTRIP')
    return kwargs
