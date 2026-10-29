"""Pure wire-contract coverage: no account network or native object construction."""
import ast
import io
import json
import sys
import time
import types
from pathlib import Path

import pytest


def pure_sidecar():
    path = Path(__file__).parents[1] / "coinmaster/api/runtime_sidecar.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    selected = {"RuntimeSchema", "RuntimeFeed", "HlStagegHashes", "HlStagegWarmup",
                "HlStagegDepositProtection", "HlStagegAccount", "HlStagegEntryControl",
                "HlStagegEvent", "HlStagegPosition", "HlStagegOrder", "HlStagegC1",
                "HlStagegProjection", "HlStagegProjectionReader", "HlLiveProjectionReader"}
    tree.body = [node for node in tree.body if
                 isinstance(node, (ast.Import, ast.ImportFrom)) and not
                 (isinstance(node, ast.ImportFrom) and (node.module or "").startswith("coinmaster"))
                 or isinstance(node, ast.ClassDef) and node.name in selected
                 or isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in
                    {"UNKNOWN", "USDC_EQUITY_BASIS", "USDC_MARGIN_BASIS"} for t in node.targets)]
    module = types.ModuleType("pure_hl_usdc_contract")
    sys.modules[module.__name__] = module
    exec(compile(tree, str(path), "exec"), module.__dict__)
    module.live_order_approval_matches = lambda _projection: False
    return module


@pytest.fixture
def sidecar():
    return pure_sidecar()


def live(sidecar):
    return {"instance_id": "hl-stageg-live", "mode": "live", "environment": "mainnet",
            "version": "hl-stageg-live-projection-v1", "provenance": "NATIVE_MAINNET_OWNED_ACCOUNT",
            "live_order_capability": True, "run_epoch": "fixture", "observed_at_ns": time.time_ns(),
            "money_currency": "USDC", "equity_basis": sidecar.USDC_EQUITY_BASIS,
            "native_thread_alive": True, "account_state": "CURRENT", "recovery_required": False,
            "account": {"currency": "USDC", "money_currency": "USDC", "equity_basis": sidecar.USDC_EQUITY_BASIS,
                        "margin_basis": sidecar.USDC_MARGIN_BASIS, "reported_total": "100.125",
                        "native_cash": "100.125", "equity": "100.125", "native_free": "91.125",
                        "native_locked": "9", "hold": "9", "unrealized_pnl": "7.5",
                        "funding": "-0.25", "funding_currency": "USDC", "funding_reason": None, "funding_coverage_end_ns": 123,
                        "withdrawable": "666", "margin_used": "777"},
            "deposit_protection": {"state": "ARMED", "drawdown_limit_percent": 55, "currency": "USDC",
                                   "equity": "100.125", "high_water_equity": "110", "threshold_equity": "49.5",
                                   "daily_sample_missed": False, "retained_equity_floor_fraction": "0.45",
                                   "high_water_basis": "INITIAL_AND_HIGHER_VALID_UTC_DAILY_CLOSE"},
            "c1": {"state": "CURRENT", "E": "100.125", "H": "110", "DD": "0.08977272727", "cushion": "50.625",
                   "currency": "USDC", "equity_basis": sidecar.USDC_EQUITY_BASIS, "rights": {}},
            "feeds": {}, "positions": [], "orders": [], "events": []}


def read(sidecar, monkeypatch, payload):
    monkeypatch.setattr(sidecar.urllib.request, "urlopen", lambda *_a, **_k: io.BytesIO(json.dumps(payload).encode()))
    return sidecar.HlLiveProjectionReader("http://fixture.invalid").runtime()


def test_usdc_roundtrip_preserves_reported_total_without_adding_upnl(sidecar, monkeypatch):
    result = read(sidecar, monkeypatch, live(sidecar))
    wire = json.loads(result.model_dump_json())
    assert wire["account"]["equity"] == "100.125"
    assert wire["account"]["unrealized_pnl"] == "7.5"
    assert wire["account"]["funding"] == "-0.25"
    assert wire["account"]["native_free"] == "91.125"
    assert wire["account"]["native_locked"] == "9"
    assert wire["account"]["im"] is None and wire["account"]["mm"] is None
    assert wire["money_currency"] == "USDC" and wire["c1"]["E"] == "100.125"
    assert wire["deposit_protection"]["retained_equity_floor_fraction"] == "0.45"


@pytest.mark.parametrize("field,value", [("money_currency", None), ("money_currency", "USD"), ("equity_basis", "old")])
def test_foreign_or_old_producer_is_unknown_not_relabelled(sidecar, monkeypatch, field, value):
    payload = live(sidecar); payload[field] = value
    payload["real_order_approval"] = True
    sidecar.live_order_approval_matches = lambda _projection: True
    result = read(sidecar, monkeypatch, payload)
    assert result.account.equity is None and result.account.native_cash is None
    assert result.account.reason == "LIVE_MONEY_DENOMINATION_UNVERIFIED"
    assert result.real_order_approval is False
    assert result.c1.E is None and result.c1.cushion is None
    assert result.deposit_protection.equity is None


def test_foreign_dp_and_c1_units_are_masked_independently(sidecar, monkeypatch):
    payload = live(sidecar)
    payload["deposit_protection"]["currency"] = "USDT"
    payload["c1"]["currency"] = "USD"
    result = read(sidecar, monkeypatch, payload)
    assert result.account.equity == "100.125"
    assert result.deposit_protection.equity is None and result.c1.E is None


def test_no_classic_free_or_margin_fallback(sidecar, monkeypatch):
    payload = live(sidecar)
    del payload["account"]["native_free"]; del payload["account"]["native_locked"]
    result = read(sidecar, monkeypatch, payload)
    assert result.account.native_free is None and result.account.native_locked is None


def test_public_candle_metadata_is_explicit_usdc():
    path = Path(__file__).parents[1] / "coinmaster/api/hl_public_candles.py"
    module = types.ModuleType("pure_hl_candles")
    exec(compile(path.read_text(), str(path), "exec"), module.__dict__)
    result = module.public_candles("BTC", "1m", 1, now_ms=120001, post=lambda _body: [])
    assert result["quote_currency"] == "USDC"
    assert result["source"] == "OFFICIAL_INFO_CANDLE_SNAPSHOT"
    assert result["candles"] == []


def test_foreign_funding_is_not_added_or_relabelled(sidecar, monkeypatch):
    payload = live(sidecar); payload["account"]["funding_currency"] = "USD"
    result = read(sidecar, monkeypatch, payload)
    assert result.account.equity == "100.125" and result.account.funding is None
    assert result.account.funding_reason == "LIVE_FUNDING_CURRENCY_UNVERIFIED"
