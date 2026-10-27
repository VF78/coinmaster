"""Focused prefix wrapper/observer proof. Install engine tripwire before import."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from unittest.mock import patch
from decimal import Decimal as D
import ast,gzip,json,subprocess,sys
import prefix_common as c
from prefix_observer import PrefixEvidence,PrefixCoverageModule,recording_engine_factory,observed_strategy_type
from nautilus_trader.cache.cache import Cache
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.test_kit.stubs.execution import TestExecStubs
from nautilus_trader.test_kit.stubs.events import TestEventStubs
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP


def rejected(fn):
    try:fn()
    except (AssertionError,ValueError,KeyError):return
    raise AssertionError('EXPECTED_REJECTION')


def proof():
    root=Path(__file__).resolve().parents[2];checks=[]
    g=dict(label='P0',data_root='/tmp/known-not-the-stock-root',namespace='/tmp/method-a-prefix-unit-namespace')
    a,args,payload,full=c.build_qualified_args(g)
    b,_,_,_=c.build_qualified_args(dict(g,label='P1'))
    assert {k for k in a if a[k]!=b[k]}=={'artifact_label','research_method_a_tp'}
    assert args['research_method_a_observer'] is True and args['research_paired_policy'] is False
    assert args['candidate'].sol_overlay_enabled and args['research_btc_split_discount']=='0.0025'
    assert args['trading_start_ms']==c.START and args['trading_end_ms']==c.END
    assert c.stock_venue_proof(root,args)['bar_execution'] is True
    assert c.stock_venue_proof(root,args)['liquidity_consumption'] is False
    checks.append('ce7_P0_P1_exact_kwargs_types_JSON_defaults_and_stock_venue_false_true')
    rejected(lambda:c.build_qualified_args(dict(g,label='P3')))
    rejected(lambda:c.verify_inputs(dict(g,input_files=[])))
    checks.append('unregistered_P3_and_wrong_data_root_actual_nine_paths_failclosed')
    with TemporaryDirectory(prefix='method-a-prefix-pure-') as directory:
        d=Path(directory)
        claim=dict(attempt_id='12345678-1234-4234-8234-123456789abc',category='prefix',label='P0',case='P0_PREFIX',status='STARTED',
            source_commit=c.SOURCE,namespace=g['namespace'],owner_approval_sha256=c.OWNER,source_seal_sha256='f'*64,
            recipe_sha256='a'*64,native_config_sha256='b'*64,native_input_sha256='c'*64,common_economic_identity_sha256='d'*64)
        ledger=dict(total_max=17,physical_started=2,active=1,categories=dict(prefix=dict(max=6)),attempts=[claim])
        path=d/'ledger.json';c.write(path,ledger)
        gate=dict(g,source_seal_sha256='f'*64,recipe_sha256='a'*64,native_config_sha256='b'*64,native_input_sha256='c'*64,common_economic_identity_sha256='d'*64)
        assert c.verify_claim(gate,path,claim['attempt_id'])==claim
        rejected(lambda:c.verify_claim(dict(gate,label='P1'),path,claim['attempt_id']))
        ledger['total_max']=18;c.write(path,ledger);rejected(lambda:c.verify_claim(gate,path,claim['attempt_id']))
        checks.append('unique_started_UUID_exact_flat_unified17_prefix6_label_source_namespace_pins')
        # Real public native Cache/Order/event classes, UNIT inputs only.
        cache=Cache();cache.add_instrument(BTC_PERP);cache.add_instrument(SOL_PERP)
        order=TestExecStubs.limit_order(instrument=BTC_PERP,order_side=OrderSide.SELL,quantity=BTC_PERP.make_qty(D('.212')),
            price=BTC_PERP.make_price(D(101)),reduce_only=True)
        cache.add_order(order);accepted=TestEventStubs.order_accepted(order,ts_event=2);order.apply(accepted);cache.update_order(order)
        intent=NS(id='UNIT-INTENT',episode_id='UNIT-PARENT',action='BTC_REDUCE',level=0,reason='BTC_TP1')
        strategy=NS(cache=cache,config=NS(btc_id=BTC_PERP.id),_domain=NS(episode=None),_ma_plans={},_ma_owners={},_ma_commands={},
            _pending_by_order={str(order.client_order_id):intent},_queued_intents=[])
        evidence=PrefixEvidence(d/'profile.jsonl.gz');evidence.bind(strategy)
        module=PrefixCoverageModule(evidence)
        q=QuoteTick(BTC_PERP.id,BTC_PERP.make_price(D(100)),BTC_PERP.make_price(D(100)),BTC_PERP.make_qty(D(1000)),BTC_PERP.make_qty(D(1000)),3,3)
        module.pre_process(q);module.pre_process(q);evidence.callback('UNIT_NATIVE_CLASS_EVENT',accepted)
        # Thin constructor/registration spy, never a native engine.
        calls=[]
        class EngineSpy:
            def __init__(self,*aa,**kk):calls.append(('constructor',aa,kk))
            def add_venue(self,*aa,**kk):calls.append(('venue',aa,kk));return 'STOCK_RETURN'
            def add_strategy(self,value):calls.append(('strategy',value));return 'STRATEGY_RETURN'
        factory=recording_engine_factory(EngineSpy,evidence);proxy=factory('UNCHANGED_CONFIG')
        old_modules=[NS(name='funding'),NS(name='tier'),NS(name='coherent')]
        kwargs=dict(venue='UNIT',liquidity_consumption=False,bar_execution=True,modules=old_modules,default_leverage=D(1))
        assert proxy.add_venue(**kwargs)=='STOCK_RETURN'
        assert kwargs['modules']==old_modules and len(kwargs['modules'])==3
        actual=calls[-1][2]
        assert actual['modules'][:3]==old_modules and isinstance(actual['modules'][-1],PrefixCoverageModule)
        assert {k:v for k,v in actual.items() if k!='modules'}=={k:v for k,v in kwargs.items() if k!='modules'}
        assert proxy.add_strategy(strategy)=='STRATEGY_RETURN'
        with patch.object(Path,'read_bytes',side_effect=AssertionError('WHOLE_STREAM_READ_FORBIDDEN')):
            profile=evidence.close()
        assert profile['native_event_UUID_frames']==1 and not hasattr(evidence,'native_event_ids')
        rows=[json.loads(line) for line in gzip.open(d/'profile.jsonl.gz','rt')]
        assert rows[0]['phase']=='BEFORE_NATIVE_MATCHING_INPUT' and rows[1]['state_ref_sha256']==rows[0]['state_sha256']
        assert rows[2]['native_event_id']==str(accepted.id) and rows[2]['native_order']['native_history'][-1]['id']==str(accepted.id)
        assert rows[0]['state']['active_orders'][str(order.client_order_id)]['quantity']=='0.212'
        assert profile['actual_venue_registrations'][0]['liquidity_consumption'] is False
        checks.append('real_Cache_Order_history_UUID_before_matching_module_compact_SHA_stream')
        checks.append('thin_engine_factory_spy_constructor1_same_kwargs_plus_readonly_module_no_native_engine')
        closed_position_capture_proof(d,cache,strategy)
        checks.append('public_native_PositionClosed_realized_commissions_and_fill_history_JSON_getters')
        evidence=PrefixEvidence(d/'delegate.jsonl.gz');base_calls=[]
        class Base:
            def on_quote_tick(self,event):base_calls.append(event);return 'BASE_RESULT'
        observed=observed_strategy_type(Base,evidence);instance=observed()
        assert instance.on_quote_tick(q)=='BASE_RESULT' and base_calls==[q]
        evidence.close();checks.append('strategy_callback_delegates_once_preserves_return_labels_after_cache_mutation')
    subprocess.run(['git','-C',str(root),'diff','--exit-code',c.SOURCE,'--','runtime'],check=True,capture_output=True)
    checks.append('all_runtime_product_and_money_bytes_exact_a4dd_unchanged')
    checks.extend(correction_proof())
    for path in Path(__file__).parent.glob('prefix_*.py'):ast.parse(path.read_text())
    return dict(status='PREFIX_WRAPPER_ENGINE_FREE_PASS',engine_constructors=0,checks=checks,
        stock_loader_actual_historical_preflight='REQUIRED_ON_MAC_BEFORE_ANY_PREFIX_GO',
        financial_outcome='NOT_RUN_NOT_PREPROVEN',source_commit=c.SOURCE)


def correction_proof():
    from dataclasses import replace
    checks=[]
    with TemporaryDirectory(prefix='method-a-correction-unit-') as directory:
        d=Path(directory);data=d/'data';physical=d/'physical';source=d/'frozen-source'
        (data/'bybit-1m').mkdir(parents=True);(data/'normalized').mkdir();physical.mkdir()
        required=[data/'bybit-1m/manifest.json']
        required[0].write_text('{}')
        for asset in ('BTCUSDT','SOLUSDT'):
            for kind in ('daily','execution-1m','mark-1m','funding'):
                actual=physical/('bybit-'+asset+'-'+kind+'.parquet');actual.write_text('UNIT_DATA_'+asset+kind)
                logical=data/'normalized'/actual.name;logical.symlink_to(actual);required.append(logical)
        profiles=[]
        for name in ('runtime/var/venue-manifest.json','runtime/var/raw/venues/bybit-BTCUSDT-risk-limit.json','runtime/var/raw/venues/bybit-SOLUSDT-risk-limit.json'):
            path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{}');profiles.append(path)
        feed=d/'feed.csv';feed.write_text('UNIT_FEED_NOT_A_TRADING_RESULT')
        refs=[dict(path=str(path.resolve()),sha256=c.sha(path)) for path in required+profiles]
        g=dict(label='P1',data_root=str(data),source_root=str(source),namespace=str(d/'P1'),input_files=refs,warmed_feed=dict(path=str(feed),sha256=c.sha(feed)))
        with patch.object(c,'WARMED',c.sha(feed)):
            inputs=c.verify_inputs(g)
            assert [row['relative_path'] for row in inputs['identity']['files']]==[str(path.relative_to(data)) for path in required]
            _,args,_,_=c.build_qualified_args(g);identity=c.common_economic_identity(g,args,inputs)
            _,p0,_,_=c.build_qualified_args(dict(g,label='P0',namespace=str(d/'P0')))
            assert c.common_economic_identity(g,p0,inputs)==identity
            bad=dict(args,execution_policy=replace(args['execution_policy'],fee_multiplier='2'))
            assert c.common_economic_identity(g,bad,inputs)!=identity
            changed=dict(inputs,native_input_sha256='f'*64)
            assert c.common_economic_identity(g,args,changed)!=identity
            changed=dict(inputs,public_profile_sha256=dict(inputs['public_profile_sha256'],extra='changed'))
            assert c.common_economic_identity(g,args,changed)!=identity
            live=d/'unused-live.json';live.write_text('{}')
            replaced=[dict(ref,path=str(live)) if Path(ref['path'])==profiles[0] else ref for ref in refs]
            rejected(lambda:c.verify_inputs(dict(g,input_files=replaced)))
            g['native_input_sha256']=inputs['native_input_sha256'];g['common_economic_identity_sha256']=identity
            chain_proof(d,g,inputs)
        checks.append('existing_normalized_symlinks_resolve_for_pins_keep_nine_logical_IDs')
        checks.append('actual_frozen_three_profiles_required_unused_live_alias_rejected')
        checks.append('P0_P1_only_TP_and_artifact_delta_fee_input_profile_drift_rejected')
        checks.append('full_prior_P0_report_manifest_supervisor_exit_role_chain_positive_and_negative')
    checks.append('observer_stream_hash_uses_chunks_no_whole_read_no_whole_run_UUID_set')
    return checks


def chain_proof(d,g,inputs):
    """Temporary metadata validation fixture; never a financial/native outcome."""
    from copy import deepcopy
    ns=d/'P0';result=ns/'result';result.mkdir(parents=True)
    ledger_path=d/'current-ledger.json';snapshot=d/'ledger-snapshot.json'
    attempt='12345678-1234-4234-8234-123456789abc'
    values=dict(source_seal_sha256='f'*64,native_config_sha256='b'*64,native_input_sha256=g['native_input_sha256'],recipe_sha256='a'*64,
        common_economic_identity_sha256=g['common_economic_identity_sha256'],kwargs_sha256='e'*64,full_bound_kwargs_sha256='c'*64)
    freeze_path=d/'prior-freeze.json';c.write(freeze_path,dict(values,source_commit=c.SOURCE,label='P0',namespace=str(ns)))
    link=dict(values,attempt_id=attempt,variant='P0',label='P0',category='prefix',source_commit=c.SOURCE,
        ledger=str(ledger_path),freeze_sha256=c.sha(freeze_path),public_profile_sha256=inputs['public_profile_sha256'],worker_pid=1234)
    for path in (result/'method-a-P0-orders.csv',result/'method-a-P0-funding.sqlite',result/'coherent-native-events.jsonl.gz',
                 result/'method-a-native-protection.jsonl.gz',result/'minute-native-risk.csv.gz',result/'method-a-P0-raw-native.json'):
        path.write_text('UNIT_BINDING_BYTES_NOT_A_NATIVE_RESULT')
    profile=dict(path=str(result/'method-a-native-protection.jsonl.gz'),sha256=c.sha(result/'method-a-native-protection.jsonl.gz'))
    c.write(ns/'native-observer-profile.json',profile)
    report_path=result/'P0.json';report=dict(unit_fixture_not_native=True,physical_prefix_attempt=link,method_a_execution_profile=profile,
        config={'unit':'metadata only'},config_hash='ORIGINAL_RAW_HASH',method_a_effective_config_sha256=c.canonical({'unit':'metadata only'}))
    c.write(report_path,report);report_sha=c.sha(report_path)
    extra_paths=dict(protection_profile=result/'method-a-native-protection.jsonl.gz',minute_risk=result/'minute-native-risk.csv.gz',
        observer_profile=ns/'native-observer-profile.json',raw_native=result/'method-a-P0-raw-native.json')
    extras=[dict(role=role,path=str(path),sha256=c.sha(path)) for role,path in extra_paths.items()]
    roles=c.artifacts(ns,'P0',report_path)
    exit_path=ns/'actual-exit.json';exit_value=dict(schema='METHOD_A_PREFIX_ACTUAL_OS_EXIT_V1',authority='ROOT_OBSERVED_CHILD_POPEN_WAIT',
        attempt_id=attempt,variant='P0',source_commit=c.SOURCE,worker_pid=1234,actual_returncode=0,freeze_sha256=link['freeze_sha256'])
    c.write(exit_path,exit_value)
    base_manifest=dict(status='NATIVE_PROCESS_EXPORTED_ACTUAL_OS_ZERO',attempt_id=attempt,variant='P0',source_commit=c.SOURCE,
        actual_returncode=0,physical_identity=link,freeze_sha256=link['freeze_sha256'],worker_pid=1234,report=str(report_path),report_sha256=report_sha,
        artifacts=roles,extra_evidence=extras,source_config_hash_preserved=report['config_hash'],effective_config_sha256=report['method_a_effective_config_sha256'],
        actual_exit_receipt=dict(path=str(exit_path),sha256=c.sha(exit_path)))
    manifest_path=ns/'completion-manifest.json';supervisor_path=ns/'supervisor.json';risk_path=ns/'risk.json';qualification_path=ns/'qualification.json'
    def seal(kind=None):
        manifest=deepcopy(base_manifest)
        supervisor=dict(ledger_status='COMPLETED',attempt_id=attempt,variant='P0',source_commit=c.SOURCE,actual_returncode=0,
            physical_identity=deepcopy(link),freeze_sha256=link['freeze_sha256'],worker_pid=1234,report=str(report_path),report_sha256=report_sha,
            completion_manifest=str(manifest_path),actual_exit_receipt=manifest['actual_exit_receipt'])
        if kind=='manifest_report':manifest['report_sha256']='0'*64
        if kind=='supervisor_physical':supervisor['physical_identity']['native_input_sha256']='0'*64
        if kind=='role_hash':manifest['artifacts'][3]['sha256']='0'*64
        c.write(manifest_path,manifest);supervisor['completion_manifest_sha256']=c.sha(manifest_path);c.write(supervisor_path,supervisor)
        detail=dict(actual_returncode=0,report=str(report_path),report_sha256=report_sha,physical_identity=link,
            completion_manifest=str(manifest_path),completion_manifest_sha256=c.sha(manifest_path),supervisor=str(supervisor_path),supervisor_sha256=c.sha(supervisor_path))
        row=dict(values,attempt_id=attempt,status='COMPLETED',category='prefix',label='P0',source_commit=c.SOURCE,namespace=str(ns),pid=1234,detail=detail)
        c.write(ledger_path,{'attempts':[row]});c.write(snapshot,{'attempts':[row]})
        receipt=dict(schema='CM_METHOD_A_FINANCIAL_QUALIFICATION_V1',label='P0',source_commit=c.SOURCE,metric_contract_sha256=c.METRIC,
            decision='FINANCIAL_ACCEPTED_CONTROL',qualification='FINANCIALLY_QUALIFIED',accounting_qualified=True,actual_returncode=0,
            financial_gates=dict({key:'PASS' for key in c.COMMON_GATES},native_3TP='NOT_APPLICABLE_LEGACY_CONTROL'),
            native_input_sha256=g['native_input_sha256'],common_economic_identity_sha256=g['common_economic_identity_sha256'],public_profile_sha256=inputs['public_profile_sha256'],
            native_ledger_path=str(ledger_path),ledger_snapshot=dict(path=str(snapshot),sha256=c.sha(snapshot)),attempt_id=attempt,
            completed_attempt_sha256=c.canonical(row),report_path=str(report_path),report_sha256=report_sha,physical_identity=link,
            freeze=dict(path=str(freeze_path),sha256=c.sha(freeze_path)),completion_manifest_path=str(manifest_path),completion_manifest_sha256=c.sha(manifest_path),
            supervisor_path=str(supervisor_path),supervisor_sha256=c.sha(supervisor_path))
        binding={key:receipt[key] for key in ('attempt_id','label','source_commit','report_path','report_sha256','completed_attempt_sha256',
            'completion_manifest_path','completion_manifest_sha256','supervisor_path','supervisor_sha256')}
        binding.update(physical_identity=link,artifact_roles={entry['role']:entry for entry in roles})
        c.write(risk_path,dict(accounting_qualified=True,qualification='VALID_ACCOUNTED_PREFIX',physical_binding=binding))
        receipt.update(risk_analysis_path=str(risk_path),risk_analysis_sha256=c.sha(risk_path))
        if kind=='receipt_input':receipt['native_input_sha256']='0'*64
        c.write(qualification_path,receipt)
        return dict(g,previous_financial_qualification=dict(path=str(qualification_path),sha256=c.sha(qualification_path)))
    valid=seal();c.verify_prior_financial(valid,ledger_path)
    for kind in ('manifest_report','supervisor_physical','role_hash','receipt_input'):
        bad=seal(kind);rejected(lambda:c.verify_prior_financial(bad,ledger_path))
    good=seal();exit_value['actual_returncode']=1;c.write(exit_path,exit_value)
    rejected(lambda:c.verify_prior_financial(good,ledger_path))


def closed_position_capture_proof(d,cache,strategy):
    from nautilus_trader.model.position import Position
    from nautilus_trader.model.identifiers import PositionId,TradeId
    from nautilus_trader.model.enums import OmsType
    from nautilus_trader.model.objects import Money
    buy=TestExecStubs.market_order(instrument=BTC_PERP,order_side=OrderSide.BUY,quantity=BTC_PERP.make_qty(D(1)))
    entry=TestEventStubs.order_filled(buy,BTC_PERP,position_id=PositionId('UNIT-CLOSED-POSITION'),trade_id=TradeId('UNIT-ENTRY'),
        last_qty=BTC_PERP.make_qty(D(1)),last_px=BTC_PERP.make_price(D(100)),commission=Money(D('.01'),BTC_PERP.quote_currency),ts_event=4)
    position=Position(BTC_PERP,entry);cache.add_position(position,OmsType.NETTING)
    sell=TestExecStubs.market_order(instrument=BTC_PERP,order_side=OrderSide.SELL,quantity=BTC_PERP.make_qty(D(1)))
    exit_=TestEventStubs.order_filled(sell,BTC_PERP,position_id=position.id,trade_id=TradeId('UNIT-EXIT'),
        last_qty=BTC_PERP.make_qty(D(1)),last_px=BTC_PERP.make_price(D(101)),commission=Money(D('.02'),BTC_PERP.quote_currency),ts_event=5)
    position.apply(exit_);cache.update_position(position)
    event=TestEventStubs.position_closed(position)
    evidence=PrefixEvidence(d/'closed-position.jsonl.gz');evidence.bind(strategy)
    evidence.callback('UNIT_NATIVE_POSITION_CLOSED',event);evidence.close()
    row=json.loads(gzip.open(d/'closed-position.jsonl.gz','rt').readline())
    captured=row['native_position']
    assert row['native_event_type']=='PositionClosed' and row['native_event_id']==str(event.id)
    assert row['native_position_closed_event']['realized_pnl']['amount']==str(event.realized_pnl.as_decimal())
    assert captured['is_closed'] is True and captured['position_id']==str(position.id)
    assert captured['realized_pnl']['amount']==str(position.realized_pnl.as_decimal())
    assert captured['commissions']==[dict(amount=str(value.as_decimal()),currency=str(value.currency)) for value in position.commissions()]
    assert [fill['trade_id'] for fill in captured['native_fill_history']]==['UNIT-ENTRY','UNIT-EXIT']
    assert captured['realized_fee_convention'].endswith('DO_NOT_SUBTRACT_AGAIN')
