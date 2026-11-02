"""Synthetic source/model boundaries only. No Strategy/Engine/Node/financial PASS."""
from dataclasses import asdict
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N, MethodType
import hashlib
import json
import sqlite3
import pytest
from coinmaster.strategy.cm2_btc_policy import (BtcConfig,BtcPolicy,BtcDay,BtcCycle,DAY,HOUR,
    partition_lots,equal_split_quantity,breakeven_price)
from coinmaster.strategy.cm2_checkpoint import canonical,decode
from coinmaster.strategy.cm2_native import CM2Strategy
from coinmaster.strategy.cm2_execution import SafetyState,ExecutionLimits,NativeExposure
from coinmaster.strategy.cm2_order_contract import FRESH_NS,MODEL_ID


@pytest.fixture(autouse=True)
def no_native_economic_constructor(monkeypatch):
    import nautilus_trader.backtest.engine as engine
    def forbidden(*args,**kwargs):raise AssertionError('CODE0_NATIVE_ECONOMIC_CONSTRUCTOR_FORBIDDEN')
    monkeypatch.setattr(engine,'BacktestEngine',forbidden)
    monkeypatch.setattr(CM2Strategy,'__new__',staticmethod(forbidden))


def policy():
    p=BtcPolicy(BtcConfig(),step=D('.00001'),start_ns=30*DAY,end_ns=100*DAY)
    for i in range(30):
        c=100+i*.3
        p.accept_day(BtcDay(i*DAY,(i+1)*DAY,(i+1)*DAY,c-.1,c+2,c-2,c),receipt_ns=(i+1)*DAY)
    return p


def cycle(p,quantity='1'):
    f=p.signals[-1]
    p.parent=BtcCycle('synthetic-cycle',f.side,f.index,p.days[-1].close_ns,D(quantity),D(quantity)/2,funding_total=D(0))
    return p.parent


def test_exact_existing_ema_and_wilder_seed_math_without_sol():
    from datetime import datetime,timezone
    from coinmaster.strategy.cm2_reference_policy import ReferenceBtcPolicy,ReferenceFlags,selected_btc_candidate
    from coinmaster.domain.wave_overlay import DailyBar
    old=ReferenceBtcPolicy(selected_btc_candidate(),flags=ReferenceFlags(True,True),btc_step=D('.00001'),
        trading_start_ns=30*DAY,terminal_ns=100*DAY,max_quote_age_ns=FRESH_NS,initial_btc_equity=D(10000))
    p=policy()
    for d in p.days:
        dt=lambda n:datetime.fromtimestamp(n/1e9,timezone.utc)
        old.accept_closed_day(DailyBar(dt(d.open_ns),dt(d.close_ns),dt(d.available_ns),d.open,d.close,1.),
            receipt_ns=d.available_ns,btc_high=d.high,btc_low=d.low)
        assert p.signals[len(old.signals)-1].ema.hex()==old._features.ema.hex()
    assert p.atr.hex()==old._atr_reentry().hex()
    assert 'sol' not in p.snapshot() and 'beta' not in p.snapshot()


@pytest.mark.parametrize('bad',['gap','future','open','nan'])
def test_closed_btc_day_rejects_bad_causal_facts(bad):
    p=policy();d=BtcDay(30*DAY,31*DAY,31*DAY,100,102,98,101)
    if bad=='gap':d=BtcDay(31*DAY,32*DAY,32*DAY,100,102,98,101)
    if bad=='open':d=BtcDay(30*DAY,31*DAY-1,31*DAY,100,102,98,101)
    if bad=='nan':d=BtcDay(30*DAY,31*DAY,31*DAY,100,102,98,float('nan'))
    with pytest.raises(ValueError):p.accept_day(d,receipt_ns=30*DAY if bad=='future' else 32*DAY)


def test_fresh_d1_only_after_flat_and_h4_only_after_regime():
    p=policy();assert p.entry_signal(30*DAY)
    c=p.open_cycle(side=1,equity=D(1000),executable=D(100),now=30*DAY,funding_total=D(0))
    c.entry_filled=D(1)
    p.confirm_flat(now=30*DAY+1,native_flat=True,owners_terminal=True)
    assert not p.entry_signal(30*DAY+2)
    p.accept_day(BtcDay(30*DAY,31*DAY,31*DAY,110,113,109,112),receipt_ns=31*DAY)
    assert p.entry_signal(31*DAY)
    c=cycle(p);c.close_reason='REGIME';p.confirm_flat(now=31*DAY,native_flat=True,owners_terminal=True)
    p._h4_release_daily_ns=None
    p.accept_h4(open_ns=31*DAY,close_ns=31*DAY+4*HOUR,available_ns=31*DAY+4*HOUR,
        receipt_ns=31*DAY+4*HOUR,close=D(150))
    assert p._h4_release_daily_ns is None
    saved=decode(json.loads(canonical(p.snapshot())));q=policy();q.restore(saved)
    assert q.consume_h4(31*DAY+4*HOUR) and q.reentry_allowed()
    q.accept_h4(open_ns=31*DAY,close_ns=31*DAY+4*HOUR,available_ns=31*DAY+4*HOUR,
        receipt_ns=31*DAY+4*HOUR,close=D(150))
    assert not q.consume_h4(31*DAY+4*HOUR+1)


def test_equal_halves_lot_rounding_and_no_old_parent_cap():
    q=equal_split_quantity(D(1000),D(100),D('.01'))
    assert q==D('78.74') and q/2==D('39.37')
    assert equal_split_quantity(D('1e8'),D(100),D('.01'))*100>D(30000000)
    assert partition_lots(101)==(30,40,31)


def test_actual_partial_entry_tp_weights_first_tp1_growth_latch_and_latefill():
    p=policy();c=cycle(p)
    assert p.entry_fill(trade_id='a',quantity=D('.5'),price=D(100),commission=D('.0216'),first_leg=True)
    assert p.target_lots()==(15000,20000,15000)
    assert not p.entry_fill(trade_id='a',quantity=D('.5'),price=D(100),commission=D('.0216'),first_leg=True)
    p.reduction_fill(trade_id='b',quantity=D('.01'),before_quantity=D('.5'),level=0)
    assert c.be_armed and c.growth_stopped
    assert c.remaining_cost==D('.021168')
    p.entry_fill(trade_id='late',quantity=D('.1'),price=D(99),commission=D('.0042768'),first_leg=False)
    assert c.growth_stopped and p.target_lots()==(17000,24000,18000)
    assert sum(p.target_lots())*p.step==D('.59')
    assert not p.reduction_fill(trade_id='b',quantity=D('.01'),before_quantity=D('.5'),level=0)


@pytest.mark.parametrize('side',[1,-1])
def test_fee_aware_be_uses_remaining_actual_cost_and_unbooked_exit_fee(side):
    p=policy();c=cycle(p)
    p.entry_fill(trade_id='a',quantity=D(1),price=D(100),commission=D('.0432'),first_leg=True)
    p.observe_funding(D('.01'))
    p.reduction_fill(trade_id='tp',quantity=D('.3'),before_quantity=D(1),level=0)
    assert c.remaining_cost==D('.02324')
    be=breakeven_price(side=side,native_average=D(100),native_quantity=D('.7'),remaining_cost=c.remaining_cost,exit_fee_rate=D('.000432'))
    gross=(be-D(100))*D(side)*D('.7')
    assert abs(gross-c.remaining_cost-be*D('.7')*D('.000432'))<D('1e-24')
    assert c.remaining_cost==D('.02324') # price reserve does not charge cash or cost twice


def native_shell(qty=D('.5')):
    from nautilus_trader.cache.cache import Cache
    from nautilus_trader.common.component import TestClock
    from nautilus_trader.common.factories import OrderFactory
    from nautilus_trader.model.identifiers import TraderId,StrategyId,PositionId,AccountId
    from nautilus_trader.model.enums import OrderSide,OmsType
    from nautilus_trader.model.position import Position
    from nautilus_trader.model.objects import Money
    from nautilus_trader.test_kit.stubs.events import TestEventStubs
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    profile=load_current_hl_diagnostic(Path(__file__).parent/'fixtures/hl-current-20261029')
    btc,sol=profile.instruments;cache=Cache();cache.add_instrument(btc);cache.add_instrument(sol)
    clock=TestClock();clock.set_time(30*DAY);sid=StrategyId('BTC-001');aid=AccountId('HYPERLIQUID-001')
    factory=OrderFactory(TraderId('TEST-001'),sid,clock)
    seed=factory.market(btc.id,OrderSide.BUY,btc.make_qty(qty))
    seed.apply(TestEventStubs.order_accepted(seed,account_id=aid,ts_event=30*DAY))
    fill=TestEventStubs.order_filled(seed,btc,account_id=aid,position_id=PositionId('BTC-POS'),
        last_px=btc.make_price(100),commission=Money(0,btc.quote_currency),ts_event=30*DAY)
    seed.apply(fill);cache.add_order(seed);pos=Position(btc,fill);cache.add_position(pos,OmsType.NETTING)
    account=N(base_currency=btc.quote_currency)
    facade=N(instrument=cache.instrument,order=cache.order,orders_open=cache.orders_open,orders_inflight=cache.orders_inflight,
        positions_open=cache.positions_open,position_id=cache.position_id,account_for_venue=lambda v:account)
    b=policy();c=cycle(b);c.entry_filled=qty;c.first_filled=qty;c.first_value=qty*100;c.first_terminal=True
    reader=lambda i:D(0);reader.journal=N()
    s=N(id=sid,config=N(policy=BtcConfig(),btc_id=btc.id,sol_id=sol.id,btc_step=btc.size_increment.as_decimal(),
        limits=ExecutionLimits(D('1e100')),margin_policy=profile.margin_policy(FRESH_NS),exit_fee_rate=D('.000432'),
        funding_reader=reader,execution_policy_hash='synthetic-only'),btc=b,cache=facade,clock=clock,
        safety=SafetyState(),_owned={},_order_audit={},_seen_trade_ids=set(),_drain={},_drain_dispatching=set(),
        _entry_dispatching=False,_protection_dispatching=False,_restore_failed=False,_needs_daily=False,
        _latest_marks={},target_blockers={},pre_submit_gate_blocks=[],entry_sizing_audit=[],fill_audit=[],liquidation_audit=[],
        _liquidating=False,_retained_audit_chain='0'*64,cm2_audit=[],drain_audit=[])
    money=lambda x:N(as_decimal=lambda:D(x))
    tick=N(instrument_id=btc.id,ts_event=30*DAY,bid_price=money('99.9'),ask_price=money('100.1'))
    s._quotes={btc.id:tick}
    sent=[]
    def submit(order):
        cache.add_order(order)
        order.apply(TestEventStubs.order_accepted(order,account_id=aid,ts_event=30*DAY));cache.update_order(order)
        sent.append(order)
    s.submit_order=submit;s.order_factory=factory;s._persist_checkpoint=lambda:None
    s._admit=lambda *a:True # explicit synthetic admission boundary, not a money proof
    s._snapshot=lambda now:NativeExposure(D('1e9'),pos.quantity.as_decimal(),D(0),D(100),D(0),False,True,{btc.id:True,sol.id:False})
    for name in ('_send','_orders','_position','_contract_spec','_format_price','_funding','_sync_protection','_fill_owner','_chain_audit','_cancel_growth','_scope_for','_execute_entry','_reconcile_btc','_protection_ready','_reconcile_protection'):
        setattr(s,name,MethodType(getattr(CM2Strategy,name),s))
    canceled=[];s.cancel_order=canceled.append
    return N(s=s,btc=btc,sol=sol,cache=cache,position=pos,aid=aid,sent=sent,canceled=canceled,tick=tick,stub=TestEventStubs,opening=fill)


def test_real_native_gtc_and_mark_stop_compose_same_cache_without_double_reserving_ro():
    c=native_shell();s=c.s
    from nautilus_trader.model.enums import TriggerType
    for level,q in enumerate((D('.15'),D('.20'),D('.15'))):
        assert s._send(c.btc.id,q,-1,'TP_GTC',30*DAY,c.tick,reduce_only=True,level=level,raw_limit=D(102+level))
    assert sum(o.leaves_qty.as_decimal() for o in c.cache.orders_open())==D('.5')
    assert s._send(c.btc.id,D('.5'),-1,'BE_STOP',30*DAY,c.tick,reduce_only=True,stop_trigger=D('100.08'))
    assert c.sent[-1].trigger_type==TriggerType.MARK_PRICE and c.sent[-1].is_reduce_only
    assert c.sent[-1].quantity.as_decimal()==D('.5')
    assert all(not o.is_post_only for o in c.sent if o.order_type.name=='LIMIT')
    assert not s._send(c.btc.id,D('.11'),-1,'TP_GTC',30*DAY,c.tick,reduce_only=True,level=0,raw_limit=D(104))
    assert s._order_audit[str(c.sent[-1].client_order_id)]['request_model_id']==MODEL_ID


def test_actual_native_optional_position_index_is_not_manufactured_and_wrong_side_rejected():
    c=native_shell();s=c.s
    assert s._send(c.btc.id,D('.11'),-1,'TP_GTC',30*DAY,c.tick,reduce_only=True,level=0,raw_limit=D(102))
    o=c.sent[-1]
    assert c.cache.position_id(o.client_order_id) is None
    event=c.stub.order_filled(o,c.btc,account_id=c.aid,position_id=c.position.id,last_qty=c.btc.make_qty('.11'),last_px=c.btc.make_price(102),ts_event=30*DAY)
    assert s._fill_owner(event,s._order_audit[str(o.client_order_id)]) is o
    from nautilus_trader.model.enums import OrderSide
    wrong=c.stub.order_filled(o,c.btc,account_id=c.aid,position_id=c.position.id,side=OrderSide.BUY,last_qty=c.btc.make_qty('.11'),last_px=c.btc.make_price(102),ts_event=30*DAY)
    with pytest.raises(ValueError,match='IDENTITY_OR_SIDE'):s._fill_owner(wrong,s._order_audit[str(o.client_order_id)])
    from nautilus_trader.model.identifiers import PositionId
    s.cache.position_id=lambda oid:PositionId('WRONG')
    with pytest.raises(ValueError,match='CONTRADICTORY'):s._fill_owner(event,s._order_audit[str(o.client_order_id)])


def test_fixed_tp_partial_open_is_protected_immediately_and_be_after_first_fill():
    c=native_shell();s=c.s;s.btc.parent.be_armed=True;s.btc.parent.growth_stopped=True
    s._sync_protection(30*DAY)
    tps=[o for o in c.sent if o.order_type.name=='LIMIT'];stops=[o for o in c.sent if o.order_type.name=='STOP_MARKET']
    assert [o.quantity.as_decimal() for o in tps]==[D('.15'),D('.2'),D('.15')]
    assert stops and stops[0].quantity.as_decimal()==D('.5')
    before=len(c.sent);s._sync_protection(30*DAY);assert len(c.sent)==before


@pytest.mark.parametrize('bad',['currency','funding','journal'])
def test_native_cost_knownness_is_not_zero_filled(bad):
    c=native_shell();s=c.s
    if bad=='currency':
        from nautilus_trader.model.objects import Currency
        s.cache.account_for_venue=lambda v:N(base_currency=Currency.from_str('USD'))
    if bad=='funding':
        reader=lambda i:D('NaN');reader.journal=N();s.config.funding_reader=reader
    if bad=='journal':s.config.funding_reader=lambda i:D(0)
    with pytest.raises(ValueError):s._funding()


def test_strict_new_model_and_unchanged_financial_qualifier():
    from coinmaster.research import cm2_runner as r
    assert r.market_config({'version':'cm2-btc-market-v1','emergency_drawdown_fraction':None})==BtcConfig()
    with pytest.raises(ValueError):r.market_config({'version':'cm2-btc-reference-v1','candidate':{},'flags':{},'emergency_drawdown_fraction':None})
    with pytest.raises(ValueError):r.market_config({'version':'cm2-btc-market-v1','emergency_drawdown_fraction':None,'sol':{'enabled':True}})
    assert hashlib.sha256((Path(r.__file__).with_name('cm2_committed_validation.py')).read_bytes()).hexdigest()=='a7d1c597d9f0bb80f1c69bf147f0b34a665f930f461a2dc001b8e3e3714ee775'
    with pytest.raises(ValueError,match='NO_ECONOMIC_API_PROBE'):r.full_api_boundary_probe({'source_family':'CM2BTCMARKET'},'unused')


def test_shared_build_leaf_reaches_real_config_and_never_strategy_constructor(monkeypatch):
    from coinmaster.research import cm2_runner as r
    import coinmaster.strategy.cm2_native as n
    from coinmaster.venues.marks import venue_mark_data_type
    from coinmaster.venues.signals import daily_signal_data_type
    from coinmaster.strategy.next_band import next_bar_type
    from nautilus_trader.model.data import BarType
    from nautilus_trader.model.identifiers import ClientId
    c=native_shell();journal=N(db=sqlite3.connect(':memory:'))
    class Spy:
        def __init__(self,config):self.config=config
    monkeypatch.setattr(n,'CM2Strategy',Spy)
    instruments=(c.btc,c.sol)
    obj=r.build_strategy(r.CM2RunConfig(BtcConfig()),instruments=instruments,
        minute_bars={i.id:BarType.from_str(str(i.id)+'-1-MINUTE-LAST-EXTERNAL') for i in instruments},
        margin_policy=c.s.config.margin_policy,start_ns=30*DAY,end_ns=100*DAY,
        mark_types=tuple(venue_mark_data_type(i.id) for i in instruments),mark_client=ClientId('MARK'),
        journal=journal,exit_fee_rate=D('.000432'),execution_hash='synthetic-only',seed_btc_days=tuple(policy().days),
        daily_types=tuple(daily_signal_data_type(i.id) for i in instruments),h4_type=next_bar_type(c.btc.id,4),
        signal_client=ClientId('SIGNAL'),initial_seed=D(10000))
    assert isinstance(obj.config,n.CM2StrategyConfig) and obj.config.policy==BtcConfig()
    assert obj.config.seed_btc_days==tuple(policy().days)
    assert not hasattr(obj.config,'sol_policy') and not hasattr(obj.config,'seed_paired_closes')
    journal.db.close()


def test_completed_first_half_posts_real_discount_gtc_once():
    c=native_shell();s=c.s
    s._sync_protection(30*DAY)
    s._execute_entry(c.tick,30*DAY)
    entries=lambda:[o for o in c.sent if not o.is_reduce_only]
    assert len(entries())==1
    order=entries()[0]
    assert order.order_type.name=='LIMIT' and order.time_in_force.name=='GTC' and not order.is_post_only
    assert order.quantity.as_decimal()==D('.5') and order.price.as_decimal()==D('99.5')
    s._execute_entry(c.tick,30*DAY)
    assert len(entries())==1 # actual live owner, no duplicate growth
    s.btc.parent.growth_stopped=True
    s._execute_entry(c.tick,30*DAY)
    assert len(entries())==1


@pytest.mark.parametrize('purpose,raw,cap',[('ENTRY_MARKET',None,D(30000000)),('ENTRY_DISCOUNT',D(99),D(300000000))])
def test_each_real_request_honors_its_own_venue_cap(purpose,raw,cap):
    c=native_shell();s=c.s
    assert s._send(c.btc.id,D('1e8'),1,purpose,30*DAY,c.tick,raw_limit=raw)
    o=c.sent[-1]
    assert o.quantity.as_decimal()*max(D('100.1'),raw or D('100.1'))<=cap
    assert o.quantity.as_decimal()>0


def test_actual_both_asset_working_sets_keep_btc_ro_authority():
    c=native_shell();s=c.s
    from nautilus_trader.model.enums import OrderSide,OmsType,TimeInForce
    from nautilus_trader.model.position import Position
    from nautilus_trader.model.identifiers import PositionId
    from nautilus_trader.model.objects import Money
    seed=s.order_factory.market(c.sol.id,OrderSide.SELL,c.sol.make_qty(2))
    seed.apply(c.stub.order_accepted(seed,account_id=c.aid,ts_event=30*DAY))
    fill=c.stub.order_filled(seed,c.sol,account_id=c.aid,position_id=PositionId('SOL-CARRIED'),last_px=c.sol.make_price(50),commission=Money(0,c.sol.quote_currency),ts_event=30*DAY)
    seed.apply(fill);c.cache.add_order(seed);position=Position(c.sol,fill);c.cache.add_position(position,OmsType.NETTING)
    ro=s.order_factory.limit(c.sol.id,OrderSide.BUY,c.sol.make_qty(2),c.sol.make_price(45),time_in_force=TimeInForce.GTC,reduce_only=True)
    c.cache.add_order(ro)
    ro.apply(c.stub.order_accepted(ro,account_id=c.aid,ts_event=30*DAY));c.cache.update_order(ro)
    s._owned[str(ro.client_order_id)]={'client_order_id':ro.client_order_id,'instrument_id':c.sol.id,'purpose':'RETAINED_SOL_RO','level':None}
    s._snapshot=lambda now:NativeExposure(D('1e9'),c.position.quantity.as_decimal(),-position.quantity.as_decimal(),D(100),D(50),False,True,{c.btc.id:True,c.sol.id:True})
    assert s._send(c.btc.id,D('.5'),-1,'BE_STOP',30*DAY,c.tick,reduce_only=True,stop_trigger=D('100.08'))
    assert c.cache.orders_open(instrument_id=c.sol.id)==[ro]
    assert position.quantity.as_decimal()==D(2)


def test_btc_fill_callback_uses_real_order_position_and_preserves_partial_tp_leaves():
    c=native_shell();s=c.s
    from nautilus_trader.model.objects import Money
    s._sync_protection(30*DAY)
    order=next(o for o in c.sent if s._owned[str(o.client_order_id)]['level']==0)
    event=c.stub.order_filled(order,c.btc,account_id=c.aid,position_id=c.position.id,
        last_qty=c.btc.make_qty('.01'),last_px=order.price,commission=Money('.00043762',c.btc.quote_currency),ts_event=30*DAY)
    order.apply(event);c.position.apply(event);c.cache.update_order(order);c.cache.update_position(c.position)
    s._terminal_event=MethodType(CM2Strategy._terminal_event,s);s._reconcile_drains=lambda now:None
    CM2Strategy.on_order_filled(s,event)
    assert s.btc.parent.be_armed and s.btc.parent.growth_stopped
    assert s.btc.parent.tp_filled_lots[0]==1000
    assert order.leaves_qty.as_decimal()==D('.14')
    assert any(o.order_type.name=='STOP_MARKET' and o.quantity.as_decimal()==D('.49') for o in c.sent)
    before=(len(c.sent),len(s.fill_audit),s.btc.parent.remaining_cost)
    CM2Strategy.on_order_filled(s,event)
    assert (len(c.sent),len(s.fill_audit),s.btc.parent.remaining_cost)==before


def test_seed_is_not_live_signal_and_multiday_tpflat_requires_next_new_d1():
    p=policy();p.complete_seed()
    assert not p.entry_signal(30*DAY)
    p.accept_day(BtcDay(30*DAY,31*DAY,31*DAY,110,113,109,112),receipt_ns=31*DAY)
    c=p.open_cycle(side=1,equity=D(1000),executable=D(100),now=31*DAY,funding_total=D(0))
    c.entry_filled=D(1)
    p.accept_day(BtcDay(31*DAY,32*DAY,32*DAY,112,115,111,114),receipt_ns=32*DAY)
    p.confirm_flat(now=32*DAY+HOUR,native_flat=True,owners_terminal=True)
    assert not p.entry_signal(32*DAY+HOUR+1)
    q=policy();q.restore(decode(json.loads(canonical(p.snapshot()))))
    assert not q.entry_signal(32*DAY+2*HOUR)
    q.accept_day(BtcDay(32*DAY,33*DAY,33*DAY,114,117,113,116),receipt_ns=33*DAY)
    assert q.entry_signal(33*DAY)


def test_failed_required_tp_stops_growth_and_blocker_does_not_poison_later_cycle():
    c=native_shell();s=c.s;s._protection_dirty=False
    s._terminal_event=MethodType(CM2Strategy._terminal_event,s);s._reconcile_drains=lambda now:None
    s._sync_protection(30*DAY)
    assert s._protection_ready(30*DAY)
    tp=c.sent[0];p=s.btc.parent;cycle_id=p.id
    event=c.stub.order_canceled(tp,account_id=c.aid,ts_event=30*DAY)
    tp.apply(event);c.cache.update_order(tp)
    s._terminal_event(event,failed=True)
    assert p.growth_stopped and not s._protection_ready(30*DAY)
    assert 'NATIVE_PROTECTION_TERMINAL:'+cycle_id+':TP_GTC:0' in s.target_blockers
    later=native_shell();later.s.btc.parent.id='later-cycle'
    later.s.target_blockers.update(s.target_blockers)
    later.s._sync_protection(30*DAY)
    assert len(later.sent)==3
    assert not any('later-cycle' in k for k in later.s.target_blockers if k.startswith('NATIVE_PROTECTION_TERMINAL:'))


def test_synchronous_actual_tp1_fill_reconciles_be_in_same_call_chain():
    c=native_shell();s=c.s;s._protection_dirty=False
    from nautilus_trader.model.objects import Money
    s._terminal_event=MethodType(CM2Strategy._terminal_event,s);s._reconcile_drains=lambda now:None
    original=s.submit_order;seen=[]
    def submit(order):
        original(order)
        info=s._owned[str(order.client_order_id)]
        if info['purpose']=='TP_GTC' and info['level']==0 and not seen:
            seen.append(str(order.client_order_id))
            event=c.stub.order_filled(order,c.btc,account_id=c.aid,position_id=c.position.id,
                last_qty=c.btc.make_qty('.01'),last_px=order.price,commission=Money('.00043762',c.btc.quote_currency),ts_event=30*DAY)
            order.apply(event);c.position.apply(event);c.cache.update_order(order);c.cache.update_position(c.position)
            CM2Strategy.on_order_filled(s,event)
    s.submit_order=submit
    s._sync_protection(30*DAY)
    assert s.btc.parent.be_armed and s.btc.parent.growth_stopped
    assert any(o.order_type.name=='STOP_MARKET' and o.quantity.as_decimal()==D('.49') for o in c.sent)
    tp1=sum(o.leaves_qty.as_decimal() for o in c.cache.orders_open() if s._owned[str(o.client_order_id)]['purpose']=='TP_GTC' and s._owned[str(o.client_order_id)]['level']==0)
    assert tp1==D('.14') # dirty callback must not submit stale extra TP1 leaves
    assert not s._protection_dispatching and not s._protection_dirty


def test_growth_waits_for_actual_accepted_complete_protection():
    c=native_shell();s=c.s;s._protection_dirty=False
    s._execute_entry(c.tick,30*DAY)
    assert not c.sent
    s._sync_protection(30*DAY)
    assert s._protection_ready(30*DAY)
    s._execute_entry(c.tick,30*DAY)
    assert any(not o.is_reduce_only for o in c.sent)


def test_shared_actual_drain_rejects_predecision_quote_and_keeps_real_order_owner():
    c=native_shell();s=c.s
    for name in ('_execute_drain','_begin_drain','_on_drain_deadline','_reconcile_drains'):
        setattr(s,name,MethodType(getattr(CM2Strategy,name),s))
    s._begin_drain(30*DAY,'BTC_ECONOMIC',[str(c.btc.id)],'REGIME')
    old=N(**vars(c.tick));old.ts_event-=1
    s._execute_drain(old,30*DAY,'BTC_ECONOMIC');assert not c.sent
    s._execute_drain(c.tick,30*DAY,'BTC_ECONOMIC')
    assert len(c.sent)==1 and c.sent[0].is_reduce_only
    assert c.position.quantity.as_decimal()==D('.5') # accepted order is not a fill/flat
    s._execute_drain(c.tick,30*DAY,'BTC_ECONOMIC');assert len(c.sent)==1
    assert s._drain['BTC_ECONOMIC']['state']['first_ns']==30*DAY


def test_actual_native_clock_deadline_does_not_reset_or_fabricate_flat():
    c=native_shell();s=c.s
    for name in ('_begin_drain','_on_drain_deadline'):
        setattr(s,name,MethodType(getattr(CM2Strategy,name),s))
    s._begin_drain(30*DAY,'BTC_ECONOMIC',[str(c.btc.id)],'REGIME')
    first=dict(s._drain['BTC_ECONOMIC']['state'])
    s._begin_drain(30*DAY+1,'BTC_ECONOMIC',[str(c.btc.id)],'REGIME')
    assert s._drain['BTC_ECONOMIC']['state']==first
    for event in s.clock.advance_time(first['deadline_ns']):event.handle()
    assert s._drain['BTC_ECONOMIC']['state']['reconcile_required']
    assert s._drain['BTC_ECONOMIC']['state']['deadline_ns']==first['deadline_ns']
    assert c.position.quantity.as_decimal()==D('.5') and not c.sent


def test_btc_daily_loader_does_not_require_sol_daily_file(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from coinmaster.research.native_baseline import _load_btc_daily_seed
    day_ms=86400000;folder=tmp_path/'normalized';folder.mkdir()
    rows=[dict(open_time_ms=i*day_ms,open=str(100+i),high=str(102+i),low=str(98+i),close=str(101+i)) for i in range(31)]
    pq.write_table(pa.Table.from_pylist(rows),folder/'bybit-BTCUSDT-daily.parquet')
    seed,tables=_load_btc_daily_seed(tmp_path,0,30*day_ms,31*day_ms)
    assert len(seed)==30 and set(tables)=={'BTCUSDT'}
    assert seed[-1].close_ns==30*DAY and not (folder/'bybit-SOLUSDT-daily.parquet').exists()
