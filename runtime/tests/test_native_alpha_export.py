"""One connected native old-export/analysis-True vs sequential/export-False proof."""
import csv
import hashlib
import json
import sqlite3
import subprocess
import sys
import types
from pathlib import Path


def test_two_episode_native_export_analysis_parity(tmp_path, monkeypatch):
    import pyarrow as pa
    import pyarrow.parquet as pq
    import coinmaster.research.native_baseline as current
    from test_native_alpha_cushion import test_production_alpha_closed_15m_release_and_daily_batch_native_identity as connected

    repo = Path(current.__file__).resolve().parents[3]
    before = subprocess.check_output(["git", "show", "bd1aa691a487ebda25bcd76d278a88ec9f9c8195:runtime/coinmaster/research/native_baseline.py"], cwd=repo, text=True)
    reference = types.ModuleType("coinmaster.research._alpha_export_reference")
    reference.__file__ = current.__file__
    monkeypatch.setitem(sys.modules, reference.__name__, reference)
    exec(compile(before, current.__file__, "exec"), reference.__dict__)
    run_current = current.run_native_diagnostic
    results = []
    signatures = []
    funding_rows = []
    ignored = {"client_order_id", "venue_order_id", "position_id", "account_id", "trader_id", "strategy_id", "tags", "exec_algorithm_id", "exec_algorithm_params", "exec_spawn_id", "order_list_id", "linked_order_ids", "parent_order_id", "last_trade_id", "init_id", "trade_id"}

    def run(data_root, **kwargs):
        # Actual funding while both native episodes hold positions, not a mock ledger.
        for symbol in ("BTCUSDT", "SOLUSDT"):
            rows = [{"funding_time_ms": current.TRADING_START_MS + minute*current.MINUTE_MS, "funding_rate": "0.0001"} for minute in (10, 1450)]
            pq.write_table(pa.Table.from_pylist(rows), data_root/"normalized"/f"bybit-{symbol}-funding.parquet")
        kwargs["include_funding"] = True
        # Keep both event batching parameters identical: only housekeeping differs.
        kwargs["weekly_batch_minutes"] = kwargs["cursor_batch_rows"]
        result = (reference.run_native_diagnostic if not results else run_current)(data_root, **kwargs)
        assert result["terminal_open_positions"] == 0
        assert result["funding"]["count"] == 3
        assert sorted(result["funding"]["by_instrument_count"].values()) == [1, 2]
        sig = {}
        for kind in ("orders", "fills"):
            artifact = result["execution_artifacts"][kind]
            path = Path(artifact["path"])
            assert hashlib.sha256(path.read_bytes()).hexdigest() == artifact["sha256"]
            with path.open() as f:
                reader = csv.DictReader(f)
                sig[kind] = {"columns": reader.fieldnames, "rows": [{k:v for k,v in row.items() if k not in ignored} for row in reader]}
            assert len(sig[kind]["rows"]) == artifact["rows"] > 0
        assert all(row["status"] in {"FILLED", "CANCELED", "EXPIRED", "REJECTED", "DENIED"} for row in sig["orders"]["rows"])
        with sqlite3.connect(result["funding_journal"]) as db:
            funding_rows.append(db.execute("SELECT instrument_id,ts_event,rate,settlement_mark,account_total_after FROM funding_events ORDER BY ts_event,instrument_id").fetchall())
        target = Path(kwargs["artifact_dir"])/"complete-result.json"
        target.write_text(json.dumps(result, default=str, sort_keys=True))
        assert json.loads(target.read_text())["terminal_total"] == result["terminal_total"]
        signatures.append(sig)
        results.append(result)
        return result

    monkeypatch.setattr(current, "run_native_diagnostic", run)
    connected(tmp_path, monkeypatch)
    left, right = results
    assert left["config"] == right["config"]
    assert left["config_hash"] == right["config_hash"]
    assert "research_housekeeping" not in left
    assert right["research_housekeeping"] == {"native_run_analysis": False, "export": "SEQUENTIAL_UNCHANGED_NATIVE_REPORTS", "economic_policy_change": False}
    for key in ("terminal_total", "native_fees", "fills", "cash_account_series", "interval_cash_account_series", "terminal_open_positions", "terminal_lifecycle", "native_order_rejections", "summary", "post_boundary_settlement", "fee_attribution", "funding", "fill_timestamps_ns"):
        assert left[key] == right[key], key
    assert funding_rows[0] == funding_rows[1]
    assert signatures[0] == signatures[1]
