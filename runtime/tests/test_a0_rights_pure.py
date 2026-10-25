"""No BacktestEngine: exact family plus immutable original-second arithmetic."""
from decimal import Decimal as D
from inspect import signature
from pathlib import Path
import pytest
from coinmaster.research.a0_family import build_a0_kwargs, validate_native_a0
from coinmaster.research.native_baseline import run_native_diagnostic
from coinmaster.research.registered_control import native_kwargs_json_roundtrip
from coinmaster.strategy.a0_rights import release_cap

@pytest.mark.parametrize('variant',['R2_OFF','R2_C0','R2_A0'])
def test_actual_kwargs_exact_roundtrip(variant):
    kwargs=build_a0_kwargs(Path('.'),Path('out'),variant,())
    payload,restored=native_kwargs_json_roundtrip(kwargs)
    assert restored==kwargs
    bound=signature(run_native_diagnostic).bind(**restored);bound.apply_defaults()
    validate_native_a0(bound.arguments)
    for name,value in [('research_btc_q_mode','CLEAN_Q'),('research_paired_prefix','B2'),('research_btc_split_discount','0.006'),('research_paired_policy',False),('research_registered_control','R2')]:
        bad=dict(bound.arguments);bad[name]=value
        with pytest.raises(ValueError):validate_native_a0(bad)


def test_c0_a0_differ_only_flag_and_artifact_label():
    c=build_a0_kwargs(Path('.'),Path('out'),'R2_C0',())
    a=build_a0_kwargs(Path('.'),Path('out'),'R2_A0',())
    assert {k for k in c if c[k]!=a[k]}=={'research_a0_original_second','artifact_label'}

@pytest.mark.parametrize('first,second,locked,remaining,expected',[
 ('0.5','0.5','0.257','0.5','0.757'),
 ('0.1','0.5','0.1','0.5','0.6'),  # partial first never creates .9 second
 ('0.5','0.5','0.257','0.4','0.657'),
 ('0.5','0.5','0.257','0','0.257'),
])
def test_original_budget_and_closed_btc_never_refunded(first,second,locked,remaining,expected):
    args=tuple(map(D,(first,second,locked,remaining)))
    assert release_cap(*args)==D(expected)
    # Repeated WAIT quotes use original locked cap; never pass raised result back.
    assert [release_cap(*args) for _ in range(10)]==[D(expected)]*10

@pytest.mark.parametrize('remaining',['-1','0.501','NaN'])
def test_unknown_cap_blocks(remaining):
    with pytest.raises(ValueError):release_cap(D('.5'),D('.5'),D('.257'),D(remaining))


def test_old_r3_guard_unchanged_new_r2_only_exact_selector():
    from run_continuous_hedge_preflight import registered_fixture_context
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
    cfg,_,_=registered_fixture_context('R2')
    with pytest.raises(ValueError,match='R3_CLEAN'):WaveOverlayStrategy(cfg.__replace__(research_paired_prefix='B2_F0'))
    for prefix in ('B2',):
        with pytest.raises(ValueError,match='EXACT_R2'):WaveOverlayStrategy(cfg.__replace__(research_a0_family='R2_A0_V1',research_paired_prefix=prefix))
    WaveOverlayStrategy(cfg.__replace__(research_a0_family='R2_A0_V1',research_paired_prefix='B2_F0',research_a0_original_second=True))
    assert cfg.research_a0_family is None and cfg.research_a0_original_second is False


def test_a0_preflight_excludes_only_paired_lock_and_preserves_native_pause():
    from run_continuous_hedge_preflight import registered_fixture_context
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
    cfg,_,_=registered_fixture_context('R2')
    s=WaveOverlayStrategy(cfg.__replace__(research_a0_family='R2_A0_V1',research_paired_prefix='B2_F0',research_a0_original_second=True))
    s._pair={'native':'held-owner'}
    assert not s._entries_enabled()
    assert s._entries_enabled(ignore_paired_lock=True)
    s._research_protect_latch='PAUSE'
    assert not s._entries_enabled(ignore_paired_lock=True)
