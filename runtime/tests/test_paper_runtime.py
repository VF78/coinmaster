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
    assert reopened.health(16).warnings == ("STALE_DATA",)
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


def test_flat_restart_is_the_only_automatic_reconciliation_path(tmp_path) -> None:
    runtime = PaperRuntime(tmp_path / "paper.sqlite", "paper", 1_000)
    runtime.acquire(); runtime.snapshot(ts_ns=1, positions=[], orders=[], funding_event_ids=[]); runtime.close()
    restarted = PaperRuntime(tmp_path / "paper.sqlite", "paper", 1_000)
    restarted.acquire()
    assert restarted.recovery_state() == "FLAT_RESTART"
    assert restarted.reconcile(positions=[], orders=[])
    restarted.close()
