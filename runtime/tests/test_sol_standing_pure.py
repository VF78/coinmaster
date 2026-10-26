"""Real native Cache/Order/event method tests. No matching/engine/financial claim."""
from types import SimpleNamespace as NS
from decimal import Decimal as D
from pathlib import Path
import ast
from nautilus_trader.cache.cache import Cache
from nautilus_trader.test_kit.stubs.execution import TestExecStubs
from nautilus_trader.test_kit.stubs.events import TestEventStubs
from nautilus_trader.model.enums import OrderSide, TriggerType, TimeInForce
from nautilus_trader.model.orders import StopMarketOrder
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.model.identifiers import ClientOrderId, TradeId
from coinmaster.research.native_fixture import SOL_PERP
from coinmaster.strategy.paired_prefix import PairedPrefixResearch, sol_prices


class Harness(PairedPrefixResearch):
    """Explicit method-unit inventory input; no positions or matcher fabricated."""
    def __init__(self):
        self.config=NS(research_sol_standing_protection=True,sol_id=SOL_PERP.id)
        self.cache=Cache();self.cache.add_instrument(SOL_PERP)
        self.id=TestExecStubs.limit_order(instrument=SOL_PERP).strategy_id
        self.clock=NS(timestamp_ns=lambda:10)
        self._pair_sol_events=set();self._pair_orders={};self.paired_prefix_audit=[]
        self.held=D(2);self.commands=[];self.cancels=[];self.failures=[]
        self._pair=dict(parent='P',p0=D(100),atr=D(2),side=1,tp_lots={0:5,1:5,2:10},
            consumed=set(),signature=None,generation=0,protection_since=None,close_sol=False)
    def _pair_qty(self,instrument):return self.held
    def _pair_fail(self,reason,ns):self.failures.append(reason)
    def _pair_submit(self,instrument,side,qty,kind,ns,price=None,stop=None,level=None):
        assert price is not None, 'Initial STOP supplied explicitly by test'
        raise AssertionError('Unexpected protection resurrection')
    def modify_order(self,order,**kw):
        self.commands.append((str(order.client_order_id),kw))
        e=TestEventStubs.order_pending_update(order,ts_event=10);order.apply(e);self.cache.update_order(order)
    def cancel_order(self,order):
        self.cancels.append(str(order.client_order_id))
        e=TestEventStubs.order_pending_cancel(order,ts_event=10);order.apply(e);self.cache.update_order(order)
    def add(self,order,kind,level=None):
        self.cache.add_order(order)
        e=TestEventStubs.order_accepted(order,ts_event=1);order.apply(e);self.cache.update_order(order)
        oid=str(order.client_order_id)
        self._pair_orders[oid]=dict(instrument=SOL_PERP.id,kind=kind,level=level,parent='P',
            initial_oid=oid,initialized_event_id=str(order.init_event.id),accepted=True,pending=None,ack=None,command_sequence=0)
        return order


def owner():
    h=Harness();prices,stop=sol_prices(D(100),D(2),-1,SOL_PERP.price_increment.as_decimal())
    for level,qty in enumerate(('.5','.5','1.0')):
        h.add(TestExecStubs.limit_order(instrument=SOL_PERP,order_side=OrderSide.BUY,
            quantity=SOL_PERP.make_qty(D(qty)),price=SOL_PERP.make_price(prices[level]),
            reduce_only=True,client_order_id=ClientOrderId('UNIT-TP'+str(level))),'TP',level)
    order=StopMarketOrder(trader_id=TestExecStubs.limit_order(instrument=SOL_PERP).trader_id,
        strategy_id=h.id,instrument_id=SOL_PERP.id,order_side=OrderSide.BUY,
        trigger_type=TriggerType.DEFAULT,init_id=UUID4(),ts_init=0,time_in_force=TimeInForce.IOC,
        quantity=SOL_PERP.make_qty(D(2)),trigger_price=SOL_PERP.make_price(stop),reduce_only=True,
        client_order_id=ClientOrderId('UNIT-STOP'))
    h.add(order,'STOP');return h


def unit_fill(h,level,qty):
    oid='UNIT-TP'+str(level);o=h.cache.order(ClientOrderId(oid))
    e=TestEventStubs.order_filled(o,SOL_PERP,last_qty=SOL_PERP.make_qty(D(qty)),
        trade_id=TradeId('UNIT-'+level.__str__()+'-'+qty),ts_event=2)
    o.apply(e);h.cache.update_order(o)
    # Isolated entitlement/quantity method inputs; execution not simulated.
    h.held-=D(qty);h._pair['tp_lots'][level]-=int(D(qty)/SOL_PERP.size_increment.as_decimal())
    if o.is_closed:h._pair['consumed'].add(level);h._pair['tp_lots'].pop(level)
    return e


def ack(h,oid,total):
    o=h.cache.order(ClientOrderId(oid));e=TestEventStubs.order_updated(o,quantity=SOL_PERP.make_qty(D(total)),ts_event=11)
    o.apply(e);h.cache.update_order(o)
    h._pair_sol_native_event(e,'typed');h._pair_sol_native_event(e,'generic');return e


def test_ordinary_partial_preserves_all_tp_oids_and_stop_same_oid_ack():
    h=owner();h._pair_sol_protect(1);assert not h.commands and not h.cancels and not h.failures
    unit_fill(h,0,'.2');h._pair_sol_protect(2)
    assert [oid for oid,_ in h.commands]==['UNIT-STOP'] and not h.cancels
    assert h.commands[0][1]['quantity'].as_decimal()==D('1.8')
    assert h._pair['protection_since']==2
    ack(h,'UNIT-STOP','1.8')
    assert h._pair['protection_since'] is None and not h.failures
    assert len([x for x in h.paired_prefix_audit if x['event']=='SOL_LATEST_MODIFY_ACK'])==1
    assert h._pair['tp_lots']=={0:3,1:5,2:10}


def test_coalesces_pending_then_uses_latest_entitlement_after_real_class_ack():
    h=owner();unit_fill(h,0,'.2');h._pair_sol_protect(2)
    unit_fill(h,0,'.1');h._pair_sol_protect(3)
    assert len(h.commands)==1 and h._pair['protection_since']==2
    ack(h,'UNIT-STOP','1.8')
    assert len(h.commands)==2 and h.commands[-1][1]['quantity'].as_decimal()==D('1.7')
    assert h._pair['protection_since']==2
    ack(h,'UNIT-STOP','1.7');assert h._pair['protection_since'] is None and not h.failures


def test_consumed_tp_never_resurrected_and_other_leaves_constant():
    h=owner();unit_fill(h,0,'.5');h._pair_sol_protect(2);ack(h,'UNIT-STOP','1.5')
    assert h._pair['consumed']=={0} and h._pair['tp_lots']=={1:5,2:10}
    assert len(h._pair_orders)==4 and not h.cancels and not h.failures
    assert h.cache.order(ClientOrderId('UNIT-TP1')).leaves_qty.as_decimal()==D('.5')


def test_pending_cancel_never_modified_and_flat_still_drains_stop():
    h=owner();o=h.cache.order(ClientOrderId('UNIT-STOP'));h.cancel_order(o)
    unit_fill(h,0,'.2');h._pair_sol_protect(2)
    assert not h.commands and h._pair['protection_since'] is not None
    h.held=D(0);h._pair_sol_protect(3)
    assert h._pair is not None and len(h.cancels)==4 and h._pair['protection_since'] is None


def test_native_history_missing_is_unknown_no_ack():
    h=owner();unit_fill(h,0,'.2');h._pair_sol_protect(2)
    o=h.cache.order(ClientOrderId('UNIT-STOP'))
    e=TestEventStubs.order_updated(o,quantity=SOL_PERP.make_qty(D('1.8')),ts_event=11)
    h._pair_sol_native_event(e,'generic')
    assert h.failures==['SOL_NATIVE_EVENT_OWNERSHIP_OR_HISTORY_UNKNOWN']
    assert h._pair_orders['UNIT-STOP']['pending'] is not None


def test_unapplied_same_stack_inventory_does_not_send_stale_total():
    h=owner();h.held=D('1.8');h._pair_sol_protect(2)
    assert not h.commands and not h.cancels and h._pair['protection_since']==2


def test_no_engine_constructor_and_unchanged_legacy_body():
    root=Path(__file__).resolve().parents[1]
    paths=[root/'coinmaster/strategy/paired_prefix.py',root/'coinmaster/strategy/wave_overlay.py',Path(__file__)]
    for p in paths:
        tree=ast.parse(p.read_text())
        assert not any(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='BacktestEngine' for n in ast.walk(tree))
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategyConfig
    assert WaveOverlayStrategyConfig.__struct_defaults__[WaveOverlayStrategyConfig.__struct_fields__.index('research_sol_standing_protection')-len(WaveOverlayStrategyConfig.__struct_fields__)] is False


def test_exact_matching_barrier_is_strict_without_mutating_orders():
    h=owner();h._pair_sol_protect(1);h._pair_sol_boundary('UNIT_MATCH_INPUT',1,strict=True)
    unit_fill(h,0,'.2');h._pair_sol_protect(2)
    import pytest
    with pytest.raises(ValueError,match='EXACT_COVERAGE_UNKNOWN'):
        h._pair_sol_boundary('UNIT_MATCH_INPUT',2,strict=True)
    assert h._pair['protection_since']==2 and len(h.commands)==1
    ack(h,'UNIT-STOP','1.8');h._pair_sol_boundary('UNIT_MATCH_INPUT',12,strict=True)
    assert h.paired_prefix_audit[-1]['state']=='PROTECTED'and not h.failures


def test_disabled_a0_still_observes_and_does_not_create_right_or_call_margin_gate():
    from copy import deepcopy
    from coinmaster.research.native_fixture import BTC_PERP
    h=owner();h.cache.add_instrument(BTC_PERP)
    h.config.research_paired_prefix='B2_F0';h.config.btc_id=BTC_PERP.id
    h.config.research_btc_split_discount=D('.0025');h.config.margin_policy=None
    h._pair_observed_rights={};h._pair_observed_marks={};h._pair_predecisions=[]
    h._pair_last_quote={};h._pending_by_order={};h._pair['caps']=NS(bmax=D(2))
    h._pair.update(risk='ACTIVE_RISK',entry_terminal=True,debt_since=None)
    h._split_parent=dict(episode_id='P',quantity=D(4),first_quantity=D(2),side=1)
    h._md_plans={'P':dict(entry_orders={'original-second':'SECOND'},p0=D(100),
        first_filled=D(2),second_filled=D('.1'),touched=set())}
    h._a0_enabled=lambda:False;h._entries_enabled=lambda **kw:True
    h._tier_allows_increase=lambda *args:(_ for _ in ()).throw(AssertionError('OBSERVER_CALLED_STOCK_GATE'))
    before=deepcopy(h._md_plans);h._pair_observe_lock(10)
    assert h._md_plans==before and 'a0'not in h._md_plans['P']
    row=h._pair_predecisions[-1]
    assert row['remaining']=='1.9'and row['native_account']=='UNKNOWN'
    assert row['stock_margin_invoked']is False and row['a0_trading_enabled']is False
    assert row['stock_margin_result']=='UNKNOWN_NOT_EXECUTED_OBSERVER'
    import json
    json.dumps(row,allow_nan=False)
    h._pair['risk']='INACTIVE_RISK';h._pair_predecision(20,'PRE_A0_DECISION')
    assert h._pair_predecisions[-1]['off_ns']=='20'and h._pair_predecisions[-1]['off_plus60_ready']is False


def test_real_class_fill_updates_only_own_right_once_via_product_handler():
    from coinmaster.strategy.paired_prefix import PairedCaps
    from coinmaster.research.native_fixture import BTC_PERP
    h=owner();h.config.btc_id=BTC_PERP.id;h._pair_seen_fills=set();h._tp_enabled=lambda:False
    caps=PairedCaps(D(2),D(1),D('.001'),D('.1'),D(2));caps.entry_terminal(D(2))
    h._pair.update(caps=caps,risk='ACTIVE_RISK',last_btc=D(2),debt_since=None)
    o=h.cache.order(ClientOrderId('UNIT-TP0'))
    e=TestEventStubs.order_filled(o,SOL_PERP,last_qty=SOL_PERP.make_qty(D('.2')),trade_id=TradeId('PRODUCT-PARTIAL'),ts_event=2)
    o.apply(e);h.cache.update_order(o);h.held=D('1.8')
    assert h._pair_fill(e)and h._pair['tp_lots']=={0:3,1:5,2:10}
    assert h._pair_fill(e)and h._pair['tp_lots']=={0:3,1:5,2:10}
    assert len(h.commands)==1 and h.commands[0][0]=='UNIT-STOP'


def test_predecision_price_motion_coalesces_but_first_off60_quote_is_kept():
    # Reuse the disabled-A0 object setup, then build explicit shadow-only inputs.
    from coinmaster.research.native_fixture import BTC_PERP
    from nautilus_trader.model.data import QuoteTick
    h=owner();h.cache.add_instrument(BTC_PERP)
    h.config.research_paired_prefix='B2_F0';h.config.btc_id=BTC_PERP.id;h.config.margin_policy=None
    h.config.research_native_book=None;h.config.research_btc_split_discount=D('.0025')
    h._pair_observed_rights={};h._pair_observed_marks={};h._pair_predecisions=[];h._pair_last_quote={};h._pending_by_order={}
    h._pair.update(caps=NS(bmax=D(2)),risk='ACTIVE_RISK',entry_terminal=True,debt_since=None)
    h._split_parent=dict(episode_id='P',quantity=D(4),first_quantity=D(2),side=1)
    h._md_plans={'P':dict(entry_orders={},p0=D(100),first_filled=D(2),second_filled=D(0),touched=set())}
    h._a0_enabled=lambda:False;h._entries_enabled=lambda **kw:True
    h._pair_observe_lock(1);h._pair['risk']='INACTIVE_RISK';h._pair_predecision(2,'RISK_OFF')
    for n in range(1,1001):
        ns=60_000_000_002+n;px=BTC_PERP.make_price(D(100)+D(n)/10)
        tick=QuoteTick(BTC_PERP.id,px,px,BTC_PERP.make_qty(D(1)),BTC_PERP.make_qty(D(1)),ns,ns)
        h._pair_predecision(ns,'AFTER_MD_RECONCILE_BEFORE_A0',tick)
    assert len(h._pair_predecisions)==3 and h._pair_predecision_counts['coalesced']==999
    row=h._pair_predecisions[-1]
    assert row['reason']=='FIRST_BTC_QUOTE_AFTER_RISK_OFF_PLUS60'and row['off_plus60_ready']
    assert row['observer_reason']=='ORIGINAL_RIGHT_NOT_ESTABLISHED'and not row['a0_trading_enabled']


def test_sol_pending_gate_preserves_original_risk_off_clock():
    from test_a0_rights_pure import guarded_owner
    from coinmaster.strategy.a0_rights import A0RightsResearch
    from copy import copy
    original,ep,m,a,orders,quote=guarded_owner()
    class Combined(PairedPrefixResearch,A0RightsResearch):pass
    h=Combined();h.__dict__.update(original.__dict__)
    h.config.research_sol_standing_protection=True;h._pair['protection_since']=1
    a['off_ns']=None
    h._a0_check(quote)
    assert a['off_ns']==quote.ts_event and not a['attempted']
    later=copy(quote);later.ts_event+=60_000_000_000
    h._a0_check(later)
    assert a['off_ns']==quote.ts_event and not a['attempted']


def test_any_stop_fill_closes_before_partial_ioc_terminal_callback():
    from coinmaster.strategy.paired_prefix import PairedCaps
    from coinmaster.research.native_fixture import BTC_PERP
    h=owner();h.config.btc_id=BTC_PERP.id;h._pair_seen_fills=set();h._tp_enabled=lambda:False
    caps=PairedCaps(D(2),D(1),D('.001'),D('.1'),D(2));caps.entry_terminal(D(2))
    h._pair.update(caps=caps,risk='ACTIVE_RISK',last_btc=D(2),debt_since=None)
    o=h.cache.order(ClientOrderId('UNIT-STOP'))
    # Native STOP_MARKET fills directly; OrderTriggered is limit-stop only.
    e=TestEventStubs.order_filled(o,SOL_PERP,last_qty=SOL_PERP.make_qty(D('.1')),trade_id=TradeId('PARTIAL-STOP-BEFORE-CANCEL'),ts_event=3)
    o.apply(e);h.cache.update_order(o);h.held=D('1.9')
    assert not o.is_closed and h._pair_fill(e)
    assert h._pair['close_sol']and not h.commands and not h.cancels
    h._pair_sol_protect(4);assert not h.commands and not h.cancels
    assert h.paired_prefix_audit[-1]['event']=='ACTUAL_FILL'
