from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/native_gui_stage_cleanup.py"
spec = importlib.util.spec_from_file_location("native_gui_stage_cleanup", SCRIPT)
assert spec and spec.loader
cleanup_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cleanup_module)


def setup_paths(tmp_path: Path, commit: str) -> tuple[Path, Path, Path, Path, Path]:
    base = tmp_path / "gui"
    releases = base / "releases"
    releases.mkdir(parents=True)
    archive_root = tmp_path / "tmp"
    archive_root.mkdir()
    current = base / "current"
    active_release = releases / "other-release"
    active_release.mkdir()
    current.symlink_to(active_release)
    incoming = releases / f"{commit}.incoming"
    incoming.mkdir()
    (incoming / "partial.txt").write_text("incomplete", encoding="utf-8")
    archive = archive_root / f"coinmaster-native-gui-{commit}.tar.gz"
    archive.write_bytes(b"partial archive")
    return base, archive_root, current, incoming, archive


def test_cleanup_removes_only_exact_incomplete_stage_and_is_idempotent(tmp_path: Path) -> None:
    commit = "a" * 40
    base, archive_root, current, incoming, archive = setup_paths(tmp_path, commit)
    assert cleanup_module.cleanup_stage(base, archive_root, current, commit) == (True, True)
    assert not incoming.exists()
    assert not archive.exists()
    assert cleanup_module.cleanup_stage(base, archive_root, current, commit) == (False, False)


def test_cleanup_refuses_complete_release_and_preserves_artifacts(tmp_path: Path) -> None:
    commit = "b" * 40
    base, archive_root, current, incoming, archive = setup_paths(tmp_path, commit)
    (base / "releases" / commit).mkdir()
    with pytest.raises(ValueError, match="complete release"):
        cleanup_module.cleanup_stage(base, archive_root, current, commit)
    assert incoming.exists() and archive.exists()


def test_cleanup_refuses_active_release_and_preserves_artifacts(tmp_path: Path) -> None:
    commit = "c" * 40
    base, archive_root, current, incoming, archive = setup_paths(tmp_path, commit)
    (base / "releases" / commit).mkdir()
    current.unlink()
    current.symlink_to(base / "releases" / commit)
    with pytest.raises(ValueError, match="active GUI release"):
        cleanup_module.cleanup_stage(base, archive_root, current, commit)
    assert incoming.exists() and archive.exists()


def test_cleanup_refuses_receipted_stage_and_preserves_artifacts(tmp_path: Path) -> None:
    commit = "d" * 40
    base, archive_root, current, incoming, archive = setup_paths(tmp_path, commit)
    (incoming / "stage.receipt").write_text("verified", encoding="utf-8")
    with pytest.raises(ValueError, match="receipt"):
        cleanup_module.cleanup_stage(base, archive_root, current, commit)
    assert incoming.exists() and archive.exists()


def test_cleanup_refuses_symlinked_incoming_and_preserves_target(tmp_path: Path) -> None:
    commit = "e" * 40
    base, archive_root, current, incoming, archive = setup_paths(tmp_path, commit)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    shutil.rmtree(incoming)
    incoming.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        cleanup_module.cleanup_stage(base, archive_root, current, commit)
    assert (outside / "keep.txt").exists() and archive.exists()
