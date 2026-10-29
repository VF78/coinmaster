"""Actual controller AST and native objects; engine constructions zero."""
import ast
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
