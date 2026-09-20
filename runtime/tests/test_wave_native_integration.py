from decimal import Decimal
from datetime import UTC, datetime, timedelta

from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.data import Bar, BarSpecification, BarType
from nautilus_trader.model.enums import AccountType, AggregationSource, BarAggregation, OmsType, PriceType
from nautilus_trader.model.objects import Money, Price, Quantity

from coinmaster.research.native_fixture import BTC_PERP, SIM, SOL_PERP, MarkPriceUpdate, quote
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig
from coinmaster.domain.wave_overlay import DailyBar
from coinmaster.venues.marks import venue_mark, venue_mark_data_type


def make_bar_type(instrument_id, price_type):
    return BarType(instrument_id, BarSpecification(1, BarAggregation.DAY, price_type), AggregationSource.EXTERNAL)


def make_bar(kind, open_price: float, close_price: float, timestamp: int) -> Bar:
    volume = "1000.000" if kind.instrument_id == BTC_PERP.id else "1000.0"
    precision = 1 if kind.instrument_id == BTC_PERP.id else 2
    price = lambda value: Price.from_str(f"{value:.{precision}f}")
    return Bar(kind, price(open_price), price(max(open_price, close_price)), price(min(open_price, close_price)), price(close_price), Quantity.from_str(volume), timestamp, timestamp)


def test_native_wave_strategy_submits_and_confirms_fills_from_four_causal_bar_streams() -> None:
    btc_last, sol_last = make_bar_type(BTC_PERP.id, PriceType.LAST), make_bar_type(SOL_PERP.id, PriceType.LAST)
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(10_000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency, default_leverage=Decimal("1"))
    engine.add_instrument(BTC_PERP)
    engine.add_instrument(SOL_PERP)
    from nautilus_trader.model.identifiers import ClientId
    strategy = WaveOverlayStrategy(WaveOverlayStrategyConfig(btc_id=BTC_PERP.id, sol_id=SOL_PERP.id, btc_bar_type=btc_last, sol_bar_type=sol_last, btc_mark_data_type=venue_mark_data_type(BTC_PERP.id), sol_mark_data_type=venue_mark_data_type(SOL_PERP.id), mark_client_id=ClientId("TEST_MARKS"), active_seed=Decimal("10000"), tier_marks=tuple(MarkPriceUpdate(BTC_PERP.id, Decimal("100"), day * 86_400_000_000_000) for day in range(1, 851)) + tuple(MarkPriceUpdate(SOL_PERP.id, Decimal("30"), day * 86_400_000_000_000) for day in range(1, 851)), tier_selected_leverage=((BTC_PERP.id, Decimal("40")), (SOL_PERP.id, Decimal("20"))), max_mark_age_ns=86_400_000_000_000))
    engine.add_strategy(strategy)
    data, marks = [], []
    for day in range(850):
        timestamp = (day + 1) * 86_400_000_000_000
        btc = 100 + day * 0.04 + (6 if (day // 20) % 2 else -6) + (day % 5) * 0.1
        sol = 30 + day * 0.02 + (btc - 100) * 0.30 + (3 if (day // 17) % 2 else -3) + (day % 7) * 0.1
        data.extend((make_bar(btc_last, btc - 0.2, btc, timestamp), make_bar(sol_last, sol - 0.1, sol, timestamp), quote(BTC_PERP.id, f"{btc - 0.05:.1f}", f"{btc + 0.05:.1f}", timestamp + 1), quote(SOL_PERP.id, f"{sol - 0.05:.2f}", f"{sol + 0.05:.2f}", timestamp + 1)))
        marks.extend((venue_mark(BTC_PERP.id, Decimal(str(btc)), timestamp), venue_mark(SOL_PERP.id, Decimal(str(sol)), timestamp)))
    engine.add_data(data, sort=False)
    engine.add_data(marks, client_id=ClientId("TEST_MARKS"), sort=False)
    engine.sort_data()
    engine.run()
    try:
        fills = engine.trader.generate_order_fills_report()
        assert not fills.empty
        assert set(fills["instrument_id"]) <= {str(BTC_PERP.id), str(SOL_PERP.id)}
        assert fills["ts_last"].is_monotonic_increasing
        assert not engine.trader.generate_positions_report()["closing_order_id"].isna().any()
        assert not engine.trader.generate_account_report(SIM).empty
        assert len(strategy._latest_marks) <= 2
        assert len(strategy._latest_tier_marks) <= 2
        assert not strategy._queued_intents
    finally:
        engine.dispose()


def test_seed_warmup_never_replays_orders_and_first_live_daily_close_can_fill() -> None:
    """The verified history seeds features only; the next causal close decides."""
    btc_last, sol_last = make_bar_type(BTC_PERP.id, PriceType.LAST), make_bar_type(SOL_PERP.id, PriceType.LAST)
    marks = tuple(MarkPriceUpdate(BTC_PERP.id, Decimal("100"), day * 86_400_000_000_000) for day in range(1, 851)) + tuple(MarkPriceUpdate(SOL_PERP.id, Decimal("30"), day * 86_400_000_000_000) for day in range(1, 851))
    seed: list[DailyBar] = []
    data, custom_marks = [], []
    for day in range(850):
        timestamp = (day + 1) * 86_400_000_000_000
        btc = 100 + day * 0.04 + (6 if (day // 20) % 2 else -6) + (day % 5) * 0.1
        sol = 30 + day * 0.02 + (btc - 100) * 0.30 + (3 if (day // 17) % 2 else -3) + (day % 7) * 0.1
        if day < 800:
            close = datetime.fromtimestamp(timestamp / 1_000_000_000, UTC)
            seed.append(DailyBar(close - timedelta(days=1), close, close, btc - 0.2, btc, sol))
        else:
            data.extend((make_bar(btc_last, btc - 0.2, btc, timestamp), make_bar(sol_last, sol - 0.1, sol, timestamp), quote(BTC_PERP.id, f"{btc - 0.05:.1f}", f"{btc + 0.05:.1f}", timestamp + 1), quote(SOL_PERP.id, f"{sol - 0.05:.2f}", f"{sol + 0.05:.2f}", timestamp + 1)))
            custom_marks.extend((venue_mark(BTC_PERP.id, Decimal(str(btc)), timestamp), venue_mark(SOL_PERP.id, Decimal(str(sol)), timestamp)))
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(10_000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency, default_leverage=Decimal("1"))
    engine.add_instrument(BTC_PERP); engine.add_instrument(SOL_PERP)
    from nautilus_trader.model.identifiers import ClientId
    engine.add_strategy(WaveOverlayStrategy(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP.id, sol_id=SOL_PERP.id, btc_bar_type=btc_last, sol_bar_type=sol_last,
        btc_mark_data_type=venue_mark_data_type(BTC_PERP.id), sol_mark_data_type=venue_mark_data_type(SOL_PERP.id), mark_client_id=ClientId("TEST_MARKS"), active_seed=Decimal("10000"),
        tier_marks=marks, tier_selected_leverage=((BTC_PERP.id, Decimal("40")), (SOL_PERP.id, Decimal("20"))), max_mark_age_ns=86_400_000_000_000,
        seed_bars=tuple(seed), trading_start_open_ns=800 * 86_400_000_000_000,
    )))
    engine.add_data(data, sort=False); engine.add_data(custom_marks, client_id=ClientId("TEST_MARKS"), sort=False); engine.sort_data(); engine.run()
    try:
        fills = engine.trader.generate_order_fills_report()
        assert not fills.empty
        # No seed bar went through on_bar: every fill follows the first live
        # daily session, never a warmup replay decision.
        assert fills["ts_last"].min().value >= 801 * 86_400_000_000_000
    finally:
        engine.dispose()


def test_warmup_only_has_no_native_orders() -> None:
    """Even valid history cannot create orders before the configured live open."""
    btc_last, sol_last = make_bar_type(BTC_PERP.id, PriceType.LAST), make_bar_type(SOL_PERP.id, PriceType.LAST)
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(10_000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency, default_leverage=Decimal("1"))
    engine.add_instrument(BTC_PERP); engine.add_instrument(SOL_PERP)
    from nautilus_trader.model.identifiers import ClientId
    engine.add_strategy(WaveOverlayStrategy(WaveOverlayStrategyConfig(
        btc_id=BTC_PERP.id, sol_id=SOL_PERP.id, btc_bar_type=btc_last, sol_bar_type=sol_last,
        btc_mark_data_type=venue_mark_data_type(BTC_PERP.id), sol_mark_data_type=venue_mark_data_type(SOL_PERP.id), mark_client_id=ClientId("TEST_MARKS"), active_seed=Decimal("10000"),
        trading_start_open_ns=999 * 86_400_000_000_000,
    )))
    data, marks = [], []
    for day in range(10):
        timestamp = (day + 1) * 86_400_000_000_000
        data.extend((make_bar(btc_last, 100, 101, timestamp), make_bar(sol_last, 30, 31, timestamp), quote(BTC_PERP.id, "100.0", "100.1", timestamp + 1), quote(SOL_PERP.id, "30.00", "30.01", timestamp + 1)))
        marks.extend((venue_mark(BTC_PERP.id, Decimal("101"), timestamp), venue_mark(SOL_PERP.id, Decimal("31"), timestamp)))
    engine.add_data(data, sort=False); engine.add_data(marks, client_id=ClientId("TEST_MARKS"), sort=False); engine.sort_data(); engine.run()
    try:
        assert engine.trader.generate_order_fills_report().empty
    finally:
        engine.dispose()
