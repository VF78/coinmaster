#!/usr/bin/env python3
"""CoinMaster Freqtrade DB preflight.

Initializes/migrates the configured Freqtrade DB before the dry-run trader is
started, then verifies the core tables used by Freqtrade exist.  This catches the
`sqlite no such table: trades` class of failures before the bot loop starts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import SQLAlchemyError

from freqtrade.persistence.models import init_db

REQUIRED_TABLES = {"trades", "orders", "pairlocks", "KeyValueStore"}


def deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(left.get(key), dict):
            deep_merge(left[key], value)
        else:
            left[key] = value
    return left


def load_config(paths: list[Path]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    for path in paths:
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise SystemExit(f"config is not a JSON object: {path}")
        deep_merge(config, payload)
    return config


def sqlite_path_from_url(db_url: str) -> Path | None:
    if not db_url.startswith("sqlite://") or db_url == "sqlite://":
        return None
    raw = db_url.removeprefix("sqlite://")
    if raw.startswith("/"):
        return Path(raw)
    return Path(raw).resolve()


def inspect_tables(db_url: str) -> set[str]:
    connect_args = {"check_same_thread": False} if db_url.startswith("sqlite://") else {}
    engine = create_engine(db_url, future=True, connect_args=connect_args)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        action="append",
        default=[],
        help="Freqtrade config JSON path. May be passed multiple times; later files override earlier ones.",
    )
    parser.add_argument("--allow-live", action="store_true", help="Allow preflight when dry_run is false.")
    args = parser.parse_args()

    config_paths = [Path(item) for item in args.config] or [
        Path("/freqtrade/user_data/config.example.json"),
        Path("/freqtrade/user_data/config.private.json"),
        Path("/freqtrade/user_data/runtime/config.trading-rules.json"),
    ]
    config = load_config(config_paths)
    db_url = str(config.get("db_url") or "").strip()
    if not db_url:
        db_url = "sqlite:////freqtrade/user_data/tradesv3.dryrun.sqlite"
        print(f"preflight_db: db_url missing; using CoinMaster dry-run default {db_url}")

    dry_run = config.get("dry_run") is True
    if not dry_run and not args.allow_live:
        raise SystemExit("refusing DB preflight because merged Freqtrade config is not dry_run=true")

    sqlite_path = sqlite_path_from_url(db_url)
    if sqlite_path is not None:
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        before = inspect_tables(db_url)
    except SQLAlchemyError as exc:
        before = set()
        print(f"preflight_db: initial inspection failed, will initialize: {exc}", file=sys.stderr)

    missing_before = REQUIRED_TABLES - before
    if missing_before:
        print(f"preflight_db: initializing/migrating DB; missing tables before={sorted(missing_before)}")
    else:
        print(f"preflight_db: core tables already present: {sorted(REQUIRED_TABLES)}")

    init_db(db_url)
    after = inspect_tables(db_url)
    missing_after = REQUIRED_TABLES - after
    if missing_after:
        raise SystemExit(f"Freqtrade DB preflight failed; missing tables after init/migration: {sorted(missing_after)}")

    if sqlite_path is not None:
        print(f"preflight_db: sqlite ok path={sqlite_path} exists={sqlite_path.exists()}")
    else:
        print("preflight_db: database ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
