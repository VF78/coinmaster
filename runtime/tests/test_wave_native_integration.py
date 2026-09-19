from decimal import Decimal

from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.data import Bar, BarSpecification, BarType
from nautilus_trader.model.enums import AccountType, AggregationSource, BarAggregation, OmsType, PriceType
from nautilus_trader.model.objects import Money, Price, Quantity

from coinmaster.research.native_fixture import BTC_PERP, SIM, SOL_PERP, quote
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy, WaveOverlayStrategyConfig


def make_bar_type(instrument_id, price_type):
    return BarType(instrument_id, BarSpecification(1, BarAggregation.DAY, price_type), AggregationSource.EXTERNAL)


def make_bar(kind, open_price: float, close_price: float, timestamp: int) -> Bar:
    volume = "1000.000" if kind.instrument_id == BTC_PERP.id else "1000.0"
    precision = 1 if kind.instrument_id == BTC_PERP.id else 2
    price = lambda value: Price.from_str(f"{value:.{precision}f}")
    return Bar(kind, price(open_price), price(max(open_price, close_price)), price(min(open_price, close_price)), price(close_price), Quantity.from_str(volume), timestamp, timestamp)


def test_native_wave_strategy_submits_and_confirms_fills_from_four_causal_bar_streams() -> None:
    btc_last, sol_last = make_bar_type(BTC_PERP.id, PriceType.LAST), make_bar_type(SOL_PERP.id, PriceType.LAST)
    # Pinned BacktestEngine rejects MARK bars; MID is a native-compatible test
    # stand-in only, not a claim about production mark provenance.
    btc_mark, sol_mark = make_bar_type(BTC_PERP.id, PriceType.MID), make_bar_type(SOL_PERP.id, PriceType.MID)
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN, starting_balances=[Money(10_000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency, default_leverage=Decimal("1"))
    engine.add_instrument(BTC_PERP)
    engine.add_instrument(SOL_PERP)
    engine.add_strategy(WaveOverlayStrategy(WaveOverlayStrategyConfig(btc_id=BTC_PERP.id, sol_id=SOL_PERP.id, btc_bar_type=btc_last, sol_bar_type=sol_last, btc_mark_bar_type=btc_mark, sol_mark_bar_type=sol_mark, active_seed=Decimal("10000"))))
    data = []
    for day in range(850):
        timestamp = (day + 1) * 86_400_000_000_000
        btc = 100 + day * 0.04 + (6 if (day // 20) % 2 else -6) + (day % 5) * 0.1
        sol = 30 + day * 0.02 + (btc - 100) * 0.30 + (3 if (day // 17) % 2 else -3) + (day % 7) * 0.1
        data.extend((make_bar(btc_last, btc - 0.2, btc, timestamp), make_bar(sol_last, sol - 0.1, sol, timestamp), make_bar(btc_mark, btc - 0.2, btc, timestamp), make_bar(sol_mark, sol - 0.1, sol, timestamp), quote(BTC_PERP.id, f"{btc - 0.05:.1f}", f"{btc + 0.05:.1f}", timestamp + 1), quote(SOL_PERP.id, f"{sol - 0.05:.2f}", f"{sol + 0.05:.2f}", timestamp + 1)))
    engine.add_data(data)
    engine.run()
    try:
        fills = engine.trader.generate_order_fills_report()
        assert not fills.empty
        assert set(fills["instrument_id"]) <= {str(BTC_PERP.id), str(SOL_PERP.id)}
        assert fills["ts_last"].is_monotonic_increasing
        assert not engine.trader.generate_positions_report()["closing_order_id"].isna().any()
        assert not engine.trader.generate_account_report(SIM).empty
    finally:
        engine.dispose()
