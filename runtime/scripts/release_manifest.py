#!/usr/bin/env python3
"""Generate and verify the identity manifest embedded in a staged release."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCHEMA = "coinmaster-release-identity-v1"
CACHE_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache", "node_modules"}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def payload_tree(root: Path) -> dict[str, Any]:
    file_count = 0
    tree = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"release payload symlink is not allowed: {path.relative_to(root)}")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == "runtime/release-manifest.json":
            continue
        parts = Path(relative).parts
        if any(part in CACHE_DIRS for part in parts) or path.suffix in {".pyc", ".pyo"}:
            continue
        digest = sha256_file(path)
        file_count += 1
        tree.update(relative.encode("utf-8") + b"\0" + bytes.fromhex(digest) + b"\n")
    if file_count == 0:
        raise ValueError("staged release contains no payload files")
    return {"sha256": tree.hexdigest(), "file_count": file_count}


def code_tree(root: Path) -> dict[str, Any]:
    base = root / "coinmaster"
    files = sorted(
        path for path in base.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )
    rows: list[dict[str, str]] = []
    tree = hashlib.sha256()
    for path in files:
        if path.is_symlink():
            raise ValueError(f"runtime code symlink is not allowed: {path}")
        relative = path.relative_to(base).as_posix()
        digest = sha256_file(path)
        rows.append({"path": relative, "sha256": digest})
        tree.update(relative.encode("utf-8") + b"\0" + bytes.fromhex(digest) + b"\n")
    if not rows:
        raise ValueError("runtime/coinmaster contains no code files")
    return {"sha256": tree.hexdigest(), "file_count": len(rows), "files": rows}


def current_policy_hash(runtime_root: Path) -> str:
    source = runtime_root / "coinmaster/ops/hyperliquid_testnet.py"
    module = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    for node in ast.walk(module):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "execution_policy" for target in targets):
                value = ast.literal_eval(node.value)
                if not isinstance(value, dict):
                    raise ValueError("execution_policy must remain a literal mapping")
                canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
                return sha256_bytes(canonical)
    raise ValueError("execution_policy literal not found in the existing Stage-G gate")


def seal_inputs(runtime_root: Path) -> dict[str, str]:
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(runtime_root))
    from coinmaster.ops.stage_g_config import load_candidate

    candidate_path = runtime_root / "configs/stage-g-v1.json"
    approval_path = runtime_root / "configs/stage-g-hl-sandbox-approval.json"
    candidate_hash = load_candidate(candidate_path).sha256
    strategy_hash = sha256_file(runtime_root / "coinmaster/strategy/wave_overlay.py")
    policy_hash = current_policy_hash(runtime_root)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    expected_keys = {"schema", "candidate_sha256", "strategy_sha256", "execution_policy_sha256"}
    if set(approval) != expected_keys or approval.get("schema") != "coinmaster-stageg-hl-sandbox-approval-v1":
        raise ValueError("existing Stage-G approval schema changed")
    identities = {
        "candidate_sha256": candidate_hash,
        "strategy_sha256": strategy_hash,
        "execution_policy_sha256": policy_hash,
    }
    for name, value in identities.items():
        if approval.get(name) != value:
            raise ValueError(f"existing exact Stage-G seal mismatch: {name}")
    return {
        "candidate_config_sha256": sha256_file(candidate_path),
        "candidate_sha256": candidate_hash,
        "strategy_sha256": strategy_hash,
        "execution_policy_sha256": policy_hash,
        "approval_sha256": sha256_file(approval_path),
    }


def make_manifest(source_root: Path, runtime_root: Path, release_root: Path) -> dict[str, Any]:
    commit = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise ValueError("invalid source commit")
    status = subprocess.run(
        ["git", "-C", str(source_root), "status", "--porcelain=v1", "--untracked-files=all"],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    status = sorted(status)
    lock_path, project_path = runtime_root / "uv.lock", runtime_root / "pyproject.toml"
    if not lock_path.is_file() or not project_path.is_file():
        raise ValueError("pinned runtime dependency files are missing")
    return {
        "schema": SCHEMA,
        "source": {"commit": commit, "dirty": bool(status), "status": status},
        "release_tree": payload_tree(release_root),
        "runtime_coinmaster": code_tree(runtime_root),
        "sealed_inputs": seal_inputs(runtime_root),
        "pinned_dependencies": {
            "lockfile": "uv.lock",
            "lockfile_sha256": sha256_file(lock_path),
            "project_file": "pyproject.toml",
            "project_file_sha256": sha256_file(project_path),
        },
    }


def write_manifest(source_root: Path, runtime_root: Path, release_root: Path, output: Path) -> None:
    manifest = make_manifest(source_root, runtime_root, release_root)
    output.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"MANIFEST_WRITTEN commit={manifest['source']['commit']} dirty={str(manifest['source']['dirty']).lower()} release_sha256={manifest['release_tree']['sha256']}")


def verify_manifest(runtime_root: Path, release_root: Path, path: Path, expected_commit: str) -> None:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise ValueError("release manifest schema mismatch")
    source = manifest.get("source", {})
    if source.get("commit") != expected_commit or source.get("dirty") is not False or source.get("status") != []:
        raise ValueError("release manifest source identity mismatch")
    current = {
        "release_tree": payload_tree(release_root),
        "runtime_coinmaster": code_tree(runtime_root),
        "sealed_inputs": seal_inputs(runtime_root),
        "pinned_dependencies": {
            "lockfile": "uv.lock",
            "lockfile_sha256": sha256_file(runtime_root / "uv.lock"),
            "project_file": "pyproject.toml",
            "project_file_sha256": sha256_file(runtime_root / "pyproject.toml"),
        },
    }
    for name, value in current.items():
        if manifest.get(name) != value:
            raise ValueError(f"release manifest mismatch: {name}")
    print(f"MANIFEST_VERIFIED commit={expected_commit} code_sha256={current['runtime_coinmaster']['sha256']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    generate = subparsers.add_parser("generate")
    generate.add_argument("--source-root", type=Path, required=True)
    generate.add_argument("--runtime-root", type=Path, required=True)
    generate.add_argument("--release-root", type=Path, required=True)
    generate.add_argument("--output", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--runtime-root", type=Path, required=True)
    verify.add_argument("--release-root", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--expected-commit", required=True)
    args = parser.parse_args()
    try:
        if args.action == "generate":
            write_manifest(args.source_root.resolve(), args.runtime_root.resolve(), args.release_root.resolve(), args.output.resolve())
        else:
            verify_manifest(args.runtime_root.resolve(), args.release_root.resolve(), args.manifest.resolve(), args.expected_commit)
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"RELEASE_MANIFEST_ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
