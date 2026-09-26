"""Read-only HL account observer tests; fake Info transport, no exchange calls."""
from __future__ import annotations

import asyncio
import json
from copy import deepcopy

from coinmaster.ops.hl_readonly_observer import (
    ACCOUNT_ENV, INFO_URL, ReadOnlyAccountObserver, ReadOnlyInfoHttp,
)
from test_hl_info_receipt import ACCOUNT, ANCHOR, BASE, CLOID, FakeInfo


class RoleInfo(FakeInfo):
    def __init__(self, data=None, failure=None, role="user"):
        super().__init__(data=data, failure=failure)
        self.role = role

    async def __call__(self, body):
        if body["type"] == "userRole":
            self.calls.append(dict(body))
            if self.failure == "userRole":
                raise RuntimeError("offline")
            return {"role": self.role}
        return await super().__call__(body)


def _observer(info, **changes):
    args = dict(
        account_ref=ACCOUNT, info=info, dex="", anchor_ms=100, anchor_tid=9,
        expected_orders={CLOID: None}, owned_coins=frozenset({"BTC", "SOL"}),
        max_age_ms=10,
    )
    args.update(changes)
    return ReadOnlyAccountObserver(**args)


def test_conditional_account_read_disconnect_and_resync():
    fake = RoleInfo()
    observer = _observer(fake)
    initial = observer.status(now_ms=200)
    assert initial.connection_state == "UNKNOWN"
    assert initial.recovery_required and not initial.orders_enabled and not initial.retry_uncertain_orders
    read = asyncio.run(observer.observe(now_ms=200))
    assert fake.calls[0] == {"type": "userRole", "user": ACCOUNT}
    assert read.connection_state == "CONNECTED_INFO"
    assert read.evidence_state == "CONDITIONAL_ONLY"
    assert read.account_value == "9999.19"
    assert (read.open_orders, read.positions, read.fills) == (1, 1, 1)
    assert read.recovery_required and not read.live_order_capability
    observer.disconnect()
    disconnected = observer.status(now_ms=201)
    assert disconnected.connection_state == "RECOVERY_REQUIRED"
    assert disconnected.evidence_state == "UNKNOWN"
    assert disconnected.account_value is None
    assert asyncio.run(observer.observe(now_ms=202)).connection_state == "CONNECTED_INFO"
    assert observer.status(now_ms=213).connection_state == "STALE"
    assert observer.status(now_ms=213).account_value is None


def test_error_partial_and_wrong_role_clear_previous_read():
    for case in ("userRole", "clearinghouseState", "userFillsByTime", "partial", "agent"):
        fake = RoleInfo()
        observer = _observer(fake)
        assert asyncio.run(observer.observe(now_ms=200)).connection_state == "CONNECTED_INFO"
        if case == "partial":
            fake.data["userFillsByTime"] = [{**ANCHOR, "tid": 10}]
        elif case == "agent":
            fake.role = "agent"
        else:
            fake.failure = case
        state = asyncio.run(observer.observe(now_ms=201))
        assert state.connection_state == "RECOVERY_REQUIRED"
        assert state.evidence_state == "UNKNOWN"
        assert state.account_value is None
        assert state.recovery_required and not state.orders_enabled
        assert not state.retry_uncertain_orders


def test_disconnection_during_inflight_read_cannot_reopen_observer():
    class HeldInfo(RoleInfo):
        def __init__(self):
            super().__init__()
            self.started = asyncio.Event()
            self.release = asyncio.Event()

        async def __call__(self, body):
            if body["type"] == "userRole":
                self.started.set()
                await self.release.wait()
            return await super().__call__(body)

    async def scenario():
        fake = HeldInfo()
        observer = _observer(fake)
        pending = asyncio.create_task(observer.observe(now_ms=200))
        await fake.started.wait()
        observer.disconnect()
        fake.release.set()
        state = await pending
        assert state.connection_state == "RECOVERY_REQUIRED"
        assert state.evidence_state == "UNKNOWN"

    asyncio.run(scenario())


def test_genuine_empty_account_is_observed_but_not_takeover_ready():
    data = deepcopy(BASE)
    data["frontendOpenOrders"] = []
    data["clearinghouseState"]["assetPositions"] = []
    data["clearinghouseState"]["marginSummary"]["accountValue"] = "0"
    data["userFillsByTime"] = []
    observer = _observer(
        RoleInfo(data), anchor_tid=None, expected_orders={},
    )
    state = asyncio.run(observer.observe(now_ms=200))
    assert (state.account_value, state.open_orders, state.positions, state.fills) == ("0", 0, 0, 0)
    assert state.evidence_state == "CONDITIONAL_ONLY"
    assert state.recovery_required


def test_account_reference_environment_and_allowlisted_info_transport():
    assert ReadOnlyAccountObserver.from_environment(
        {ACCOUNT_ENV: ACCOUNT}, info=RoleInfo(), dex="", anchor_ms=0,
        anchor_tid=None, expected_orders={}, owned_coins=frozenset({"BTC"}),
    ).account_ref == ACCOUNT
    try:
        ReadOnlyAccountObserver.from_environment(
            {}, info=RoleInfo(), dex="", anchor_ms=0,
            anchor_tid=None, expected_orders={}, owned_coins=frozenset({"BTC"}),
        )
    except ValueError as error:
        assert str(error) == "PUBLIC_ACCOUNT_REF_MISSING"
    else:
        raise AssertionError("MISSING_ACCOUNT_ACCEPTED")

    class Response:
        status = 200
        headers = {"Content-Type": "application/json"}
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self, _limit):
            return b'{"role":"user"}'

    class Opener:
        def __init__(self):
            self.requests = []
        def open(self, request, timeout):
            self.requests.append((request, timeout))
            return Response()

    transport = ReadOnlyInfoHttp(ACCOUNT)
    opener = Opener()
    transport._opener = opener
    assert asyncio.run(transport({"type": "userRole", "user": ACCOUNT})) == {"role": "user"}
    request, timeout = opener.requests[0]
    assert request.full_url == INFO_URL
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {"type": "userRole", "user": ACCOUNT}
    assert timeout == 5
    for body in (
        {"type": "exchange", "user": ACCOUNT},
        {"type": "userRole", "user": "0x" + "b" * 40},
        {"type": "userRole", "user": ACCOUNT, "secret": "forbidden"},
    ):
        try:
            asyncio.run(transport(body))
        except ValueError:
            pass
        else:
            raise AssertionError("FORBIDDEN_INFO_REQUEST_ACCEPTED")
    assert len(opener.requests) == 1
