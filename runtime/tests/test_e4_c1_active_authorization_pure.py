"""Actual authorization functions via AST; synthetic temp metadata, no native imports."""
import ast
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1] / "coinmaster"
PINS = (
    "strategy/residual_recovery.py", "strategy/wave_overlay.py", "strategy/next_band.py",
    "strategy/hedge_band.py", "domain/wave_overlay.py", "strategy/c1_inputs.py",
    "ops/hl_unified_account.py", "ops/hl_unified_instruments.py", "ops/hl_live_execution.py",
    "ops/hl_info_receipt.py", "ops/hl_live_money.py",
)
UNIFIED = "HYPERLIQUID_UNIFIED_SPOT_USDC_REPORTED_TOTAL_V1"
ACTIVE_SCHEMA = "coinmaster-live-selected-c1-v1"
PREPARE_SCHEMA = "coinmaster-live-input-readiness-v1"


def selected_nodes(relative, names):
    tree = ast.parse((ROOT / relative).read_text())
    nodes = []
    for item in tree.body:
        if isinstance(item, (ast.ClassDef, ast.FunctionDef)) and item.name in names:
            nodes.append(item)
        elif isinstance(item, ast.Assign) and any(isinstance(n, ast.Name) and n.id in names for n in item.targets):
            nodes.append(item)
    return nodes


def execute(nodes, namespace):
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, *nodes], type_ignores=[]))
    exec(compile(module, "actual_authorization_source", "exec"), namespace)


@pytest.fixture(scope="module")
def code():
    env = dict(__name__=__name__, Path=Path, json=json, hashlib=hashlib, dataclass=dataclass, asdict=asdict)
    execute(selected_nodes("domain/wave_overlay.py", {"Candidate"}), env)
    execute(selected_nodes("ops/stage_g_config.py", {"canonical_candidate_json", "candidate_content_hash"}), env)
    execute(selected_nodes("ops/hl_live_profile.py", {"FLAGS", "INPUT_FLAGS", "initial_capital_limit", "ACTUAL_INITIAL_CAPITAL_POLICY", "actual_initial_capital",
        "_validate_input_readiness_profile", "load_live_profile"}), env)
    execute(selected_nodes("ops/hl_live_worker.py", {"require_live_order_approval"}), env)
    return env


def profile_metadata(tmp_path, code, *, active=True, cap="100", initialization=None):
    candidate = code["Candidate"]()
    pins = {}
    for relative in PINS:
        name = "coinmaster/" + relative
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = ("# SYNTHETIC METADATA PIN ONLY: " + relative + "\n").encode()
        path.write_bytes(payload)
        pins[name] = hashlib.sha256(payload).hexdigest()
    profile = dict(schema=ACTIVE_SCHEMA if active else PREPARE_SCHEMA,
        profile_id="E4_C1_ACTIVE_SELECTED" if active else "E4_C1_INPUT_READINESS_ONLY",
        initial_capital_usdc=cap, candidate_sha256=code["candidate_content_hash"](candidate),
        research_source="fccd60c01e8cae5e8258748b046f43f88a16bb79",
        economic_config_sha256="a2c7d88b5aff67399c0db849585bc5ad3625ce4e82068b3e29254d355c119253",
        strategy_flags=deepcopy(code["INPUT_FLAGS"]), manage_only_readiness=not active,
        input_readiness=True, live_order_capability=active, source_pins=pins,
        deposit_protection_percent=55, retained_equity_floor_fraction="0.45",
        initialization_intent=initialization, account_mode="unifiedAccount", equity_basis=UNIFIED)
    if active:
        profile["owner_start_required"] = True
    return profile, candidate


def ticket_metadata(tmp_path, code, *, active=True, cap="100", initialization=None, legacy=False):
    base, candidate = profile_metadata(tmp_path, code, active=active, cap=cap, initialization=initialization)
    profile = code["_validate_input_readiness_profile"](tmp_path, base, candidate)
    identity = dict(source_commit="SYNTHETIC_NOT_A_DEPLOYED_RELEASE", strategy_sha256="1" * 64,
        candidate_sha256=profile["candidate_sha256"], profile_sha256=profile["profile_sha256"],
        initial_capital_limit_usdc=cap, account_mode=profile["account_mode"], equity_basis=profile["equity_basis"],
        money_currency="USDC", research_source=profile["research_source"], economic_config_sha256=profile["economic_config_sha256"])
    fingerprint = {"master_address_sha256": hashlib.sha256(b"SYNTHETIC_NO_ACCOUNT_ADDRESS").hexdigest()}
    start = active or initialization is not None
    approval = dict(schema="coinmaster-live-order-approval-v1" if legacy else "coinmaster-live-order-approval-v2",
        instance_id="hl-stageg-live", release_commit=identity["source_commit"],
        master_address_sha256=fingerprint["master_address_sha256"], strategy_sha256=identity["strategy_sha256"],
        candidate_sha256=identity["candidate_sha256"], profile_sha256=identity["profile_sha256"],
        initial_capital_limit_usdc=cap, account_mode=profile["account_mode"], equity_basis=profile["equity_basis"],
        authorization="START_LIVE_E4_C1" if start else "PREPARE_ONLY", start_approved=start,
        orders_approved=True if legacy else start)
    if legacy:
        approval["pilot_capital_usdc"] = cap
    paths = (tmp_path / "synthetic-approval.json", tmp_path / "synthetic-fingerprint.json", tmp_path)
    return profile, identity, fingerprint, approval, paths


def write_metadata(identity, fingerprint, approval, paths):
    approval_path, fingerprint_path, root = paths
    approval_path.write_text(json.dumps(approval))
    fingerprint_path.write_text(json.dumps(fingerprint))
    (root / "live-release.json").write_text(json.dumps(identity))


@pytest.mark.parametrize("value", ["72", "108", "100", "72.5", "0.125"])
def test_canonical_private_initial_capital_is_not_literal_82(code, value):
    assert code["initial_capital_limit"](value) == Decimal(value)


@pytest.mark.parametrize("value", ["0", "-1", "-0", "NaN", "sNaN", "Inf", "Infinity", "-Infinity",
    "1e2", "1E+2", "1e-2", "100.0", "72.50", "01", "+1", " 72", "72 ", "1_00", "", None, 100, True])
def test_noncanonical_or_nonpositive_cap_denied(code, value):
    with pytest.raises(RuntimeError, match="LIVE_INITIAL_CAPITAL_LIMIT_INVALID"):
        code["initial_capital_limit"](value)


@pytest.mark.parametrize("active,cap", [(True, "72"), (True, "108"), (True, "100"), (True, "72.5"), (False, "108")])
def test_selected_profile_real_candidate_flags_hash_and_source_pins(tmp_path, code, active, cap):
    profile, candidate = profile_metadata(tmp_path, code, active=active, cap=cap)
    before = deepcopy(profile)
    result = code["_validate_input_readiness_profile"](tmp_path, profile, candidate)
    assert profile == before and result["strategy_flags"] == code["INPUT_FLAGS"]
    assert result["profile_sha256"] == hashlib.sha256(json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert result["live_order_capability"] is active


@pytest.mark.parametrize("active,field,value", [
    (True, "schema", PREPARE_SCHEMA), (False, "schema", ACTIVE_SCHEMA), (False, "schema", "unknown"),
    (True, "owner_start_required", False), (True, "manage_only_readiness", True),
    (False, "manage_only_readiness", False), (True, "live_order_capability", False),
    (False, "live_order_capability", True), (True, "input_readiness", False),
    (True, "profile_id", "UNKNOWN_ROLE"), (True, "equity_basis", "OTHER_BASIS"),
    (True, "account_mode", "portfolioMargin"), (True, "initial_capital_usdc", "100.0"),
    (True, "deposit_protection_percent", 45), (True, "retained_equity_floor_fraction", "0.55"),
])
def test_profile_role_schema_flags_and_money_mismatch_denied(tmp_path, code, active, field, value):
    profile, candidate = profile_metadata(tmp_path, code, active=active)
    profile[field] = value
    with pytest.raises(RuntimeError):
        code["_validate_input_readiness_profile"](tmp_path, profile, candidate)


def test_profile_economic_candidate_and_actual_root_pin_tamper_denied(tmp_path, code):
    profile, candidate = profile_metadata(tmp_path, code)
    wrong = deepcopy(profile)
    wrong["strategy_flags"]["research_c1_btc_cut_divisor"] = 2
    with pytest.raises(RuntimeError, match="LIVE_INPUT_PROFILE_MISMATCH"):
        code["_validate_input_readiness_profile"](tmp_path, wrong, candidate)
    with pytest.raises(RuntimeError, match="LIVE_INPUT_PROFILE_MISMATCH"):
        code["_validate_input_readiness_profile"](tmp_path, profile, replace(candidate, ema_period=candidate.ema_period + 1))
    target = tmp_path / next(iter(profile["source_pins"]))
    target.write_bytes(target.read_bytes() + b"changed")
    with pytest.raises(RuntimeError, match="LIVE_INPUT_PROFILE_SOURCE_MISMATCH"):
        code["_validate_input_readiness_profile"](tmp_path, profile, candidate)


def test_selected_profile_filename_has_priority_without_legacy_fallback(tmp_path, code):
    selected, candidate = profile_metadata(tmp_path, code)
    (tmp_path / "configs").mkdir()
    selected_path = tmp_path / "configs/hl-live-selected.profile.json"
    selected_path.write_text(json.dumps(selected))
    (tmp_path / "configs/hl-live-v3-dp50.profile.json").write_text("invalid legacy must not be read")
    assert code["load_live_profile"](tmp_path, candidate)["profile_id"] == "E4_C1_ACTIVE_SELECTED"
    selected["live_order_capability"] = False
    selected_path.write_text(json.dumps(selected))
    with pytest.raises(RuntimeError):
        code["load_live_profile"](tmp_path, candidate)


@pytest.mark.parametrize("active,initialization", [(True, None), (False, None), (False, "INITIALIZE_FRESH_C1_EPOCH")])
def test_exact_selected_v2_start_or_readonly_preparation(tmp_path, code, active, initialization):
    profile, identity, fingerprint, approval, paths = ticket_metadata(tmp_path, code, active=active, initialization=initialization)
    write_metadata(identity, fingerprint, approval, paths)
    result = code["require_live_order_approval"](*paths, profile=profile)
    assert result == approval
    assert result["orders_approved"] is (active or initialization is not None)
    if not active and initialization is None:
        assert result["authorization"] == "PREPARE_ONLY" and result["orders_approved"] is False


@pytest.mark.parametrize("target,field,value", [
    ("approval", "schema", "coinmaster-live-order-approval-v1"), ("approval", "schema", "unknown"),
    ("approval", "instance_id", "wrong-instance"), ("approval", "release_commit", "wrong-source"),
    ("approval", "master_address_sha256", "wrong-account"), ("approval", "strategy_sha256", "wrong-strategy"),
    ("approval", "candidate_sha256", "wrong-candidate"), ("approval", "profile_sha256", "wrong-profile"),
    ("approval", "initial_capital_limit_usdc", "108"), ("approval", "initial_capital_limit_usdc", "100.0"),
    ("approval", "account_mode", "disabled"), ("approval", "equity_basis", "wrong-basis"),
    ("approval", "authorization", "PREPARE_ONLY"), ("approval", "start_approved", False),
    ("approval", "orders_approved", False), ("profile", "profile_id", "E4_C1_INPUT_READINESS_ONLY"),
    ("identity", "initial_capital_limit_usdc", "108"), ("identity", "account_mode", "disabled"),
    ("identity", "equity_basis", "wrong-basis"), ("identity", "money_currency", "USD"),
    ("identity", "research_source", "wrong-source"), ("identity", "economic_config_sha256", "wrong-economics"),
])
def test_v2_one_field_mismatch_denies(tmp_path, code, target, field, value):
    profile, identity, fingerprint, approval, paths = ticket_metadata(tmp_path, code)
    {"profile": profile, "identity": identity, "approval": approval}[target][field] = value
    write_metadata(identity, fingerprint, approval, paths)
    with pytest.raises(RuntimeError, match="LIVE_OWNER_ORDER_APPROVAL_REQUIRED"):
        code["require_live_order_approval"](*paths, profile=profile)


@pytest.mark.parametrize("field", ["authorization", "start_approved", "orders_approved", "account_mode", "equity_basis", "initial_capital_limit_usdc"])
def test_v2_missing_start_or_money_binding_denied(tmp_path, code, field):
    profile, identity, fingerprint, approval, paths = ticket_metadata(tmp_path, code)
    approval.pop(field)
    write_metadata(identity, fingerprint, approval, paths)
    with pytest.raises(RuntimeError, match="LIVE_OWNER_ORDER_APPROVAL_REQUIRED"):
        code["require_live_order_approval"](*paths, profile=profile)


@pytest.mark.parametrize("initialization", [None, "INITIALIZE_FRESH_C1_EPOCH"])
def test_readonly_ticket_never_grants_orders_and_cannot_authorize_fresh_init(tmp_path, code, initialization):
    profile, identity, fingerprint, approval, paths = ticket_metadata(tmp_path, code, active=False, initialization=initialization)
    approval.update(authorization="PREPARE_ONLY", start_approved=False, orders_approved=True if initialization is None else False)
    write_metadata(identity, fingerprint, approval, paths)
    with pytest.raises(RuntimeError, match="LIVE_OWNER_ORDER_APPROVAL_REQUIRED"):
        code["require_live_order_approval"](*paths, profile=profile)


@pytest.mark.parametrize("cap", ["72", "108", "100", "72.5"])
def test_legacy_v1_exact_canonical_cap_is_not_literal_82(tmp_path, code, cap):
    profile, identity, fingerprint, approval, paths = ticket_metadata(tmp_path, code, cap=cap, legacy=True)
    write_metadata(identity, fingerprint, approval, paths)
    assert code["require_live_order_approval"](*paths)["pilot_capital_usdc"] == cap
    approval["pilot_capital_usdc"] = "109"
    write_metadata(identity, fingerprint, approval, paths)
    with pytest.raises(RuntimeError, match="LIVE_OWNER_ORDER_APPROVAL_REQUIRED"):
        code["require_live_order_approval"](*paths)


def test_actual_initial_policy_is_exclusive_active_and_exact_approval_bound(tmp_path,code):
    base,candidate=profile_metadata(tmp_path,code)
    policy=code['ACTUAL_INITIAL_CAPITAL_POLICY']
    base.pop('initial_capital_usdc');base['initial_capital_policy']=policy
    profile=code['_validate_input_readiness_profile'](tmp_path,base,candidate)
    identity=dict(source_commit='synthetic',strategy_sha256='s',candidate_sha256=profile['candidate_sha256'],
        profile_sha256=profile['profile_sha256'],initial_capital_policy=policy,account_mode=profile['account_mode'],
        equity_basis=profile['equity_basis'],money_currency='USDC',research_source=profile['research_source'],
        economic_config_sha256=profile['economic_config_sha256'])
    approval=dict(schema='coinmaster-live-order-approval-v2',instance_id='hl-stageg-live',release_commit='synthetic',
        strategy_sha256='s',candidate_sha256=identity['candidate_sha256'],profile_sha256=identity['profile_sha256'],
        master_address_sha256='synthetic-fingerprint',initial_capital_policy=policy,account_mode=profile['account_mode'],
        equity_basis=profile['equity_basis'],authorization='START_LIVE_E4_C1',start_approved=True,orders_approved=True)
    fp=tmp_path/'fp.json';fp.write_text(json.dumps(dict(master_address_sha256='synthetic-fingerprint')))
    ticket=tmp_path/'ticket.json';release=tmp_path/'live-release.json';release.write_text(json.dumps(identity))
    ticket.write_text(json.dumps(approval))
    assert code['require_live_order_approval'](ticket,fp,tmp_path,profile=profile)==approval
    for field in ('initial_capital_policy','orders_approved'):
        wrong=approval|{field:'wrong'};ticket.write_text(json.dumps(wrong))
        with pytest.raises(RuntimeError,match='LIVE_OWNER_ORDER_APPROVAL_REQUIRED'):
            code['require_live_order_approval'](ticket,fp,tmp_path,profile=profile)
    with pytest.raises(RuntimeError):code['actual_initial_capital'](base|{'initial_capital_usdc':'82'})
    with pytest.raises(RuntimeError):code['actual_initial_capital'](base|{'profile_id':'E4_C1_INPUT_READINESS_ONLY'})
