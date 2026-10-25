"""Explicit engineering-only R2/R3 family; legacy economic launcher is unchanged."""
from pathlib import Path
from inspect import signature
import hashlib
import json

CONFIG_PINS = {
    "R2": "d9ea9c51260941c58cd483ea25a5ad80b85bbdccc7754fe092ad964ed08247ea",
    "R3": "375a644eaa0a6634a2a8c22434824a49fddcca732542e2ade4b802ac644bfd80",
}

def config_for(family):
    if type(family) is not str or family not in CONFIG_PINS:
        raise ValueError("UNREGISTERED_ENGINEERING_CONTROL")
    path = Path(__file__).parent / "control_configs" / (family + ".json")
    if hashlib.sha256(path.read_bytes()).hexdigest() != CONFIG_PINS[family]:
        raise ValueError("REGISTERED_CONTROL_CONFIG_PIN_MISMATCH")
    return json.loads(path.read_text())

def validate_config(config, family):
    expected = config_for(family)
    # Canonical JSON preserves boolean/number distinction (True != 1 here).
    canonical = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if canonical(config) != canonical(expected):
        raise ValueError("EXACT_REGISTERED_CONTROL_CONFIG_REQUIRED")

def build_registered_control_kwargs(config, family, data_root, artifact_dir, feed, start_ms, end_ms):
    if any(type(t) is not int for t in (start_ms, end_ms)) or not 0 < end_ms-start_ms <= 48*3600*1000:
        raise ValueError("ENGINEERING_FIXTURE_MAX_48_HOURS")
    from coinmaster.research.paired_prefix_run import build_native_kwargs
    kwargs = build_native_kwargs(config, data_root, artifact_dir, "OFF", feed, registered_control=family)
    kwargs.update(trading_start_ms=start_ms, trading_end_ms=end_ms, artifact_label="registered-control-"+family)
    return kwargs

def validate_native_control(actual):
    """Check the complete real call, including defaults, before engine creation."""
    from coinmaster.research.paired_prefix_run import build_native_kwargs
    from coinmaster.research.native_baseline import run_native_diagnostic
    family=actual["research_registered_control"]
    expected=build_native_kwargs(config_for(family), actual["data_root"], actual["artifact_dir"], "OFF", actual["research_paired_signal_rows"], registered_control=family)
    bound=signature(run_native_diagnostic).bind(**expected);bound.apply_defaults()
    context={"data_root", "artifact_dir", "artifact_label", "trading_start_ms", "trading_end_ms", "research_paired_signal_rows"}
    for key, value in bound.arguments.items():
        if key not in context and (type(actual[key]) is not type(value) or actual[key] != value):
            raise ValueError("REGISTERED_NATIVE_ARGUMENT_MISMATCH:"+key)
    start,end=actual["trading_start_ms"],actual["trading_end_ms"]
    if any(type(t) is not int for t in (start,end)) or not 0 < end-start <= 48*3600*1000:
        raise ValueError("ENGINEERING_FIXTURE_MAX_48_HOURS")
