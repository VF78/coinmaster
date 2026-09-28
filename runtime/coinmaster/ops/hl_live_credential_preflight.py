"""Fail-closed check for one systemd-copied Hyperliquid broker record.

This validates a future live unit's credential source. It does not unlock the
native live execution route or sign an exchange request.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

from nautilus_trader.core.nautilus_pyo3 import hyperliquid_resolve_execution_account_address

from coinmaster.api.connections_broker import ADDRESS_RE, ID_RE, KEY_RE, _hyperliquid_info


class CredentialGateError(RuntimeError):
    """Public reason code only; never include record contents."""


def _read_json(path: Path) -> dict:
    try:
        with path.open("rb") as file:
            raw = file.read(16_385)
        if len(raw) > 16_384:
            raise ValueError
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (OSError, ValueError, UnicodeError):
        raise CredentialGateError("CREDENTIAL_RECORD_INVALID") from None


def _fingerprint(address: str) -> str:
    return hashlib.sha256(address.lower().encode("ascii")).hexdigest()


def check_live_credential(credential_path: Path, fingerprint_path: Path, *, info_lookup=_hyperliquid_info) -> None:
    record = _read_json(credential_path)
    expected = _read_json(fingerprint_path)
    master = record.get("master_address")
    key = record.get("agent_private_key")
    state = record.get("verification_state")
    if (
        record.get("venue") != "hyperliquid"
        or not isinstance(record.get("id"), str) or not ID_RE.fullmatch(record["id"])
        or not isinstance(master, str) or not ADDRESS_RE.fullmatch(master)
        or not isinstance(key, str) or not KEY_RE.fullmatch(key)
        or not isinstance(state, dict)
        or state.get("public_observation") != "REACHABLE"
        or state.get("agent_authorization") != "VERIFIED"
    ):
        raise CredentialGateError("CREDENTIAL_RECORD_UNVERIFIED")
    if (
        expected.get("schema") != "coinmaster-hl-live-public-account-fingerprint-v1"
        or expected.get("environment") != "mainnet"
        or expected.get("fingerprint_algorithm") != "sha256(lowercase_ascii_0x_address)"
    ):
        raise CredentialGateError("ACCOUNT_FINGERPRINT_INVALID")
    try:
        agent = hyperliquid_resolve_execution_account_address(private_key=key)
        if not isinstance(agent, str) or not ADDRESS_RE.fullmatch(agent):
            raise ValueError
    except (ValueError, TypeError, RuntimeError):
        raise CredentialGateError("AGENT_ADDRESS_INVALID") from None
    for label, address in (("master", master), ("agent", agent)):
        saved = expected.get(label + "_address_sha256")
        if not isinstance(saved, str) or not hmac.compare_digest(_fingerprint(address), saved):
            raise CredentialGateError("ACCOUNT_FINGERPRINT_MISMATCH")
    try:
        master_role = info_lookup("userRole", master)
        agent_role = info_lookup("userRole", agent)
        state_response = info_lookup("clearinghouseState", master)
        if master_role.get("role") != "user":
            raise ValueError
        if agent_role.get("role") != "agent":
            raise ValueError
        agent_data = agent_role.get("data")
        if not isinstance(agent_data, dict) or not isinstance(agent_data.get("user"), str):
            raise ValueError
        if agent_data["user"].lower() != master.lower():
            raise ValueError
        margin = state_response.get("marginSummary")
        if not isinstance(margin, dict):
            raise ValueError
        collateral = Decimal(str(margin.get("accountValue")))
        if not collateral.is_finite() or collateral <= 0:
            raise CredentialGateError("ACCOUNT_COLLATERAL_NOT_POSITIVE")
    except CredentialGateError:
        raise
    except (ValueError, TypeError, InvalidOperation, AttributeError, OSError):
        raise CredentialGateError("ACCOUNT_LIVE_CHECK_FAILED") from None


def main() -> int:
    parser = argparse.ArgumentParser(description="Check one systemd-copied live account credential")
    parser.add_argument("--fingerprints", type=Path, required=True)
    args = parser.parse_args()
    directory = os.environ.get("CREDENTIALS_DIRECTORY")
    if not directory:
        print("CREDENTIAL_DIRECTORY_MISSING")
        return 1
    try:
        check_live_credential(Path(directory) / "connection.json", args.fingerprints)
    except CredentialGateError as error:
        print(str(error))
        return 1
    except Exception:
        print("ACCOUNT_LIVE_CHECK_FAILED")
        return 1
    print("LIVE_CREDENTIAL_PREFLIGHT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
