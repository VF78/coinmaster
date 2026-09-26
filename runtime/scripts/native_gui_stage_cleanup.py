#!/usr/bin/env python3
"""Remove only an incomplete, inactive GUI release stage for one exact commit."""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


def cleanup_stage(base: Path, archive_root: Path, current: Path, commit: str) -> tuple[bool, bool]:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("invalid commit SHA")
    releases = (base / "releases").resolve(strict=True)
    release = releases / commit
    incoming = releases / f"{commit}.incoming"
    current_target = current.resolve(strict=False)
    if current_target == release:
        raise ValueError("cannot clean the active GUI release")
    if release.exists() or release.is_symlink():
        raise ValueError("complete release exists; refusing cleanup")

    if incoming.is_symlink():
        raise ValueError("incoming stage is a symlink; refusing cleanup")
    incoming_exists = incoming.exists()
    if incoming_exists:
        if incoming.resolve(strict=True) != release.with_name(f"{commit}.incoming"):
            raise ValueError("incoming stage realpath escaped release directory")
        if not incoming.is_dir():
            raise ValueError("incoming stage is not a directory")
        if (incoming / "stage.receipt").exists():
            raise ValueError("incoming stage has a receipt; refusing cleanup")

    archive_dir = archive_root.resolve(strict=True)
    archive = archive_dir / f"coinmaster-native-gui-{commit}.tar.gz"
    if archive.is_symlink():
        raise ValueError("staged archive is a symlink; refusing cleanup")
    archive_exists = archive.exists()
    if archive_exists:
        if archive.resolve(strict=True) != archive:
            raise ValueError("staged archive realpath escaped temporary directory")
        if not archive.is_file():
            raise ValueError("staged archive is not a regular file")

    # Validate every target before removing either one; repeated cleanup is safe.
    if incoming_exists:
        shutil.rmtree(incoming)
    if archive_exists:
        archive.unlink()
    return incoming_exists, archive_exists


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("commit")
    args = parser.parse_args()
    try:
        incoming, archive = cleanup_stage(args.base, args.archive_root, args.current, args.commit)
    except (OSError, ValueError) as error:
        print(f"STAGE_CLEANUP_REFUSED: {error}")
        return 1
    print(f"STAGE_CLEANUP_OK commit={args.commit} incoming_removed={str(incoming).lower()} archive_removed={str(archive).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
