"""Retired legacy paper must be an explicit, observed state for GUI release."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from native_gui_peer_guard import PaperUnitState, retired_paper


def test_retired_paper_requires_all_four_observations() -> None:
    retired = PaperUnitState("inactive", "disabled", 0)
    assert retired_paper(retired, port_open=False)
    assert not retired_paper(retired, port_open=True)
    assert not retired_paper(PaperUnitState("active", "disabled", 4242), port_open=False)
    assert not retired_paper(PaperUnitState("failed", "disabled", 0), port_open=False)
    assert not retired_paper(PaperUnitState("inactive", "enabled", 0), port_open=False)
    assert not retired_paper(PaperUnitState("inactive", "disabled", 4242), port_open=False)
