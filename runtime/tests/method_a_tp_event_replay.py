"""Real Cache/Order/Position class method-unit replay. No matching/economics.

Synthetic test events and explicit domain snapshots are unit inputs only, never
reported as actual native-engine fills, ACKs, balance, or M1 qualification.
"""
from types import SimpleNamespace as NS
from decimal import Decimal as D
from nautilus_trader.cache.cache import Cache
from nautilus_trader.model.position import Position
from nautilus_trader.model.enums import OrderSide, OmsType
from nautilus_trader.model.identifiers import ClientOrderId, TradeId, PositionId
from nautilus_trader.test_kit.stubs.execution import TestExecStubs
from nautilus_trader.test_kit.stubs.events import TestEventStubs
from coinmaster.domain.wave_overlay import Candidate, Episode, WaveOverlayState
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from coinmaster.strategy.method_a_tp import MethodATpResearch, cumulative_entitlement


def replay_proof():
    class Harness(MethodATpResearch):
        def __init__(self):
            self.config=NS(research_method_a_tp=True,btc_id=BTC_PERP.id,tp_fee_floor_v1=False)
            self.cache=Cache();self.cache.add_instrument(BTC_PERP);self.cache.add_instrument(SOL_PERP)
            self._candidate=Candidate(btc_tp_fractions_initial_qty=(.2125,.2125,.575))
            self._domain=WaveOverlayState(self._candidate)
            ep=Episode('UNIT-PARENT',1,10000,1,wave_levels=(.01,.02,.03),h=10000)
            ep.btc_entry_qty_exact=D(2);ep.btc_entry_notional_exact=D(200);ep.btc_initial_qty=2;ep.btc_open_qty=2
            ep.btc_entry_vwap=100;ep.btc_planref_vwap=D(100);ep.btc_net_planned_qty=2
            self._domain.episode=ep
            self._pending_by_order={};self._bars=[];self._forced_close_reason=None;self._liquidating=False
            self._split_parent=dict(first_vwap=D(100),deadline_ns=4*3600*10**9,fallback=False)
            self.cancelled=[];self.modified=[];self.submitted=[];self._ma_init()
            self._ma_plans[ep.id]=dict(d3=D('.03'),expected_cancels=set(),raw_target_lots={0:425,1:425,2:1150})
        def _bind_native_lots(self):self._domain.set_execution_lots(btc=D('.001'),sol=D('.1'))
        def modify_order(self,order,quantity,price):
            self.modified.append((str(order.client_order_id),quantity,price))
            event=TestEventStubs.order_pending_update(order,ts_event=20+len(self.modified))
            order.apply(event);self.cache.update_order(order)
        def cancel_order(self,order):self.cancelled.append(str(order.client_order_id))
        def _begin_forced_close(self,reason):raise AssertionError(reason)
        def _submit_intent(self,intent,*a,**k):
            self.submitted.append(intent)
            order=TestExecStubs.limit_order(instrument=BTC_PERP,order_side=OrderSide.SELL,
                quantity=BTC_PERP.make_qty(D(str(intent.quantity))),price=BTC_PERP.make_price(D(str(intent.limit_price))),
                reduce_only=True,client_order_id=ClientOrderId('UNIT-NEW-'+str(len(self.submitted))))
            self._pending_by_order[str(order.client_order_id)]=intent;self._ma_bind_order(order,intent)
            self.cache.add_order(order)
            event=TestEventStubs.order_accepted(order,ts_event=50+len(self.submitted));order.apply(event);self.cache.update_order(order);self._ma_native_event(event)
    h=Harness();ep=h._domain.episode
    buy=TestExecStubs.market_order(instrument=BTC_PERP,order_side=OrderSide.BUY,quantity=BTC_PERP.make_qty(D(2)))
    fill=TestEventStubs.order_filled(buy,BTC_PERP,last_qty=BTC_PERP.make_qty(D(2)),last_px=BTC_PERP.make_price(D(100)),trade_id=TradeId('UNIT-ENTRY'),position_id=PositionId('UNIT-POSITION'),ts_event=1)
    position=Position(BTC_PERP,fill);h.cache.add_position(position,OmsType.NETTING)
    old_grants,_=cumulative_entitlement(1000,{},{});orders=[]
    for i,n in old_grants.items():
        order=TestExecStubs.limit_order(instrument=BTC_PERP,order_side=OrderSide.SELL,
            quantity=BTC_PERP.make_qty(D(n)*D('.001')),price=BTC_PERP.make_price(D(101+i)),reduce_only=True,
            client_order_id=ClientOrderId('UNIT-TP-'+str(i)))
        h.id=order.strategy_id
        intent=h._domain._intent(ep,'BTC_REDUCE',-1,i,quantity=float(D(n)*D('.001')),limit_price=101+i)
        h._pending_by_order[str(order.client_order_id)]=intent;h._ma_bind_order(order,intent)
        h.cache.add_order(order);event=TestEventStubs.order_accepted(order,ts_event=2+i);order.apply(event);h.cache.update_order(order)
        h._ma_owners[str(order.client_order_id)]['ack']=True;orders.append(order)
    h._ma_reconcile(10)
    assert len(h.modified)==3 and h.cancelled==[] and not h._ma_entry_ready()
    assert all(o.status.name=='PENDING_UPDATE' for o in orders)
    assert [o.leaves_qty.as_decimal() for o in orders]==[D('.212'),D('.213'),D('.575')]
    # TP0 fully fills while update is pending. Its native terminal history
    # releases that command even if no update/cancel ACK will ever follow.
    order=orders[0];oid=str(order.client_order_id)
    h._ma_plans[ep.id]['expected_cancels'].add(oid)
    event=TestEventStubs.order_filled(order,BTC_PERP,last_qty=order.leaves_qty,last_px=order.price,trade_id=TradeId('UNIT-LATE-TERMINAL'),position_id=PositionId('UNIT-POSITION'),ts_event=30)
    order.apply(event);h.cache.update_order(order);position.apply(event);h.cache.update_position(position)
    h._ma_before_fill(event)
    assert oid not in h._ma_commands and oid not in h._ma_plans[ep.id]['expected_cancels']
    # Domain post-fill snapshot supplied as a method-unit boundary, no on_fill.
    ep.btc_tp_filled_lots[0]=212;ep.btc_tp_filled_qty[0]=.212;ep.btc_open_qty=1.788
    h._pending_by_order.pop(oid);h._domain.on_parent_terminal(h._ma_owners[oid]['intent_id'])
    h._ma_reconcile(31)
    assert h.submitted[-1].level==0 and D(str(h.submitted[-1].quantity))==D('.213')
    assert h.cancelled==[] and len(h.modified)==3
    for order in orders[1:]:
        oid=str(order.client_order_id);command=h._ma_commands[oid]
        event=TestEventStubs.order_updated(order,quantity=BTC_PERP.make_qty(command['total']),price=BTC_PERP.make_price(command['price']),ts_event=40)
        order.apply(event);h.cache.update_order(order);h._ma_native_event(event);h._ma_native_event(event)
    h._ma_reconcile(60)
    assert h._ma_entry_ready() and not h._ma_commands and h.cancelled==[]
    assert h.cache.positions_open()[0].quantity.as_decimal()==D('1.788')
    state=[x for x in h.method_a_tp_audit if x['event']=='ENTITLEMENT'][-1]
    assert state['leaves']=={0:213,1:425,2:1150} and sum(state['acknowledged_current_lots'].values())==1788
    return dict(status='METHOD_UNIT_REPLAY_PASS',engine_constructors=0,
        public_modify_commands=3,cancel_commands=0,real_native_class_terminal_fill_retired_command=True,
        real_Cache_Position_quantity='1.788',duplicate_ACK_delivery_ignored=True,
        new_TP0_rights_only='.213',economic_or_native_M1_evidence=False)
