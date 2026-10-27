"""Focused V2 observer method-unit proof. No matching, money result or native run."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
from decimal import Decimal as D
from dataclasses import asdict
from datetime import datetime,timezone,timedelta
import ast,copy,gzip,hashlib,importlib,json,subprocess

def proof():
    engine=importlib.import_module('nautilus_trader.backtest.engine');original_engine=engine.BacktestEngine;attempts=[]
    def blocked(*a,**k):
        attempts.append('BacktestEngine')
        raise AssertionError('NATIVE_ENGINE_CONSTRUCTOR_FORBIDDEN')
    engine.BacktestEngine=blocked
    try:
        from prefix_observer import PrefixEvidence,observed_strategy_type
        from coinmaster.domain.wave_overlay import Candidate,Episode,Intent,WaveOverlayState,DailyBar,Features
        from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
        from nautilus_trader.cache.cache import Cache
        from nautilus_trader.model.data import Bar,BarType,QuoteTick
        from nautilus_trader.model.objects import Quantity
        from nautilus_trader.model.enums import OrderSide
        from nautilus_trader.model.identifiers import ClientOrderId
        from nautilus_trader.test_kit.stubs.execution import TestExecStubs
        from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
        checks=[]
        class Base:
            def _record_submission(self,*args,**kwargs):
                self.original_calls+=1
                return WaveOverlayStrategy._record_submission(self,*args,**kwargs)
            def _ma_enabled(self):return False
            def _split_tp_ioc_eligible(self,intent):return False
        def setup(evidence):
            cls=observed_strategy_type(Base,evidence);s=cls()
            s.original_calls=0;s.sink_calls=0;s.sink_result=True;s.sink_error=None
            def sink(**kwargs):
                s.sink_calls+=1
                if s.sink_error is not None:raise s.sink_error
                return s.sink_result
            s.config=NS(btc_id=BTC_PERP.id,submission_sink=sink,research_v0_selective_lifecycle_repairs=True)
            s._order_audit={};s.cache=Cache();s.cache.add_instrument(BTC_PERP);s.cache.add_instrument(SOL_PERP)
            s._candidate=Candidate(sol_size_multipliers_h=(1.75,2.625,3.5),sol_late_entry_after_tp=True)
            s._domain=WaveOverlayState(s._candidate);ep=Episode('UNIT-PARENT',1,10000,1,h=100,wave_levels=(0,.01,.02))
            ep.btc_entry_qty_exact=D('.5');ep.btc_initial_qty=.5;ep.btc_net_planned_qty=1.;ep.btc_reference_qty=1.
            ep.btc_entry_vwap=10000.;ep.sol_rights={0};ep.sol_right_fraction={0:.5};ep.sol_right_decision_index={0:0}
            ep.sol_add_filled_notional={0:1.25};ep.sol_ownership_transfer_credit={0:2.5};ep.sol_risk_retired_notional={0:3.75}
            ep.btc_deferred_right_touched=True;ep.btc_deferred_right_reference_price=D('10000.1');ep.btc_omitted_zero_levels={0}
            ep.btc_reference_target_lots={0:212,1:212,2:576};ep.btc_tp_target_lots={0:0,1:250,2:250};ep.btc_tp_filled_lots={1:10}
            s._domain.episode=ep
            intent=Intent('UNIT-INTENT',ep.id,'SOL_ADD',0,-1,requested_notional=10.,decision_index=0,reason='UNIT_ONLY')
            ep.pending[intent.id]=intent
            order=TestExecStubs.market_order(instrument=SOL_PERP,order_side=OrderSide.SELL,quantity=SOL_PERP.make_qty(D('.1')),client_order_id=ClientOrderId('UNIT-SOL'))
            s._pending_by_order={str(order.client_order_id):intent};s._decision_index_by_order={str(order.client_order_id):0}
            s._ma_plans={};s._ma_owners={};s._ma_commands={};s._queued_intents=[(intent,None,0)];s._accepted_reductions={}
            when=datetime(2024,9,2,tzinfo=timezone.utc);ns=int(when.timestamp()*1_000_000_000)
            s._bars=[DailyBar(when-timedelta(days=1),when,when,10000.,10000.,100.)]
            s._last_accepted_session=ns;s._latest_seen_session=ns
            def bar(inst,px):
                price=inst.make_price(D(px))
                return Bar(BarType.from_str(str(inst.id)+'-1-DAY-LAST-EXTERNAL'),price,price,price,price,Quantity.from_int(1),ns,ns)
            s._current_btc=bar(BTC_PERP,'10000');s._current_sol=bar(SOL_PERP,'100')
            s._current_signals=[Features(0,1,1.,.1,0.,.05,2.)]
            q=QuoteTick(SOL_PERP.id,SOL_PERP.make_price(D('100')),SOL_PERP.make_price(D('100.1')),SOL_PERP.make_qty(D('1')),SOL_PERP.make_qty(D('1')),ns+1,ns+1)
            s.cache.add_quote_tick(q);evidence.bind(s)
            return s,ep,intent,order
        def call(s,i,o,action=None):
            return s._record_submission(o,i.id,i.episode_id,action or i.action,i.reason,i.level)
        with TemporaryDirectory(prefix='method-a-observer-v2-pure-') as directory:
            d=Path(directory);e=PrefixEvidence(d/'actual-object-unit.gz');s,ep,i,o=setup(e)
            before=copy.deepcopy(asdict(ep));order_events=[str(x.id) for x in o.events]
            assert call(s,i,o) is True and (s.original_calls,s.sink_calls)==(1,1)
            assert asdict(ep)==before and [str(x.id) for x in o.events]==order_events
            assert s.cache.order(o.client_order_id) is None and not s.cache.orders_open() and not s.cache.positions_open()
            assert e.admission_attempts==e.admission_recorded==1 and e.admission_errors==0
            meta=e.close();rows=[json.loads(x) for x in gzip.open(e.path,'rt')]
            assert len(rows)==1 and rows[0]['phase']=='SOL_ADD_PRE_NATIVE_TRANSPORT_AFTER_CHECKPOINT'
            a=rows[0]['admission'];v=a['episode'];state=rows[0]['state']
            assert a['checkpoint_result'] is True and a['initialized_order_is_ACK_or_fill'] is False
            assert a['native_initialized_order']['status']=='INITIALIZED' and not a['current_native_cache_order_present']
            assert v['h_at_SOL_ADD_admission']==100 and v['source_float_hex']['h']==float(100).hex()
            assert v['sol_add_filled_notional_at_SOL_ADD_admission']=={'0':1.25}
            assert v['sol_ownership_transfer_credit']=={'0':2.5} and v['sol_risk_retired_notional']=={'0':3.75}
            assert v['btc_deferred_right_touched'] is True and v['sol_right_decision_index']=={'0':0}
            sessions=a['sessions'];assert sessions['last_accepted_session']==sessions['current_BTC_SOL_signal_sessions']['BTC']['ts_event']==sessions['current_BTC_SOL_signal_sessions']['SOL']['ts_event']
            assert a['pending_intent']['requested_notional']==10. and state['queued'][0]['requested_notional']==10.
            assert meta['legacy_SOL_admission_capture']['error_count']==0 and meta['sha256']==hashlib.sha256(e.path.read_bytes()).hexdigest()
            checks+=['actual_Episode_Cache_initialized_Order_readonly_snapshot_and_six_facts','original_checkpoint_true_once_with_actual_source_method','JSON_roundtrip_hex_maps_intent_sessions_and_stream_hash']
            e=PrefixEvidence(d/'false-unit.gz');s,ep,i,o=setup(e);s.sink_result=False
            assert call(s,i,o) is False and (s.original_calls,s.sink_calls)==(1,1) and e.admission_attempts==0
            e.close()
            e=PrefixEvidence(d/'exception-unit.gz');s,ep,i,o=setup(e);error=RuntimeError('UNIT_ORIGINAL');s.sink_error=error
            try:call(s,i,o)
            except RuntimeError as actual:assert actual is error
            else:raise AssertionError('ORIGINAL_EXCEPTION_SWALLOWED')
            assert (s.original_calls,s.sink_calls)==(1,1) and e.admission_attempts==0
            e.close()
            checks.append('false_and_original_exception_preserved_once_no_admitted_frame')
            e=PrefixEvidence(d/'nonSOL-unit.gz');s,ep,i,o=setup(e)
            assert call(s,i,o,'BTC_REDUCE') is True and e.admission_attempts==0
            e.close();checks.append('nonSOL_checkpoint_route_unchanged')
            e=PrefixEvidence(d/'capture-failure-unit.gz');s,ep,i,o=setup(e);before=copy.deepcopy(asdict(ep))
            def unavailable(*a,**k):raise TypeError('UNIT_SERIALIZATION_FAILURE')
            e.record=unavailable
            assert call(s,i,o) is True and (s.original_calls,s.sink_calls)==(1,1) and asdict(ep)==before
            assert e.admission_errors==1 and e.admission_recorded==0
            meta=e.close();assert meta['legacy_SOL_admission_capture']['requires_financial_UNKNOWN_if_errors'] is True
            checks.append('capture_serialization_failure_does_not_change_original_result_or_domain')
            # The only source call between checkpoint true and native submit is inert for SOL_ADD.
            accepted=copy.deepcopy(s._accepted_reductions)
            WaveOverlayStrategy._own_accepted_reduction(s,i,D('.1'))
            assert s._accepted_reductions==accepted and asdict(ep)==before
            checks.append('actual_source_post_checkpoint_SOL_ADD_bridge_nonmutating')
        root=Path(__file__).resolve().parents[2]
        subprocess.run(['git','diff','--exit-code','a4dd4694284192dc7fe063495ac3e727efff4b38','--','runtime'],cwd=root,check=True,capture_output=True)
        for name in ('prefix_common.py','prefix_worker.py','prefix_preflight.py','test_prefix_wrappers_pure.py'):
            expected=subprocess.check_output(['git','show','334bc5a56bef36e981022c1fd2d22dc9ffd4c74f:reports/method-a-verification-20261027/'+name],cwd=root)
            assert (Path(__file__).parent/name).read_bytes()==expected
        checks.append('all_runtime_bytes_a4_other334_wrappers_unchanged')
        assert not attempts
        return dict(status='METHOD_A_OBSERVER_V2_FOCUSED_PURE_PASS',checks=checks,engine_constructors=0,
            engine_tripwire_attempts=attempts,matching_runs=0,unit_states_are_not_actual_native_events=True,
            intent_origin='Immutable actual Intent is copied; global creation_to_submission_nonmutation_NOT_CLAIMED; actual stream proof required',
            runtime_source='a4dd4694284192dc7fe063495ac3e727efff4b38')
    finally:engine.BacktestEngine=original_engine
