"""Credential-free pinned client boundary regressions."""
import asyncio
from types import SimpleNamespace

import pytest

from coinmaster.ops.hl_live_execution import QualifiedInfoBoundary, ScopedHyperliquidExecClientFactory
from coinmaster.ops.live_recovery import NativeLiveRecoveryScope


ACCOUNT = "0x" + "a" * 40


class Event:
    pass


class Probe(QualifiedInfoBoundary):
    def __init__(self, *, fail=False, no_effect=False, limit=2):
        self.fail = fail
        self.no_effect = no_effect
        self.effects = 0
        self.socket = SimpleNamespace(active=True, closed=False)
        self._ws_client = SimpleNamespace(
            is_active=lambda: self.socket.active, is_closed=lambda: self.socket.closed,
        )
        scope = NativeLiveRecoveryScope(ACCOUNT, "", 1, None, (), frozenset({"BTC"}))
        self.configure_info_boundary(scope, lambda _: None, lambda: frozenset(), max_ws_messages=limit)

    def handle(self, msg):
        if self.fail:
            raise RuntimeError("native handler failed")
        if not self.no_effect:
            self.effects += 1

    async def generate_mass_status(self, lookback_mins=None):
        return SimpleNamespace(effects=self.effects)


def test_scoped_factory_requires_explicit_durable_scope_before_any_native_creation():
    with pytest.raises(RuntimeError, match="RECOVERY_SCOPE_NOT_BOUND"):
        ScopedHyperliquidExecClientFactory.create(None, None, None, None, None, None)


def test_ws_buffer_requires_observed_effect_not_handler_return(monkeypatch):
    from coinmaster.ops import hl_live_execution as owner
    monkeypatch.setattr(owner, "_WS_HANDLERS", ((Event, "handle"),))
    async def run():
        client = Probe(no_effect=True)
        client._handle_msg(Event())
        assert client.effects == 0
        with pytest.raises(RuntimeError, match="WS_EFFECT_PARITY_FAILED"):
            await client.release_after_effect_parity(lambda mass: asyncio.sleep(0, result=mass.effects == 1))
        assert client._cm_ws_phase == "BUFFERING"
        assert client._cm_ws_failure == "WS_EFFECT_PARITY_FAILED"
    asyncio.run(run())


def test_ws_buffer_releases_once_after_effect_and_latches_dispatch_failure(monkeypatch):
    from coinmaster.ops import hl_live_execution as owner
    monkeypatch.setattr(owner, "_WS_HANDLERS", ((Event, "handle"),))
    async def run():
        client = Probe()
        event = Event()
        client._handle_msg(event)
        await client.release_after_effect_parity(lambda mass: asyncio.sleep(0, result=mass.effects == 1))
        assert client._cm_ws_phase == "LIVE"
        assert client.effects == 1
        bad = Probe(fail=True)
        bad._handle_msg(event)
        with pytest.raises(RuntimeError, match="native handler failed"):
            await bad.release_after_effect_parity(lambda mass: asyncio.sleep(0, result=True))
        with pytest.raises(RuntimeError, match="RECOVERY_REQUIRED:WS_DISPATCH_FAILED"):
            bad._cm_require_healthy()
    asyncio.run(run())


def test_ws_unknown_and_overflow_fail_closed(monkeypatch):
    from coinmaster.ops import hl_live_execution as owner
    monkeypatch.setattr(owner, "_WS_HANDLERS", ((Event, "handle"),))
    unknown = Probe()
    unknown._handle_msg(object())
    with pytest.raises(RuntimeError, match="RECOVERY_REQUIRED:WS_UNKNOWN_EVENT"):
        unknown._cm_require_healthy()
    full = Probe(limit=1)
    full._handle_msg(Event())
    full._handle_msg(Event())
    with pytest.raises(RuntimeError, match="RECOVERY_REQUIRED:WS_BUFFER_OVERFLOW"):
        full._cm_require_healthy()


def test_pending_native_fill_cannot_release_on_handler_no_effect(monkeypatch):
    from coinmaster.ops import hl_live_execution as owner
    monkeypatch.setattr(owner, "_WS_HANDLERS", ((Event, "handle"),))
    async def run():
        client = Probe(no_effect=True)
        client._pending_fills = {"CM05-OWNED": [Event()]}
        client._handle_msg(Event())
        with pytest.raises(RuntimeError, match="WS_FILL_PENDING_WITHOUT_NATIVE_EFFECT"):
            await client.release_after_effect_parity(lambda _: asyncio.sleep(0, result=True))
        assert not client.recovery_healthy()
    asyncio.run(run())


def test_post_release_ws_error_revokes_bound_strategy_gate(monkeypatch):
    from coinmaster.ops import hl_live_execution as owner
    monkeypatch.setattr(owner, "_WS_HANDLERS", ((Event, "handle"),))
    async def run():
        client = Probe()
        active = SimpleNamespace(recovery_confirmed=True)
        client.bind_recovery_revocation(lambda: setattr(active, "recovery_confirmed", False))
        await client.release_after_effect_parity(lambda _: asyncio.sleep(0, result=True))
        assert client.recovery_healthy()
        client._handle_msg(object())
        assert active.recovery_confirmed is False
        assert not client.recovery_healthy()
    asyncio.run(run())


def test_strict_info_generation_failure_latches_and_revokes():
    class FailedInfo(QualifiedInfoBoundary):
        def __init__(self):
            scope = NativeLiveRecoveryScope(ACCOUNT, "", 1, None, (), frozenset({"BTC"}))
            async def failed(_):
                raise TimeoutError("raw Info timed out")
            self.configure_info_boundary(scope, failed, lambda: frozenset())
            self._clock = SimpleNamespace(timestamp_ns=lambda: 2_000_000)
        _cache = SimpleNamespace(orders=lambda **_: ())
        venue = SimpleNamespace(value="HYPERLIQUID")
    async def run():
        client = FailedInfo()
        active = SimpleNamespace(recovery_confirmed=True)
        client.bind_recovery_revocation(lambda: setattr(active, "recovery_confirmed", False))
        with pytest.raises(ValueError, match="INFO_TRANSPORT_FAILED"):
            await client.generate_mass_status()
        assert client._cm_ws_failure == "INFO_GENERATION_FAILED"
        assert active.recovery_confirmed is False
    asyncio.run(run())


def test_bound_factory_checks_durable_ids_before_native_construction():
    scope = NativeLiveRecoveryScope(
        ACCOUNT, "", 1, None, (("CM05-ORDER", "0x" + "b" * 32, None),), frozenset({"BTC"}),
    )
    from test_live_native_report_recovery import _strategy
    mismatch = SimpleNamespace(all_submissions=lambda: [])
    with pytest.raises(ValueError, match="RECOVERY_DURABLE_SCOPE_MISMATCH"):
        ScopedHyperliquidExecClientFactory.bind(scope, mismatch, _strategy())
    leases = []
    matching = SimpleNamespace(
        all_submissions=lambda: [{"client_order_id": "CM05-ORDER"}],
        applied_fill_ids=lambda: frozenset(),
        acquire_live_account=lambda *args, **kwargs: leases.append((args, kwargs)),
    )
    strategy = _strategy()
    bound = ScopedHyperliquidExecClientFactory.bind(scope, matching, strategy)
    assert bound._scope is scope and bound._runtime is matching and bound._strategy is strategy
    assert leases[0][0] == (ACCOUNT, "HYPERLIQUID")
    assert ScopedHyperliquidExecClientFactory._scope is None


def test_socket_loss_without_native_disconnect_revokes_and_stays_latched_after_reconnect(monkeypatch):
    from coinmaster.ops import hl_live_execution as owner
    monkeypatch.setattr(owner, "_WS_HANDLERS", ((Event, "handle"),))
    async def run():
        client = Probe()
        revoked = []
        client.bind_recovery_revocation(lambda: revoked.append(True))
        await client.release_after_effect_parity(
            lambda _: asyncio.sleep(0, result=True), monitor_interval_secs=0.01,
        )
        assert client.recovery_healthy()
        client.socket.active = False
        assert not client.recovery_healthy()
        assert client._cm_ws_failure == "WS_TRANSPORT_INACTIVE"
        client.socket.active = True
        assert not client.recovery_healthy()
        assert revoked
    asyncio.run(run())


def test_periodic_strict_parity_failure_revokes_without_disconnect(monkeypatch):
    from coinmaster.ops import hl_live_execution as owner
    monkeypatch.setattr(owner, "_WS_HANDLERS", ((Event, "handle"),))
    async def run():
        client = Probe()
        revoked = []
        checks = []
        client.bind_recovery_revocation(lambda: revoked.append(True))
        async def verify(_):
            checks.append(True)
            return len(checks) == 1
        await client.release_after_effect_parity(verify, monitor_interval_secs=0.01)
        assert client.recovery_healthy()
        await asyncio.sleep(0.85)
        assert len(checks) >= 2
        assert not client.recovery_healthy()
        assert client._cm_ws_failure == "WS_PERIODIC_EFFECT_PARITY_FAILED"
        assert revoked
    asyncio.run(run())


def test_bound_handover_rejects_open_funding_unknown_and_latches_before_release():
    from nautilus_trader.model.identifiers import AccountId, Venue
    from coinmaster.ops.hl_live_execution import bind_clean_flat_live_handover
    from test_live_native_report_recovery import _strategy

    async def run():
        client = Probe()
        client.venue = Venue("HYPERLIQUID")
        client.account_id = AccountId("HYPERLIQUID-master")
        client._cm_scope = NativeLiveRecoveryScope(
            ACCOUNT, "", 1, None,
            (("HLTG-PENDING", "0x" + "b" * 32, None),), frozenset({"BTC", "SOL"}),
        )
        client._cm_last_receipt = object()
        client._clock = SimpleNamespace(timestamp_ns=lambda: 2_000_000)
        strategy = _strategy()
        client._cache = strategy.cache
        client._msgbus = strategy.msgbus
        client.trader_id = strategy.trader_id
        async def mass(_lookback=None):
            return SimpleNamespace(
                account_id=client.account_id, venue=client.venue,
                order_reports={}, fill_reports={}, position_reports={},
            )
        client.generate_mass_status = mass
        runtime = SimpleNamespace(
            all_submissions=lambda: [], applied_fill_ids=lambda: frozenset(),
            strategy_checkpoint=lambda: None,
        )
        bind_clean_flat_live_handover(client, strategy, runtime)
        with pytest.raises(ValueError, match="LIVE_OPEN_FUNDING_CURSOR_UNPROVEN"):
            await strategy._post_drain_verifier()
        assert strategy.recovery_confirmed is False
        assert client._cm_ws_failure == "WS_EFFECT_PARITY_FAILED"
        assert client._cm_ws_phase == "BUFFERING"
    asyncio.run(run())


def test_handover_rejects_other_instrument_or_dex_scope_before_attach():
    import msgspec
    from nautilus_trader.model.identifiers import InstrumentId, Venue
    from coinmaster.ops.hl_live_execution import bind_clean_flat_live_handover
    from test_live_native_report_recovery import _strategy

    client = Probe()
    client.venue = Venue("HYPERLIQUID")
    client._cm_scope = NativeLiveRecoveryScope(
        ACCOUNT, "", 1, None, (), frozenset({"BTC", "SOL"}),
    )
    runtime = SimpleNamespace(all_submissions=lambda: [])
    correct = _strategy()
    wrong = type(correct)(msgspec.structs.replace(
        correct.config, btc_id=InstrumentId.from_str("ETH-USD-PERP.HYPERLIQUID"),
    ))
    with pytest.raises(RuntimeError, match="INSTRUMENT_SCOPE_MISMATCH"):
        bind_clean_flat_live_handover(client, wrong, runtime)
    assert wrong._post_drain_verifier is None
    client._cm_scope = NativeLiveRecoveryScope(
        ACCOUNT, "other-dex", 1, None, (), frozenset({"BTC", "SOL"}),
    )
    with pytest.raises(RuntimeError, match="INSTRUMENT_SCOPE_MISMATCH"):
        bind_clean_flat_live_handover(client, correct, runtime)
    client._cm_scope = NativeLiveRecoveryScope(
        ACCOUNT, "", 1, None, (), frozenset({"BTC"}),
    )
    with pytest.raises(RuntimeError, match="INSTRUMENT_SCOPE_MISMATCH"):
        bind_clean_flat_live_handover(client, correct, runtime)


def test_handover_rejects_different_native_cache_after_start():
    from nautilus_trader.model.identifiers import AccountId, Venue
    from coinmaster.ops.hl_live_execution import bind_clean_flat_live_handover
    from test_live_native_report_recovery import _strategy

    async def run():
        client = Probe()
        client.venue = Venue("HYPERLIQUID")
        client.account_id = AccountId("HYPERLIQUID-master")
        client._cm_scope = NativeLiveRecoveryScope(
            ACCOUNT, "", 1, None, (), frozenset({"BTC", "SOL"}),
        )
        strategy = _strategy()
        client._cache = object()  # Different owner, even if both venues say HYPERLIQUID.
        client._msgbus = strategy.msgbus
        client.trader_id = strategy.trader_id
        async def mass(_lookback=None):
            return SimpleNamespace(
                account_id=client.account_id, venue=client.venue,
                order_reports={}, fill_reports={}, position_reports={},
            )
        client.generate_mass_status = mass
        runtime = SimpleNamespace(
            all_submissions=lambda: [], applied_fill_ids=lambda: frozenset(),
            strategy_checkpoint=lambda: None,
        )
        bind_clean_flat_live_handover(client, strategy, runtime)
        with pytest.raises(ValueError, match="NATIVE_ROUTE_MISMATCH"):
            await strategy._post_drain_verifier()
        assert not strategy.recovery_confirmed
        assert client._cm_ws_failure == "WS_EFFECT_PARITY_FAILED"
    asyncio.run(run())


def test_current_process_scope_tracks_durable_cloid_oid_and_revision_without_accepting_foreign_order():
    from nautilus_trader.model.identifiers import Venue
    from coinmaster.ops.hl_info_receipt import IncompleteInfoReport

    client = Probe()
    client.venue = Venue("HYPERLIQUID")
    client._cm_bootstrapped = True
    order = SimpleNamespace(
        client_order_id="HLTG-OWNED-1", venue_order_id="7", status="ACCEPTED",
        filled_qty="0", trade_ids=[],
    )
    current = [order]
    revision = [1]
    client._cache = SimpleNamespace(orders=lambda **_: current)
    client._cm_runtime = SimpleNamespace(
        native_revision=lambda: revision[0],
        all_submissions=lambda: [{"client_order_id": "HLTG-OWNED-1"}],
        applied_fill_ids=lambda: frozenset(),
    )
    scope, observed_revision, orders, fills, signature = client._cm_owned_scope()
    assert observed_revision == 1 and orders == (order,) and fills == frozenset()
    assert scope.durable_orders[0][0] == "HLTG-OWNED-1"
    assert scope.durable_orders[0][2] == 7
    assert scope.durable_orders[0][1].startswith("0x")
    order.venue_order_id = None  # Accepted-before-ACK remains exact CLOID-only.
    assert client._cm_owned_scope()[0].durable_orders[0][2] is None
    current.append(SimpleNamespace(
        client_order_id="FOREIGN", venue_order_id="8", status="ACCEPTED",
        filled_qty="0", trade_ids=[],
    ))
    with pytest.raises(IncompleteInfoReport, match="LIVE_FOREIGN_NATIVE_ORDER"):
        client._cm_owned_scope()
    current.pop()
    revision[0] += 1
    assert client._cm_owned_scope()[1] == 2


def test_current_process_owned_partial_tp_uses_dynamic_strict_info_generation():
    from copy import deepcopy
    from nautilus_trader.model.identifiers import AccountId, ClientId, Venue
    from test_hl_info_receipt import FakeInfo
    from test_hl_qualified_reports import CLIENT, CLOID, raw, native_order
    from test_hl_stageg_sandbox_lifecycle import HL_BTC, HL_SOL

    async def run():
        data = deepcopy(raw())
        data["clearinghouseState"]["crossMarginSummary"] = deepcopy(
            data["clearinghouseState"]["marginSummary"]
        )
        data["userRole"] = {"role": "user"}
        data["userAbstraction"] = "disabled"
        data["userDexAbstraction"] = False
        info = FakeInfo(data)
        order = native_order()
        class NativeProbe(QualifiedInfoBoundary):
            pass
        client = NativeProbe()
        client.configure_info_boundary(
            NativeLiveRecoveryScope(ACCOUNT, "", 100, 9, ((CLIENT, CLOID, 7),), frozenset({"BTC", "SOL"})),
            info, lambda: frozenset({"8", "9"}),
        )
        client._cm_scope = NativeLiveRecoveryScope(
            ACCOUNT, "", 100, 9, ((CLIENT, CLOID, 7),), frozenset({"BTC", "SOL"}),
        )
        client._cm_info = info
        client._cm_bootstrapped = True
        client._cm_runtime = SimpleNamespace(
            native_revision=lambda: 2,
            all_submissions=lambda: [{"client_order_id": CLIENT}],
            applied_fill_ids=lambda: frozenset({"8", "9"}),
        )
        client._cm_applied_fill_ids = client._cm_runtime.applied_fill_ids
        client._cache = SimpleNamespace(
            orders=lambda **_: (order,),
            instrument=lambda identity: {HL_BTC.id: HL_BTC, HL_SOL.id: HL_SOL}.get(identity),
        )
        client._clock = SimpleNamespace(timestamp_ns=lambda: 200_000_000)
        client.account_id = AccountId("HYPERLIQUID-master")
        client.id = ClientId("HYPERLIQUID")
        client.venue = Venue("HYPERLIQUID")
        mass = await client.generate_mass_status()
        assert len(mass.order_reports) == len(mass.fill_reports) == len(mass.position_reports) == 1
        assert client._cm_last_receipt.end_ms == 201
        assert client._cm_ws_failure is None
        assert {call["type"] for call in info.calls} >= {
            "frontendOpenOrders", "clearinghouseState", "orderStatus", "userFillsByTime",
        }
    asyncio.run(run())


def _owned_raw_client(info, revision, order, rows, *, anchor_tid=9):
    from nautilus_trader.model.identifiers import AccountId, ClientId, Venue
    from test_hl_qualified_reports import CLIENT, CLOID
    from test_hl_stageg_sandbox_lifecycle import HL_BTC, HL_SOL

    class NativeProbe(QualifiedInfoBoundary):
        pass

    client = NativeProbe()
    client.configure_info_boundary(
        NativeLiveRecoveryScope(
            ACCOUNT, "", 100, anchor_tid,
            ((CLIENT, CLOID, 7),) if anchor_tid is not None else (),
            frozenset({"BTC", "SOL"}),
        ), info, lambda: frozenset({"8", "9"}) if anchor_tid is not None else frozenset(),
    )
    client._cm_bootstrapped = True
    client._cm_runtime = SimpleNamespace(
        native_revision=lambda: revision[0],
        all_submissions=lambda: rows,
        applied_fill_ids=lambda: frozenset({"8", "9"}) if anchor_tid is not None else frozenset(),
    )
    client._cache = SimpleNamespace(
        orders=lambda **_: (order,),
        instrument=lambda identity: {HL_BTC.id: HL_BTC, HL_SOL.id: HL_SOL}.get(identity),
    )
    client._clock = SimpleNamespace(timestamp_ns=lambda: 200_000_000)
    client.account_id = AccountId("HYPERLIQUID-master")
    client.id = ClientId("HYPERLIQUID")
    client.venue = Venue("HYPERLIQUID")
    return client


@pytest.mark.parametrize("observed_revision_change", [False, True])
@pytest.mark.parametrize("race_kind, error_code", [
    ("partial", "OPEN_ORDER_STATUS_FIELD_MISMATCH"),
    ("cancel", "ORDER_OPEN_STATUS_MISMATCH"),
])
def test_mid_sweep_partial_mismatch_retries_only_after_native_revision_moves(
    observed_revision_change, race_kind, error_code,
):
    from copy import deepcopy
    from coinmaster.ops.hl_info_receipt import IncompleteInfoReport
    from test_hl_info_receipt import FakeInfo
    from test_hl_qualified_reports import CLIENT, native_order, raw

    data = deepcopy(raw())
    data["clearinghouseState"]["crossMarginSummary"] = deepcopy(data["clearinghouseState"]["marginSummary"])
    data.update(userRole={"role": "user"}, userAbstraction="disabled", userDexAbstraction=False)
    revision = [2]

    class RacingInfo(FakeInfo):
        async def __call__(self, body):
            result = await super().__call__(body)
            if body["type"] == "orderStatus" and self.calls.count(body) == 1:
                if race_kind == "partial":
                    result["order"]["order"]["sz"] = "0.024"
                else:
                    result["order"]["status"] = "canceled"
                if observed_revision_change:
                    revision[0] += 1
            return result

    info = RacingInfo(data)
    client = _owned_raw_client(info, revision, native_order(), [{"client_order_id": CLIENT}])
    if observed_revision_change:
        mass = asyncio.run(client.generate_mass_status())
        assert len(mass.order_reports) == 1
        assert len([call for call in info.calls if call["type"] == "orderStatus"]) == 3
        assert client._cm_ws_failure is None
    else:
        with pytest.raises(IncompleteInfoReport, match=error_code):
            asyncio.run(client.generate_mass_status())
        assert len([call for call in info.calls if call["type"] == "orderStatus"]) == 1
        assert client._cm_ws_failure == "INFO_GENERATION_FAILED"


def test_native_local_denial_requires_no_venue_order_status_but_unknown_ack_does():
    from copy import deepcopy
    from nautilus_trader.core.uuid import UUID4
    from nautilus_trader.model.enums import OrderSide, TimeInForce
    from nautilus_trader.model.events import OrderDenied
    from nautilus_trader.model.identifiers import ClientOrderId
    from nautilus_trader.model.objects import Quantity
    from nautilus_trader.model.orders import MarketOrder
    from coinmaster.ops.hl_info_receipt import IncompleteInfoReport
    from test_hl_info_receipt import FakeInfo, BASE
    from test_hl_qualified_reports import CLIENT, TRADER, STRATEGY
    from test_hl_stageg_sandbox_lifecycle import HL_BTC

    order = MarketOrder(
        TRADER, STRATEGY, HL_BTC.id, ClientOrderId(CLIENT), OrderSide.BUY,
        Quantity.from_str("0.01000"), UUID4(), 90_000_000,
        time_in_force=TimeInForce.IOC,
    )
    order.apply(OrderDenied(
        TRADER, STRATEGY, HL_BTC.id, ClientOrderId(CLIENT),
        "native local risk deny", UUID4(), 90_000_001,
    ))
    data = deepcopy(BASE)
    data["frontendOpenOrders"] = []
    data["clearinghouseState"]["assetPositions"] = []
    data["clearinghouseState"]["crossMarginSummary"] = deepcopy(data["clearinghouseState"]["marginSummary"])
    data["userFillsByTime"] = []
    data.update(userRole={"role": "user"}, userAbstraction="disabled", userDexAbstraction=False)
    info = FakeInfo(data)
    rows = [{"client_order_id": CLIENT, "state": "TERMINAL"}]
    client = _owned_raw_client(info, [3], order, rows, anchor_tid=None)
    mass = asyncio.run(client.generate_mass_status())
    assert not mass.order_reports and not mass.fill_reports
    assert "orderStatus" not in [call["type"] for call in info.calls]
    assert rows[0]["client_order_id"] == CLIENT  # Durable history was retained.
    rows[0]["state"] = "SUBMITTING"  # Unknown ACK is not a local denial.
    info.data["orderStatus"] = {"status": "unknownOid"}
    with pytest.raises(IncompleteInfoReport, match="ORDER_STATUS_UNKNOWN"):
        asyncio.run(client.generate_mass_status())
    assert client._cm_ws_failure == "INFO_GENERATION_FAILED"


def test_monitor_blocks_increase_through_retry_then_restores_only_after_parity(monkeypatch):
    from coinmaster.ops import hl_live_execution as owner
    from test_live_native_report_recovery import _strategy

    monkeypatch.setattr(owner, "_WS_HANDLERS", ((Event, "handle"),))

    async def run():
        client = Probe()
        strategy = _strategy()
        strategy.recovery_confirmed = True
        first_retry = asyncio.Event()
        resumed = asyncio.Event()
        checks = [0]
        client.bind_recovery_revocation(lambda: setattr(strategy, "recovery_confirmed", False))
        client.bind_recovery_suspension(
            lambda: setattr(strategy, "recovery_confirmed", False),
            lambda: (setattr(strategy, "recovery_confirmed", True), resumed.set()),
        )
        async def verify(_):
            checks[0] += 1
            if checks[0] == 2:
                first_retry.set()
                return False
            return True
        await client.release_after_effect_parity(verify, monitor_interval_secs=0.01)
        await asyncio.wait_for(first_retry.wait(), timeout=1)
        with pytest.raises(RuntimeError, match="RECOVERY_NOT_CONFIRMED"):
            strategy._require_recovery_confirmed()
        await asyncio.wait_for(resumed.wait(), timeout=1)
        assert strategy.recovery_confirmed is True
        assert client._cm_ws_failure is None
        client._cm_parity_task.cancel()
        try:
            await client._cm_parity_task
        except asyncio.CancelledError:
            pass
    asyncio.run(run())



def test_live_account_lease_excludes_same_account_across_journals_and_processes(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path
    from coinmaster.ops.paper import PaperRuntime

    lock_root = tmp_path / "account-leases"
    first = PaperRuntime(tmp_path / "first.sqlite", "first", 10**20)
    second = PaperRuntime(tmp_path / "second.sqlite", "second", 10**20)
    try:
        first.acquire_live_account(ACCOUNT, "HYPERLIQUID", lock_root=lock_root)
        with pytest.raises(RuntimeError, match="LIVE_ACCOUNT_ALREADY_OWNED"):
            second.acquire_live_account(ACCOUNT.upper().replace("0X", "0x"), "HYPERLIQUID", lock_root=lock_root)
        child = """
from pathlib import Path
from coinmaster.ops.paper import PaperRuntime
import sys
runtime = PaperRuntime(Path(sys.argv[1]), "child", 10**20)
try:
    runtime.acquire_live_account(sys.argv[3], "HYPERLIQUID", lock_root=Path(sys.argv[2]))
except RuntimeError as error:
    print(str(error))
else:
    print("UNEXPECTED_ACQUIRED")
finally:
    runtime.close()
"""
        environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        result = subprocess.run(
            [sys.executable, "-c", child, str(tmp_path / "third.sqlite"), str(lock_root), ACCOUNT],
            env=environment, capture_output=True, text=True, check=True,
        )
        assert result.stdout.strip() == "LIVE_ACCOUNT_ALREADY_OWNED"
    finally:
        first.close()
    try:
        second.acquire_live_account(ACCOUNT, "HYPERLIQUID", lock_root=lock_root)
    finally:
        second.close()


def test_on_demand_strict_refresh_uses_shared_budget_and_never_resumes_on_exhaustion():
    from copy import deepcopy
    from test_hl_info_receipt import FakeInfo
    from test_hl_qualified_reports import native_order, raw

    data = deepcopy(raw())
    data["clearinghouseState"]["crossMarginSummary"] = deepcopy(data["clearinghouseState"]["marginSummary"])
    data.update(userRole={"role": "user"}, userAbstraction="disabled", userDexAbstraction=False)
    info = FakeInfo(data)
    client = _owned_raw_client(info, [2], native_order(), [{"client_order_id": str(native_order().client_order_id)}])
    gate = [False]
    client._cm_ws_phase = "LIVE"
    client._cm_transport_ok = lambda: True
    client.bind_recovery_suspension(lambda: gate.__setitem__(0, False), lambda: gate.__setitem__(0, True))
    async def verify(_mass):
        return True
    client._cm_parity_verifier = verify

    async def run():
        assert client.request_effect_parity_refresh()
        await client._cm_refresh_task
        assert gate[0] is True and client._cm_ws_failure is None
        assert client.request_effect_parity_refresh()
        await client._cm_refresh_task
        assert gate[0] is True and client._cm_ws_failure is None
        assert client.request_effect_parity_refresh()
        await client._cm_refresh_task
        assert gate[0] is True  # A third clean generation still fits the shared limit.
        assert client.request_effect_parity_refresh()
        await client._cm_refresh_task
        assert gate[0] is False  # Budget exhausted; no accepted stale receipt.
        assert client._cm_last_receipt is None
        assert sum(weight for _, weight in client._cm_info_usage) <= 1000
    asyncio.run(run())
