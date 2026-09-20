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
    BybitTierMarginModule,
    ReserveTransferInstruction,
    normalize_native_order_request,
    perpetual,
)
from nautilus_trader.model.data import FundingRateUpdate
from nautilus_trader.backtest.models import LeveragedMarginModel
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.objects import Money, Price, Quantity
from coinmaster.ledger.journal import NativeEventJournal
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.models import LimitOrderPartialFillModel
from nautilus_trader.config import LoggingConfig, StrategyConfig
from nautilus_trader.model.enums import AccountType, OmsType, TimeInForce
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.trading.strategy import Strategy
import pytest


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


def test_native_funding_matrix_boundaries_duplicates_and_negative_rates(tmp_path) -> None:
    """Only the at-entry settlement changes native cash; signs come from native positions."""
    quotes = [
        quote(SOL_PERP.id, "100.00", "100.10", 1),  # before-settlement: no BTC position
        quote(BTC_PERP.id, "100.0", "100.1", 2),  # native entry then at-settlement
        quote(BTC_PERP.id, "100.0", "100.1", 3),  # native close; reconnect duplicate is ignored
        quote(SOL_PERP.id, "100.00", "100.10", 4),  # after-settlement: flat BTC
    ]
    cases = ((OrderSide.BUY, Decimal("0.01"), Decimal("-1")), (OrderSide.BUY, Decimal("-0.01"), Decimal("1")), (OrderSide.SELL, Decimal("0.01"), Decimal("1")), (OrderSide.SELL, Decimal("-0.01"), Decimal("-1")))
    for index, (entry_side, rate, expected_delta) in enumerate(cases):
        actions = ((BTC_PERP.id, entry_side, "1.000"), (BTC_PERP.id, OrderSide.SELL if entry_side == OrderSide.BUY else OrderSide.BUY, "1.000"))
        baseline = build_engine(actions=actions)
        database = str(tmp_path / f"funding-{index}.sqlite")
        journal = NativeEventJournal(database)
        events = (
            FundingInstruction(f"before-{index}", BTC_PERP.id, rate, 1, Decimal("100"), "synthetic_mid", True),
            FundingInstruction(f"at-{index}", BTC_PERP.id, rate, 2, Decimal("100"), "synthetic_mid", True),
            FundingInstruction(f"at-{index}", BTC_PERP.id, rate, 3, Decimal("100"), "synthetic_mid", True),
            FundingInstruction(f"after-{index}", BTC_PERP.id, rate, 4, Decimal("100"), "synthetic_mid", True),
        )
        funded = build_engine(events, funding_journal=journal, actions=actions)
        baseline.add_data(quotes); funded.add_data(quotes)
        baseline.run(); funded.run()
        try:
            plain_total = Decimal(baseline.trader.generate_account_report(SIM)["total"].iloc[-1].split()[0])
            funded_total = Decimal(funded.trader.generate_account_report(SIM)["total"].iloc[-1].split()[0])
            assert funded_total - plain_total == expected_delta
            assert [row[0] for row in journal.funding_audit()] == [f"at-{index}"]
        finally:
            baseline.dispose(); funded.dispose(); journal.close()


def test_native_tick_step_and_min_notional_decisions_are_auditable() -> None:
    btc = perpetual("BTC-AUDIT", BTC_PERP.base_currency, "0.1", "0.001", "0.025", min_quantity="0.001", min_notional="5")
    sol = perpetual("SOL-AUDIT", SOL_PERP.base_currency, "0.01", "0.1", "0.05", min_quantity="0.1", min_notional="20")
    btc_rounded = normalize_native_order_request(btc, Decimal("100.05"), Decimal("0.0504"))
    sol_rounded = normalize_native_order_request(sol, Decimal("160.005"), Decimal("0.24"))
    btc_too_small = normalize_native_order_request(btc, Decimal("100.04"), Decimal("0.001"))
    sol_bad_step = normalize_native_order_request(sol, Decimal("160.005"), Decimal("0.0009"))
    sol_too_small = normalize_native_order_request(sol, Decimal("160.004"), Decimal("0.1"))
    assert (btc_rounded.requested_price, btc_rounded.accepted_price, btc_rounded.requested_quantity, btc_rounded.accepted_quantity, btc_rounded.status) == ("100.05", "100.0", "0.0504", "0.050", "ACCEPTED")
    assert (sol_rounded.accepted_price, sol_rounded.accepted_quantity, sol_rounded.status) == ("160.00", "0.2", "ACCEPTED")
    assert (btc_too_small.status, btc_too_small.reason) == ("REJECTED", "MIN_NOTIONAL")
    assert sol_bad_step.status == "REJECTED" and sol_bad_step.reason.startswith("NATIVE_INCREMENT:")
    assert (sol_too_small.status, sol_too_small.reason) == ("REJECTED", "MIN_NOTIONAL")


def test_native_active_to_reserve_transfer_debits_collateral_and_replays_neutrally(tmp_path) -> None:
    journal = NativeEventJournal(str(tmp_path / "reserve.sqlite"))
    events = (ReserveTransferInstruction("reserve-1", Decimal("1000"), 1), ReserveTransferInstruction("reserve-1", Decimal("1000"), 2))
    engine = build_engine(actions=(), transfer_events=events, transfer_journal=journal)
    engine.add_data([quote(BTC_PERP.id, "100.0", "100.1", 1), quote(BTC_PERP.id, "100.0", "100.1", 2)])
    engine.run()
    try:
        account = engine.trader._cache.account_for_venue(SIM)
        assert account.balance_total(BTC_PERP.quote_currency).as_decimal() == Decimal("9000")
        assert account.balance_free(BTC_PERP.quote_currency).as_decimal() == Decimal("9000")
        assert journal.transfer_audit() == [("reserve-1", "10000", "9000", "0", "1000")]
        NativeEventJournal.assert_total(Decimal("9000"), Decimal("1000"), Decimal("10000"))
    finally:
        engine.dispose(); journal.close()


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


class PartialParentConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId


class PartialParentStrategy(Strategy):
    """Native callback fixture: cancel only after Nautilus reports a partial fill."""
    def __init__(self, config: PartialParentConfig, journal: NativeEventJournal) -> None:
        super().__init__(config)
        self.journal = journal
        self.instrument = None
        self.parent = None
        self.close_order = None
        self.parent_fees = Decimal("0")
        self.close_fees = Decimal("0")
        self.phase = "NEW"

    def on_start(self) -> None:
        self.instrument = self.cache.instrument(self.config.instrument_id)
        assert self.instrument is not None
        self.subscribe_quote_ticks(self.config.instrument_id)

    def _audit(self, state: str) -> None:
        assert self.parent is not None
        account = self.cache.account_for_venue(SIM)
        assert account is not None
        position_initial_margin = account.margin_init(self.config.instrument_id)
        position_maintenance_margin = account.margin_maint(self.config.instrument_id)
        native_locked = account.balance_locked(BTC_PERP.quote_currency).as_decimal()
        # Native locked collateral includes the live position maintenance
        # amount. The remainder above that is the pending-parent reservation;
        # it is deliberately not called position initial margin.
        pending_reservation = native_locked - (
            position_maintenance_margin.as_decimal() if position_maintenance_margin is not None else Decimal("0")
        )
        self.journal.record_native_parent_order(
            str(self.parent.client_order_id), state, self.parent.quantity.as_decimal(),
            self.parent.filled_qty.as_decimal(), self.parent.leaves_qty.as_decimal(),
            self.parent.leaves_qty.as_decimal() if self.parent.status.name == "CANCELED" else Decimal("0"),
            pending_reservation,
            position_initial_margin.as_decimal() if position_initial_margin is not None else None,
            position_maintenance_margin.as_decimal() if position_maintenance_margin is not None else None,
            native_locked,
            account.balance_free(BTC_PERP.quote_currency).as_decimal(),
            self.parent_fees, self.close_fees,
        )

    def on_quote_tick(self, tick) -> None:
        assert self.instrument is not None
        if self.phase == "NEW":
            self.parent = self.order_factory.limit(
                instrument_id=tick.instrument_id, order_side=OrderSide.BUY,
                quantity=self.instrument.make_qty(Decimal("10")), price=self.instrument.make_price(Decimal("100.1")),
                time_in_force=TimeInForce.GTC,
            )
            self.phase = "PARENT_SUBMITTED"
            self.submit_order(self.parent)
        elif self.phase == "PARENT_CANCELED":
            # The tier module has now processed a fresh explicit mark against
            # the native open position. Capture this before reducing it.
            self._audit("POSITION_IM_HELD")
            self.phase = "POSITION_AUDITED"
        elif self.phase == "POSITION_AUDITED":
            self.close_order = self.order_factory.market(
                instrument_id=tick.instrument_id, order_side=OrderSide.SELL,
                quantity=self.instrument.make_qty(Decimal("5")), time_in_force=TimeInForce.IOC, reduce_only=True,
            )
            self.phase = "CLOSE_SUBMITTED"
            self.submit_order(self.close_order)
        elif self.phase == "CLOSE_FILLED":
            self._audit("CLOSED_MARGIN_CLEARED")
            self.phase = "CLOSED"

    def on_order_filled(self, event) -> None:
        if self.parent is not None and event.client_order_id == self.parent.client_order_id:
            # LimitOrderPartialFillModel emits a genuine native 5-contract
            # fill before this callback; do not manufacture a partial event.
            if self.parent.is_open:
                assert self.parent.status.name == "PARTIALLY_FILLED"
                self.parent_fees += event.commission.as_decimal()
                self._audit(self.parent.status.name)
                self.phase = "CANCEL_REQUESTED"
                self.cancel_order(self.parent)
        elif self.close_order is not None and event.client_order_id == self.close_order.client_order_id:
            self.close_fees += event.commission.as_decimal()
            self._audit("CLOSE_FILLED")
            self.phase = "CLOSE_FILLED"

    def on_order_canceled(self, event) -> None:
        if self.parent is not None and event.client_order_id == self.parent.client_order_id:
            self._audit("CANCELED")
            self.phase = "PARENT_CANCELED"


def test_native_partial_limit_parent_cancel_holds_remainder_until_confirmation(tmp_path) -> None:
    journal = NativeEventJournal(str(tmp_path / "partial-parent.sqlite"))
    engine = BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level="ERROR")))
    engine.add_venue(
        venue=SIM, oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
        starting_balances=[Money(10_000, BTC_PERP.quote_currency)], base_currency=BTC_PERP.quote_currency,
        default_leverage=Decimal("1"), fill_model=LimitOrderPartialFillModel(),
        modules=[BybitTierMarginModule(
            marks=(MarkPriceUpdate(BTC_PERP.id, Decimal("100.1"), 1),),
            # Captured 40x selected leverage yields max(tier IM, 1/40)=2.5%.
            selected_leverage=((BTC_PERP.id, Decimal("40")),),
            max_mark_age_ns=1,
        )],
    )
    engine.add_instrument(BTC_PERP)
    strategy = PartialParentStrategy(PartialParentConfig(instrument_id=BTC_PERP.id), journal)
    engine.add_strategy(strategy)
    engine.add_data([
        quote(BTC_PERP.id, "100.0", "100.1", 1),
        quote(BTC_PERP.id, "100.0", "100.1", 2),
        quote(BTC_PERP.id, "100.0", "100.1", 3),
        quote(BTC_PERP.id, "100.0", "100.1", 4),
    ])
    engine.run()
    try:
        orders = engine.trader.generate_orders_report()
        parent = orders[orders["type"] == "LIMIT"].iloc[0]
        close = orders[orders["type"] == "MARKET"].iloc[0]
        assert parent["status"] == "CANCELED" and Decimal(str(parent["filled_qty"])) == Decimal("5")
        assert Decimal(str(parent["quantity"])) == Decimal("10")
        assert Decimal(str(close["filled_qty"])) == Decimal("5")
        audit = {row[1]: row for row in journal.native_parent_order_audit()}
        partial, canceled, held, close_filled, closed = (
            audit["PARTIALLY_FILLED"], audit["CANCELED"], audit["POSITION_IM_HELD"],
            audit["CLOSE_FILLED"], audit["CLOSED_MARGIN_CLEARED"],
        )
        assert tuple(Decimal(value) for value in partial[2:5]) == (Decimal("10"), Decimal("5"), Decimal("5"))
        assert tuple(Decimal(value) for value in canceled[3:5]) == (Decimal("5"), Decimal("5"))
        assert Decimal(canceled[5]) == Decimal("5")
        # Distinct facts: the parent reservation is released at cancel. The
        # native exchange's pre-tier maintenance collateral remains 2.5025;
        # a fresh captured-tier update then holds the five-contract IM/MM.
        assert Decimal(partial[6]) == Decimal("25.025")
        assert Decimal(canceled[6]) == Decimal("0")
        assert Decimal(canceled[8]) == Decimal("2.5025")
        assert Decimal(canceled[9]) == Decimal("2.5025")
        expected_position_im = Decimal("5") * Decimal("100.1") * Decimal("0.025")
        assert Decimal(held[7]) == expected_position_im == Decimal("12.5125")
        assert Decimal(held[8]) == Decimal("1.65165")
        assert Decimal(held[9]) == Decimal(held[7]) + Decimal(held[8])
        assert Decimal(closed[9]) == 0
        assert closed[7] is None and closed[8] is None
        assert Decimal(partial[10]) < Decimal(canceled[10]) < Decimal(closed[10])
        assert Decimal(partial[11]) == Decimal("0.50050000")
        assert Decimal(close_filled[12]) == Decimal("0.50000000")
        assert Decimal(closed[12]) == Decimal("0.50000000")
        assert parent["commissions"] == ["0.50050000 USDT"]
        assert close["commissions"] == ["0.50000000 USDT"]
        assert engine.trader._cache.positions_open() == [] and engine.trader._cache.orders_open() == []
        assert strategy.phase == "CLOSED"
    finally:
        engine.dispose(); journal.close()


def test_pinned_automatic_liquidation_path_fails_closed_without_fiction() -> None:
    from coinmaster.research.native_fixture import NATIVE_1231_UNSUPPORTED, require_native_execution_capability
    assert "maximum 5 contracts" in LimitOrderPartialFillModel.__doc__
    assert "liquidation" not in BacktestEngine.add_venue.__doc__.lower()
    for capability, code in NATIVE_1231_UNSUPPORTED.items():
        with pytest.raises(RuntimeError, match=code):
            require_native_execution_capability(capability)


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
