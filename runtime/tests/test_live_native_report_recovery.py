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
from types import SimpleNamespace
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
from nautilus_trader.model.identifiers import AccountId, ClientId, ClientOrderId, InstrumentId, PositionId, TradeId, TraderId, Venue, VenueOrderId
from nautilus_trader.model.objects import AccountBalance, Money, Price, Quantity
from nautilus_trader.model.events import OrderAccepted, OrderFilled
from nautilus_trader.model.orders import MarketOrder
from nautilus_trader.model.position import Position

from coinmaster.ops.paper import PaperRuntime
from coinmaster.ops.live_recovery import LiveRecoverySubmissionSink, LiveRecoveryReconciler
from coinmaster.domain.wave_overlay import Episode, Intent
from coinmaster.strategy.wave_overlay import WaveOverlayStrategyConfig
from coinmaster.strategy.live_recovery import RecoverableWaveOverlayStrategy
from coinmaster.venues.marks import venue_mark_data_type
from test_hl_stageg_sandbox_lifecycle import HL_BTC, HL_SOL


ACCOUNT = AccountId("HYPERLIQUID-master")
CLIENT_ORDER = ClientOrderId("HLTG-RESTART-PROBE-1")
VENUE_ORDER = VenueOrderId("7")


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
        log = Path(os.environ["CM_FAKE_SUBMIT_LOG"])
        with log.open("a") as stream:
            stream.write(str(command.order.client_order_id) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        if os.environ.get("CM_FAKE_ACCEPT_CRASH") != "1":
            raise AssertionError("unexpected submit during recovery")
        path = Path(os.environ["CM_FAKE_VENUE_STATE"])
        state = json.loads(path.read_text())
        if state.get("partial"):
            raise AssertionError("duplicate fake venue submit")
        state.update(partial=True, accepted_order=str(command.order.client_order_id))
        temporary = path.with_suffix(".accepted")
        with temporary.open("w") as stream:
            json.dump(state, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.environ.get("CM_FAKE_ACCEPT_LIVE") == "1":
            order = command.order
            now = self._clock.timestamp_ns()
            self.generate_order_accepted(order.strategy_id, order.instrument_id, order.client_order_id, VENUE_ORDER, now)
            self.generate_order_filled(
                order.strategy_id, order.instrument_id, order.client_order_id,
                VENUE_ORDER, None, TradeId("trade-1"), OrderSide.BUY, OrderType.LIMIT,
                Quantity.from_str("0.01000"), Price.from_str("60000.0"),
                USDC, Money(Decimal("0.27"), USDC), LiquiditySide.TAKER, now,
            )
            total = Money(Decimal("9999.73"), USDC)
            self.generate_account_state([AccountBalance(total, Money(0, USDC), total)], [], True, now)
            return
        os._exit(137)  # Abrupt process exit after fake acceptance, before native ACK.

    async def generate_mass_status(self, lookback_mins=None):
        if os.environ.get("CM_FAKE_RAW_CONVERTER") != "1":
            return await super().generate_mass_status(lookback_mins)
        from nautilus_trader.core import nautilus_pyo3
        from coinmaster.ops.hl_info_receipt import collect_info_receipt
        from coinmaster.ops.hl_qualified_reports import qualified_mass_status

        client = self._fake_venue_state.get("accepted_order", str(CLIENT_ORDER))
        cloid = str(nautilus_pyo3.hyperliquid_cloid_from_client_order_id(
            nautilus_pyo3.ClientOrderId(client)
        ))
        native_orders = self._cache.orders(venue=self.venue)
        assert len(native_orders) == 1
        cached = native_orders[0]
        order_ms = cached.ts_init // 1_000_000
        journal = os.environ.get("CM_FAKE_JOURNAL")
        if journal:
            durable = PaperRuntime(Path(journal), "live-recovery-probe", 10**20)
            applied = durable.applied_fill_ids()
            durable.close()
        else:
            applied = frozenset()
        native_fills = [
            event for event in cached.events if hasattr(event, "trade_id")
            and str(event.trade_id) in applied
        ]
        if applied:
            assert len(native_fills) == len(applied)
            anchor_event = max(native_fills, key=lambda event: (event.ts_event, int(str(event.trade_id))))
            fill_ms = anchor_event.ts_event // 1_000_000
            anchor_tid = int(str(anchor_event.trade_id))
        else:
            fill_ms = max(order_ms + 1, self._clock.timestamp_ns() // 1_000_000 - 1)
            anchor_tid = None
        market_ioc = os.environ.get("CM_FAKE_MARKET_IOC") == "1"
        order = {
            "coin": "BTC", "oid": 7, "cloid": cloid,
            "side": "B", "origSz": "0.02000", "sz": "0.01000",
            "reduceOnly": False, "orderType": "Limit",
            "tif": "Ioc" if market_ioc else "Gtc",
            "limitPx": "60300.0" if market_ioc else "60000.0",
            "timestamp": order_ms,
        }
        data = {
            "frontendOpenOrders": [] if market_ioc else [order],
            "clearinghouseState": {
                "assetPositions": [{"position": {
                    "coin": "BTC", "szi": "0.01000", "entryPx": "60000.0",
                }}],
                "marginSummary": {
                    "accountValue": "9999.73", "totalRawUsd": "10000",
                    "totalMarginUsed": "100", "totalNtlPos": "600",
                },
                "withdrawable": "9900",
            },
            "orderStatus": {
                "status": "order", "order": {
                    "order": order, "status": "canceled" if market_ioc else "open",
                    "statusTimestamp": fill_ms,
                },
            },
            "userFillsByTime": [{
                "coin": "BTC", "oid": 7, "tid": anchor_tid or 1, "time": fill_ms,
                "side": "B",
                "sz": "0.00500" if os.environ.get("CM_FAKE_TWO_FILLS") == "1" else "0.01000",
                "px": "60000.0",
                "fee": "0.135" if os.environ.get("CM_FAKE_TWO_FILLS") == "1" else "0.27",
                "feeToken": "USDC", "hash": "0xfake",
                "crossed": True,
            }],
        }

        async def info(body):
            value = data[body["type"]]
            if body["type"] == "userFillsByTime":
                return [x for x in value if body["startTime"] <= x["time"] <= body["endTime"]]
            return value

        async def collect(end_ms):
            return await collect_info_receipt(
                info, account="0x" + "a" * 40, dex="",
                anchor_ms=fill_ms if anchor_tid is not None else order_ms,
                anchor_tid=anchor_tid, end_ms=end_ms,
                expected_orders={cloid: None}, owned_coins=frozenset({"BTC", "SOL"}),
            )

        first = await collect(fill_ms + 1)
        second = await collect(fill_ms + 2)
        return qualified_mass_status(
            first, second, expected_account_ref="0x" + "a" * 40, expected_dex="",
            account_id=ACCOUNT, client_id=self.id, venue=self.venue,
            instruments={"BTC": HL_BTC, "SOL": HL_SOL},
            durable_orders={client: (cloid, None)}, native_orders=native_orders,
            applied_trade_ids=applied, ts_init=self._clock.timestamp_ns(),
        )

    async def generate_order_status_reports(self, command):
        if not self._fake_venue_state["partial"]:
            return []
        now = self._clock.timestamp_ns()
        client_order = ClientOrderId(self._fake_venue_state.get("accepted_order", str(CLIENT_ORDER)))
        return [OrderStatusReport(
            ACCOUNT, HL_BTC.id, VENUE_ORDER, OrderSide.BUY, OrderType.LIMIT,
            TimeInForce.GTC, OrderStatus.PARTIALLY_FILLED,
            Quantity.from_str("0.02000"), Quantity.from_str("0.01000"),
            UUID4(), now, now, now, client_order_id=client_order,
            price=Price.from_str("60000.0"),
        )]

    async def generate_fill_reports(self, command):
        if not self._fake_venue_state["partial"] or self._fake_venue_state.get("omit_fill"):
            return []
        now = self._clock.timestamp_ns()
        client_order = ClientOrderId(self._fake_venue_state.get("accepted_order", str(CLIENT_ORDER)))
        if os.environ.get("CM_FAKE_TWO_FILLS") == "1":
            return [
                FillReport(
                    ACCOUNT, HL_BTC.id, VENUE_ORDER, TradeId(str(tid)),
                    OrderSide.BUY, Quantity.from_str("0.00500"), Price.from_str("60000.0"),
                    Money(Decimal("0.135"), USDC), LiquiditySide.TAKER,
                    UUID4(), now - (9 - tid) * 1_000_000, now,
                    client_order_id=client_order,
                )
                for tid in (8, 9)
            ]
        return [FillReport(
            ACCOUNT, HL_BTC.id, VENUE_ORDER,
            TradeId(
                "9" if os.environ.get("CM_FAKE_NUMERIC_FILL") == "1"
                else "1" if os.environ.get("CM_FAKE_RAW_CONVERTER") == "1"
                else "trade-1"
            ),
            OrderSide.BUY, Quantity.from_str("0.01000"), Price.from_str("60000.0"),
            Money(Decimal("0.27"), USDC), LiquiditySide.TAKER,
            UUID4(), now, now, client_order_id=client_order,
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
        if os.environ.get("CM_FAKE_HANDOVER_PROBE") == "1":
            self._on_start_reconciled = self._probe_engine._startup_reconciliation_event.is_set()
            return super().on_start()


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
    if os.environ.get("CM_FAKE_HANDOVER_PROBE") == "1":
        from coinmaster.ops.hl_info_receipt import collect_info_receipt
        from coinmaster.ops.hl_qualified_reports import qualified_mass_status

        strategy._probe_engine = node.kernel.exec_engine
        gate = asyncio.Event()
        strategy._probe_release = gate

        async def verified_clean_flat():
            strategy._probe_verifier_started = True
            await gate.wait()
            account_ref = "0x" + "a" * 40
            data = {
                "frontendOpenOrders": [],
                "clearinghouseState": {
                    "assetPositions": [],
                    "marginSummary": {
                        "accountValue": "10000", "totalRawUsd": "10000",
                        "totalMarginUsed": "0", "totalNtlPos": "0",
                    },
                    "withdrawable": "10000",
                },
                "userFillsByTime": [],
            }

            async def info(body):
                return data[body["type"]]

            async def sweep(end_ms):
                return await collect_info_receipt(
                    info, account=account_ref, dex="", anchor_ms=1,
                    anchor_tid=None, end_ms=end_ms, expected_orders={},
                    owned_coins=frozenset({"BTC", "SOL"}),
                )

            first, second = await sweep(2), await sweep(3)
            mass = qualified_mass_status(
                first, second, expected_account_ref=account_ref, expected_dex="",
                account_id=ACCOUNT, client_id=ClientId("HYPERLIQUID"),
                venue=Venue("HYPERLIQUID"),
                instruments={"BTC": HL_BTC, "SOL": HL_SOL},
                durable_orders={}, native_orders=node.cache.orders(venue=Venue("HYPERLIQUID")),
                applied_trade_ids=frozenset(), ts_init=node.kernel.clock.timestamp_ns(),
            )
            native_account = node.cache.account_for_venue(Venue("HYPERLIQUID"))
            if (
                mass.order_reports or mass.fill_reports or mass.position_reports
                or node.cache.positions_open() or strategy._domain.episode is not None
                or native_account is None
                or native_account.balance_total(USDC).as_decimal() != Decimal("10000")
            ):
                raise RuntimeError("FAKE_POST_DRAIN_PARITY_FAILED")
            strategy.recovery_confirmed = True

        strategy.attach_post_drain_verifier(verified_clean_flat)
    node.trader.add_strategy(strategy)
    await node.kernel.start_async()
    if os.environ.get("CM_FAKE_HANDOVER_PROBE") == "1":
        assert strategy._on_start_reconciled is True
        assert strategy.recovery_confirmed is False
        with pytest.raises(RuntimeError, match="RECOVERY_NOT_CONFIRMED"):
            strategy.cancel_all_orders()
        await asyncio.sleep(0)
        assert strategy._probe_verifier_started is True
        strategy._probe_release.set()
        await strategy._post_drain_task
        print("HANDOVER_PROOF=" + json.dumps({
            "on_start_after_reconcile": strategy._on_start_reconciled,
            "blocked_before_parity": True,
            "confirmed_after_parity": strategy.recovery_confirmed,
        }), flush=True)
        await node.kernel.stop_async()
        node.kernel.dispose()
        return
    if os.environ.get("CM_FAKE_EXIT_RECONCILE") == "1":
        from nautilus_trader.core import nautilus_pyo3
        from coinmaster.ops.hl_info_receipt import collect_info_receipt
        from coinmaster.ops.hl_qualified_reports import qualified_mass_status
        from test_hl_info_receipt import FakeInfo

        now = node.kernel.clock.timestamp_ns()
        trader = TraderId(str(node.trader.id))
        strategy_id = strategy.id
        position_id = PositionId("CM05-EXIT-POS")
        entry = OrderFilled(
            trader, strategy_id, HL_BTC.id, ClientOrderId("CM05-SEED"),
            VenueOrderId("6"), ACCOUNT, TradeId("seed"), position_id,
            OrderSide.BUY, OrderType.MARKET, Quantity.from_str("0.01000"),
            Price.from_str("60000.0"), USDC, Money(Decimal("0.27"), USDC),
            LiquiditySide.TAKER, UUID4(), now - 2_000_000, now - 2_000_000,
        )
        node.cache.add_position(Position(HL_BTC, entry), OmsType.NETTING)
        exit_order = MarketOrder(
            trader, strategy_id, HL_BTC.id, CLIENT_ORDER, OrderSide.SELL,
            Quantity.from_str("0.01000"), UUID4(), now - 1_000_000,
            time_in_force=TimeInForce.IOC, reduce_only=True,
        )
        exit_order.apply(OrderAccepted(
            trader, strategy_id, HL_BTC.id, CLIENT_ORDER, VENUE_ORDER, ACCOUNT,
            UUID4(), now - 1_000_000, now - 1_000_000,
        ))
        node.cache.add_order(exit_order, position_id=position_id, client_id=ClientId("HYPERLIQUID"))
        cloid = str(nautilus_pyo3.hyperliquid_cloid_from_client_order_id(
            nautilus_pyo3.ClientOrderId(str(CLIENT_ORDER))
        ))
        order_ms = exit_order.ts_init // 1_000_000
        fill_ms = order_ms + 1
        row = {
            "coin": "BTC", "oid": 7, "cloid": cloid,
            "side": "A", "origSz": "0.01000", "sz": "0",
            "reduceOnly": True, "orderType": "Limit", "tif": "Ioc",
            "limitPx": "59700.0", "timestamp": order_ms,
        }
        data = {
            "frontendOpenOrders": [],
            "clearinghouseState": {
                "assetPositions": [],
                "marginSummary": {
                    "accountValue": "9999.73", "totalRawUsd": "10000",
                    "totalMarginUsed": "0", "totalNtlPos": "0",
                },
                "withdrawable": "9999.73",
            },
            "orderStatus": {"status": "order", "order": {
                "order": row, "status": "filled", "statusTimestamp": fill_ms,
            }},
            "userFillsByTime": [{
                "coin": "BTC", "oid": 7, "tid": 9, "time": fill_ms,
                "side": "A", "sz": "0.01000", "px": "60000.0",
                "fee": "0.27", "feeToken": "USDC", "hash": "0xexit",
                "crossed": True,
            }],
        }
        async def info(body):
            value = data[body["type"]]
            if body["type"] == "userFillsByTime":
                return [item for item in value if body["startTime"] <= item["time"] <= body["endTime"]]
            return value
        async def sweep(end_ms):
            return await collect_info_receipt(
                info, account="0x" + "a" * 40, dex="", anchor_ms=order_ms,
                anchor_tid=None, end_ms=end_ms, expected_orders={cloid: 7},
                owned_coins=frozenset({"BTC", "SOL"}),
            )
        mass = qualified_mass_status(
            await sweep(fill_ms + 1), await sweep(fill_ms + 2),
            expected_account_ref="0x" + "a" * 40, expected_dex="",
            account_id=ACCOUNT, client_id=ClientId("HYPERLIQUID"),
            venue=Venue("HYPERLIQUID"), instruments={"BTC": HL_BTC, "SOL": HL_SOL},
            durable_orders={str(CLIENT_ORDER): (cloid, 7)},
            native_orders=[exit_order], applied_trade_ids=frozenset(),
            ts_init=node.kernel.clock.timestamp_ns(),
        )
        applied = node.kernel.exec_engine._reconcile_execution_mass_status(mass)
        print("EXIT_PROOF=" + json.dumps({
            "applied": applied,
            "order_type": next(iter(mass.order_reports.values())).order_type.name,
            "positions_open": [
                (str(p.instrument_id), str(p.quantity)) for p in node.cache.positions_open()
            ],
            "order_filled_qty": str(node.cache.order(CLIENT_ORDER).filled_qty),
        }), flush=True)
        await node.kernel.stop_async()
        node.kernel.dispose()
        return
    if os.environ.get("CM_FAKE_SUBMIT") == "1":
        # This branch models a prior healthy fake session, not recovery startup.
        strategy.recovery_confirmed = True
        assert journal
        active = PaperRuntime(Path(journal), "live-recovery-probe", 10**20)
        active.acquire()
        active.snapshot(ts_ns=node.kernel.clock.timestamp_ns(), positions=[], orders=[], funding_event_ids=[])
        episode = Episode("episode-accepted", 1, 10000, 1.2)
        intent = Intent("intent-accepted", episode.id, "BTC_ENTRY", None, 1, quantity=0.02)
        episode.pending[intent.id] = intent
        strategy._domain.episode = episode
        if os.environ.get("CM_FAKE_MARKET_IOC") == "1":
            order = strategy.order_factory.market(
                instrument_id=HL_BTC.id, order_side=OrderSide.BUY,
                quantity=Quantity.from_str("0.02000"), time_in_force=TimeInForce.IOC,
            )
        else:
            order = strategy.order_factory.limit(
                instrument_id=HL_BTC.id, order_side=OrderSide.BUY,
                quantity=Quantity.from_str("0.02000"), price=Price.from_str("60000.0"),
                time_in_force=TimeInForce.GTC,
            )
        order_id = str(order.client_order_id)
        strategy._pending_by_order[order_id] = intent
        strategy._sigma_by_order[order_id] = None
        strategy._decision_index_by_order[order_id] = 1483
        assert LiveRecoverySubmissionSink(active, strategy, frozenset({str(HL_BTC.id)}))(
            client_order_id=order_id, intent_id=intent.id, episode_id=episode.id,
            action="BTC_ENTRY", instrument_id=str(HL_BTC.id), quantity="0.02000", reduce_only=False,
        )
        strategy.attach_recovery_runtime(active)
        strategy.submit_order(order)
        await asyncio.sleep(3)
        if os.environ.get("CM_FAKE_ACCEPT_LIVE") != "1":
            raise AssertionError("fake venue did not accept native submit")
        active.close()
    if journal and os.environ.get("CM_FAKE_SUBMIT") != "1" and os.environ.get("CM_FAKE_MARKET_IOC") != "1" and json.loads(Path(os.environ["CM_FAKE_VENUE_STATE"]).read_text())["partial"]:
        client = next(item for item in node.kernel.exec_engine._clients.values() if isinstance(item, FakeReportClient))
        reports = await client.generate_fill_reports(None)
        order_reports = await client.generate_order_status_reports(None)
        active = PaperRuntime(Path(journal), "live-recovery-probe", 10**20)
        active.acquire()
        if os.environ.get("CM_FAKE_NORMAL_CALLBACK") == "1":
            strategy.attach_recovery_runtime(active)
            for report in reports:
                strategy.on_order_filled(SimpleNamespace(
                    trade_id=report.trade_id, client_order_id=report.client_order_id,
                    instrument_id=report.instrument_id, last_qty=report.last_qty,
                    last_px=report.last_px, ts_event=report.ts_event, ts_init=report.ts_init,
                    commission=report.commission, liquidity_side=report.liquidity_side,
                    order_type=OrderType.LIMIT,
                ))
                assert active.has_applied_fill(str(report.trade_id))
            assert active.strategy_checkpoint()[0] == strategy.on_save()["wave_overlay_live_recovery_v1"]
            os._exit(137)
        LiveRecoveryReconciler(active, strategy, str(ACCOUNT)).apply_partial_fills(
            reports, node.cache.orders_open(), node.cache.positions_open(), order_reports,
            node.cache.account_for_venue(Venue("HYPERLIQUID")),
        )
        active.close()
    episode = strategy._domain.episode
    result = {
        "running": node.is_running(),
        "orders": [(str(o.client_order_id), str(o.quantity), str(o.filled_qty)) for o in node.cache.orders_open()],
        "native_order_types": sorted(str(o.order_type.name) for o in node.cache.orders(venue=Venue("HYPERLIQUID"))),
        "positions": [(str(p.instrument_id), str(p.quantity)) for p in node.cache.positions_open()],
        "fills": len(node.trader.generate_order_fills_report()),
        "cached_fill_events": sorted(
            str(event.trade_id)
            for order in node.cache.orders(venue=Venue("HYPERLIQUID"))
            for event in order.events if hasattr(event, "trade_id")
        ),
        "native_commissions": sorted(str(item.get("commission")) for item in node.trader.generate_fills_report().to_dict("records")),
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


def test_normal_partial_callback_restarts_without_replay(tmp_path):
    if not os.environ.get("COINMASTER_TEST_REDIS_PORT"):
        pytest.skip("requires disposable loopback Redis")
    state, journal, submit_log = (tmp_path / name for name in ("state.json", "intents.sqlite", "submits.txt"))
    state.write_text('{"partial": true}')
    env = dict(os.environ, CM_FAKE_VENUE_STATE=str(state), CM_FAKE_JOURNAL=str(journal),
               CM_FAKE_SUBMIT_LOG=str(submit_log), CM_FAKE_TRADER_ID="HL-NORMAL-" + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:8].upper())
    env["PYTHONPATH"] = os.pathsep.join((str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)))
    runtime = PaperRuntime(journal, "live-recovery-probe", 10**20)
    runtime.acquire()
    runtime.snapshot(ts_ns=__import__("time").time_ns(), positions=[], orders=[], funding_event_ids=[])
    strategy = _strategy()
    episode = Episode("episode-1", 1, 10000, 1.2)
    intent = Intent("intent-1", episode.id, "BTC_ENTRY", None, 1, quantity=0.02)
    episode.pending[intent.id] = intent
    strategy._domain.episode = episode
    strategy._pending_by_order[str(CLIENT_ORDER)] = intent
    strategy._sigma_by_order[str(CLIENT_ORDER)] = None
    strategy._decision_index_by_order[str(CLIENT_ORDER)] = 1483
    assert LiveRecoverySubmissionSink(runtime, strategy, frozenset({str(HL_BTC.id)}))(
        client_order_id=str(CLIENT_ORDER), intent_id=intent.id, episode_id=episode.id,
        action="BTC_ENTRY", instrument_id=str(HL_BTC.id), quantity="0.02000", reduce_only=False,
    )
    runtime.close()
    env["CM_FAKE_NORMAL_CALLBACK"] = "1"
    env["CM_FAKE_NUMERIC_FILL"] = "1"
    env["CM_FAKE_TWO_FILLS"] = "1"
    first = subprocess.run([sys.executable, __file__, "--child"], env=env, capture_output=True, text=True, timeout=45)
    assert first.returncode == 137, first.stderr
    env.pop("CM_FAKE_NORMAL_CALLBACK")
    env["CM_FAKE_RAW_CONVERTER"] = "1"
    persisted = PaperRuntime(journal, "live-recovery-probe", 10**20)
    checkpoint = persisted.strategy_checkpoint()
    assert persisted.applied_fill_ids() == frozenset({"8", "9"})
    persisted.close()
    second = subprocess.run([sys.executable, __file__, "--child"], env=env, capture_output=True, text=True, timeout=45)
    assert second.returncode == 0, second.stderr
    result = json.loads(next(line.split("=", 1)[1] for line in second.stdout.splitlines() if line.startswith("RECOVERY_PROOF=")))
    assert result["episode_btc_open_qty"] == 0.01
    assert result["fills"] == 1, result
    assert len(result["native_commissions"]) == 2, result
    assert result["cached_fill_events"] == ["8", "9"]
    assert not submit_log.exists()
    final = PaperRuntime(journal, "live-recovery-probe", 10**20)
    assert final.strategy_checkpoint() == checkpoint
    final.close()


def test_fake_transport_accepts_before_ack_then_restart_recovers_native_order(tmp_path):
    if not os.environ.get("COINMASTER_TEST_REDIS_PORT"):
        pytest.skip("requires disposable loopback Redis")
    state, journal, submit_log = (tmp_path / name for name in ("state.json", "intents.sqlite", "submits.txt"))
    state.write_text('{"partial": false}')
    env = dict(os.environ, CM_FAKE_VENUE_STATE=str(state), CM_FAKE_JOURNAL=str(journal),
               CM_FAKE_SUBMIT_LOG=str(submit_log), CM_FAKE_TRADER_ID="HL-ACCEPT-" + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:8].upper())
    env["PYTHONPATH"] = os.pathsep.join((str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)))
    env["CM_FAKE_SUBMIT"] = env["CM_FAKE_ACCEPT_CRASH"] = "1"
    crashed = subprocess.run([sys.executable, __file__, "--child"], env=env, capture_output=True, text=True, timeout=45)
    assert crashed.returncode == 137, crashed.stderr
    accepted = json.loads(state.read_text())
    order_id = accepted["accepted_order"]
    assert accepted["partial"] is True
    assert submit_log.read_text().splitlines() == [order_id]
    pending = PaperRuntime(journal, "live-recovery-probe", 10**20)
    assert pending.pending_submissions()[0]["client_order_id"] == order_id
    assert pending.pending_submissions()[0]["state"] == "SUBMITTING"
    assert pending.strategy_checkpoint() is not None
    pending.close()
    env.pop("CM_FAKE_SUBMIT")
    env.pop("CM_FAKE_ACCEPT_CRASH")
    env["CM_FAKE_RAW_CONVERTER"] = "1"
    recovered = subprocess.run([sys.executable, __file__, "--child"], env=env, capture_output=True, text=True, timeout=45)
    assert recovered.returncode == 0, recovered.stderr
    result = json.loads(next(line.split("=", 1)[1] for line in recovered.stdout.splitlines() if line.startswith("RECOVERY_PROOF=")))
    assert result["orders"] == [[order_id, "0.02000", "0.01000"]]
    assert result["positions"] == [[str(HL_BTC.id), "0.01000"]]
    assert result["episode_btc_open_qty"] == 0.01
    assert result["fills"] == 1
    assert submit_log.read_text().splitlines() == [order_id]

    # Independent uninterrupted native path, same fake venue account/fill facts.
    live_state = tmp_path / "live-state.json"
    live_journal = tmp_path / "live-intents.sqlite"
    live_log = tmp_path / "live-submits.txt"
    live_state.write_text('{"partial": false}')
    live_env = dict(env, CM_FAKE_VENUE_STATE=str(live_state), CM_FAKE_JOURNAL=str(live_journal),
                    CM_FAKE_SUBMIT_LOG=str(live_log), CM_FAKE_TRADER_ID="HL-LIVE-" + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:8].upper(),
                    CM_FAKE_SUBMIT="1", CM_FAKE_ACCEPT_CRASH="1", CM_FAKE_ACCEPT_LIVE="1",
                    CM_FAKE_RAW_CONVERTER="0")
    uninterrupted = subprocess.run([sys.executable, __file__, "--child"], env=live_env, capture_output=True, text=True, timeout=45)
    assert uninterrupted.returncode == 0, uninterrupted.stderr
    live_result = json.loads(next(line.split("=", 1)[1] for line in uninterrupted.stdout.splitlines() if line.startswith("RECOVERY_PROOF=")))
    assert live_result["positions"] == result["positions"]
    assert live_result["fills"] == result["fills"]
    assert live_result["native_commissions"] == result["native_commissions"]
    assert len(result["native_commissions"]) == 1
    amount, currency = result["native_commissions"][0].rsplit(" ", 1)
    assert Decimal(amount) == Decimal("0.27") and currency == "USDC"
    assert live_log.read_text().splitlines() == [json.loads(live_state.read_text())["accepted_order"]]
    assert live_result["native_total_usdc"] == result["native_total_usdc"]


if __name__ == "__main__" and "--child" in sys.argv:
    asyncio.run(_run_child())

def test_market_ioc_entry_lost_ack_reconciles_native_type(tmp_path):
    if not os.environ.get("COINMASTER_TEST_REDIS_PORT"):
        pytest.skip("requires disposable loopback Redis")
    state, journal, submit_log = (tmp_path / name for name in ("state.json", "intents.sqlite", "submits.txt"))
    state.write_text('{"partial": false}')
    env = dict(
        os.environ, CM_FAKE_VENUE_STATE=str(state), CM_FAKE_JOURNAL=str(journal),
        CM_FAKE_SUBMIT_LOG=str(submit_log),
        CM_FAKE_TRADER_ID="HL-MARKET-" + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:8].upper(),
        CM_FAKE_MARKET_IOC="1", CM_FAKE_SUBMIT="1", CM_FAKE_ACCEPT_CRASH="1",
    )
    env["PYTHONPATH"] = os.pathsep.join((str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)))
    first = subprocess.run([sys.executable, __file__, "--child"], env=env, capture_output=True, text=True, timeout=45)
    assert first.returncode == 137, first.stderr
    assert json.loads(state.read_text())["partial"] is True
    env.pop("CM_FAKE_SUBMIT")
    env.pop("CM_FAKE_ACCEPT_CRASH")
    env["CM_FAKE_RAW_CONVERTER"] = "1"
    second = subprocess.run([sys.executable, __file__, "--child"], env=env, capture_output=True, text=True, timeout=45)
    assert second.returncode == 0, second.stderr
    result = json.loads(next(line.split("=", 1)[1] for line in second.stdout.splitlines() if line.startswith("RECOVERY_PROOF=")))
    assert result["native_order_types"] == ["MARKET"]
    assert result["positions"] == [[str(HL_BTC.id), "0.01000"]]
    assert result["fills"] == 1
    assert len(submit_log.read_text().splitlines()) == 1

def test_reduce_only_market_ioc_exit_reconciles_native_flat(tmp_path):
    if not os.environ.get("COINMASTER_TEST_REDIS_PORT"):
        pytest.skip("requires disposable loopback Redis")
    state = tmp_path / "state.json"
    state.write_text('{"partial": false}')
    env = dict(
        os.environ, CM_FAKE_VENUE_STATE=str(state),
        CM_FAKE_TRADER_ID="HL-EXIT-" + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:8].upper(),
        CM_FAKE_EXIT_RECONCILE="1",
    )
    env["PYTHONPATH"] = os.pathsep.join((str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)))
    run = subprocess.run([sys.executable, __file__, "--child"], env=env, capture_output=True, text=True, timeout=45)
    assert run.returncode == 0, run.stderr
    result = json.loads(next(line.split("=", 1)[1] for line in run.stdout.splitlines() if line.startswith("EXIT_PROOF=")))
    assert result == {
        "applied": True, "order_type": "MARKET",
        "positions_open": [], "order_filled_qty": "0.01000",
    }

def test_kernel_reconciles_before_post_start_async_parity_gate(tmp_path):
    if not os.environ.get("COINMASTER_TEST_REDIS_PORT"):
        pytest.skip("requires disposable loopback Redis")
    state = tmp_path / "state.json"
    state.write_text('{"partial": false}')
    env = dict(
        os.environ, CM_FAKE_VENUE_STATE=str(state),
        CM_FAKE_TRADER_ID="HL-HANDOVER-" + hashlib.sha256(str(tmp_path).encode()).hexdigest()[:8].upper(),
        CM_FAKE_HANDOVER_PROBE="1",
    )
    env["PYTHONPATH"] = os.pathsep.join((str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)))
    run = subprocess.run([sys.executable, __file__, "--child"], env=env, capture_output=True, text=True, timeout=45)
    assert run.returncode == 0, run.stderr
    result = json.loads(next(line.split("=", 1)[1] for line in run.stdout.splitlines() if line.startswith("HANDOVER_PROOF=")))
    assert result == {
        "on_start_after_reconcile": True,
        "blocked_before_parity": True,
        "confirmed_after_parity": True,
    }
