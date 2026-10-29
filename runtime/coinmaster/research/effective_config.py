"""Shared effective research candidate; no account or native-engine dependency."""
from dataclasses import replace
from coinmaster.domain.wave_overlay import Candidate

SELECTED_MAX_PARENT_NOTIONAL = 30_000_000.0


def effective_research_candidate(candidate: Candidate | None = None, *, selective_lifecycle_repairs: bool = False) -> Candidate:
    """Apply the original selected CLI transformation to every API entry path."""
    candidate = candidate or Candidate()
    if selective_lifecycle_repairs:
        return replace(candidate, max_parent_notional=SELECTED_MAX_PARENT_NOTIONAL)
    return candidate
