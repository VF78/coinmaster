from decimal import Decimal

from coinmaster.research.native_fixture import (
    BTC_PERP,
    SOL_PERP,
    FundingInstruction,
    SIM,
    build_engine,
    quote,
    MarkPriceUpdate,
    TierMarginPolicy,
)
from nautilus_trader.model.data import FundingRateUpdate
from nautilus_trader.backtest.models import LeveragedMarginModel
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.objects import Price, Quantity
from coinmaster.venues.margin import MarginReservations
from coinmaster.ledger.journal import NativeEventJournal


TIER_LEVERAGE = ((BTC_PERP.id, Decimal("100")), (SOL_PERP.id, Decimal("100")))


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


def test_supported_funding_module_posts_signed_native_account_adjustments_once(tmp_path) -> None:
    events = (
        FundingInstruction("btc-positive", BTC_PERP.id, Decimal("0.01"), 6, Decimal("80999.5"), "synthetic_mid", True),
        FundingInstruction("sol-negative", SOL_PERP.id, Decimal("-0.01"), 6, Decimal("159.95"), "synthetic_mid", True),
        FundingInstruction("btc-positive", BTC_PERP.id, Decimal("0.01"), 6, Decimal("80999.5"), "synthetic_mid", True),  # deduped ID
    )
    journal = NativeEventJournal(str(tmp_path / "funding.sqlite"))
    engine = build_engine(events, funding_journal=journal)
    engine.add_data(fixture_quotes())
    engine.run()
    try:
        total = Decimal(engine.trader.generate_account_report(SIM)["total"].iloc[-1].split()[0])
        # At ts=6: BTC long 0.6 at mid 80,999.5 pays 485.997; SOL short 500 at
        # mid 159.95 pays 799.75 under a negative rate. The account owns the postings.
        assert total == Decimal("14346.303")
        assert [row[0] for row in journal.funding_audit()] == ["btc-positive", "sol-negative"]
    finally:
        engine.dispose()


def test_funding_replay_uses_durable_ids_and_does_not_repost_native_money(tmp_path) -> None:
    events = (
        FundingInstruction("btc-positive", BTC_PERP.id, Decimal("0.01"), 6, Decimal("80999.5"), "synthetic_mid", True),
        FundingInstruction("sol-negative", SOL_PERP.id, Decimal("-0.01"), 6, Decimal("159.95"), "synthetic_mid", True),
    )
    database = str(tmp_path / "funding.sqlite")
    journal = NativeEventJournal(database)
    first = build_engine(events, funding_journal=journal)
    first.add_data(fixture_quotes())
    first.run()
    first.dispose()
    journal.close()

    replay_journal = NativeEventJournal(database)
    replay = build_engine(events, funding_journal=replay_journal)
    replay.add_data(fixture_quotes())
    replay.run()
    try:
        total = Decimal(replay.trader.generate_account_report(SIM)["total"].iloc[-1].split()[0])
        assert total == Decimal("15632.05")
        assert [row[0] for row in replay_journal.funding_audit()] == ["btc-positive", "sol-negative"]
    finally:
        replay.dispose()
        replay_journal.close()


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
    assert reservations.total_held_im() == Decimal("1000")
    reservations.cancel_remainder("btc-parent")
    assert reservations.total_held_im() == Decimal("0")


def test_production_funding_requires_confirmed_venue_settlement_mark() -> None:
    try:
        FundingInstruction("missing-mark", BTC_PERP.id, Decimal("0.01"), 6)
    except ValueError as error:
        assert "settlement mark" in str(error)
    else:
        raise AssertionError("funding without venue settlement mark must fail closed")


def test_journal_dedupes_events_and_transfers_cannot_create_total() -> None:
    journal = NativeEventJournal()
    assert journal.record_funding("venue-funding-1", str(BTC_PERP.id), 6, Decimal("0.01"), Decimal("80999.5"), Decimal("14346.303"))
    assert not journal.record_funding("venue-funding-1", str(BTC_PERP.id), 6, Decimal("0.01"), Decimal("80999.5"), Decimal("14346.303"))
    assert journal.record_transfer("transfer-1", Decimal("9000"), Decimal("8000"), Decimal("1000"), Decimal("2000"))
    assert not journal.record_transfer("transfer-1", Decimal("9000"), Decimal("8000"), Decimal("1000"), Decimal("2000"))
    NativeEventJournal.assert_total(Decimal("8000"), Decimal("2000"), Decimal("10000"))


def test_mark_tier_crossing_updates_native_margin_account_without_fill() -> None:
    engine = build_engine(tier_probe=True, marks=(
        MarkPriceUpdate(BTC_PERP.id, Decimal("75000"), 1),
        MarkPriceUpdate(BTC_PERP.id, Decimal("80000"), 2),
    ), tier_selected_leverage=TIER_LEVERAGE)
    engine.add_data([
        quote(BTC_PERP.id, "80000.0", "80001.0", 1),
        quote(BTC_PERP.id, "80000.0", "80001.0", 2),
    ])
    engine.run()
    try:
        policy = TierMarginPolicy(
            (MarkPriceUpdate(BTC_PERP.id, Decimal("75000"), 1), MarkPriceUpdate(BTC_PERP.id, Decimal("80000"), 2)),
            dict(TIER_LEVERAGE),
            0,
        )
        # Selected 100x leverage imposes a 1% IM floor before the first public tier;
        # the second tier's 1% IM then produces the same rate at the 300k boundary.
        assert policy.margin_for(BTC_PERP.id, Decimal("4"), 1)[:2] == (Decimal("3000.00"), Decimal("990.000"))
        assert policy.margin_for(BTC_PERP.id, Decimal("4"), 2)[:2] == (Decimal("3200.00"), Decimal("1090.00"))
        account = engine.trader._cache.account_for_venue(SIM)
        assert account.margin_init(BTC_PERP.id).as_decimal() == Decimal("3200.00")
        assert account.margin_maint(BTC_PERP.id).as_decimal() == Decimal("1090.00")
    finally:
        engine.dispose()


def test_tier_module_clears_native_margins_after_native_btc_and_sol_closes() -> None:
    engine = build_engine(
        tier_probe=True,
        tier_selected_leverage=TIER_LEVERAGE,
        marks=(
            MarkPriceUpdate(BTC_PERP.id, Decimal("75000"), 1),
            MarkPriceUpdate(BTC_PERP.id, Decimal("80000"), 2),
            MarkPriceUpdate(SOL_PERP.id, Decimal("160"), 3),
            MarkPriceUpdate(SOL_PERP.id, Decimal("160"), 4),
        ),
        tier_actions=(
            (BTC_PERP.id, OrderSide.BUY, "4.000"),
            (BTC_PERP.id, OrderSide.SELL, "4.000"),
            (SOL_PERP.id, OrderSide.SELL, "500.0"),
            (SOL_PERP.id, OrderSide.BUY, "500.0"),
        ),
    )
    engine.add_data([
        quote(BTC_PERP.id, "80000.0", "80001.0", 1),
        quote(BTC_PERP.id, "80000.0", "80001.0", 2),
        quote(SOL_PERP.id, "159.90", "160.00", 3),
        quote(SOL_PERP.id, "159.90", "160.00", 4),
    ])
    engine.run()
    try:
        account = engine.trader._cache.account_for_venue(SIM)
        positions = engine.trader.generate_positions_report()
        assert len(positions) == 2
        assert positions["closing_order_id"].notna().all()
        assert engine.trader._cache.orders_open() == []
        assert account.margin_init(BTC_PERP.id) is None
        assert account.margin_maint(BTC_PERP.id) is None
        assert account.margin_init(SOL_PERP.id) is None
        assert account.margin_maint(SOL_PERP.id) is None
    finally:
        engine.dispose()


def test_stale_marks_reject_new_risk_but_native_reduction_still_closes() -> None:
    engine = build_engine(
        tier_probe=True,
        tier_selected_leverage=TIER_LEVERAGE,
        marks=(MarkPriceUpdate(BTC_PERP.id, Decimal("80000"), 1),),
        max_mark_age_ns=0,
        tier_actions=(
            (BTC_PERP.id, OrderSide.BUY, "4.000"),
            (BTC_PERP.id, OrderSide.BUY, "1.000"),
            (BTC_PERP.id, OrderSide.SELL, "4.000"),
        ),
    )
    engine.add_data([quote(BTC_PERP.id, "80000.0", "80001.0", ts) for ts in (1, 2, 3)])
    engine.run()
    try:
        assert len(engine.trader.generate_order_fills_report()) == 2
        assert engine.trader.generate_positions_report()["closing_order_id"].notna().all()
        assert engine.trader._cache.orders_open() == []
    finally:
        engine.dispose()


def test_tier_policy_rejects_unknown_and_out_of_range_risk() -> None:
    policy = TierMarginPolicy((MarkPriceUpdate(BTC_PERP.id, Decimal("80000"), 1),), dict(TIER_LEVERAGE), 0)
    for instrument_id, quantity in ((SOL_PERP.id, Decimal("1")), (BTC_PERP.id, Decimal("20000"))):
        try:
            policy.margin_for(instrument_id, quantity, 1)
        except ValueError:
            pass
        else:
            raise AssertionError("unknown mark or out-of-range tier must reject an increase")
