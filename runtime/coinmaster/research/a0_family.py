"""Exact registered R2 OFF/C0/A0 calls; source06 families remain unchanged."""
from inspect import signature
from coinmaster.research.registered_control import config_for, native_kwargs_json_roundtrip

FAMILY = "R2_A0_V1"
VARIANTS = {"R2_OFF": (None, False), "R2_C0": ("B2_F0", False), "R2_A0": ("B2_F0", True)}
START_MS, END_MS = 1725148800000, 1736899200000


def build_a0_kwargs(data_root, artifact_dir, variant, feed, *, start_ms=START_MS, end_ms=END_MS, standing_tp=False, sol_standing=False, trim_control=False):
    if variant not in VARIANTS:
        raise ValueError("A0_EXACT_VARIANT_REQUIRED")
    if not ((start_ms, end_ms) == (START_MS, END_MS) or 0 < end_ms - start_ms <= 48 * 3600000 or (standing_tp is True and (start_ms,end_ms)==(-86400000,90600000))):
        raise ValueError("A0_APPROVED_WINDOW_REQUIRED")
    from coinmaster.research.paired_prefix_run import build_native_kwargs
    kwargs = build_native_kwargs(config_for("R2"), data_root, artifact_dir, "OFF", feed, registered_control="R2")
    if type(standing_tp) is not bool: raise ValueError("STANDING_FLAG_MUST_BE_BOOL")
    if standing_tp and variant == "R2_OFF": raise ValueError("STANDING_OFF_CONTROL_MUST_USE_DEFAULT_FALSE")
    if type(sol_standing)is not bool or type(trim_control)is not bool:raise ValueError("CONTROL_FLAGS_MUST_BE_BOOL")
    if sol_standing and (not standing_tp or variant=="R2_OFF"):raise ValueError("SOL_STANDING_EXACT_FAMILY_REQUIRED")
    if trim_control and (not standing_tp or sol_standing or variant!="R2_C0"):raise ValueError("TRIM_EXACT_BTC_ONLY_CONTROL_REQUIRED")
    if standing_tp: kwargs["research_btc_standing_tp"] = True
    if sol_standing:kwargs["research_sol_standing_protection"]=True
    if trim_control:kwargs["research_btc_trim_control"]=True;kwargs["artifact_label"]="BTC_TRIM"
    kwargs["research_registered_control"] = None
    kwargs["research_a0_family"] = FAMILY
    kwargs["research_paired_prefix"], kwargs["research_a0_original_second"] = VARIANTS[variant]
    kwargs.update(trading_start_ms=start_ms, trading_end_ms=end_ms, artifact_label="BTC_TRIM"if trim_control else variant)
    _, restored = native_kwargs_json_roundtrip(kwargs)
    if restored != kwargs:
        raise ValueError("A0_KWARGS_ROUNDTRIP_FAILED")
    return restored


def validate_native_a0(actual):
    from coinmaster.research.native_baseline import run_native_diagnostic
    selectors = (actual["research_paired_prefix"], actual["research_a0_original_second"])
    variant = next((k for k, v in VARIANTS.items() if v == selectors), None)
    if actual["research_a0_family"] != FAMILY or variant is None:
        raise ValueError("A0_EXACT_FAMILY_REQUIRED")
    expected = build_a0_kwargs(actual["data_root"], actual["artifact_dir"], variant,
        actual["research_paired_signal_rows"], start_ms=actual["trading_start_ms"], end_ms=actual["trading_end_ms"], standing_tp=actual["research_btc_standing_tp"], sol_standing=actual.get("research_sol_standing_protection",False), trim_control=actual.get("research_btc_trim_control",False))
    bound = signature(run_native_diagnostic).bind(**expected)
    bound.apply_defaults()
    for key, value in bound.arguments.items():
        if type(actual[key]) is not type(value) or actual[key] != value:
            raise ValueError("A0_EXACT_NATIVE_ARGUMENT_REQUIRED:" + key)
