"""Isolated mainnet composition. No Sandbox account or automatic restart takeover."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import threading
import time
import uuid
from decimal import Decimal
from pathlib import Path

from nautilus_trader.adapters.bybit import BybitLiveDataClientFactory
from nautilus_trader.adapters.hyperliquid import HyperliquidLiveDataClientFactory
from nautilus_trader.adapters.hyperliquid.config import HyperliquidExecClientConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.enums import TimeInForce
from nautilus_trader.model.identifiers import ClientId

from coinmaster.ops.hl_live_credential_preflight import check_live_credential, _read_json
from coinmaster.ops.hl_live_execution import ScopedHyperliquidExecClientFactory
from coinmaster.ops.hyperliquid_testnet import (
    BTC_PERP, SOL_PERP, TESTNET_IDS, LifecycleHooks, HyperliquidTestnetNode,
    cross_venue_stage_g_gate, hyperliquid_testnet_node_config, load_stageg_warmup_bundle,
)
from coinmaster.ops.hyperliquid_testnet_worker import TestnetWorker, create_status_server
from coinmaster.ops.live_recovery import NativeLiveRecoveryScope, LiveRecoverySubmissionSink
from coinmaster.ops.native_paper_node import BYBIT_IDS, FeedBook, FeedObserver, FeedObserverConfig, bybit_daily_bar_type
from coinmaster.ops.paper import PaperRuntime
from coinmaster.ops.stage_g_config import load_candidate, load_testnet_instance_config
from coinmaster.strategy.live_recovery import RecoverableWaveOverlayStrategy
from coinmaster.strategy.wave_overlay import WaveOverlayStrategyConfig
from coinmaster.venues.marks import venue_mark_data_type

SEALED_V0_SHA = "0edecde9548533004292d5a6174ef6aeb77596817080c4a160f72aa2dc7dd511"


def require_live_order_approval(path: Path, fingerprint_path: Path, release_root: Path) -> None:
    """Owner must approve this exact immutable release and selected account separately."""
    try:
        approval = json.loads(path.read_text())
        fingerprint = json.loads(fingerprint_path.read_text())
        identity = json.loads((release_root / "live-release.json").read_text())
        if (approval.get("schema") != "coinmaster-live-order-approval-v1"
                or approval.get("instance_id") != "hl-stageg-live"
                or approval.get("orders_approved") is not True
                or approval.get("pilot_capital_usdc") != "100"
                or approval.get("release_commit") != identity["source_commit"]
                or approval.get("master_address_sha256") != fingerprint["master_address_sha256"]
                or approval.get("strategy_sha256") != SEALED_V0_SHA):
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise RuntimeError("LIVE_OWNER_ORDER_APPROVAL_REQUIRED") from None


class LiveSubmissionHooks(LifecycleHooks):
    def __init__(self, runtime):
        super().__init__(runtime)
        self.strategy = None

    def __call__(self, **request):
        if self.strategy is None:
            raise RuntimeError("LIVE_STRATEGY_NOT_BOUND")
        return LiveRecoverySubmissionSink(
            self.runtime, self.strategy, frozenset(map(str, TESTNET_IDS)),
        )(**request)


class HyperliquidLiveNode:
    # Reuse only public feature/warmup, native cache projection and lifecycle helpers.
    _refresh_warmup_readiness = HyperliquidTestnetNode._refresh_warmup_readiness
    native_snapshot = HyperliquidTestnetNode.sandbox_snapshot
    strategy_restartable = HyperliquidTestnetNode.strategy_restartable
    start = HyperliquidTestnetNode.start
    stop = HyperliquidTestnetNode.stop

    def __init__(self, *, instance, candidate, state, credential_path, fingerprint_path):
        if instance.mode != "live" or instance.instance_id != "hl-stageg-live":
            raise RuntimeError("LIVE_INSTANCE_REQUIRED")
        self.instance, self.candidate, self.state = instance, candidate, state
        self.profile_root = Path(__file__).resolve().parents[2]
        source = self.profile_root / "coinmaster/strategy/wave_overlay.py"
        if hashlib.sha256(source.read_bytes()).hexdigest() != SEALED_V0_SHA:
            raise RuntimeError("LIVE_SEALED_V0_SOURCE_MISMATCH")
        # Qualification never implies order authorization: main checks approval before this read.
        equity = check_live_credential(credential_path, fingerprint_path)
        if equity != Decimal("100"):
            raise RuntimeError("LIVE_PILOT_REQUIRES_EXACT_100_USDC")
        record = _read_json(credential_path)
        self.master = record["master_address"]
        self.gate = cross_venue_stage_g_gate(
            candidate=candidate, warmup_manifest=instance.signal_warmup_manifest,
            strategy_path=source, profile_root=self.profile_root,
        )
        self.candidate_hash = self.gate.candidate_hash
        self.warmup_bundle, self.warmup_state = load_stageg_warmup_bundle(instance.signal_warmup_manifest)
        if self.warmup_bundle is None or not self.gate.attachable:
            raise RuntimeError("LIVE_WARMUP_OR_SEAL_NOT_READY")
        self._warmup_verified_day = time.time_ns() // 86_400_000_000_000
        self._warmup_verified_target = instance.signal_warmup_manifest.resolve()
        self._warmup_checked_at_ns = time.time_ns()
        self.hooks = LiveSubmissionHooks(state)
        self.feed = FeedBook(ids=TESTNET_IDS, native_event_sink=self.hooks.record_event)
        self.loop = asyncio.new_event_loop()
        self.config = hyperliquid_testnet_node_config(trader_id=instance.trader_id, execution_mode="live")
        execution = self.config.exec_clients["HYPERLIQUID-LIVE"]
        self.config.exec_clients["HYPERLIQUID-LIVE"] = HyperliquidExecClientConfig(
            instrument_provider=execution.instrument_provider, routing=execution.routing,
            environment=execution.environment, private_key=record["agent_private_key"],
            account_address=self.master, vault_address=None, include_builder_attribution=False,
        )
        del record
        self.strategy = RecoverableWaveOverlayStrategy(WaveOverlayStrategyConfig(
            strategy_id=instance.strategy_id, order_id_tag=instance.order_id_tag,
            btc_id=BTC_PERP, sol_id=SOL_PERP,
            btc_bar_type=bybit_daily_bar_type(BYBIT_IDS[0]), sol_bar_type=bybit_daily_bar_type(BYBIT_IDS[1]),
            btc_mark_data_type=venue_mark_data_type(BTC_PERP), sol_mark_data_type=venue_mark_data_type(SOL_PERP),
            mark_client_id=ClientId("HYPERLIQUID-MAINNET-DATA"), live_mark_client_id=ClientId("HYPERLIQUID-MAINNET-DATA"),
            active_seed=Decimal("100"), candidate=candidate, seed_bars=self.warmup_bundle.bars,
            max_mark_age_ns=120_000_000_000, entries_gate=self._entries_enabled,
            event_sink=self.hooks.record_event, native_fill_sink=state.record_native_fill, submission_sink=self.hooks,
            btc_signal_id=BYBIT_IDS[0], sol_signal_id=BYBIT_IDS[1],
            execution_policy_hash="hl-mainnet-native-owned-v1", execution_policy_version="hl-mainnet-native-owned-v1",
            market_exit_time_in_force=TimeInForce.IOC, market_exit_reduce_only=True,
            deposit_runtime=state, deposit_instance_id=instance.instance_id, deposit_account_id="HYPERLIQUID-master",
            deposit_equity_reader=lambda strategy: strategy._validated_live_money().equity,
            deposit_initialization_allowed=lambda: self.strategy.recovery_confirmed and not state.all_submissions(),
        ))
        self.hooks.strategy = self.strategy
        scope = NativeLiveRecoveryScope(self.master, "", time.time_ns() // 1_000_000, None, (), frozenset({"BTC", "SOL"}))
        factory = ScopedHyperliquidExecClientFactory.bind(scope, state, self.strategy, account_lock_root=Path("/run/coinmaster-hl-live"))
        self.node = TradingNode(config=self.config, loop=self.loop)
        self.node.add_data_client_factory("BYBIT", BybitLiveDataClientFactory)
        self.node.add_data_client_factory("HYPERLIQUID", HyperliquidLiveDataClientFactory)
        self.node.add_exec_client_factory("HYPERLIQUID", factory)
        self.node.build()
        self.feed_observer = FeedObserver(FeedObserverConfig(
            instrument_ids=TESTNET_IDS, client_ids=(ClientId("HYPERLIQUID-MAINNET-DATA"),) * 2, feed=self.feed,
        ))
        self.node.trader.add_strategy(self.feed_observer)
        self.node.trader.add_strategy(self.strategy)
        self._thread = None
        self.prime_error = None

    def _entries_enabled(self):
        try:
            self._refresh_warmup_readiness()
            self.strategy._validated_live_money()
            return (self.state.entry_control_state() != "PAUSED" and self.gate.attachable
                    and self.node.is_running() and self.strategy.recovery_confirmed
                    and self.strategy.deposit_projection()["state"] == "ARMED"
                    and self.state.health(time.time_ns()).safe_for_increase
                    and all(row["state"] == "READY" for row in self.feed.status(time.time_ns()).values()))
        except Exception:
            return False

    def status(self):
        return {"instance_id": self.instance.instance_id, "mode": "live", "environment": "mainnet",
                "state": "PUBLIC_FEEDS_READY" if self._entries_enabled() else "RECOVERY_REQUIRED/PAUSED",
                "orders_enabled": self._entries_enabled(), "live_order_capability": True,
                "recovery_required": not self.strategy.recovery_confirmed,
                "recovery_capability": "MANUAL_CLEAN_FLAT_ONLY", "feeds": self.feed.status(time.time_ns()),
                "warmup": {"state": self.warmup_state, "rows": self.warmup_bundle.rows},
                "prime_error": self.prime_error,
                "signal_seal": {"state": self.gate.approval_state, "strategy_sha256": self.gate.strategy_code_hash},
                "margin_policy": "NATIVE_SELECTED_ACCOUNT_CROSS_MARGIN",
                "accounting": "NATIVE_ACCOUNT_AND_CONFIRMED_INFO_NO_MODEL_FX"}


class LiveWorker:
    deposit_control = TestnetWorker.deposit_control

    def __init__(self, environment=None):
        environment = os.environ if environment is None else environment
        self.instance = load_testnet_instance_config(Path(environment["COINMASTER_HL_LIVE_INSTANCE_CONFIG"]))
        root = Path(__file__).resolve().parents[2]
        fingerprints = root / "configs/hl-stageg-live.account-fingerprint.json"
        require_live_order_approval(Path(environment.get("COINMASTER_LIVE_ORDER_APPROVAL", "/etc/coinmaster/live-order-approval.json")), fingerprints, root)
        self.candidate = load_candidate(self.instance.strategy_config)
        self.run_epoch = uuid.uuid4().hex
        self.control_available = bool(environment.get("COINMASTER_HL_STAGEG_CONTROL_TOKEN"))
        self._warmup_thread = None
        self._warmup_refresh_after = 0
        self.runtime = PaperRuntime(self.instance.state_db, self.instance.instance_id, int(120e9), require_native_cash=True)
        self.runtime.acquire()
        self.recovery_marker = self.instance.state_db.parent / "manual-recovery-required"
        try:
            if self.recovery_marker.exists():
                raise RuntimeError("LIVE_RESTART_MANUAL_RECOVERY_REQUIRED")
            # Even a flat native cache cannot erase a previous episode or ambiguous result.
            if (self.runtime.all_submissions() or self.runtime.strategy_checkpoint()
                    or self.runtime.recovery_state() != "FLAT_RESTART"):
                raise RuntimeError("LIVE_RESTART_MANUAL_RECOVERY_REQUIRED")
            self.native = HyperliquidLiveNode(
                instance=self.instance, candidate=self.candidate.candidate, state=self.runtime,
                credential_path=Path(environment["CREDENTIALS_DIRECTORY"]) / "connection.json", fingerprint_path=fingerprints,
            )
        except BaseException:
            self.runtime.close()
            raise

    def refresh_warmup(self):
        if time.monotonic() < self._warmup_refresh_after or (self._warmup_thread and self._warmup_thread.is_alive()):
            return
        self._warmup_refresh_after = time.monotonic() + 900
        def refresh():
            from coinmaster.ops.stage_g_refresh import refresh_stageg_warmup
            try:
                refresh_stageg_warmup(self.instance.signal_warmup_manifest.parent.parent)
            except Exception:
                # The native admission gate keeps stale/invalid history closed.
                pass
        self._warmup_thread = threading.Thread(target=refresh, name="hl-live-public-warmup", daemon=True)
        self._warmup_thread.start()

    def start(self):
        self.native.start()

    def poll(self):
        self.runtime.heartbeat(time.time_ns())
        if not self.native.strategy.recovery_confirmed:
            return
        try:
            money = self.native.strategy._validated_live_money()
            revision = self.runtime.native_revision()
            if money.native_revision != revision:
                self.native.loop.call_soon_threadsafe(self.native.strategy._request_live_refresh)
                return
            positions, orders = self.native.native_snapshot()
            committed = self.runtime.snapshot(ts_ns=time.time_ns(), positions=positions, orders=orders,
                                  funding_event_ids=self.runtime.funding_event_ids(), reconciled=True,
                                  expected_revision=revision, native_account_total=str(money.raw_usd),
                                  strategy_restartable=self.native.strategy_restartable(), run_epoch=self.run_epoch)
            if not committed:
                self.native.loop.call_soon_threadsafe(self.native.strategy._request_live_refresh)
                return
            self.runtime.record_native_equity_observation(run_epoch=self.run_epoch, observed_at_ns=time.time_ns(), equity_usdc=str(money.equity))
        except ValueError as error:
            if str(error) == "LIVE_MONEY_STALE_OR_UNKNOWN":
                self.native.loop.call_soon_threadsafe(self.native.strategy._request_live_refresh)
                return
            self._manual_recovery()
        except Exception:
            self._manual_recovery()

    def _manual_recovery(self):
        self.native.strategy.recovery_confirmed = False
        for client in self.native.node.kernel.exec_engine._clients.values():
            fail = getattr(client, "_cm_fail", None)
            if callable(fail):
                fail("LIVE_WORKER_SNAPSHOT_FAILED")
        # Minimal process/restart latch, deliberately no automatic clearing.
        with self.recovery_marker.open("w") as stream:
            stream.write("LIVE_WORKER_SNAPSHOT_FAILED\n")
            stream.flush()
            os.fsync(stream.fileno())
        directory = os.open(self.recovery_marker.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def projection(self):
        self.poll()
        status = self.native.status()
        positions, orders = self.native.native_snapshot()
        events, cursor = self.runtime.projection_events(100)
        account = {}
        if self.native.strategy.recovery_confirmed:
            try:
                money = self.native.strategy._validated_live_money()
                account = {"equity": str(money.equity), "native_cash": str(money.raw_usd),
                           "withdrawable": str(money.free_collateral), "margin_used": str(money.margin_used)}
            except ValueError as error:
                if str(error) != "LIVE_MONEY_STALE_OR_UNKNOWN":
                    raise
                self.native.loop.call_soon_threadsafe(self.native.strategy._request_live_refresh)
                status["state"] = "LIVE_MONEY_STALE/PAUSED"
                status["orders_enabled"] = False
        return {**status, "version": "hl-stageg-live-projection-v1", "run_epoch": self.run_epoch,
                "account": account, "account_state": "CURRENT" if account else "UNAVAILABLE", "positions": positions, "orders": orders, "events": events, "event_cursor": cursor,
                "deposit_protection": self.native.strategy.deposit_projection(),
                "entry_control": {"state": self.runtime.entry_control_state(), "capability": "READY" if self.control_available else "UNAVAILABLE"},
                "provenance": "NATIVE_MAINNET_OWNED_ACCOUNT"}

    def close(self):
        if self.native.stop():
            self.runtime.close()


def main():
    worker = LiveWorker()
    server = create_status_server(worker, int(os.getenv("COINMASTER_HL_STAGEG_STATUS_PORT", "18185")), os.getenv("COINMASTER_HL_STAGEG_CONTROL_TOKEN"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    try:
        worker.start()
        while not stopped.wait(5):
            worker.refresh_warmup()
            worker.poll()
    finally:
        server.shutdown()
        server.server_close()
        worker.close()


if __name__ == "__main__":
    main()
