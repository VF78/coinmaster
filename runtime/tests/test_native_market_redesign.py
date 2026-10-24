"""Focused genuine native fills/ACKs, independent of archived calendars."""
from decimal import Decimal as D
import json
import pytest
from coinmaster.domain.wave_overlay import Episode, Candidate
from coinmaster.strategy.market_redesign import u_prices, target_lots, legacy_net_lots, PHI
from coinmaster.research.native_fixture import BTC_PERP
from test_native_split_cover import cfg
from test_native_episode_risk import NativeProbe, tick, run_ticks, marks
from test_native_btc_sizing import prepare_day
from test_wave_native_integration import native_engine


def setup(side=1,qty=100):
    conf=cfg(True,research_btc_real_u=True,research_btc_q_mode="LEGACY_Q_CONTROL",
        research_sol_off=True,research_btc_split_planref_v1=True,
        research_btc_split_tp_ioc=True,research_btc_split_discount=D(".005"))
    conf=conf.__replace__(candidate=Candidate(sol_overlay_enabled=False,btc_tp_fractions_initial_qty=(.2125,.2125,.575)))
    s=NativeProbe(conf)
    e=native_engine(s)
    run_ticks(e,[tick(BTC_PERP,1)])
    prepare_day(s,2);marks(s,2)
    ep=s._domain.episode=Episode("real-u",side,10000,1,wave_levels=(0,0,.03),h=10000)
    i=s._domain._intent(ep,"BTC_ENTRY",side,None,quantity=qty)
    s._submit_intent(i,100,100,.01,0,ts_now=2)
    return s,e,ep


@pytest.mark.parametrize("side",[1,-1])
def test_three_actual_accepted_tp_before_second_and_no_deadline_chase(side):
    s,e,ep=setup(side)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4)])
        targets=[o for o in e.cache.orders_open() if o.is_reduce_only]
        second=[o for o in e.cache.orders_open() if not o.is_reduce_only]
        assert len(targets)==3
        assert all(o.status.name=="ACCEPTED" for o in targets)
        assert sum((o.leaves_qty.as_decimal() for o in targets),D(0))==D(50)
        assert len(second)==1 and second[0].order_type.name=="LIMIT"
        assert second[0].price.as_decimal()==(D("99.5") if side==1 else D("100.5"))
        run_ticks(e,[tick(BTC_PERP,24*3600*10**9+5)])
        assert len([o for o in e.cache.orders() if not o.is_reduce_only])==2
        assert s._split_parent["filled"]==D(50)
        assert not s._split_parent["fallback"]
        report=json.loads(json.dumps(s._md_report()))
        assert any(r["event"]=="PLAN" and r["raw_causal_d3"]=="0.03" for r in report["events"])
        assert len([r for r in report["events"] if r["event"]=="TARGET_ACCEPTED"])==3
    finally:
        e.end();e.dispose()


def test_second_fill_resizes_three_actual_targets_at_original_p0():
    s,e,ep=setup()
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,"99"),tick(BTC_PERP,6,"99")])
        assert ep.btc_initial_qty==100
        assert ep.btc_planref_vwap==D(100)
        targets=[o for o in e.cache.orders_open() if o.is_reduce_only]
        assert len(targets)==3
        assert [o.price.as_decimal() for o in sorted(targets,key=lambda o:o.price)]==[D(101),D(102),D(103)]
        assert sum((o.leaves_qty.as_decimal() for o in targets),D(0))==D(100)
        assert len([o for o in e.cache.orders() if not o.is_reduce_only])==2
    finally:
        e.end();e.dispose()


def test_tp_cancels_second_and_filled_target_never_resurrects():
    s,e,ep=setup()
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,"101"),tick(BTC_PERP,6,"99")])
        assert s._split_parent["stop_reason"]=="FIRST_POSITIVE_TP_FILL"
        assert ep.btc_initial_qty==50
        assert 0 in ep.btc_filled_tps
        assert not ep.sol_rights
        targets=[o for o in e.cache.orders_open() if o.is_reduce_only]
        assert len(targets)==2 and all(o.price.as_decimal()>101 for o in targets)
        assert sum((o.leaves_qty.as_decimal() for o in targets),D(0))==D(str(ep.btc_open_qty))
    finally:
        e.end();e.dispose()


def test_partial_first_child_terminal_freezes_actual_vwap_and_protects():
    s,e,ep=setup()
    try:
        run_ticks(e,[tick(BTC_PERP,3,size="10"),tick(BTC_PERP,4)])
        assert ep.btc_initial_qty==10
        assert ep.btc_planref_vwap==D(100)
        assert s._md_plans[ep.id]["first_done"]
        targets=[o for o in e.cache.orders_open() if o.is_reduce_only]
        assert len(targets)==3
        assert sum((o.leaves_qty.as_decimal() for o in targets),D(0))==10
        assert len([o for o in e.cache.orders() if not o.is_reduce_only])==2
    finally:
        e.end();e.dispose()


def test_geometry_and_sizing_are_pure_and_reject_invalid_net_prices():
    assert legacy_net_lots(10000,{0:2125,1:2125,2:5750},{0,1},True)==5750
    assert legacy_net_lots(10000,{0:2125,1:2125,2:5750},{0,1},False)==10000
    assert PHI[1]*min(D(6)*D(10_000_000),D(30_000_000))==D("25654606.1394175050000000")
    assert sum(target_lots(10000,{0}).values())==10000
    with pytest.raises(ValueError,match="NONPOSITIVE_NET"):
        u_prices(D(100),D(".0001"),1,D(".00001"),D(".00055"),D(".00055"))
    with pytest.raises(ValueError,match="INVALID_CAUSAL_D3"):
        u_prices(D(100),D(0),1,D(".1"),D(".00055"),D(".00055"))
