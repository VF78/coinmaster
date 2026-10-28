"""Two credential-free connected native cases. Import/help never imports Nautilus.

This is a native event-routing fixture, NOT venue matching/execution evidence.
Run A then B in fresh processes. Root claims each physical attempt BEFORE launch.
No pytest collection entry points and no engine at import time.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

BASE = "8ef2ece80a4c6dc7a38cb95852d7ff3439da6e75"
FRESH_NATIVE_INIT_API_WIRED = True
UNIFIED_SOURCE_WIRED = False  # Await writer final Unified source/schema and peer.
ROOT_NATIVE_GO = False  # Root alone authorizes a reviewed frozen physical attempt.
KEY = "wave_overlay_live_recovery_v1"
PRODUCT = (
    "ops/hl_live_worker.py", "ops/hl_live_execution.py", "ops/hl_live_money.py",
    "ops/hl_live_epoch.py", "ops/hl_info_receipt.py", "ops/hl_live_profile.py",
    "ops/hl_qualified_reports.py", "ops/live_recovery.py", "strategy/live_recovery.py",
    "strategy/residual_recovery.py", "strategy/c1_inputs.py", "strategy/wave_overlay.py",
)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def preflight(args):
    if not ROOT_NATIVE_GO or not UNIFIED_SOURCE_WIRED or not FRESH_NATIVE_INIT_API_WIRED:
        raise RuntimeError("PREPARATION_ONLY_FINAL_UNIFIED_SOURCE_AND_ROOT_NATIVE_GO_REQUIRED")
    root = Path(__file__).resolve().parents[2]
    pins = {}
    for rel in PRODUCT:
        name = "runtime/coinmaster/" + rel
        pinned = subprocess.check_output(["git", "show", args.expected_source + ":" + name], cwd=root)
        actual = (root / name).read_bytes()
        if actual != pinned:
            raise RuntimeError("PRODUCT_SOURCE_NOT_FROZEN:" + name)
        pins[name] = digest(actual)
    fixture_hash = digest(Path(__file__).read_bytes())
    ledger = json.loads(args.ledger.read_text())
    attempts = ledger["attempts"]
    if len(attempts) > 3:
        raise RuntimeError("NATIVE_ATTEMPT_CAP_EXCEEDED")
    matches = [a for a in attempts if a["attempt_id"] == args.attempt_id]
    if len(matches) != 1:
        raise RuntimeError("ROOT_LEDGER_CLAIM_REQUIRED")
    claim = matches[0]
    for field, value in dict(case=args.case, status="RUNNING", source_commit=args.expected_source,
                             fixture_sha256=fixture_hash).items():
        if claim.get(field) != value:
            raise RuntimeError("ROOT_LEDGER_CLAIM_MISMATCH:" + field)
    if args.case == "B":
        prior = json.loads((args.artifact_dir / "A-result.json").read_text())
        if prior["status"] != "PASS" or prior["source_commit"] != args.expected_source:
            raise RuntimeError("CASE_A_PASS_SAME_SOURCE_REQUIRED")
    return pins, fixture_hash


async def run(args, result):
    # Imports are deliberately below CLI/preflight. Nothing here is run for --help.
    from decimal import Decimal as D
    from types import SimpleNamespace
    import importlib.metadata
    import socket
    import urllib.request
    if importlib.metadata.version("nautilus_trader") != "1.231.0":
        raise RuntimeError("PINNED_NAUTILUS_1_231_0_REQUIRED")
    from nautilus_trader.common import Environment
    from nautilus_trader.config import LoggingConfig, LiveExecClientConfig
    from nautilus_trader.live.config import TradingNodeConfig, LiveExecEngineConfig, RoutingConfig
    from nautilus_trader.live.node import TradingNode
    from nautilus_trader.live.factories import LiveExecClientFactory
    from nautilus_trader.trading.strategy import Strategy
    from nautilus_trader.model.data import BarType, BarSpecification
    from nautilus_trader.model.enums import (OrderSide, OrderType, TimeInForce, LiquiditySide,
                                            BarAggregation, PriceType, AggregationSource)
    from nautilus_trader.model.identifiers import ClientOrderId, ClientId, InstrumentId, TradeId, VenueOrderId, Venue
    from nautilus_trader.model.objects import Quantity, Price, Money, AccountBalance
    from nautilus_trader.model.currencies import USDC
    from nautilus_trader.core import nautilus_pyo3
    from coinmaster.ops.hl_live_epoch import LiveEpochRuntime
    from coinmaster.ops.live_recovery import NativeLiveRecoveryScope, durable_management_scope
    from coinmaster.ops.hl_info_receipt import collect_info_receipt, IncompleteInfoReport
    from coinmaster.ops.hl_live_profile import load_live_profile
    from coinmaster.ops.stage_g_config import load_candidate
    from coinmaster.ops.hl_live_execution import SingleAttemptInfoTransport, bind_clean_flat_live_handover
    import coinmaster.ops.hl_live_execution as execution
    from coinmaster.strategy.live_recovery import RecoverableWaveOverlayStrategy
    from coinmaster.strategy.wave_overlay import WaveOverlayStrategyConfig
    from coinmaster.domain.wave_overlay import Episode
    from coinmaster.venues.marks import venue_mark_data_type
    from test_live_native_report_recovery import FakeReportClient, HL_BTC, HL_SOL, ACCOUNT, ACCOUNT_REF

    result["native_version"] = "1.231.0"
    result["fixture_capital_tag"] = "SYNTHETIC_APPROVED_100_USDC_NOT_REAL_BUDGET"
    result["financial_source_mode"] = "unifiedAccount"
    result["financial_equity_basis"] = "NATIVE_REPORTED_USDC_TOTAL_NO_ADDED_UPNL"
    counts = result["counts"]
    def forbidden(*unused, **kwargs):
        counts["external_network_attempts"] += 1
        raise RuntimeError("FIXTURE_EXTERNAL_NETWORK_FORBIDDEN")
    # The event loop already exists. All subsequent network connection attempts fail.
    old_connect, old_urlopen = socket.socket.connect, urllib.request.urlopen
    socket.socket.connect = forbidden
    urllib.request.urlopen = forbidden
    execution.urlopen = forbidden
    runtime = LiveEpochRuntime(args.artifact_dir / "native.sqlite", "e4-c1-native-fixture", 10**20)
    runtime.acquire()
    runtime.acquire_live_account(ACCOUNT_REF, "HYPERLIQUID", lock_root=args.artifact_dir/"account-locks")
    if args.case == "A":
        assert runtime.strategy_checkpoint() is None and runtime.c1_initialization() is None
        assert runtime.deposit_protection_state(instance_id=runtime.owner, account_id=str(ACCOUNT)) is None
        runtime.entry_control_command("pause-new-entries", "c1-init-prepare")
    os.environ["CM_FAKE_VENUE_STATE"] = str(args.artifact_dir / "fake-venue.json")
    (args.artifact_dir / "fake-venue.json").write_text(json.dumps(dict(partial=False, balance="100")))
    os.environ["CM_FAKE_PRODUCTION_PARITY"] = "1"

    class Client(FakeReportClient):
        def __init__(self, *a):
            super().__init__(*a)
            self.total = D("100")
            self.delay_account = False
            self.lost = set()
            self.info_unknown = set()
            self.seen_commands = []
            self.oid = 7
        def account_state(self):
            self.generate_account_state([AccountBalance(Money(self.total, USDC), Money(0, USDC),
                Money(self.total, USDC))], [], True, self._clock.timestamp_ns())
        async def _connect(self):
            self.account_state()
        async def _query_account(self, command):
            counts["query_account_commands"] += 1
            if not self.delay_account:
                self.account_state()
        async def _submit_order(self, command):
            counts["synthetic_submit_commands"] += 1
            order = command.order
            self.seen_commands.append(str(order.client_order_id))
            if str(order.client_order_id) not in self.lost:
                self.oid += 1
                self.generate_order_accepted(order.strategy_id, order.instrument_id, order.client_order_id,
                    VenueOrderId(str(self.oid)), self._clock.timestamp_ns())
        async def _cancel_order(self, command):
            counts["synthetic_cancel_commands"] += 1
            # ACK is deliberately controlled separately to expose the fill race.
        async def generate_mass_status(self, lookback_mins=None):
            return await execution.QualifiedInfoBoundary.generate_mass_status(self, lookback_mins)
        async def generate_order_status_reports(self, command):
            return []
        async def generate_fill_reports(self, command):
            return []
        async def generate_position_status_reports(self, command):
            return []

    clients = []
    class Factory(LiveExecClientFactory):
        @staticmethod
        def create(loop, name, config, msgbus, cache, clock):
            client = Client(loop, msgbus, cache, clock)
            clients.append(client)
            return client

    startup = []
    class Probe(RecoverableWaveOverlayStrategy):
        # Keep real on_start; intercept only public feed transports, never fabricate bars.
        def subscribe_bars(self, kind, *a, **kw):
            startup.append(("subscribe", str(kind), kw))
        def request_bars(self, kind, *a, **kw):
            startup.append(("request", str(kind), kw))
        def subscribe_quote_ticks(self, *a, **kw):
            pass
        def subscribe_data(self, *a, **kw):
            pass

    root = Path(__file__).resolve().parents[1]
    candidate = load_candidate(root / "configs/hl-live-v3-dp50.candidate.json").candidate
    profile = load_live_profile(root, candidate)
    flags = dict(profile["strategy_flags"])
    for k in ("research_c1_restore_dd", "research_regime_reentry_band", "research_btc_split_discount"):
        flags[k] = D(str(flags[k]))
    def bar(coin, aggregation):
        return BarType(InstrumentId.from_str(coin + "USDT-LINEAR.BYBIT"),
            BarSpecification(1, aggregation, PriceType.LAST), AggregationSource.EXTERNAL)
    strategy = Probe(WaveOverlayStrategyConfig(strategy_id="e4-c1-native-fixture", order_id_tag="E4C1",
        btc_id=HL_BTC.id, sol_id=HL_SOL.id,
        btc_bar_type=bar("BTC", BarAggregation.DAY), sol_bar_type=bar("SOL", BarAggregation.DAY),
        btc_mark_data_type=venue_mark_data_type(HL_BTC.id), sol_mark_data_type=venue_mark_data_type(HL_SOL.id),
        mark_client_id=ClientId("HYPERLIQUID"), active_seed=D("100"), candidate=candidate,
        entries_enabled=False, native_fill_sink=runtime.record_native_fill,
        deposit_runtime=runtime, deposit_instance_id=runtime.owner, deposit_account_id=str(ACCOUNT),
        deposit_equity_reader=lambda s: s._validated_live_deposit_equity(),
        deposit_initialization_allowed=lambda: False,
        execution_policy_hash="hl-mainnet-native-owned-v1", execution_policy_version="hl-mainnet-native-owned-v1",
        **flags))
    strategy._input_readiness_preparation = True
    strategy._live_minute_bar_types = (bar("BTC", BarAggregation.MINUTE), bar("SOL", BarAggregation.MINUTE))
    strategy.attach_recovery_runtime(runtime)
    strategy.enable_manage_only_preparation()
    if args.case == "B":
        strategy.on_load({KEY: runtime.strategy_checkpoint()[0]})
    else:
        # Same actual virgin preparation used by the worker. No checkpoint/H/rights seed.
        strategy._fresh_c1_init_intent = "INITIALIZE_FRESH_C1_EPOCH"

    config = TradingNodeConfig(environment=Environment.LIVE, trader_id="E4-C1-NATIVE-ACCEPTANCE",
        logging=LoggingConfig(log_level="ERROR"), exec_engine=LiveExecEngineConfig(reconciliation=False),
        exec_clients={"FAKE": LiveExecClientConfig(routing=RoutingConfig(venues=frozenset({"HYPERLIQUID"})))})
    node = None
    async def wait_for(predicate, reason):
        for _ in range(100):
            if predicate():
                return
            await asyncio.sleep(.01)
        raise AssertionError(reason)
    async def gate(name, action):
        try:
            value = action()
            if hasattr(value, "__await__"):
                await value
            result["gates"][name] = dict(status="PASS")
        except Exception as exc:
            result["gates"][name] = dict(status="FAIL", reason=repr(exc), traceback=traceback.format_exc())
    def cloid(client):
        return str(nautilus_pyo3.hyperliquid_cloid_from_client_order_id(nautilus_pyo3.ClientOrderId(client)))
    async def settle():
        await asyncio.sleep(.05)
    def fills():
        return runtime.native_fill_details()
    def state():
        positions = []
        notional = D(0)
        upnl = D(0)
        for p in node.cache.positions_open():
            mark = Price.from_str("60000.0")
            size = p.quantity.as_decimal() * (1 if p.is_long else -1)
            notional += abs(size) * mark.as_decimal()
            upnl += p.unrealized_pnl(mark).as_decimal()  # Native computation only.
            positions.append(dict(position=dict(coin="BTC", szi=str(size), entryPx=str(p.avg_px_open),
                leverage=dict(type="cross", value=10), positionValue=str(abs(size)*mark.as_decimal()),
                unrealizedPnl=str(p.unrealized_pnl(mark).as_decimal()))))
        # These are explicit synthetic venue cash inputs, never a custom PnL engine.
        # Unified money truth is the USDC spot/native total. Perp summary is NOT
        # combined with it; native UPNL remains a position diagnostic only.
        summary = dict(accountValue="0", totalRawUsd="0", totalMarginUsed="0", totalNtlPos=str(notional))
        return dict(assetPositions=positions, marginSummary=summary,
            crossMarginSummary=dict(summary), withdrawable="0")
    def raw_order(order):
        return dict(coin="BTC", oid=int(str(order.venue_order_id)), cloid=cloid(str(order.client_order_id)),
            side="B" if order.side == OrderSide.BUY else "A", origSz=str(order.quantity.as_decimal()),
            sz=str(order.quantity.as_decimal()-order.filled_qty.as_decimal()), reduceOnly=order.is_reduce_only,
            orderType="Limit", tif="Ioc", limitPx="60000.0", timestamp=order.ts_init//1_000_000)
    async def info(body, **unused):
        counts["synthetic_info_requests"] += 1
        kind = body["type"]
        if kind == "clearinghouseState": return state()
        if kind == "userRole": return {"role": "user"}
        if kind == "userAbstraction": return "unifiedAccount"
        if kind == "spotClearinghouseState":
            return dict(balances=[dict(coin="USDC", token=0, total=str(client.total), hold="0", entryNtl="0")])
        if kind == "userDexAbstraction": return False
        if kind == "activeAssetData":
            return dict(user=ACCOUNT_REF, coin=body["coin"], leverage=dict(type="cross", value=10),
                markPx="60000" if body["coin"] == "BTC" else "200")
        if kind == "frontendOpenOrders": return [raw_order(o) for o in node.cache.orders_open()]
        if kind == "orderStatus":
            found = [o for o in node.cache.orders() if cloid(str(o.client_order_id)) == body["oid"]]
            if not found or str(found[0].client_order_id) in client.info_unknown: return dict(status="unknownOid")
            order = found[0]
            if order.venue_order_id is None: return dict(status="unknownOid")
            return dict(status="order", order=dict(order=raw_order(order),
                status="filled" if order.is_filled else "canceled" if order.is_closed else "open",
                statusTimestamp=max(order.ts_init, order.ts_last)//1_000_000))
        if kind == "userFillsByTime":
            rows = []
            for f in fills():
                ms = f["ts_event_ns"]//1_000_000
                if body["startTime"] <= ms <= body["endTime"]:
                    rows.append(dict(coin="BTC", oid=int(f["venue_order_id"]), tid=int(f["trade_id"]), time=ms,
                        side="B" if f["order_side"] == "BUY" else "A", sz=f["quantity"], px=f["price"],
                        fee=f["commission_amount"], feeToken="USDC", hash="0xfixture"+f["trade_id"], crossed=True))
            return rows
        raise AssertionError("UNEXPECTED_INFO:"+kind)

    async def seed(name, side, qty, *, close=False, lost=False):
        order = strategy.order_factory.limit(instrument_id=HL_BTC.id, order_side=side,
            quantity=Quantity.from_str(qty), price=Price.from_str("60000.0"), time_in_force=TimeInForce.IOC,
            reduce_only=close, client_order_id=ClientOrderId(name))
        if not close:
            episode = strategy._domain.episode
            intent = strategy._domain._intent(episode, "BTC_ENTRY", 1, 0, quantity=float(qty))
            strategy._pending_by_order[name] = intent
        else:
            strategy._forced_close_orders.add(name)
        runtime.record_submission(client_order_id=name, intent_id=name, episode_id="fixture", action="CLOSE_ALL" if close else "BTC_ENTRY",
            instrument_id=str(HL_BTC.id), quantity=qty, reduce_only=close, strategy_state=strategy.on_save()[KEY])
        if lost: client.lost.add(name)
        # Fixed fixture seeds bypass only the strategy decision gate; native Strategy ->
        # RiskEngine -> ExecutionEngine -> FAKE client is the actual public route.
        Strategy.submit_order(strategy, order)
        await settle()
        assert name in client.seen_commands, "Native submit route did not reach FAKE client"
        return order
    async def emit_fill(order, tid, qty):
        client.generate_order_filled(order.strategy_id, order.instrument_id, order.client_order_id,
            order.venue_order_id, None, TradeId(tid), order.side, OrderType.LIMIT,
            Quantity.from_str(qty), Price.from_str("60000.0"), HL_BTC.quote_currency, Money(D("0.00027"), USDC),
            LiquiditySide.TAKER, client._clock.timestamp_ns())
        await settle()

    try:
        counts["nodes_constructed"] += 1
        node = TradingNode(config=config, loop=asyncio.get_running_loop())
        node.add_exec_client_factory("FAKE", Factory)
        node.build()
        node.cache.add_instrument(HL_BTC)
        node.cache.add_instrument(HL_SOL)
        node.trader.add_strategy(strategy)
        client = clients[0]
        assert str(HL_BTC.quote_currency) == "USD" and str(HL_SOL.quote_currency) == "USD"
        assert str(HL_BTC.settlement_currency) == "USDC" and str(HL_SOL.settlement_currency) == "USDC"
        if args.case == "A":
            scope = NativeLiveRecoveryScope(ACCOUNT_REF, "", time.time_ns()//1_000_000, None, (), frozenset({"BTC", "SOL"}))
            execution.read_info_http = info  # Only the network edge is fake.
            client.configure_info_boundary(scope, SingleAttemptInfoTransport(testnet=False, timeout=1), runtime.applied_fill_ids)
            client._cm_runtime = runtime
            bind_clean_flat_live_handover(client, strategy, runtime, manage_only=True, monitor_interval_secs=60)
        await node.kernel.start_async()
        await settle()
        def startup_check():
            requests = [r for r in startup if r[0] == "request" and "MINUTE" in r[1]]
            assert len(requests) == 2, startup
            assert len([r for r in startup if r[0] == "subscribe" and "MINUTE" in r[1]]) == 2
            for _, _, kw in requests:
                assert int(kw["end"].timestamp()*1e9) == strategy._live_history_cutoff_ns
                assert kw["start"] < kw["end"]
        await gate("native_startup_closed_minute_requests", startup_check)
        if args.case == "B":
            expected = json.loads((args.artifact_dir/"restart-proof.json").read_text())
            def restart_check():
                assert digest(strategy.on_save()[KEY]) == expected["checkpoint_sha256"]
                assert strategy.deposit_projection()["drawdown_limit_percent"] == 55
                assert strategy._deposit.high_water == D(expected["high_water"])
                assert runtime.c1_initialization() == expected["initialization_marker"]
                assert strategy._fresh_c1_init_intent is None
                assert strategy._deposit.latched is True
                assert strategy._c1_peak == D(expected["c1_peak"])
                assert strategy._next_peak == D(expected["next_peak"])
                assert strategy._live_signal_clock_state == expected["signal_clock"]
                assert runtime.applied_fill_ids() == frozenset(expected["applied_fill_ids"])
                assert not node.cache.positions_open() and not node.cache.orders_open() and not node.cache.orders_inflight()
                assert strategy.recovery_confirmed is False and strategy._management_certificate is None
                assert strategy._management_dispatch_enabled is False and not strategy._quote_ns
                assert strategy._last_live_input_observation is None
                assert not strategy._entries_enabled()
                try: runtime.prepare_flat_epoch(release_commit=args.expected_source)
                except RuntimeError as exc: assert str(exc) == "C1_E4_CHECKPOINT_REQUIRES_MANAGE_ONLY"
                else: raise AssertionError("C1 flat history was retired")
                assert counts["synthetic_submit_commands"] == 0
            await gate("paused_flat_restart_preserves_H55_rights_clocks_and_audit", restart_check)
            return

        async def fresh_init():
            assert strategy._post_drain_task is not None
            await strategy._post_drain_task  # Actual native on_start invokes the production full verifier.
            marker = runtime.c1_initialization()
            assert marker is not None and D(marker["initial_equity"]) == D("100")
            assert marker["history_anchor_ms"] == client._cm_scope.anchor_ms
            assert strategy._c1_peak == strategy._next_peak == D("100")
            assert strategy._c1_state is None and not strategy._c1_intents and not strategy._pending_by_order
            assert runtime.strategy_checkpoint()[0] == strategy.on_save()[KEY]
            assert runtime.entry_control_state() == "PAUSED" and strategy._management_dispatch_enabled is False
            assert not node.cache.positions_open() and not node.cache.orders_open() and not node.cache.orders_inflight()
            zero_fill_scope = durable_management_scope(runtime, ACCOUNT_REF, "", cloid)
            assert zero_fill_scope.anchor_ms == marker["history_anchor_ms"]
            initial_marker.update(marker)
            # A genuine current observation supplies the REAL production DP reader.
            await client._cm_collect_portfolio_observation(strategy)
            await settle()
            await client._cm_collect_portfolio_observation(strategy)
            assert strategy._validated_live_deposit_equity() == D("100")
        initial_marker = {}
        await gate("actual_virgin_native_flat_INIT_atomic_once_and_original_anchor", fresh_init)
        if not initial_marker:
            raise RuntimeError("FRESH_NATIVE_INIT_NOT_QUALIFIED_NO_FIXTURE_SEEDS")
        async def initialize_dp_control():
            assert strategy._deposit.high_water is None  # Never reset an existing anchor.
            strategy.initialize_fresh_live_deposit_protection("fixture-initialize-virgin-dp55")
            assert strategy._deposit.high_water == D("100") and strategy._deposit.threshold == D("45")
        await gate("public_virgin_DP55_wrapper_from_native_equity_never_existing_H_reset", initialize_dp_control)
        strategy._domain.episode = Episode("fixture", time.time_ns(), 100, 1)
        entry = await seed("E4C1-IOC", OrderSide.BUY, "0.00020")
        async def partial_and_cancel():
            await emit_fill(entry, "101", "0.00010")
            Strategy.cancel_order(strategy, entry)
            await settle()
            await emit_fill(entry, "102", "0.00005")
            client.generate_order_canceled(entry.strategy_id, entry.instrument_id, entry.client_order_id,
                entry.venue_order_id, client._clock.timestamp_ns())
            await settle()
            assert entry.filled_qty.as_decimal() == D("0.00015") and entry.is_closed
            assert node.cache.positions_open()[0].quantity.as_decimal() == D("0.00015")
            assert runtime.applied_fill_ids() == frozenset({"101", "102"})
            assert len(fills()) == 2
            for row in fills():
                assert row["commission_currency"] == "USDC"
        await gate("partial_ioc_fill_during_cancel_then_remainder_cancel", partial_and_cancel)
        async def duplicate():
            original = next(e for e in entry.events if str(getattr(e, "trade_id", "")) == "102")
            before = (node.cache.positions_open()[0].quantity.as_decimal(), len(fills()), runtime.native_revision())
            node.kernel.exec_engine.process(original)
            await settle()
            assert before == (node.cache.positions_open()[0].quantity.as_decimal(), len(fills()), runtime.native_revision())
        await gate("duplicate_native_fill_no_quantity_fee_or_journal_replay", duplicate)
        def stock_currency_contract():
            position = node.cache.positions_open()[0]
            account = node.cache.account_for_venue(Venue("HYPERLIQUID"))
            qty = position.quantity
            px = HL_BTC.make_price(D("60001"))
            pnl = position.unrealized_pnl(px)
            initial = account.calculate_margin_init(HL_BTC, qty, px)
            maintenance = account.calculate_margin_maint(HL_BTC, position.side, qty, px)
            commission = account.calculate_commission(HL_BTC, qty, px, LiquiditySide.TAKER)
            fees = position.commissions()
            result["stock_currency_observations"] = dict(quote=str(HL_BTC.quote_currency),
                instrument_settlement=str(HL_BTC.settlement_currency), position_settlement=str(position.settlement_currency),
                native_pnl=str(pnl), native_margin_init=str(initial), native_margin_maint=str(maintenance),
                native_helper_commission=str(commission), actual_fill_commissions=[str(m) for m in fees],
                realized_pnl=str(position.realized_pnl))
            assert all(str(m.currency) == "USDC" for m in fees)
            assert str(position.settlement_currency) == "USDC", "STOCK_5024_POSITION_COST_CURRENCY_NOT_SETTLEMENT"
            assert str(pnl.currency) == "USDC", "STOCK_5024_PNL_CURRENCY_NOT_SETTLEMENT"
            assert position.realized_pnl.as_decimal() == -sum((m.as_decimal() for m in fees), D(0)), "STOCK_5024_USDC_COMMISSION_NOT_REALIZED"
            assert str(initial.currency) == str(maintenance.currency) == "USDC", "STOCK_5024_MARGIN_CURRENCY_NOT_SETTLEMENT"
            assert str(commission.currency) == "USDC", "STOCK_5024_COMMISSION_HELPER_QUOTE_CURRENCY"
        await gate("stock_5024_actual_USD_quote_USDC_settlement_accounting", stock_currency_contract)
        async def lost_ack():
            order = await seed("E4C1-LOST", OrderSide.BUY, "0.00010", lost=True)
            assert order.venue_order_id is None and not order.is_closed
            before = counts["synthetic_submit_commands"]
            expected = {cloid(str(o.client_order_id)): int(str(o.venue_order_id)) if o.venue_order_id else None for o in node.cache.orders()}
            try:
                await collect_info_receipt(info, account=ACCOUNT_REF, dex="", anchor_ms=entry.ts_init//1_000_000,
                    anchor_tid=None, end_ms=client._clock.timestamp_ns()//1_000_000,
                    expected_orders=expected, owned_coins=frozenset({"BTC", "SOL"}), require_money_scope=True)
            except IncompleteInfoReport as exc: assert str(exc) == "ORDER_STATUS_UNKNOWN"
            else: raise AssertionError("Lost ACK accepted as known")
            assert counts["synthetic_submit_commands"] == before
            client.generate_order_accepted(order.strategy_id, order.instrument_id, order.client_order_id,
                VenueOrderId("99"), client._clock.timestamp_ns())
            await settle()
            client.generate_order_canceled(order.strategy_id, order.instrument_id, order.client_order_id,
                order.venue_order_id, client._clock.timestamp_ns())
            await settle()
            assert order.is_closed and counts["synthetic_submit_commands"] == before
        await gate("lost_ack_unknown_no_submit_retry_then_native_terminal", lost_ack)

        async def full_and_account():
            assert runtime.c1_initialization() == initial_marker
            assert client.request_effect_parity_refresh()
            await client._cm_refresh_task
            assert client.recovery_healthy() and strategy._management_certificate is not None
            assert strategy._management_dispatch_enabled is False
            client.delay_account = True
            strategy._live_inputs_dirty = True
            await client._cm_collect_portfolio_observation(strategy)
            await settle()
            assert strategy._last_live_input_observation is None and client._cm_account_refresh_wait is not None
            old = node.cache.account_for_venue(Venue("HYPERLIQUID")).last_event
            await client._cm_collect_portfolio_observation(strategy)
            assert node.cache.account_for_venue(Venue("HYPERLIQUID")).last_event == old
            client.delay_account = False
            client.account_state()
            await settle()
            await client._cm_collect_portfolio_observation(strategy)
            obs = strategy._last_live_input_observation
            assert obs is not None and not hasattr(obs, "command_capability")
            assert obs.equity == client.total  # Native reported Unified USDC equity, no added UPNL.
            try: obs.require_current(now_ns=obs.response_completed_ns+9_000_000_001, revision=obs.native_revision,
                                     fill_epoch=obs.fill_epoch, ws_epoch=obs.ws_epoch)
            except IncompleteInfoReport: pass
            else: raise AssertionError("Stale observation accepted")
            try: obs.require_current(now_ns=time.monotonic_ns(), revision=obs.native_revision+1,
                                     fill_epoch=obs.fill_epoch, ws_epoch=obs.ws_epoch)
            except IncompleteInfoReport: pass
            else: raise AssertionError("Moved revision accepted")
            from coinmaster.ops.hl_live_money import materialize_live_c1_input
            mark_ns = client._clock.timestamp_ns()
            marks = {HL_BTC.id: SimpleNamespace(price=D("60001"), ts_event=mark_ns, ts_init=mark_ns)}
            dto = materialize_live_c1_input(obs, native_positions=tuple(node.cache.positions_open()),
                native_marks=marks, native_cache=node.cache, account_event_id=obs.native_account_event_id,
                strategy_id=str(strategy.id), account_id=str(ACCOUNT), decision_ns=mark_ns,
                monotonic_ns=time.monotonic_ns(), revision=obs.native_revision, fill_epoch=obs.fill_epoch,
                ws_epoch=obs.ws_epoch, max_mark_age_ns=120_000_000_000)
            assert dto.equity == obs.equity
            assert dto.positions[0].native_pnl == node.cache.positions_open()[0].unrealized_pnl(Price.from_str("60001.0")).as_decimal()
        await gate("full_native_parity_and_actual_query_account_completion", full_and_account)
        async def funding():
            before = node.cache.account_for_venue(Venue("HYPERLIQUID")).balance_total(USDC).as_decimal()
            row = dict(time=time.time_ns()//1_000_000, hash="0xfixturefunding", delta=dict(coin="BTC", usdc="0.01"))
            cursor = dict(end_ms=row["time"])
            runtime.record_funding_page([row], expected_cursor=None, next_cursor=cursor, complete=True)
            runtime.record_funding_page([row], expected_cursor=cursor, next_cursor=cursor, complete=True)
            assert runtime.db.execute("SELECT COUNT(*) FROM live_evidence_payloads WHERE kind='funding_cash'").fetchone()[0] == 1
            assert node.cache.account_for_venue(Venue("HYPERLIQUID")).balance_total(USDC).as_decimal() == before
            client.account_state()
            await settle()
            assert node.cache.account_for_venue(Venue("HYPERLIQUID")).balance_total(USDC).as_decimal() == before
        await gate("funding_observation_dedup_never_cash_posts", funding)
        async def deposit():
            assert strategy._deposit.limit_percent == 55 and strategy._deposit.threshold == D("45")
            await client._cm_collect_portfolio_observation(strategy)
            # Use EXACT production configured reader; no scalar fixture reader swap.
            assert strategy._deposit_equity() is not None, "PRODUCTION_MANAGE_ONLY_DP_MONEY_UNAVAILABLE"
            for equity, latched in (("45.01", False), ("45", True), ("100", True)):
                client.total = D(equity)
                client.account_state()
                await settle()
                # New native account event and actual cheap bridge, never re-label old money.
                strategy._live_inputs_dirty = True
                await client._cm_collect_portfolio_observation(strategy)
                await settle()
                await client._cm_collect_portfolio_observation(strategy)
                assert strategy._deposit_equity() == D(equity), "PRODUCTION_DP_READER_NOT_CURRENT"
                strategy._deposit_check()
                assert strategy._deposit.latched is latched
            order = strategy.order_factory.limit(instrument_id=HL_BTC.id, order_side=OrderSide.BUY,
                quantity=Quantity.from_str("0.00010"), price=Price.from_str("60000.0"))
            before = counts["synthetic_submit_commands"]
            try: strategy.submit_order(order)
            except RuntimeError: pass
            assert counts["synthetic_submit_commands"] == before
        await gate("DP55_production_money_threshold_latch_and_increase_block", deposit)
        async def flat():
            qty = str(node.cache.positions_open()[0].quantity.as_decimal())
            close = await seed("E4C1-CLOSE", OrderSide.SELL, qty, close=True)
            await emit_fill(close, "103", qty)
            assert not node.cache.positions_open() and not node.cache.orders_open() and not node.cache.orders_inflight()
            assert runtime.applied_fill_ids() == frozenset({"101", "102", "103"})
            assert len(fills()) == 3
            assert all(r["state"] == "TERMINAL" for r in runtime.all_submissions())
            runtime.snapshot(ts_ns=time.time_ns(), positions=[], orders=[], funding_event_ids=[], reconciled=True,
                expected_revision=runtime.native_revision(), native_account_total=str(client.total), strategy_restartable=True)
        await gate("actual_native_flat_after_owned_reduction", flat)
        async def reconnect():
            client.socket_epoch += 1
            assert not client.recovery_healthy()
            assert strategy._management_certificate is None and not strategy.recovery_confirmed
            assert strategy._management_dispatch_enabled is False
            assert client._cm_ws_failure is not None
            # The existing design latches reconnect; no automatic freshening/reset.
        await gate("reconnect_epoch_latches_and_revokes", reconnect)
        checkpoint = runtime.strategy_checkpoint()
        assert checkpoint is not None
        proof = dict(checkpoint_sha256=digest(checkpoint[0]), high_water=str(strategy._deposit.high_water),
            c1_peak=str(strategy._c1_peak), next_peak=str(strategy._next_peak), signal_clock=strategy._live_signal_clock_state,
            initialization_marker=runtime.c1_initialization(),
            applied_fill_ids=sorted(runtime.applied_fill_ids()), deposit=runtime.deposit_protection_state(
                instance_id=runtime.owner, account_id=str(ACCOUNT)))
        (args.artifact_dir/"restart-proof.json").write_text(json.dumps(proof, indent=2))
    finally:
        if node is not None:
            await node.kernel.stop_async()
            node.kernel.dispose()
        runtime.close()
        socket.socket.connect, urllib.request.urlopen = old_connect, old_urlopen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("A", "B"), required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--expected-source", default=BASE)
    args = parser.parse_args()
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    result = dict(schema="e4-c1-connected-native-acceptance-v1", case=args.case,
        source_commit=args.expected_source, status="FAIL", matching_proof=False,
        gates={}, counts=dict(nodes_constructed=0, external_network_attempts=0,
            synthetic_submit_commands=0, synthetic_cancel_commands=0, query_account_commands=0,
            synthetic_info_requests=0), started_ns=time.time_ns())
    try:
        pins, fixture_hash = preflight(args)
        result.update(source_pins=pins, fixture_sha256=fixture_hash)
        asyncio.run(run(args, result))
        assert result["counts"]["nodes_constructed"] == 1
        assert result["counts"]["external_network_attempts"] == 0
        if result["gates"] and all(g["status"] == "PASS" for g in result["gates"].values()):
            result["status"] = "PASS"
    except BaseException as exc:
        result.update(error=repr(exc), traceback=traceback.format_exc())
    result["finished_ns"] = time.time_ns()
    (args.artifact_dir/(args.case+"-result.json")).write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps(dict(case=args.case, status=result["status"], counts=result["counts"],
                         failed_gates=[n for n,g in result["gates"].items() if g["status"] != "PASS"])))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
