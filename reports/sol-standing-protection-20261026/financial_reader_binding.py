"""Pure root-pinned financial interface validation; no engine, imports from product, or writes."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

PACKET = Path(__file__).resolve().parent
OLD = PACKET.parent / 'hedge-risk-contract-20261025' / 'acceptance'
PINS = {
    'approval': '6b8625d810878d0ef0a959687cc14f43b4a3adc85ac79e078c65eafc3e3be6d1',
    'protocol': 'faa392477050d3c33f54b837edd6e0d9dca536eef4e740730d64ca52b7a5d0ea',
    'metric': 'ca815cbe3b8e163b16ccca8e388c9299125f74f0e1dd10beaa3ee15e4fe31102',
    'financial_schema': 'b02b624a4e60e166f033a3daa184b7ea03e10390fb472bc3e1acdf591c5425c2',
}
KINDS = ('OFF', 'C0_FIXED', 'BTC_TRIM', 'A0_FIXED')
COMMON_GATES = ('complete_cash_reconciliation', 'signed_asset_funding_reconciliation',
    'native_3TP', 'ownership', 'continuous_settled_coverage',
    'coherent_prefill_preopen_event_coverage', 'source_config_data_comparable',
    'rights_audit_complete')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def require(condition, reason):
    if not condition:
        raise ValueError(reason)

def pinned(ref):
    require(isinstance(ref, dict) and set(ref) == {'path', 'sha256'}, 'EXACT_PIN_REQUIRED')
    path = Path(ref['path'])
    require(path.is_absolute() and path.is_file(), 'ABSOLUTE_EXISTING_PIN_REQUIRED')
    require(digest(path) == ref['sha256'], 'PIN_HASH_MISMATCH:' + str(path))
    return path.resolve()

def load_json(ref):
    return json.loads(pinned(ref).read_text())

def field(obj, path):
    require(isinstance(path, list) and path and all(isinstance(k, str) and k for k in path), 'EXPLICIT_JSON_KEY_PATH_REQUIRED')
    for key in path:
        require(isinstance(obj, dict) and key in obj, 'BOUND_JSON_FIELD_MISSING:' + key)
        obj = obj[key]
    return obj

def canonical_entry_sha(entry):
    return hashlib.sha256(json.dumps(entry, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()

def validate_roles(roles, completion):
    require(isinstance(roles, dict) and set(roles) == {'report', 'orders', 'funding', 'coherent'}, 'EXACT_FOUR_FROZEN_ROLES_REQUIRED')
    paths = {k: pinned(v) for k, v in roles.items()}
    require(len(set(paths.values())) == 4, 'ROLE_PATH_ALIAS')
    artifacts = completion.get('artifacts')
    require(isinstance(artifacts, list) and len(artifacts) == 4, 'EXACT_FOUR_COMPLETION_ARTIFACTS_REQUIRED')
    require({x.get('role') for x in artifacts} == set(roles), 'ROLE_SET_MISMATCH')
    for x in artifacts:
        role = x['role']
        require(Path(x['path']).resolve() == paths[role] and x['sha256'] == roles[role]['sha256'], 'FROZEN_ROLE_MANIFEST_MISMATCH')
    return paths

def passing_receipt(receipt):
    require(receipt.get('schema') == 'CM_A0_FINANCIAL_QUALIFICATION_V1', 'PRIOR_SCHEMA_MISMATCH')
    require(receipt.get('decision') == 'FINANCIAL_ACCEPTED_CONTROL' and receipt.get('qualification') == 'FINANCIALLY_QUALIFIED', 'PRIOR_NOT_FINANCIALLY_ACCEPTED')
    require(receipt.get('accounting_qualified') is True and type(receipt.get('actual_returncode')) is int and receipt.get('actual_returncode') == 0, 'PRIOR_ACCOUNTING_OR_OS_FAIL')
    require(receipt.get('metric_contract_sha256') == PINS['metric'], 'PRIOR_METRIC_MISMATCH')
    gates = receipt.get('financial_gates', {})
    require(all(gates.get(k) == 'PASS' for k in COMMON_GATES + ('actual_os_exit0', 'terminal_positions0_orders0', 'zero_model_liquidations')), 'PRIOR_GATE_FAIL_OR_UNKNOWN')

def validate_prior(ref, expected_label, expected_source):
    receipt = load_json(ref)
    passing_receipt(receipt)
    require(receipt['label'] == expected_label and receipt['source_commit'] == expected_source, 'PRIOR_LABEL_SOURCE_MISMATCH')
    for name in ('report', 'risk_analysis', 'completion_manifest', 'supervisor'):
        pinned({'path': receipt[name + '_path'], 'sha256': receipt[name + '_sha256']})
    snap = load_json(receipt['ledger_snapshot'])
    current = json.loads(Path(receipt['native_ledger_path']).read_text())
    def selected(ledger):
        matches = [e for e in ledger['attempts'] if e.get('attempt_id') == receipt['attempt_id'] and e.get('status') == 'COMPLETED']
        require(len(matches) == 1, 'PRIOR_UNIQUE_COMPLETED_UUID_REQUIRED')
        e = matches[0]
        require(e['variant'] == expected_label and e['source_commit'] == expected_source, 'PRIOR_ENTRY_LABEL_SOURCE_MISMATCH')
        require(type(e['detail']['actual_returncode']) is int, 'PRIOR_ENTRY_OS_MUST_BE_INTEGER')
        require(e['detail']['report_sha256'] == receipt['report_sha256'] and Path(e['detail']['report']).resolve() == Path(receipt['report_path']).resolve() and e['detail']['actual_returncode'] == 0, 'PRIOR_ENTRY_REPORT_MISMATCH')
        require(canonical_entry_sha(e) == receipt['completed_attempt_sha256'], 'PRIOR_CANONICAL_ENTRY_MUTATED')
    selected(current); selected(snap)
    risk = json.loads(Path(receipt['risk_analysis_path']).read_text())
    require(risk.get('accounting_qualified') is True and risk.get('qualification') == 'VALID_ACCOUNTED_PREFIX', 'PRIOR_RISK_NOT_QUALIFIED')
    pb = risk['physical_binding']
    for key in ('attempt_id', 'label', 'source_commit', 'report_path', 'report_sha256', 'completed_attempt_sha256'):
        require(pb[key] == receipt[key], 'PRIOR_RISK_BINDING_MISMATCH:' + key)
    report = json.loads(Path(receipt['report_path']).read_text())
    physical = report['physical_prefix_attempt']
    require(physical['attempt_id'] == receipt['attempt_id'] and physical['variant'] == expected_label and physical['source_commit'] == expected_source and Path(physical['ledger']).resolve() == Path(receipt['native_ledger_path']).resolve(), 'PRIOR_REPORT_PHYSICAL_IDENTITY_MISMATCH')
    completion = json.loads(Path(receipt['completion_manifest_path']).read_text())
    supervisor = json.loads(Path(receipt['supervisor_path']).read_text())
    for metadata in (completion, supervisor):
        require(metadata['attempt_id'] == receipt['attempt_id'] and metadata['variant'] == expected_label and metadata['source_commit'] == expected_source and type(metadata['actual_returncode']) is int and metadata['actual_returncode'] == 0, 'PRIOR_RECEIPT_METADATA_IDENTITY_MISMATCH')
    require(supervisor['ledger_status'] == 'COMPLETED' and completion['status'] == 'NATIVE_PROCESS_EXPORTED_ACTUAL_OS_ZERO', 'PRIOR_METADATA_NOT_COMPLETED')
    return receipt

PREDECISION_FACTS = (
    'original_second_budget', 'actual_second_filled_ever', 'original_second_remaining',
    'risk_off_plus_60_clock', 'actual_quote_and_cross', 'native_debt', 'native_cap',
    'remaining_TP_and_ordinary_exit', 'pending_ACK_and_reservations', 'native_current_margin',
)

def validate_predecision_coverage(proof, gate):
    """Validate a root-pinned observational proof, not hypothetical A0 admission/profit."""
    declaration = gate['predecision']
    require(proof.get('schema') == 'CM_SOL_STANDING_PREDECISION_COVERAGE_V1', 'PREDECISION_PROOF_SCHEMA_REQUIRED')
    require(proof.get('status') == 'ROOT_ACCEPTED_COMPLETE_OBSERVATIONAL_COVERAGE', 'PREDECISION_COVERAGE_NOT_ACCEPTED')
    for key in ('attempt_id', 'source_commit', 'label', 'phase'):
        require(isinstance(gate.get(key), str) and gate[key] and proof.get(key) == gate[key], 'PREDECISION_IDENTITY_MISMATCH:' + key)
    require(proof.get('report_sha256') == gate['roles']['report']['sha256'], 'PREDECISION_REPORT_SHA_MISMATCH')
    path = declaration['producer_json_path']
    require(isinstance(path, list) and path and all(isinstance(k, str) and k for k in path), 'PREDECISION_EXPLICIT_PRODUCER_PATH_REQUIRED')
    require(proof.get('producer_json_path') == path, 'PREDECISION_PRODUCER_PATH_MISMATCH')
    require(isinstance(declaration.get('record_stage'), str) and declaration['record_stage'] and proof.get('record_stage') == declaration['record_stage'], 'PREDECISION_STAGE_MISMATCH')
    require(proof.get('independent_of_A0_trading_flag') is True, 'PREDECISION_MUST_RUN_WITH_A0_OFF')
    require(proof.get('coverage_complete') is True and proof.get('facts_capture_complete') is True, 'PREDECISION_COVERAGE_UNKNOWN_OR_INCOMPLETE')
    mapping = declaration['field_map']
    require(isinstance(mapping, dict) and set(mapping) == set(PREDECISION_FACTS) and proof.get('frozen_field_map') == mapping, 'PREDECISION_EXACT_FROZEN_FACT_MAP_REQUIRED')
    require(all(isinstance(v, list) and v and all(isinstance(k, str) and k for k in v) for v in mapping.values()), 'PREDECISION_EXPLICIT_FACT_PATHS_REQUIRED')
    require(set(proof.get('captured_fact_names', [])) == set(PREDECISION_FACTS), 'PREDECISION_REQUIRED_FACTS_MISSING')
    universes = proof.get('universes')
    require(isinstance(universes, dict) and set(universes) == {'risk_selections', 'risk_OFF', 'candidate_parents'}, 'PREDECISION_ALL_CAUSAL_UNIVERSES_REQUIRED')
    for name, universe in universes.items():
        require(universe.get('status') == 'COMPLETE', 'PREDECISION_UNIVERSE_UNKNOWN:' + name)
        expected, observed = universe.get('expected_ids'), universe.get('observed_ids')
        require(isinstance(expected, list) and isinstance(observed, list) and all(isinstance(x, str) and x for x in expected + observed), 'PREDECISION_EXACT_EVENT_IDS_REQUIRED:' + name)
        require(len(set(expected)) == len(expected) and len(set(observed)) == len(observed) and set(expected) == set(observed), 'PREDECISION_EVENT_COVERAGE_MISMATCH:' + name)
        require(universe.get('missing_ids') == [] and universe.get('extra_ids') == [], 'PREDECISION_MISSING_OR_EXTRA_CAUSES:' + name)
    clock = proof.get('timestamp_coverage', {})
    require(clock.get('status') == 'COMPLETE' and type(clock.get('missing_or_unbound_records')) is int and clock.get('missing_or_unbound_records') == 0, 'PREDECISION_TIMESTAMP_COVERAGE_UNKNOWN')
    count = clock.get('records')
    require(type(count) is int and count >= 0, 'PREDECISION_RECORD_COUNT_REQUIRED')
    if count:
        first, last = clock.get('first_event_ns'), clock.get('last_event_ns')
        require(type(first) is int and type(last) is int and 0 <= first <= last, 'PREDECISION_ACTUAL_TIMESTAMP_RANGE_REQUIRED')
    else:
        require(clock.get('first_event_ns') is None and clock.get('last_event_ns') is None, 'PREDECISION_EMPTY_CLOCK_NOT_ZERO_FILLED')
    require(proof.get('missing_fact_reason_capture') == 'COMPLETE_EXPLICIT_REASONS', 'PREDECISION_MISSING_REASONS_REQUIRED')
    # Margin invocation/result is an observed fact. False/UNKNOWN with a reason is legitimate,
    # and never proves or disproves own-account A0 dispatch margin/future fills.
    require(proof.get('margin_observation_policy') == 'RECORDED_UNKNOWN_ALLOWED_OWN_A0_GUARDS_AT_DISPATCH', 'PREDECISION_NO_COUNTERFACTUAL_MARGIN_REQUIRED')
    opportunities = proof.get('structurally_admissible_original_rights')
    require(type(opportunities) is int and opportunities >= 0, 'PREDECISION_STRUCTURAL_OPPORTUNITY_COUNT_REQUIRED')
    meaningful = len(universes['risk_selections']['expected_ids'])
    require(count >= meaningful, 'PREDECISION_RISK_SELECTIONS_WITHOUT_RECORDS')
    expected_status = 'NOT_TESTED' if meaningful == 0 else ('NO_STRUCTURAL_OPPORTUNITY' if opportunities == 0 else 'OBSERVATIONAL_COVERAGE_ONLY')
    require(proof.get('measurement_status') == expected_status, 'PREDECISION_MEASUREMENT_STATUS_MISMATCH')
    require(meaningful > 0 or opportunities == 0, 'PREDECISION_OPPORTUNITY_WITHOUT_RISK_SELECTION')
    return {'coverage_complete': True, 'measurement_status': expected_status,
        'risk_selections': meaningful, 'structurally_admissible_original_rights': opportunities,
        'future_A0_margin_fill_profit': 'NOT_PREPROVEN_OWN_ACCOUNT_RUNTIME_GUARDS_REQUIRED'}

def load_root_gate(path, expected_sha):
    require(__debug__, 'OPTIMIZED_PYTHON_FORBIDDEN')
    gate_path = pinned({'path': str(Path(path).resolve()), 'sha256': expected_sha})
    require(gate_path.parent == PACKET and gate_path.name.startswith('interface') and gate_path.suffix == '.json', 'ROOT_GATE_MUST_BE_PACKET_INTERFACE_JSON')
    gate = json.loads(gate_path.read_text())
    require(gate.get('schema') == 'CM_SOL_STANDING_FINANCIAL_ROOT_GATE_V1' and gate.get('decision') == 'ROOT_APPROVED_FINANCIAL_READ', 'ROOT_FINANCIAL_READ_GATE_REQUIRED')
    require(gate.get('approved_by') == '/root' and gate.get('completed_result_only') is True, 'ROOT_COMPLETE_RESULT_GATE_REQUIRED')
    for key, sha in PINS.items():
        pinned(gate[key]); require(gate[key]['sha256'] == sha, 'FROZEN_AUTHORITY_PIN_MISMATCH:' + key)
    require(pinned(gate['metric']) == (OLD / 'metric-contract.json').resolve() and pinned(gate['financial_schema']) == (OLD / 'financial-qualification-receipt-schema.json').resolve(), 'AUTHORITATIVE_METRIC_SCHEMA_PATH_REQUIRED')
    kind = gate['variant_kind']; require(kind in KINDS, 'EXACT_VARIANT_KIND_REQUIRED')
    label = gate['label']; require(isinstance(label, str) and label and '/' not in label, 'EXPLICIT_LABEL_REQUIRED')
    source = gate['source_commit']; require(isinstance(source, str) and len(source) == 40 and all(c in '0123456789abcdef' for c in source), 'EXPLICIT_SOURCE_REQUIRED')
    freeze = load_json(gate['freeze'])
    for key in ('source_commit', 'label'):
        require(field(freeze, gate['freeze_fields'][key]) == gate[key], 'FROZEN_INTERFACE_MISMATCH:' + key)
    # Actual kwargs/config/data/engine/clock identities are root reviewed, immutable pins, not CLI options.
    required_identity = ('config', 'kwargs', 'data', 'engine', 'clock', 'source_review', 'engineering_acceptance')
    require(set(gate['identity_pins']) == set(required_identity), 'COMPLETE_IDENTITY_PINS_REQUIRED')
    for ref in gate['identity_pins'].values(): pinned(ref)
    require(set(gate['reader_pins']) == {'financial_reader.py', 'financial_reader_binding.py', 'financial_reader_rights.py'}, 'EXACT_READER_SOURCE_PINS_REQUIRED')
    for name, ref in gate['reader_pins'].items():
        require(pinned(ref) == (PACKET / name).resolve(), 'ROOT_APPROVED_READER_PATH_REQUIRED')
    completion = load_json(gate['completion']); supervisor = load_json(gate['supervisor'])
    paths = validate_roles(gate['roles'], completion)
    ledger_path = pinned(gate['ledger_snapshot'])
    snapshot = json.loads(ledger_path.read_text())
    actual_ledger = Path(gate['current_ledger_path']).resolve()
    current = json.loads(actual_ledger.read_text())
    uuid = gate['attempt_id']
    entries = []
    for ledger in (snapshot, current):
        selected = [e for e in ledger['attempts'] if e.get('attempt_id') == uuid and e.get('status') == 'COMPLETED']
        require(len(selected) == 1, 'UNIQUE_COMPLETED_CURRENT_AND_SNAPSHOT_REQUIRED')
        entry = selected[0]
        require(canonical_entry_sha(entry) == gate['completed_attempt_sha256'], 'CANONICAL_COMPLETED_ENTRY_MUTATED')
        entries.append(entry)
    e = entries[0]
    require(e['variant'] == label and e['source_commit'] == source and type(e['detail']['actual_returncode']) is int and e['detail']['actual_returncode'] == 0, 'CURRENT_ENTRY_IDENTITY_OR_OS_FAIL')
    require(e['detail']['report_sha256'] == gate['roles']['report']['sha256'] and Path(e['detail']['report']).resolve() == paths['report'], 'CURRENT_ENTRY_REPORT_MISMATCH')
    require(e['freeze_sha256'] == gate['freeze']['sha256'], 'ENTRY_FROZEN_GATE_MISMATCH')
    for r in (completion, supervisor):
        require(r['attempt_id'] == uuid and r['variant'] == label and r['source_commit'] == source and type(r['actual_returncode']) is int and r['actual_returncode'] == 0 and r['freeze_sha256'] == gate['freeze']['sha256'], 'RECEIPT_UUID_SOURCE_RC_FREEZE_MISMATCH')
    require(supervisor['ledger_status'] == 'COMPLETED' and completion['status'] == 'NATIVE_PROCESS_EXPORTED_ACTUAL_OS_ZERO', 'COMPLETION_OR_OS_NOT_ACCEPTED')
    expected_prior_kinds = KINDS[:KINDS.index(kind)]
    prior = gate['previous_financial_qualifications']
    require(isinstance(prior, list) and len(prior) == len(expected_prior_kinds) and [r['variant_kind'] for r in prior] == list(expected_prior_kinds), 'EXACT_ORDERED_PRIOR_RECEIPT_SET_REQUIRED')
    require(len({r['label'] for r in prior}) == len(prior) and label not in {r['label'] for r in prior}, 'DUPLICATE_PRIOR_LABEL')
    for r in prior: validate_prior(r['receipt'], r['label'], source)
    ev = load_json(gate['evidence'])
    require(ev['label'] == label and ev['report_sha256'] == gate['roles']['report']['sha256'], 'EVIDENCE_RESULT_MISMATCH')
    if kind in ('C0_FIXED', 'A0_FIXED'):
        declaration = gate.get('predecision')
        require(isinstance(declaration, dict), 'ROOT_PINNED_PREDECISION_SCOPE_GATE_REQUIRED')
        proof = load_json(declaration['proof'])
        require(declaration['proof'] in ev.get('proof_artifacts', []), 'PREDECISION_MUST_BE_PINNED_EVIDENCE_ARTIFACT')
        require(ev.get('predecision_coverage') == 'PASS' and ev.get('predecision_proof') == declaration['proof'], 'ROOT_EVIDENCE_PREDECISION_PROOF_PIN_REQUIRED')
        gate['predecision_qualification'] = validate_predecision_coverage(proof, gate)
    if kind == 'BTC_TRIM':
        trim = gate['trim_provenance']
        require(trim.get('status') == 'ROOT_ACCEPTED_EX_ANTE_CAUSAL_COMPARATOR' and trim.get('future_C0_SOL_fills_online') is False, 'TRIM_CAUSAL_PROVENANCE_REQUIRED')
        for name in ('frozen_formula', 'source_review', 'actual_clock_quantity_proof'): pinned(trim[name])
        require(ev.get('trim_causal_provenance') == 'PASS', 'TRIM_EVIDENCE_CAUSAL_PROVENANCE_REQUIRED')
    output = Path(gate['output_path']).resolve()
    require(output.parent == PACKET and output.name.startswith('financial_reader') and output.suffix == '.json' and not output.exists(), 'FRESH_PACKET_FINANCIAL_OUTPUT_REQUIRED')
    all_inputs = set(paths.values()) | {gate_path, pinned(gate['evidence']), pinned(gate['completion']), pinned(gate['supervisor']), actual_ledger, ledger_path}
    require(output not in all_inputs, 'INPUT_IS_IMMUTABLE')
    # Protect inherited assert checks too. No root-gate bool substitutes for actual producer data.
    args = SimpleNamespace(report=paths['report'], orders=paths['orders'], funding=paths['funding'], coherent=paths['coherent'], ledger=actual_ledger, completion=pinned(gate['completion']), supervisor=pinned(gate['supervisor']), evidence=pinned(gate['evidence']), output=output, label=label)
    return gate, args, gate_path
