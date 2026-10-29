"""Shared structural execution-mode validation; no engine or account dependency."""


def validate_zero_tp_modes(*,deferred_selective_zero_tp: bool,zero_tp_netting: bool) -> None:
    """The deferred selector already computes net entry quantity once."""
    if deferred_selective_zero_tp and zero_tp_netting:
        raise ValueError("DEFERRED_SELECTIVE_REQUIRES_ORIGINAL_ZERO_TP_BASE")
