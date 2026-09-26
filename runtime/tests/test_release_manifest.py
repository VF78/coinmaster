from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/release_manifest.py"
spec = importlib.util.spec_from_file_location("release_manifest", SCRIPT)
assert spec and spec.loader
release_manifest = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = release_manifest
spec.loader.exec_module(release_manifest)


def fixture_source(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    runtime = source / "runtime"
    for relative in (
        "coinmaster/__init__.py",
        "coinmaster/domain/__init__.py",
        "coinmaster/domain/wave_overlay.py",
        "coinmaster/ops/__init__.py",
        "coinmaster/ops/stage_g_config.py",
        "coinmaster/ops/hyperliquid_testnet.py",
        "coinmaster/strategy/__init__.py",
        "coinmaster/strategy/wave_overlay.py",
        "configs/stage-g-v1.json",
        "configs/stage-g-hl-sandbox-approval.json",
        "uv.lock",
        "pyproject.toml",
    ):
        destination = runtime / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        source_file = ROOT / relative
        if source_file.is_file():
            shutil.copy2(source_file, destination)
        else:
            destination.write_text("", encoding="utf-8")
    (runtime / "coinmaster/ops/fixture_executable.py").write_text("VALUE = 1\n")
    import subprocess

    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Fixture"], check=True)
    subprocess.run(["git", "-C", str(source), "add", "runtime"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "fixture"], check=True)
    return source, runtime


def test_manifest_is_deterministic_for_same_clean_release(tmp_path: Path) -> None:
    source, runtime = fixture_source(tmp_path)
    first = release_manifest.make_manifest(source, runtime)
    second = release_manifest.make_manifest(source, runtime)
    assert first == second
    assert first["source"]["dirty"] is False
    assert first["runtime_coinmaster"]["file_count"] == 9


def test_verify_detects_executable_code_mismatch(tmp_path: Path) -> None:
    source, runtime = fixture_source(tmp_path)
    manifest = release_manifest.make_manifest(source, runtime)
    output = runtime / "release-manifest.json"
    output.write_text(json.dumps(manifest, sort_keys=True))
    (runtime / "coinmaster/ops/fixture_executable.py").write_text("VALUE = 2\n")
    with pytest.raises(ValueError, match="mismatch: runtime_coinmaster"):
        release_manifest.verify_manifest(runtime, output, manifest["source"]["commit"])


def test_generate_records_dirty_source_status(tmp_path: Path) -> None:
    source, runtime = fixture_source(tmp_path)
    (source / "runtime/fixture-untracked.txt").write_text("change\n")
    manifest = release_manifest.make_manifest(source, runtime)
    assert manifest["source"]["dirty"] is True
    assert manifest["source"]["status"] == ["?? runtime/fixture-untracked.txt"]
