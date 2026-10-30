"""Sentinel-only checks for the future systemd credential handoff."""
from __future__ import annotations

import hashlib
import json

import pytest
from nautilus_trader.core.nautilus_pyo3 import hyperliquid_resolve_execution_account_address

from coinmaster.ops.hl_live_credential_preflight import CredentialGateError, check_live_credential


KEY = "0x" + "2" * 64
MASTER = "0x" + "1" * 40
AGENT = hyperliquid_resolve_execution_account_address(private_key=KEY)


def _hash(address):
    return hashlib.sha256(address.lower().encode()).hexdigest()


def _fixture(tmp_path, *, authorization="VERIFIED", collateral="100"):
    record = tmp_path / "connection.json"
    record.write_text(json.dumps({
        "id": "a" * 32, "venue": "hyperliquid", "master_address": MASTER,
        "agent_private_key": KEY,
        "verification_state": {"public_observation": "REACHABLE", "agent_authorization": authorization},
    }))
    fingerprints = tmp_path / "fingerprints.json"
    fingerprints.write_text(json.dumps({
        "schema": "coinmaster-hl-live-public-account-fingerprint-v1",
        "environment": "mainnet",
        "fingerprint_algorithm": "sha256(lowercase_ascii_0x_address)",
        "master_address_sha256": _hash(MASTER),
        "agent_address_sha256": _hash(AGENT),
    }))
    seen = []
    def info_lookup(kind, address):
        seen.append((kind, address))
        if kind == "userRole" and address == MASTER:
            return {"role": "user"}
        if kind == "userRole" and address == AGENT:
            return {"role": "agent", "data": {"user": MASTER}}
        if kind == "clearinghouseState" and address == MASTER:
            return {"marginSummary": {"accountValue": collateral}}
        raise AssertionError("unexpected account query")
    return record, fingerprints, info_lookup, seen


def test_verified_sentinel_record_uses_master_for_account_query(tmp_path):
    record, fingerprints, info_lookup, seen = _fixture(tmp_path)
    check_live_credential(record, fingerprints, info_lookup=info_lookup)
    assert seen == [
        ("userRole", MASTER), ("userRole", AGENT), ("clearinghouseState", MASTER),
    ]


@pytest.mark.parametrize("change,reason", [
    ({"authorization": "UNVERIFIED"}, "CREDENTIAL_RECORD_UNVERIFIED"),
    ({"collateral": "0"}, "ACCOUNT_COLLATERAL_NOT_POSITIVE"),
])
def test_unverified_or_unfunded_record_fails_closed(tmp_path, change, reason):
    record, fingerprints, info_lookup, _ = _fixture(tmp_path, **change)
    with pytest.raises(CredentialGateError, match=reason) as error:
        check_live_credential(record, fingerprints, info_lookup=info_lookup)
    assert KEY not in str(error.value)


def test_wrong_saved_agent_fingerprint_fails_before_info(tmp_path):
    record, fingerprints, info_lookup, seen = _fixture(tmp_path)
    data = json.loads(fingerprints.read_text())
    data["agent_address_sha256"] = "0" * 64
    fingerprints.write_text(json.dumps(data))
    with pytest.raises(CredentialGateError, match="ACCOUNT_FINGERPRINT_MISMATCH"):
        check_live_credential(record, fingerprints, info_lookup=info_lookup)
    assert seen == []


def test_fresh_role_mismatch_fails_closed(tmp_path):
    record, fingerprints, _, _ = _fixture(tmp_path)
    def wrong_role(kind, address):
        if kind == "userRole" and address == MASTER:
            return {"role": "user"}
        return {"role": "agent", "data": {"user": "0x" + "3" * 40}}
    with pytest.raises(CredentialGateError, match="ACCOUNT_LIVE_CHECK_FAILED"):
        check_live_credential(record, fingerprints, info_lookup=wrong_role)


def test_saved_verified_agent_missing_now_has_public_reason(tmp_path):
    record, fingerprints, lookup, _ = _fixture(tmp_path)
    def missing(kind, address):
        if kind == "userRole" and address == AGENT:
            return {"role": "missing"}
        return lookup(kind, address)
    with pytest.raises(CredentialGateError, match="AGENT_AUTHORIZATION_MISSING"):
        check_live_credential(record, fingerprints, info_lookup=missing)


def _fake_http(monkeypatch, *, mode="unifiedAccount", malformed=None):
    """Exercise the default adapter and real HTTP decoder without network access."""
    import io
    from coinmaster.ops import hl_live_execution

    seen = []
    def urlopen(request, *, timeout):
        assert request.full_url == "https://api.hyperliquid.xyz/info"
        assert request.method == "POST" and timeout == 5
        body = json.loads(request.data)
        assert set(body) == {"type", "user"}
        kind, address = body["type"], body["user"]
        seen.append((kind, address))
        if kind == "userRole":
            value = ({"role": "user"} if address == MASTER else
                     {"role": "agent", "data": {"user": MASTER}})
        elif kind == "userAbstraction":
            value = mode
        elif kind == "spotClearinghouseState":
            value = {"balances": [{"coin": "USDC", "total": "100", "hold": "0"}]}
        elif kind == "clearinghouseState":
            value = {"marginSummary": {"accountValue": "100"}}
        else:
            raise AssertionError("unexpected Info endpoint")
        if malformed and kind == malformed[0]:
            value = malformed[1]
        response = io.BytesIO(json.dumps(value).encode())
        response.status = 200
        return response
    monkeypatch.setattr(hl_live_execution, "urlopen", urlopen)
    return seen


@pytest.mark.parametrize("mode", ["disabled", "unifiedAccount"])
def test_default_lookup_decodes_endpoint_specific_types(tmp_path, monkeypatch, mode):
    from decimal import Decimal
    from coinmaster.ops.hl_live_execution import ReadinessInfoBudget
    record, fingerprints, _, _ = _fixture(tmp_path)
    seen = _fake_http(monkeypatch, mode=mode)
    context = {}
    assert check_live_credential(
        record, fingerprints, account_mode=mode,
        readiness_budget=ReadinessInfoBudget(), context_out=context,
    ) == Decimal("100")
    assert seen == [("userRole", MASTER), ("userRole", AGENT)] + (
        [("userAbstraction", MASTER), ("spotClearinghouseState", MASTER)]
        if mode == "unifiedAccount" else [("clearinghouseState", MASTER)]
    )
    assert context["master_role"] == "user" and context["agent_role"] == "agent"


@pytest.mark.parametrize("mode,malformed,reason", [
    ("unifiedAccount", ("userRole", "user"), "ACCOUNT_LIVE_CHECK_FAILED"),
    ("unifiedAccount", ("userAbstraction", {"mode": "unifiedAccount"}), "ACCOUNT_MODE_MISMATCH"),
    ("unifiedAccount", ("spotClearinghouseState", []), "ACCOUNT_LIVE_CHECK_FAILED"),
    ("disabled", ("clearinghouseState", "100"), "ACCOUNT_LIVE_CHECK_FAILED"),
])
def test_default_lookup_malformed_endpoint_types_fail_closed(tmp_path, monkeypatch, mode, malformed, reason):
    from coinmaster.ops.hl_live_execution import ReadinessInfoBudget
    record, fingerprints, _, _ = _fixture(tmp_path)
    _fake_http(monkeypatch, mode=mode, malformed=malformed)
    with pytest.raises(CredentialGateError, match=reason):
        check_live_credential(record, fingerprints, account_mode=mode,
                              readiness_budget=ReadinessInfoBudget())


def test_actual_live_node_constructor_uses_default_lookup(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from coinmaster.ops import hl_live_worker
    record, fingerprints, _, _ = _fixture(tmp_path)
    seen = _fake_http(monkeypatch)
    monkeypatch.setattr(hl_live_worker, "load_live_profile",
                        lambda root, candidate: {"account_mode": "unifiedAccount"})
    class QualifiedBeforeEngine(Exception):
        pass
    def qualification_boundary(*args, **kwargs):
        assert "info_lookup" not in kwargs
        assert check_live_credential(*args, **kwargs) == 100
        raise QualifiedBeforeEngine
    monkeypatch.setattr(hl_live_worker, "check_live_credential", qualification_boundary)
    with pytest.raises(QualifiedBeforeEngine):
        hl_live_worker.HyperliquidLiveNode(
            instance=SimpleNamespace(mode="live", instance_id="hl-stageg-live"),
            candidate=object(), state=object(), credential_path=record,
            fingerprint_path=fingerprints,
        )
    assert seen[-2:] == [("userAbstraction", MASTER), ("spotClearinghouseState", MASTER)]
