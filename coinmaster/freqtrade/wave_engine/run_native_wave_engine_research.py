#!/usr/bin/env python3
"""Prepare and optionally run native Freqtrade validation in a temp research dir."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from .freqtrade_adapter import snapshot_summary
except Exception:
    from freqtrade_adapter import snapshot_summary  # type: ignore[no-redef]

REPO_ROOT = Path(__file__).resolve().parents[2]
FREQTRADE_ROOT = REPO_ROOT / "freqtrade"
USER_DATA_ROOT = FREQTRADE_ROOT / "user_data"
RUNTIME_RESEARCH_ROOT = USER_DATA_ROOT / "runtime" / "wave-engine-native-local"
SOURCE_FILES = (
    "CoinMasterWaveEngineV1.py",
    "engine.py",
    "freqtrade_adapter.py",
    "wave_engine_profiles.selected.json",
    "__init__.py",
)


def _load_base_config() -> dict[str, Any]:
    return json.loads((USER_DATA_ROOT / "config.example.json").read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def prepare_workspace(timerange: str, pairs: list[str], run_id: str | None = None, workspace_root: Path | None = None) -> dict[str, Any]:
    run_name = run_id or datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    run_root = (workspace_root or RUNTIME_RESEARCH_ROOT) / run_name
    strategies_dir = run_root / "strategies"
    strategies_dir.mkdir(parents=True, exist_ok=False)

    for name in SOURCE_FILES:
        shutil.copy2(Path(__file__).resolve().with_name(name), strategies_dir / name)

    base_config = _load_base_config()
    base_config["strategy"] = "CoinMasterWaveEngineV1"
    base_config["timeframe"] = "5m"
    base_config["dry_run"] = True
    base_config["initial_state"] = "stopped"
    base_config["api_server"]["enabled"] = False
    base_config["telegram"]["enabled"] = False
    base_config["exchange"]["pair_whitelist"] = pairs
    base_config["exchange"]["pair_blacklist"] = []

    config_path = run_root / "config.wave-engine.json"
    _write_json(config_path, base_config)

    # Freqtrade's lookahead-analysis internally switches to market entries.
    # Market entries are rejected unless entry_pricing.price_side is "other",
    # so keep a separate research-only config for that command instead of
    # weakening the normal backtest config or touching the running dry config.
    lookahead_config = json.loads(json.dumps(base_config))
    lookahead_config.setdefault("entry_pricing", {})["price_side"] = "other"
    lookahead_config.setdefault("exit_pricing", {})["price_side"] = "other"
    lookahead_config_path = run_root / "config.wave-engine-lookahead.json"
    _write_json(lookahead_config_path, lookahead_config)

    command_bundle = {
        "list_strategies": _docker_cmd(run_root, "list-strategies", pairs=pairs),
        "backtesting": _docker_cmd(run_root, "backtesting", "--timerange", timerange, "--export", "trades", "--breakdown", "month", pairs=pairs),
        "lookahead_analysis": _docker_cmd(run_root, "lookahead-analysis", "--timerange", timerange, pairs=pairs, config_name="config.wave-engine-lookahead.json"),
        "recursive_analysis": _docker_cmd(run_root, "recursive-analysis", "--timerange", timerange, pairs=pairs),
    }
    _write_json(run_root / "commands.json", command_bundle)
    (run_root / "COMMANDS.md").write_text(_commands_markdown(run_root, timerange, pairs, command_bundle), encoding="utf-8")
    _write_json(
        run_root / "workspace.json",
        {
            "run_id": run_name,
            "run_root": str(run_root),
            "timerange": timerange,
            "pairs": pairs,
            "snapshot": snapshot_summary(),
            "created_at": datetime.now(tz=UTC).isoformat(),
        },
    )
    return {
        "run_id": run_name,
        "run_root": run_root,
        "config_path": config_path,
        "strategies_dir": strategies_dir,
        "commands": command_bundle,
    }


def _docker_cmd(run_root: Path, subcommand: str, *extra: str, pairs: list[str], config_name: str = "config.wave-engine.json") -> list[str]:
    run_root_container = "/wave-engine-native"
    command = [
        "docker",
        "compose",
        "-f",
        "freqtrade/docker-compose.yml",
        "-f",
        "freqtrade/docker-compose.research.yml",
        "run",
        "--rm",
        "-v",
        f"{run_root}:{run_root_container}",
        "freqtrade",
        subcommand,
        "--config",
        f"{run_root_container}/{config_name}",
        "--strategy",
        "CoinMasterWaveEngineV1",
        "--strategy-path",
        f"{run_root_container}/strategies",
        "--userdir",
        "/freqtrade/user_data",
    ]
    if subcommand != "list-strategies":
        command.extend(["--timeframe", "5m", "--pairs", *pairs])
    command.extend(extra)
    return command


def _commands_markdown(run_root: Path, timerange: str, pairs: list[str], commands: dict[str, list[str]]) -> str:
    lines = [
        "# Native Wave Engine research workspace",
        "",
        f"- Run root: `{run_root}`",
        f"- Timerange: `{timerange}`",
        f"- Pairs: `{', '.join(pairs)}`",
        "",
        "## Commands",
        "",
    ]
    for key, command in commands.items():
        lines.append(f"### {key}")
        lines.append("")
        lines.append("```bash")
        lines.append(" ".join(command))
        lines.append("```")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def maybe_run(label: str, command: list[str], execute: bool) -> dict[str, Any]:
    if not execute:
        return {"label": label, "executed": False, "command": command}
    completed = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    return {
        "label": label,
        "executed": True,
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a temporary native Freqtrade Wave Engine research workspace.")
    parser.add_argument("--timerange", default="20260101-20260427")
    parser.add_argument("--run-id")
    parser.add_argument("--workspace-root", default=str(RUNTIME_RESEARCH_ROOT))
    parser.add_argument("--pairs", nargs="+", default=["BTC/USDC:USDC", "ETH/USDC:USDC", "HYPE/USDC:USDC"])
    parser.add_argument("--execute", action="store_true", help="Run the requested native Freqtrade command(s) after preparing the workspace.")
    parser.add_argument(
        "--tasks",
        nargs="+",
        choices=["list_strategies", "backtesting", "lookahead_analysis", "recursive_analysis"],
        default=["list_strategies"],
    )
    args = parser.parse_args()

    prepared = prepare_workspace(
        timerange=args.timerange,
        pairs=args.pairs,
        run_id=args.run_id,
        workspace_root=Path(args.workspace_root),
    )
    results = [maybe_run(task, prepared["commands"][task], args.execute) for task in args.tasks]
    print(
        json.dumps(
            {
                "ok": True,
                "run_id": prepared["run_id"],
                "run_root": str(prepared["run_root"]),
                "config_path": str(prepared["config_path"]),
                "strategies_dir": str(prepared["strategies_dir"]),
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
