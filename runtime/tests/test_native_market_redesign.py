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


def setup(side=1,qty=100,probe=NativeProbe):
    conf=cfg(True,research_btc_real_u=True,research_btc_q_mode="LEGACY_Q_CONTROL",
        research_sol_off=True,research_btc_split_planref_v1=True,
        research_btc_split_tp_ioc=True,research_btc_split_discount=D(".005"))
    conf=conf.__replace__(candidate=Candidate(sol_overlay_enabled=False,btc_tp_fractions_initial_qty=(.2125,.2125,.575)))
    s=probe(conf)
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


def test_cancel_request_is_not_ack_late_second_fill_protected_without_tp_resurrection():
    class DelayedCancel(NativeProbe):
        def cancel_order(self,order,*args,**kwargs):
            if not order.is_reduce_only:
                return  # Explicit transport fixture: no cancel ACK delivered.
            return super().cancel_order(order,*args,**kwargs)
    s,e,ep=setup(probe=DelayedCancel)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,"101")])
        assert 0 in ep.btc_filled_tps
        run_ticks(e,[tick(BTC_PERP,6,"99"),tick(BTC_PERP,7,"99")])
        assert ep.btc_initial_qty==100
        assert not ep.sol_rights
        targets=[o for o in e.cache.orders_open() if o.is_reduce_only]
        assert len(targets)==2
        assert all(o.price.as_decimal()>101 for o in targets)
        assert sum((o.leaves_qty.as_decimal() for o in targets),D(0))==D(str(ep.btc_open_qty))
        assert len([o for o in e.cache.orders() if not o.is_reduce_only])==2
        payload={"adapter":s.reporting_state(),"split":s._split_cover_report(),"u":s._md_report(),"native_orders":s._order_audit}
        from coinmaster.research.native_audit import audit_json_default
        roundtrip=json.loads(json.dumps(payload,default=audit_json_default))
        assert len(roundtrip["adapter"]["fill_audit"])>=3
    finally:
        e.end();e.dispose()


def test_full_tp_keeps_empty_signal_episode_and_closed_d1_trail_or_regime():
    from dataclasses import replace
    from types import SimpleNamespace
    s,e,ep=setup()
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,"103"),tick(BTC_PERP,6,"103")])
        assert not e.cache.positions_open()
        assert s._domain.episode is ep
        assert ep.btc_open_qty==0
        features=[SimpleNamespace(side=1,beta=1)]*3
        assert s._domain.decide(s._bars,features,2,10000)==[]
        assert s._domain.episode is ep
        bars=list(s._bars);bars[2]=replace(bars[2],btc_close=105)
        assert s._domain.decide(bars,features,2,10000)==[]
        bars[2]=replace(bars[2],btc_close=101)
        assert s._domain.decide(bars,features,2,10000)[0].reason=="TRAIL"
        features[2]=SimpleNamespace(side=-1,beta=1)
        assert s._domain.decide(bars,features,2,10000)[0].reason=="REGIME"
    finally:
        e.end();e.dispose()


def test_clean_q_outside_cap_and_legacy_q0_q1_selector_are_separate():
    s,e,ep=setup()
    try:
        # Native quotes, pure sizing observation; no extra engine order.
        i=s._domain._intent(ep,"BTC_ENTRY",1,None,requested_notional=30_000_000)
        ep.wave_levels=(0,0,.03)
        assert s._select_deferred_btc_entry(i,tick(BTC_PERP,10,"100")) is None
        legacy=s._select_deferred_btc_entry(i,tick(BTC_PERP,11,"99"))
        assert legacy==D("172500")
        assert s._selected_entry_audits[i.id]["branch"]=="PASSIVE_NET_ZERO_LEVELS"
        # The pure CLEAN_Q formula uses capped own-equity notional first.
        assert int(PHI[1]*D(30_000_000)/D(100)/D(".001"))==256546061
    finally:
        e.end();e.dispose()


def test_signed_funding_receipts_are_actual_native_before_after_cash(tmp_path):
    from coinmaster.research.native_fixture import FundingInstruction,BTC_PERP,SOL_PERP
    from coinmaster.ledger.journal import NativeEventJournal
    from test_native_fixture import build_engine,fixture_quotes
    events=(
        FundingInstruction("btc-positive",BTC_PERP.id,D(".01"),6,D("80999.5"),"synthetic_mid",True),
        FundingInstruction("sol-negative",SOL_PERP.id,D("-.01"),6,D("159.95"),"synthetic_mid",True),
    )
    journal=NativeEventJournal(str(tmp_path/"signed-native.sqlite"))
    e=build_engine(events,funding_journal=journal)
    e.add_data(fixture_quotes());e.run()
    try:
        rows=journal.funding_cash_audit()
        assert [r[1] for r in rows]==[str(BTC_PERP.id),str(SOL_PERP.id)]
        assert [D(r[5]) for r in rows]==[D("-485.997"),D("-799.75")]
        assert all(D(r[4])-D(r[3])==D(r[5]) for r in rows)
        json.loads(json.dumps(rows))
    finally:
        e.dispose();journal.close()


def test_tiny_native_partial_records_protection_exception_and_blocks_second():
    s,e,ep=setup()
    try:
        run_ticks(e,[tick(BTC_PERP,3,size=".001"),tick(BTC_PERP,4)])
        assert ep.btc_initial_qty==.001
        assert len([o for o in e.cache.orders() if not o.is_reduce_only])==1
        assert not [o for o in e.cache.orders_open() if o.is_reduce_only]
        events=s._md_report()["events"]
        assert any(r["event"]=="PROTECTION_EXCEPTION" and r["reason"]=="PARTIAL_BELOW_THREE_VALID_LOTS" for r in events)
        assert any(r["event"]=="UNDERSIZED_TERMINAL_FIRST_FAILCLOSED" for r in events)
        assert not e.cache.positions_open()
        assert not e.cache.orders_open()
        assert s._md_report()["open_protection_exception_since_ns"] is None
    finally:
        e.end();e.dispose()


def test_old_target_generation_can_fill_during_second_partial_replacement_cancel_race():
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
    class DelayedTargets(NativeProbe):
        def cancel_order(self,order,*args,**kwargs):
            if order.is_reduce_only:
                return  # Native order stays live until explicit transport ACK below.
            return super().cancel_order(order,*args,**kwargs)
    s,e,ep=setup(probe=DelayedTargets)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,5,"99.5",size="10")])
        assert ep.btc_initial_qty==60
        assert s._md_plans[ep.id]["accepted"]==set()
        run_ticks(e,[tick(BTC_PERP,6,"101",size="1")])
        assert 0<ep.btc_tp_filled_lots[0]<10625
        assert ep.btc_planref_vwap==D(100)
        old=[o for o in e.cache.orders_open() if o.is_reduce_only]
        assert len(old)==3
        assert sum((o.leaves_qty.as_decimal() for o in old),D(0))<=D(str(ep.btc_open_qty))
        # ACK one old cancellation; another historically authorized old order
        # is still allowed to fill before its own ACK.
        old1=next(o for o in old if o.price.as_decimal()==102)
        WaveOverlayStrategy.cancel_order(s,old1)
        run_ticks(e,[tick(BTC_PERP,7,"101")])
        assert 0 in ep.btc_filled_tps
        for o in list(e.cache.orders_open()):
            if o.is_reduce_only:
                WaveOverlayStrategy.cancel_order(s,o)
        run_ticks(e,[tick(BTC_PERP,8,"100")])
        current=[o for o in e.cache.orders_open() if o.is_reduce_only]
        assert all(o.price.as_decimal()>101 for o in current)
        assert sum((o.leaves_qty.as_decimal() for o in current),D(0))==D(str(ep.btc_open_qty))
        assert len([o for o in e.cache.orders() if not o.is_reduce_only])==2
        assert ep.btc_planref_vwap==D(100)
    finally:
        e.end();e.dispose()


@pytest.mark.parametrize("phase",["first","second"])
@pytest.mark.parametrize("mode",["denied","rejected","expired"])
def test_genuine_native_entry_terminal_callbacks_cleanup_without_implicit_retry(phase,mode):
    from datetime import datetime,timezone
    from nautilus_trader.model.enums import TimeInForce
    from nautilus_trader.model.objects import Quantity
    class NativeTerminalFixture(NativeProbe):
        seen=[]
        def submit_order(self,order,*args,**kwargs):
            intent=self._pending_by_order.get(str(order.client_order_id))
            is_second=bool(self._split_child_submit)
            if intent and intent.action=="BTC_ENTRY" and is_second==(phase=="second"):
                common=dict(instrument_id=order.instrument_id,order_side=order.side,
                    client_order_id=order.client_order_id)
                if mode=="denied":
                    order=self.order_factory.market(quantity=Quantity.from_str("50.0001"),time_in_force=TimeInForce.IOC,**common)
                elif mode=="rejected":
                    order=self.order_factory.limit(quantity=order.quantity,price=BTC_PERP.make_price(D(101)),
                        time_in_force=TimeInForce.GTC,post_only=True,**common)
                else:
                    order=self.order_factory.limit(quantity=order.quantity,price=BTC_PERP.make_price(D("99.5")),
                        time_in_force=TimeInForce.GTD,expire_time=datetime.fromtimestamp(1,tz=timezone.utc),**common)
            return super().submit_order(order,*args,**kwargs)
        def on_order_denied(self,event):
            self.seen.append("denied");return super().on_order_denied(event)
        def on_order_rejected(self,event):
            self.seen.append("rejected");return super().on_order_rejected(event)
        def on_order_expired(self,event):
            self.seen.append("expired");return super().on_order_expired(event)
    s,e,ep=setup(probe=NativeTerminalFixture)
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4),tick(BTC_PERP,1_000_000_001)])
        assert mode in s.seen
        assert not [i for i in s._pending_by_order.values() if i.action=="BTC_ENTRY"]
        assert len([o for o in e.cache.orders() if not o.is_reduce_only])==(1 if phase=="first" else 2)
        assert s._split_parent["closed"]
        if phase=="first":
            assert not e.cache.positions_open()
        else:
            assert ep.btc_planref_vwap==D(100)
            targets=[o for o in e.cache.orders_open() if o.is_reduce_only]
            assert len(targets)==3
            assert sum((o.leaves_qty.as_decimal() for o in targets),D(0))==D(50)
    finally:
        e.end();e.dispose()


def test_native_terminal_boundary_closes_only_observer_interval_after_actual_flat():
    s,e,ep=setup()
    try:
        run_ticks(e,[tick(BTC_PERP,3),tick(BTC_PERP,4)])
        entry_fills=[dict(r) for r in s.fill_audit]
        before_orders=len(e.cache.orders())
        held=next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==BTC_PERP.id)
        assert held==D(50)
        s._begin_forced_close("TERMINAL_BOUNDARY_SETTLEMENT")
        # Native cancel callbacks can be delivered at the next engine tick;
        # inspect the actual callback sequence after native settlement.
        run_ticks(e,[tick(BTC_PERP,5)])
        assert not e.cache.positions_open() and not e.cache.orders_open()
        assert s.terminal_lifecycle["status"]=="FLAT"
        terminal=[r for r in s.fill_audit if r["action"]=="TERMINAL_CLOSE"]
        assert len(terminal)==1 and D(terminal[0]["qty"])==held
        assert len(e.cache.orders())==before_orders+1
        assert s.fill_audit[:len(entry_fills)]==entry_fills
        native_terminal=next(o for o in e.cache.orders() if str(o.client_order_id) in s._terminal_order_ids)
        assert native_terminal.status.name=="FILLED"
        assert native_terminal.filled_qty.as_decimal()==held
        report=s._md_report()
        assert report["open_protection_exception_since_ns"] is None
        canceled=[r for r in report["events"] if r["event"]=="PROTECTION_EXCEPTION" and r["reason"]=="TARGET_CANCEL_ACK"]
        assert canceled and int(canceled[-1]["timestamp_ns"])<=int(terminal[0]["fill_ns"])
        restored=[r for r in report["events"] if r["event"]=="PROTECTION_RESTORED" and r["reason"]=="NATIVE_TERMINAL_FLAT"]
        assert len(restored)==1
        assert restored[0]["timestamp_ns"]==terminal[0]["fill_ns"]
        # Repeated reporting/flat callbacks are observer-idempotent.
        s._reconcile_terminal_flat();s.reporting_state()
        assert len([r for r in s._md_report()["events"] if r["event"]=="PROTECTION_RESTORED" and r["reason"]=="NATIVE_TERMINAL_FLAT"])==1
    finally:
        e.end();e.dispose()
