"""Method-A P0/P1 prefix plumbing. No ledger writes, engine or money model."""
from pathlib import Path
from datetime import datetime,timezone
from inspect import signature
import ast,hashlib,json,os,subprocess,sys,uuid

SOURCE='a4dd4694284192dc7fe063495ac3e727efff4b38'
OWNER='3d17cb80101d1b88cd39043a062665f89086b22bebd53b5135535d260494ab60'
PROTOCOL='d7d32143cd26d2ff389483d2be0149499547b77c00af2404492b3b1b6af6bf93'
METRIC='ca815cbe3b8e163b16ccca8e388c9299125f74f0e1dd10beaa3ee15e4fe31102'
START=1725148800000;END=1736899200000
WARMED='5a02a0bc2555404261780cb4979e398494c70194e99317d8db1020fb026b8698'
LABELS=('P0','P1')
COMMON_GATES=('actual_os_exit0','complete_cash_reconciliation','signed_asset_funding_reconciliation',
 'ownership','continuous_settled_coverage','coherent_prefill_preopen_event_coverage','source_config_data_comparable',
 'rights_audit_complete','terminal_positions0_orders0','zero_model_liquidations')


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        while data:=stream.read(1024*1024):h.update(data)
    return h.hexdigest()


def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def write(path,value):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
    encoded=json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+chr(10)
    with tmp.open('w') as stream:stream.write(encoded);stream.flush();os.fsync(stream.fileno())
    os.replace(tmp,path);assert json.loads(path.read_text())==json.loads(encoded)


def pinned(ref):
    path=Path(ref['path']);assert path.is_absolute() and path.is_file()
    assert sha(path)==ref['sha256'],'METHOD_A_PIN_CHANGED:'+str(path)
    return path


def load_freeze(path):
    path=Path(path).resolve();g=json.loads(path.read_text());g['_freeze_path']=str(path);g['_freeze_sha256']=sha(path)
    assert g['schema']=='METHOD_A_PREFIX_FREEZE_V1' and g['label'] in LABELS
    assert g['source_commit']==SOURCE and g['total_max']==17 and g['prefix_max']==6
    assert g['calendar_ms']==[START,END] and g['seed']=='10000' and g['reserve']=='0'
    assert g['metric_contract_sha256']==METRIC
    return g


def verify_inputs(g):
    root=Path(g['data_root']).resolve()
    required=[root/'bybit-1m/manifest.json']+[root/'normalized'/('bybit-'+asset+'-'+kind+'.parquet')
        for asset in ('BTCUSDT','SOLUSDT') for kind in ('daily','execution-1m','mark-1m','funding')]
    pins={pinned(ref).resolve():ref['sha256'] for ref in g['input_files']}
    assert len(pins)==len(g['input_files']) and all(path.resolve() in pins for path in required),'ACTUAL_STOCK_NINE_FILES_NOT_PINNED_CHECK_DATA_ROOT'
    # Keep logical consumer IDs while resolving immutable existing symlinks.
    profile_ids=('runtime/var/venue-manifest.json','runtime/var/raw/venues/bybit-BTCUSDT-risk-limit.json','runtime/var/raw/venues/bybit-SOLUSDT-risk-limit.json')
    source=Path(g['source_root']).resolve()
    assert all((source/name).resolve() in pins for name in profile_ids),'ACTUAL_FROZEN_SOURCE_PUBLIC_PROFILES_NOT_PINNED'
    profiles={name:pins[(source/name).resolve()] for name in profile_ids}
    pinned(g['warmed_feed']);assert g['warmed_feed']['sha256']==WARMED
    identity=dict(calendar_ms=[START,END],files=[dict(relative_path=str(path.relative_to(root)),sha256=pins[path.resolve()]) for path in required],
        actual_public_profile_sha256=profiles,warmed_feed_sha256=WARMED,warmed_feed_role='PINNED_NOT_CONSUMED_BY_P0_P1_OLD_SOL')
    return dict(data_root=str(root),consumed_files=9,all_pinned_files=len(pins),native_input_sha256=canonical(identity),identity=identity,public_profile_sha256=profiles)


def common_economic_identity(g,args,inputs):
    from coinmaster.research.registered_control import native_kwargs_json_roundtrip
    projection=dict(args)
    projection['research_method_a_tp']=False
    projection['artifact_label']='<CONTROL_LABEL>'
    projection['artifact_dir']=Path('<ARTIFACT_NAMESPACE>')
    payload,_=native_kwargs_json_roundtrip(projection)
    return canonical(dict(source_commit=SOURCE,metric_contract_sha256=METRIC,
        native_input_sha256=inputs['native_input_sha256'],public_profile_sha256=inputs['public_profile_sha256'],
        economic_kwargs=json.loads(payload),venue=dict(liquidity_consumption=False,bar_execution=True)))


def verify_source(g):
    root=Path(g['source_root']).resolve()
    sys.path.insert(0,str(root/'runtime'));sys.path.insert(0,str(root/'runtime/tests'))
    from run_method_a_m1 import source_inventory
    seal=json.loads(pinned(dict(path=g['source_seal_path'],sha256=g['source_seal_sha256'])).read_text())
    assert seal['source_commit']==SOURCE and seal['files']==source_inventory(root),'EXACT_A4DD_IMMUTABLE_RUNTIME_REQUIRED'
    if (root/'.git').exists():
        # Wrapper-only report commits may advance Git HEAD. All runtime bytes
        # must still be exactly the accepted product/M1 a4dd reference.
        subprocess.run(['git','-C',str(root),'diff','--exit-code',SOURCE,'--','runtime'],check=True,capture_output=True)
    expected={'prefix_common.py','prefix_observer.py','prefix_worker.py','prefix_preflight.py'}
    assert {Path(ref['path']).name for ref in g['script_pins']}==expected
    for ref in g['script_pins']:
        assert pinned(ref).resolve()==Path(__file__).with_name(Path(ref['path']).name).resolve()
    return root


def verify_authority(g,launch=False):
    approval=json.loads(pinned(g['owner_approval']).read_text())
    assert g['owner_approval']['sha256']==OWNER and approval['physical_cap_total']==17 and approval['prefix']['max']==6
    assert approval['owner_exact_reply']=='согласовано' and approval['old_budgets_transferred'] is False
    assert g['protocol']['sha256']==PROTOCOL;pinned(g['protocol'])
    pinned(g['financial_contract']);engineering=json.loads(pinned(g['M1_root_acceptance']).read_text())
    # Root controls exact acceptance schema; identity must bind actual M1 source
    # and actual completed evidence, never an old E7/fixture permission.
    assert engineering['decision']=='ROOT_ACCEPTED_M1_CASE_ONLY_ALLOW_P0_P1_PREPARATION'
    assert engineering['source_commit']==SOURCE and engineering['attempt_id']=='ee47c0f4-b157-4362-9700-21a1b8c6c1e8'
    assert type(engineering['actual_os_exit']) is int and engineering['actual_os_exit']==0
    assert engineering['native_flat_before_cleanup'] is True and engineering['native_pending_orders0'] is True
    if launch:
        assert g['root_go'] is True and g['engineering_accepted'] is True
        go=json.loads(pinned(g['root_go_receipt']).read_text())
        assert go['root_go'] is True and go['label']==g['label'] and go['source_commit']==SOURCE
        for key in ('recipe_sha256','native_config_sha256','native_input_sha256','namespace'):assert go[key]==g[key]


def build_qualified_args(g):
    from coinmaster.research.method_a_controls import build_method_a_kwargs
    from coinmaster.research.registered_control import native_kwargs_json_roundtrip
    from coinmaster.research.native_baseline import run_native_diagnostic
    result=Path(g['namespace']).resolve()/'result'
    kwargs=build_method_a_kwargs(Path(g['data_root']).resolve(),result,g['label'])
    payload,restored=native_kwargs_json_roundtrip(kwargs);assert restored==kwargs
    bound=signature(run_native_diagnostic).bind(**kwargs);bound.apply_defaults()
    full_payload,_=native_kwargs_json_roundtrip(dict(bound.arguments))
    assert bound.arguments['research_method_a_observer'] is True and bound.arguments['observe_minute_risk'] is True
    assert bound.arguments['research_method_a_tp'] is (g['label']=='P1')
    assert bound.arguments['research_paired_policy'] is False and bound.arguments['research_paired_prefix'] is None
    assert bound.arguments['research_a0_family'] is None and bound.arguments['research_a0_original_second'] is False
    if g.get('kwargs_payload'):
        assert pinned(g['kwargs_payload']).read_text()==payload+chr(10),'FROZEN_CALL_KWARGS_CHANGED'
    return kwargs,dict(bound.arguments),payload,hashlib.sha256(full_payload.encode()).hexdigest()


def stock_preflight(g,args):
    from coinmaster.research.native_baseline import coverage_blockers,_load_daily_seed,funding_with_prior_minute_marks,iter_minute_bundles
    root=Path(args['data_root']);blockers=coverage_blockers(root);assert blockers==[]
    seed,daily=_load_daily_seed(root,args['warmup_start_ms'],START,END)
    assert len(seed)==730
    funding=funding_with_prior_minute_marks(root,START,END)
    count=0;first=last=None
    for row in iter_minute_bundles(root,START,END):
        if first is None:first=row.open_time_ms
        last=row.open_time_ms;count+=1
    assert count==195840 and first==START and last==END-60000
    return seed,daily,dict(status='ACTUAL_STOCK_LOADERS_ENGINE_FREE',engines_created=0,daily_seed_rows=len(seed),
        minute_bundles=count,first_minute_ms=first,last_minute_ms=last,
        funding_events=len(funding),funding_by_instrument={str(i):sum(row.instrument_id==i for row in funding) for i in {row.instrument_id for row in funding}},
        funding_prior_mark_basis=sorted({row.basis for row in funding}),last_seed_available=seed[-1].available_at.isoformat())


def native_config(g,args,seed,daily):
    from decimal import Decimal as D
    from nautilus_trader.model.data import BarType,BarSpecification
    from nautilus_trader.model.enums import BarAggregation,PriceType,AggregationSource
    from nautilus_trader.model.identifiers import ClientId
    from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP,perpetual
    from coinmaster.strategy.next_band import next_bar_type
    from coinmaster.research.native_baseline import build_native_strategy_config
    from run_continuous_hedge_preflight import snapshot_config
    instruments=[perpetual(i.raw_symbol.value,i.base_currency,str(i.price_increment),str(i.size_increment),str(i.margin_init),maker_fee=D('.00020'),taker_fee=D('.00055')) for i in (BTC_PERP,SOL_PERP)]
    btc,sol=instruments
    def kind(iid,price_type):return BarType(iid,BarSpecification(1,BarAggregation.DAY,price_type),AggregationSource.EXTERNAL)
    context=dict(args);context.update(btc_instrument=btc,sol_instrument=sol,kind=kind,mark_client=ClientId('BYBIT_MARK'),signal_client=ClientId('BYBIT_SIGNAL'),
        max_mark_age_ns=120*10**9,selected_leverage=((btc.id,D(40)),(sol.id,D(20))),policy=args['execution_policy'],
        seed_bars=seed,daily=daily,next_bar_types=(next_bar_type(btc.id,4),next_bar_type(sol.id,1)),
        confirmation_bars=(),h4_bar_type=None,h4_seed=(),cover_hour_seed=(),
        start_at=datetime.fromtimestamp(START/1000,timezone.utc),end_at=datetime.fromtimestamp(END/1000,timezone.utc))
    cfg=build_native_strategy_config(context);receipt=snapshot_config(cfg)
    return receipt['sha256']


def stock_venue_proof(source,args):
    tree=ast.parse((source/'runtime/coinmaster/research/native_baseline.py').read_text())
    call=next(n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='add_venue' and any(k.arg=='liquidity_consumption' for k in n.keywords))
    values={kw.arg:kw.value for kw in call.keywords}
    actual={key:eval(compile(ast.Expression(values[key]),'stock-venue-arg','eval'),{},args) for key in ('liquidity_consumption','bar_execution')}
    assert actual==dict(liquidity_consumption=False,bar_execution=True)
    return dict(status='EXACT_STOCK_AST_AND_BOUND_KWARGS',**actual,actual_registration='FUTURE_WORKER_PUBLIC_ADD_VENUE_RETURN_REQUIRED')


def prepare(g):
    source=verify_source(g);verify_authority(g);inputs=verify_inputs(g)
    kwargs,args,payload,full_sha=build_qualified_args(g)
    seed,daily,stock=stock_preflight(g,args);config_sha=native_config(g,args,seed,daily)
    economic_sha=common_economic_identity(g,args,inputs)
    recipe=dict(label=g['label'],calendar_ms=[START,END],seed='10000',reserve='0',native_config_sha256=config_sha,
        kwargs_sha256=hashlib.sha256((payload+chr(10)).encode()).hexdigest(),full_bound_kwargs_sha256=full_sha,
        input_sha256=inputs['native_input_sha256'],common_economic_identity_sha256=economic_sha,public_profile_sha256=inputs['public_profile_sha256'],metric_contract_sha256=METRIC,
        venue=stock_venue_proof(source,args),observer='IDENTICAL_READ_ONLY_PRE_MATCH_MODULE_AND_POST_CACHE_CALLBACK_STREAM',
        BTC_protection='NOT_APPLICABLE_LEGACY_CONTROL' if g['label']=='P0' else 'ACTUAL_CUMULATIVE_ENTRY_TP_AND_LATEST_NATIVE_ACK_REQUIRED',SOL_policy='UNCHANGED_OLD_OVERLAY_DIAGNOSTIC')
    return kwargs,dict(status='PREPARED_ENGINE_FREE_NO_FINANCIAL_PASS',source_commit=SOURCE,label=g['label'],engine_constructors=0,
        native_config_sha256=config_sha,native_input_sha256=inputs['native_input_sha256'],recipe_sha256=canonical(recipe),
        kwargs_sha256=recipe['kwargs_sha256'],full_bound_kwargs_sha256=full_sha,common_economic_identity_sha256=economic_sha,public_profile_sha256=inputs['public_profile_sha256'],recipe=recipe,stock=stock,inputs=inputs),payload


def verify_claim(g,ledger_path,attempt):
    assert str(uuid.UUID(attempt))==attempt
    ledger=json.loads(Path(ledger_path).read_text());assert ledger['total_max']==17 and ledger['categories']['prefix']['max']==6
    assert 1<=ledger['physical_started']<=17 and ledger['active']==1
    rows=[r for r in ledger['attempts'] if r['attempt_id']==attempt];assert len(rows)==1;row=rows[0]
    assert row['status']=='STARTED' and row['category']=='prefix' and row['label']==g['label'] and row['case']==g['label']+'_PREFIX'
    assert row['source_commit']==SOURCE and Path(row['namespace']).resolve()==Path(g['namespace']).resolve()
    assert row['owner_approval_sha256']==OWNER and row['source_seal_sha256']==g['source_seal_sha256']
    for key in ('recipe_sha256','native_config_sha256','native_input_sha256','common_economic_identity_sha256'):assert row[key]==g[key]
    assert len([r for r in ledger['attempts'] if r['category']=='prefix'])<=6
    return row


def verify_prior_financial(g,ledger_path):
    if g['label']=='P0':
        assert g.get('previous_financial_qualification') is None
        return
    inputs=verify_inputs(g);_,args,_,_=build_qualified_args(g)
    economic_sha=common_economic_identity(g,args,inputs)
    assert g['native_input_sha256']==inputs['native_input_sha256']
    assert g['common_economic_identity_sha256']==economic_sha
    receipt=json.loads(pinned(g['previous_financial_qualification']).read_text())
    assert receipt['schema']=='CM_METHOD_A_FINANCIAL_QUALIFICATION_V1'
    assert receipt['label']=='P0' and receipt['source_commit']==SOURCE and receipt['metric_contract_sha256']==METRIC
    assert receipt['decision']=='FINANCIAL_ACCEPTED_CONTROL' and receipt['qualification']=='FINANCIALLY_QUALIFIED' and receipt['accounting_qualified'] is True
    assert type(receipt['actual_returncode']) is int and receipt['actual_returncode']==0
    assert all(receipt['financial_gates'][key]=='PASS' for key in COMMON_GATES)
    assert receipt['financial_gates']['native_3TP']=='NOT_APPLICABLE_LEGACY_CONTROL'
    assert receipt['native_input_sha256']==g['native_input_sha256']
    assert receipt['common_economic_identity_sha256']==economic_sha and receipt['public_profile_sha256']==inputs['public_profile_sha256']
    assert Path(receipt['native_ledger_path']).resolve()==Path(ledger_path).resolve()
    current=json.loads(Path(ledger_path).read_text());snapshot=json.loads(pinned(receipt['ledger_snapshot']).read_text())
    for ledger in (current,snapshot):
        rows=[row for row in ledger['attempts'] if row['attempt_id']==receipt['attempt_id']]
        assert len(rows)==1;row=rows[0]
        assert row['status']=='COMPLETED' and row['category']=='prefix' and row['label']=='P0' and row['source_commit']==SOURCE
        assert canonical(row)==receipt['completed_attempt_sha256']
        detail=row['detail'];assert type(detail['actual_returncode']) is int and detail['actual_returncode']==0
        assert detail['report_sha256']==receipt['report_sha256'] and Path(detail['report']).resolve()==Path(receipt['report_path']).resolve()
        assert row['native_input_sha256']==g['native_input_sha256'] and row['common_economic_identity_sha256']==economic_sha
    namespace=Path(row['namespace']).resolve();detail=row['detail']
    report_path=pinned(dict(path=receipt['report_path'],sha256=receipt['report_sha256'])).resolve()
    assert report_path==namespace/'result/P0.json'
    report=json.loads(report_path.read_text());link=report['physical_prefix_attempt']
    assert link==receipt['physical_identity']==detail['physical_identity']
    assert link['attempt_id']==receipt['attempt_id'] and link['variant']==link['label']=='P0' and link['category']=='prefix' and link['source_commit']==SOURCE
    assert Path(link['ledger']).resolve()==Path(ledger_path).resolve()
    keys=('source_seal_sha256','native_config_sha256','native_input_sha256','recipe_sha256','common_economic_identity_sha256')
    for key in keys:assert link[key]==row[key]
    assert link['common_economic_identity_sha256']==economic_sha and link['public_profile_sha256']==inputs['public_profile_sha256']
    assert type(link['worker_pid']) is int and link['worker_pid']>0 and row['pid']==link['worker_pid']
    freeze=json.loads(pinned(receipt['freeze']).read_text());assert receipt['freeze']['sha256']==link['freeze_sha256']
    assert freeze['source_commit']==SOURCE and freeze['label']=='P0' and Path(freeze['namespace']).resolve()==namespace
    for key in keys+('kwargs_sha256','full_bound_kwargs_sha256'):assert freeze[key]==link[key]
    documents={}
    for role in ('risk_analysis','completion_manifest','supervisor'):
        value=json.loads(pinned(dict(path=receipt[role+'_path'],sha256=receipt[role+'_sha256'])).read_text());documents[role]=value
        if role=='risk_analysis':
            assert value['accounting_qualified'] is True and value['qualification']=='VALID_ACCOUNTED_PREFIX'
            binding=value['physical_binding']
            for key in ('attempt_id','label','source_commit','report_path','report_sha256','completed_attempt_sha256','completion_manifest_path','completion_manifest_sha256','supervisor_path','supervisor_sha256'):assert binding[key]==receipt[key]
            assert binding['physical_identity']==link
        else:
            assert value['attempt_id']==receipt['attempt_id'] and value['variant']=='P0' and value['source_commit']==SOURCE
            assert type(value['actual_returncode']) is int and value['actual_returncode']==0
            assert value['physical_identity']==link and value['freeze_sha256']==link['freeze_sha256'] and value['worker_pid']==link['worker_pid']
            assert Path(value['report']).resolve()==report_path and value['report_sha256']==receipt['report_sha256']
            assert value['status']=='NATIVE_PROCESS_EXPORTED_ACTUAL_OS_ZERO' if role=='completion_manifest' else value['ledger_status']=='COMPLETED'
    manifest=documents['completion_manifest'];supervisor=documents['supervisor']
    assert Path(receipt['completion_manifest_path']).resolve()==namespace/'completion-manifest.json'
    for obj in (supervisor,detail):
        assert Path(obj['completion_manifest']).resolve()==Path(receipt['completion_manifest_path']).resolve()
        assert obj['completion_manifest_sha256']==receipt['completion_manifest_sha256']
    assert detail['supervisor_sha256']==receipt['supervisor_sha256'] and Path(detail['supervisor']).resolve()==Path(receipt['supervisor_path']).resolve()
    expected={entry['role']:entry for entry in artifacts(namespace,'P0',report_path)}
    assert len(manifest['artifacts'])==4 and {entry['role']:entry for entry in manifest['artifacts']}==expected
    assert documents['risk_analysis']['physical_binding']['artifact_roles']==expected
    extras={'protection_profile':namespace/'result/method-a-native-protection.jsonl.gz','minute_risk':namespace/'result/minute-native-risk.csv.gz',
        'observer_profile':namespace/'native-observer-profile.json','raw_native':namespace/'result/method-a-P0-raw-native.json'}
    assert len(manifest['extra_evidence'])==4 and {entry['role'] for entry in manifest['extra_evidence']}==set(extras)
    for entry in manifest['extra_evidence']:assert pinned(dict(path=entry['path'],sha256=entry['sha256'])).resolve()==extras[entry['role']]
    profile=json.loads(extras['observer_profile'].read_text());assert profile==report['method_a_execution_profile']
    protection=next(entry for entry in manifest['extra_evidence'] if entry['role']=='protection_profile')
    assert Path(profile['path']).resolve()==Path(protection['path']).resolve() and profile['sha256']==protection['sha256']
    assert report['method_a_effective_config_sha256']==canonical(report['config'])==manifest['effective_config_sha256']
    assert report['config_hash']==manifest['source_config_hash_preserved']
    exit_receipt=json.loads(pinned(manifest['actual_exit_receipt']).read_text())
    assert exit_receipt['schema']=='METHOD_A_PREFIX_ACTUAL_OS_EXIT_V1' and exit_receipt['authority']=='ROOT_OBSERVED_CHILD_POPEN_WAIT'
    for key in ('attempt_id','variant','source_commit','worker_pid'):assert exit_receipt[key]==manifest[key]
    assert type(exit_receipt['actual_returncode']) is int and exit_receipt['actual_returncode']==0
    assert exit_receipt['freeze_sha256']==link['freeze_sha256']
    assert supervisor['actual_exit_receipt']==manifest['actual_exit_receipt']


def artifacts(namespace,label,report):
    namespace=Path(namespace).resolve();root=namespace/'result';stem='method-a-'+label
    paths=dict(report=Path(report),orders=root/(stem+'-orders.csv'),funding=root/(stem+'-funding.sqlite'),coherent=root/'coherent-native-events.jsonl.gz')
    assert len(set(paths.values()))==4
    return [dict(role=role,path=str(path.resolve()),sha256=sha(path)) for role,path in paths.items()]
