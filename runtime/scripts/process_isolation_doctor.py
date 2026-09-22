"""Read-only D4 ownership, credential, and path checks for deployment files."""
from __future__ import annotations

import argparse
import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRADER = ROOT / "ops/coinmaster-hl-stageg-testnet.service"
RUNTIME = ROOT / "ops/coinmaster-runtime.service"
TRADER_ENV = ROOT / "ops/coinmaster-hl-stageg-testnet.env.example"
RUNTIME_ENV = ROOT / "ops/coinmaster-runtime.env.example"
TRADER_CONFIG = ROOT / "configs/hl-stageg-testnet.instance.json"


def _protected_path_failures(path: Path, *, expected_mode: int, expected_uid: int) -> list[str]:
    try:
        metadata = path.stat()
    except OSError:
        return [f"MISSING_PROTECTED_PATH:{path}"]
    failures: list[str] = []
    if stat.S_IMODE(metadata.st_mode) != expected_mode:
        failures.append(f"UNSAFE_MODE:{path}:{oct(stat.S_IMODE(metadata.st_mode))}")
    if metadata.st_uid != expected_uid:
        failures.append(f"UNEXPECTED_OWNER:{path}:{metadata.st_uid}")
    return failures


def check_host_metadata(*, trader_env: Path, runtime_env: Path, trader_state_dir: Path,
                        research_state_dir: Path, root_uid: int, trader_uid: int,
                        research_uid: int) -> list[str]:
    """Check actual host paths against their distinct expected owners/modes.

    Numeric UIDs are supplied explicitly so this stays usable in a non-root
    local fixture as well as on the VPS, where root owns the env files and the
    two service identities own different StateDirectories.
    """
    return [
        *_protected_path_failures(trader_env, expected_mode=0o600, expected_uid=root_uid),
        *_protected_path_failures(runtime_env, expected_mode=0o600, expected_uid=root_uid),
        *_protected_path_failures(trader_state_dir, expected_mode=0o700, expected_uid=trader_uid),
        *_protected_path_failures(research_state_dir, expected_mode=0o700, expected_uid=research_uid),
    ]


def check() -> list[str]:
    trader, runtime, trader_env, runtime_env, config = (
        path.read_text() for path in (TRADER, RUNTIME, TRADER_ENV, RUNTIME_ENV, TRADER_CONFIG)
    )
    failures: list[str] = []
    for value in (
        "coinmaster.ops.hyperliquid_testnet_worker",
        "EnvironmentFile=/etc/coinmaster-hl-stageg-testnet.env",
        "User=coinmaster-hl",
        "Group=coinmaster-hl",
        "StateDirectory=coinmaster-hl-stageg-testnet",
        "StateDirectoryMode=0700",
        "UMask=0077",
        "WorkingDirectory=/srv/coinmaster/runtime",
        "ReadOnlyPaths=/srv/coinmaster/runtime /etc/coinmaster",
        "ReadWritePaths=/var/lib/coinmaster-hl-stageg-testnet",
    ):
        if value not in trader:
            failures.append(f"TRADER_SERVICE_MISSING:{value}")
    for value in (
        "EnvironmentFile=/etc/coinmaster-runtime.env",
        "User=coinmaster-research",
        "Group=coinmaster-research",
        "StateDirectory=coinmaster-runtime",
        "StateDirectoryMode=0700",
        "COINMASTER_RESEARCH_MAX_WORKERS=1",
        "COINMASTER_RESEARCH_DATA_ROOT=/var/lib/coinmaster-runtime/data",
        "WorkingDirectory=/srv/coinmaster/runtime",
        "ReadOnlyPaths=/srv/coinmaster/runtime /srv/coinmaster/research-inputs",
    ):
        if value not in runtime:
            failures.append(f"RESEARCH_SERVICE_MISSING:{value}")
    for forbidden in ("coinmaster-runtime.service", "coinmaster-paper.service", "COINMASTER_RUNTIME_CONTROL_DB"):
        if forbidden in trader:
            failures.append(f"TRADER_SERVICE_CROSSES_BOUNDARY:{forbidden}")
    if "/root/" in trader or "/root/" in runtime or "/root/" in config:
        failures.append("ROOT_HOME_RUNTIME_PATH_FORBIDDEN")
    if '"state_db":"/var/lib/coinmaster-hl-stageg-testnet/hl-stageg-testnet.sqlite"' not in config:
        failures.append("TRADER_STATE_DB_PATH_MISMATCH")
    if '"strategy_config":"/srv/coinmaster/runtime/configs/stage-g-v1.json"' not in config:
        failures.append("TRADER_SHARED_CODE_PATH_MISMATCH")
    if any(name in trader_env for name in ("HYPERLIQUID_TESTNET_PK", "HYPERLIQUID_PRIVATE_KEY", "COINMASTER_HL_TESTNET_MASTER_ACCOUNT_ADDRESS")):
        failures.append("TRADER_ENV_CONTAINS_FORBIDDEN_AUTHENTICATED_HL_CONTRACT")
    if "COINMASTER_RUNTIME_API_TOKEN" in trader_env or "COINMASTER_PAPER_DB" in trader_env:
        failures.append("TRADER_ENV_CROSSES_API_OR_PAPER_BOUNDARY")
    if "HYPERLIQUID" in runtime_env or "BYBIT_" in runtime_env:
        failures.append("RESEARCH_ENV_CONTAINS_VENUE_CREDENTIAL_CONTRACT")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only D4 service and host ownership doctor")
    parser.add_argument("--trader-env", type=Path)
    parser.add_argument("--runtime-env", type=Path)
    parser.add_argument("--trader-state", type=Path)
    parser.add_argument("--research-state", type=Path)
    parser.add_argument("--root-uid", type=int)
    parser.add_argument("--trader-uid", type=int)
    parser.add_argument("--research-uid", type=int)
    args = parser.parse_args()
    failures = check()
    supplied = (args.trader_env, args.runtime_env, args.trader_state, args.research_state,
                args.root_uid, args.trader_uid, args.research_uid)
    if any(value is not None for value in supplied):
        if any(value is None for value in supplied):
            parser.error("all --*-env/state/uid host metadata arguments are required together")
        failures.extend(check_host_metadata(
            trader_env=args.trader_env, runtime_env=args.runtime_env,
            trader_state_dir=args.trader_state, research_state_dir=args.research_state,
            root_uid=args.root_uid, trader_uid=args.trader_uid, research_uid=args.research_uid,
        ))
    if failures:
        raise SystemExit("FAIL " + ";".join(failures))
    print("OK trader=separate-uid/one-node/sandbox-only research=separate-uid/one-worker credentials=none paths=isolated")


if __name__ == "__main__":
    main()
