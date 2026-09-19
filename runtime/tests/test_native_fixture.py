from decimal import Decimal

from coinmaster.research.native_fixture import (
    BTC_PERP,
    SOL_PERP,
    FundingInstruction,
    SIM,
    build_engine,
    quote,
)
from nautilus_trader.model.data import FundingRateUpdate


def fixture_quotes():
    return [
        quote(BTC_PERP.id, "80000.0", "80001.0", 1), quote(BTC_PERP.id, "80999.0", "81000.0", 2),
        quote(BTC_PERP.id, "80999.0", "81000.0", 3), quote(BTC_PERP.id, "80999.0", "81000.0", 4),
        quote(SOL_PERP.id, "159.90", "160.00", 5), quote(SOL_PERP.id, "159.90", "160.00", 6),
        quote(BTC_PERP.id, "80999.0", "81000.0", 7), quote(BTC_PERP.id, "80999.0", "81000.0", 8),
        quote(SOL_PERP.id, "149.90", "150.00", 9), quote(SOL_PERP.id, "149.90", "150.00", 10),
    ]


def test_native_engine_emits_two_leg_fills_and_closes_them() -> None:
    engine = build_engine()
    # Market orders fill from the quote which triggers the native strategy action.
    engine.add_data(fixture_quotes())
    engine.run()
    fills = engine.trader.generate_order_fills_report()
    positions = engine.trader.generate_positions_report()
    try:
        assert len(fills) == 5
        assert set(fills["instrument_id"]) == {str(BTC_PERP.id), str(SOL_PERP.id)}
        assert positions["closing_order_id"].notna().all()
        assert len(positions) == 2
        total = Decimal(engine.trader.generate_account_report(SIM)["total"].iloc[-1].split()[0])
        # Start 10,000 + BTC realized 998 - BTC fees 162 + SOL realized 4,950 - SOL fees 154.95.
        assert total == Decimal("15632.05")
    finally:
        engine.dispose()


def test_native_funding_update_alone_does_not_post_account_money() -> None:
    engine = build_engine()
    engine.add_data(fixture_quotes())
    # The event is delivered while the BTC position is open. The pinned engine
    # exposes the data event, but has no perpetual-funding account module.
    engine.add_data([FundingRateUpdate(BTC_PERP.id, Decimal("0.01"), 6, 6, interval=480, next_funding_ns=6)])
    engine.run()
    try:
        total = Decimal(engine.trader.generate_account_report(SIM)["total"].iloc[-1].split()[0])
        assert total == Decimal("15632.05")
    finally:
        engine.dispose()


def test_supported_funding_module_posts_signed_native_account_adjustments_once() -> None:
    events = (
        FundingInstruction("btc-positive", BTC_PERP.id, Decimal("0.01"), 6),
        FundingInstruction("sol-negative", SOL_PERP.id, Decimal("-0.01"), 6),
        FundingInstruction("btc-positive", BTC_PERP.id, Decimal("0.01"), 6),  # deduped ID
    )
    engine = build_engine(events)
    engine.add_data(fixture_quotes())
    engine.run()
    try:
        total = Decimal(engine.trader.generate_account_report(SIM)["total"].iloc[-1].split()[0])
        # At ts=6: BTC long 0.6 at mid 80,999.5 pays 485.997; SOL short 500 at
        # mid 159.95 pays 799.75 under a negative rate. The account owns the postings.
        assert total == Decimal("14346.303")
    finally:
        engine.dispose()
