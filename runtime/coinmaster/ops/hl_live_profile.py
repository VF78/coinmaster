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


INPUT_FLAGS={**FLAGS,'research_btc_split50':True,'research_btc_split_planref_v1':True,'research_btc_split_tp_ioc':True,
    'research_btc_split_discount':'0.0025','research_residual_recovery':True,'research_wait_4h':True,
    'research_regime_reentry_band':'0.5','research_c1_btc_cut_divisor':4,'research_c1_restore_dd':'0.40',
    'research_c1_global_cut_arm':False,'research_c1_first_fresh_h4':True,'research_c1_btc_postcut_d1':True}


def initial_capital_limit(value):
    """Canonical PRIVATE maximuminitial funding, never a future NAV ceiling."""
    from decimal import Decimal,InvalidOperation
    if type(value) is not str:raise RuntimeError('LIVE_INITIAL_CAPITAL_LIMIT_INVALID')
    try:amount=Decimal(value)
    except (InvalidOperation,ValueError):raise RuntimeError('LIVE_INITIAL_CAPITAL_LIMIT_INVALID') from None
    canonical=format(amount,'f')
    if '.' in canonical:canonical=canonical.rstrip('0').rstrip('.')
    if not amount.is_finite() or amount<=0 or canonical!=value:raise RuntimeError('LIVE_INITIAL_CAPITAL_LIMIT_INVALID')
    return amount


def _validate_input_readiness_profile(root,profile,candidate):
    from decimal import Decimal
    active=profile.get('profile_id')=='E4_C1_ACTIVE_SELECTED'
    keys={'schema','profile_id','initial_capital_usdc','candidate_sha256','research_source','economic_config_sha256',
        'strategy_flags','manage_only_readiness','input_readiness','live_order_capability','source_pins','deposit_protection_percent','retained_equity_floor_fraction','initialization_intent','account_mode','equity_basis'}
    if active:keys=keys|{'owner_start_required'}
    if (set(profile)!=keys or profile.get('schema')!=('coinmaster-live-selected-c1-v1' if active else 'coinmaster-live-input-readiness-v1') or (active and (profile.get('owner_start_required') is not True or profile.get('schema')!='coinmaster-live-selected-c1-v1')) or profile['account_mode'] not in ('disabled','unifiedAccount')
        or profile['equity_basis']!=('HYPERLIQUID_UNIFIED_SPOT_USDC_REPORTED_TOTAL_V1' if profile['account_mode']=='unifiedAccount' else 'HYPERLIQUID_CLASSIC_PERPS_ACCOUNT_VALUE_V1')
        or profile['initialization_intent'] not in (None,'INITIALIZE_FRESH_C1_EPOCH') or profile['profile_id'] not in ('E4_C1_INPUT_READINESS_ONLY','E4_C1_ACTIVE_SELECTED')
        or profile['manage_only_readiness'] is not (not active) or profile['input_readiness'] is not True or profile['live_order_capability'] is not active
        or profile['research_source']!='fccd60c01e8cae5e8258748b046f43f88a16bb79'
        or profile['economic_config_sha256']!='a2c7d88b5aff67399c0db849585bc5ad3625ce4e82068b3e29254d355c119253'
        or type(profile['deposit_protection_percent']) is not int or profile['deposit_protection_percent']!=55
        or profile['retained_equity_floor_fraction']!='0.45'
        or profile['strategy_flags']!=INPUT_FLAGS or profile['candidate_sha256']!=candidate_content_hash(candidate)):
        raise RuntimeError('LIVE_INPUT_PROFILE_MISMATCH')
    initial_capital_limit(profile['initial_capital_usdc'])
    required={'coinmaster/strategy/residual_recovery.py','coinmaster/strategy/wave_overlay.py','coinmaster/strategy/next_band.py',
        'coinmaster/strategy/hedge_band.py','coinmaster/domain/wave_overlay.py','coinmaster/strategy/c1_inputs.py','coinmaster/ops/hl_unified_account.py','coinmaster/ops/hl_unified_instruments.py',
        'coinmaster/ops/hl_live_execution.py','coinmaster/ops/hl_info_receipt.py','coinmaster/ops/hl_live_money.py'}
    if set(profile['source_pins'])!=required or any(hashlib.sha256((root/name).read_bytes()).hexdigest()!=digest for name,digest in profile['source_pins'].items()):
        raise RuntimeError('LIVE_INPUT_PROFILE_SOURCE_MISMATCH')
    return {**profile,'profile_sha256':hashlib.sha256(json.dumps(profile,sort_keys=True,separators=(',',':')).encode()).hexdigest()}


def load_live_profile(root: Path, candidate):
    selected=root / "configs/hl-live-selected.profile.json"
    path=selected if selected.exists() else root / "configs/hl-live-v3-dp50.profile.json"
    profile = json.loads(path.read_text())
    if profile.get('schema') in ('coinmaster-live-input-readiness-v1','coinmaster-live-selected-c1-v1'):return _validate_input_readiness_profile(root,profile,candidate)
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


def require_profile_deposit_parity(profile, projection):
    """Release gate only: never initializes/resets HWM or edits durable control."""
    expected = profile.get('deposit_protection_percent')
    if (type(expected) is not int or expected != 55
        or profile.get('retained_equity_floor_fraction') != '0.45'
        or type(projection.get('drawdown_limit_percent')) is not int
        or projection['drawdown_limit_percent'] != expected):
        raise RuntimeError('LIVE_DEPOSIT_PROFILE_STATE_MISMATCH')
    return True
