"""Real Cache/Order/event-class UNIT replay, zero matching/engine/economics.

These deliberately constructed test events verify callback-method contracts;
they are never reported as actual native fills/ACKs/financial evidence.
"""
from types import SimpleNamespace as NS
from decimal import Decimal as D
from nautilus_trader.cache.cache import Cache
from nautilus_trader.test_kit.stubs.execution import TestExecStubs
from nautilus_trader.test_kit.stubs.events import TestEventStubs
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import ClientOrderId,TradeId
from coinmaster.research.native_fixture import BTC_PERP
from coinmaster.strategy.standing_tp import StandingTPResearch


def replay_proof():
    class Harness(StandingTPResearch):
        def __init__(self):
            self.config=NS(research_btc_standing_tp=True,btc_id=BTC_PERP.id,research_native_book=NS(detailed=True))
            self.cache=Cache();self.cache.add_instrument(BTC_PERP);self._pending_by_order={};self._pair=None;self._forced_close_reason=None;self._liquidating=False
            self._domain=NS(episode=NS(id='parent',side=1));self._md_plans={'parent':dict(generation=0,standing={0:212},consumed=set(),order_generation={})}
            self._tp_init()
        def _tp_book(self):return dict(bid='100',ask='100',epoch=1)
    h=Harness();order=TestExecStubs.limit_order(instrument=BTC_PERP,order_side=OrderSide.SELL,quantity=BTC_PERP.make_qty(D('.212')),price=BTC_PERP.make_price(D(101)),reduce_only=True)
    h.id=order.strategy_id;oid=str(order.client_order_id);intent=NS(id='intent',action='BTC_REDUCE',episode_id='parent',level=0)
    h._pending_by_order[oid]=intent;h._tp_bind_order(order,intent)
    assert h.cache.order(order.client_order_id)is None
    h._tp_native_event(order.init_event,'generic');assert h._tp_owners[oid]['ack_generation']is None
    h.cache.add_order(order)
    submitted=TestEventStubs.order_submitted(order,ts_event=1);order.apply(submitted);h.cache.update_order(order);h._tp_native_event(submitted,'generic')
    accepted=TestEventStubs.order_accepted(order,ts_event=2);order.apply(accepted);h.cache.update_order(order)
    h._tp_native_event(accepted,'typed');h._tp_native_event(accepted,'generic');assert h._tp_owners[oid]['ack_generation']==0
    partial=TestEventStubs.order_filled(order,BTC_PERP,last_qty=BTC_PERP.make_qty(D('.050')),trade_id=TradeId('UNIT-PARTIAL'),ts_event=3)
    order.apply(partial);h.cache.update_order(order);h._tp_before_fill(partial);h._tp_native_event(partial,'generic')
    assert h._md_plans['parent']['standing']=={0:162}
    # Inventory-triggered command model: actual native class PENDING_UPDATE,
    # actual total quantity includes the earlier real-class replay partial.
    m=h._md_plans['parent'];m['standing']={0:169};m['generation']=1
    h._tp_owners[oid]['generation']=1;h._tp_commands[oid]=dict(sequence=1,generation=1,total=D('.219'),desired_lots=169)
    pending=TestEventStubs.order_pending_update(order,ts_event=4);order.apply(pending);h.cache.update_order(order)
    assert order.status.name=='PENDING_UPDATE';h._tp_native_event(pending,'generic');assert oid in h._tp_commands
    updated=TestEventStubs.order_updated(order,quantity=BTC_PERP.make_qty(D('.219')),ts_event=5);order.apply(updated);h.cache.update_order(order)
    h._tp_native_event(updated,'typed');h._tp_native_event(updated,'generic')
    assert order.filled_qty.as_decimal()==D('.050')and order.leaves_qty.as_decimal()==D('.169')and not h._tp_commands
    assert h._tp_owners[oid]['ack_generation']==h._tp_owners[oid]['ack_sequence']==1
    terminal=TestEventStubs.order_filled(order,BTC_PERP,last_qty=BTC_PERP.make_qty(D('.169')),trade_id=TradeId('UNIT-TERMINAL'),ts_event=4)
    order.apply(terminal);h.cache.update_order(order);h._tp_before_fill(terminal)
    del h._pending_by_order[oid] # typed terminal handler's genuine lifecycle order
    h._domain.episode=NS(id='new-parent',side=-1);h._md_plans['new-parent']={}
    before=dict(h._md_plans['parent']['standing']);h._tp_native_event(terminal,'generic');h._tp_native_event(terminal,'generic')
    assert h._md_plans['parent']['standing']==before=={0:0}and not h._tp_commands and oid not in h._pending_by_order
    # A real native event which was not applied to actual order history receives
    # no terminal-history credit, even if it names the old client order ID.
    unknown=TestEventStubs.order_canceled(order,ts_event=5)
    try:h._tp_native_event(unknown,'generic')
    except ValueError as error:assert 'NOT_IN_NATIVE_HISTORY'in str(error)
    else:raise AssertionError('UNKNOWN_TERMINAL_HISTORY_ACCEPTED')
    # Separate accepted/canceled order; history remains valid after intent loss.
    other=TestExecStubs.limit_order(instrument=BTC_PERP,order_side=OrderSide.SELL,quantity=BTC_PERP.make_qty(D('.212')),price=BTC_PERP.make_price(D(101)),reduce_only=True,client_order_id=ClientOrderId('UNIT-CANCEL'))
    h._domain.episode=NS(id='parent',side=1);intent2=NS(id='intent2',action='BTC_REDUCE',episode_id='parent',level=1);h._pending_by_order[str(other.client_order_id)]=intent2
    h._tp_bind_order(other,intent2);h._tp_native_event(other.init_event,'generic');h.cache.add_order(other)
    event=TestEventStubs.order_accepted(other,ts_event=6);other.apply(event);h.cache.update_order(other);h._tp_native_event(event,'typed')
    canceled=TestEventStubs.order_canceled(other,ts_event=7);other.apply(canceled);h.cache.update_order(other);del h._pending_by_order[str(other.client_order_id)]
    h._tp_native_event(canceled,'generic');assert other.is_closed
    # Lost live mapping and foreign immutable owner remain strict failures.
    live=TestExecStubs.limit_order(instrument=BTC_PERP,order_side=OrderSide.SELL,quantity=BTC_PERP.make_qty(D('.212')),price=BTC_PERP.make_price(D(101)),reduce_only=True,client_order_id=ClientOrderId('UNIT-LOST-LIVE'))
    intent3=NS(id='intent3',action='BTC_REDUCE',episode_id='parent',level=2);h._pending_by_order[str(live.client_order_id)]=intent3;h._tp_bind_order(live,intent3);h.cache.add_order(live)
    event=TestEventStubs.order_accepted(live,ts_event=8);live.apply(event);h.cache.update_order(live);del h._pending_by_order[str(live.client_order_id)]
    try:h._tp_native_event(event,'typed')
    except ValueError as error:assert 'CURRENT_OWNER_UNKNOWN'in str(error)
    else:raise AssertionError('LOST_LIVE_OWNER_ACCEPTED')
    # Explicit valid-controller native rejection remains fatal.
    from nautilus_trader.model.events import OrderModifyRejected,OrderAccepted
    from nautilus_trader.model.identifiers import StrategyId,AccountId
    from nautilus_trader.core.uuid import UUID4
    h._pending_by_order[str(live.client_order_id)]=intent3
    foreign=OrderAccepted(live.trader_id,StrategyId('FOREIGN-001'),live.instrument_id,live.client_order_id,live.venue_order_id,AccountId('UNIT-001'),UUID4(),9,9)
    try:h._tp_native_event(foreign,'generic')
    except ValueError as error:assert 'FOREIGN_EVENT_OWNER'in str(error)
    else:raise AssertionError('FOREIGN_OWNER_ACCEPTED')
    rejected=OrderModifyRejected(live.trader_id,live.strategy_id,live.instrument_id,live.client_order_id,live.venue_order_id,live.account_id,'UNIT_REJECTION',UUID4(),10,10)
    try:h._tp_native_event(rejected,'typed')
    except ValueError as error:assert 'VALID_MODIFY_REJECTED'in str(error)
    else:raise AssertionError('VALID_MODIFY_REJECTION_WAIVED')
    # Actual controller debt observation with native quantity getter isolated as
    # an explicit method-unit input, never a simulated monetary outcome.
    h._pair= {'parent':'parent','caps':NS(bmax=D('.752')),'debt_since':10}
    assert h._tp_debt_clock(20,False)is None
    assert h._tp_debt_clock(80_000_000_020,False)is None
    assert h._tp_debt_clock(90_000_000_020,True)==90_000_000_020 and h._pair['debt_since']==10
    assert h._tp_debt_clock(91_000_000_020,True)==90_000_000_020 and not h._pair['standing_debt_deferred']
    h._pair_qty=lambda instrument:D('.940')
    state=h._tp_debt_observe(20,'UNIT_RESIDUAL');assert state['residual_debt']=='0.188'and state['duration_ns']=='10'
    h._pair_qty=lambda instrument:D(0);h._tp_debt_observe(30,'UNIT_ORDINARY_FLAT')
    resolved=[e for e in h.standing_tp_audit if e['event']=='ACTUAL_DEBT_RESOLVED'];assert resolved[-1]['native_flat']is True and resolved[-1]['duration_ns']=='20'
    h.config.research_native_book.detailed=False
    before=len(h.standing_tp_audit);counts=h._tp_audit_counts.get('SETTLED',0)
    h._tp_log('SETTLED',40,label='UNIT_STABLE',leaves={1:159});h._tp_log('SETTLED',41,label='UNIT_STABLE',leaves={1:159})
    assert len(h.standing_tp_audit)==before+1 and h._tp_audit_counts['SETTLED']==counts+2
    return dict(status='REAL_NATIVE_CLASS_METHOD_UNIT_PASS',engine_constructors=0,native_matching_fills=0,simulated_cash=False,constructed_event_replay_not_native_evidence=True,checks=['bound_initialized_before_real_cache_add_no_ACK','real_submitted_accepted_dedup','real_order_partial_right_precheck','actual_native_class_pending_update_total_offset_latest_ACK_dedup','foreign_owner_and_valid_modify_rejection_STOP','state_change_audit_counts_every_guard','typed_full_terminal_then_generic_after_intent_loss_and_parent_rollover','real_cache_terminal_history_not_recreated','unknown_history_and_lost_live_owner_reject','actual_controller_debt_quantity_duration_resolution_method','marketable_defer_over60_then_safe_dispatch_clock_preserves_absolute_debt_age'])
