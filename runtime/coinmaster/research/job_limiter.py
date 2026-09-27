"""Apply the native research child OS memory ceiling, then exec it."""
from __future__ import annotations

import os
import resource
import sys


MAX_ADDRESS_SPACE_BYTES = 1536 * 1024 * 1024
MIN_ADDRESS_SPACE_BYTES = 64 * 1024 * 1024


def main() -> None:
    if len(sys.argv) < 4 or sys.argv[2] != "--":
        print("RESEARCH_RESOURCE_LAUNCHER_INVALID_ARGUMENTS", file=sys.stderr, flush=True)
        raise SystemExit(125)
    try:
        requested = int(sys.argv[1])
        if not MIN_ADDRESS_SPACE_BYTES <= requested <= MAX_ADDRESS_SPACE_BYTES:
            raise ValueError("address-space ceiling outside policy")
        soft, hard = resource.getrlimit(resource.RLIMIT_AS)
        effective = requested
        for inherited in (soft, hard):
            if inherited != resource.RLIM_INFINITY:
                effective = min(effective, inherited)
        if effective < MIN_ADDRESS_SPACE_BYTES:
            raise ValueError("inherited address-space ceiling below minimum")
        # Equal soft and hard limits make the ceiling non-increasable by the
        # research process after exec.
        resource.setrlimit(resource.RLIMIT_AS, (effective, effective))
    except (AttributeError, OSError, ValueError) as error:
        print(f"RESEARCH_ADDRESS_SPACE_LIMIT_UNAVAILABLE:{type(error).__name__}", file=sys.stderr, flush=True)
        raise SystemExit(125)

    command = sys.argv[3:]
    try:
        os.execvpe(command[0], command, os.environ)
    except OSError as error:
        print(f"RESEARCH_CHILD_EXEC_FAILED:{type(error).__name__}", file=sys.stderr, flush=True)
        raise SystemExit(127)


if __name__ == "__main__":
    main()
