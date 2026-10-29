"""Collision rejection before engine/data work; no engines are constructed."""
from decimal import Decimal
from pathlib import Path
import pytest
from coinmaster.strategy.execution_config import validate_zero_tp_modes

ERROR="DEFERRED_SELECTIVE_REQUIRES_ORIGINAL_ZERO_TP_BASE"


@pytest.mark.parametrize("deferred,netting",[(False,False),(False,True),(True,False)])
def test_other_zero_tp_modes_remain_accepted(deferred,netting):
    validate_zero_tp_modes(deferred_selective_zero_tp=deferred,zero_tp_netting=netting)


def test_direct_api_rejects_collision_before_any_engine_or_coverage(monkeypatch,tmp_path):
    import nautilus_trader.backtest.engine as native_engine
    from coinmaster.research import native_baseline
    calls=[]
    def engine(*a,**kw):calls.append("engine");raise AssertionError("engine constructed")
    def coverage(*a,**kw):calls.append("coverage");raise AssertionError("data work started")
    monkeypatch.setattr(native_engine,"BacktestEngine",engine)
    monkeypatch.setattr(native_baseline,"coverage_blockers",coverage)
    with pytest.raises(ValueError,match=ERROR):
        native_baseline.run_native_diagnostic(tmp_path,research_v0_deferred_selective_zero_tp=True)
    assert calls==[]


def test_correct_original_false_passes_api_guard_without_constructing_engine(monkeypatch,tmp_path):
    import nautilus_trader.backtest.engine as native_engine
    from coinmaster.research import native_baseline
    class GuardPassed(Exception):pass
    calls=[]
    def engine(*a,**kw):calls.append("engine");raise AssertionError("engine constructed")
    def coverage(*a,**kw):calls.append("coverage");raise GuardPassed
    monkeypatch.setattr(native_engine,"BacktestEngine",engine)
    monkeypatch.setattr(native_baseline,"coverage_blockers",coverage)
    with pytest.raises(GuardPassed):
        native_baseline.run_native_diagnostic(tmp_path,research_v0_execution_repairs=True,
            research_v0_deferred_selective_zero_tp=True,research_v0_zero_tp_netting=False)
    assert calls==["coverage"]


def test_public_cli_wrapper_uses_the_same_collision_rule_before_control_data(tmp_path):
    from coinmaster.research.native_baseline import run_research_v0_repairs_cli
    with pytest.raises(ValueError,match=ERROR):
        run_research_v0_repairs_cli(tmp_path,tmp_path/"new",tmp_path/"absent.json",
            deferred_selective_zero_tp=True,zero_tp_netting=True)
    assert not (tmp_path/"new").exists()


def test_direct_strategy_rejects_collision_but_accepts_original_false():
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy,WaveOverlayStrategyConfig
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    from coinmaster.venues.marks import venue_mark_data_type
    from nautilus_trader.model.data import BarType,BarSpecification
    from nautilus_trader.model.enums import BarAggregation,PriceType,AggregationSource
    from nautilus_trader.model.identifiers import ClientId
    profile=load_current_hl_diagnostic(Path(__file__).parent/"fixtures/hl-current-20261029")
    btc,sol=profile.instruments
    kind=lambda i:BarType(i.id,BarSpecification(1,BarAggregation.DAY,PriceType.LAST),AggregationSource.EXTERNAL)
    cfg=WaveOverlayStrategyConfig(btc_id=btc.id,sol_id=sol.id,btc_bar_type=kind(btc),sol_bar_type=kind(sol),
        btc_mark_data_type=venue_mark_data_type(btc.id),sol_mark_data_type=venue_mark_data_type(sol.id),
        mark_client_id=ClientId("PROBE"),active_seed=Decimal(10000),
        research_v0_execution_repairs=True,research_v0_deferred_selective_zero_tp=True,research_v0_zero_tp_netting=False)
    values={name:getattr(cfg,name) for name in cfg.__struct_fields__}
    values["research_v0_zero_tp_netting"]=True
    with pytest.raises(ValueError,match=ERROR):
        WaveOverlayStrategyConfig(**values)
    with pytest.raises(ValueError,match=ERROR):
        WaveOverlayStrategy(cfg.__replace__(research_v0_zero_tp_netting=True))
    strategy=WaveOverlayStrategy(cfg)
    assert strategy.config.research_v0_zero_tp_netting is False
