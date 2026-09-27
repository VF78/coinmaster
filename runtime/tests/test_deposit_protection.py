from decimal import Decimal
import sqlite3

import pytest

from coinmaster.domain.deposit_protection import DAY_NS, DepositProtection
from coinmaster.ops.paper import PaperRuntime


def test_unknown_is_not_zero_and_trigger_latches_across_durable_reload(tmp_path):
    state = DepositProtection()
    state.initialize(Decimal("100"), DAY_NS + 1)
    changed, triggered = state.observe(None, DAY_NS + 2)
    assert (changed, triggered) == (False, False)
    assert state.projection()["state"] == "EQUITY_UNAVAILABLE"
    changed, triggered = state.observe(Decimal("50"), DAY_NS + 3)
    assert (changed, triggered) == (True, True)
    assert state.projection()["state"] == "EXITING"
    restored = DepositProtection.from_durable(state.durable())
    restored.observe(Decimal("90"), DAY_NS + 4)
    assert restored.latched and restored.threshold == Decimal("50")
    assert restored.projection()["state"] == "EXITING"


def test_utc_high_water_uses_only_fresh_daily_close_and_missed_day_never_fabricates_high():
    state = DepositProtection()
    state.initialize(Decimal("100"), DAY_NS + 1)
    state.observe(Decimal("120"), 2 * DAY_NS - 1_000_000_000)
    state.observe(Decimal("119"), 2 * DAY_NS + 1)
    assert state.high_water == Decimal("120")
    assert state.last_boundary_ns == 2 * DAY_NS
    assert not state.daily_sample_missed
    state.observe(Decimal("130"), 3 * DAY_NS - 121_000_000_000)
    state.observe(Decimal("129"), 3 * DAY_NS + 1)
    assert state.high_water == Decimal("120")
    assert state.daily_sample_missed


def test_default_half_drawdown_uses_initial_or_confirmed_daily_high():
    initial = DepositProtection()
    initial.initialize(Decimal("100"), DAY_NS + 1)
    assert initial.threshold == Decimal("50")
    assert initial.observe(Decimal("50.01"), DAY_NS + 2) == (False, False)
    assert initial.observe(Decimal("50"), DAY_NS + 3) == (True, True)
    assert initial.trigger["high_water_equity"] == "100"
    assert initial.trigger["threshold_equity"] == "50"

    daily_high = DepositProtection()
    daily_high.initialize(Decimal("100"), DAY_NS + 1)
    daily_high.observe(Decimal("110"), 2 * DAY_NS - 1)
    assert daily_high.high_water == Decimal("100")
    daily_high.observe(Decimal("109"), 2 * DAY_NS + 1)
    assert daily_high.high_water == Decimal("110")
    assert daily_high.threshold == Decimal("55")
    assert daily_high.observe(Decimal("55.01"), 2 * DAY_NS + 2) == (False, False)
    assert daily_high.observe(Decimal("55"), 2 * DAY_NS + 3) == (True, True)
    assert daily_high.trigger["high_water_equity"] == "110"
    assert daily_high.trigger["threshold_equity"] == "55"


def test_true_zero_triggers_and_percent_bounds():
    state = DepositProtection(limit_percent=50)
    state.initialize(Decimal("100"), DAY_NS + 1)
    assert state.observe(Decimal("0"), DAY_NS + 2) == (True, True)
    for bad in (0, 100, 50.0, True):
        with pytest.raises(ValueError, match="DEPOSIT_PERCENT_INVALID"):
            DepositProtection(limit_percent=bad)


def test_sqlite_account_instance_binding_and_idempotent_audit(tmp_path):
    runtime = PaperRuntime(tmp_path / "paper.sqlite", "dp-owner", 10**20)
    runtime.acquire()
    state = DepositProtection()
    state.initialize(Decimal("100"), DAY_NS + 1)
    assert runtime.save_deposit_protection(
        instance_id="stage-g-a", account_id="HYPERLIQUID-001", action="INITIALIZE",
        event_key="deposit:init:one", state=state.durable(), ts_ns=DAY_NS + 1,
    )
    assert not runtime.save_deposit_protection(
        instance_id="stage-g-a", account_id="HYPERLIQUID-001", action="INITIALIZE",
        event_key="deposit:init:one", state=state.durable(), ts_ns=DAY_NS + 1,
    )
    assert runtime.deposit_protection_state(
        instance_id="stage-g-a", account_id="HYPERLIQUID-001",
    ) == state.durable()
    with pytest.raises(ValueError, match="DEPOSIT_ACCOUNT_IDENTITY_MISMATCH"):
        runtime.deposit_protection_state(
            instance_id="stage-g-b", account_id="HYPERLIQUID-001",
        )
    with pytest.raises(ValueError, match="DEPOSIT_IDEMPOTENCY_CONFLICT"):
        runtime.save_deposit_protection(
            instance_id="stage-g-a", account_id="HYPERLIQUID-001", action="RESET",
            event_key="deposit:init:one", state=state.durable(), ts_ns=DAY_NS + 2,
        )
    with pytest.raises(ValueError, match="DEPOSIT_ACCOUNT_IDENTITY_MISMATCH"):
        runtime.save_deposit_protection(
            instance_id="stage-g-a", account_id="HYPERLIQUID-OTHER", action="RESET",
            event_key="deposit:reset:one", state=state.durable(), ts_ns=DAY_NS + 2,
        )


def test_verified_flat_pause_and_deposit_state_commit_atomically(tmp_path):
    runtime = PaperRuntime(tmp_path / "paper.sqlite", "dp-owner", 10**20)
    runtime.acquire()
    try:
        state = DepositProtection()
        state.initialize(Decimal("100"), DAY_NS + 1)
        runtime.save_deposit_protection(
            instance_id="stage-g-a", account_id="HYPERLIQUID-001", action="INITIALIZE",
            event_key="deposit:init:one", state=state.durable(), ts_ns=DAY_NS + 1,
        )
        state.observe(Decimal("50"), DAY_NS + 2)
        runtime.save_deposit_protection(
            instance_id="stage-g-a", account_id="HYPERLIQUID-001", action="TRIGGER",
            event_key="deposit:trigger:one", state=state.durable(), ts_ns=DAY_NS + 2,
        )
        assert runtime.entry_control_state() == "RUNNING"
        state.exit_state = "TRIPPED_FLAT"
        kwargs = dict(
            instance_id="stage-g-a", account_id="HYPERLIQUID-001", action="TRIPPED_FLAT",
            event_key="deposit:exit:one", state=state.durable(), ts_ns=DAY_NS + 3,
            pause_on_flat=True,
        )
        runtime.db.execute("""
            CREATE TRIGGER reject_deposit_pause BEFORE INSERT ON paper_command_audit
            WHEN NEW.command='pause-new-entries'
            BEGIN SELECT RAISE(ABORT, 'TEST_PAUSE_WRITE_FAILED'); END
        """)
        with pytest.raises(sqlite3.DatabaseError, match="TEST_PAUSE_WRITE_FAILED"):
            runtime.save_deposit_protection(**kwargs)
        assert runtime.entry_control_state() == "RUNNING"
        assert runtime.deposit_protection_state(
            instance_id="stage-g-a", account_id="HYPERLIQUID-001",
        )["exit_state"] == "EXITING"
        assert runtime.deposit_audit_action("deposit:exit:one") is None
        runtime.db.execute("DROP TRIGGER reject_deposit_pause")
        assert runtime.save_deposit_protection(**kwargs)
        assert not runtime.save_deposit_protection(**kwargs)
        assert runtime.entry_control_state() == "PAUSED"
        assert runtime.db.execute(
            "SELECT COUNT(*) FROM paper_command_audit WHERE command='pause-new-entries'"
        ).fetchone()[0] == 1
    finally:
        runtime.close()
