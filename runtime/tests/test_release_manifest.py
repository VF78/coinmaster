from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
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


def fixture_source(tmp_path: Path, *, strategy_mismatch: bool = False) -> tuple[Path, Path, Path]:
    source = tmp_path / "source"
    release = source / "payload"
    runtime = release / "runtime"
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
    scripts = runtime / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "deploy_native_gui.sh").write_text("#!/bin/sh\nexit 0\n")
    web_assets = release / "web/assets"
    web_assets.mkdir(parents=True)
    (web_assets / "app.js").write_text("window.release = 'fixture';\n")
    (release / "web/index.html").write_text("<!doctype html><script src='/assets/app.js'></script>\n")
    strategy = runtime / "coinmaster/strategy/wave_overlay.py"
    approval = runtime / "configs/stage-g-hl-sandbox-approval.json"
    approval_data = json.loads(approval.read_text(encoding="utf-8"))
    approval_data["strategy_sha256"] = hashlib.sha256(strategy.read_bytes()).hexdigest()
    if strategy_mismatch:
        strategy.write_text("STRATEGY_CODE_CHANGED = True\n", encoding="utf-8")
    approval.write_text(json.dumps(approval_data, sort_keys=True) + "\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Fixture"], check=True)
    subprocess.run(["git", "-C", str(source), "add", "payload"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "fixture"], check=True)
    return source, runtime, release


def test_manifest_is_deterministic_for_same_clean_release(tmp_path: Path) -> None:
    source, runtime, release = fixture_source(tmp_path)
    first = release_manifest.make_manifest(source, runtime, release)
    second = release_manifest.make_manifest(source, runtime, release)
    assert first == second
    assert first["source"]["dirty"] is False
    assert first["runtime_coinmaster"]["file_count"] == 9
    assert first["release_tree"]["file_count"] > first["runtime_coinmaster"]["file_count"]


@pytest.mark.parametrize(
    ("relative", "changed"),
    [
        ("runtime/scripts/deploy_native_gui.sh", "#!/bin/sh\nexit 1\n"),
        ("web/assets/app.js", "window.release = 'tampered';\n"),
    ],
)
def test_verify_detects_script_and_web_asset_mismatch(tmp_path: Path, relative: str, changed: str) -> None:
    source, runtime, release = fixture_source(tmp_path)
    manifest = release_manifest.make_manifest(source, runtime, release)
    output = runtime / "release-manifest.json"
    output.write_text(json.dumps(manifest, sort_keys=True))
    (release / relative).write_text(changed, encoding="utf-8")
    with pytest.raises(ValueError, match="mismatch: release_tree"):
        release_manifest.verify_manifest(runtime, release, output, manifest["source"]["commit"])


def test_gui_manifest_accepts_strategy_change_but_trader_manifest_rejects_it(tmp_path: Path) -> None:
    source, runtime, release = fixture_source(tmp_path, strategy_mismatch=True)
    manifest = release_manifest.make_manifest(source, runtime, release, component="gui")
    assert manifest["component"] == "gui"
    assert "sealed_inputs" not in manifest
    strategy_hash = hashlib.sha256((runtime / "coinmaster/strategy/wave_overlay.py").read_bytes()).hexdigest()
    assert any(row["sha256"] == strategy_hash and row["path"] == "strategy/wave_overlay.py" for row in manifest["runtime_coinmaster"]["files"])
    output = runtime / "release-manifest.json"
    output.write_text(json.dumps(manifest, sort_keys=True))

    release_manifest.verify_manifest(runtime, release, output, manifest["source"]["commit"], component="gui")
    with pytest.raises(ValueError, match="component mismatch"):
        release_manifest.verify_manifest(runtime, release, output, manifest["source"]["commit"], component="trader")
    with pytest.raises(ValueError, match="strategy_sha256"):
        release_manifest.make_manifest(source, runtime, release, component="trader")


def test_generate_records_dirty_source_status(tmp_path: Path) -> None:
    source, runtime, release = fixture_source(tmp_path)
    (source / "runtime-fixture-untracked.txt").write_text("change\n")
    manifest = release_manifest.make_manifest(source, runtime, release)
    assert manifest["source"]["dirty"] is True
    assert manifest["source"]["status"] == ["?? runtime-fixture-untracked.txt"]
