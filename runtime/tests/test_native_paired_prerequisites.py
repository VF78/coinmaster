"""Native 1.231 launch gates, never economic prefix replay.

Deliberately use the stock engine and Strategy; no replacement fill/account model.
The source contract requires quote-wide aggregate capacity including TP siblings.
"""
from decimal import Decimal as D
import json

from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.models import MakerTakerFeeModel
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide, TimeInForce
from nautilus_trader.model.objects import Money
from nautilus_trader.trading.strategy import Strategy

from coinmaster.research.native_fixture import SIM, SOL_PERP
from test_native_episode_risk import tick, run_ticks


class NativeCapabilityProbe(Strategy):
    def __init__(self):
        super().__init__()
        self.receipts = []

    def on_order_event(self, event):
        self.receipts.append(dict(kind=type(event).__name__, order_id=str(event.client_order_id),
                                 ts=str(event.ts_event)))

    def on_order_filled(self, event):
        self.receipts.append(dict(kind="FILL", order_id=str(event.client_order_id),
            ts=str(event.ts_event), qty=str(event.last_qty), px=str(event.last_px),
            fee=str(event.commission), liquidity=event.liquidity_side.name))


def engine_probe():
    strategy = NativeCapabilityProbe()
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
        starting_balances=[Money(1000000, SOL_PERP.quote_currency)],
        base_currency=SOL_PERP.quote_currency, default_leverage=D(1),
        fee_model=MakerTakerFeeModel(), liquidity_consumption=True, bar_execution=False)
    engine.add_instrument(SOL_PERP)
    engine.add_strategy(strategy)
    run_ticks(engine, [tick(SOL_PERP, 1, "100", "1000")])
    return engine, strategy


def send(strategy, side, quantity, *, price=None, stop=None, reduce=False):
    kw = dict(instrument_id=SOL_PERP.id, order_side=side,
              quantity=SOL_PERP.make_qty(D(quantity)), reduce_only=reduce)
    if stop is not None:
        order = strategy.order_factory.stop_market(**kw,
            trigger_price=SOL_PERP.make_price(D(stop)), time_in_force=TimeInForce.IOC)
    elif price is None:
        order = strategy.order_factory.market(**kw, time_in_force=TimeInForce.IOC)
    else:
        order = strategy.order_factory.limit(**kw, price=SOL_PERP.make_price(D(price)),
                                             time_in_force=TimeInForce.GTC)
    strategy.submit_order(order)
    return order


def filled(order):
    return order.filled_qty.as_decimal()


def test_native_one_quote_ioc_aggregate_and_real_fresh_size_replenishment():
    e, s = engine_probe()
    try:
        a = send(s, OrderSide.BUY, "700")
        b = send(s, OrderSide.BUY, "700")
        run_ticks(e, [tick(SOL_PERP, 2, "100", "1000")])
        assert filled(a) + filled(b) == D(1000)
        assert {filled(a), filled(b)} == {D(700), D(300)}
        c = send(s, OrderSide.BUY, "100")
        run_ticks(e, [tick(SOL_PERP, 3, "100", "1000")])
        assert filled(c) == 0  # New timestamp alone is not a stock refill.
        d = send(s, OrderSide.BUY, "100")
        run_ticks(e, [tick(SOL_PERP, 4, "100", "1001")])
        assert filled(d) == D(100)  # Queued command observes next fresh update.
        f = send(s, OrderSide.BUY, "100")
        run_ticks(e, [tick(SOL_PERP, 5, "100", "1001")])
        assert filled(f) == D(100)
        json.loads(json.dumps(s.receipts))
    finally:
        e.end(); e.dispose()


def test_native_l1_real_tp_siblings_share_single_quote_capacity():
    e, s = engine_probe()
    try:
        entry = send(s, OrderSide.BUY, "1000")
        run_ticks(e, [tick(SOL_PERP, 2, "100", "1000")])
        assert filled(entry) == D(1000)
        targets = [send(s, OrderSide.SELL, q, price=p, reduce=True)
                   for q, p in (("250", "101"), ("250", "102"), ("500", "104"))]
        run_ticks(e, [tick(SOL_PERP, 3, "100", "1000")])
        assert all(o.status.name == "ACCEPTED" for o in targets)
        run_ticks(e, [tick(SOL_PERP, 4, "105", "300")])
        total = sum((filled(o) for o in targets), D(0))
        assert total <= D(300), f"STOCK_L1_TP_CAPACITY_BREACH:{total}>300;{s.receipts}"
        run_ticks(e, [tick(SOL_PERP, 5, "105", "300")])
        assert sum((filled(o) for o in targets), D(0)) <= D(300), json.dumps(s.receipts)
        run_ticks(e, [tick(SOL_PERP, 6, "105", "301")])
        assert sum((filled(o) for o in targets), D(0)) <= D(601), json.dumps(s.receipts)
    finally:
        e.end(); e.dispose()


def test_native_reduce_only_protective_stop_partial_and_cancel_ack():
    e, s = engine_probe()
    try:
        entry = send(s, OrderSide.BUY, "1000")
        run_ticks(e, [tick(SOL_PERP, 2, "100", "1000")])
        assert filled(entry) == D(1000)
        stop = send(s, OrderSide.SELL, "1000", stop="99", reduce=True)
        run_ticks(e, [tick(SOL_PERP, 3, "100", "1000")])
        assert stop.status.name == "ACCEPTED" and stop.is_reduce_only
        run_ticks(e, [tick(SOL_PERP, 4, "98", "300")])
        assert filled(stop) <= D(300), json.dumps(s.receipts)
        assert stop.status.name == "CANCELED"  # Triggered IOC remainder is terminal, no synthetic level.
        run_ticks(e, [tick(SOL_PERP, 5, "98", "300")])
        assert filled(stop) == D(300)
        assert any(r["kind"] == "OrderCanceled" for r in s.receipts)
        assert e.cache.positions_open()[0].quantity.as_decimal() == D(700)
    finally:
        e.end(); e.dispose()
