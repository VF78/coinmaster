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
from nautilus_trader.backtest.models import LeveragedMarginModel
from nautilus_trader.model.objects import Price, Quantity
from coinmaster.venues.margin import MarginReservations
from coinmaster.ledger.journal import NativeEventJournal


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
        FundingInstruction("btc-positive", BTC_PERP.id, Decimal("0.01"), 6, Decimal("80999.5"), "synthetic_mid", True),
        FundingInstruction("sol-negative", SOL_PERP.id, Decimal("-0.01"), 6, Decimal("159.95"), "synthetic_mid", True),
        FundingInstruction("btc-positive", BTC_PERP.id, Decimal("0.01"), 6, Decimal("80999.5"), "synthetic_mid", True),  # deduped ID
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


def test_native_margin_model_sums_two_legs_and_engine_rejects_excess_increase() -> None:
    margin = LeveragedMarginModel()
    btc_im = margin.calculate_margin_init(BTC_PERP, Quantity.from_str("1.000"), Price.from_str("80000.0"), Decimal("1"))
    sol_im = margin.calculate_margin_init(SOL_PERP, Quantity.from_str("500.0"), Price.from_str("160.00"), Decimal("1"))
    assert btc_im.as_decimal() + sol_im.as_decimal() == Decimal("6000")

    engine = build_engine(margin_probe=True)
    engine.add_data([
        quote(BTC_PERP.id, "80000.0", "80001.0", 1),
        quote(SOL_PERP.id, "159.90", "160.00", 2),
        quote(SOL_PERP.id, "159.90", "160.00", 3),
    ])
    engine.run()
    try:
        # The 1100-SOL increase needs 8,800 additional IM after BTC+SOL's 6,000;
        # native preflight must not let it become a third fill on a 10,000 account.
        assert len(engine.trader.generate_order_fills_report()) == 2
    finally:
        engine.dispose()


def test_partial_fill_keeps_parent_margin_reserved_until_cancel_confirmation() -> None:
    reservations = MarginReservations()
    reservations.reserve("btc-parent", Decimal("2000"))
    reservations.record_fill("btc-parent", Decimal("1000"))
    assert reservations.total_held_im() == Decimal("2000")
    reservations.cancel_remainder("btc-parent")
    assert reservations.total_held_im() == Decimal("1000")


def test_production_funding_requires_confirmed_venue_settlement_mark() -> None:
    try:
        FundingInstruction("missing-mark", BTC_PERP.id, Decimal("0.01"), 6)
    except ValueError as error:
        assert "settlement mark" in str(error)
    else:
        raise AssertionError("funding without venue settlement mark must fail closed")


def test_journal_dedupes_events_and_transfers_cannot_create_total() -> None:
    journal = NativeEventJournal()
    assert journal.record_funding("venue-funding-1", Decimal("14346.303"))
    assert not journal.record_funding("venue-funding-1", Decimal("14346.303"))
    assert journal.record_transfer("transfer-1", Decimal("9000"), Decimal("8000"), Decimal("1000"), Decimal("2000"))
    assert not journal.record_transfer("transfer-1", Decimal("9000"), Decimal("8000"), Decimal("1000"), Decimal("2000"))
    NativeEventJournal.assert_total(Decimal("8000"), Decimal("2000"), Decimal("10000"))


def test_mark_tier_crossing_updates_native_margin_account_without_fill() -> None:
    engine = build_engine(tier_probe=True)
    engine.add_data([
        quote(BTC_PERP.id, "80000.0", "80001.0", 1),
        quote(BTC_PERP.id, "99999.0", "100000.0", 2),
    ])
    engine.run()
    try:
        account = engine.trader._cache.account_for_venue(SIM)
        assert account.margin_init(BTC_PERP.id).as_decimal() == Decimal("3999.98")
        assert account.margin_maint(BTC_PERP.id).as_decimal() == Decimal("1489.99")
    finally:
        engine.dispose()
