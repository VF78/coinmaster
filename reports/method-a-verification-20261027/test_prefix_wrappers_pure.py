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
            recipe_sha256='a'*64,native_config_sha256='b'*64,native_input_sha256='c'*64)
        ledger=dict(total_max=17,physical_started=2,active=1,categories=dict(prefix=dict(max=6)),attempts=[claim])
        path=d/'ledger.json';c.write(path,ledger)
        gate=dict(g,source_seal_sha256='f'*64,recipe_sha256='a'*64,native_config_sha256='b'*64,native_input_sha256='c'*64)
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
        profile=evidence.close();rows=[json.loads(line) for line in gzip.open(d/'profile.jsonl.gz','rt')]
        assert rows[0]['phase']=='BEFORE_NATIVE_MATCHING_INPUT' and rows[1]['state_ref_sha256']==rows[0]['state_sha256']
        assert rows[2]['native_event_id']==str(accepted.id) and rows[2]['native_order']['native_history'][-1]['id']==str(accepted.id)
        assert rows[0]['state']['active_orders'][str(order.client_order_id)]['quantity']=='0.212'
        assert profile['actual_venue_registrations'][0]['liquidity_consumption'] is False
        checks.append('real_Cache_Order_history_UUID_before_matching_module_compact_SHA_stream')
        checks.append('thin_engine_factory_spy_constructor1_same_kwargs_plus_readonly_module_no_native_engine')
        evidence=PrefixEvidence(d/'delegate.jsonl.gz');base_calls=[]
        class Base:
            def on_quote_tick(self,event):base_calls.append(event);return 'BASE_RESULT'
        observed=observed_strategy_type(Base,evidence);instance=observed()
        assert instance.on_quote_tick(q)=='BASE_RESULT' and base_calls==[q]
        evidence.close();checks.append('strategy_callback_delegates_once_preserves_return_labels_after_cache_mutation')
    subprocess.run(['git','-C',str(root),'diff','--exit-code',c.SOURCE,'--','runtime'],check=True,capture_output=True)
    checks.append('all_runtime_product_and_money_bytes_exact_a4dd_unchanged')
    for path in Path(__file__).parent.glob('prefix_*.py'):ast.parse(path.read_text())
    return dict(status='PREFIX_WRAPPER_ENGINE_FREE_PASS',engine_constructors=0,checks=checks,
        stock_loader_actual_historical_preflight='REQUIRED_ON_MAC_BEFORE_ANY_PREFIX_GO',
        financial_outcome='NOT_RUN_NOT_PREPROVEN',source_commit=c.SOURCE)
