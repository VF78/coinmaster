"""Constructed real Cache/Order events; no matching engine or economic evidence."""
from types import SimpleNamespace as NS
from decimal import Decimal as D
import copy
import pytest
from nautilus_trader.cache.cache import Cache
from nautilus_trader.test_kit.stubs.execution import TestExecStubs
from nautilus_trader.test_kit.stubs.events import TestEventStubs
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.identifiers import ClientOrderId
from coinmaster.research.native_fixture import BTC_PERP
from coinmaster.strategy.standing_tp import StandingTPResearch

class Harness(StandingTPResearch):
    def __init__(self):
        self.config=NS(research_btc_standing_tp=True,research_a0_family="R2_A0_V1",research_paired_prefix="B2_F0",research_a0_original_second=False,research_sol_standing=False,btc_id=BTC_PERP.id,research_native_book=NS(detailed=True))
        self.cache=Cache();self.cache.add_instrument(BTC_PERP)
        self._domain=NS(episode=NS(id="P",side=1));self._md_plans={"P":dict(generation=0,order_generation={},entry_orders={},standing={0:233,1:233,2:634},consumed=set())}
        self._pending_by_order={};self._pair=None;self.held=0;self.cancels=[];self.releases=[];self.coverage=[];self._tp_init()
        self.orders=[self.add(i)for i in range(3)]
    def add(self,i,entry=False):
        o=TestExecStubs.limit_order(instrument=BTC_PERP,order_side=OrderSide.BUY if entry else OrderSide.SELL,quantity=BTC_PERP.make_qty(D(".233")),price=BTC_PERP.make_price(D(101+i)),reduce_only=not entry,client_order_id=ClientOrderId("UNIT-"+str(i)))
        self.id=o.strategy_id;oid=str(o.client_order_id)
        it=NS(id="intent"+str(i),action="BTC_ENTRY"if entry else"BTC_REDUCE",episode_id="P",level=i)
        self._pending_by_order[oid]=it
        if not entry:self._tp_bind_order(o,it)
        else:self._md_plans["P"]["entry_orders"][oid]=True
        self.cache.add_order(o);self.apply(o,TestEventStubs.order_accepted(o,ts_event=1))
        return o
    def apply(self,o,e):o.apply(e);self.cache.update_order(o);return e
    def _tp_held_lots(self):return self.held # Explicit method-unit input; no native position claimed.
    def _tp_transient_boundary(self,*a):pass
    def _md_coverage(self,*a):self.coverage.append(a)
    def _pair_release_if_terminal(self,ts):self.releases.append(ts)
    def cancel_order(self,o):
        self.cancels.append(str(o.client_order_id));self.apply(o,TestEventStubs.order_pending_cancel(o,ts_event=10))
    def drain(self):return self._tp_flat_owned_drain("P",self._md_plans["P"],10)
    def ack(self,o):
        e=self.apply(o,TestEventStubs.order_canceled(o,ts_event=12));self._pending_by_order.pop(str(o.client_order_id),None)
        self._tp_native_event(e,"typed");self._tp_native_event(e,"generic")

def test_public_cancel_once_waits_for_three_actual_event_history_acks():
    h=Harness();rights=copy.deepcopy(h._md_plans["P"]["standing"])
    assert h.drain()and len(h.cancels)==3 and h._tp_flat_terminal_busy()and not h.releases
    h.drain();assert len(h.cancels)==3
    for o in h.orders[:-1]:h.ack(o);assert h._tp_flat_terminal_busy()and not h.releases
    h.ack(h.orders[-1]);assert not h._tp_flat_terminal_busy()and h.releases==[12]
    assert h._md_plans["P"]["standing"]==rights and not h._md_plans["P"]["consumed"]
    assert len(h._tp_owners)==3 and all(x.get("terminal_event_id")for x in h._tp_owners.values())
    h.drain();assert len(h.cancels)==3 and h.releases==[12]

def test_pending_entry_waits_without_cancel_or_early_release_and_late_inventory_barrier():
    h=Harness();entry=h.add(9,True);h.drain()
    assert not h.cancels and h._tp_flat_terminal_busy()and not h.releases
    from nautilus_trader.model.identifiers import TradeId
    h.apply(entry,TestEventStubs.order_filled(entry,BTC_PERP,last_qty=BTC_PERP.make_qty(D(".100")),trade_id=TradeId("UNIT-LATE-ENTRY"),ts_event=11))
    h.held=100;assert h.drain()is False and h._tp_flat_terminal_busy()and not h.cancels
    assert not entry.is_closed and str(entry.client_order_id)in h._pending_by_order

def test_modify_pending_waits_then_real_updated_event_enters_cancel_path():
    h=Harness();o=h.orders[0];oid=str(o.client_order_id)
    h._tp_commands[oid]=dict(total=D(".233"),generation=0,sequence=1)
    h.apply(o,TestEventStubs.order_pending_update(o,ts_event=2));h.drain();assert not h.cancels
    e=h.apply(o,TestEventStubs.order_updated(o,quantity=o.quantity,ts_event=3));h._tp_native_event(e,"typed")
    assert not h._tp_commands and len(h.cancels)==3 and not h.releases

@pytest.mark.parametrize("kind",["missing_intent","foreign_side","unknown_entry"])
def test_ownership_unknown_rejects_before_any_cancel(kind):
    h=Harness()
    if kind=="missing_intent":h._pending_by_order.pop(str(h.orders[-1].client_order_id))
    elif kind=="foreign_side":h._tp_owners[str(h.orders[-1].client_order_id)]["side"]="BUY"
    else:
        e=h.add(9,True);h._md_plans["P"]["entry_orders"].clear();h._pending_by_order.pop(str(e.client_order_id))
    with pytest.raises(ValueError):h.drain()
    assert not h.cancels and not h.releases

@pytest.mark.parametrize("field,value",[("research_btc_standing_tp",False),("research_a0_family","OTHER"),("research_paired_prefix","")])
def test_default_off_other_family_never_cancels(field,value):
    h=Harness();setattr(h.config,field,value);assert h.drain()is False and not h.cancels

def test_terminal_callback_after_episode_retirement_keeps_old_ownership():
    h=Harness();h.drain();h._domain.episode=None
    for o in h.orders:h.ack(o)
    assert not h._tp_flat_terminal_busy()and len(h._tp_owners)==3 and len(h.releases)==1
