"""E04: one native engine,18 synthetic hours, current-child/continuity proof.

Import is constructor-free. TESTONLY order shapes/faults never change normal
admission or account money. Physical execution requires separate root GO.
"""
from collections import deque
from dataclasses import asdict
from decimal import Decimal as D
import json
from pathlib import Path
from coinmaster.strategy.cm2_policy import Config, Features, State, PairedHourBuilder, HOUR_NS, MINUTE_NS

FIXTURE_ID='cm2-current-child-native-v2'
START_NS=1725148800000000000
END_NS=START_NS+18*HOUR_NS
CAPACITY_NOTIONAL=D(40000)
FUNDING_EXPECTED=(D('-.495'),D('.48'))
QUEUED_LATENCY_NS=240_000_000_000
QUEUE_PULSE_MINUTES=(1026,1034)
TIMING_MODEL_ID='CM2_E04_SYNTHETIC_ZERO_BASE_240S_INSERT_ONLY'
DENIED_QUANTITY_TEXT='0.001'


def fixed_feature(hour):
    """Finalized causal H1 script; H1/H10 intentionally deliver NO feature."""
    rows={0:(1010,1005,990,-2,-.02),2:(990,1100,900,-2,-.02),
        3:(990,1100,900,-2,-.02),4:(990,1100,900,-2,-.02),
        5:(1070,1100,900,-2,-.02),6:(1070,1100,900,-2,-.02),
        7:(1100,1090,900,0,.01),8:(950,1100,900,0,.01),
        9:(940,1000,945,2,.02),11:(960,1100,900,2,.02),
        12:(960,1100,900,2,.02),13:(960,1100,900,2,.02),
        14:(880,1100,850,2,.02),15:(880,1100,850,2,.02),
        16:(850,1100,860,0,-.01),17:(980,1100,850,0,-.01)}
    close,high,low,z,ret=rows[hour];t=START_NS+hour*HOUR_NS
    return Features(t,t,True,close=close,channel_high=high,channel_low=low,atr=10,
        beta=1,beta_guard=1,rho=1,residual_z=z,btc_return6=ret,
        common_loss=.02,residual_loss=.001,hedge_valid=True)


def minute_prices(minute):
    if minute<3:return D(1000),D(100)
    if minute<300:return D(990),D(100)
    if minute<303:return D(1070),D(90)
    if minute<360:return D(990),D(100)
    if minute<420:return D(1070),D(90)
    if minute<480:return D(1100),D(90)
    if minute<540:return D(950),D(100)
    if minute<542:return D(950),D(100)
    if minute<840:return D(960),D(100)
    if minute<843:return D(880),D(110)
    if minute<900:return D(960),D(100)
    if minute<960:return D(880),D(110)
    if minute<1020:return D(850),D(110)
    return D(980),D(100)


def btc_turnover(minute):
    return D(4000000) if minute==1 else D(3800000) if minute==540 else D('1e9')


def write_partial_failure_evidence(output,request,error,*,native_clock_ns,evidence):
    """Exclusive forensic export only; aborted prefix is never a full PASS."""
    packet={"status":"FAILED_PARTIAL_NATIVE_EVIDENCE","fixture_id":FIXTURE_ID,
        "run_id":request.get("run_id"),"declared_interval":{"start_ns":START_NS,"end_ns":END_NS},
        "native_clock_ns":str(native_clock_ns) if native_clock_ns is not None else None,
        "original_error":{"type":type(error).__name__,"message":str(error)},
        "checks":"UNKNOWN_NOT_FINALIZED","financial_qualification":"UNKNOWN_ABORTED_PREFIX",
        "coherence":"UNFINALIZED_ENGINE_CALLBACK_STATE_NOT_A_SETTLED_RECEIPT",
        "native_evidence":evidence,"ranking_eligible":False,
        "terminal_close_or_synthetic_fill_performed_by_export":False,
        "original_failure_and_budget_spend_preserved":True}
    path=Path(output)/"engineering-partial-failure.json"
    with path.open("x") as stream:stream.write(json.dumps(packet,indent=2,sort_keys=True,default=str)+"\n")
    return path


def run_fixture(request):
    if (request.get('fixture_id'),request.get('start_ns'),request.get('end_ns'))!=(FIXTURE_ID,START_NS,END_NS):
        raise ValueError('CM2_EXPLICIT_E04_18H_CONTRACT_REQUIRED')
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.config import BacktestEngineConfig,SimulationModuleConfig
    from nautilus_trader.backtest.modules import SimulationModule
    from nautilus_trader.backtest.models import LimitOrderPartialFillModel,LatencyModel
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.core.data import Data
    from nautilus_trader.model.data import CustomData,DataType,BarType,BarSpecification
    from nautilus_trader.model.enums import AccountType,OmsType,OrderType,OrderSide,OrderStatus,TimeInForce,BarAggregation,PriceType,AggregationSource
    from nautilus_trader.model.identifiers import ClientId
    from nautilus_trader.model.objects import Money,Quantity
    from coinmaster.strategy.cm2_native import CM2Strategy,CM2StrategyConfig,minute_turnover
    from coinmaster.strategy.cm2_execution import ExecutionLimits,stage_targets,order_plan
    from coinmaster.strategy.cm2_policy import decide,Snapshot,positive_harvest
    from coinmaster.strategy.cm2_checkpoint import NativeCheckpointStore,observer_continuity,canonical,KEY
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    from coinmaster.research.native_full_fill import ZeroImpactFullFillDiagnostic,zero_impact_venue_options
    from coinmaster.research.native_fixture import FundingInstruction,PerpetualFundingModule,BybitTierMarginModule,instrument_quote
    from coinmaster.ledger.journal import NativeEventJournal
    from coinmaster.venues.marks import venue_mark,venue_mark_data_type
    from coinmaster.research.native_accounting import native_position_lifecycles
    from coinmaster.research.paired_observer import CommittedNativeObserver
    from coinmaster.research.minute_risk import NativeMinuteRiskRecorder,observed_neutral_strategy_type
    from types import SimpleNamespace

    output=Path(request['artifact_dir']);output.mkdir(parents=True,exist_ok=True)
    journal_path=output/'fixture-funding.sqlite'
    if journal_path.exists():raise ValueError('FRESH_FIXTURE_JOURNAL_REQUIRED')
    profile=load_current_hl_diagnostic(Path(request['current_hl_execution_inputs']))
    btc,sol=profile.instruments;seed=D(10000);selected=dict(profile.selected_leverage)
    journal=NativeEventJournal(str(journal_path));store=NativeCheckpointStore(journal)
    observer=CommittedNativeObserver(output/'fixture-coherent-native-events.jsonl.gz',seed,(btc,sol),journal,END_NS)
    recorder=NativeMinuteRiskRecorder(output/'fixture-minute-native-risk.csv.gz',seed,(btc,sol),selected,
        END_NS,margin_policy=profile.margin_policy(120_000_000_000))

    class InputEvent(Data):
        def __init__(self,ns,feature=None,actions=()):self.ns=ns;self.feature=feature;self.actions=actions
        @property
        def ts_event(self):return self.ns
        @property
        def ts_init(self):return self.ns
    input_type=DataType(InputEvent)

    class FaultModule(SimulationModule):
        def __init__(self):super().__init__(SimulationModuleConfig())
        def process(self,ts_now):pass
        def log_diagnostics(self,logger):pass
        def reset(self):pass
    faults=FaultModule()

    class FixturePartialModel(ZeroImpactFullFillDiagnostic):
        def __init__(self):super().__init__();self.stock_partial=LimitOrderPartialFillModel()
        def get_orderbook_for_fill_simulation(self,instrument,order,best_bid,best_ask):
            if order.order_type==OrderType.LIMIT and order.time_in_force==TimeInForce.IOC:
                return self.stock_partial.get_orderbook_for_fill_simulation(instrument,order,best_bid,best_ask)
            return super().get_orderbook_for_fill_simulation(instrument,order,best_bid,best_ask)

    class FixtureStrategy(CM2Strategy):
        def __init__(self,config):
            super().__init__(config);self.fixture_events=[];self.fixture_ids={};self.fixture_snapshots={}
            self.fixture_shapes={};self.fixture_replays=[];self.fixture_duplicates=[]
        def on_start(self):
            super().on_start();self.subscribe_data(input_type,client_id=ClientId('CM2_E04'))
        def on_data(self,data):
            value=getattr(data,'data',data)
            if not isinstance(value,InputEvent):return super().on_data(data)
            if value.feature is not None:self.current_features=value.feature
            for action in value.actions:
                if action=='SNAPSHOT':self._capture(value.ns)
                elif action=='REPLAY':self._replay(value.ns)
                elif action in ('DENIED','REJECTED','DELAYED_ACK','LATE_BTC'):self._sentinel(action,value.ns)
                elif action in ('UNKNOWN_ACK','UNKNOWN_LATE_BTC'):
                    tag='DELAYED_ACK' if action=='UNKNOWN_ACK' else 'LATE_BTC'
                    s=self._snapshot(value.ns);oid=self.fixture_ids[tag];order=self.cache.order(oid)
                    self.fixture_snapshots['unknown_ack' if tag=='DELAYED_ACK' else 'unknown_late_btc']={'unknown':s.unknown_orders,'acked':self._owned[str(oid)]['acked'],
                        'status':order.status.name,'native_id':str(oid),'ts_ns':str(value.ns)}
                    if not order.is_closed:self.cancel_order(order)
        def _capture(self,now):
            s=self._snapshot(now)
            self.fixture_snapshots[str((now-START_NS)//MINUTE_NS)]={
                'btc':str(s.btc_qty),'sol':str(s.sol_qty),'unknown':s.unknown_orders,
                'feature_closed_ns':str(self.current_features.closed_ns),'harvested':self.policy_state.harvested,
                'safety_cap':str(self.policy_state.safety_cap),'btc_intent':self.policy_state.btc_intent,
                'parent':self.policy_state.parent,'restore_failed_lockout':self._restore_failed,'ts_ns':str(now)}
        def _make_order(self,iid,side,quantity,reducing,price):
            hour=(self.clock.timestamp_ns()-START_NS)//HOUR_NS
            if iid==self.config.btc_id and reducing and self.policy_state.btc_intent=='POSITIVE_HARVEST' and not self.policy_state.draining:
                phase='LONG' if hour<9 else 'SHORT'
                key=phase+'_GTC' if hour in (5,14) else phase+'_IOC' if hour in (6,15) else None
                if key is not None and key not in self.fixture_shapes:
                    if quantity.as_decimal()!=D(10):raise ValueError('E04_EXPECTED_FINITE_HARVEST_CHILD10')
                    if key.endswith('GTC'):
                        # Test-only far working order; profitable IOC uses REAL production factory.
                        far=1200 if phase=='LONG' else 700
                        order=self.order_factory.limit(instrument_id=iid,order_side=side,quantity=quantity,
                            price=self.cache.instrument(iid).make_price(far),time_in_force=TimeInForce.GTC,
                            reduce_only=True,post_only=False)
                    else:
                        order=super()._make_order(iid,side,quantity,reducing,price)
                        if order is None or order.order_type!=OrderType.LIMIT or order.time_in_force!=TimeInForce.IOC:
                            raise ValueError('E04_PRODUCTION_HARVEST_LIMIT_IOC_REQUIRED')
                    self.fixture_shapes[key]=str(order.client_order_id)
                    return order
            return super()._make_order(iid,side,quantity,reducing,price)
        def _record_event(self,kind,event):
            self.fixture_events.append({'kind':kind,'event_id':str(event.id),
                'client_order_id':str(event.client_order_id),'ts_ns':str(event.ts_event)})
        def on_order_accepted(self,event):
            self._record_event('ACCEPTED',event);super().on_order_accepted(event)
            if str(event.client_order_id)==str(self.fixture_ids.get('DELAYED_ACK')):
                self.cancel_order(self.cache.order(event.client_order_id))
        def on_order_canceled(self,event):self._record_event('CANCELED',event);super().on_order_canceled(event)
        def on_order_denied(self,event):self._record_event('DENIED',event);super().on_order_denied(event)
        def on_order_rejected(self,event):self._record_event('REJECTED',event);super().on_order_rejected(event)
        def on_order_cancel_rejected(self,event):
            self._record_event('CANCEL_REJECTED',event);super().on_order_cancel_rejected(event)
        def on_order_filled(self,event):
            self._record_event('FILLED',event);super().on_order_filled(event)
            if str(event.client_order_id)==self.fixture_shapes.get('LONG_IOC') and not self.fixture_duplicates:
                before=canonical({'fills':self.fill_audit,'entry_fees':self._entry_fees,'cost_qty':self._btc_cost_qty,
                    'funding':self._parent_funding,'seen':sorted(self._seen_trade_ids)})
                CM2Strategy.on_order_filled(self,event)  # domain ONLY; no native/recorder/observer replay
                after=canonical({'fills':self.fill_audit,'entry_fees':self._entry_fees,'cost_qty':self._btc_cost_qty,
                    'funding':self._parent_funding,'seen':sorted(self._seen_trade_ids)})
                self.fixture_duplicates.append({'trade_id':str(event.trade_id),'unchanged':before==after,
                    'scope':'CM2_HANDLER_ONLY_ACTUAL_NATIVE_EVENT_NOT_REPOSTED'})
        def _sentinel(self,tag,now):
            if self.cache.positions_open():raise ValueError('E04_SENTINEL_REQUIRES_NATIVE_FLAT')
            inst=self.cache.instrument(self.config.btc_id if tag=='LATE_BTC' else self.config.sol_id)
            if tag=='LATE_BTC':order=self.order_factory.market(instrument_id=inst.id,order_side=OrderSide.BUY,
                quantity=inst.make_qty('1'),time_in_force=TimeInForce.IOC)
            elif tag=='DENIED':order=self.order_factory.market(instrument_id=inst.id,order_side=OrderSide.BUY,
                # Deliberately raw precision3 > verified SOLprecision2; make_qty would normalize.
                quantity=Quantity.from_str(DENIED_QUANTITY_TEXT),time_in_force=TimeInForce.IOC)
            else:order=self.order_factory.limit(instrument_id=inst.id,order_side=OrderSide.BUY,
                quantity=inst.make_qty('1' if tag=='REJECTED' else '10'),
                price=inst.make_price('100' if tag=='REJECTED' else '1'),post_only=tag=='REJECTED',time_in_force=TimeInForce.GTC)
            oid=order.client_order_id;self.fixture_ids[tag]=oid
            self._owned[str(oid)]={'instrument_id':inst.id,'client_order_id':oid,'submit_ns':now,'terminal':False,'acked':False}
            self._order_audit[str(oid)]={'client_order_id':str(oid),'instrument':str(inst.id),'action':'BTC' if tag=='LATE_BTC' else 'SOL',
                'reason':'FIXTURE_SENTINEL','submit_ns':str(now),'decision_ns':str(now),'quantity':str(order.quantity),
                'reduce_only':False,'admission':{'intent':'FIXTURE_SENTINEL','parent':-1,'test_only':True,'tag':tag}}
            if hasattr(self,'_chain_audit'):self._chain_audit('FIXTURE_SENTINEL',self._order_audit[str(oid)])
            self._persist_checkpoint()
            if tag in ('DELAYED_ACK','LATE_BTC'):faults.exchange.set_latency_model(LatencyModel(base_latency_nanos=0,insert_latency_nanos=QUEUED_LATENCY_NS))
            try:self.submit_order(order)
            finally:
                if tag in ('DELAYED_ACK','LATE_BTC'):faults.exchange.set_latency_model(LatencyModel(base_latency_nanos=0))
        def _shadow(self,now):
            s=self._snapshot(now);f=self.current_features
            decision=decide(self.config.policy,f,s,self.policy_state,now_ns=now)
            inst=self.cache.instrument(self.config.sol_id)
            bt,so,staged=stage_targets(decision,s,f,sol_step=inst.size_increment.as_decimal(),
                sol_min_qty=inst.min_quantity.as_decimal() if inst.min_quantity is not None else D(0),sol_min_notional=inst.min_notional.as_decimal())
            b=self.cache.instrument(self.config.btc_id);quote=self._quotes[b.id]
            price=(quote.ask_price if bt>s.btc_qty else quote.bid_price).as_decimal()
            plan=order_plan(actual=s.btc_qty,target=bt,pending=s.btc_pending,unknown=s.unknown_orders,
                price=price,step=b.size_increment.as_decimal(),min_qty=b.min_quantity.as_decimal() if b.min_quantity is not None else b.size_increment.as_decimal(),
                max_child=self._child_capacity(b.id,now),min_notional=b.min_notional.as_decimal())
            return {'decision':asdict(decision),'stage':[bt,so,staged],'btc_plan':asdict(plan),
                'cadence_eligible':now-self._last_child.get(b.id,0)>=self.config.limits.child_interval_ns}
        def _replay(self,now):
            before=self._shadow(now);saved=self.save();continuity=canonical(observer_continuity(recorder,observer))
            native=canonical(self._native_checkpoint_binding());body=saved[KEY]
            self.policy_state=State();self.current_features=Features(0,0,False,'TESTONLY_DOMAIN_RESET')
            self.hours=deque(maxlen=170);self.hour_builder=PairedHourBuilder();self._owned={};self._seen_trade_ids=set();self._last_child={}
            self._entry_fees=D(0);self._btc_cost_qty=D(0);self._parent_funding=D(0);self._funding_last=D(0)
            self._parent_cost_known=False;self._liquidating=False;self._risk_unknown=False;self.orphan_started_ns=None
            self.load(saved);after=self._shadow(now)
            self.fixture_replays.append({'ts_ns':str(now),'public_actor_save_load':True,
                'domain_bytes_restored':canonical(self._checkpoint_document())==body,
                'shadow_plan_equal':canonical(before)==canonical(after),
                'native_binding_unchanged':native==canonical(self._native_checkpoint_binding()),
                'both_HWM_seed_unchanged':continuity==canonical(observer_continuity(recorder,observer)),
                'remaining_child_quantity':str(abs(after['btc_plan']['signed_quantity'])),
                'cadence_blocks_duplicate_same_clock':not after['cadence_eligible'],
                'revision':store.read()[0],'scope':'SAME_ENGINE_RETAINED_NATIVE_CACHE_ACCOUNT_OBSERVERS_FEEDS_NOT_COLD_RECOVERY'})

    funding=(FundingInstruction('cm2-e04-btc-long',btc.id,D('.0001'),START_NS+270*MINUTE_NS,D(990)),
        FundingInstruction('cm2-e04-sol-long',sol.id,D('.0001'),START_NS+270*MINUTE_NS,D(100)),
        FundingInstruction('cm2-e04-btc-short',btc.id,D('.0001'),START_NS+810*MINUTE_NS,D(960)),
        FundingInstruction('cm2-e04-sol-short',sol.id,D('.0001'),START_NS+810*MINUTE_NS,D(100)))
    modules=[PerpetualFundingModule(funding,journal),BybitTierMarginModule((),tuple(profile.selected_leverage),
        120_000_000_000,margin_policy=profile.margin_policy(120_000_000_000),settlement_currency=btc.settlement_currency),observer,faults]
    ObservedFixture=observed_neutral_strategy_type(FixtureStrategy,recorder)
    strategy=None
    engine=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR'),run_analysis=False))
    try:
        engine.add_venue(venue=btc.id.venue,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,
            starting_balances=[Money(seed,btc.settlement_currency)],base_currency=btc.settlement_currency,
            default_leverage=D(1),leverages=selected,modules=modules,bar_execution=False,
            use_message_queue=True,latency_model=LatencyModel(base_latency_nanos=0),**zero_impact_venue_options(FixturePartialModel()))
        for inst in (btc,sol):engine.add_instrument(inst)
        minute_types={i.id:BarType(i.id,BarSpecification(1,BarAggregation.MINUTE,PriceType.LAST),AggregationSource.EXTERNAL) for i in (btc,sol)}
        def funding_reader(iid):return sum((D(r[5]) for r in journal.funding_cash_audit() if r[1]==str(iid)),D(0))
        strategy=ObservedFixture(CM2StrategyConfig(btc_id=btc.id,sol_id=sol.id,btc_bar_type=minute_types[btc.id],sol_bar_type=minute_types[sol.id],
            btc_mark_data_type=venue_mark_data_type(btc.id),sol_mark_data_type=venue_mark_data_type(sol.id),mark_client_id=ClientId('CM2_E04'),
            policy=Config(load=8,core=.5,hedge_fraction=.75),limits=ExecutionLimits(CAPACITY_NOTIONAL),
            margin_policy=profile.margin_policy(120_000_000_000),trading_start_open_ns=START_NS,terminal_close_at_ns=END_NS,
            funding_reader=funding_reader,execution_policy_hash='CM2_E04_NATIVE_CURRENT_CHILD_V2',
            checkpoint_store=store,continuity_reader=lambda:observer_continuity(recorder,observer)))
        engine.add_strategy(strategy)
        inputs=[CustomData(input_type,InputEvent(START_NS+h*HOUR_NS,feature=fixed_feature(h))) for h in range(18) if h not in (1,10)]
        samples={2,3,61,121,181,241,270,301,302,303,304,361,362,421,481,492,493,1022,1025,1027,541,542,601,661,721,781,810,841,842,843,844,901,902,961,1021,1030,1033,1035,1079}
        for m in samples:
            actions=['SNAPSHOT']
            if m in (361,901):actions.append('REPLAY')
            if m==492:actions.append('DENIED')
            if m==493:actions.append('REJECTED')
            if m==1022:actions.append('DELAYED_ACK')
            if m==1025:actions.append('UNKNOWN_ACK')
            if m==1030:actions.append('LATE_BTC')
            if m==1033:actions.append('UNKNOWN_LATE_BTC')
            inputs.append(CustomData(input_type,InputEvent(START_NS+m*MINUTE_NS+1,actions=actions)))
        # A queued deadline is NOT a timer: first public no-op data settles it,
        # next +1ns data may observe actual acceptance/fill and native callbacks.
        for minute in QUEUE_PULSE_MINUTES:
            inputs.append(CustomData(input_type,InputEvent(START_NS+minute*MINUTE_NS+1)))
            inputs.append(CustomData(input_type,InputEvent(START_NS+minute*MINUTE_NS+2,actions=('SNAPSHOT',))))
        marks=[];quotes=[];bundles=[]
        for minute in range(1,1081):
            ns=START_NS+minute*MINUTE_NS;bp,sp=minute_prices(minute)
            marks.extend((minute_turnover(btc.id,btc_turnover(minute),ns),minute_turnover(sol.id,D('1e9'),ns),venue_mark(btc.id,bp,ns),venue_mark(sol.id,sp,ns)))
            quotes.extend((instrument_quote(btc,bp,bp,ns,size='100000'),instrument_quote(sol,sp,sp,ns,size='100000')))
            def bar(px):return {k:str(px) for k in ('open','high','low','close')}
            bundles.append(SimpleNamespace(open_time_ms=(ns-MINUTE_NS)//1_000_000,btc_mark=bar(bp),sol_mark=bar(sp)))
        observer.set_week(bundles);recorder.set_week(bundles)
        engine.add_data(inputs,client_id=ClientId('CM2_E04'),sort=False);engine.add_data(marks,client_id=ClientId('CM2_E04'),sort=False)
        engine.add_data(quotes,sort=False);engine.sort_data();engine.run();engine.end()
        coherent=observer.finish_after_engine_end(END_NS);minute_summary=recorder.close();state=strategy.reporting_state()
        fills=state['fill_audit'];orders=engine.cache.orders();snap=strategy.fixture_snapshots
        def qty(m,symbol='btc'):return D(snap[str(m)][symbol])
        def event(kind,oid):return [r for r in strategy.fixture_events if r['kind']==kind and r['client_order_id']==str(oid)]
        shaped={k:engine.cache.order(next(o.client_order_id for o in orders if str(o.client_order_id)==oid)) for k,oid in strategy.fixture_shapes.items()}
        partial=[o for o in orders if D(0)<o.filled_qty.as_decimal()<o.quantity.as_decimal()]
        def phase_harvest(hour,side):return [f for f in fills if f['instrument']==str(btc.id) and f['order_side']==side and START_NS+hour*HOUR_NS<=int(f['fill_ns'])<START_NS+(hour+1)*HOUR_NS]
        long_h=phase_harvest(6,'SELL');short_h=phase_harvest(15,'BUY')
        stage=[a for a in strategy.cm2_audit if a['reason']=='SOL_BEFORE_ORDINARY_BTC_REDUCTION']
        progress={'actual_long_positive_harvest':sum((D(f['qty']) for f in long_h),D(0))==10,
            'actual_short_positive_harvest':sum((D(f['qty']) for f in short_h),D(0))==10,
            'confirmed_sol_before_long_harvest':bool(stage) and qty(301,'sol')>D('-148.5') and qty(301)==20,
            'bounded_long_harvest_progress':qty(361)==15 and qty(362)==10,
            'ordinary_staging_no_endless_loop':0<len(stage)<=16,'long_harvest_actual_quantity':str(sum((D(f['qty']) for f in long_h),D(0))),
            'long_staging_callbacks':sum(int(a['parent']==1) for a in stage)}
        gross=-sum(((D(1) if f['order_side']=='BUY' else D(-1))*D(f['qty'])*D(f['px']) for f in fills),D(0))
        expected_fees=sum((Money(D(f['qty'])*D(f['px'])*D('.000432'),btc.settlement_currency).as_decimal() for f in fills),D(0))
        fees=sum((D(f['commission']) for f in fills),D(0));postings=journal.funding_cash_audit()
        signed=sum((D(r[5]) for r in postings),D(0));cash=engine.cache.account_for_venue(btc.id.venue).balance_total(btc.settlement_currency).as_decimal()
        pair_totals=[sum((D(r[5]) for r in postings if int(r[2])==START_NS+m*MINUTE_NS),D(0)) for m in (270,810)]
        def current_permission(fill):
            a=fill.get('admission') or {}
            if a.get('intent') not in ('INITIAL_ENTRY','FAVORABLE_ADD','POSITIVE_HARVEST'):return True
            if a.get('model')!='CM2_CURRENT_CHILD_ADMISSION_V1' or not a.get('allowed'):return False
            q=D(a['btc_actual']);p=D(a['executable_price'])
            if int(a['candidate_ns'])!=int(fill['fill_ns']) or p!=D(fill['px']):return False
            if a['intent']=='POSITIVE_HARVEST':
                s=Snapshot(D(1),q,D(0),p,D(1),btc_vwap=D(a['btc_native_vwap']),btc_entry_fees=D(a['btc_allocated_entry_fees']),
                    btc_signed_funding=D(a['btc_allocated_signed_funding']),exit_fee_rate=D(a['exit_fee_rate']),btc_tick=D(a['btc_tick']))
                return positive_harvest(s)
            return not q or (D(1) if q>0 else D(-1))*(p-D(a['btc_native_vwap']))>0
        def exact_limit_remainder(minute,side):
            matched=[f for f in fills if f['instrument']==str(btc.id) and f['order_side']==side
                and int(f['fill_ns'])==START_NS+minute*MINUTE_NS]
            return len(matched)==1 and D(matched[0]['qty'])==5 and any(
                str(o.client_order_id)==matched[0]['client_order_id'] and o.order_type==OrderType.LIMIT and o.time_in_force==TimeInForce.IOC
                and o.is_reduce_only and not o.is_post_only
                and o.quantity.as_decimal()==5 and o.filled_qty.as_decimal()==5 for o in orders)
        def exact_gtc_cancel(key,accepted_minute,canceled_minute):
            order=shaped.get(key)
            if order is None:return False
            accepted=event('ACCEPTED',order.client_order_id);canceled=event('CANCELED',order.client_order_id)
            return (order.status==OrderStatus.CANCELED and order.filled_qty.as_decimal()==0
                and len(accepted)==1 and len(canceled)==1
                and int(accepted[0]['ts_ns'])==START_NS+accepted_minute*MINUTE_NS
                and int(canceled[0]['ts_ns'])==START_NS+canceled_minute*MINUTE_NS)
        btc_fills=[f for f in fills if f['instrument']==str(btc.id)]
        actual_harvests=[f for f in btc_fills if (f.get('admission') or {}).get('intent')=='POSITIVE_HARVEST']
        native_orders={str(o.client_order_id):o for o in orders}
        sentinel_orders={tag:engine.cache.order(oid) for tag,oid in strategy.fixture_ids.items()}
        late_buys=[f for f in btc_fills if f['client_order_id']==str(strategy.fixture_ids.get('LATE_BTC'))]
        late_sells=[f for f in btc_fills if START_NS+1034*MINUTE_NS<int(f['fill_ns'])<END_NS and f['order_side']=='SELL']
        late_pair=late_buys+late_sells
        late_fees=sum((D(f['commission']) for f in late_pair),D(0))
        def zero_cap(minute):
            try:return D(snap[str(minute)]['safety_cap'])==0
            except Exception:return False
        checks={'native_terminal_flat':not engine.cache.positions_open() and not engine.cache.orders_open() and not engine.cache.orders_inflight(),
            'native_partial_fill':bool(partial),'native_partial_terminal_canceled':all(shaped.get(k) is not None and shaped[k].status==OrderStatus.CANCELED and shaped[k].quantity.as_decimal()==10 and shaped[k].filled_qty.as_decimal()==5 for k in ('LONG_IOC','SHORT_IOC')),
            'both_btc_sides':{f['order_side'] for f in btc_fills}=={'BUY','SELL'},
            'actual_positive_harvest':progress['actual_long_positive_harvest'] and progress['actual_short_positive_harvest'],
            'actual_sol_fill':any(f['instrument']==str(sol.id) for f in fills),'actual_funding':len(postings)==4,
            'exact_independent_fees':fees==expected_fees,'exact_independent_terminal_cash':cash==seed+gross-expected_fees+signed,
            'multiple_actual_parents':strategy.policy_state.parent>=2,'coherent_observer':coherent['status']=='PASS',
            'first_fixed_funding':pair_totals[0]==FUNDING_EXPECTED[0],'minute_watermarks':minute_summary['rows']==1080*3,
            'ordinary_sol_first_staging':progress['confirmed_sol_before_long_harvest'],**{k:v for k,v in progress.items() if type(v) is bool},
            'initial_entry_capacity_and_adverse_no_add':qty(2)==40 and qty(3)==40 and qty(541)==-40 and qty(542)==-40,
            'stale_clock_fixed_half_trim':qty(61)==20 and qty(601)==-20 and snap['61']['feature_closed_ns']==str(START_NS) and snap['601']['feature_closed_ns']==str(START_NS+9*HOUR_NS),
            'valid_recovery_retains_reduced_quantity':all(qty(m)==q for m,q in ((121,D(20)),(181,D(20)),(661,D(-20)),(721,D(-20)))),
            'actual_opposite_hedge_before_funding':qty(241)==20 and qty(241,'sol')==D('-148.5') and qty(781)==-20 and qty(781,'sol')==D(144),
            'both_signed_funding_pairs':pair_totals==list(FUNDING_EXPECTED) and signed==D('-.015'),
            'working_harvest_revoked_actual_native_cancel':exact_gtc_cancel('LONG_GTC',302,303) and exact_gtc_cancel('SHORT_GTC',842,843) and qty(303)==20 and qty(843)==-20,
            'no_losing_ordinary_child':all(current_permission(f) for f in btc_fills),
            'actual_native_harvest_net_geometry_positive':bool(long_h and short_h) and all(f.get('actual_harvest_geometry',{}).get('status')=='PASS' for f in actual_harvests),
            'production_harvest_limit_IOC_both_sides':bool(long_h and short_h) and all(
                native_orders[f['client_order_id']].order_type==OrderType.LIMIT
                and native_orders[f['client_order_id']].time_in_force==TimeInForce.IOC
                and native_orders[f['client_order_id']].is_reduce_only and not native_orders[f['client_order_id']].is_post_only
                and native_orders[f['client_order_id']].price.as_decimal()==D(f['admission']['executable_price'])
                for f in actual_harvests),
            'bounded_mirrored_harvest_remainders':qty(361)==15 and qty(362)==10 and qty(901)==-15 and qty(902)==-10 and exact_limit_remainder(362,'SELL') and exact_limit_remainder(902,'BUY'),
            'no_postharvest_favorable_readd':qty(421)==10 and qty(961)==-10 and snap['421']['harvested'] and snap['961']['harvested'] and not any(START_NS+h*HOUR_NS<=int(f['fill_ns'])<START_NS+(h+1)*HOUR_NS for f in btc_fills for h in (7,16)),
            'native_denied_and_rejected':all(tag in sentinel_orders and sentinel_orders[tag].status==status and event(tag,sentinel_orders[tag].client_order_id) for tag,status in (('DENIED',OrderStatus.DENIED),('REJECTED',OrderStatus.REJECTED))),
            'actual_queued_unknown_ack_freeze':snap.get('unknown_ack',{}).get('unknown') is True and snap['unknown_ack']['acked'] is False,
            'late_ack_native_accept_cancel_resolution':'DELAYED_ACK' in sentinel_orders and sentinel_orders['DELAYED_ACK'].status==OrderStatus.CANCELED and bool(event('ACCEPTED',strategy.fixture_ids['DELAYED_ACK'])) and bool(event('CANCELED',strategy.fixture_ids['DELAYED_ACK'])),
            'fault_sol_sentinels_no_native_fills':len(sentinel_orders)==4 and all(sentinel_orders[k].filled_qty.as_decimal()==0 for k in ('DENIED','REJECTED','DELAYED_ACK')) and qty(1021)==0 and qty(1021,'sol')==0 and qty(1027)==0 and qty(1027,'sol')==0,
            'late_foreign_BTC_native_fill_zero_quarantine_drain':len(late_buys)==1 and len(late_sells)==1 and all(D(f['qty'])==1 and D(f['px'])==980 for f in late_pair)
                and late_buys[0].get('foreign_parent_quarantine') is True and qty(1034)==1 and qty(1035)==0
                and zero_cap(1033) and snap.get('unknown_late_btc',{}).get('unknown') is True
                and snap['1034']['parent']==snap['1021']['parent']==snap['1035']['parent']
                and snap['1035']['restore_failed_lockout'] and snap['1079']['restore_failed_lockout']
                and late_fees==D('.84672') and bool(event('CANCEL_REJECTED',strategy.fixture_ids.get('LATE_BTC'))),
            'duplicate_actual_fill_domain_idempotent':len(strategy.fixture_duplicates)==1 and strategy.fixture_duplicates[0]['unchanged'] and coherent['native_unique_fills']==len(fills),
            'public_actor_domain_replay_native_HWM_retained':len(strategy.fixture_replays)==2 and all(all(r[k] for k in ('public_actor_save_load','domain_bytes_restored','shadow_plan_equal','native_binding_unchanged','both_HWM_seed_unchanged','cadence_blocks_duplicate_same_clock')) and D(r['remaining_child_quantity'])==5 for r in strategy.fixture_replays)}
        report={'fixture_id':FIXTURE_ID,'execution_model_id':'CM2_FIXTURE_NATIVE_STOCK_LIMIT_PARTIAL_PLUS_QUALIFIED_MARKET_FULLFILL',
            'fixture_timing_model':{'id':TIMING_MODEL_ID,'normal_base_latency_ns':0,'queued_insert_latency_ns':QUEUED_LATENCY_NS,
                'queued_cancel_latency_ns':0,'scope':'TEST_ONLY_NOT_BENCHMARK_LATENCY_OR_E02_E03_EQUIVALENCE'},
            'ranking_eligible':False,'engine_constructors':1,'interval':{'start_ns':START_NS,'end_ns':END_NS},
            'checks':checks,'actual_progress_evidence':progress,'status':'PASS' if all(checks.values()) else 'FAIL',
            'manual_arithmetic':{'seed':str(seed),'gross_closed_fill_double_entry':str(gross),'expected_fees_from_fixed_rate':str(expected_fees),
                'native_fees':str(fees),'signed_native_funding':str(signed),'expected_cash':str(seed+gross-expected_fees+signed),'native_cash':str(cash),
                'late_foreign_BTC_native_pair_fees':str(late_fees),'late_pair_expected_fees':'.84672',
                'first_funding_expected':str(FUNDING_EXPECTED[0]),'first_funding_actual':str(pair_totals[0]),'second_funding_expected':str(FUNDING_EXPECTED[1]),'second_funding_actual':str(pair_totals[1]),
                'fee_rounding':'PER_FILL_NATIVE_COMMISSION_CURRENCY_MONEY_QUANTUM_NO_TOLERANCE_CHANGE'},
            'native_partial_orders':[{'client_order_id':str(o.client_order_id),'status':str(o.status),'requested':str(o.quantity),'filled':str(o.filled_qty)} for o in partial],
            'actual_native_fill_audit':fills,'native_adapter':state,'coherent_native_observer':coherent,'minute_native_risk':minute_summary,
            'native_lifecycles':native_position_lifecycles(engine.cache),'v2_actual_event_ids':strategy.fixture_events,
            'v2_script_snapshots':snap,'v2_testonly_order_shapes':strategy.fixture_shapes,
            'v2_fault_sentinel_ids':{k:str(v) for k,v in strategy.fixture_ids.items()},'v2_duplicate_delivery':strategy.fixture_duplicates,'v2_domain_replay':strategy.fixture_replays,
            'coverage_unknown':['OS_COLD_RESTART_NATIVE_ACCOUNT_RECONSTRUCTION_NOT_IMPLEMENTED','REAL_TRANSPORT_LOSS_NOT_SIMULATED','HISTORICAL_INTRAMINUTE_EXECUTION_NOT_PROVEN'],
            'coverage_pure':['FIXED_18H_CAUSAL_SCRIPT','CURRENT_CHILD_INTENT_AND_FINITE_HARVEST_PROPERTIES'],
            'test_only_fault_scope':'OWNED_NO_FILL_SENTINELS_NATIVE_RISK_EXCHANGE_AND_LOCAL_QUEUED_LATENCY_NOT_PRODUCTION_CHANGES'}
        (output/'engineering-report.json').write_text(json.dumps(report,sort_keys=True,default=str)+'\n')
        if not all(checks.values()):raise ValueError('CM2_E04_NATIVE_ENGINEERING_CHECKS_FAILED')
        return report
    except BaseException as error:
        # Read/cache-export BEFORE disposal; no flatten, fabricated fill, end(),
        # tracker.summary(), or completed receipt is introduced on an abort.
        try:
            evidence={}
            readers={"native_orders":lambda:[{"client_order_id":str(o.client_order_id),"instrument":str(o.instrument_id),
                "order_type":o.order_type.name,"time_in_force":o.time_in_force.name,
                "status_name":o.status.name,"status_value":o.status.value,"side":o.side.name,
                "quantity":str(o.quantity),"filled_quantity":str(o.filled_qty),"leaves_quantity":str(o.leaves_qty),
                "limit_price":str(o.price) if getattr(o,"price",None) is not None else None,
                "reduce_only":o.is_reduce_only} for o in engine.cache.orders()],
                "native_position_lifecycles":lambda:native_position_lifecycles(engine.cache),
                "native_funding_cash_audit":journal.funding_cash_audit,
                "retained_observer_state":lambda:observer_continuity(recorder,observer)}
            if strategy is not None:
                readers.update(native_cache_snapshot=strategy._native_checkpoint_binding,
                    native_adapter=strategy.reporting_state,
                    native_domain_checkpoint_observation=strategy._checkpoint_document,
                    latest_durable_checkpoint=lambda:{"revision":store.read()[0],
                        "document":json.loads(store.read()[1])} if store.read() is not None else None,
                    v2_native_event_ids=lambda:strategy.fixture_events,
                    v2_script_snapshots=lambda:strategy.fixture_snapshots,
                    v2_domain_replay=lambda:strategy.fixture_replays,
                    v2_testonly_order_shapes=lambda:strategy.fixture_shapes,
                    v2_fault_sentinel_ids=lambda:{k:str(v) for k,v in strategy.fixture_ids.items()})
            for name,reader in readers.items():
                try:evidence[name]=reader()
                except Exception as field_error:
                    evidence[name]={"status":"UNKNOWN_EXPORT_FIELD_FAILED","error_type":type(field_error).__name__,"error":str(field_error)}
            write_partial_failure_evidence(output,request,error,
                native_clock_ns=strategy.clock.timestamp_ns() if strategy is not None else None,evidence=evidence)
        except Exception as export_error:
            # Never replace the original native/fixture failure with exporter failure.
            try:
                with (output/'partial-export-error.json').open('x') as stream:
                    stream.write(json.dumps({'original_error_type':type(error).__name__,
                        'export_error_type':type(export_error).__name__,'export_error':str(export_error)})+'\n')
            except Exception:pass
        raise
    finally:
        engine.dispose();observer.file.close();recorder.close_writers();journal.close()
