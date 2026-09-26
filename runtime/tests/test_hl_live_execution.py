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
        _cache = SimpleNamespace()
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
    matching = SimpleNamespace(
        all_submissions=lambda: [{"client_order_id": "CM05-ORDER"}],
        applied_fill_ids=lambda: frozenset(),
    )
    strategy = _strategy()
    bound = ScopedHyperliquidExecClientFactory.bind(scope, matching, strategy)
    assert bound._scope is scope and bound._runtime is matching and bound._strategy is strategy
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
        await asyncio.sleep(0.03)
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
