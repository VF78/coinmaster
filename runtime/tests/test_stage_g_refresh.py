from __future__ import annotations

import json
from datetime import UTC, datetime

from coinmaster.ops import stage_g_refresh as refresh
from coinmaster.ops.stage_g_warmup import DAY_MS


def _pointer(tmp_path, end_ms):
    artifact = tmp_path / "verified-current"
    artifact.mkdir()
    manifest = artifact / "manifest.json"
    manifest.write_text(json.dumps({"warmup_end_exclusive_ms": end_ms}))
    (tmp_path / "current").symlink_to(artifact.name, target_is_directory=True)
    return manifest


def test_refresh_noop_keeps_verified_pointer_and_does_not_fetch(tmp_path, monkeypatch):
    day = int(datetime(2026, 9, 24, tzinfo=UTC).timestamp() * 1000)
    manifest = _pointer(tmp_path, day)
    monkeypatch.setattr(refresh, "load_stageg_bybit_warmup", lambda path, now_ms: ({}, "READY"))
    monkeypatch.setattr(refresh, "ingest", lambda *_: (_ for _ in ()).throw(AssertionError("unexpected fetch")))
    assert refresh.refresh_stageg_warmup(tmp_path, now_ms=day + DAY_MS // 2) == manifest
    assert (tmp_path / "current").resolve() == manifest.parent


def test_refresh_fetches_only_missing_completed_utc_tail(tmp_path, monkeypatch):
    day = int(datetime(2026, 9, 24, tzinfo=UTC).timestamp() * 1000)
    _pointer(tmp_path, day - DAY_MS)
    calls = []

    def fake_ingest(start, end, tail):
        calls.append((start, end))
        source = tail / "bybit"
        source.mkdir(parents=True)
        (source / "manifest.json").write_text(json.dumps({"raw_manifest_sha256": "a" * 64}))

    def fake_extend(*, predecessor_manifest, tail_root, output_root, now_ms):
        output_root.mkdir()
        manifest = output_root / "manifest.json"
        manifest.write_text(json.dumps({"warmup_end_exclusive_ms": now_ms}))
        return manifest

    monkeypatch.setattr(refresh, "ingest", fake_ingest)
    monkeypatch.setattr(refresh, "extend_stageg_bybit_warmup", fake_extend)
    monkeypatch.setattr(refresh, "load_stageg_bybit_warmup", lambda path, now_ms: ({}, "READY"))
    result = refresh.refresh_stageg_warmup(tmp_path, now_ms=day + DAY_MS // 2)
    assert calls == [("2026-09-23T00:00:00+00:00", "2026-09-24T00:00:00+00:00")]
    assert (tmp_path / "current" / "manifest.json").resolve() == result
    assert refresh.refresh_stageg_warmup(tmp_path, now_ms=day + DAY_MS // 2) == result
    assert len(calls) == 1
