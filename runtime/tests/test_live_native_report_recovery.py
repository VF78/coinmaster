"""Isolated native reconciliation proof with a fake venue and real Redis cache.

Run with COINMASTER_TEST_REDIS_PORT pointing to a disposable loopback Redis.
No Hyperliquid client, credential, or network execution factory is constructed.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from nautilus_trader.common import Environment
from nautilus_trader.common.providers import InstrumentProvider
from nautilus_trader.config import CacheConfig, DatabaseConfig, LiveExecClientConfig, LoggingConfig
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.execution.reports import FillReport, OrderStatusReport, PositionStatusReport
from nautilus_trader.live.config import LiveExecEngineConfig, RoutingConfig, TradingNodeConfig
from nautilus_trader.live.execution_client import LiveExecutionClient
from nautilus_trader.live.factories import LiveExecClientFactory
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.data import BarSpecification, BarType
from nautilus_trader.model.enums import (
    AccountType, AggregationSource, BarAggregation, LiquiditySide, OmsType,
    OrderSide, OrderStatus, OrderType, PositionSide, PriceType, TimeInForce,
)
from nautilus_trader.model.identifiers import AccountId, ClientId, ClientOrderId, InstrumentId, TradeId, Venue, VenueOrderId
from nautilus_trader.model.objects import AccountBalance, Money, Price, Quantity

from coinmaster.ops.paper import PaperRuntime
from coinmaster.ops.live_recovery import LiveRecoverySubmissionSink, LiveRecoveryReconciler
from coinmaster.domain.wave_overlay import Episode, Intent
from coinmaster.strategy.wave_overlay import WaveOverlayStrategyConfig
from coinmaster.strategy.live_recovery import RecoverableWaveOverlayStrategy
from coinmaster.venues.marks import venue_mark_data_type
from test_hl_stageg_sandbox_lifecycle import HL_BTC, HL_SOL


ACCOUNT = AccountId("HYPERLIQUID-master")
CLIENT_ORDER = ClientOrderId("HLTG-RESTART-PROBE-1")
VENUE_ORDER = VenueOrderId("venue-1")


class FakeReportClient(LiveExecutionClient):
    """Report-only transport: submits are recorded and rejected by the test."""

    def __init__(self, loop, msgbus, cache, clock):
        super().__init__(
            loop=loop, client_id=ClientId("HYPERLIQUID"), venue=Venue("HYPERLIQUID"),
            oms_type=OmsType.NETTING, account_type=AccountType.MARGIN,
            base_currency=USDC, instrument_provider=InstrumentProvider(),
            msgbus=msgbus, cache=cache, clock=clock,
        )
        self._set_account_id(ACCOUNT)
        self._fake_venue_state = json.loads(Path(os.environ["CM_FAKE_VENUE_STATE"]).read_text())

    async def _connect(self):
        total = Decimal("9999.73") if self._fake_venue_state["partial"] else Decimal("10000")
        self.generate_account_state(
            [AccountBalance(Money(total, USDC), Money(0, USDC), Money(total, USDC))],
            [], True, self._clock.timestamp_ns(),
        )

    async def _disconnect(self):
        pass

    async def _submit_order(self, command):
        Path(os.environ["CM_FAKE_SUBMIT_LOG"]).write_text(str(command.order.client_order_id))
        raise AssertionError("unexpected submit during recovery")

    async def generate_order_status_reports(self, command):
        if not self._fake_venue_state["partial"]:
            return []
        now = self._clock.timestamp_ns()
        return [OrderStatusReport(
            ACCOUNT, HL_BTC.id, VENUE_ORDER, OrderSide.BUY, OrderType.LIMIT,
            TimeInForce.GTC, OrderStatus.PARTIALLY_FILLED,
            Quantity.from_str("0.02000"), Quantity.from_str("0.01000"),
            UUID4(), now, now, now, client_order_id=CLIENT_ORDER,
            price=Price.from_str("60000.0"),
        )]

    async def generate_fill_reports(self, command):
        if not self._fake_venue_state["partial"] or self._fake_venue_state.get("omit_fill"):
            return []
        now = self._clock.timestamp_ns()
        return [FillReport(
            ACCOUNT, HL_BTC.id, VENUE_ORDER, TradeId("trade-1"),
            OrderSide.BUY, Quantity.from_str("0.01000"), Price.from_str("60000.0"),
            Money(Decimal("0.27"), USDC), LiquiditySide.TAKER,
            UUID4(), now, now, client_order_id=CLIENT_ORDER,
        )]

    async def generate_position_status_reports(self, command):
        if not self._fake_venue_state["partial"]:
            return []
        now = self._clock.timestamp_ns()
        return [PositionStatusReport(
            ACCOUNT, HL_BTC.id, PositionSide.LONG, Quantity.from_str("0.01000"),
            UUID4(), now, now,
        )]


class FakeReportFactory(LiveExecClientFactory):
    @staticmethod
    def create(loop, name, config, msgbus, cache, clock):
        return FakeReportClient(loop, msgbus, cache, clock)


class RecoveryProbeStrategy(RecoverableWaveOverlayStrategy):
    """The exact decision/submit implementation, without public subscriptions."""

    def on_start(self):
        pass


def _strategy():
    btc = BarType(
        InstrumentId.from_str("BTCUSDT-LINEAR.BYBIT"),
        BarSpecification(1, BarAggregation.DAY, PriceType.LAST),
        AggregationSource.EXTERNAL,
    )
    sol = BarType(
        InstrumentId.from_str("SOLUSDT-LINEAR.BYBIT"),
        BarSpecification(1, BarAggregation.DAY, PriceType.LAST),
        AggregationSource.EXTERNAL,
    )
    return RecoveryProbeStrategy(WaveOverlayStrategyConfig(
        strategy_id="stage-g-recovery-probe", order_id_tag="HLTG",
        external_order_claims=[HL_BTC.id, HL_SOL.id],
        btc_id=HL_BTC.id, sol_id=HL_SOL.id, btc_bar_type=btc, sol_bar_type=sol,
        btc_mark_data_type=venue_mark_data_type(HL_BTC.id),
        sol_mark_data_type=venue_mark_data_type(HL_SOL.id),
        mark_client_id=ClientId("HYPERLIQUID"),
        active_seed=Decimal("10000"), entries_enabled=False,
    ))


async def _run_child():
    port = int(os.environ["COINMASTER_TEST_REDIS_PORT"])
    config = TradingNodeConfig(
        environment=Environment.LIVE,
        trader_id=os.environ["CM_FAKE_TRADER_ID"],
        cache=CacheConfig(database=DatabaseConfig(host="127.0.0.1", port=port), flush_on_start=False),
        load_state=True, save_state=True,
        logging=LoggingConfig(log_level="ERROR"),
        exec_engine=LiveExecEngineConfig(
            reconciliation=True, reconciliation_startup_delay_secs=0.0,
            snapshot_orders=True, snapshot_positions=True,
            filter_unclaimed_external_orders=True,
        ),
        exec_clients={"FAKE": LiveExecClientConfig(
            routing=RoutingConfig(venues=frozenset({"HYPERLIQUID"})),
        )},
    )
    node = TradingNode(config=config, loop=asyncio.get_running_loop())
    node.add_exec_client_factory("FAKE", FakeReportFactory)
    node.build()
    node.cache.add_instrument(HL_BTC)
    node.cache.add_instrument(HL_SOL)
    strategy = _strategy()
    journal = os.environ.get("CM_FAKE_JOURNAL")
    if journal:
        previous = PaperRuntime(Path(journal), "live-recovery-probe", 10**20)
        checkpoint = previous.strategy_checkpoint()
        previous.close()
        if checkpoint:
            strategy.on_load({"wave_overlay_live_recovery_v1": checkpoint[0]})
    node.trader.add_strategy(strategy)
    await node.kernel.start_async()
    if journal and json.loads(Path(os.environ["CM_FAKE_VENUE_STATE"]).read_text())["partial"]:
        client = next(item for item in node.kernel.exec_engine._clients.values() if isinstance(item, FakeReportClient))
        reports = await client.generate_fill_reports(None)
        active = PaperRuntime(Path(journal), "live-recovery-probe", 10**20)
        active.acquire()
        LiveRecoveryReconciler(active, strategy, str(ACCOUNT)).apply_partial_fills(
            reports, node.cache.orders_open(), node.cache.positions_open(),
        )
        active.close()
    episode = strategy._domain.episode
    result = {
        "running": node.is_running(),
        "orders": [(str(o.client_order_id), str(o.quantity), str(o.filled_qty)) for o in node.cache.orders_open()],
        "positions": [(str(p.instrument_id), str(p.quantity)) for p in node.cache.positions_open()],
        "fills": len(node.trader.generate_order_fills_report()),
        "episode_btc_open_qty": episode.btc_open_qty if episode else None,
        "episode_pending": sorted(episode.pending) if episode else None,
        "native_total_usdc": str(node.cache.account_for_venue(Venue("HYPERLIQUID")).balance_total(USDC).as_decimal()),
    }
    print("RECOVERY_PROOF=" + json.dumps(result), flush=True)
    if os.environ.get("CM_FAKE_CRASH") == "1":
        os._exit(137)
    await node.kernel.stop_async()
    node.kernel.dispose()


def test_crash_before_ack_then_native_partial_report_recovers_once(tmp_path):
    port = os.environ.get("COINMASTER_TEST_REDIS_PORT")
    if not port:
        pytest.skip("requires disposable loopback Redis >=6.2")
    state = tmp_path / "fake-venue.json"
    submit_log = tmp_path / "submits.txt"
    journal = tmp_path / "intents.sqlite"
    state.write_text('{"partial": false}')
    environment = dict(os.environ, CM_FAKE_VENUE_STATE=str(state), CM_FAKE_SUBMIT_LOG=str(submit_log), CM_FAKE_JOURNAL=str(journal))
    environment["PYTHONPATH"] = os.pathsep.join((str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)))
    environment["CM_FAKE_TRADER_ID"] = "HL-RECOVERY-" + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:8].upper()
    first = PaperRuntime(journal, "live-recovery-probe", 10**20)
    first.acquire()
    first.snapshot(ts_ns=__import__("time").time_ns(), positions=[], orders=[], funding_event_ids=[])
    strategy = _strategy()
    episode = Episode("episode-1", 1, 10000, 1.2)
    intent = Intent("intent-1", "episode-1", "BTC_ENTRY", None, 1, quantity=0.02)
    episode.pending[intent.id] = intent
    strategy._domain.episode = episode
    strategy._pending_by_order[str(CLIENT_ORDER)] = intent
    strategy._sigma_by_order[str(CLIENT_ORDER)] = None
    strategy._decision_index_by_order[str(CLIENT_ORDER)] = 1483
    sink = LiveRecoverySubmissionSink(first, strategy, frozenset({str(HL_BTC.id)}))
    assert sink(client_order_id=str(CLIENT_ORDER), intent_id=intent.id, episode_id=episode.id,
                action="BTC_ENTRY", instrument_id=str(HL_BTC.id), quantity="0.02000", reduce_only=False)
    first.close()
    environment["CM_FAKE_CRASH"] = "1"
    crashed = subprocess.run([sys.executable, __file__, "--child"], env=environment, capture_output=True, text=True, timeout=45)
    assert crashed.returncode == 137, crashed.stderr
    state.write_text('{"partial": true}')
    environment.pop("CM_FAKE_CRASH")
    observations = []
    for _ in range(2):
        run = subprocess.run([sys.executable, __file__, "--child"], env=environment, capture_output=True, text=True, timeout=45)
        assert run.returncode == 0, run.stderr
        observations.append(json.loads(next(line.split("=", 1)[1] for line in run.stdout.splitlines() if line.startswith("RECOVERY_PROOF="))))
    assert observations == [observations[0], observations[0]]
    assert observations[0]["running"]
    assert observations[0]["orders"] == [[str(CLIENT_ORDER), "0.02000", "0.01000"]]
    assert observations[0]["positions"] == [[str(HL_BTC.id), "0.01000"]]
    assert observations[0]["fills"] == 1
    assert observations[0]["episode_btc_open_qty"] == 0.01, observations
    assert observations[0]["episode_pending"] == ["intent-1"]
    assert observations[0]["native_total_usdc"] == "9999.73"
    assert not submit_log.exists()
    reopened = PaperRuntime(journal, "live-recovery-probe", 10**20)
    assert reopened.recovery_state() == "MANAGE_ONLY_PENDING_INTENT"
    assert reopened.has_recovered_fill("trade-1")
    persisted = reopened.strategy_checkpoint()
    recovered = _strategy()
    recovered.on_load({"wave_overlay_live_recovery_v1": persisted[0]})
    assert recovered._domain.episode.btc_open_qty == 0.01
    reopened.close()


if __name__ == "__main__" and "--child" in sys.argv:
    asyncio.run(_run_child())
