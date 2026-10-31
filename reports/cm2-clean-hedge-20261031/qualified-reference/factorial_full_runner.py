"""Private resolved-profile harness. No native construction before ROOT claim."""
import argparse, ast, csv, gzip, hashlib, importlib.util, inspect, json, signal, subprocess, sys, time, uuid
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path
ORIGINAL='fccd60c01e8cae5e8258748b046f43f88a16bb79'
LEGACY_SHA='2809421a2a584d8b227f2c7f5adfe4987f97016e2609724451188a39ef415f9a'
REFERENCE=None
ORIGINAL_API=None
DATA=None
INPUTS=None
PROBE_ROOT=None
H4_WARMUP=None
TP_DISTANCE_SCALE=1.0
SOL_DISABLED=False
ALLOW_ANTICIPATORY=False
RISK_RESERVE_FLOOR=False
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v): Path(p).write_text(json.dumps(v,indent=2,default=str)+'\n')
def tree_function(text):
    return next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='run_native_diagnostic')
def old_defaults(text):
    f=tree_function(text); a=f.args
    nodes={n.arg:v for n,v in zip(a.args[-len(a.defaults):],a.defaults)}
    nodes.update({n.arg:v for n,v in zip(a.kwonlyargs,a.kw_defaults) if v is not None})
    return {k:ast.literal_eval(v) for k,v in nodes.items() if k.startswith('research_') or k=='tp_fee_floor_v1'}
def resolve(cfg,oldtext):
    defaults=old_defaults(oldtext); resolved=dict(defaults); origins={k:'original_API_literal_default' for k in defaults}
    special={'research_btc_direction_sizing':lambda v: v=={'long':'5.5','short':'7.875','freeze':'GENUINE_EPISODE_CREATION'}}
    for k in defaults:
        if k in cfg:
            value=cfg[k]
            if k in special and isinstance(value,dict):
                if not special[k](value): raise ValueError('UNSUPPORTED_ORIGINAL_CONFIG:'+k)
                value=True
            if isinstance(value,(dict,list)): raise ValueError('UNSUPPORTED_ORIGINAL_CONFIG:'+k)
            resolved[k]=value;origins[k]='original_config.'+k
    aliases={
      'hedge_band_research':{'c0':'research_sol_btc_open_only','h4_ema':'research_h4_ema','h4_gamma':'research_h4_gamma','regime_reentry_band':'research_regime_reentry_band'},
      'next_band_research':{k:'research_'+k for k in ('wait_4h','wait_persist','zero_retrace','sol_dominant')},
      'residual_recovery_research':{'btc_cut_divisor':'research_c1_btc_cut_divisor','restore_DD':'research_c1_restore_dd'}}
    for group,fields in aliases.items():
        for key,target in fields.items():
            if key in cfg.get(group,{}):resolved[target]=cfg[group][key];origins[target]='original_config.'+group+'.'+key
    rr=cfg.get('residual_recovery_research')
    if rr:
        if rr.get('version')!='C1':raise ValueError('UNSUPPORTED_C1_VERSION')
        for target,key in [('research_residual_recovery',None),('research_c1_first_fresh_h4','first_fresh_h4'),('research_c1_btc_postcut_d1','btc_postcut_d1'),('research_c1_global_cut_arm','global_cut_arm')]:
            resolved[target]=True if key is None else key in rr;origins[target]='original_config.residual_recovery_research'+('' if key is None else '.'+key)
    unknown={k for k in cfg if k.startswith('research_') and k not in defaults}
    if unknown:raise ValueError('UNSUPPORTED_ORIGINAL_FIELDS:'+str(sorted(unknown)))
    if cfg.get('hedge_band_research',{}).get('h4_warmup_sha256') is not None:raise ValueError('UNSUPPORTED_NONDEFAULT_OLD_WARMUP')
    if resolved['research_v0_deferred_selective_zero_tp'] and resolved['research_v0_zero_tp_netting'] is not False:raise ValueError('DEFERRED_REQUIRES_EXPLICIT_ZERO_NETTING_FALSE')
    return resolved,origins

def prepare(source,out,case,seed):
    legacy_path=Path(__file__).with_name('factorial_full_helper.py')
    if sha(legacy_path)!=LEGACY_SHA:raise ValueError('LEGACY_HELPER_CHANGED')
    spec=importlib.util.spec_from_file_location('preserved_full_runner',legacy_path);legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
    legacy.DATA=DATA;legacy.INPUTS=INPUTS;legacy.REFERENCE=REFERENCE
    sys.path.insert(0,str(source/'runtime'))
    import nautilus_trader.backtest.engine as ne
    original_engine=ne.BacktestEngine
    def forbidden(*a,**k):raise RuntimeError('ENGINE_FORBIDDEN_BEFORE_ROOT_CLAIM')
    class EngineFree:
        add_venue=original_engine.add_venue
        def __new__(cls,*a,**k):return forbidden(*a,**k)
    ne.BacktestEngine=EngineFree
    try: nb,kwargs,pins,ne=legacy.prepare(source,out)
    finally:ne.BacktestEngine=forbidden
    try:
        oldtext=ORIGINAL_API.read_text()
        cfg=json.loads(REFERENCE.read_text())['config'];resolved,origins=resolve(cfg,oldtext)
        from coinmaster.domain.wave_overlay import Candidate
        candidate=Candidate(**cfg['candidate'])
        if json.loads(json.dumps(asdict(candidate)))!=cfg['candidate']:raise ValueError('CANDIDATE_ROUNDTRIP_MISMATCH')
        sig=inspect.signature(nb.run_native_diagnostic)
        matrix={}; unsupported=[]
        for k,v in resolved.items():
            supported=k in sig.parameters
            if not supported and v!=old_defaults(oldtext)[k]:unsupported.append(k)
            matrix[k]=dict(original_resolved=v,origin=origins[k],supported=supported,actual_api=v if supported else 'UNSUPPORTED_INERT_OLD_DEFAULT')
        if unsupported:raise ValueError('UNSUPPORTED_OLD_NONDEFAULT:'+str(unsupported))
        kwargs.update({k:v for k,v in resolved.items() if k in sig.parameters})
        kwargs['candidate']=candidate
        new_flags={k:p.default for k,p in sig.parameters.items() if k.startswith('research_') and k not in resolved}
        for k,v in new_flags.items():
            if v not in (False,None) and not (k=='research_factorial_tp_distance_scale' and v==1.0) and not (k=='research_factorial_hedge_require_btc_adverse' and v is True):raise ValueError('NEW_FLAG_NOT_OFF:'+k)
            kwargs[k]=v
        if case in ('A10','A01','A11','T08','T12','B0','A01C','A11C','A01N','A11N','PF_STAGE','PB_A10','PB_DEFER'):
            if 'research_sol_capital_staging_a' not in sig.parameters:raise ValueError('A_SOURCE_API_UNAVAILABLE')
            kwargs['research_sol_capital_staging_a']=True
            kwargs['research_factorial_tp']=case in ('A10','A11','T08','T12','A11C','A11N','PF_STAGE','PB_A10','PB_DEFER')
            kwargs['research_parent_bound_a10']=case in ('PB_A10','PB_DEFER')
            if case in ('PB_A10','PB_DEFER') and TP_DISTANCE_SCALE!=1.0:raise ValueError('PB_A10_REQUIRES_DISTANCE_ONE')
            kwargs['research_factorial_tp_distance_scale']=TP_DISTANCE_SCALE
            if case in ('A01C','A11C','A01N','A11N','PF_STAGE') and TP_DISTANCE_SCALE!=1.0:raise ValueError('CORRECTED_H_REQUIRES_DISTANCE_SCALE_ONE')
            if case in ('T08','T12') and TP_DISTANCE_SCALE!={'T08':.8,'T12':1.2}[case]:raise ValueError('FROZEN_T_DISTANCE_CASE_MISMATCH')
            if SOL_DISABLED!=(case=='B0'):raise ValueError('SOL_DISABLED_REQUIRES_B0_CASE_AND_FLAG')
            kwargs['research_factorial_sol_disabled']=SOL_DISABLED
            if ALLOW_ANTICIPATORY!=(case in ('A01N','A11N','PF_STAGE')):raise ValueError('ANTICIPATORY_H_REQUIRES_N_CASE_AND_FLAG')
            kwargs['research_factorial_hedge_require_btc_adverse']=not ALLOW_ANTICIPATORY
            if RISK_RESERVE_FLOOR!=(case=='PF_STAGE'):raise ValueError('RESERVE_FLOOR_REQUIRES_PF_STAGE_CASE_AND_FLAG')
            kwargs['research_factorial_risk_reserve_floor']=RISK_RESERVE_FLOOR
            kwargs['research_factorial_hedge']=case in ('A01','A11','B0','A01C','A11C','A01N','A11N','PF_STAGE')
            kwargs['research_factorial_h4_warmup']=H4_WARMUP if kwargs['research_factorial_hedge'] or kwargs['research_parent_bound_a10'] else None
        else:raise ValueError('FACTORIAL_CASE_REQUIRED')
        # Preserve the original policy's actual dataclass shape, overriding only
        # declared current-HL assumptions, as in current run API's own factory.
        policy=dict(cfg['execution_policy']);inspect.signature(nb.ExecutionPolicy).bind(**policy)
        policy.update(version='current-hl-usdc-full-fill-diagnostic-v1',fees='OWNER_EFFECTIVE_HL_MAKER_0.000144_TAKER_0.000432_REFERRAL_ALREADY_APPLIED',spread_slippage_liquidity='ZERO_MARKET_IMPACT_FULL_FILL_DIAGNOSTIC_NOT_OBSERVED_CAPACITY',liquidation='CURRENT_PUBLIC_HL_TIERS_NATIVE_USDC_ON_HISTORICAL_PROXY_MARKS')
        kwargs.update(execution_policy=None,fixed_base_fee_policy=None,initial_active_seed=seed,artifact_label=case,stop_on_liquidation=False,observe_minute_risk=True)
        sig.bind(**kwargs)
        # Build the actual strategy config using the current API's own AST
        # projection of every scalar research input. No strategy/engine runs.
        from coinmaster.strategy.wave_overlay import WaveOverlayStrategyConfig
        from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
        from nautilus_trader.model.data import BarType
        from nautilus_trader.model.identifiers import ClientId
        from coinmaster.venues.marks import venue_mark_data_type
        profile=load_current_hl_diagnostic(legacy.INPUTS);btc,sol=profile.instruments
        sc=dict(btc_id=btc.id,sol_id=sol.id,btc_bar_type=BarType.from_str(str(btc.id)+'-1-DAY-LAST-EXTERNAL'),sol_bar_type=BarType.from_str(str(sol.id)+'-1-DAY-LAST-EXTERNAL'),btc_mark_data_type=venue_mark_data_type(btc.id),sol_mark_data_type=venue_mark_data_type(sol.id),mark_client_id=ClientId('RESOLVED_PREFLIGHT'),active_seed=seed,candidate=candidate)
        call=next(n for n in ast.walk(tree_function(inspect.getsource(nb.run_native_diagnostic))) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='WaveOverlayStrategyConfig')
        factorial_seed=()
        if kwargs['research_factorial_hedge'] or kwargs['research_parent_bound_a10']:
            with H4_WARMUP.open() as h:
                factorial_seed=tuple((int(r['close_time_ns']),r['btc_close'],r['sol_close']) for r in csv.DictReader(h))
        env={**kwargs,'Decimal':D,'factorial_seed':factorial_seed}
        for kw in call.keywords:
            if kw.arg and (kw.arg.startswith('research_') or kw.arg=='tp_fee_floor_v1'):
                names={n.id for n in ast.walk(kw.value) if isinstance(n,ast.Name)}
                if names <= env.keys():sc[kw.arg]=eval(compile(ast.Expression(kw.value),'<actual-run-config>','eval'),{'__builtins__':{}},env)
        actual=WaveOverlayStrategyConfig(**sc)
        actual_flags=dict(research_parent_bound_a10=actual.research_parent_bound_a10,research_factorial_tp=actual.research_factorial_tp,research_factorial_hedge=actual.research_factorial_hedge,
            research_factorial_tp_distance_scale=actual.research_factorial_tp_distance_scale,
            research_factorial_sol_disabled=actual.research_factorial_sol_disabled,
            research_factorial_hedge_require_btc_adverse=actual.research_factorial_hedge_require_btc_adverse,
            research_factorial_risk_reserve_floor=actual.research_factorial_risk_reserve_floor,
            paired_h4_seed_rows=len(actual.research_factorial_h4_seed),seed_last_ns=actual.research_factorial_h4_seed[-1][0] if actual.research_factorial_h4_seed else None)
        if json.loads(json.dumps(actual_flags))!=actual_flags:raise ValueError('FACTORIAL_FLAG_JSON_ROUNDTRIP')
        if actual_flags['research_parent_bound_a10']!=kwargs['research_parent_bound_a10'] or actual_flags['research_factorial_tp']!=kwargs['research_factorial_tp'] or actual_flags['research_factorial_hedge']!=kwargs['research_factorial_hedge'] or actual_flags['research_factorial_tp_distance_scale']!=kwargs['research_factorial_tp_distance_scale'] or actual_flags['research_factorial_sol_disabled']!=kwargs['research_factorial_sol_disabled'] or actual_flags['research_factorial_hedge_require_btc_adverse']!=kwargs['research_factorial_hedge_require_btc_adverse'] or actual_flags['research_factorial_risk_reserve_floor']!=kwargs['research_factorial_risk_reserve_floor']:
            raise ValueError('FACTORIAL_ACTUAL_CONFIG_FLAG_DRIFT')
        if (kwargs['research_factorial_hedge'] or kwargs['research_parent_bound_a10']) and (actual_flags['paired_h4_seed_rows']<181 or actual_flags['seed_last_ns']!=1725148800000000000):
            raise ValueError('FACTORIAL_ACTUAL_CONFIG_H4_WARMUP_DRIFT')
        pins['factorial_actual_strategy_flags']=actual_flags
        pins['factorial_h4_feature_sha256']=sha(H4_WARMUP) if kwargs['research_factorial_hedge'] or kwargs['research_parent_bound_a10'] else None
        for k,row in matrix.items():
            if hasattr(actual,k):
                value=getattr(actual,k);expected=resolved[k]
                if isinstance(value,D) and expected is not None:expected=D(str(expected))
                row['actual_strategy_config']=value
                if value!=expected:raise ValueError('CONFIG_PROJECTION_MISMATCH:'+k)
        oldbase=next(n.value for n in ast.parse(oldtext).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='BASELINE_CONFIG' for t in n.targets))
        fixed=ast.literal_eval(oldbase)
        for k,v in fixed.items():
            if cfg.get(k)!=v:raise ValueError('UNSUPPORTED_ORIGINAL_BASELINE_OVERRIDE:'+k)
            if nb.BASELINE_CONFIG.get(k)!=v:raise ValueError('CURRENT_BASELINE_DRIFT:'+k)
        pins['original_fixed_strategy_envelope']=fixed
        if actual.research_v0_zero_tp_netting is not False or not actual.research_v0_deferred_selective_zero_tp:raise ValueError('ACTUAL_CONFIG_ZERO_NETTING_DRIFT')
        from types import SimpleNamespace
        strategy_tree=ast.parse(inspect.getsource(sys.modules[WaveOverlayStrategyConfig.__module__]))
        guard=next(n.test for n in ast.walk(strategy_tree) if isinstance(n,ast.If) and 'research_v0_zero_tp_netting' in ast.unparse(n.test) and 'rounded > 0' in ast.unparse(n.test))
        renet=eval(compile(ast.Expression(guard),'<actual-BTC-entry-guard>','eval'),{'__builtins__':{}},dict(self=SimpleNamespace(config=actual,_split_child_submit=False),intent=SimpleNamespace(action='BTC_ENTRY'),rounded=D('0.79073')))
        if renet:raise ValueError('FIRST_BTC_LEGACY_RENET_BRANCH_ACTIVE')
        pins['first_btc_selected_qty_probe']=dict(selected_input='0.79073',native_step=str(btc.size_increment),rounded_native_qty=str(btc.make_qty(D('0.79073'))),legacy_renet_branch=renet,basis='actual source predicate with actual typed resolved config; pure quantity probe, not a native fill')
        origins_actual={n:str(Path(m.__file__).resolve()) for n,m in sys.modules.items() if n.startswith('coinmaster') and getattr(m,'__file__',None)}
        if not all(Path(p).is_relative_to(source/'runtime') for p in origins_actual.values()):raise ValueError('SOURCE_ORIGIN_DRIFT')
        pins['source_origins']=origins_actual
        pins.update(harness_sha256=sha(__file__),legacy_helper_sha256=sha(legacy_path),case=case,original_source_commit=ORIGINAL,original_source_sha256=hashlib.sha256(oldtext.encode()).hexdigest(),resolved_field_matrix=matrix,new_flags={k:kwargs[k] for k in new_flags},candidate_exact_original=True,execution_policy_original=cfg['execution_policy'],execution_policy_expected=policy,execution_policy_overrides={k:v for k,v in policy.items() if cfg['execution_policy'][k]!=v},actual_strategy_config_constructed=True,engine_constructions=0,zero_tp_netting_explicit_false=True,first_btc_no_legacy_renet=True,kwargs={k:asdict(v) if k in ('candidate','execution_policy','fixed_base_fee_policy') and v is not None else str(v) if isinstance(v,(Path,D)) else v for k,v in kwargs.items()})
        return nb,kwargs,pins,ne,original_engine,legacy
    finally:ne.BacktestEngine=original_engine

def first_actual_features(nb,kwargs,source):
    """Real pinned inputs through the exact causal H consumer, engine count0."""
    from math import isfinite
    from types import SimpleNamespace as N
    from coinmaster.domain.wave_overlay import features_for
    from coinmaster.strategy.factorial_hedge import FactorialHedge
    from coinmaster.strategy.next_band import NextClosedBar
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    from nautilus_trader.cache.cache import Cache
    start=kwargs['trading_start_ms'];end=start+14400000
    seed,_=nb._load_daily_seed(DATA,kwargs['warmup_start_ms'],start,kwargs['trading_end_ms'])
    signal=features_for(list(seed),kwargs['candidate'])[-1]
    if signal.z is None or not isfinite(signal.z):raise ValueError('ACTUAL_INITIAL_LEGACY_Z_UNAVAILABLE')
    daily_ns=int(seed[-1].close_time.timestamp()*1_000_000_000)
    if daily_ns>start*1_000_000:raise ValueError('ACTUAL_INITIAL_Z_FROM_FUTURE')
    with H4_WARMUP.open() as f:
        h4seed=tuple((int(r['close_time_ns']),r['btc_close'],r['sol_close']) for r in csv.DictReader(f))
    rows=list(nb.iter_minute_bundles(DATA,start,end,batch_rows=240))
    if len(rows)!=240:raise ValueError('ACTUAL_FIRST_H4_NOT_COMPLETE')
    if any(b.open_time_ms-a.open_time_ms!=60000 for a,b in zip(rows,rows[1:])):raise ValueError('ACTUAL_FIRST_H4_GAP')
    profile=load_current_hl_diagnostic(INPUTS);btc,sol=profile.instruments
    class Consumer(FactorialHedge):pass
    h=Consumer();h.config=N(research_factorial_hedge=True,research_factorial_h4_seed=h4seed,btc_id=btc.id,sol_id=sol.id)
    h.cache=Cache();h.cache.add_instrument(btc);h.cache.add_instrument(sol)
    h._domain=N(episode=None);h._current_signals=[signal];h.clock=N(timestamp_ns=lambda:end*1_000_000)
    h._fh_init()
    for inst,key in ((btc,'btc_execution'),(sol,'sol_execution')):
        bars=[getattr(row,key) for row in rows]
        event=NextClosedBar(inst.id,4,D(bars[0]['open']),max(D(b['high']) for b in bars),min(D(b['low']) for b in bars),D(bars[-1]['close']),end*1_000_000)
        h._fh_bar(event)
    feature=h._fh_feature
    if feature is None or not all(v.is_finite() for v in feature.values() if isinstance(v,D)) or feature['var_btc']<=0 or feature['var_sol']<=0:
        raise ValueError('ACTUAL_FIRST_H4_FEATURE_UNAVAILABLE')
    if not feature['prior_end_ns']<feature['ns'] or h._current_signals[-1].z!=signal.z:raise ValueError('ACTUAL_H_CONSUMER_CAUSALITY_DRIFT')
    return dict(status='ACTUAL_INPUT_CONSUMER_READY',engine_constructions=0,paired_seed_closes=len(h4seed),first_h4_minutes=len(rows),
        legacy_z=signal.z,legacy_z_field='_current_signals[-1].z',legacy_z_available_ns=daily_ns,
        first_joint_h4_available_ns=end*1_000_000,first_h4_feature=feature,
        note='Input readiness only: actual BTC parent and conjunctive trigger still required; no fabricated eligibility/fill')

def preengine_probe(nb,kwargs,pins,ne,original,out):
    """Execute exact public-data API gates; intercept before native constructor."""
    probe=PROBE_ROOT/str(uuid.uuid4())
    if probe.is_relative_to(out.resolve()) or out.resolve().is_relative_to(probe):raise ValueError('PROBE_CASE_ARTIFACT_OVERLAP')
    probe.mkdir(parents=True,exist_ok=False)
    captured={}; calls=0
    class EngineBoundaryReached(BaseException):pass
    def boundary(*args,**kw):
        nonlocal calls
        calls+=1
        frame=inspect.currentframe().f_back
        try:
            if frame.f_code is not nb.run_native_diagnostic.__code__:raise ValueError('UNEXPECTED_ENGINE_CALLER')
            # Capture only the three approved resolved objects, never the frame.
            for key in ('policy','fee_policy','candidate'):captured[key]=asdict(frame.f_locals[key])
        finally:del frame
        raise EngineBoundaryReached('ENGINE_BOUNDARY_REACHED')
    ne.BacktestEngine=boundary
    t=time.monotonic();reached=False;error=None
    try:
        nb.run_native_diagnostic(**{**kwargs,'artifact_dir':probe})
        raise ValueError('API_RETURNED_WITHOUT_ENGINE_BOUNDARY')
    except EngineBoundaryReached:
        reached=True
    except BaseException as exc:
        error=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        ne.BacktestEngine=original
        write(probe/'probe-io-provenance.json',dict(case_artifact_dir=str(out.resolve()),probe_artifact_dir=str(probe),only_kwarg_substitution='artifact_dir',artifact_label=kwargs['artifact_label'],initial_active_seed=str(kwargs['initial_active_seed']),engine_boundary_reached=reached,native_engine_constructions=0,boundary_calls=calls,elapsed_seconds=time.monotonic()-t,error=error,generated_files=[dict(path=str(p.relative_to(probe)),size=p.stat().st_size,sha256=sha(p)) for p in probe.rglob('*') if p.is_file()]))
    if calls!=1 or not reached:raise ValueError('EXACT_ONE_PREENGINE_BOUNDARY_REQUIRED')
    expected_fees=dict(json.loads(REFERENCE.read_text())['config']['fixed_base_fee_policy'])
    expected_fees.update(venue='hyperliquid',hyperliquid_maker='0.000144',hyperliquid_taker='0.000432')
    if captured['policy']!=pins['execution_policy_expected']:raise ValueError('ACTUAL_FACTORY_EXECUTION_POLICY_DRIFT')
    if captured['fee_policy']!=expected_fees:raise ValueError('ACTUAL_FACTORY_FEE_POLICY_DRIFT')
    if json.loads(json.dumps(captured['candidate']))!=json.loads(json.dumps(asdict(kwargs['candidate']))):raise ValueError('ACTUAL_FACTORY_EFFECTIVE_CANDIDATE_DRIFT')
    receipt=dict(status='ACTUAL_API_ENGINE_BOUNDARY_PASS',native_engine_constructions=0,boundary_calls=calls,probe_artifact_dir=str(probe),only_kwarg_substitution='artifact_dir',execution_policy_kwarg=None,fixed_base_fee_policy_kwarg=None,actual_execution_policy=captured['policy'],actual_fee_policy=captured['fee_policy'],actual_effective_candidate=captured['candidate'],policy_matches_original_plus_declared_overrides=True,fee_policy_matches_declared_current_profile=True,effective_candidate_exact_original=True,io_provenance_sha256=sha(probe/'probe-io-provenance.json'))
    write(probe/'api-boundary-proof.json',receipt)
    return receipt

def coverage(result,out):
    paths=list(out.rglob('minute-native-settled-receipts.csv.gz'))
    if len(paths)!=1:raise ValueError('SETTLED_RECEIPTS_CSV_NOT_UNIQUE:'+str(paths))
    counts=Counter();n=0;first=None;last=None
    with gzip.open(paths[0],'rt') as f:
        reader=csv.DictReader(f)
        for row in reader:
            if n==0:
                source_key=next((k for k in ('source_quote_ns','source_ts_ns','source_timestamp_ns','source_ns') if k in row),None)
                receipt_key=next((k for k in ('receipt_ts_ns','receipt_timestamp_ns','receipt_ns') if k in row),None)
                if source_key is None or receipt_key is None:raise ValueError('UNKNOWN_RECEIPT_CSV_SHAPE:'+str(reader.fieldnames))
            s=int(row[source_key]);r=int(row[receipt_key]);expected=1725148860000000000+n*60000000000
            if s!=expected or r!=s+60000000000:raise ValueError('SETTLED_RECEIPT_SEQUENCE_OR_BOUND_DRIFT')
            first=first or s;last=r;counts[datetime.fromtimestamp(s//1000000000,tz=timezone.utc).strftime('%Y-%m')]+=1;n+=1
    import calendar
    month_counts_complete=all(count==calendar.monthrange(int(month[:4]),int(month[5:]))[1]*1440-(1 if month=='2024-09' else 0) for month,count in counts.items())
    return dict(month_counts_complete=month_counts_complete,path=str(paths[0]),sha256=sha(paths[0]),rows=n,initial_seed_samples=1,first_source_ns=first,last_receipt_ns=last,source_calendar_months=len(counts),month_rows=dict(counts),full=n==1051199 and last==1788220800000000000 and len(counts)==24 and month_counts_complete)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--case',choices=['A10','A01','A11','T08','T12','B0','A01C','A11C','A01N','A11N','PF_STAGE','PB_A10','PB_DEFER'],required=True);ap.add_argument('--source-root',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--claim',type=Path);ap.add_argument('--preflight',action='store_true');ap.add_argument('--seed',type=D,default=D('10000'));ap.add_argument('--data-root',type=Path,required=True);ap.add_argument('--public-inputs',type=Path,required=True);ap.add_argument('--reference-report',type=Path,required=True);ap.add_argument('--original-api-source',type=Path,required=True);ap.add_argument('--probe-root',type=Path,required=True);ap.add_argument('--h4-warmup',type=Path,required=True);ap.add_argument('--tp-distance-scale',type=float,default=1.0);ap.add_argument('--sol-disabled',action='store_true');ap.add_argument('--allow-anticipatory-hedge',action='store_true');ap.add_argument('--risk-reserve-floor',action='store_true');a=ap.parse_args()
    global REFERENCE,ORIGINAL_API,DATA,INPUTS,PROBE_ROOT,H4_WARMUP,TP_DISTANCE_SCALE,SOL_DISABLED,ALLOW_ANTICIPATORY,RISK_RESERVE_FLOOR
    TP_DISTANCE_SCALE=a.tp_distance_scale;SOL_DISABLED=a.sol_disabled;ALLOW_ANTICIPATORY=a.allow_anticipatory_hedge;RISK_RESERVE_FLOOR=a.risk_reserve_floor
    REFERENCE=a.reference_report.resolve();ORIGINAL_API=a.original_api_source.resolve()
    DATA=a.data_root.resolve();INPUTS=a.public_inputs.resolve();PROBE_ROOT=a.probe_root.resolve();H4_WARMUP=a.h4_warmup.resolve()
    if a.seed<=0 or not a.seed.is_finite():raise ValueError('INVALID_SEED')
    a.out.mkdir(parents=True,exist_ok=True);source=a.source_root.resolve()
    if not a.preflight and any((a.out/n).exists() for n in ('native-report.json','process-result.json','failure.json')):raise ValueError('PRESERVE_EXISTING_RUN_RECEIPTS')
    nb,kwargs,pins,ne,original,legacy=prepare(source,a.out,a.case,a.seed)
    if a.case in ('A01','A11','B0','A01C','A11C','A01N','A11N','PF_STAGE','PB_A10','PB_DEFER'):pins['first_actual_h_feature']=first_actual_features(nb,kwargs,source)
    pins['actual_api_boundary']=preengine_probe(nb,kwargs,pins,ne,original,a.out)
    write(a.out/'preflight.json',pins)
    if a.preflight:print(json.dumps(dict(status='ENGINE_FREE_PREFLIGHT_PASS',engine_constructions=0,harness_sha256=sha(__file__),zero_tp_netting=False)));return
    if a.claim is None:raise ValueError('ROOT_CLAIM_REQUIRED')
    c=json.loads(a.claim.read_text())
    if D(str(c.get('initial_active_seed','10000')))!=a.seed:raise ValueError('ROOT_CLAIM_SEED_MISMATCH')
    claim=legacy.consume_claim(a.claim,a.case,source,harness_file=__file__)
    def cap(*_):raise TimeoutError('WALL_CAP_90_MIN_NO_DD_STOP')
    signal.signal(signal.SIGALRM,cap);signal.alarm(5400);engines=[];t=time.monotonic()
    def one(*args,**kw):
        if engines:raise RuntimeError('ONE_ENGINE_ONLY')
        engines.append(None) # reserve before native constructor, including failure
        e=original(*args,**kw);engines[0]=e;return e
    ne.BacktestEngine=one
    try:
        result=nb.run_native_diagnostic(**kwargs);write(a.out/'native-report.json',result)
        obs=result['coherent_native_observer'];cash=result['native_cash_reconciliation'];cov=coverage(result,a.out);write(a.out/'actual-feed-coverage.json',cov)
        checks=dict(one_engine=len(engines)==1,full_feed=result['streaming']['processed_rows_per_source']==1051200,full_24months=cov['full'],coherent_end=int(obs['end_exclusive_ns'])==1788220800000000000,settled_receipts=int(obs['settled_receipts'])==1051199,observer=obs['status']=='PASS',native_cash=cash['status']=='EXACT' and D(cash['actual_native_cash_transitions']['exact_bridge'])==0,USDC=result['config']['accounting_currency']=='USDC',DP_off=result['config']['deposit_protection']=='DISABLED_CLEAN_EXECUTION_DIAGNOSTIC_ONLY',terminal_flat=result['terminal_open_positions']==0,terminal_orders=obs['status']=='PASS' and not any('ORDERS_NONTERMINAL' in x for x in obs['unknown']))
        fail=bool(result['liquidation_count']);qualified=all(checks.values())
        receipt=dict(status=('ACCOUNTING_QUALIFIED_ECONOMIC_NO_GO' if fail else 'COMPLETE_ENGINEERING_ACCOUNTING') if qualified else 'ACCOUNTING_NOT_QUALIFIED',checks=checks,economic_failure=fail,engine_constructions=len(engines),elapsed_seconds=time.monotonic()-t,claim_sha256=claim,report_sha256=sha(a.out/'native-report.json'),full_TOTAL=result['terminal_total'] if qualified else None)
        write(a.out/'process-result.json',receipt)
        if not qualified:raise ValueError('FULL_ACCOUNTING_CHECK_FAILED')
    except BaseException as exc:
        write(a.out/'failure.json',dict(error=type(exc).__name__,message=str(exc),engine_constructions=len(engines),elapsed_seconds=time.monotonic()-t,full_TOTAL=None));raise
    finally:signal.alarm(0);ne.BacktestEngine=original
if __name__=='__main__':main()
