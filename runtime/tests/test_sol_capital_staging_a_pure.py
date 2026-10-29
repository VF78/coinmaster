"""Variant-A actual dispatch/domain tests; native engines and runs: zero."""
import ast
from dataclasses import asdict
from datetime import datetime,UTC,timedelta
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N
import pytest
from coinmaster.domain.wave_overlay import Candidate,Episode,Features,DailyBar,WaveOverlayState
from coinmaster.research.effective_config import effective_research_candidate
from coinmaster.strategy.sol_capital_staging import funded_scale,normalized_parent_ceiling,staged_sol_child
from coinmaster.strategy.wave_overlay import WaveOverlayStrategyConfig
from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
from coinmaster.research.native_fixture import instrument_quote
from coinmaster.venues.marks import venue_mark_data_type
from nautilus_trader.common.component import TestClock
from nautilus_trader.common.factories import OrderFactory
from nautilus_trader.model.data import BarType,BarSpecification
from nautilus_trader.model.enums import OrderSide,TimeInForce,BarAggregation,PriceType,AggregationSource
from nautilus_trader.model.identifiers import TraderId,StrategyId,ClientId

SOURCE=Path(__file__).parents[1]/"coinmaster/strategy/wave_overlay.py"


def dispatch(seed,*,admit=True,enabled=True):
    seed=D(str(seed))
    profile=load_current_hl_diagnostic(Path(__file__).parent/"fixtures/hl-current-20261029")
    btc,sol=profile.instruments
    candidate=effective_research_candidate(selective_lifecycle_repairs=True,capital_staging_seed=seed if enabled else None)
    kind=lambda i:BarType(i.id,BarSpecification(1,BarAggregation.DAY,PriceType.LAST),AggregationSource.EXTERNAL)
    config=WaveOverlayStrategyConfig(btc_id=btc.id,sol_id=sol.id,btc_bar_type=kind(btc),sol_bar_type=kind(sol),
        btc_mark_data_type=venue_mark_data_type(btc.id),sol_mark_data_type=venue_mark_data_type(sol.id),
        mark_client_id=ClientId("PROBE"),active_seed=seed,candidate=candidate,
        research_sol_capital_staging_a=enabled,research_v0_selective_lifecycle_repairs=True)
    cls=next(n for n in ast.parse(SOURCE.read_text()).body if isinstance(n,ast.ClassDef) and n.name=="WaveOverlayStrategy")
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=="_submit_intent")
    module=ast.Module(body=[ast.ImportFrom(module="__future__",names=[ast.alias(name="annotations")],level=0),
        ast.ClassDef(name="Actual",bases=[],keywords=[],body=[method],decorator_list=[])],type_ignores=[])
    env=dict(Decimal=D,OrderSide=OrderSide,TimeInForce=TimeInForce)
    exec(compile(ast.fix_missing_locations(module),str(SOURCE),"exec"),env)
    s=env["Actual"]();s.config=config;s._candidate=candidate
    state=WaveOverlayState(candidate);ep=state.episode=Episode("staging",1,float(seed),1,h=200000)
    ep.sol_rights.add(0)
    intent=state._intent(ep,"SOL_ADD",-1,0,requested_notional=200000)
    s._domain=state;s._carry_busy=lambda:False;s._carry_physical=False;s._rf_sol_child=False
    s._deposit=N(latched=False);s._v3_sol_block_episode=None;s._next_before_submit=lambda *a:True
    s._conditional_enabled=lambda:False;s._entries_enabled=lambda:True
    gates=[];sent=[];denials=[]
    s._tier_allows_increase=lambda i,side,q,t:(gates.append(q) or admit)
    s._risk_first_sol_prepare=lambda i,q,*a:q;s._risk_first_sol_bind=lambda *a:None;s._risk_first_sol_limit=lambda *a:None
    s._pending_by_order={};s._sigma_by_order={};s._decision_index_by_order={};s._order_audit={}
    s._own_accepted_reduction=lambda *a:None;s._c1_bind_submission=lambda *a:None
    s.clock=TestClock();s.order_factory=OrderFactory(TraderId("STAGING-001"),StrategyId("A-001"),s.clock)
    tick=instrument_quote(sol,"100","100",100)
    s.cache=N(instrument=lambda i:btc if i==btc.id else sol,positions_open=lambda:[],quote_tick=lambda i:tick)
    s.log=N(warning=lambda *a:None)
    def deny(i,reason,t):denials.append(reason);state.on_parent_terminal(i.id)
    s._deny_local_entry=deny
    def record(order,*a):s._order_audit[str(order.client_order_id)]={};return True
    s._record_submission=record;s.submit_order=sent.append
    s._submit_intent(intent,100,100,None,0,ts_now=100)
    return N(s=s,ep=ep,state=state,intent=intent,gates=gates,sent=sent,denials=denials)


@pytest.mark.parametrize("seed,cap,child",[
    ("10000","30000000","1000"),("81","243000","8.10"),("1234.56","3703680","123.45"),
])
def test_seed_scales_shared_economic_ceiling_and_post_admission_child(seed,cap,child):
    candidate=effective_research_candidate(selective_lifecycle_repairs=True,capital_staging_seed=D(seed))
    expected=asdict(effective_research_candidate(selective_lifecycle_repairs=True))
    expected["max_parent_notional"]=float(D(cap))
    assert asdict(candidate)==expected
    assert effective_research_candidate(candidate,selective_lifecycle_repairs=True,capital_staging_seed=D(seed))==candidate
    assert normalized_parent_ceiling(D(seed))==D(cap)
    result=dispatch(seed)
    assert result.gates==[D(2000)]
    assert len(result.sent)==1 and result.sent[0].quantity.as_decimal()==D(child)
    row=result.s._order_audit[str(result.sent[0].client_order_id)]
    assert row["staging_a_full_admitted_qty"]=="2000.00"
    assert D(row["staging_a_child_qty"])==D(child)
    assert row["staging_a_initial_seed"]==seed and row["staging_a_timing"]=="POST_ORIGINAL_FULL_ADMISSION"


def test_full_original_denial_is_not_rescued_by_a_smaller_staged_child():
    result=dispatch("81",admit=False)
    assert result.gates==[D(2000)] and result.sent==[]
    assert result.denials==["PRE_SUBMIT_INCREASE_GATE_OR_MINIMUM"]
    assert result.ep.sol_rights=={0} and result.ep.sol_add_filled_notional=={}


def test_flag_off_is_original_quantity_and_fixed_seed_does_not_follow_equity():
    plain=dispatch("81",enabled=False)
    staged=dispatch("81")
    assert plain.sent[0].quantity.as_decimal()==D(2000)
    assert staged.sent[0].quantity.as_decimal()==D("8.10")
    staged.ep.active_entry=1000000  # Later capital changes cannot change config.active_seed.
    assert staged_sol_child(D(2000),staged.s.config.active_seed,D(".01"))==D("8.10")
    assert plain.s.config.research_sol_capital_staging_a is False


@pytest.mark.parametrize("seed",["0.01","0.1"])
def test_post_staging_lot_or_notional_minimum_holds_without_charging_rights(seed):
    result=dispatch(seed)
    assert result.gates and not result.sent
    assert result.denials==["STAGING_A_CHILD_BELOW_VENUE_MINIMUM"]
    assert result.ep.sol_rights=={0} and result.ep.sol_add_filled_notional=={}
    assert result.intent.id not in result.ep.pending


def test_arbitrary_venue_lot_rounding_never_increases_quantity():
    assert staged_sol_child(D("8.109"),D(81),D(".01"))==D("8.10")
    assert staged_sol_child(D("8.009"),D(81),D(".01"))==D("8.00")
    with pytest.raises(ValueError):funded_scale(0)


def test_actual_domain_filled_child_keeps_unspent_right_and_original_daily_attempt_frequency():
    state=WaveOverlayState(Candidate(episode_fixed_beta=False,sol_late_entry_after_tp=True,sol_size_multipliers_h=(1.75,2.625,3.5)))
    state.set_execution_lots(btc=D(".00001"),sol=D(".01"))
    ep=state.episode=Episode("remaining",1,81,1,h=2000,btc_initial_qty=20,btc_open_qty=20,
        btc_entry_vwap=100,wave_levels=(.5,.6,.7))
    ep.sol_rights.add(0)
    start=datetime(2024,9,1,tzinfo=UTC)
    bars=[DailyBar(start+timedelta(days=i),start+timedelta(days=i+1),start+timedelta(days=i+1),100,100,100) for i in range(2)]
    features=[Features(i,1,1,4,0,.1,4) for i in range(2)]
    first=state.decide(bars,features,0,81)
    assert len(first)==1 and first[0].action=="SOL_ADD" and first[0].requested_notional==3500
    child=staged_sol_child(D(first[0].requested_notional)/100,D(81),D(".01"))
    state.on_fill(first[0].id,float(child),100,start,sigma=.1,decision_index=0)
    state.on_parent_terminal(first[0].id)  # Authoritative native FILLED path, no canceled event.
    assert ep.sol_add_filled_notional=={0:810.0} and ep.sol_rights=={0} and ep.h==2000
    assert first[0].id not in ep.pending
    assert state.decide(bars,features,0,81)==[]  # No same-D1/level depth recycling.
    second=state.decide(bars,features,1,81)
    assert len(second)==1 and second[0].requested_notional==2690
    assert ep.sol_rights=={0} and ep.attempted_sol_at[0]==1


def test_actual_runner_factory_and_direct_strategy_do_not_restore_unscaled_cap():
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
    source=Path(__file__).parents[1]/"coinmaster/research/native_baseline.py"
    function=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=="run_native_diagnostic")
    statement=next(n for n in function.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="candidate" for t in n.targets))
    env=dict(candidate=Candidate(),research_v0_selective_lifecycle_repairs=True,
             research_sol_capital_staging_a=True,initial_active_seed=D(81),effective_research_candidate=effective_research_candidate)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[statement],type_ignores=[])),str(source),"exec"),env)
    assert env["candidate"].max_parent_notional==243000
    cfg=dispatch("81").s.config.__replace__(candidate=effective_research_candidate(selective_lifecycle_repairs=True))
    strategy=WaveOverlayStrategy(cfg)  # Object only; no engine/cache/node is constructed.
    assert strategy._candidate.max_parent_notional==strategy._domain.config.max_parent_notional==243000
    assert cfg.candidate.max_parent_notional==30000000
