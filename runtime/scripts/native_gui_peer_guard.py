#!/usr/bin/env python3
"""Require an explicitly retired legacy paper unit before GUI deployment."""
from __future__ import annotations

import socket
import subprocess
from dataclasses import dataclass

PAPER = "coinmaster-paper.service"


@dataclass(frozen=True)
class PaperUnitState:
    active_state: str
    unit_file_state: str
    main_pid: int


def retired_paper(state: PaperUnitState, *, port_open: bool) -> bool:
    return (
        state.active_state == "inactive"
        and state.unit_file_state == "disabled"
        and state.main_pid == 0
        and not port_open
    )


def unit_property(name: str) -> str:
    return subprocess.check_output(
        ["systemctl", "show", "-P", name, PAPER], text=True,
    ).strip()


def paper_port_open() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 18181), timeout=0.5):
            return True
    except ConnectionRefusedError:
        return False


def main() -> None:
    state = PaperUnitState(
        active_state=unit_property("ActiveState"),
        unit_file_state=unit_property("UnitFileState"),
        main_pid=int(unit_property("MainPID")),
    )
    if not retired_paper(state, port_open=paper_port_open()):
        raise SystemExit("legacy paper is not explicitly retired (disabled, inactive, PID 0, port 18181 closed)")
    print("RETIRED_DISABLED")


if __name__ == "__main__":
    main()
