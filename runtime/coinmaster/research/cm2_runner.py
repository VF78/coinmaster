"""CM2 BTC-reference construction and existing bounded native admission path."""
from __future__ import annotations
import argparse
from dataclasses import dataclass,asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from coinmaster.domain.wave_overlay import Candidate
from coinmaster.strategy.cm2_reference_policy import ReferenceConfig,ReferenceFlags,selected_btc_candidate,DAY
from coinmaster.strategy.cm2_execution import ExecutionLimits
from coinmaster.strategy.cm2_order_contract import MODEL_ID


def reference_config(value):
    if type(value) is not dict or set(value)!={'version','candidate','flags','emergency_drawdown_fraction'}:
        raise ValueError('CM2_REFERENCE_POLICY_FIELDS_REQUIRED')
    expected=asdict(selected_btc_candidate());candidate=value['candidate']
    if type(candidate) is not dict or set(candidate)!=set(expected):raise ValueError('CM2_REFERENCE_CANDIDATE_FIELDS')
    normalized=dict(candidate)
    for key in ('wave_quantiles','btc_tp_fractions_initial_qty','sol_size_multipliers_h','sol_entry_z'):
        if type(normalized[key]) not in (list,tuple):raise ValueError('CM2_REFERENCE_TUPLE_FIELD')
        normalized[key]=tuple(normalized[key])
    flags=value['flags']
    if type(flags) is not dict or set(flags)!={'c1_first_fresh_h4','c1_btc_postcut_d1'}:raise ValueError('CM2_REQUIRED_PROVEN_FLAGS')
    fraction=value['emergency_drawdown_fraction']
    if fraction is not None:raise ValueError('MATCHED_RESEARCH_EMERGENCY_EXPLICITLY_DISABLED')
    return ReferenceConfig(value['version'],Candidate(**normalized),ReferenceFlags(**flags),None)


@dataclass(frozen=True)
class CM2RunConfig:
    policy: ReferenceConfig
    absolute_child_limit: Decimal = Decimal('1e100')

    def __post_init__(self):
        if not isinstance(self.policy,ReferenceConfig):raise ValueError('OLD_CM2_POLICY_VERSION_REJECTED')
        if not self.absolute_child_limit.is_finite() or self.absolute_child_limit<=0:raise ValueError('CM2_CHILD_LIMIT_INVALID')


def request_interval(request):
    start,end=request.get('start_ns'),request.get('end_ns')
    minute=60_000_000_000
    if type(start) is not int or type(end) is not int or not 0<start<end or start%minute or end%minute:
        raise ValueError('EXPLICIT_CAUSAL_REQUEST_INTERVAL_REQUIRED')
    if request.get('request_execution_model_id')!=MODEL_ID:raise ValueError('CM2_REQUEST_EXECUTION_VERSION_MISMATCH')
    return start,end


def build_strategy(run_config, *, instruments,minute_bars,margin_policy,start_ns,end_ns,
                   mark_types,mark_client,journal,exit_fee_rate,execution_hash,
                   seed_days,seed_ohlc,daily_types,h4_type,signal_client,initial_seed,
                   risk_recorder=None,coherent_observer=None):
    from coinmaster.strategy.cm2_native import CM2Strategy,CM2StrategyConfig
    if journal is None:raise ValueError('CM2_NATIVE_FUNDING_JOURNAL_REQUIRED')
    cls=CM2Strategy
    if risk_recorder is not None:
        from coinmaster.research.minute_risk import observed_neutral_strategy_type
        cls=observed_neutral_strategy_type(cls,risk_recorder)
    from coinmaster.research.cm2_funding_reader import NativeSignedFundingReader
    from coinmaster.strategy.cm2_checkpoint import NativeCheckpointStore,observer_continuity
    return cls(CM2StrategyConfig(btc_id=instruments[0].id,sol_id=instruments[1].id,
        btc_bar_type=minute_bars[instruments[0].id],sol_bar_type=minute_bars[instruments[1].id],
        btc_mark_data_type=mark_types[0],sol_mark_data_type=mark_types[1],mark_client_id=mark_client,
        btc_signal_data_type=daily_types[0],sol_signal_data_type=daily_types[1],
        h4_data_type=h4_type,signal_client_id=signal_client,
        policy=run_config.policy,limits=ExecutionLimits(run_config.absolute_child_limit),
        margin_policy=margin_policy,active_seed=initial_seed,btc_step=instruments[0].size_increment.as_decimal(),
        trading_start_open_ns=start_ns,terminal_close_at_ns=end_ns,seed_days=tuple(seed_days),seed_ohlc=tuple(seed_ohlc),
        exit_fee_rate=exit_fee_rate,execution_policy_hash=execution_hash,
        funding_reader=NativeSignedFundingReader(journal),checkpoint_store=NativeCheckpointStore(journal),
        continuity_reader=lambda:observer_continuity(risk_recorder,coherent_observer)))


def auxiliary_audits(strategy):
    if hasattr(strategy,'cm2_audit'):return {'native_cm2_audit':strategy.cm2_audit}
    return dict(native_risk_first_audit=strategy.risk_first_sol_audit,
        native_carry_audit=strategy.carry_pair_audit,native_carry_counts=strategy.carry_pair_counts,
        native_alpha_audit=strategy.alpha_cushion_audit,native_alpha_counts=strategy.alpha_cushion_counts)


def complete_report(result,strategy,engine,journal,seed,coherent):
    from coinmaster.research.native_accounting import native_position_lifecycles
    postings=journal.funding_cash_audit() if journal else []
    signed=sum((Decimal(row[5]) for row in postings),Decimal(0))
    result["funding_cash_audit"]=postings
    result["funding"]["signed_amount"]=str(signed)
    lifecycle=native_position_lifecycles(engine.cache)
    complete=not lifecycle["unknown"] and all(p["closed"] and p["realized_pnl"] is not None for p in lifecycle["positions"]) and not engine.cache.positions_open()
    realized=sum((Decimal(p["realized_pnl"]) for p in lifecycle["positions"]),Decimal(0)) if complete else None
    bridge=Decimal(result["terminal_active"])-seed-realized-signed if complete else None
    result["native_cash_reconciliation"]={
        "status":"EXACT" if bridge==0 else "UNKNOWN_UNALLOCATED_NATIVE_BRIDGE",
        "native_position_lifecycle_export":lifecycle,
        "native_realized_total":str(realized) if complete else None,
        "signed_funding":str(signed),"unallocated_bridge":str(bridge) if complete else None,
        "fees_policy":"NATIVE_POSITION_REALIZED_ALREADY_INCLUDES_COMMISSIONS",
        "actual_native_cash_transitions":(coherent or {}).get("native_cash_transitions")}
    result["cm2"]=strategy.reporting_state()["cm2"]
    result["config"]["strategy_id"]="cm2_btc_reference_v1"
    result["config"]["candidate"]=asdict(strategy.config.policy.candidate)
    result["config"]["cm2"]=result["cm2"]["policy"]
    result["config"]["cm2_request_contract"]=result["cm2"]["request_contract"]
    result["request_execution_model_id"]=result["cm2"]["request_execution_model_id"]
    result["request_contract_sha256"]=result["cm2"]["request_contract_sha256"]
    result['cm2']['structural_diagnostics']='NATIVE_QUALIFICATION_PENDING'
    result["source_hashes"]={str(path.relative_to(Path(__file__).parents[1])):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (Path(__file__),Path(__file__).parents[1]/"strategy/cm2_reference_policy.py",
                     Path(__file__).parents[1]/"domain/wave_overlay.py",Path(__file__).parents[1]/"strategy/cm2_policy.py",
                     Path(__file__).parents[1]/"strategy/cm2_execution.py",Path(__file__).parents[1]/"strategy/cm2_native.py",
                     Path(__file__).parents[1]/"strategy/cm2_order_contract.py",Path(__file__).parents[1]/"strategy/cm2_checkpoint.py",Path(__file__).with_name("cm2_funding_reader.py"),Path(__file__).with_name("cm2_committed_validation.py"))}
    # The config hash includes the new economic policy, unlike the legacy wrapper.
    result["config_hash"]=hashlib.sha256(json.dumps(result["config"],sort_keys=True,separators=(",",":")).encode()).hexdigest()

def acquire_shared_lease(path):
    import fcntl
    stream=Path(path).open("a+")
    try:
        fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BaseException:
        stream.close()
        raise
    # Never LOCK_UN: a child may share this open-file-description.
    return stream

def preflight(request,receipt):
    required=('source_config_data_binary_freeze','independent_money_causality_review',
        'own_stage_root_GO','fresh_resource_check','secretless_environment')
    if receipt.get('status')!='R2_RELEASED' or not all(receipt.get(k) is True for k in required):
        raise ValueError('CM2_NATIVE_HOLD_RESOURCE_OR_SCOPED_GATE')
    if receipt.get('stage')!=request['stage']:raise ValueError('CM2_STAGE_RECEIPT_MISMATCH')
    start,end=request_interval(request);family=source_family(request)
    if family=='CM2BTCREF':cfg=CM2RunConfig(reference_config(request['policy']))
    else:
        expected={'version':'reference-btc-only-public5b-v1',
            'source_commit':'5b56f7d02e09d4495ac018ec1ce701f6f0dfb737',
            'prepared_kwargs_sha256':request['prepared_control_kwargs_sha256']}
        if type(request['policy']) is not dict or request['policy']!=expected:
            raise ValueError('CONTROL_EXACT_EXTERNAL_POLICY_DESCRIPTOR_REQUIRED')
        cfg=None
    import re
    if type(request.get('run_id')) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}',request['run_id']) is None:
        raise ValueError('CM2_LITERAL_RUN_ID_REQUIRED')
    family=source_family(request)
    policy_sha=hashlib.sha256(json.dumps(request['policy'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    request_sha=hashlib.sha256(json.dumps(request,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    bindings=receipt.get('case_bindings')
    if bindings is not None:
        if (type(bindings) is not dict or request['run_id'] not in bindings
                or any(key in receipt for key in ('run_id','source_family','policy_sha256','request_content_sha256'))):
            raise ValueError('CM2_EXACT_CASE_RECEIPT_MAP_REQUIRED')
        binding=bindings[request['run_id']]
        if type(binding) is not dict or set(binding)!={'source_family','policy_sha256','request_content_sha256'}:
            raise ValueError('CM2_EXACT_CASE_RECEIPT_FIELDS_REQUIRED')
    else:
        if receipt.get('run_id')!=request['run_id']:raise ValueError('CM2_EXACT_REQUEST_GO_BINDING_REQUIRED')
        binding=receipt
    if (binding.get('source_family')!=family or binding.get('policy_sha256')!=policy_sha
            or binding.get('request_content_sha256')!=request_sha):
        raise ValueError('CM2_EXACT_REQUEST_GO_BINDING_REQUIRED')
    if family=='REFERENCE_BTC_ONLY':
        if request['stage']=='engineering':raise ValueError('REFERENCE_CONTROL_NOT_ENGINEERING_FIXTURE')
        from coinmaster.research.cm2_reference_control_worker import validate_binding
        validate_binding(request)
    if not request.get('freeze_files'):raise ValueError('CM2_SOURCE_CONFIG_DATA_BINARY_FREEZE_REQUIRED')
    for item in request['freeze_files']:
        if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('CM2_FREEZE_MISMATCH:'+str(item['path']))
    source_root=Path(__file__).parents[1]
    required_sources={source_root/name for name in ('strategy/cm2_reference_policy.py','domain/wave_overlay.py',
        'strategy/cm2_policy.py','strategy/cm2_native.py','strategy/cm2_execution.py','strategy/cm2_order_contract.py',
        'strategy/cm2_checkpoint.py','research/cm2_runner.py','research/cm2_committed_validation.py',
        'research/native_baseline.py','research/cm2_batch.py','research/cm2_funding_reader.py','research/minute_risk.py','research/paired_observer.py')}
    if not {p.resolve() for p in required_sources}.issubset({Path(x['path']).resolve() for x in request['freeze_files']}):
        raise ValueError('CM2_REFERENCE_EXECUTED_SOURCE_FREEZE_REQUIRED')
    if family=='REFERENCE_BTC_ONLY':
        required_control={Path(request[k]).resolve() for k in ('execution_source_manifest','prepared_control_kwargs')}
        required_control.add(Path(__file__).with_name('cm2_reference_control_worker.py').resolve())
        if not required_control.issubset({Path(x['path']).resolve() for x in request['freeze_files']}):
            raise ValueError('CONTROL_BOOTSTRAP_AND_PREPARATION_FREEZE_REQUIRED')
    if request['stage']=='engineering':
        fixture=engineering_fixture_module(request)
        if (start,end)!=fixture.fixture_interval(request['fixture_id']):raise ValueError('CM2_EXPLICIT_ENGINEERING_INTERVAL_REQUIRED')
    if request.get('initial_active_seed')!='10000':raise ValueError('CM2_FROZEN_BENCHMARK_SEED_REQUIRED')
    return cfg


def engineering_fixture_module(request):
    if request.get('fixture_id') not in ('cm2-btc-reference-cycle-native-v1','cm2-btc-reference-terminal-native-v1'):
        raise ValueError('OLD_BREAKOUT_FIXTURE_NOT_QUALIFICATION_FOR_BTC_REFERENCE')
    from coinmaster.research import cm2_reference_fixture
    return cm2_reference_fixture



def fixture_api_boundary_probe(request,probe):
    """Exercise the ACTUAL fixture up to its imported native constructor."""
    import nautilus_trader.backtest.engine as native_engine
    fixture=engineering_fixture_module(request)
    probe=Path(probe);probe.mkdir(parents=True,exist_ok=True)
    original=native_engine.BacktestEngine
    calls=[]
    class BoundaryReached(BaseException): pass
    def boundary(*args,**kwargs):
        calls.append(1)
        raise BoundaryReached()
    class BoundaryProxy:
        add_venue=original.add_venue
        def __new__(cls,*args,**kwargs):return boundary(*args,**kwargs)
    native_engine.BacktestEngine=BoundaryProxy
    try:
        try: fixture.run_fixture({**request,"artifact_dir":str(probe)})
        except BoundaryReached: pass
        else: raise ValueError("CM2_FIXTURE_NATIVE_BOUNDARY_NOT_REACHED")
    finally:
        native_engine.BacktestEngine=original
    if len(calls)!=1: raise ValueError("CM2_FIXTURE_NATIVE_BOUNDARY_COUNT")
    receipt={"status":"ACTUAL_API_ENGINE_BOUNDARY_PASS","kind":"ENGINEERING_FIXTURE",
        "boundary_calls":len(calls),"native_engine_constructions":0,
        "fixture_id":request["fixture_id"],"start_ns":request["start_ns"],"end_ns":request["end_ns"],
        "only_kwarg_substitution":"artifact_dir","fixture_source_sha256":hashlib.sha256(Path(fixture.__file__).read_bytes()).hexdigest()}
    (probe/"api-boundary-proof.json").write_text(json.dumps(receipt,indent=2)+"\n")
    return receipt


def append_ledger(path,row):
    import fcntl,os
    with Path(path).open("a+") as stream:
        fcntl.flock(stream.fileno(),fcntl.LOCK_EX)
        stream.write(json.dumps(row,sort_keys=True)+"\n")
        stream.flush()
        os.fsync(stream.fileno())

def register_attempt(request,receipt):
    import fcntl,os
    budget=json.loads(Path(request["budget_path"]).read_text())
    ledger=Path(request["attempt_ledger"])
    ledger.parent.mkdir(parents=True,exist_ok=True)
    with ledger.open("a+") as stream:
        fcntl.flock(stream.fileno(),fcntl.LOCK_EX)
        stream.seek(0)
        rows=[json.loads(line) for line in stream if line.strip()]
        starts=[row for row in rows if row.get("status")=="STARTED"]
        if any(row["run_id"]==request["run_id"] for row in starts):
            raise ValueError("CM2_ATTEMPT_EXISTS_NO_REPLAY")
        stage=request["stage"]
        count=sum(row["stage"]==stage for row in starts)
        spec=budget["stages"][stage]
        if len(starts)>=budget["total_physical_cap"] or count>=spec["cap"]:
            raise ValueError("CM2_BUDGET_EXHAUSTED")
        if stage=="broad" and count>=spec["initial_block"] and receipt.get("second_broad_block_GO") is not True:
            raise ValueError("CM2_CONDITIONAL_BROAD_HOLD")
        if stage=="local" and receipt.get("explained_region_GO") is not True:
            raise ValueError("CM2_CONDITIONAL_LOCAL_HOLD")
        if stage=="qualification" and receipt.get("actual_finalist_GO") is not True:
            raise ValueError("CM2_QUALIFICATION_HOLD")
        entry={"run_id":request["run_id"],"stage":stage,"status":"STARTED",
               "scope_version":budget["scope_version"]}
        stream.seek(0,2)
        stream.write(json.dumps(entry,sort_keys=True)+"\n")
        stream.flush()
        os.fsync(stream.fileno())
    return entry

def validate_full_output(result,request):
    # Postprocessing only: project actual committed-native watermarks; preserve
    # sparse legacy recorder, original raw file, money and source/model IDs.
    from coinmaster.research.cm2_committed_validation import qualify,sha,provenance_files
    output=Path(request["artifact_dir"])
    raw=output/(request["run_id"]+"-raw-native.json")
    count=json.loads((output/"engine-construction-count.json").read_text())["engine_constructions"]
    proof=qualify(raw,output/"minute-native-settled-receipts.csv.gz",
        output/"coherent-native-events.jsonl.gz",output/"committed-wm-qualification-v1",
        (Path(request['execution_source_root'])/'runtime/coinmaster/research/minute_risk.py'
            if source_family(request)=='REFERENCE_BTC_ONLY' else Path(__file__).with_name('minute_risk.py')),
        Path(request["qualified_coverage_source"]),count,
        expected_report_sha=sha(raw),expected_start_ns=request["start_ns"],expected_end_ns=request["end_ns"],provenance=provenance_files(
            request=request.get("_request_path"),ledger=request.get("attempt_ledger"),
            engine_count_path=output/"engine-construction-count.json"))
    result["actual_feed_coverage"]=proof["coverage"]
    if source_family(request)=='CM2BTCREF':
        result["cm2"]["financial_checks"]=proof["checks"]
        result["cm2"]["accounting_status"]="PASS"
    result["derived_financial_status"]="PASS"
    result["committed_wm_qualification"]={k:proof[k] for k in
        ("qualification_model_id","original_report_sha256","parent_raw_model_ids","comparability","derived_report_sha256")}
    result["committed_wm_qualification_receipt"]=str(output/"committed-wm-qualification-v1/QUALIFICATION.json")


def postchild_validation(request):
    """Parent-only source-family binding; original raw bytes stay immutable."""
    if request['stage']=='engineering':return validate_engineering_output(request)
    output=Path(request['artifact_dir']);family=source_family(request)
    raw=output/(request['run_id']+'-raw-native.json')
    result=json.loads(raw.read_text());before=hashlib.sha256(raw.read_bytes()).hexdigest()
    if family=='REFERENCE_BTC_ONLY':
        terminal=json.loads((output/'control-native-terminal.json').read_text())
        root=Path(request['execution_source_root']).resolve()
        if (terminal['source_family']!=family or terminal['execution_source_commit']!=request['execution_source_commit']
                or terminal['raw_report_sha256']!=before or terminal['native_engine_constructions']!=1
                or terminal['prepared_kwargs_sha256']!=request['prepared_control_kwargs_sha256']
                or terminal['execution_source_root']!=str(root)
                or terminal['orchestrator_source_root']!=request['orchestrator_source_root']
                or terminal['orchestrator_source_commit']!=request['orchestrator_source_commit']
                or terminal['bootstrap_sha256']!=hashlib.sha256(Path(__file__).with_name('cm2_reference_control_worker.py').read_bytes()).hexdigest()
                or not terminal['source_origins'] or not all(Path(v).resolve().is_relative_to(root/'runtime') for v in terminal['source_origins'].values())):
            raise ValueError('CONTROL_CHILD_SOURCE_OR_RAW_BINDING_MISMATCH')
        if 'cm2' in result:raise ValueError('CONTROL_RAW_MUST_NOT_INVENT_CM2_POLICY')
        from coinmaster.research.cm2_reference_control_worker import same_typed
        prepared=json.loads(Path(request['prepared_control_kwargs']).read_text())
        if not same_typed(result['config']['candidate'],prepared['candidate']):raise ValueError('CONTROL_RAW_CANDIDATE_BINDING_MISMATCH')
    else:
        policy=asdict(reference_config(request['policy']))
        # JSON changes tuple lists only, so compare canonical JSON values.
        if json.loads(json.dumps(policy))!=result['cm2']['policy'] or result['request_execution_model_id']!=MODEL_ID:
            raise ValueError('CM2_RAW_POLICY_REQUEST_VERSION_MISMATCH')
        source_root=Path(__file__).parents[1]
        required={'research/cm2_runner.py','strategy/cm2_reference_policy.py','domain/wave_overlay.py',
            'strategy/cm2_policy.py','strategy/cm2_execution.py','strategy/cm2_native.py','strategy/cm2_order_contract.py',
            'strategy/cm2_checkpoint.py','research/cm2_funding_reader.py','research/cm2_committed_validation.py'}
        if set(result['source_hashes'])!=required or any(hashlib.sha256((source_root/name).read_bytes()).hexdigest()!=digest
                for name,digest in result['source_hashes'].items()):raise ValueError('CM2_EXECUTED_SOURCE_HASH_BINDING_MISMATCH')
        if result['cm2']['capacity_model']['participation'] is not None:
            raise ValueError('CM2_MATCHED_ZERO_IMPACT_PROFILE_REQUIRED')
    validate_full_output(result,request)
    if hashlib.sha256(raw.read_bytes()).hexdigest()!=before:raise ValueError('RAW_NATIVE_REPORT_MUTATED')
    (output/(request['run_id']+'-qualified-summary.json')).write_text(json.dumps(result,sort_keys=True)+'\n')
    return result


def engineering_artifact_integrity(output,result,end_ns):
    """Read existing engineering exports through gzip EOF; no money rebuild."""
    import csv,gzip
    output=Path(output);artifacts={}
    def fail(condition,reason):
        if not condition:raise ValueError('CM2_ENGINEERING_ARTIFACT_'+reason)
    path=output/'coherent-native-events.jsonl.gz';rows=0;last=None
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line);rows+=1
            fail(type(row) is dict and {'sequence','kind','event_ns'}.issubset(row),'JSONL_SCHEMA')
            fail(type(row['sequence']) is int and row['sequence']==rows,'JSONL_SEQUENCE')
            fail(type(row['kind']) is str and int(row['event_ns'])<=end_ns,'JSONL_EVENT')
            last=row
    expected=result['coherent_native_observer']['sequence_count']
    fail(type(expected) is int and rows==expected and rows>0,'JSONL_COUNT')
    fail(last['kind']=='DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED' and int(last['event_ns'])==end_ns,'JSONL_TERMINAL')
    artifacts[path.name]={'rows':rows,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    risk=result['minute_risk_observations']
    schemas=(('minute-native-risk.csv.gz',
        ['bar_open_ms','close_available_ns','phase','cash','free_cash','native_initial_margin','native_maintenance_margin',
         'paired_close_equity','conditional_adverse_equity','conditional_favorable_equity','conditional_high_mark_mm_upper',
         'conditional_margin_breach','native_positions_and_mark_ohlc_json'],risk['rows']),
        ('minute-native-settled-receipts.csv.gz',
         ['source_quote_ns','receipt_ns','fill_epoch','cash','paired_close_equity','native_positions_and_mark_ohlc_json'],
         risk['settled_native_close_receipts']['receipts']))
    for name,header,expected in schemas:
        path=output/name;rows=0
        with gzip.open(path,'rt',encoding='utf-8',newline='') as stream:
            reader=csv.reader(stream,strict=True)
            fail(next(reader,None)==header,'CSV_SCHEMA:'+name)
            for row in reader:
                fail(len(row)==len(header),'CSV_ROW_SHAPE:'+name)
                json.loads(row[-1]);rows+=1
        fail(type(expected) is int and expected>=0 and rows==expected,'CSV_COUNT:'+name)
        artifacts[name]={'rows':rows,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    return artifacts


def validate_engineering_output(request):
    """Existing engineering leaf's persisted actual gates, not FULL finance."""
    fixture=engineering_fixture_module(request);output=Path(request['artifact_dir'])
    raw=output/'fixture-result.json';before=hashlib.sha256(raw.read_bytes()).hexdigest()
    result=json.loads(raw.read_text());protocol=fixture.fixture_protocol(request['fixture_id'])
    count=json.loads((output/'engine-construction-count.json').read_text())['engine_constructions']
    artifacts=engineering_artifact_integrity(output,result,fixture.fixture_interval(request['fixture_id'])[1])
    checks=result['checks'];events=result['native_strategy_events'];life=result['native_position_lifecycles']
    required=set(protocol['mandatory'])
    predicates={
        'actual_one_engine':type(count) is int and count==1 and result['native_engine_constructions']==1,
        'fixture_identity':result['fixture_id']==request['fixture_id'] and result['fixture_protocol']==protocol,
        'mandatory_component_evidence':set(checks)==required and all(checks[k] is True for k in required)
            and result['status']=='CASE_COMPONENT_GATES_PASS',
        'terminal_native_flat':events['terminal_lifecycle']['status']=='FLAT' and events['terminal_open_orders']==0,
        'native_lifecycles_complete':not life['unknown'] and all(p['closed'] and p['realized_pnl'] is not None for p in life['positions']),
        'exact_native_cash_bridge':Decimal(result['terminal_cash'])-Decimal(10000)-Decimal(result['native_realized'])-Decimal(result['signed_funding'])==0,
        'native_fee_currency':all(f['commission_currency']=='USDC' for f in events['fill_audit']),
        'no_liquidations':not events['liquidations']}
    for key,value in predicates.items():
        if value is not True:raise ValueError('CM2_ENGINEERING_EVIDENCE_FAILED:'+key)
    if hashlib.sha256(raw.read_bytes()).hexdigest()!=before:raise ValueError('RAW_ENGINEERING_REPORT_MUTATED')
    proof={'status':'ENGINEERING_COMPONENT_EVIDENCE_VALIDATED_NOT_FULL_FINANCIAL_QUALIFICATION',
        'fixture_id':request['fixture_id'],'raw_sha256':before,'predicates':predicates,
        'actual_engine_constructions':count,'unobserved':protocol['not_claimed'],'artifact_integrity':artifacts}
    with (output/'engineering-postchild-proof.json').open('x') as stream:
        stream.write(json.dumps(proof,sort_keys=True)+'\n')
    return proof


def full_native_kwargs(request, *, artifact_dir=None):
    start,end=request_interval(request);cfg=CM2RunConfig(reference_config(request['policy']))
    return dict(data_root=Path(request['data_root']),
        artifact_dir=Path(request['artifact_dir']) if artifact_dir is None else Path(artifact_dir),
        artifact_label=request['run_id'],include_funding=True,
        current_hl_execution_inputs=Path(request['current_hl_execution_inputs']),
        qualification_mode='execution_diagnostic',qualification_quantity_model='hl_current_usdc',
        qualification_instrument_metadata=None,qualification_deposit_runtime=None,
        qualification_deposit_equity_reader=None,qualification_deposit_account_id='',
        trading_start_ms=start//1_000_000,trading_end_ms=end//1_000_000,
        warmup_start_ms=start//1_000_000-730*86_400_000,
        initial_active_seed=Decimal(request['initial_active_seed']),observe_minute_risk=True,
        candidate=cfg.policy.candidate,research_cm2=cfg,weekly_batch_minutes=1440,cursor_batch_rows=1440)


def full_api_boundary_probe(request,probe_dir):
    """Run exact public-data pipeline; intercept BEFORE actual engine creation."""
    import inspect,time
    import nautilus_trader.backtest.engine as native_engine
    from coinmaster.research import native_baseline as nb
    probe=Path(probe_dir).resolve()
    case=Path(request["artifact_dir"]).resolve()
    if probe==case or probe.is_relative_to(case) or case.is_relative_to(probe):
        raise ValueError("PROBE_CASE_ARTIFACT_OVERLAP")
    probe.mkdir(parents=True,exist_ok=True)
    if (probe/"probe-io-provenance.json").exists() or (probe/"api-boundary-proof.json").exists():
        raise ValueError("PROBE_EVIDENCE_EXISTS_NO_REPLAY")
    kwargs=full_native_kwargs(request,artifact_dir=probe)
    original=native_engine.BacktestEngine
    calls=0;captured={};opened_journal=None
    class EngineBoundaryReached(BaseException): pass
    class BoundaryProxy:
        add_venue=original.add_venue
        def __new__(cls,*args,**kw):
            nonlocal calls,opened_journal
            calls+=1
            frame=inspect.currentframe().f_back
            try:
                if frame.f_code is not nb.run_native_diagnostic.__code__:
                    raise ValueError("UNEXPECTED_ENGINE_BOUNDARY_CALLER")
                local=frame.f_locals
                # Approved fields only; never serialize the frame or account/env.
                profile=local["current_hl"]
                captured.update(qualification_mode=local["qualification_mode"],
                    qualification_quantity_model=local["qualification_quantity_model"],
                    deposit_parameters_disabled=all(local[k] is None for k in
                        ("qualification_instrument_metadata","qualification_deposit_runtime","qualification_deposit_equity_reader"))
                        and local["qualification_deposit_account_id"]=="",
                    actual_execution_policy=asdict(local["policy"]),actual_fee_policy=asdict(local["fee_policy"]),
                    initial_active_seed=str(local["initial_active_seed"]),
                    trading_start_ms=local["trading_start_ms"],trading_end_ms=local["trading_end_ms"],
                    warmup_start_ms=local["warmup_start_ms"],
                    accounting_currencies=[str(i.settlement_currency) for i in profile.instruments],
                    instruments=[str(i.id) for i in profile.instruments],
                    public_profile_evidence=profile.evidence,
                    selected_leverage={str(i):str(v) for i,v in local["selected_leverage"]},
                    actual_cm2_policy=asdict(local["research_cm2"].policy))
                opened_journal=local.get("journal")
            finally:
                del frame
            raise EngineBoundaryReached()
    native_engine.BacktestEngine=BoundaryProxy
    started=time.monotonic();reached=False;error=None
    try:
        nb.run_native_diagnostic(**kwargs)
        raise ValueError("API_RETURNED_WITHOUT_ENGINE_BOUNDARY")
    except EngineBoundaryReached:
        reached=True
    except BaseException as exc:
        error={"type":type(exc).__name__,"message":str(exc)}
        raise
    finally:
        native_engine.BacktestEngine=original
        if opened_journal is not None:
            opened_journal.close()
        provenance={"case_artifact_dir":str(case),"probe_artifact_dir":str(probe),
            "only_kwarg_substitution":"artifact_dir","boundary_calls":calls,
            "native_engine_constructions":0,"engine_boundary_reached":reached,
            "elapsed_seconds":time.monotonic()-started,"error":error}
        (probe/"probe-io-provenance.json").write_text(json.dumps(provenance,indent=2)+"\n")
    if calls!=1 or not reached:
        raise ValueError("EXACT_ONE_PREENGINE_BOUNDARY_REQUIRED")
    if (captured["qualification_mode"]!="execution_diagnostic"
        or captured["qualification_quantity_model"]!="hl_current_usdc"
        or not captured["deposit_parameters_disabled"]
        or captured["accounting_currencies"]!=["USDC","USDC"]
        or captured["initial_active_seed"]!="10000"
        or captured["trading_start_ms"]!=request["start_ns"]//1_000_000 or captured["trading_end_ms"]!=request["end_ns"]//1_000_000):
        raise ValueError("ACTUAL_CM2_NATIVE_API_CONTRACT_DRIFT")
    actual=captured["actual_fee_policy"]
    if actual["venue"]!="hyperliquid" or actual["hyperliquid_maker"]!="0.000144" or actual["hyperliquid_taker"]!="0.000432":
        raise ValueError("ACTUAL_CM2_NATIVE_FEE_DRIFT")
    receipt={"status":"ACTUAL_API_ENGINE_BOUNDARY_PASS","native_engine_constructions":0,
        "boundary_calls":calls,"probe_artifact_dir":str(probe),"only_kwarg_substitution":"artifact_dir",
        "captured":captured,"source_sha256":{
            "native_baseline":hashlib.sha256(Path(nb.__file__).read_bytes()).hexdigest(),
            "cm2_runner":hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "provenance_sha256":hashlib.sha256((probe/"probe-io-provenance.json").read_bytes()).hexdigest()}
    (probe/"api-boundary-proof.json").write_text(json.dumps(receipt,indent=2,default=str)+"\n")
    return receipt

def run_worker(request,lease_fd):
    # Worker alone imports the runner capable of constructing a native engine.
    import os
    stat=os.fstat(lease_fd)
    target=os.stat(request["shared_lock_path"])
    if (stat.st_dev,stat.st_ino)!=(target.st_dev,target.st_ino):
        raise ValueError("CM2_LEASE_FD_INODE_MISMATCH")
    import nautilus_trader.backtest.engine as native_engine
    original=native_engine.BacktestEngine
    constructions=[]
    def exactly_one(*args,**kwargs):
        if constructions:
            raise RuntimeError("CM2_ONE_NATIVE_ENGINE_PER_ATTEMPT")
        constructions.append("RESERVED_BEFORE_CONSTRUCTOR")
        return original(*args,**kwargs)
    class OneEngineProxy:
        add_venue=original.add_venue
        def __new__(cls,*args,**kwargs):return exactly_one(*args,**kwargs)
    native_engine.BacktestEngine=OneEngineProxy
    try:
        if request["stage"]=="engineering":
            result=engineering_fixture_module(request).run_fixture(request)
            if len(constructions)!=1: raise ValueError("CM2_ACTUAL_FIXTURE_ENGINE_CONSTRUCTOR_COUNT")
            return result
        from coinmaster.research.native_baseline import run_native_diagnostic,save_diagnostic_report
        result=run_native_diagnostic(**full_native_kwargs(request))
        (Path(request["artifact_dir"])/"engine-construction-count.json").write_text(
            json.dumps({"engine_constructions":len(constructions)})+"\n")
        # Preserve raw native evidence before an independent validation failure.
        save_diagnostic_report(Path(request["data_root"]),result,request["run_id"],Path(request["artifact_dir"]))
        return result
    finally:
        native_engine.BacktestEngine=original
        (Path(request["artifact_dir"])/"engine-construction-count.json").write_text(
            json.dumps({"engine_constructions":len(constructions)})+"\n")

def source_family(request):
    family=request.get('source_family')
    if family not in ('CM2BTCREF','REFERENCE_BTC_ONLY'):raise ValueError('EXPLICIT_CM2_SOURCE_FAMILY_REQUIRED')
    return family


def worker_process_spec(request,lease_fd,digest,*,api_probe=False):
    """Literal secretless child contract; never copy the host environment."""
    import sys
    output=Path(request["artifact_dir"]).resolve()
    output.mkdir(parents=True,exist_ok=True)
    own_home=output/".worker-home"
    own_home.mkdir(exist_ok=True)
    child_env={"PATH":"/usr/bin:/bin:/usr/sbin:/sbin","HOME":str(own_home),
        "LANG":"C","LC_ALL":"C","TZ":"UTC","PYTHONUTF8":"1",
        "PYTHONNOUSERSITE":"1","PYTHONDONTWRITEBYTECODE":"1",
        "OMP_NUM_THREADS":"1","OPENBLAS_NUM_THREADS":"1","MKL_NUM_THREADS":"1",
        "VECLIB_MAXIMUM_THREADS":"1","NUMEXPR_NUM_THREADS":"1",
        "PYTHONPATH":str(Path(__file__).parents[2])}
    family=source_family(request)
    if family=='REFERENCE_BTC_ONLY':
        if Path(request['orchestrator_source_root']).resolve()!=Path(__file__).parents[3].resolve():
            raise ValueError('CONTROL_ORCHESTRATOR_ROOT_MISMATCH')
        child_env['PYTHONPATH']=str(Path(request['execution_source_root']).resolve()/'runtime')
        command=[sys.executable,'-B','-s',str(Path(__file__).with_name('cm2_reference_control_worker.py').resolve())]
        command.append('--api-probe' if api_probe else '--worker')
    else:
        command=[sys.executable,"-B","-s","-m","coinmaster.research.cm2_runner",
            "--api-probe" if api_probe else "--worker"]
    command.extend(["--request",str(Path(request["_request_path"]).resolve()),"--request-sha256",digest])
    if not api_probe:command.extend(["--lease-fd",str(lease_fd)])
    else:command.extend(["--probe-dir",str(output)])
    return command,child_env,str(output)

def record_native_child(output,pid,run_id,request_sha256):
    """Persist only safe operational identity immediately after worker spawn."""
    import os
    from datetime import datetime,timezone
    receipt={"status":"RUNNING","native_child_pid":int(pid),"parent_pid":os.getpid(),
        "run_id":run_id,"request_sha256":request_sha256,
        "spawn_utc":datetime.now(timezone.utc).isoformat()}
    with (Path(output)/"native-child.json").open("x") as stream:
        stream.write(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    return receipt

def wait_native_child(child):
    """Per-PID rusage; earlier constructor-free probe is not this worker."""
    import os,sys
    _,status,usage=os.wait4(child.pid,0)
    child.returncode=os.waitstatus_to_exitcode(status)
    peak=int(usage.ru_maxrss)*(1 if sys.platform=="darwin" else 1024)
    return child.returncode,peak

def main(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--request",type=Path,required=True)
    parser.add_argument("--resource-receipt",type=Path)
    parser.add_argument("--run",action="store_true")
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--api-probe",action="store_true",help=argparse.SUPPRESS)
    parser.add_argument("--probe-dir",type=Path,help=argparse.SUPPRESS)
    parser.add_argument("--lease-fd",type=int,help=argparse.SUPPRESS)
    parser.add_argument("--request-sha256",help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    request_bytes=args.request.read_bytes()
    request=json.loads(request_bytes)
    digest=hashlib.sha256(request_bytes).hexdigest()
    if args.api_probe:
        if args.probe_dir is None or digest!=args.request_sha256:
            raise SystemExit("CM2_INTERNAL_PROBE_CONTRACT")
        if request["stage"]=="engineering": fixture_api_boundary_probe(request,args.probe_dir)
        else: full_api_boundary_probe(request,args.probe_dir)
        print("ACTUAL_API_ENGINE_BOUNDARY_PASS_CONSTRUCTORS0")
        return
    if args.worker:
        request["_request_path"]=str(args.request.resolve())
        if args.lease_fd is None or digest!=args.request_sha256:
            raise SystemExit("CM2_INTERNAL_WORKER_CONTRACT")
        return run_worker(request,args.lease_fd)
    if args.resource_receipt is None:
        raise SystemExit("CM2_NATIVE_HOLD_NO_RESOURCE_RECEIPT")
    receipt=json.loads(args.resource_receipt.read_text())
    preflight(request,receipt)
    if request['stage'] in ('engineering','qualification','broad','local'):
        import uuid,subprocess
        probe=Path(request.get("api_probe_root",str(Path(request["artifact_dir"]).parent/"api-probes")))/str(uuid.uuid4())
        command,env,cwd=worker_process_spec(
            {**request,"artifact_dir":str(probe),"_request_path":str(args.request)},None,digest,api_probe=True)
        result=subprocess.run(command,env=env,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        (probe/"api-probe-worker.log").write_text(result.stdout)
        if result.returncode:
            raise SystemExit("CM2_FULL_API_PREFLIGHT_FAILED_NO_ATTEMPT:"+str(probe))
        proof=json.loads((probe/"api-boundary-proof.json").read_text())
        if proof["status"]!="ACTUAL_API_ENGINE_BOUNDARY_PASS" or proof["boundary_calls"]!=1 or proof["native_engine_constructions"]!=0:
            raise SystemExit("CM2_FULL_API_PREFLIGHT_INVALID_NO_ATTEMPT")
    if not args.run:
        print("CM2_PREFLIGHT_READY_NO_ENGINE_NO_ATTEMPT")
        return
    import os,subprocess,sys,time
    try:
        shared=acquire_shared_lease(request["shared_lock_path"])
    except BlockingIOError:
        raise SystemExit("CM2_NATIVE_HOLD_SHARED_LEASE")
    # Closing parent FD does not unlock the inherited child FD.
    with shared:
        output=Path(request["artifact_dir"])
        output.mkdir(parents=True,exist_ok=True)
        entry=register_attempt(request,receipt)
        entry["request_sha256"]=digest
        (output/"ATTEMPT_STARTED.json").write_text(json.dumps(entry)+"\n")
        command,child_env,child_cwd=worker_process_spec(
            {**request,"_request_path":str(args.request)},shared.fileno(),digest)
        start=time.monotonic()
        child=None;terminal_recorded=False
        try:
            with (output/"worker.log").open("w") as log:
                child=subprocess.Popen(command,env=child_env,cwd=child_cwd,stdout=log,stderr=subprocess.STDOUT,
                                       pass_fds=(shared.fileno(),))
                child_identity=record_native_child(output,child.pid,request["run_id"],digest)
                code,peak=wait_native_child(child)
            if code==0:
                request['_request_path']=str(args.request.resolve())
                postchild_validation(request)
            terminal={**entry,"status":"COMPLETED" if code==0 else "FAILED","exit_code":code,
                      "elapsed_seconds":time.monotonic()-start,"true_child_peak_rss_bytes":peak,
                      "rss_basis":"WAIT4_EXACT_NATIVE_CHILD_RUSAGE_MAXRSS"}
            with (output/"native-child-terminal.json").open("x") as stream:
                stream.write(json.dumps({**child_identity,**terminal},indent=2,sort_keys=True)+"\n")
            append_ledger(request["attempt_ledger"],terminal);terminal_recorded=True
            if code:
                raise SystemExit(code)
        except BaseException as error:
            if child is None:
                append_ledger(request["attempt_ledger"],{**entry,"status":"FAILED","error_type":type(error).__name__,
                    "elapsed_seconds":time.monotonic()-start})
            elif child.poll() is None:
                append_ledger(request["attempt_ledger"],{**entry,"status":"PARENT_INTERRUPTED_CHILD_STATE_UNKNOWN",
                    "child_pid":child.pid,"elapsed_seconds":time.monotonic()-start})
            elif not terminal_recorded:
                failure={**entry,'status':'FAILED','error_type':type(error).__name__,
                    'error':str(error),'native_child_pid':child.pid,'exit_code':child.returncode,
                    'elapsed_seconds':time.monotonic()-start,'phase':'POST_CHILD_PERSISTED_QUALIFICATION'}
                append_ledger(request['attempt_ledger'],failure)
                with (output/'native-child-terminal.json').open('x') as stream:
                    stream.write(json.dumps({**child_identity,**failure},indent=2,sort_keys=True)+'\n')
            raise

if __name__=="__main__": main()
