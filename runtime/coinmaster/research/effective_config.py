"""Shared effective research candidate; no account or native-engine dependency."""
from dataclasses import replace
from coinmaster.domain.wave_overlay import Candidate

SELECTED_MAX_PARENT_NOTIONAL = 30_000_000.0


def effective_research_candidate(candidate: Candidate | None = None, *, selective_lifecycle_repairs: bool = False, capital_staging_seed=None) -> Candidate:
    """Apply the original selected CLI transformation to every API entry path."""
    candidate = candidate or Candidate()
    if capital_staging_seed is not None:
        if not selective_lifecycle_repairs:
            raise ValueError("STAGING_A_REQUIRES_SELECTED_LIFECYCLE")
        from coinmaster.strategy.sol_capital_staging import normalized_parent_ceiling
        return replace(candidate,max_parent_notional=float(normalized_parent_ceiling(capital_staging_seed)))
    if selective_lifecycle_repairs:
        return replace(candidate, max_parent_notional=SELECTED_MAX_PARENT_NOTIONAL)
    return candidate
