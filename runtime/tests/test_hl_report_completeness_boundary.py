"""Pinned Nautilus 1.231 Hyperliquid bulk-report negative contract.

All calls use fake transport. These tests document why bare native bulk lists
cannot certify a complete recovery snapshot; they never enable takeover.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

import nautilus_trader.adapters.hyperliquid.execution as execution
from nautilus_trader.adapters.hyperliquid.execution import HyperliquidExecutionClient
from nautilus_trader.live.execution_client import LiveExecutionClient
from nautilus_trader.model.identifiers import AccountId, ClientId, ClientOrderId, Venue, VenueOrderId


METHODS = (
    ("generate_order_status_reports", "orders"),
    ("generate_fill_reports", "fills"),
    ("generate_position_status_reports", "positions"),
)


class FakeTransport:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def _request(self, name, **kwargs):
        self.calls.append((name, kwargs))
        if self.error is not None:
            raise self.error
        return self.result

    async def request_order_status_reports(self, **kwargs):
        return await self._request("orders", **kwargs)

    async def request_fill_reports(self, **kwargs):
        return await self._request("fills", **kwargs)

    async def request_position_status_reports(self, **kwargs):
        return await self._request("positions", **kwargs)


def fake_client(transport):
    errors = []
    client = SimpleNamespace(
        _client=transport,
        _log_report_error=lambda exc, kind: errors.append((type(exc).__name__, kind)),
        _log_report_receipt=lambda *args: None,
        _log=SimpleNamespace(debug=lambda *args: None),
        _cache=SimpleNamespace(client_order_id=lambda *args: None),
        _resolve_cloid=lambda value: value,
        _is_external_order=lambda value: value == "external",
        _promote_replacement_if_inflight_modify=lambda report: None,
        _is_inflight_modify_old_leg_cancel=lambda report: False,
    )
    return client, errors


def command(start=123, end=456):
    return SimpleNamespace(instrument_id=None, start=start, end=end, log_receipt_level=None)


@pytest.mark.parametrize(("method", "call_name"), METHODS)
@pytest.mark.parametrize(
    ("result", "error"),
    [
        ([], None),
        (None, TimeoutError("timeout")),
        (None, RuntimeError("429 rate limited")),
        (None, RuntimeError("500 server error")),
        (None, asyncio.CancelledError()),
        (None, None),
    ],
    ids=("empty", "timeout", "429", "500", "cancelled", "malformed-container"),
)
def test_empty_error_and_malformed_have_identical_bulk_result(method, call_name, result, error):
    transport = FakeTransport(result, error)
    client, errors = fake_client(transport)
    assert asyncio.run(getattr(HyperliquidExecutionClient, method)(client, command())) == []
    assert transport.calls == [(call_name, {"instrument_id": None})]
    assert bool(errors) == (error is not None or result is None)


@pytest.mark.parametrize(("method", "call_name"), METHODS)
def test_nonempty_owned_partial_tp_reports_keep_native_conversion_but_no_completeness(monkeypatch, method, call_name):
    row = SimpleNamespace(
        instrument_id="BTC-USD-PERP.HYPERLIQUID",
        client_order_id="HLTG-OWNED-TP",
        venue_order_id="123",
        quantity="0.03000", filled_qty="0.00500", reduce_only=True,
        trade_id="fill-1", last_qty="0.00500", position_qty="0.02500",
    )
    report_class = {
        "orders": "OrderStatusReport", "fills": "FillReport", "positions": "PositionStatusReport",
    }[call_name]
    monkeypatch.setattr(execution, report_class, SimpleNamespace(from_pyo3=lambda value: value))
    transport = FakeTransport([row])
    client, errors = fake_client(transport)
    assert asyncio.run(getattr(HyperliquidExecutionClient, method)(client, command())) == [row]
    assert transport.calls == [(call_name, {"instrument_id": None})]
    assert errors == []


@pytest.mark.parametrize(("method", "call_name"), METHODS)
def test_missing_or_bad_row_turns_even_nonempty_reply_into_empty(monkeypatch, method, call_name):
    report_class = {
        "orders": "OrderStatusReport", "fills": "FillReport", "positions": "PositionStatusReport",
    }[call_name]

    def convert(row):
        if row is None:
            raise ValueError("malformed row")
        return row

    monkeypatch.setattr(execution, report_class, SimpleNamespace(from_pyo3=convert))
    row = SimpleNamespace(client_order_id="HLTG-OWNED-TP", venue_order_id="123")
    transport = FakeTransport([row, None])
    client, errors = fake_client(transport)
    assert asyncio.run(getattr(HyperliquidExecutionClient, method)(client, command())) == []
    assert transport.calls == [(call_name, {"instrument_id": None})]
    assert errors == [("ValueError", {
        "orders": "OrderStatusReports", "fills": "FillReports", "positions": "PositionStatusReports",
    }[call_name])]


def test_fill_window_and_history_cap_have_no_native_report_contract(monkeypatch):
    monkeypatch.setattr(execution, "FillReport", SimpleNamespace(from_pyo3=lambda value: value))
    rows = [SimpleNamespace(client_order_id="HLTG-OWNED-TP", venue_order_id="123", trade_id=i) for i in range(2000)]
    transport = FakeTransport(rows)
    client, errors = fake_client(transport)
    for start, end in ((0, 100), (100, 200)):
        assert len(asyncio.run(HyperliquidExecutionClient.generate_fill_reports(client, command(start, end)))) == 2000
    assert transport.calls == [
        ("fills", {"instrument_id": None}),
        ("fills", {"instrument_id": None}),
    ]
    assert errors == []


def test_unresolved_cloid_is_returned_without_a_completeness_signal(monkeypatch):
    monkeypatch.setattr(execution, "OrderStatusReport", SimpleNamespace(from_pyo3=lambda value: value))
    row = SimpleNamespace(client_order_id="external", venue_order_id="123")
    transport = FakeTransport([row])
    client, errors = fake_client(transport)
    assert asyncio.run(HyperliquidExecutionClient.generate_order_status_reports(client, command())) == [row]
    assert row.client_order_id == "external"
    assert errors == []


def test_inherited_mass_status_accepts_three_empty_lists_after_transport_failure():
    class Clock:
        def timestamp_ns(self):
            return 1

    client = SimpleNamespace(
        _log=SimpleNamespace(info=lambda *args: None, exception=lambda *args: None),
        _clock=Clock(), id=ClientId("HYPERLIQUID"),
        account_id=AccountId("HYPERLIQUID-master"), venue=Venue("HYPERLIQUID"),
        reconciliation_active=False,
    )
    client.generate_order_status_reports = lambda cmd: HyperliquidExecutionClient.generate_order_status_reports(client, cmd)
    client.generate_fill_reports = lambda cmd: HyperliquidExecutionClient.generate_fill_reports(client, cmd)
    client.generate_position_status_reports = lambda cmd: HyperliquidExecutionClient.generate_position_status_reports(client, cmd)
    transport = FakeTransport(error=TimeoutError("timeout"))
    client._client = transport
    client._log_report_error = lambda *args: None
    client._log_report_receipt = lambda *args: None
    result = asyncio.run(LiveExecutionClient.generate_mass_status(client))
    assert result is not None
    assert len(transport.calls) == 3
    assert client.reconciliation_active is False


def test_simulated_rust_skipped_raw_row_has_no_completeness_signal():
    # The pinned Rust report parser can log/skip an unparseable venue row and
    # hand Python an Ok([]). FakeTransport models precisely that Python seam.
    transport = FakeTransport([])
    transport.hidden_raw_rows = [{"malformed": True}]
    client, errors = fake_client(transport)
    assert asyncio.run(HyperliquidExecutionClient.generate_fill_reports(client, command())) == []
    assert errors == []
    assert transport.calls == [("fills", {"instrument_id": None})]
    # No returned field or Python callback distinguishes this from raw [].
    assert transport.hidden_raw_rows


def test_native_websocket_dispatcher_swallows_handler_exception(monkeypatch):
    class FakeFillMessage:
        pass

    monkeypatch.setattr(execution.nautilus_pyo3, "FillReport", FakeFillMessage)
    errors = []

    def fail(_msg):
        raise ValueError("native fill handler failed")

    client = SimpleNamespace(
        _handle_fill_report_pyo3=fail,
        _log=SimpleNamespace(exception=lambda *args: errors.append(args)),
    )
    assert HyperliquidExecutionClient._handle_msg(client, FakeFillMessage()) is None
    assert len(errors) == 1 and isinstance(errors[0][1], ValueError)

def test_pinned_ws_fill_handler_can_return_after_buffering_without_native_effect(monkeypatch):
    # _handle_msg can return normally while a fill is neither processed nor in Cache.
    # A report-owner drain must inspect pending fills and later cache parity.
    report = SimpleNamespace(
        trade_id=SimpleNamespace(value="9"),
        client_order_id=ClientOrderId("CM05-OWNED"),
        venue_order_id=VenueOrderId("7"),
        last_qty="0.001", last_px="60000",
    )
    monkeypatch.setattr(execution.FillReport, "from_pyo3", lambda _: report)
    pending = {}
    client = SimpleNamespace(
        _log=SimpleNamespace(debug=lambda *args: None, warning=lambda *args: None),
        _processed_trade_ids=set(),
        _resolve_cloid=lambda x: x,
        _is_external_order=lambda _: False,
        _cache=SimpleNamespace(order=lambda _: None),
        _pending_fills=pending,
    )
    msg = object()
    assert HyperliquidExecutionClient._handle_fill_report_pyo3(client, msg) is None
    assert pending == {"CM05-OWNED": [msg]}
    assert "9" not in client._processed_trade_ids


def test_pinned_ws_position_status_handler_only_logs(monkeypatch):
    # A successful return from this native WS branch does not update Cache.
    report = object()
    monkeypatch.setattr(execution.PositionStatusReport, "from_pyo3", lambda _: report)
    seen = []
    client = SimpleNamespace(_log=SimpleNamespace(debug=lambda *args: seen.append(args)))
    assert HyperliquidExecutionClient._handle_position_status_report_pyo3(client, object()) is None
    assert seen and seen[0][0].startswith("Received ")
