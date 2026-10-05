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
