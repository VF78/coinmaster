"""Pinned Nautilus 1.231 Hyperliquid bulk-report completeness boundary.

These tests use the installed adapter methods with a fake transport. They must
remain a negative contract test, not an authorization to reconcile empty reports.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from nautilus_trader.adapters.hyperliquid.execution import HyperliquidExecutionClient


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


@pytest.mark.parametrize(
    ("method", "call_name"),
    [
        ("generate_order_status_reports", "orders"),
        ("generate_fill_reports", "fills"),
        ("generate_position_status_reports", "positions"),
    ],
)
def test_bulk_report_empty_failure_and_malformed_are_indistinguishable(method, call_name):
    outcomes = []
    for result, error in (([], None), (None, RuntimeError("transport failure")), (None, None)):
        transport = FakeTransport(result, error)
        logged_errors = []
        client = SimpleNamespace(
            _client=transport,
            _log_report_error=lambda exc, kind: logged_errors.append((type(exc).__name__, kind)),
            _log_report_receipt=lambda *args: None,
        )
        command = SimpleNamespace(
            instrument_id=None, start=123, end=456, log_receipt_level=None,
        )
        reports = asyncio.run(getattr(HyperliquidExecutionClient, method)(client, command))
        outcomes.append(reports)
        assert transport.calls == [(call_name, {"instrument_id": None})]
    assert outcomes == [[], [], []]


def test_fill_window_and_pagination_completeness_have_no_report_contract():
    transport = FakeTransport([])
    client = SimpleNamespace(
        _client=transport,
        _log_report_receipt=lambda *args: None,
        _log_report_error=lambda *args: None,
    )
    for start, end in ((0, 100), (100, 200)):
        command = SimpleNamespace(instrument_id=None, start=start, end=end)
        assert asyncio.run(HyperliquidExecutionClient.generate_fill_reports(client, command)) == []
    assert transport.calls == [
        ("fills", {"instrument_id": None}),
        ("fills", {"instrument_id": None}),
    ]
