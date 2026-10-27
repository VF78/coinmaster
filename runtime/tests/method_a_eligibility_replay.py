"""Domain method-unit eligibility regression, not native matching evidence."""
from types import SimpleNamespace as NS
from datetime import datetime,timezone
from decimal import Decimal as D
from nautilus_trader.model.data import QuoteTick
from coinmaster.domain.wave_overlay import Candidate,Episode,WaveOverlayState
from coinmaster.strategy.method_a_tp import MethodATpResearch
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy,_fee_floor_price
from coinmaster.research.native_fixture import BTC_PERP


def eligibility_proof():
    domain=WaveOverlayState(Candidate());domain.research_method_a_tp=True
    domain.set_execution_lots(btc=D('.001'),sol=D('.1'))
    ep=Episode('UNIT-OMITTED',1,10000,1,wave_levels=(0,0,.03),h=10000)
    ep.btc_initial_qty=2;ep.btc_open_qty=2;ep.btc_entry_qty_exact=D(2)
    ep.btc_entry_vwap=100;ep.btc_net_planned_qty=4
    ep.btc_tp_target_lots={0:425,1:425,2:1150};ep.btc_tp_target_qty={0:.425,1:.425,2:1.15}
    ep.btc_omitted_zero_levels={0,1};ep.sol_right_fraction={0:.5,1:.5}
    ep.sol_right_decision_index={0:7,1:7};ep.btc_deferred_right_reference_price=D(110)
    domain.episode=ep
    intent=domain._intent(ep,'BTC_REDUCE',-1,0,quantity=.1)
    domain.on_fill(intent.id,.1,101,datetime.fromtimestamp(9,timezone.utc),decision_index=9)
    assert ep.sol_rights==set() and ep.sol_right_decision_index=={0:7,1:7}
    class Harness(MethodATpResearch):
        def _ma_reconcile(self,ts):pass
        def _advance_current_day(self):pass
    h=Harness();h.config=NS(research_method_a_tp=True,tp_fee_floor_v1=False,deposit_runtime=None,research_v0_selective_lifecycle_repairs=True)
    h._domain=domain;h._ma_init();h._ma_plans[ep.id]=dict(raw_target_lots={0:0,1:0,2:4000})
    event=NS(ts_event=9,trade_id='UNIT-OMITTED',client_order_id='UNIT-OMITTED',last_qty=BTC_PERP.make_qty(D('.1')))
    h._ma_after_fill(intent,event)
    assert not ep.sol_rights and ep.sol_right_fraction[0]==.5
    h._forced_close_reason=None;h._liquidating=False;session=10*10**9
    h._bars=[NS(close_time=datetime.fromtimestamp(10,timezone.utc))]
    h._current_btc=NS(ts_event=session);h._current_sol=NS(ts_event=session)
    h._last_accepted_session=session;h._latest_seen_session=session+1
    h._mandatory_sol_exit=None;h.entry_sizing_audit=[]
    def quote(px):return QuoteTick(BTC_PERP.id,BTC_PERP.make_price(D(px)),BTC_PERP.make_price(D(px)),BTC_PERP.make_qty(D(1)),BTC_PERP.make_qty(D(1)),session,session)
    WaveOverlayStrategy._activate_selective_sol_rights(h,quote('101'))
    assert not ep.sol_rights and not ep.btc_deferred_right_touched
    WaveOverlayStrategy._activate_selective_sol_rights(h,quote('110'))
    assert not ep.sol_rights and ep.btc_deferred_right_touched
    h._latest_seen_session=session
    WaveOverlayStrategy._activate_selective_sol_rights(h,quote('110'))
    assert ep.sol_rights=={0,1} and ep.sol_right_decision_index=={0:0,1:0}
    h.config.tp_fee_floor_v1=True;ep.btc_entry_notional_exact=D(220)
    ep.btc_entry_fees_exact=D('.121');ep.btc_entry_fee_fill_count=1;ep.btc_entry_fill_count=1
    floor=_fee_floor_price(BTC_PERP,ep,maker=True).as_decimal()
    assert h._ma_wire_prices(ep,BTC_PERP,D(100),D('.03'))==tuple(floor for _ in range(3))
    return dict(status='METHOD_UNIT_ELIGIBILITY_PASS',old_omitted_right_requires_original_cross_and_paired_session=True,shared_fee_floor_wire_consistent=True,native_engine_constructors=0,economic_or_M1_native_evidence=False)
