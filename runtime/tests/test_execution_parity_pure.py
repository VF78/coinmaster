"""Actual controller AST and native objects; engine constructions zero."""
import ast
import pytest
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N
from coinmaster.research.minute_risk import DrawdownTracker
from coinmaster.research.native_full_fill import ZeroImpactFullFillDiagnostic
from coinmaster.research.native_fixture import SOL_PERP
from nautilus_trader.model.enums import LiquiditySide, OrderSide


def actual():
    source=Path(__file__).parents[1]/"coinmaster/strategy/wave_overlay.py"
    cls=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.ClassDef) and n.name=="WaveOverlayStrategy")
    names={"_submit_forced_close_on_quote","_submit_forced_closes_from_cache"}
    body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
    env=dict(QuoteTick=object,OrderSide=N(SELL="SELL",BUY="BUY"),TimeInForce=N(IOC="IOC"))
    module=ast.Module(body=[ast.ClassDef(name="Actual",bases=[],keywords=[],body=body,decorator_list=[])],type_ignores=[])
    exec(compile(ast.fix_missing_locations(module),str(source),"exec"),env)
    s=env["Actual"]();s.config=N(deposit_runtime=None,btc_id="BTC",sol_id="SOL",research_v3_risk=None)
    s._forced_close_reason="REGIME";s._forced_close_decision_ns=100;s._forced_close_cancel_ack_ns=101
    s._forced_close_intent=None;s._forced_close_submitted=set();s._forced_close_orders=set()
    s._pending_by_order={};s._carry_busy=lambda:False
    pos=N(instrument_id="BTC",is_long=True,quantity=N(as_decimal=lambda:D("2")))
    quotes={};opened=[];sent=[];s._order_audit={}
    s.cache=N(orders_open=lambda:opened,positions_open=lambda:[pos],orders_inflight=lambda:[],
        instrument=lambda _:N(make_qty=lambda q:q),quote_tick=lambda i:quotes.get(i))
    s.order_factory=N(market=lambda **kw:N(client_order_id="close",quantity=kw["quantity"]))
    def record(o,*a):s._order_audit[str(o.client_order_id)]={};return True
    s._record_submission=record;s.submit_order=sent.append
    return s,quotes,opened,sent


def tick(i,t):return N(instrument_id=i,ts_event=t,bid_price="99",ask_price="101")


def test_actual_cancel_ack_requires_causally_fresh_instrument_quote():
    s,quotes,opened,sent=actual();quotes["BTC"]=tick("BTC",99)
    s._submit_forced_closes_from_cache();assert not sent
    s._submit_forced_close_on_quote(tick("SOL",100));assert not sent
    opened.append(object());quotes["BTC"]=tick("BTC",100)
    s._submit_forced_closes_from_cache();assert not sent
    opened.clear();s._submit_forced_closes_from_cache();assert len(sent)==1
    row=s._order_audit["close"]
    assert (row["decision_ns"],row["quote_ns"],row["cancel_ack_ns"])==("100","100","101")
    s._submit_forced_closes_from_cache()
    assert len(sent)==1


def test_same_ns_drawdown_keeps_original_sequence_math_and_actual_clock():
    old=DrawdownTracker(100);new=DrawdownTracker(100)
    for seq,val in enumerate((100,200,80,210),1):
        old.add(seq,val);new.add(seq,val,sequence_id=seq,timestamp_ns=1000)
    a=old.summary();b=new.summary()
    assert a["maximum_loss_below_seed_percent"]==b["maximum_loss_below_seed_percent"]
    x=a["top3_distinct_excursions"][0];y=b["top3_distinct_excursions"][0]
    assert x["drawdown_peak_percent"]==y["drawdown_peak_percent"]=="60.0"
    assert y["peak"]["sequence_id"]=="2" and y["trough"]["sequence_id"]=="3"
    assert y["peak"]["timestamp_ns"]==y["trough"]["timestamp_ns"]=="1000"


def test_native_fill_api_order_sized_capacity_and_strict_maker_touch():
    model=ZeroImpactFullFillDiagnostic()
    assert not model.fill_limit_inside_spread() and not model.is_limit_filled()
    order=N(side=OrderSide.BUY,liquidity_side=LiquiditySide.TAKER,leaves_qty=SOL_PERP.make_qty(D("1234567.8")))
    bid=SOL_PERP.make_price(D(99));ask=SOL_PERP.make_price(D(101))
    book=model.get_orderbook_for_fill_simulation(SOL_PERP,order,bid,ask)
    assert book.best_ask_size()==order.leaves_qty and book.best_ask_price()==ask
    order.leaves_qty=SOL_PERP.make_qty(D("1001.2"))
    assert model.get_orderbook_for_fill_simulation(SOL_PERP,order,bid,ask).best_ask_size()==order.leaves_qty
    order.liquidity_side=LiquiditySide.MAKER;order.price=ask
    assert model.get_orderbook_for_fill_simulation(SOL_PERP,order,bid,ask).best_ask_price() is None
    order.price=SOL_PERP.make_price(D(102))
    assert model.get_orderbook_for_fill_simulation(SOL_PERP,order,bid,ask).best_ask_price()==order.price


def test_old_checkpoint_decodes_without_inventing_forced_decision_clock():
    from coinmaster.strategy.live_recovery import checkpoint_structure, _FIELDS, _SCHEMA
    old={name:None for name in _FIELDS if name not in {"_forced_close_decision_ns","_forced_close_cancel_ack_ns"}}
    doc=dict(schema=_SCHEMA,candidate_sha256="x",strategy_id="x",domain=dict(episode=None,locked_after_liquidation=False,decision_index=0),state=old)
    assert checkpoint_structure(doc) is False
    assert doc["state"]["_forced_close_decision_ns"] is None
    s,quotes,opened,sent=actual();s._forced_close_decision_ns=None
    quotes["BTC"]=tick("BTC",1000);s._submit_forced_closes_from_cache()
    assert not sent


def test_current_hl_native_usdc_profile_uses_effective_fees_tiers_and_shared_wire_rounding():
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    from coinmaster.venues.effective_fees import CURRENT_HL_FEES,HL_FEE_RESERVE_BUFFER
    from coinmaster.strategy.wave_overlay import _native_limit_price,_fee_floor_price
    from coinmaster.venues.marks import VenueMark
    profile=load_current_hl_diagnostic(Path(__file__).parent/"fixtures/hl-current-20261029")
    btc,sol=profile.instruments
    assert [(str(i.quote_currency),str(i.settlement_currency),i.size_precision) for i in profile.instruments]==[("USDC","USDC",5),("USDC","USDC",2)]
    assert all(i.maker_fee==CURRENT_HL_FEES.maker and i.taker_fee==CURRENT_HL_FEES.taker and i.min_notional.as_decimal()==10 for i in profile.instruments)
    assert CURRENT_HL_FEES.reserve_taker(HL_FEE_RESERVE_BUFFER)==D(".0005")
    assert CURRENT_HL_FEES.reserve_taker(0)==D(".000432")
    policy=profile.margin_policy(100)
    policy.update_mark(N(instrument_id=btc.id,price=D(100000),ts_event=100))
    initial,maintenance,mark=policy.margin_for(btc.id,D(1),100)
    assert initial==D(2500) and maintenance==D(1250)
    price=_native_limit_price(sol,D("183.8199"))
    assert price.as_decimal()==D("183.82")
    episode=N(btc_entry_qty_exact=D(1),btc_entry_notional_exact=D(100000),btc_entry_fees_exact=D("43.2"),
              btc_entry_fee_fill_count=1,btc_entry_fill_count=1,side=1)
    floor=_fee_floor_price(btc,episode,maker=False).as_decimal()
    assert floor>=D(100000)*(1+CURRENT_HL_FEES.taker)/(1-CURRENT_HL_FEES.taker)


def test_actual_native_margin_module_process_uses_injected_policy_configured_ids_and_currency():
    source=Path(__file__).parents[1]/"coinmaster/research/native_fixture.py"
    cls=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.ClassDef) and n.name=="BybitTierMarginModule")
    process=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=="process")
    def forbidden(*a,**kw):raise AssertionError("legacy policy constructed under HL injection")
    env=dict(Decimal=D,Money=lambda value,currency:(value,currency),TierMarginPolicy=forbidden)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[process],type_ignores=[])),str(source),"exec"),env)
    positions=[N(instrument_id=i,quantity=N(as_decimal=lambda:D(2))) for i in ("BTC.HL","SOL.HL")]
    calls=[];cleared=[];updated=[]
    account=N(clear_margin_init=lambda i:cleared.append(("IM",i)),clear_margin_maint=lambda i:cleared.append(("MM",i)),
        update_margin_init=lambda i,m:updated.append((i,m)),update_margin_maint=lambda i,m:updated.append((i,m)))
    policy=N(margin_for=lambda i,q,t:(calls.append((i,q,t)) or (D(5),D(2),D(100))))
    obj=N(exchange=N(get_account=lambda:account,cache=N(positions_open=lambda:positions)),
        _selected_leverage={"BTC.HL":D(40),"SOL.HL":D(20)},_injected_policy=policy,_settlement_currency="USDC",observed=[])
    env["process"](obj,100)
    assert [x[0] for x in calls]==["BTC.HL","SOL.HL"]
    assert all(m[1]=="USDC" for _,m in updated)
    positions.clear();env["process"](obj,101)
    assert set(cleared)=={("IM","BTC.HL"),("MM","BTC.HL"),("IM","SOL.HL"),("MM","SOL.HL")}


def test_native_plus_minus_upnl_and_live_share_economic_core_with_additional_live_gate(monkeypatch):
    from coinmaster.ops import hl_live_money as module
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    from nautilus_trader.model.currencies import USDC
    from nautilus_trader.model.objects import Money
    profile=load_current_hl_diagnostic(Path(__file__).parent/"fixtures/hl-current-20261029")
    btc,sol=profile.instruments
    marks={btc.id:N(instrument_id=btc.id,price=D(100000),ts_event=100),sol.id:N(instrument_id=sol.id,price=D(100),ts_event=100)}
    policy=profile.margin_policy(100)
    for mark in marks.values():policy.update_mark(mark)
    original=module.prospective_cross_margin_core;seen=[]
    def observe(**kw):
        result=original(**kw);seen.append((kw,result));return result
    monkeypatch.setattr(module,"prospective_cross_margin_core",observe)
    for pnl,expected in ((D(-1000),False),(D(1000),True)):
        pos=N(instrument_id=sol.id,is_long=True,quantity=sol.make_qty(D(10)),
              unrealized_pnl=lambda price:Money(pnl,USDC))
        pending=N(client_order_id="pending",is_closed=False,instrument_id=sol.id,is_reduce_only=False,quantity=sol.make_qty(D(2)),filled_qty=sol.make_qty(D(0)),side=OrderSide.SELL)
        strategy=N(config=N(btc_id=btc.id,sol_id=sol.id,max_mark_age_ns=100,margin_policy=policy,
            native_hl_selected_leverage=profile.selected_leverage,max_gross_to_active=D(50)),
            _latest_marks=marks,pre_submit_gate_blocks=[],
            cache=N(account_for_venue=lambda v:N(balance_total=lambda c:Money(10000,USDC)),
                positions_open=lambda:[pos],orders_open=lambda:[pending],orders_inflight=lambda:[pending],instrument=lambda i:btc if i==btc.id else sol))
        assert module.native_usdc_margin_core(strategy,sol.id,OrderSide.BUY,D(1800),100)==expected
        native_input,native_result=seen[-1]
        live_result=original(**native_input)
        assert live_result["allowed"]==native_result["allowed"]==expected
        assert native_input["equity"]==D(10000)+pnl and native_input["free_collateral"]==D(9950)+pnl
        # Explicit fixture venue availability may deny even a passing economic core.
        assets=tuple(module.SelectedCrossAsset(a.coin,a.leverage,a.mark,(D(0),D(0)),(D(0),D(0))) for a in native_input["selected_assets"])
        view=N(equity=native_input["equity"],free_collateral=native_input["free_collateral"],
               selected_assets=assets,account_mode="unifiedAccount")
        assert not module.prospective_cross_margin_ok(view,positions={"SOL":D(10)},pending_openings=(("SOL","SELL",D(2)),),
            coin="SOL",side="BUY",quantity=D(1800),max_gross_multiple=D(50))


@pytest.mark.parametrize("coin,quantity,allowed",[
    ("BTC","1499.99999",True),("BTC","1500",False),
    ("SOL","699999.99",True),("SOL","700000",False),
])
def test_current_hl_exact_prospective_tier_boundaries_and_opposite_side_netting(coin,quantity,allowed):
    from coinmaster.ops.hl_live_money import native_usdc_margin_core
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    from nautilus_trader.model.currencies import USDC
    from nautilus_trader.model.objects import Money
    profile=load_current_hl_diagnostic(Path(__file__).parent/"fixtures/hl-current-20261029")
    btc,sol=profile.instruments
    marks={btc.id:N(instrument_id=btc.id,price=D(100000),ts_event=100),sol.id:N(instrument_id=sol.id,price=D(100),ts_event=100)}
    policy=profile.margin_policy(100)
    for mark in marks.values():policy.update_mark(mark)
    held=[];pending=[]
    strategy=N(config=N(btc_id=btc.id,sol_id=sol.id,max_mark_age_ns=100,margin_policy=policy,
        native_hl_selected_leverage=profile.selected_leverage,max_gross_to_active=D(50)),
        _latest_marks=marks,pre_submit_gate_blocks=[],
        cache=N(account_for_venue=lambda v:N(balance_total=lambda c:Money(1000000000,USDC)),
            positions_open=lambda:held,orders_open=lambda:pending,orders_inflight=lambda:[],
            instrument=lambda i:btc if i==btc.id else sol))
    instrument=btc if coin=="BTC" else sol
    assert native_usdc_margin_core(strategy,instrument.id,OrderSide.BUY,D(quantity),100)==allowed
    if not allowed:assert "PROSPECTIVE_TIER_DENIED" in strategy.pre_submit_gate_blocks[-1]["reason"]
    # A pending opposite SELL cannot erase worst-side BUY exposure. A net-only
    # sum would show 500 BTC; the current worst side is 1500 BTC and is denied.
    held.append(N(instrument_id=btc.id,is_long=True,quantity=btc.make_qty(D(1000)),unrealized_pnl=lambda p:Money(0,USDC)))
    pending.append(N(client_order_id="opposite",is_closed=False,is_reduce_only=False,instrument_id=btc.id,
        quantity=btc.make_qty(D(1000)),filled_qty=btc.make_qty(D(0)),side=OrderSide.SELL))
    assert not native_usdc_margin_core(strategy,btc.id,OrderSide.BUY,D(500),100)
    assert "PROSPECTIVE_TIER_DENIED" in strategy.pre_submit_gate_blocks[-1]["reason"]
    assert native_usdc_margin_core(strategy,btc.id,OrderSide.SELL,D(500),100)


@pytest.mark.parametrize("coin",["BTC","SOL"])
def test_actual_baseline_quote_builder_uses_instrument_precision_and_native_codec(coin):
    import json
    from coinmaster.research.native_fixture import instrument_quote,quote
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    from nautilus_trader.model.data import QuoteTick
    profile=load_current_hl_diagnostic(Path(__file__).parent/"fixtures/hl-current-20261029")
    instrument=next(i for i in profile.instruments if i.base_currency.code==coin)
    # Reproduce attempt1 lexical mismatch, then exercise actual baseline producer.
    direct=instrument_quote(instrument,"99.99","100",100)
    assert direct.bid_price.precision==direct.ask_price.precision==instrument.price_precision
    assert direct.bid_size.precision==direct.ask_size.precision==instrument.size_precision
    source=Path(__file__).parents[1]/"coinmaster/research/native_baseline.py"
    method=next(n for n in ast.walk(ast.parse(source.read_text())) if isinstance(n,ast.FunctionDef) and n.name=="native_quote")
    env=dict(Decimal=D,current_hl=profile,spread=D(0),quote=quote,instrument_quote=instrument_quote)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[method],type_ignores=[])),str(source),"exec"),env)
    actual=env["native_quote"](instrument,"100",2,100)
    decoded=QuoteTick.from_dict(json.loads(json.dumps(QuoteTick.to_dict(actual))))
    assert decoded==actual
    assert decoded.bid_price.precision==decoded.ask_price.precision==instrument.price_precision
    assert decoded.bid_size.precision==decoded.ask_size.precision==instrument.size_precision
