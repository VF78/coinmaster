"""Exact owner-approved technical profile; this seal never grants real orders."""
import hashlib
import json
from pathlib import Path

from coinmaster.ops.stage_g_config import candidate_content_hash

FLAGS = {
    "research_v0_execution_repairs": True,
    "research_v0_zero_tp_netting": False,
    "research_v0_deferred_selective_zero_tp": True,
    "research_v0_selective_lifecycle_repairs": True,
    "research_btc_direction_sizing": True,
    "tp_fee_floor_v1": False,
}


def load_live_profile(root: Path, candidate):
    path = root / "configs/hl-live-v3-dp50.profile.json"
    profile = json.loads(path.read_text())
    if (set(profile) != {"schema", "profile_id", "initial_capital_usdc",
                         "deposit_protection_percent", "research_source",
                         "candidate_sha256", "strategy_sha256", "domain_sha256", "strategy_flags",
                         "btc_long_notional_multiplier", "btc_short_notional_multiplier"}
            or profile["schema"] != "coinmaster-live-technical-profile-v1"
            or profile["profile_id"] != "V3+DP50"
            or profile["initial_capital_usdc"] != "82"
            or profile["deposit_protection_percent"] != 50
            or profile["research_source"] != "a9cbb737a5239d10b9ffcb97d55f997917945263"
            or profile["btc_long_notional_multiplier"] != "5.5"
            or profile["btc_short_notional_multiplier"] != "7.875"
            or profile["strategy_flags"] != FLAGS
            or profile["candidate_sha256"] != candidate_content_hash(candidate)):
        raise RuntimeError("LIVE_TECHNICAL_PROFILE_MISMATCH")
    for key, relative in (("strategy_sha256", "coinmaster/strategy/wave_overlay.py"),
                          ("domain_sha256", "coinmaster/domain/wave_overlay.py")):
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != profile[key]:
            raise RuntimeError("LIVE_TECHNICAL_PROFILE_SOURCE_MISMATCH")
    return {**profile, "profile_sha256": hashlib.sha256(
        json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
