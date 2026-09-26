from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.model.objects import Money

from coinmaster.domain.wave_overlay import DailyBar, Episode, Intent
from coinmaster.strategy.live_recovery import RecoverableWaveOverlayStrategy
from coinmaster.venues.marks import VenueMark
from test_live_native_report_recovery import _strategy
from test_hl_stageg_sandbox_lifecycle import HL_BTC


def _native_account(account_id="HYPERLIQUID-master"):
    return SimpleNamespace(
        id=AccountId(account_id),
        balance_total=lambda currency: Money(Decimal("9999.73"), USDC) if currency == USDC else None,
    )


def test_versioned_episode_and_order_mapping_roundtrip_stays_paused():
    source = RecoverableWaveOverlayStrategy(_strategy().config)
    open_time = datetime(2026, 9, 23, tzinfo=UTC)
    source._bars.append(DailyBar(open_time, open_time + timedelta(days=1),
                                 open_time + timedelta(days=1), 60000, 61000, 150))
    episode = Episode("episode-1", 1, 10000, 1.2, btc_initial_qty=0.02, btc_open_qty=0.01)
    episode.btc_tps.add(0)
    episode.sol_rights.add(0)
    episode.sol_right_fraction[0] = 0.5
    intent = Intent("intent-1", episode.id, "BTC_REDUCE", 0, -1, quantity=0.01)
    episode.pending[intent.id] = intent
    source._domain.episode = episode
    source._domain._decision_index = 1483
    source._pending_by_order["HLTG-RESTART-PROBE-1"] = intent
    source._sigma_by_order["HLTG-RESTART-PROBE-1"] = 0.18
    source._decision_index_by_order["HLTG-RESTART-PROBE-1"] = 1483
    source._latest_marks[HL_BTC.id] = VenueMark(HL_BTC.id, Decimal("61000"), 1)
    encoded = source.on_save()
    restored = RecoverableWaveOverlayStrategy(_strategy().config)
    restored.on_load(encoded)
    assert restored._domain.episode == episode
    assert restored._pending_by_order == source._pending_by_order
    assert restored._sigma_by_order == source._sigma_by_order
    assert restored._decision_index_by_order == source._decision_index_by_order
    assert restored._bars == source._bars
    assert restored._latest_marks[HL_BTC.id].price == Decimal("61000")
    assert restored.recovery_confirmed is False
    assert restored._entries_enabled() is False


def test_recovered_management_and_entries_require_new_fresh_public_feeds():
    import time
    import msgspec
    from test_hl_stageg_sandbox_lifecycle import HL_SOL

    config = msgspec.structs.replace(
        _strategy().config, entries_enabled=True, max_mark_age_ns=5_000_000_000,
    )
    strategy = RecoverableWaveOverlayStrategy(config)
    now = time.time_ns()
    strategy._latest_marks[HL_BTC.id] = VenueMark(HL_BTC.id, Decimal("60000"), now)
    strategy._latest_marks[HL_SOL.id] = VenueMark(HL_SOL.id, Decimal("200"), now)
    strategy._quote_ns[HL_BTC.id] = now
    strategy._quote_ns[HL_SOL.id] = now
    assert not strategy._feeds_fresh(now)
    assert not strategy._entries_enabled()
    assert strategy._record_submission() is False

    strategy.recovery_confirmed = True
    assert strategy._feeds_fresh(now)
    assert strategy._entries_enabled()
    strategy._quote_ns[HL_SOL.id] = now - config.max_mark_age_ns - 1
    assert not strategy._feeds_fresh(now)
    assert not strategy._entries_enabled()
    assert strategy._record_submission() is False

    strategy._quote_ns[HL_SOL.id] = now
    strategy._latest_marks[HL_BTC.id] = VenueMark(HL_BTC.id, Decimal("60000"), now - config.max_mark_age_ns - 1)
    assert not strategy._feeds_fresh(now)
    restored = RecoverableWaveOverlayStrategy(config)
    restored.on_load(strategy.on_save())
    assert restored._quote_ns == {}
    assert not restored._feeds_fresh(now)


def test_versioned_state_rejects_wrong_candidate_and_unknown_schema():
    source = RecoverableWaveOverlayStrategy(_strategy().config)
    payload = source.on_save()
    bad = {key: value.replace(b"coinmaster-wave-overlay-live-recovery-v1", b"unknown-v1")
           for key, value in payload.items()}
    with pytest.raises(ValueError, match="RECOVERY_STATE_IDENTITY_MISMATCH"):
        RecoverableWaveOverlayStrategy(_strategy().config).on_load(bad)


def test_pre_submit_intent_and_complete_episode_checkpoint_commit_atomically(tmp_path):
    import time
    from coinmaster.ops.live_recovery import LiveRecoverySubmissionSink
    from coinmaster.ops.paper import PaperRuntime

    journal = tmp_path / "live-outbox.sqlite"
    runtime = PaperRuntime(journal, "live-recovery", 10**20)
    runtime.acquire()
    runtime.snapshot(ts_ns=time.time_ns(), positions=[], orders=[], funding_event_ids=[])
    strategy = RecoverableWaveOverlayStrategy(_strategy().config)
    episode = Episode("episode-1", 1, 10000, 1.2)
    intent = Intent("intent-1", episode.id, "BTC_ENTRY", None, 1, quantity=0.02)
    episode.pending[intent.id] = intent
    strategy._domain.episode = episode
    order_id = "HLTG-RESTART-PROBE-1"
    strategy._pending_by_order[order_id] = intent
    strategy._sigma_by_order[order_id] = 0.2
    strategy._decision_index_by_order[order_id] = 1483
    sink = LiveRecoverySubmissionSink(runtime, strategy, frozenset({str(HL_BTC.id)}))
    request = {
        "client_order_id": order_id, "intent_id": intent.id,
        "episode_id": episode.id, "action": "BTC_ENTRY",
        "instrument_id": str(HL_BTC.id), "quantity": "0.02000",
        "reduce_only": False,
    }
    assert sink(**request)
    first_checkpoint = runtime.strategy_checkpoint()
    assert first_checkpoint is not None
    assert first_checkpoint[1] == runtime.native_revision()
    assert not sink(**request)
    assert runtime.strategy_checkpoint() == first_checkpoint
    runtime.close()

    reopened = PaperRuntime(journal, "live-recovery", 10**20)
    assert reopened.pending_submissions()[0]["client_order_id"] == order_id
    persisted = reopened.strategy_checkpoint()
    assert persisted == first_checkpoint
    recovered = RecoverableWaveOverlayStrategy(_strategy().config)
    recovered.on_load({"wave_overlay_live_recovery_v1": persisted[0]})
    assert recovered._domain.episode == episode
    assert recovered._pending_by_order[order_id] == intent
    assert not recovered._entries_enabled()
    reopened.close()


def test_wrong_native_fill_identity_never_advances_episode_or_trade_cursor(tmp_path):
    from types import SimpleNamespace
    from nautilus_trader.model.identifiers import AccountId, ClientOrderId, VenueOrderId, TradeId
    from nautilus_trader.model.objects import Price, Quantity
    from coinmaster.ops.live_recovery import LiveRecoveryReconciler
    from coinmaster.ops.paper import PaperRuntime

    runtime = PaperRuntime(tmp_path / "wrong-fill.sqlite", "live-recovery", 10**20)
    runtime.acquire()
    strategy = RecoverableWaveOverlayStrategy(_strategy().config)
    episode = Episode("episode-1", 1, 10000, 1.2)
    intent = Intent("intent-1", episode.id, "BTC_ENTRY", None, 1, quantity=0.02)
    episode.pending[intent.id] = intent
    strategy._domain.episode = episode
    order_id = "HLTG-RESTART-PROBE-1"
    strategy._pending_by_order[order_id] = intent
    assert runtime.record_submission(client_order_id=order_id, intent_id=intent.id, episode_id=episode.id,
                                     action=intent.action, instrument_id=str(HL_BTC.id), quantity="0.02000",
                                     reduce_only=False, strategy_state=strategy.on_save()["wave_overlay_live_recovery_v1"])
    before = runtime.strategy_checkpoint()
    report = SimpleNamespace(
        account_id=AccountId("WRONG-master"), client_order_id=ClientOrderId(order_id),
        venue_order_id=VenueOrderId("venue-1"), instrument_id=HL_BTC.id,
        trade_id=TradeId("trade-wrong"), last_qty=Quantity.from_str("0.01000"),
        last_px=Price.from_str("60000.0"), ts_event=1,
    )
    order = SimpleNamespace(
        client_order_id=ClientOrderId(order_id), venue_order_id=VenueOrderId("venue-1"),
        instrument_id=HL_BTC.id, is_closed=False,
    )
    with pytest.raises(ValueError, match="RECOVERY_FILL_IDENTITY_MISMATCH"):
        LiveRecoveryReconciler(runtime, strategy, "HYPERLIQUID-master").apply_partial_fills([report], [order], [], [SimpleNamespace(client_order_id=ClientOrderId(order_id))])
    assert runtime.strategy_checkpoint() == before
    assert episode.btc_open_qty == 0
    assert not runtime.has_recovered_fill("trade-wrong")
    runtime.close()


def test_missing_native_fill_history_with_open_position_fails_closed(tmp_path):
    from types import SimpleNamespace
    from nautilus_trader.model.objects import Quantity
    from coinmaster.ops.live_recovery import LiveRecoveryReconciler
    from coinmaster.ops.paper import PaperRuntime

    runtime = PaperRuntime(tmp_path / "missing-fill.sqlite", "live-recovery", 10**20)
    runtime.acquire()
    strategy = RecoverableWaveOverlayStrategy(_strategy().config)
    strategy._domain.episode = Episode("episode-1", 1, 10000, 1.2)
    assert runtime.record_submission(client_order_id="unfilled", intent_id="intent-1", episode_id="episode-1",
                                     action="BTC_ENTRY", instrument_id=str(HL_BTC.id), quantity="0.02000",
                                     reduce_only=False, strategy_state=strategy.on_save()["wave_overlay_live_recovery_v1"])
    before = runtime.strategy_checkpoint()
    position = SimpleNamespace(instrument_id=HL_BTC.id, quantity=Quantity.from_str("0.01000"), is_long=True,
                               account_id="HYPERLIQUID-master", strategy_id=str(strategy.id))
    with pytest.raises(ValueError, match="RECOVERY_EPISODE_POSITION_MISMATCH"):
        LiveRecoveryReconciler(runtime, strategy, "HYPERLIQUID-master").apply_partial_fills([], [], [position], [], _native_account())
    assert runtime.strategy_checkpoint() == before
    assert not strategy.recovery_confirmed
    runtime.close()

def test_valid_native_fill_with_wrong_position_does_not_poison_checkpoint(tmp_path):
    from types import SimpleNamespace
    from nautilus_trader.model.enums import OrderSide
    from nautilus_trader.model.identifiers import AccountId, ClientOrderId, VenueOrderId, TradeId
    from nautilus_trader.model.objects import Price, Quantity
    from coinmaster.ops.live_recovery import LiveRecoveryReconciler
    from coinmaster.ops.paper import PaperRuntime

    runtime = PaperRuntime(tmp_path / "parity.sqlite", "live-recovery", 10**20)
    runtime.acquire()
    strategy = RecoverableWaveOverlayStrategy(_strategy().config)
    episode = Episode("episode-1", 1, 10000, 1.2)
    intent = Intent("intent-1", episode.id, "BTC_ENTRY", None, 1, quantity=0.02)
    episode.pending[intent.id] = intent
    strategy._domain.episode = episode
    order_id = "HLTG-RESTART-PROBE-1"
    strategy._pending_by_order[order_id] = intent
    assert runtime.record_submission(client_order_id=order_id, intent_id=intent.id, episode_id=episode.id,
                                     action=intent.action, instrument_id=str(HL_BTC.id), quantity="0.02000",
                                     reduce_only=False, strategy_state=strategy.on_save()["wave_overlay_live_recovery_v1"])
    before = runtime.strategy_checkpoint()
    report = SimpleNamespace(
        account_id=AccountId("HYPERLIQUID-master"), client_order_id=ClientOrderId(order_id),
        venue_order_id=VenueOrderId("venue-1"), instrument_id=HL_BTC.id,
        trade_id=TradeId("trade-1"), last_qty=Quantity.from_str("0.01000"),
        last_px=Price.from_str("60000.0"), ts_event=1, order_side=OrderSide.BUY,
    )
    order = SimpleNamespace(
        client_order_id=report.client_order_id, venue_order_id=report.venue_order_id,
        instrument_id=HL_BTC.id, account_id=None, strategy_id=str(strategy.id),
        side=OrderSide.BUY, is_closed=False, is_reduce_only=False, trade_ids=[report.trade_id],
        quantity=Quantity.from_str("0.02000"), filled_qty=Quantity.from_str("0.01000"),
    )
    status = SimpleNamespace(
        client_order_id=report.client_order_id, venue_order_id=report.venue_order_id,
        instrument_id=HL_BTC.id, account_id=report.account_id,
        order_side=OrderSide.BUY, filled_qty=order.filled_qty,
        quantity=order.quantity, reduce_only=False,
    )
    wrong_position = SimpleNamespace(
        instrument_id=HL_BTC.id, account_id=report.account_id,
        strategy_id=str(strategy.id), quantity=Quantity.from_str("0.02000"), is_long=True,
    )
    reconciler = LiveRecoveryReconciler(runtime, strategy, str(report.account_id))
    with pytest.raises(ValueError, match="RECOVERY_EPISODE_POSITION_MISMATCH"):
        reconciler.apply_partial_fills([report], [order], [wrong_position], [status], _native_account())
    assert runtime.strategy_checkpoint() == before
    assert not runtime.has_applied_fill("trade-1")
    assert strategy.on_save()["wave_overlay_live_recovery_v1"] == before[0]
    assert episode.btc_open_qty == 0
    good_position = SimpleNamespace(**{**vars(wrong_position), "quantity": Quantity.from_str("0.01000")})
    reconciler.apply_partial_fills([report], [order], [good_position], [status], _native_account())
    assert runtime.has_applied_fill("trade-1")
    assert strategy._domain.episode.btc_open_qty == 0.01
    runtime.close()
def test_sol_half_exit_full_fill_replay_preserves_cooldown_and_terminal_cleanup(tmp_path):
    from types import SimpleNamespace
    from nautilus_trader.model.enums import OrderSide
    from nautilus_trader.model.identifiers import AccountId, ClientOrderId, VenueOrderId, TradeId
    from nautilus_trader.model.objects import Price, Quantity
    from coinmaster.ops.live_recovery import LiveRecoveryReconciler
    from coinmaster.ops.paper import PaperRuntime
    from test_hl_stageg_sandbox_lifecycle import HL_SOL

    runtime = PaperRuntime(tmp_path / "sol-half.sqlite", "live-recovery", 10**20)
    runtime.acquire()
    strategy = RecoverableWaveOverlayStrategy(_strategy().config)
    episode = Episode("episode-sol", -1, 10000, 1.2, sol_qty=0.02)
    intent = Intent("intent-half", episode.id, "SOL_HALF_EXIT", None, -1, quantity=0.01)
    episode.pending[intent.id] = intent
    strategy._domain.episode = episode
    order_id = "HLTG-SOL-HALF-1"
    strategy._pending_by_order[order_id] = intent
    strategy._sigma_by_order[order_id] = 0.2
    strategy._decision_index_by_order[order_id] = 1490
    assert runtime.record_submission(client_order_id=order_id, intent_id=intent.id, episode_id=episode.id,
                                     action=intent.action, instrument_id=str(HL_SOL.id), quantity="0.01000",
                                     reduce_only=True, strategy_state=strategy.on_save()["wave_overlay_live_recovery_v1"])
    report = SimpleNamespace(
        account_id=AccountId("HYPERLIQUID-master"), client_order_id=ClientOrderId(order_id),
        venue_order_id=VenueOrderId("sol-venue-1"), instrument_id=HL_SOL.id,
        trade_id=TradeId("sol-half-trade"), last_qty=Quantity.from_str("0.01000"),
        last_px=Price.from_str("150.0"), ts_event=1, order_side=OrderSide.SELL,
    )
    order = SimpleNamespace(
        client_order_id=report.client_order_id, venue_order_id=report.venue_order_id,
        instrument_id=HL_SOL.id, account_id=None, strategy_id=str(strategy.id),
        side=OrderSide.SELL, is_closed=True, is_reduce_only=True, trade_ids=[report.trade_id],
        quantity=Quantity.from_str("0.01000"), filled_qty=Quantity.from_str("0.01000"),
    )
    status = SimpleNamespace(
        client_order_id=report.client_order_id, venue_order_id=report.venue_order_id,
        instrument_id=HL_SOL.id, account_id=report.account_id,
        order_side=OrderSide.SELL, filled_qty=order.filled_qty,
        quantity=order.quantity, reduce_only=True,
    )
    position = SimpleNamespace(
        instrument_id=HL_SOL.id, account_id=report.account_id,
        strategy_id=str(strategy.id), quantity=Quantity.from_str("0.01000"), is_long=True,
    )
    reconciler = LiveRecoveryReconciler(runtime, strategy, str(report.account_id))
    reconciler.apply_partial_fills([report], [order], [position], [status], _native_account())
    assert strategy._domain.episode.sol_qty == 0.01
    assert strategy._domain.episode.sol_half_done is True
    assert strategy._domain.episode.sol_half_decision_index == 1490
    assert intent.id not in strategy._domain.episode.pending
    assert order_id not in strategy._pending_by_order
    checkpoint = runtime.strategy_checkpoint()
    assert runtime.has_applied_fill("sol-half-trade")
    restored = RecoverableWaveOverlayStrategy(_strategy().config)
    restored.on_load({"wave_overlay_live_recovery_v1": checkpoint[0]})
    LiveRecoveryReconciler(runtime, restored, str(report.account_id)).apply_partial_fills(
        [report], [order], [position], [status], _native_account(),
    )
    assert restored._domain.episode == strategy._domain.episode
    assert runtime.strategy_checkpoint() == checkpoint
    runtime.close()

@pytest.mark.parametrize(
    "fault",
    ["missing", "foreign", "not_reduce_only", "wrong_account",
     "wrong_direction", "wrong_price", "wrong_type", "wrong_tif", "not_open", "missing_shape"],
)
def test_open_btc_reduce_only_ownership_rejects_uncertain_reports(tmp_path, fault):
    from nautilus_trader.model.enums import OrderSide, OrderStatus, OrderType, TimeInForce
    from nautilus_trader.model.identifiers import ClientOrderId, VenueOrderId
    from nautilus_trader.model.objects import Price, Quantity
    from coinmaster.ops.live_recovery import LiveRecoveryReconciler
    from coinmaster.ops.paper import PaperRuntime

    runtime = PaperRuntime(tmp_path / "open-reduction.sqlite", "live-recovery", 10**20)
    runtime.acquire()
    strategy = RecoverableWaveOverlayStrategy(_strategy().config)
    episode = Episode("episode-open", 1, 10000, 1.2, btc_initial_qty=0.02,
                      btc_open_qty=0.02, btc_entry_vwap=60000)
    intent = Intent("intent-reduce", episode.id, "BTC_REDUCE", 0, -1, quantity=0.01)
    episode.pending[intent.id] = intent
    episode.btc_tps.add(0)
    strategy._domain.episode = episode
    order_id = "HLTG-REDUCE-1"
    strategy._pending_by_order[order_id] = intent
    strategy._decision_index_by_order[order_id] = 1483
    assert runtime.record_submission(
        client_order_id=order_id, intent_id=intent.id, episode_id=episode.id,
        action=intent.action, instrument_id=str(HL_BTC.id), quantity="0.01000",
        reduce_only=True, strategy_state=strategy.on_save()["wave_overlay_live_recovery_v1"],
        order_shape=None if fault == "missing_shape" else {"side": "SELL", "kind": "LIMIT", "tif": "GTC",
                     "post_only": True, "price": "60000.0"},
    )
    account = AccountId("HYPERLIQUID-master")
    order = SimpleNamespace(
        client_order_id=ClientOrderId(order_id), venue_order_id=VenueOrderId("tp-venue-1"),
        instrument_id=HL_BTC.id, account_id=None, strategy_id=str(strategy.id),
        side=OrderSide.SELL, is_closed=False, is_reduce_only=True, is_post_only=True,
        order_type=OrderType.LIMIT, time_in_force=TimeInForce.GTC,
        price=Price.from_str("60000.0"), trade_ids=[],
        quantity=Quantity.from_str("0.01000"), filled_qty=Quantity.from_str("0.00000"),
    )
    status = SimpleNamespace(
        client_order_id=order.client_order_id, venue_order_id=order.venue_order_id,
        instrument_id=HL_BTC.id, account_id=account, order_side=OrderSide.SELL,
        filled_qty=order.filled_qty, quantity=order.quantity, reduce_only=True,
        post_only=True, order_type=OrderType.LIMIT, time_in_force=TimeInForce.GTC,
        price=Price.from_str("60000.0"), order_status=OrderStatus.ACCEPTED,
    )
    position = SimpleNamespace(
        instrument_id=HL_BTC.id, account_id=account, strategy_id=str(strategy.id),
        quantity=Quantity.from_str("0.02000"), is_long=True,
    )
    reconciler = LiveRecoveryReconciler(runtime, strategy, str(account))
    before = runtime.strategy_checkpoint()
    assert before is not None
    if fault != "missing_shape":
        reconciler.apply_partial_fills([], [order], [position], [status], _native_account())
        assert runtime.strategy_checkpoint() == before
    if fault == "missing":
        native_orders, statuses, native_account = [], [], _native_account()
        expected = "RECOVERY_EXPECTED_ORDER_MISSING"
    elif fault == "foreign":
        foreign = SimpleNamespace(**{**vars(order), "client_order_id": ClientOrderId("FOREIGN-ORDER")})
        foreign_status = SimpleNamespace(**{**vars(status), "client_order_id": foreign.client_order_id})
        native_orders, statuses, native_account = [order, foreign], [status, foreign_status], _native_account()
        expected = "RECOVERY_ORDER_OWNERSHIP_MISMATCH"
    elif fault == "not_reduce_only":
        native_orders = [order]
        statuses = [SimpleNamespace(**{**vars(status), "reduce_only": False})]
        native_account = _native_account()
        expected = "RECOVERY_ORDER_OWNERSHIP_MISMATCH"
    elif fault == "wrong_account":
        native_orders, statuses, native_account = [order], [status], _native_account("OTHER-master")
        expected = "RECOVERY_ACCOUNT_IDENTITY_MISMATCH"
    elif fault == "missing_shape":
        native_orders, statuses, native_account = [order], [status], _native_account()
        expected = "RECOVERY_ORDER_SHAPE_MISSING"
    elif fault == "wrong_direction":
        native_orders = [SimpleNamespace(**{**vars(order), "side": OrderSide.BUY})]
        statuses = [SimpleNamespace(**{**vars(status), "order_side": OrderSide.BUY})]
        native_account = _native_account()
        expected = "RECOVERY_ORDER_OWNERSHIP_MISMATCH"
    elif fault == "wrong_price":
        native_orders = [order]
        statuses = [SimpleNamespace(**{**vars(status), "price": Price.from_str("59999.0")})]
        native_account = _native_account()
        expected = "RECOVERY_ORDER_SHAPE_MISMATCH"
    elif fault == "wrong_type":
        native_orders = [SimpleNamespace(**{**vars(order), "order_type": OrderType.MARKET})]
        statuses = [SimpleNamespace(**{**vars(status), "order_type": OrderType.MARKET})]
        native_account = _native_account()
        expected = "RECOVERY_ORDER_SHAPE_MISMATCH"
    elif fault == "wrong_tif":
        native_orders = [SimpleNamespace(**{**vars(order), "time_in_force": TimeInForce.IOC})]
        statuses = [SimpleNamespace(**{**vars(status), "time_in_force": TimeInForce.IOC})]
        native_account = _native_account()
        expected = "RECOVERY_ORDER_SHAPE_MISMATCH"
    else:
        native_orders = [order]
        statuses = [SimpleNamespace(**{**vars(status), "order_status": OrderStatus.CANCELED})]
        native_account = _native_account()
        expected = "RECOVERY_ORDER_SHAPE_MISMATCH"
    with pytest.raises(ValueError, match=expected):
        reconciler.apply_partial_fills([], native_orders, [position], statuses, native_account)
    assert runtime.strategy_checkpoint() == before
    assert strategy.on_save()["wave_overlay_live_recovery_v1"] == before[0]
    assert strategy.recovery_confirmed is False
    runtime.close()

def test_unreported_venue_flat_cannot_clear_open_episode(tmp_path):
    from coinmaster.ops.live_recovery import LiveRecoveryReconciler
    from coinmaster.ops.paper import PaperRuntime

    runtime = PaperRuntime(tmp_path / "venue-flat.sqlite", "live-recovery", 10**20)
    runtime.acquire()
    strategy = RecoverableWaveOverlayStrategy(_strategy().config)
    strategy._domain.episode = Episode(
        "episode-open", 1, 10000, 1.2,
        btc_initial_qty=0.02, btc_open_qty=0.02, btc_entry_vwap=60000,
    )
    state = strategy.on_save()["wave_overlay_live_recovery_v1"]
    assert runtime.commit_applied_fills(["prior-native-fill"], state)
    before = runtime.strategy_checkpoint()
    with pytest.raises(ValueError, match="RECOVERY_EPISODE_POSITION_MISMATCH"):
        LiveRecoveryReconciler(runtime, strategy, "HYPERLIQUID-master").apply_partial_fills(
            [], [], [], [], _native_account(),
        )
    assert runtime.strategy_checkpoint() == before
    assert runtime.has_applied_fill("prior-native-fill")
    assert strategy._domain.episode.btc_open_qty == 0.02
    assert strategy.recovery_confirmed is False
    runtime.close()


@pytest.mark.parametrize("method", [
    "submit_order", "submit_order_list", "modify_order", "cancel_order",
    "cancel_orders", "cancel_all_orders", "close_position", "close_all_positions",
])
def test_recovery_final_order_api_gate_blocks_until_confirmed(monkeypatch, method):
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategy

    strategy = RecoverableWaveOverlayStrategy(_strategy().config)
    with pytest.raises(RuntimeError, match="RECOVERY_NOT_CONFIRMED"):
        getattr(strategy, method)()
    called = []
    marker = object()
    monkeypatch.setattr(
        WaveOverlayStrategy, method,
        lambda self, *args, **kwargs: called.append((args, kwargs)) or marker,
    )
    strategy.recovery_confirmed = True
    assert getattr(strategy, method)("fake") is marker
    assert called == [(("fake",), {})]


def test_async_verifier_return_cannot_confirm_recovery():
    import asyncio

    strategy = RecoverableWaveOverlayStrategy(_strategy().config)

    async def report_only():
        return True

    strategy.attach_post_drain_verifier(report_only)
    asyncio.run(strategy._run_post_drain_verifier())
    assert strategy.recovery_confirmed is False
    with pytest.raises(RuntimeError, match="RECOVERY_VERIFIER_ALREADY_ATTACHED"):
        strategy.attach_post_drain_verifier(report_only)


def test_live_info_scope_requires_selected_account_and_durable_anchor():
    from coinmaster.ops.live_recovery import NativeLiveRecoveryScope

    account = "0x" + "a" * 40
    scope = NativeLiveRecoveryScope(
        account, "", 100, 9,
        (("CM05-ORDER", "0x" + "b" * 32, None),), frozenset({"BTC", "SOL"}),
    )
    assert scope.account_ref == account and scope.anchor_tid == 9
    with pytest.raises(ValueError, match="LIVE_ACCOUNT_REF_REQUIRED"):
        NativeLiveRecoveryScope("", "", 100, None, (), frozenset({"BTC"}))
    with pytest.raises(ValueError, match="LIVE_ANCHOR_WITHOUT_DURABLE_ORDER"):
        NativeLiveRecoveryScope(account, "", 100, 9, (), frozenset({"BTC"}))

def test_failed_post_drain_verifier_never_releases_order_gate():
    import asyncio

    strategy = RecoverableWaveOverlayStrategy(_strategy().config)

    async def fail():
        raise RuntimeError("WS_BUFFER_OVERFLOW")

    strategy.attach_post_drain_verifier(fail)
    with pytest.raises(RuntimeError, match="WS_BUFFER_OVERFLOW"):
        asyncio.run(strategy._run_post_drain_verifier())
    assert strategy.recovery_confirmed is False
    with pytest.raises(RuntimeError, match="RECOVERY_NOT_CONFIRMED"):
        strategy.submit_order()
