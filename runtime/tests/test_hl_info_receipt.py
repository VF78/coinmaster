"""Read-only fake Hyperliquid Info receipt; no network or execution client."""
from __future__ import annotations

import asyncio
from copy import deepcopy

import pytest

from coinmaster.ops.hl_info_receipt import IncompleteInfoReport, collect_info_receipt


ACCOUNT = "0x" + "a" * 40
CLOID = "0x" + "b" * 32
ORDER = {
    "coin": "BTC", "oid": 7, "cloid": CLOID, "sz": "0.025",
    "origSz": "0.03", "side": "A", "reduceOnly": True,
}
ANCHOR = {
    "coin": "BTC", "oid": 7, "tid": 9, "time": 100,
    "side": "A", "sz": "0.005", "px": "60010",
    "fee": "0.045", "feeToken": "USDC", "hash": "0xabc",
}
BASE = {
    "frontendOpenOrders": [ORDER],
    "clearinghouseState": {
        "assetPositions": [{"position": {"coin": "BTC", "szi": "0.025"}}],
        "marginSummary": {"accountValue": "9999.19"},
    },
    "orderStatus": {"status": "order", "order": {"order": ORDER, "status": "open"}},
    "userFillsByTime": [ANCHOR],
}


class FakeInfo:
    def __init__(self, data=None, failure=None):
        self.data = deepcopy(data or BASE)
        self.failure = failure
        self.calls = []

    async def __call__(self, body):
        self.calls.append(dict(body))
        if body["type"] == self.failure:
            raise RuntimeError("read failure")
        value = self.data[body["type"]]
        if body["type"] == "userFillsByTime" and isinstance(value, list):
            return [row for row in value if body["startTime"] <= row["time"] <= body["endTime"]]
        return deepcopy(value)


def collect(fake=None, **kwargs):
    return asyncio.run(collect_info_receipt(
        fake or FakeInfo(), account=ACCOUNT, dex="", anchor_ms=100,
        anchor_tid=9, end_ms=200, expected_orders={CLOID: None},
        owned_coins=frozenset({"BTC", "SOL"}), **kwargs,
    ))


def test_partial_tp_conditional_receipt_and_lost_ack_cloid_resolution():
    fake = FakeInfo()
    receipt = collect(fake)
    assert receipt.conditional_only and receipt.fill_anchor_proven
    assert len(receipt.fills) == len(receipt.open_orders) == len(receipt.positions) == 1
    assert fake.calls[:3] == [
        {"type": "frontendOpenOrders", "user": ACCOUNT, "dex": ""},
        {"type": "clearinghouseState", "user": ACCOUNT, "dex": ""},
        {"type": "orderStatus", "user": ACCOUNT, "oid": CLOID},
    ]
    assert fake.calls[-1] == {
        "type": "userFillsByTime", "user": ACCOUNT,
        "startTime": 100, "endTime": 200, "aggregateByTime": False,
    }


def test_genuine_empty_report_stays_conditional_without_fill_anchor():
    data = deepcopy(BASE)
    data["frontendOpenOrders"] = []
    data["clearinghouseState"]["assetPositions"] = []
    data["userFillsByTime"] = []
    receipt = asyncio.run(collect_info_receipt(
        FakeInfo(data), account=ACCOUNT, dex="", anchor_ms=100,
        anchor_tid=None, end_ms=200, expected_orders={},
        owned_coins=frozenset({"BTC"}),
    ))
    assert not receipt.open_orders and not receipt.positions and not receipt.fills
    assert receipt.conditional_only and not receipt.fill_anchor_proven


@pytest.mark.parametrize("failure", ["frontendOpenOrders", "clearinghouseState", "orderStatus", "userFillsByTime"])
def test_transport_failure_fails_closed(failure):
    with pytest.raises(IncompleteInfoReport, match="INFO_TRANSPORT_FAILED"):
        collect(FakeInfo(failure=failure))


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("frontendOpenOrders", None, "MALFORMED"),
        ("clearinghouseState", [], "MALFORMED"),
        ("orderStatus", {"status": "unknownOid"}, "ORDER_STATUS_UNKNOWN"),
        ("userFillsByTime", None, "MALFORMED_OR_OVERSIZE"),
    ],
)
def test_malformed_and_unknown_fail_closed(field, value, error):
    data = deepcopy(BASE)
    data[field] = value
    with pytest.raises(IncompleteInfoReport, match=error):
        collect(FakeInfo(data))


def test_foreign_open_order_and_position_fail_closed():
    for field, replacement in (
        ("frontendOpenOrders", [{**ORDER, "oid": 8}]),
        ("clearinghouseState", {
            "assetPositions": [{"position": {"coin": "ETH", "szi": "1"}}],
            "marginSummary": {"accountValue": "9999"},
        }),
    ):
        data = deepcopy(BASE)
        data[field] = replacement
        with pytest.raises(IncompleteInfoReport):
            collect(FakeInfo(data))


def test_missing_anchor_is_retention_or_gap_failure():
    data = deepcopy(BASE)
    data["userFillsByTime"] = [{**ANCHOR, "tid": 10, "time": 101}]
    with pytest.raises(IncompleteInfoReport, match="ANCHOR_NOT_RETAINED"):
        collect(FakeInfo(data))


def test_duplicate_fill_deduplicates_without_double_counting():
    data = deepcopy(BASE)
    data["userFillsByTime"] = [ANCHOR, deepcopy(ANCHOR)]
    receipt = collect(FakeInfo(data))
    assert len(receipt.fills) == 1


def test_conflicting_duplicate_fill_fails_closed():
    data = deepcopy(BASE)
    data["userFillsByTime"] = [ANCHOR, {**ANCHOR, "sz": "0.006"}]
    with pytest.raises(IncompleteInfoReport, match="CONFLICTING_DUPLICATE_FILL"):
        collect(FakeInfo(data))


def test_capped_window_splits_and_saturated_millisecond_fails_closed():
    data = deepcopy(BASE)
    data["userFillsByTime"] = [
        {**ANCHOR, "tid": index + 9, "time": 100 + index // 1000}
        for index in range(2000)
    ]
    fake = FakeInfo(data)
    receipt = collect(fake)
    assert len(receipt.fills) == 2000
    assert len([x for x in fake.calls if x["type"] == "userFillsByTime"])  > 3
    data["userFillsByTime"] = [
        {**ANCHOR, "tid": index + 9} for index in range(2000)
    ]
    with pytest.raises(IncompleteInfoReport, match="SATURATED_FILL_TIMESTAMP"):
        collect(FakeInfo(data))


def test_order_status_and_cloid_must_resolve():
    for status in ("filled", "unknown"):
        data = deepcopy(BASE)
        data["orderStatus"]["order"]["status"] = status
        with pytest.raises(IncompleteInfoReport):
            collect(FakeInfo(data))
    data = deepcopy(BASE)
    data["orderStatus"]["order"]["order"]["cloid"] = None
    with pytest.raises(IncompleteInfoReport, match="LOST_ACK_CLOID_UNPROVED"):
        collect(FakeInfo(data))
