from decimal import Decimal

from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import LoggingConfig, StrategyConfig
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide, TimeInForce
from nautilus_trader.model.events import OrderFilled
from nautilus_trader.model.identifiers import ClientId, InstrumentId
from nautilus_trader.model.objects import Money
from nautilus_trader.trading.strategy import Strategy

from coinmaster.research.native_fixture import (
    BTC_PERP,
    SIM,
    BybitTierMarginModule,
    MarkPriceUpdate,
    quote,
)
from coinmaster.venues.marks import VenueMark, venue_mark, venue_mark_data_type


class MarkProbeConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    mark_client_id: ClientId


class MarkProbeStrategy(Strategy):
    """Uses marks for equity only; it has no mark-triggered order path."""

    def __init__(self, config: MarkProbeConfig) -> None:
        super().__init__(config)
        self._instrument = None
        self._submitted = False
        self.fill_count = 0
        self.marked_equity: list[Decimal] = []
        self.fills_when_marked: list[int] = []

    def on_start(self) -> None:
        self._instrument = self.cache.instrument(self.config.instrument_id)
        assert self._instrument is not None
        self.subscribe_quote_ticks(self.config.instrument_id)
        self.subscribe_data(venue_mark_data_type(self.config.instrument_id), client_id=self.config.mark_client_id)

    def on_quote_tick(self, tick) -> None:
        if self._submitted:
            return
        self.submit_order(self.order_factory.market(
            instrument_id=self.config.instrument_id,
            order_side=OrderSide.BUY,
            quantity=self._instrument.make_qty(Decimal("1")),
            time_in_force=TimeInForce.IOC,
        ))
        self._submitted = True

    def on_order_filled(self, event: OrderFilled) -> None:
        self.fill_count += 1

    def on_data(self, data) -> None:
        # CustomData is intentionally unwrapped before delivery in Nautilus.
        if not isinstance(data, VenueMark) or data.instrument_id != self.config.instrument_id:
            return
        position = next(iter(self.cache.positions_open()), None)
        assert position is not None
        account = self.cache.account_for_venue(SIM)
        assert account is not None
        self.marked_equity.append(
            account.balance_total(BTC_PERP.quote_currency).as_decimal()
            + position.unrealized_pnl(self._instrument.make_price(data.price)).as_decimal(),
        )
        self.fills_when_marked.append(self.fill_count)


def test_custom_mark_reprices_equity_and_native_margin_without_matching() -> None:
    mark_client = ClientId("TEST_MARKS")
    marks = (
        MarkPriceUpdate(BTC_PERP.id, Decimal("100"), 102),
        MarkPriceUpdate(BTC_PERP.id, Decimal("200"), 103),
    )
    margin_module = BybitTierMarginModule(
        marks,
        ((BTC_PERP.id, Decimal("40")),),
        0,
    )
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(
        venue=SIM,
        oms_type=OmsType.NETTING,
        account_type=AccountType.MARGIN,
        starting_balances=[Money(10_000, BTC_PERP.quote_currency)],
        base_currency=BTC_PERP.quote_currency,
        default_leverage=Decimal("1"),
        modules=[margin_module],
    )
    engine.add_instrument(BTC_PERP)
    strategy = MarkProbeStrategy(MarkProbeConfig(instrument_id=BTC_PERP.id, mark_client_id=mark_client))
    engine.add_strategy(strategy)
    # Both executable quotes have the same price. Only CustomData differs.
    engine.add_data([quote(BTC_PERP.id, "99.9", "100.1", 100), quote(BTC_PERP.id, "99.9", "100.1", 101)], sort=False)
    engine.add_data([venue_mark(BTC_PERP.id, Decimal("100"), 102), venue_mark(BTC_PERP.id, Decimal("200"), 103)], client_id=mark_client, sort=False)
    engine.sort_data()
    engine.run()
    try:
        assert strategy.fill_count == 1
        assert strategy.fills_when_marked == [1, 1]
        assert strategy.marked_equity[1] - strategy.marked_equity[0] == Decimal("100")
        # The module receives the same explicit marks and reprices both native
        # IM and MM. Neither mark was eligible to match an order.
        at_100 = next(item for item in margin_module.observed if item[1] == Decimal("100"))
        at_200 = next(item for item in margin_module.observed if item[1] == Decimal("200"))
        assert at_200[2] > at_100[2]
        assert at_200[3] > at_100[3]
    finally:
        engine.dispose()
