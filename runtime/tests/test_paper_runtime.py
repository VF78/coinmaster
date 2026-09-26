import pytest
from decimal import Decimal
from coinmaster.ops.paper import PaperRuntime


def test_paper_runtime_is_wal_durable_idempotent_and_fail_closed(tmp_path) -> None:
    path = tmp_path / "paper.sqlite"
    first = PaperRuntime(path, "owner-a", 10)
    first.acquire()
    assert first.health(0).safe_for_increase is False
    first.snapshot(ts_ns=5, positions=[], orders=[], funding_event_ids=["f1"])
    assert first.command("pause-new-entries", "pause-1") is True
    assert first.command("pause-new-entries", "pause-1") is False
    assert first.record_native_event("native-order-1", "order") is True
    assert first.record_native_event("native-fill-1", "fill") is True
    assert first.record_native_event("native-funding-1", "funding") is True
    assert first.health(10).safe_for_increase is False
    first.close()
    reopened = PaperRuntime(path, "owner-b", 10)
    assert reopened.record_native_event("native-order-1", "order") is False
    assert reopened.record_native_event("native-fill-1", "fill") is False
    assert reopened.record_native_event("native-funding-1", "funding") is False
    assert reopened.health(16).warnings == ("STALE_DATA", "RECOVERY_REQUIRED_UNSNAPSHOTTED_NATIVE_STATE")
    with pytest.raises(RuntimeError, match="PAPER_OWNER_LOCKED"): reopened.acquire()
    reopened.close()


def test_modelled_funding_is_signed_idempotent_and_restart_safe(tmp_path) -> None:
    path = tmp_path / "paper.sqlite"
    runtime = PaperRuntime(path, "owner-a", 100)
    runtime.acquire()
    # Positive funding charges a long and credits an equal short.
    assert runtime.funding_cash_delta(Decimal("2"), Decimal("100"), Decimal("0.01")) == Decimal("-2.00")
    assert runtime.funding_cash_delta(Decimal("-2"), Decimal("100"), Decimal("0.01")) == Decimal("2.00")
    assert runtime.record_modelled_funding(event_id="bybit:BTC:200", instrument_id="BTC", settlement_ns=200, rate=Decimal("0.01"), mark=Decimal("100"), signed_quantity=Decimal("2"))
    assert not runtime.record_modelled_funding(event_id="bybit:BTC:200", instrument_id="BTC", settlement_ns=200, rate=Decimal("0.01"), mark=Decimal("100"), signed_quantity=Decimal("2"))
    runtime.snapshot(ts_ns=10, positions=[], orders=[], funding_event_ids=runtime.funding_event_ids())
    runtime.close()
    restarted = PaperRuntime(path, "owner-a", 100)
    assert restarted.funding_event_ids() == ["bybit:BTC:200"]
    assert restarted.reconcile(positions=[], orders=[])
    assert not restarted.reconcile(positions=[{"instrument_id": "BTC", "signed_quantity": "1"}], orders=[])
    restarted.close()


def test_native_funding_prepare_blocks_restart_until_native_post_is_completed(tmp_path) -> None:
    path = tmp_path / "native-funding.sqlite"
    runtime = PaperRuntime(path, "native-funding", 10)
    runtime.acquire()
    accepted, delta = runtime.prepare_native_funding(
        event_id="hyperliquid:mainnet:BTC:1", instrument_id="BTC", settlement_ns=1,
        rate=Decimal("0.01"), mark=Decimal("100"), signed_quantity=Decimal("2"),
    )
    assert accepted and delta == Decimal("-2.00")
    runtime.close()
    restarted = PaperRuntime(path, "native-funding", 10); restarted.acquire()
    assert restarted.recovery_state() == "MANAGE_ONLY_PENDING_NATIVE_FUNDING"
    restarted.complete_native_funding("hyperliquid:mainnet:BTC:1")
    assert restarted.pending_native_funding() == []
    restarted.close()


def test_pause_resume_and_flatten_command_audit_are_idempotent(tmp_path) -> None:
    runtime = PaperRuntime(tmp_path / "paper.sqlite", "owner", 100)
    runtime.acquire(); runtime.snapshot(ts_ns=1, positions=[], orders=[], funding_event_ids=[])
    assert runtime.command("pause-new-entries", "pause")
    assert runtime.health(2).paused_new_entries
    assert runtime.command("resume-new-entries", "resume")
    assert not runtime.health(2).paused_new_entries
    assert runtime.command("flatten-paper", "flat")
    assert runtime.health(2).flatten_requested
    assert not runtime.command("flatten-paper", "flat")
    runtime.close()


def test_command_rejects_unknown_action_without_consuming_idempotency_key(tmp_path) -> None:
    runtime = PaperRuntime(tmp_path / "paper.sqlite", "owner", 100)
    runtime.acquire()
    with pytest.raises(ValueError, match="unsupported paper command"):
        runtime.command("live-order", "key")
    assert runtime.command("pause-new-entries", "key")
    runtime.close()


def test_open_sandbox_group_after_crash_enters_manage_only_without_reenabling_risk(tmp_path) -> None:
    """Sandbox has no supported process-to-process group restoration."""
    path = tmp_path / "paper.sqlite"
    open_group_positions = [{"instrument_id": "BTCUSDT-LINEAR.BYBIT", "signed_quantity": "1.000"}]
    open_group_orders = [{"client_order_id": "SANDBOX-OPEN-GROUP-ENTRY-1"}]
    submitted = PaperRuntime(path, "paper", 1_000)
    submitted.acquire()
    submitted.snapshot(ts_ns=100, positions=open_group_positions, orders=open_group_orders, funding_event_ids=[])
    assert submitted.record_submission(
        client_order_id="SANDBOX-OPEN-GROUP-ENTRY-1", intent_id="intent-1", episode_id="episode-1",
        action="BTC_ENTRY", instrument_id="BTCUSDT-LINEAR.BYBIT", quantity="1.000", reduce_only=False,
    )
    # Deliberately no order ACK: crash after submit, before callback.
    submitted.close()

    restarted = PaperRuntime(path, "paper", 1_000)
    restarted.acquire()
    assert restarted.recovery_state() == "MANAGE_ONLY_PENDING_INTENT"
    assert not restarted.reconcile(positions=open_group_positions, orders=open_group_orders)
    restarted.heartbeat(101)
    assert restarted.health(101).safe_for_increase is False
    assert restarted.health(101).warnings == ("MANAGE_ONLY_PENDING_INTENT", "SANDBOX_RECONCILIATION_MISMATCH", "UNRECONCILED_ORDERS")
    assert not restarted.record_submission(
        client_order_id="SANDBOX-OPEN-GROUP-ENTRY-1", intent_id="intent-1", episode_id="episode-1",
        action="BTC_ENTRY", instrument_id="BTCUSDT-LINEAR.BYBIT", quantity="1.000", reduce_only=False,
    )
    restarted.close()


def test_current_reconciled_owned_btc_tp_orders_do_not_block_increases(tmp_path) -> None:
    runtime = PaperRuntime(tmp_path / "owned-tp.sqlite", "stageg", 1_000)
    runtime.acquire()
    assert runtime.record_submission(
        client_order_id="tp-2", intent_id="intent-2", episode_id="episode-1",
        action="BTC_REDUCE", instrument_id="BTC-USD-PERP.HYPERLIQUID", quantity="0.10000",
        reduce_only=True,
    )
    runtime.acknowledge_submission("tp-2")
    assert runtime.snapshot(
        ts_ns=1,
        positions=[{"instrument_id": "BTC-USD-PERP.HYPERLIQUID", "signed_quantity": "0.50000"}],
        orders=[{
            "client_order_id": "tp-2", "instrument_id": "BTC-USD-PERP.HYPERLIQUID",
            "reduce_only": True,
        }],
        funding_event_ids=[],
    )
    assert runtime.recovery_state() == "ACTIVE_OWNED_REDUCTIONS"
    assert runtime.health(2).safe_for_increase
    accepted, _ = runtime.prepare_native_funding(
        event_id="funding-1", instrument_id="BTC", settlement_ns=2,
        rate=Decimal("0.01"), mark=Decimal("100"), signed_quantity=Decimal("1"),
    )
    assert accepted
    assert runtime.recovery_state() == "MANAGE_ONLY_PENDING_NATIVE_FUNDING"
    assert not runtime.health(2).safe_for_increase
    runtime.close()


def test_unknown_or_restarted_open_order_remains_fail_closed(tmp_path) -> None:
    path = tmp_path / "unknown-tp.sqlite"
    runtime = PaperRuntime(path, "stageg", 1_000)
    runtime.acquire()
    runtime.snapshot(
        ts_ns=1, positions=[],
        orders=[{"client_order_id": "foreign", "instrument_id": "BTC-USD-PERP.HYPERLIQUID", "reduce_only": True}],
        funding_event_ids=[],
    )
    assert not runtime.health(2).safe_for_increase
    assert "UNRECONCILED_ORDERS" in runtime.health(2).warnings
    runtime.close()
    restarted = PaperRuntime(path, "stageg", 1_000)
    restarted.acquire()
    assert restarted.recovery_state() == "MANAGE_ONLY_DURABLE_OPEN_STATE"
    assert not restarted.health(2).safe_for_increase
    restarted.close()


def test_flat_restart_is_the_only_automatic_reconciliation_path(tmp_path) -> None:
    runtime = PaperRuntime(tmp_path / "paper.sqlite", "paper", 1_000)
    runtime.acquire(); runtime.snapshot(ts_ns=1, positions=[], orders=[], funding_event_ids=[]); runtime.close()
    restarted = PaperRuntime(tmp_path / "paper.sqlite", "paper", 1_000)
    restarted.acquire()
    assert restarted.recovery_state() == "FLAT_RESTART"
    assert restarted.reconcile(positions=[], orders=[])
    restarted.close()


def test_terminal_fill_before_native_snapshot_cannot_reopen_flat(tmp_path) -> None:
    path = tmp_path / "terminal-crash.sqlite"
    first = PaperRuntime(path, "stageg", 10**20, require_native_cash=True)
    first.acquire()
    first.snapshot(ts_ns=1, positions=[], orders=[], funding_event_ids=[], native_account_total="10000", strategy_restartable=True)
    assert first.record_submission(client_order_id="entry-1", intent_id="i-1", episode_id="e-1", action="BTC_ENTRY", instrument_id="BTC", quantity="0.01", reduce_only=False)
    first.terminal_submission("entry-1")
    first.close()
    restarted = PaperRuntime(path, "stageg", 10**20, require_native_cash=True)
    assert restarted.recovery_state() == "RECOVERY_REQUIRED_UNSNAPSHOTTED_NATIVE_STATE"
    assert restarted.flat_native_cash() is None
    assert not restarted.health(2).safe_for_increase
    restarted.close()


def test_verified_flat_native_cash_handoff_preserves_exact_decimal(tmp_path) -> None:
    path = tmp_path / "cash.sqlite"
    first = PaperRuntime(path, "stageg", 10**20, require_native_cash=True)
    first.acquire()
    first.record_native_event("fill-1", "fill")
    revision = first.native_revision()
    assert first.snapshot(ts_ns=1, positions=[], orders=[], funding_event_ids=[],
                          expected_revision=revision, native_account_total="9999.987654321",
                          strategy_restartable=True, run_epoch="first")
    assert first.coherent_snapshot()
    first.close()
    restarted = PaperRuntime(path, "stageg", 10**20, require_native_cash=True)
    assert restarted.recovery_state() == "FLAT_RESTART"
    assert restarted.flat_native_cash() == Decimal("9999.987654321")
    restarted.acquire()
    restarted.record_native_event("fill-2", "fill")
    assert not restarted.coherent_snapshot()
    assert restarted.recovery_state() == "RECOVERY_REQUIRED_UNSNAPSHOTTED_NATIVE_STATE"
    revision = restarted.native_revision()
    assert restarted.snapshot(ts_ns=2, positions=[], orders=[], funding_event_ids=[],
                              expected_revision=revision, native_account_total="9999.975308642",
                              strategy_restartable=True, run_epoch="second")
    restarted.close()
    third = PaperRuntime(path, "stageg", 10**20, require_native_cash=True)
    assert third.flat_native_cash() == Decimal("9999.975308642")
    third.close()


def test_flat_cash_handoff_blocks_unrestored_episode_and_revision_race(tmp_path) -> None:
    path = tmp_path / "episode.sqlite"
    first = PaperRuntime(path, "stageg", 10**20, require_native_cash=True)
    first.acquire()
    first.record_native_event("fill-1", "fill")
    revision = first.native_revision()
    first.record_native_event("fill-2", "fill")
    assert not first.snapshot(ts_ns=1, positions=[], orders=[], funding_event_ids=[],
                              expected_revision=revision, native_account_total="9999",
                              strategy_restartable=True)
    assert first.recovery_state() == "RECOVERY_REQUIRED_UNSNAPSHOTTED_NATIVE_STATE"
    assert first.snapshot(ts_ns=2, positions=[], orders=[], funding_event_ids=[],
                          expected_revision=first.native_revision(), native_account_total="9999",
                          strategy_restartable=False)
    first.close()
    restarted = PaperRuntime(path, "stageg", 10**20, require_native_cash=True)
    assert restarted.recovery_state() == "RECOVERY_REQUIRED_STRATEGY_STATE"
    assert restarted.flat_native_cash() is None
    restarted.close()


def test_current_native_process_can_continue_after_event_until_next_snapshot(tmp_path) -> None:
    runtime = PaperRuntime(tmp_path / "active.sqlite", "stageg", 10**20, require_native_cash=True)
    runtime.acquire()
    runtime.snapshot(ts_ns=1, positions=[], orders=[], funding_event_ids=[],
                     native_account_total="10000", strategy_restartable=True)
    runtime.record_native_event("fill-1", "fill")
    assert runtime.recovery_state() == "FLAT_RESTART"
    assert not runtime.coherent_snapshot()
    assert runtime.health(2).safe_for_increase
    runtime.close()
    restarted = PaperRuntime(tmp_path / "active.sqlite", "stageg", 10**20, require_native_cash=True)
    assert restarted.recovery_state() == "RECOVERY_REQUIRED_UNSNAPSHOTTED_NATIVE_STATE"
    restarted.close()

def test_process_lifetime_lock_rejects_second_owner_process(tmp_path) -> None:
    import subprocess
    import sys

    path = tmp_path / "single-owner.sqlite"
    first = PaperRuntime(path, "same-account", 10)
    first.acquire()
    child = (
        "import sys; from pathlib import Path; from coinmaster.ops.paper import PaperRuntime; "
        "p=PaperRuntime(Path(sys.argv[1]), 'same-account', 10); "
        "\ntry: p.acquire(); print('ACQUIRED')"
        "\nexcept RuntimeError as error: print(str(error))"
        "\nfinally: p.close()"
    )
    blocked = subprocess.run([sys.executable, "-c", child, str(path)], capture_output=True, text=True, check=True)
    assert blocked.stdout.strip() == "PAPER_PROCESS_LOCKED"
    first.close()
    resumed = subprocess.run([sys.executable, "-c", child, str(path)], capture_output=True, text=True, check=True)
    assert resumed.stdout.strip() == "ACQUIRED"
