"""Real SQLite/checkpoint ownership boundary; native parity remains separate."""
import json
from decimal import Decimal

import pytest

from coinmaster.domain.deposit_protection import DepositProtection
from coinmaster.domain.wave_overlay import Episode, Intent
from coinmaster.ops.hl_live_epoch import LiveEpochRuntime
from coinmaster.ops.paper import PaperRuntime
from coinmaster.strategy.live_recovery import RecoverableWaveOverlayStrategy, _KEY
from test_live_native_report_recovery import _strategy


def settled(tmp_path, balance="82"):
    runtime = LiveEpochRuntime(tmp_path / "live.sqlite", "hl-stageg-live", 10**20, require_native_cash=True)
    runtime.acquire()
    strategy = RecoverableWaveOverlayStrategy(_strategy().config)
    protection = DepositProtection()
    protection.initialize(Decimal("82"), 86400000000000)
    runtime.save_deposit_protection(
        instance_id=runtime.owner, account_id="HYPERLIQUID-master", action="INITIALIZED",
        event_key="original82", state=protection.durable(), ts_ns=86400000000000)
    runtime.record_submission(client_order_id="OWNED-1", intent_id="intent", episode_id="episode",
        action="BTC_ENTRY", instrument_id=str(strategy.config.btc_id), quantity=".001", reduce_only=False,
        strategy_state=strategy.on_save()[_KEY])
    runtime.terminal_submission("OWNED-1", strategy.on_save()[_KEY])
    runtime.snapshot(ts_ns=1, positions=[], orders=[], funding_event_ids=[], reconciled=True,
        native_account_total=balance, strategy_restartable=True, run_epoch="old")
    runtime._local_sandbox_active = False
    return runtime, strategy


@pytest.mark.parametrize("balance", ("82", "91.227", "65.04"))
def test_profit_loss_epoch_keeps_full_audit_and_original_protection(tmp_path, balance):
    runtime, strategy = settled(tmp_path, balance)
    try:
        old_checkpoint = PaperRuntime.strategy_checkpoint(runtime)
        old_protection = runtime.deposit_protection_state(instance_id=runtime.owner, account_id="HYPERLIQUID-master")
        assert runtime.prepare_flat_epoch(release_commit="new") == Decimal(balance)
        assert not runtime.all_submissions() and runtime.strategy_checkpoint() is None
        assert len(PaperRuntime.all_submissions(runtime)) == 1
        assert PaperRuntime.strategy_checkpoint(runtime) == old_checkpoint
        assert runtime.deposit_protection_state(instance_id=runtime.owner, account_id="HYPERLIQUID-master") == old_protection
        assert old_protection["high_water_equity"] == "82"
        assert len(runtime.db.execute("SELECT kind FROM paper_events").fetchall()) == 1
        strategy._domain._decision_index += 1
        assert runtime.persist_strategy_checkpoint(strategy.on_save()[_KEY], runtime.native_revision())
        assert runtime.strategy_checkpoint() is not None
    finally:
        runtime.close()


@pytest.mark.parametrize("fault", ("unknown_ack", "open", "revision", "foreign_fill", "unresolved", "missing_anchor"))
def test_epoch_rejects_uncertainty_and_never_erases_audit(tmp_path, fault):
    runtime, strategy = settled(tmp_path)
    try:
        if fault == "unknown_ack":
            runtime.record_submission(client_order_id="UNKNOWN", intent_id="i2", episode_id="e2",
                action="BTC_ENTRY", instrument_id=str(strategy.config.btc_id), quantity=".001", reduce_only=False)
        elif fault == "open":
            runtime.snapshot(ts_ns=2, positions=[{"quantity":"1"}], orders=[], funding_event_ids=[],
                native_account_total="82", strategy_restartable=True)
        elif fault == "revision":
            runtime._bump_native_revision(); runtime.db.commit()
        elif fault == "foreign_fill":
            runtime.db.execute("INSERT INTO paper_recovered_fills VALUES ('unknown')"); runtime.db.commit()
        elif fault == "unresolved":
            strategy._queued_intents.append((Intent("i", "e", "BTC_ENTRY", 0, 1, quantity=.01), None, 0))
            runtime.persist_strategy_checkpoint(strategy.on_save()[_KEY], runtime.native_revision())
        elif fault == "missing_anchor":
            runtime.db.execute("DELETE FROM paper_deposit_protection"); runtime.db.commit()
        with pytest.raises(RuntimeError, match="LIVE_FLAT_HISTORY"):
            runtime.prepare_flat_epoch(release_commit="new")
        assert len(PaperRuntime.all_submissions(runtime)) >= 1
    finally:
        runtime.close()


def test_selective_decision_reduction_checkpoint_roundtrip(tmp_path):
    source = RecoverableWaveOverlayStrategy(_strategy().config)
    intent = Intent("i", "e", "BTC_REDUCE", 1, -1, quantity=.001)
    source._deferred_selective_entries["e"] = {"quantity": Decimal(".001"), "index": 14}
    source._selected_entry_audits["e"] = {"source": "owned"}
    source._accepted_reductions[("e", "BTC_REDUCE", 1)] = (intent, Decimal(".0005"))
    source._mandatory_sol_retry_after_ns = 44
    source._deferred_entry_session = 123
    restored = RecoverableWaveOverlayStrategy(_strategy().config)
    restored.on_load(source.on_save())
    for field in ("_deferred_selective_entries", "_selected_entry_audits", "_accepted_reductions",
                  "_mandatory_sol_retry_after_ns", "_deferred_entry_session"):
        assert getattr(restored, field) == getattr(source, field)
    assert not restored.recovery_confirmed
