"""Engine-free proof that extracted config mapping equals original 7d constructor."""
import ast,inspect
from pathlib import Path
import pytest
from coinmaster.research import native_baseline as native
from coinmaster.strategy.wave_overlay import WaveOverlayStrategyConfig,WaveOverlayStrategy
from coinmaster.research.native_fixture import TierMarginPolicy
from coinmaster.venues.marks import venue_mark_data_type
from coinmaster.venues.signals import daily_signal_data_type
from nautilus_trader.model.enums import PriceType
from run_continuous_hedge_preflight import registered_fixture_context,snapshot_config

@pytest.mark.parametrize('family',['R2','R3'])
def test_shared_constructor_is_frozen_original_expression_and_actual_config(family):
    frozen=Path(__file__).parent/'fixtures/frozen-native-strategy-constructor-7d513.expr'
    expr=frozen.read_text()
    tree=ast.parse(inspect.getsource(native.build_native_strategy_config))
    actual=next(n.value for n in ast.walk(tree) if isinstance(n,ast.Return))
    assert ast.dump(actual)==ast.dump(ast.parse(expr,mode='eval').body)
    config,context,receipt=registered_fixture_context(family)
    env={**vars(native),**context,'WaveOverlayStrategyConfig':WaveOverlayStrategyConfig,'TierMarginPolicy':TierMarginPolicy,'PriceType':PriceType,'venue_mark_data_type':venue_mark_data_type,'daily_signal_data_type':daily_signal_data_type}
    original=eval(compile(expr,str(frozen),'eval'),env)
    assert snapshot_config(config)==snapshot_config(original)
    assert config.candidate is context['candidate']
    assert config.research_paired_prefix is None
    assert config.research_btc_direction_sizing is True
    assert config.research_wait_4h is True
    assert str(config.research_regime_reentry_band)=='0.5'
    # Strategy construction itself is engine-free and preserves money guard.
    WaveOverlayStrategy(config)
    with pytest.raises(ValueError,match='R2_PAIRED_NOT_ADMITTED'):
        registered_fixture_context('R2',paired=True)
    if family=='R3':WaveOverlayStrategy(registered_fixture_context('R3',paired=True)[0])


def test_fixture_seed_days_are_completed_before_q0_without_engine():
    from run_continuous_hedge_preflight import ControlProbe,prepare_completed_day
    config,_,_=registered_fixture_context('R2')
    strategy=ControlProbe(config)
    prepare_completed_day(strategy,2)
    assert max(int(row.available_at.timestamp()*10**9) for row in strategy._bars)==0
    assert all(row.open_time<row.close_time==row.available_at for row in strategy._bars)
