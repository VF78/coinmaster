"""Validate P0 evidence rather than silently invent venue constraints."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SnapshotEvidence:
    path: str
    sha256: str
    source: str
    collected_at: str


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(root: Path) -> dict:
    manifest = json.loads((root / "var/venue-manifest.json").read_text())
    for item in manifest["snapshots"]:
        evidence = SnapshotEvidence(**item)
        actual = sha256_file(root / evidence.path)
        if actual != evidence.sha256:
            raise ValueError(f"snapshot hash mismatch: {evidence.path}")
    return manifest
