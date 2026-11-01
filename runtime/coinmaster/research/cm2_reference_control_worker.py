"""Thin original-API child. Top level is stdlib only; never imports current CM2.

Existing cm2_runner owns admission, lease, claim, ledger and qualification. This
leaf only materializes the frozen 5b kwargs and preserves its native raw report.
"""
from __future__ import annotations
import argparse,hashlib,inspect,json,os,sys,time
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

REFERENCE_COMMIT='5b56f7d02e09d4495ac018ec1ce701f6f0dfb737'
FAMILY='REFERENCE_BTC_ONLY'
PATH_FIELDS={'data_root','artifact_dir','current_hl_execution_inputs'}
DECIMAL_FIELDS={'initial_active_seed'}
FIXED={
    'include_funding':True,'initial_active_seed':'10000','stop_on_liquidation':False,'observe_minute_risk':True,
    'research_v0_execution_repairs':True,'research_v0_deferred_selective_zero_tp':True,
    'research_v0_selective_lifecycle_repairs':True,'research_btc_split50':True,
    'research_btc_split_planref_v1':True,'research_btc_split_tp_ioc':True,'research_btc_direction_sizing':True,
    'research_wait_4h':True,'research_regime_reentry_band':'0.5','research_residual_recovery':True,
    'research_c1_btc_cut_divisor':4,'research_c1_restore_dd':'0.40','research_c1_first_fresh_h4':True,
    'research_c1_btc_postcut_d1':True,'qualification_mode':'execution_diagnostic',
    'qualification_quantity_model':'hl_current_usdc','tp_fee_floor_v1':False,'research_v0_zero_tp_netting':False,
    'research_sol_notional_cap_6x':False,'research_portfolio_protect_45':False,'research_btc_drawdown_sizing':False,
    'research_v3_risk':None,'research_h1_b1':None,'research_btc_split_discount':'0.0025',
    'research_sol_btc_open_only':False,'research_h4_ema':None,'research_h4_gamma':'0.5',
    'research_h4_warmup':None,'research_wait_persist':False,'research_zero_retrace':False,
    'research_sol_dominant':False,'research_sol_cover':None,'research_conditional_sol':False,
    'research_immediate_sol':None,'research_immediate_lookback':90,'research_sol_risk_first':None,
    'research_alpha_cushion':False,'research_chop_pair':False,'research_btc_episode_loss_20':False,
    'research_sol_remaining_btc_hedge':False,'research_sol_capital_staging_a':True,
    'execution_policy':None,'fixed_base_fee_policy':None}
VARIABLE={'data_root','candidate','trading_start_ms','trading_end_ms','warmup_start_ms','artifact_label','artifact_dir','current_hl_execution_inputs'}
CANDIDATE={'ema_period':34,'beta_days':270,'relative_days':65,'z_history_days':180,'wave_history_days':730,
    'wave_min_count':8,'wave_quantiles':[.1,.3,.6],'btc_tp_fractions_initial_qty':[.2125,.2125,.575],
    'btc_notional_multiplier':7.875,'max_parent_notional':30000000.0,'sol_size_multipliers_h':[1.75,2.625,3.5],
    'sol_entry_z':[1.25,2.5,3.75],'sol_exit_half_z':.375,'sol_exit_all_z':.125,'sol_max_holding_days':14,
    'btc_close_trail_fraction':.03,'sol_timeout_preempts_add':False,'sol_late_entry_after_tp':True,
    'sol_overlay_enabled':False,'episode_fixed_beta':False}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok,reason):
    if not ok:raise ValueError(reason)


def same_typed(actual,expected):
    if type(actual) is not type(expected):return False
    if isinstance(expected,dict):return set(actual)==set(expected) and all(same_typed(actual[k],v) for k,v in expected.items())
    if isinstance(expected,list):return len(actual)==len(expected) and all(same_typed(a,b) for a,b in zip(actual,expected))
    return actual==expected


def validate_binding(request):
    require(request.get('source_family')==FAMILY,'CONTROL_SOURCE_FAMILY_REQUIRED')
    require(request.get('execution_source_commit')==REFERENCE_COMMIT,'CONTROL_EXACT_PUBLIC_COMMIT_REQUIRED')
    require(Path(request['execution_source_root']).is_absolute(),'CONTROL_ABSOLUTE_EXECUTION_ROOT_REQUIRED')
    root=Path(request['execution_source_root']).resolve();runtime=root/'runtime'
    require(root.is_absolute() and runtime.is_dir(),'CONTROL_EXECUTION_ROOT_REQUIRED')
    manifest_path=Path(request['execution_source_manifest'])
    require(sha(manifest_path)==request['execution_source_manifest_sha256'],'CONTROL_MANIFEST_HASH_MISMATCH')
    manifest=json.loads(manifest_path.read_text())
    require(manifest['commit']==REFERENCE_COMMIT and len(manifest['entries'])>=91,'CONTROL_SOURCE_MANIFEST_INCOMPLETE')
    seen=set()
    for entry in manifest['entries']:
        relative=Path(entry['path']);target=(root/relative).resolve()
        require(not relative.is_absolute() and target.is_relative_to(root),'CONTROL_SOURCE_PATH_ESCAPE')
        require(str(relative) not in seen,'CONTROL_DUPLICATE_SOURCE_ENTRY');seen.add(str(relative))
        content=target.read_bytes();blob=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
        require(len(content)==entry['bytes'] and blob==entry['git_blob_sha1'],'CONTROL_PUBLIC_BLOB_MISMATCH')
    kwargs_path=Path(request['prepared_control_kwargs'])
    require(sha(kwargs_path)==request['prepared_control_kwargs_sha256'],'CONTROL_PREPARED_KWARGS_HASH_MISMATCH')
    kwargs=json.loads(kwargs_path.read_text())
    require(type(kwargs) is dict and set(kwargs)==set(FIXED)|VARIABLE,'CONTROL_UNKNOWN_OR_MISSING_KWARG')
    for key,value in FIXED.items():
        require(type(kwargs[key]) is type(value) and kwargs[key]==value,'CONTROL_FROZEN_FLAG_MISMATCH:'+key)
    require(same_typed(kwargs['candidate'],CANDIDATE),'CONTROL_EXACT_CANDIDATE_REQUIRED')
    start,end=request['start_ns'],request['end_ns'];minute=60_000_000_000
    require(type(start) is int and type(end) is int and 0<start<end and start%minute==end%minute==0,'CONTROL_EXPLICIT_INTERVAL_REQUIRED')
    require(all(type(kwargs[k]) is int for k in ('trading_start_ms','trading_end_ms','warmup_start_ms')),'CONTROL_INTERVAL_TYPES_REQUIRED')
    require(all(type(kwargs[k]) is str and kwargs[k] for k in PATH_FIELDS|{'artifact_label'}),'CONTROL_PATH_LABEL_TYPES_REQUIRED')
    require(kwargs['trading_start_ms']*1_000_000==start and kwargs['trading_end_ms']*1_000_000==end
        and kwargs['warmup_start_ms']==start//1_000_000-730*86_400_000,'CONTROL_PREPARED_INTERVAL_MISMATCH')
    for key in ('data_root','current_hl_execution_inputs'):
        require(Path(kwargs[key]).resolve()==Path(request[key]).resolve(),'CONTROL_INPUT_ROOT_MISMATCH')
    return root,runtime,kwargs


def materialize(kwargs,request,*,artifact_dir):
    # Explicit whitelist above. No eval, dynamic types or compatibility fallbacks.
    from coinmaster.domain.wave_overlay import Candidate
    result=dict(kwargs)
    for key in PATH_FIELDS:result[key]=Path(result[key])
    for key in DECIMAL_FIELDS:result[key]=Decimal(result[key])
    result['candidate']=Candidate(**result['candidate'])
    result['artifact_dir']=Path(artifact_dir);result['artifact_label']=request['run_id']
    return result


def origins(runtime,verified_sources):
    result={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items()
        if n.startswith('coinmaster') and getattr(m,'__file__',None)}
    require(bool(result) and all(Path(v).is_relative_to(runtime) for v in result.values()),'CONTROL_MIXED_COINMASTER_ORIGINS')
    for value in result.values():
        path=Path(value);entry=verified_sources.get(str(path))
        require(entry is not None,'CONTROL_IMPORTED_SOURCE_NOT_IN_VERIFIED_MANIFEST')
        content=path.read_bytes();blob=hashlib.sha1(b'blob '+str(len(content)).encode()+b'\0'+content).hexdigest()
        require(len(content)==entry['bytes'] and blob==entry['git_blob_sha1'],'CONTROL_IMPORTED_SOURCE_BLOB_MISMATCH')
    return result


def validate_claim(request,lease_fd,request_sha256):
    require(lease_fd is not None and type(request_sha256) is str and len(request_sha256)==64,'CONTROL_STARTED_CLAIM_REQUIRED')
    a,b=os.fstat(lease_fd),os.stat(request['shared_lock_path'])
    require((a.st_dev,a.st_ino)==(b.st_dev,b.st_ino),'CONTROL_LEASE_INODE_MISMATCH')
    claim=json.loads((Path(request['artifact_dir'])/'ATTEMPT_STARTED.json').read_text())
    require(claim.get('status')=='STARTED' and claim.get('run_id')==request['run_id']
        and claim.get('stage')==request['stage'] and claim.get('request_sha256')==request_sha256,'CONTROL_STARTED_CLAIM_MISMATCH')
    rows=[json.loads(line) for line in Path(request['attempt_ledger']).read_text().splitlines() if line.strip()]
    starts=[r for r in rows if r.get('status')=='STARTED' and r.get('run_id')==request['run_id']]
    require(len(starts)==1 and all(starts[0].get(k)==claim.get(k) for k in ('run_id','stage','scope_version')),
        'CONTROL_PARENT_STARTED_LEDGER_MISMATCH')


def execute(request,*,lease_fd=None,probe_dir=None,request_sha256=None):
    root,runtime,prepared=validate_binding(request)
    # The child must be fresh: loading current coinmaster first is never safe.
    require(not any(n=='coinmaster' or n.startswith('coinmaster.') for n in sys.modules),'CONTROL_NOT_FRESH_PROCESS')
    require(Path(os.environ.get('PYTHONPATH','')).resolve()==runtime,'CONTROL_PYTHONPATH_MISMATCH')
    if probe_dir is None:validate_claim(request,lease_fd,request_sha256)
    output=Path(probe_dir or request['artifact_dir']);output.mkdir(parents=True,exist_ok=True)
    allowed={'.worker-home'} if probe_dir is not None else {'.worker-home','ATTEMPT_STARTED.json','native-child.json','worker.log'}
    require(all(p.name in allowed for p in output.iterdir()),'CONTROL_FRESH_ARTIFACT_NAMESPACE_REQUIRED')
    manifest=json.loads(Path(request['execution_source_manifest']).read_text())
    verified_sources={str((root/entry['path']).resolve()):entry for entry in manifest['entries']}
    import nautilus_trader.backtest.engine as ne
    original=ne.BacktestEngine;calls=[];capture={};opened=[];strategy_original=None;strategy_class=None;started=time.monotonic()
    class BoundaryReached(BaseException):pass
    class OneEngine:
        add_venue=original.add_venue  # Original API introspects this exact method.
        def __new__(cls,*args,**kwargs):
            require(not calls,'CONTROL_EXACTLY_ONE_ENGINE');calls.append('RESERVED_BEFORE_CONSTRUCTOR')
            if probe_dir is None:return original(*args,**kwargs)
            frame=inspect.currentframe().f_back
            try:
                require(frame.f_code is nb.run_native_diagnostic.__code__,'CONTROL_UNEXPECTED_ENGINE_CALLER')
                local=frame.f_locals
                capture.update(candidate=asdict(local['candidate']),execution_policy=asdict(local['policy']),
                    fee_policy=asdict(local['fee_policy']),funding_events_prepared=len(local['funding_events']))
                for name in ('journal','coherent_observer'):
                    if local.get(name) is not None:opened.append(local[name])
            finally:del frame
            raise BoundaryReached()
    ne.BacktestEngine=OneEngine
    try:
        from coinmaster.research import native_baseline as nb
        if probe_dir is not None:
            from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
            strategy_class=WaveOverlayStrategy;strategy_original=WaveOverlayStrategy.__init__
            def forbid_strategy(*args,**kwargs):raise ValueError('CONTROL_PROBE_NATIVE_STRATEGY_CONSTRUCTION_FORBIDDEN')
            WaveOverlayStrategy.__init__=forbid_strategy
        kwargs=materialize(prepared,request,artifact_dir=output)
        inspect.signature(nb.run_native_diagnostic).bind(**kwargs)
        origins(runtime,verified_sources)
        try:
            result=nb.run_native_diagnostic(**kwargs)
        except BoundaryReached:
            require(probe_dir is not None,'CONTROL_UNEXPECTED_BOUNDARY')
            result=None
        require(len(calls)==1,'CONTROL_ENGINE_BOUNDARY_NOT_REACHED')
        source_origins=origins(runtime,verified_sources)
        if probe_dir is not None:
            require(same_typed(capture['candidate'],CANDIDATE),'CONTROL_ACTUAL_CANDIDATE_DRIFT')
            fees=capture['fee_policy']
            require(fees['hyperliquid_maker']=='0.000144' and fees['hyperliquid_taker']=='0.000432','CONTROL_ACTUAL_FEE_DRIFT')
            receipt={'status':'ACTUAL_API_ENGINE_BOUNDARY_PASS','boundary_calls':len(calls),
                'native_engine_constructions':0,'captured':capture}
        else:
            # Original API already wrote run_id-raw-native.json. Never alter it.
            raw=output/(request['run_id']+'-raw-native.json')
            require(raw.is_file(),'CONTROL_ORIGINAL_RAW_REPORT_MISSING')
            receipt={'status':'ORIGINAL_NATIVE_API_RETURNED_NOT_FINANCIALLY_QUALIFIED',
                'raw_report':str(raw),'raw_report_sha256':sha(raw),'native_engine_constructions':len(calls)}
        receipt.update(source_family=FAMILY,execution_source_commit=REFERENCE_COMMIT,execution_source_root=str(root),
            orchestrator_source_root=request['orchestrator_source_root'],orchestrator_source_commit=request['orchestrator_source_commit'],
            bootstrap_sha256=sha(__file__),native_child_pid=os.getpid(),source_origins=source_origins,
            prepared_kwargs_sha256=request['prepared_control_kwargs_sha256'],elapsed_seconds=time.monotonic()-started)
        (output/('api-boundary-proof.json' if probe_dir is not None else 'control-native-terminal.json')).write_text(json.dumps(receipt,indent=2)+'\n')
        return receipt
    except BaseException as error:
        receipt={'status':'CONTROL_CHILD_FAILED_NOT_FINANCIALLY_QUALIFIED','error_type':type(error).__name__,
            'error':str(error),'native_child_pid':os.getpid(),'source_family':FAMILY,
            'native_engine_constructions':0 if probe_dir is not None else len(calls),
            'boundary_calls':len(calls),'elapsed_seconds':time.monotonic()-started}
        (output/'control-native-failure.json').write_text(json.dumps(receipt,indent=2)+'\n')
        raise
    finally:
        ne.BacktestEngine=original
        if strategy_class is not None:strategy_class.__init__=strategy_original
        for obj in opened:obj.close()
        (output/'engine-construction-count.json').write_text(json.dumps({'engine_constructions':0 if probe_dir is not None else len(calls),
            'boundary_calls':len(calls),'source_family':FAMILY})+'\n')


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--request',type=Path,required=True)
    p.add_argument('--request-sha256',required=True);p.add_argument('--lease-fd',type=int)
    modes=p.add_mutually_exclusive_group(required=True);modes.add_argument('--api-probe',action='store_true');modes.add_argument('--worker',action='store_true')
    p.add_argument('--probe-dir',type=Path)
    a=p.parse_args(argv);require(sha(a.request)==a.request_sha256,'CONTROL_REQUEST_HASH_MISMATCH')
    require(a.api_probe==(a.probe_dir is not None),'CONTROL_PROBE_ARGUMENT_BINDING')
    execute(json.loads(a.request.read_text()),lease_fd=a.lease_fd,probe_dir=a.probe_dir if a.api_probe else None,request_sha256=a.request_sha256)

if __name__=='__main__':main()
