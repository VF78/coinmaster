"""Read-only health inspection for the durable paper-control SQLite database."""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


REQUIRED_TABLES = frozenset({"paper_lock", "paper_commands", "paper_events", "paper_snapshot", "paper_funding_ledger"})


def inspect(database: Path) -> dict[str, object]:
    try:
        connection = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    except sqlite3.Error as error:
        return {"status": "BLOCKED", "reason": "JOURNAL_UNAVAILABLE", "detail": type(error).__name__, "live_gate": "BLOCKED_PAPER_ONLY"}
    try:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = sorted(REQUIRED_TABLES - tables)
        row = connection.execute("SELECT body FROM paper_snapshot WHERE id=1").fetchone() if "paper_snapshot" in tables else None
        snapshot = json.loads(row[0]) if row else None
        if missing or snapshot is None:
            return {"status": "BLOCKED", "reason": "MISSING_JOURNAL_STRUCTURE" if missing else "MISSING_SNAPSHOT", "missing_tables": missing, "live_gate": "BLOCKED_PAPER_ONLY"}
        return {
            "status": "OK", "journal_mode": connection.execute("PRAGMA journal_mode").fetchone()[0],
            "positions": len(snapshot.get("positions", [])), "orders": len(snapshot.get("orders", [])),
            "reconciled": bool(snapshot.get("reconciled", False)), "live_gate": "BLOCKED_PAPER_ONLY",
        }
    except (sqlite3.Error, ValueError, TypeError, json.JSONDecodeError) as error:
        return {"status": "BLOCKED", "reason": "JOURNAL_INVALID", "detail": type(error).__name__, "live_gate": "BLOCKED_PAPER_ONLY"}
    finally:
        connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    print(json.dumps(inspect(parser.parse_args().database), sort_keys=True))
