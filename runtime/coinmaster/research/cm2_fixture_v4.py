"""PREPARED v4 one-engine native contract cycle; never economic qualification.

Import/API0 construct no engine. Physical run requires a fresh explicit budget.
Synthetic features/marks and a documented native dust-seed order are TEST ONLY.
Native cache, statuses, fills, cash and funding are never assigned or fabricated.
"""
from dataclasses import asdict,replace
from decimal import Decimal as D
import json
from pathlib import Path
from coinmaster.strategy.cm2_policy import Config,Features,HOUR_NS,MINUTE_NS,btc_child_permission

FIXTURE_ID='cm2-systematic-repair-native-v4'
TRIM_FIXTURE_ID='cm2-systematic-repair-trim-native-v4'
EMERGENCY_FIXTURE_ID='cm2-execution-units-emergency-native-v1'
FIXTURE_IDS=(FIXTURE_ID,TRIM_FIXTURE_ID,EMERGENCY_FIXTURE_ID)
START_NS=1725148800000000000
END_NS=START_NS+12*HOUR_NS
TEST_ONLY_POLICY=Config(load=4,core=.5,hedge_fraction=.45,parent_risk_fraction=.9,
    initial_band_atr=2,hedge_future_cost_rate=.000432,
    downside_scenarios=((-0.02,-0.04),(-0.01,.005),(.02,.04),(.01,-.005)))


# This fixture alone composes stock five-contract LIMIT depth with the existing
# zero-impact MARKET diagnostic. It is not a production liquidity model.
from nautilus_trader.backtest.models import FillModel,LimitOrderPartialFillModel
from coinmaster.research.native_full_fill import ZeroImpactFullFillDiagnostic
STOCK_LIMIT_TOUCH_DEPTH=D(5)
TEST_NATIVE_REDUCTION_CAP=2*STOCK_LIMIT_TOUCH_DEPTH
CANCEL_LATENCY_NS=120_000_000_000

class V4PartialModel(ZeroImpactFullFillDiagnostic):
    def __init__(self):
        # ZeroImpactFullFillDiagnostic normally prohibits touches. This explicit
        # stock-partial fixture requires touch fills; MARKET hook is unchanged.
        FillModel.__init__(self,prob_fill_on_limit=1.0,prob_slippage=0.0)
        self.stock=LimitOrderPartialFillModel()
    def get_orderbook_for_fill_simulation(self,instrument,order,best_bid,best_ask):
        from nautilus_trader.model.enums import OrderType
        if order.order_type==OrderType.LIMIT:
            return self.stock.get_orderbook_for_fill_simulation(instrument,order,best_bid,best_ask)
        return super().get_orderbook_for_fill_simulation(instrument,order,best_bid,best_ask)

def finite_reduction_witness_quantity(actual,target):
    # Only a currently admitted long reduction. Never create a target or right.
    if actual<=0 or target<0 or target>=actual:return D(0)
    return min(TEST_NATIVE_REDUCTION_CAP,actual-target,actual)

def witness_clock(mode):
    # All values are relative to START_NS; actual events still determine PASS.
    if mode=='btc_trim':return dict(submit=122*MINUTE_NS+1,cancel=123*MINUTE_NS+1,touch=124*MINUTE_NS+1_000_000_000,revert=124*MINUTE_NS+2_000_000_000,price=D(1010))
    return dict(submit=182*MINUTE_NS+1,cancel=190*MINUTE_NS,touch=191*MINUTE_NS+1_000_000_000,revert=191*MINUTE_NS+2_000_000_000,price=D(1200))

def test_policy(fixture_id):
    if fixture_id == EMERGENCY_FIXTURE_ID:
        return replace(TEST_ONLY_POLICY,emergency_drawdown_fraction=.40)
    if fixture_id == TRIM_FIXTURE_ID:
        return replace(TEST_ONLY_POLICY,mode='btc_trim',restore_band_atr=2,restore_lifetime_ns=HOUR_NS)
    if fixture_id != FIXTURE_ID:raise ValueError('CM2_V4_UNKNOWN_VARIANT')
    return TEST_ONLY_POLICY

def fixed_feature(hour,mode='joint'):
    rows={0:(1010,1005,990,-2,-.02),1:(1000,1010,990,-2,-.02),
        2:(1020,1010,990,-2,-.02),3:(1070,1080,990,-2,-.02),
        4:(950,1010,960,2,.02),5:(950,1010,960,2,.02),
        6:(880,970,870,2,.02),7:(880,970,870,2,.02),
        8:(980,990,870,0,-.01),9:(980,990,870,0,-.01),
        10:(980,990,870,0,-.01),11:(980,990,870,0,-.01)}
    if mode == 'btc_trim' and hour in (3,4):rows[hour]=(1000,1010,990,0,.01)
    close,hi,lo,z,r=rows[hour];t=START_NS+hour*HOUR_NS
    return Features(t,t,True,close=close,channel_high=hi,channel_low=lo,atr=10,execution_atr=10,
        beta=1,beta_guard=1,rho=.8,residual_z=z,btc_return6=r,hedge_valid=True,
        covariance_ratio=.75)

def prices(minute,mode="joint"):
    btc=D(1000) if minute<121 else D(1020) if minute==121 else D(999) if minute<180 else D(1070) if minute<=190 else D(950) if minute<360 else D(880) if minute<480 else D(980)
    sol=D(100) if minute<180 else D(90) if minute<=190 else D(100) if minute<360 else D(110) if minute<480 else D(300) if minute==570 else D(190) if minute>570 else D(100)
    if mode == 'btc_trim' and 180<=minute<=270:btc,sol=D(1000),D(100)
    if mode == 'btc_trim' and 271<=minute<360:btc,sol=D(950),D(100)
    return btc,sol

def run_fixture(request):
    fixture_id=request.get('fixture_id')
    if fixture_id not in FIXTURE_IDS or (request.get('start_ns'),request.get('end_ns'))!=(START_NS,END_NS):
        raise ValueError('CM2_EXPLICIT_V4_12H_CONTRACT_REQUIRED')
    policy=test_policy(fixture_id);mode=policy.mode
    emergency_case=fixture_id==EMERGENCY_FIXTURE_ID
    invalid_minute=270 if mode=='btc_trim' else 190
    if json.dumps(request.get('fixture_policy'),sort_keys=True)!=json.dumps(asdict(policy),sort_keys=True):
        raise ValueError('CM2_V4_EXPLICIT_TEST_ONLY_POLICY_REQUIRED')
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.config import LoggingConfig
    from nautilus_trader.backtest.models import LimitOrderPartialFillModel,LatencyModel
    from nautilus_trader.core.data import Data
    from nautilus_trader.model.data import CustomData,DataType,BarType,BarSpecification
    from nautilus_trader.model.enums import AccountType,OmsType,OrderType,TimeInForce,OrderSide,BarAggregation,PriceType,AggregationSource
    from nautilus_trader.model.identifiers import ClientId
    from nautilus_trader.model.objects import Money
    from coinmaster.strategy.cm2_native import CM2Strategy,CM2StrategyConfig,minute_turnover
    from coinmaster.strategy.cm2_execution import ExecutionLimits
    from coinmaster.strategy.cm2_checkpoint import NativeCheckpointStore,observer_continuity,canonical
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    from coinmaster.research.native_full_fill import ZeroImpactFullFillDiagnostic,zero_impact_venue_options
    from coinmaster.research.native_fixture import FundingInstruction,PerpetualFundingModule,BybitTierMarginModule,instrument_quote
    from coinmaster.ledger.journal import NativeEventJournal
    from coinmaster.venues.marks import venue_mark,venue_mark_data_type
    from coinmaster.research.native_accounting import native_position_lifecycles
    from coinmaster.research.cm2_fixture_validation import canceled_native_order
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
    recorder=NativeMinuteRiskRecorder(output/'fixture-minute-native-risk.csv.gz',seed,(btc,sol),selected,END_NS,margin_policy=profile.margin_policy(120_000_000_000))
    class Input(Data):
        def __init__(self,ns,feature=None,action=''):self.ns=ns;self.feature=feature;self.action=action
        @property
        def ts_event(self):return self.ns
        @property
        def ts_init(self):return self.ns
    input_type=DataType(Input)
    class FixtureStrategy(CM2Strategy):
        def __init__(self,config):super().__init__(config);self.samples={};self.replays=[];self.dust_seed=None;self.late_sentinel=None;self.trim_sentinel=None;self.cancel_requests=[];self.cancel_outcomes=[];self.native_fill_states=[];self.stop_transitions=[];self.emergency_observations=[];self.initial_emergency_seed=None
        def on_start(self):
            super().on_start();self.subscribe_data(input_type,client_id=ClientId('CM2_V4'))
            self.initial_emergency_seed=asdict(self.policy_state) if emergency_case else None
        def cancel_order(self,order,*args,**kwargs):
            self.cancel_requests.append({'oid':str(order.client_order_id),'ns':self.clock.timestamp_ns()})
            return super().cancel_order(order,*args,**kwargs)
        def on_order_canceled(self,event):
            self.cancel_outcomes.append({'oid':str(event.client_order_id),'ns':event.ts_event,'kind':'CANCELED'})
            super().on_order_canceled(event)
        def on_order_cancel_rejected(self,event):
            self.cancel_outcomes.append({'oid':str(event.client_order_id),'ns':event.ts_event,'kind':'CANCEL_REJECTED'})
            super().on_order_cancel_rejected(event)
        def on_order_filled(self,event):
            self.native_fill_states.append({'oid':str(event.client_order_id),'ns':event.ts_event,'draining':self.policy_state.draining,'parent':self.policy_state.parent,'initial_band_width':str(self.policy_state.initial_band_width),'execution_atr':self.current_features.execution_atr,'core_stop_atr':self.current_features.atr})
            super().on_order_filled(event)
        def _observe_emergency_transition(self,before,callback):
            if emergency_case and not before.emergency_latched and self.policy_state.emergency_latched:
                self.emergency_observations.append({'native_clock_ns':str(self.clock.timestamp_ns()),'callback':callback,
                    'state':asdict(self.policy_state),'actual_drain':dict(self._drain) if self._drain else None,
                    'scope':'AFTER_ACTUAL_PRODUCT_CALLBACK_BEFORE_NEXT_EXTERNAL_EVENT'})
        def on_quote_tick(self,tick):
            before=self.policy_state
            super().on_quote_tick(tick)
            self._observe_emergency_transition(before,'on_quote_tick')
            if not before.draining and self.policy_state.draining:
                self.stop_transitions.append({'ns':self.clock.timestamp_ns(),'old_stop':before.stop,'hedge_valid':self.current_features.hedge_valid,'btc_target':str(self.policy_state.btc_target)})
        def _late_harvest(self,now):
            st=self.policy_state;s=self._snapshot(now)
            if (st.btc_intent!='POSITIVE_HARVEST' or st.harvest_target is None
                    or st.draining or s.btc_qty<=0 or self._orders(btc.id)):
                self.late_sentinel={'status':'NOT_REACHED','reason':'ACTUAL_FINITE_HARVEST_NOT_AVAILABLE'};return
            allowed,why=btc_child_permission(self.config.policy,self.current_features,s,st,now_ns=now,executable_price=s.btc_mark)
            if not allowed:
                self.late_sentinel={'status':'NOT_REACHED','reason':why};return
            remaining=max(D(0),abs(s.btc_qty)-abs(st.harvest_target))
            qty=btc.make_qty(finite_reduction_witness_quantity(s.btc_qty,st.harvest_target))
            if qty.as_decimal()<=STOCK_LIMIT_TOUCH_DEPTH:
                self.late_sentinel={'status':'NOT_REACHED','reason':'FINITE_BUDGET_NOT_ABOVE_STOCK_DEPTH'};return
            if qty.as_decimal()*D(1200)<10:
                self.late_sentinel={'status':'NOT_REACHED','reason':'ACTUAL_HARVEST_REMAINDER_BELOW_MIN'};return
            order=self.order_factory.limit(instrument_id=btc.id,order_side=OrderSide.SELL,
                quantity=qty,price=btc.make_price('1200'),time_in_force=TimeInForce.GTC,reduce_only=True)
            oid=str(order.client_order_id)
            admission=self._permission_context(now,self.current_features,s,st,s.btc_mark,True,'TESTONLY_V4_LATE_WORKING_HARVEST')
            admission.update(test_only=True,native_factory='EXPLICIT_GTC_NOT_PRODUCTION_IOC')
            self._owned[oid]={'instrument_id':btc.id,'client_order_id':order.client_order_id,'submit_ns':now,'acked':False,'terminal':False}
            self._order_audit[oid]={'client_order_id':oid,'instrument':str(btc.id),'action':'BTC','reason':'TESTONLY_V4_LATE_WORKING_HARVEST','submit_ns':str(now),'decision_ns':str(self.current_features.available_ns),'quantity':str(qty),'reduce_only':True,'admission':admission}
            self.late_sentinel={'status':'SUBMITTED_NOT_ASSUMED_FILLED','client_order_id':oid,'original_parent':st.parent,'finite_remaining_budget':str(remaining)}
            self._chain_audit('FIXTURE_SENTINEL',self._order_audit[oid]);self._persist_checkpoint();self.submit_order(order)
        def _trim_partial(self,now):
            st=self.policy_state;s=self._snapshot(now)
            if (mode!='btc_trim' or st.btc_intent!='RISK_TRIM' or st.draining
                    or not s.ownership_known or s.unknown_orders or self._orders(btc.id)):
                self.trim_sentinel={'status':'NOT_REACHED','reason':'ACTUAL_FINITE_TRIM_NOT_AVAILABLE'};return
            qty=btc.make_qty(finite_reduction_witness_quantity(s.btc_qty,st.btc_target))
            if qty.as_decimal()<=STOCK_LIMIT_TOUCH_DEPTH:
                self.trim_sentinel={'status':'NOT_REACHED','reason':'FINITE_TRIM_NOT_ABOVE_STOCK_DEPTH'};return
            order=self.order_factory.limit(instrument_id=btc.id,order_side=OrderSide.SELL,
                quantity=qty,price=btc.make_price(str(witness_clock(mode)['price'])),time_in_force=TimeInForce.GTC,reduce_only=True)
            oid=str(order.client_order_id)
            admission=self._permission_context(now,self.current_features,s,st,s.btc_mark,True,'TESTONLY_V4_FINITE_MATCHED_TRIM')
            admission.update(test_only=True,native_factory='EXPLICIT_GTC_NOT_PRODUCTION_IOC')
            self._owned[oid]={'instrument_id':btc.id,'client_order_id':order.client_order_id,'submit_ns':now,'acked':False,'terminal':False}
            self._order_audit[oid]={'client_order_id':oid,'instrument':str(btc.id),'action':'BTC','reason':'TESTONLY_V4_FINITE_MATCHED_TRIM','submit_ns':str(now),'decision_ns':str(self.current_features.available_ns),'quantity':str(qty),'reduce_only':True,'admission':admission}
            self.trim_sentinel={'status':'SUBMITTED_NOT_ASSUMED_FILLED','client_order_id':oid,'original_parent':st.parent,'finite_remaining_budget':str(s.btc_qty-st.btc_target),'actual_native_quantity':str(s.btc_qty),'actual_admitted_target':str(st.btc_target)}
            self._chain_audit('FIXTURE_SENTINEL',self._order_audit[oid]);self._persist_checkpoint();self.submit_order(order)
        def on_data(self,data):
            value=getattr(data,'data',data)
            if not isinstance(value,Input):
                before=self.policy_state
                result=super().on_data(data)
                self._observe_emergency_transition(before,'on_data')
                return result
            if value.feature is not None:self.current_features=value.feature
            if value.action=='LATE_HARVEST':self._late_harvest(value.ns)
            if value.action=='TRIM_PARTIAL':self._trim_partial(value.ns)
            if value.action=='TRIM_PARTIAL_CANCEL':
                oid=(self.trim_sentinel or {}).get('client_order_id')
                for order in self._orders(btc.id):
                    if str(order.client_order_id)==oid:self.cancel_order(order)
            if value.action=='REPLAY':
                before=canonical(self._checkpoint_document());saved=self.save();native=canonical(self._native_checkpoint_binding())
                self.load(saved)
                self.replays.append({'same_domain':before==canonical(self._checkpoint_document()),'same_native':native==canonical(self._native_checkpoint_binding()),'scope':'SAME_ENGINE_RETAINED_FEEDS_NOT_COLD'})
            if value.action=='DUST_SEED' and not emergency_case:
                s=self._snapshot(value.ns)
                if s.btc_qty or s.sol_qty or self._orders(btc.id) or self._orders(sol.id):
                    self.dust_seed={'status':'NOT_REACHED','reason':'ACTUAL_INVENTORY_NOT_FLAT'}
                else:
                    # Independent TESTONLY native order establishes actual known dust.
                    order=self.order_factory.market(instrument_id=sol.id,order_side=OrderSide.BUY,quantity=sol.make_qty('.04'),time_in_force=TimeInForce.IOC)
                    oid=str(order.client_order_id)
                    self._owned[oid]={'instrument_id':sol.id,'client_order_id':order.client_order_id,'submit_ns':value.ns,'acked':False,'terminal':False}
                    self._order_audit[oid]={'client_order_id':oid,'instrument':str(sol.id),'action':'SOL','reason':'TESTONLY_V4_DUST_SEED','submit_ns':str(value.ns),'decision_ns':str(value.ns),'quantity':'.04','reduce_only':False,'admission':{'intent':'FIXTURE_SENTINEL','test_only':True}}
                    self.dust_seed={'status':'SUBMITTED_NOT_ASSUMED_FILLED','client_order_id':oid}
                    self._chain_audit('FIXTURE_SENTINEL',self._order_audit[oid]);self._persist_checkpoint();self.submit_order(order)
            if value.action in ('SAMPLE','DUST_SEED','REPLAY'):
                s=self._snapshot(value.ns)
                self.samples[str((value.ns-START_NS)//MINUTE_NS)]={'btc':str(s.btc_qty),'sol':str(s.sol_qty),'btc_target':str(self.policy_state.btc_target),'sol_target':str(self.policy_state.sol_target),'intent':self.policy_state.btc_intent,'draining':self.policy_state.draining,'blockers':dict(self.target_blockers),'initial_band_width':str(self.policy_state.initial_band_width),'execution_atr':self.current_features.execution_atr}
    funding=tuple(FundingInstruction('v4-'+str(m)+'-'+str(i.id),i.id,D('.0001'),START_NS+m*MINUTE_NS,prices(m,mode)[0 if i==btc else 1]) for m in (150,450) for i in (btc,sol))
    modules=[PerpetualFundingModule(funding,journal),BybitTierMarginModule((),tuple(selected.items()),120_000_000_000,margin_policy=profile.margin_policy(120_000_000_000),settlement_currency=btc.settlement_currency),observer]
    Observed=observed_neutral_strategy_type(FixtureStrategy,recorder);engine=None
    try:
        # API0 intercepts this ACTUAL public-dispatched constructor; never substitutes source.
        engine=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR'),run_analysis=False))
        engine.add_venue(venue=btc.id.venue,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,starting_balances=[Money(seed,btc.settlement_currency)],base_currency=btc.settlement_currency,default_leverage=D(1),leverages=selected,modules=modules,bar_execution=False,use_message_queue=True,latency_model=LatencyModel(base_latency_nanos=0,cancel_latency_nanos=120_000_000_000),**zero_impact_venue_options(V4PartialModel()))
        for i in (btc,sol):engine.add_instrument(i)
        bt={i.id:BarType(i.id,BarSpecification(1,BarAggregation.MINUTE,PriceType.LAST),AggregationSource.EXTERNAL) for i in (btc,sol)}
        reader=lambda iid:sum((D(row[5]) for row in journal.funding_cash_audit() if row[1]==str(iid)),D(0))
        strategy=Observed(CM2StrategyConfig(btc_id=btc.id,sol_id=sol.id,btc_bar_type=bt[btc.id],sol_bar_type=bt[sol.id],btc_mark_data_type=venue_mark_data_type(btc.id),sol_mark_data_type=venue_mark_data_type(sol.id),mark_client_id=ClientId('CM2_V4'),policy=policy,limits=ExecutionLimits(D(1000)),margin_policy=profile.margin_policy(120_000_000_000),trading_start_open_ns=START_NS,terminal_close_at_ns=END_NS,funding_reader=reader,execution_policy_hash='CM2_V4_PREP_SYNTHETIC_NOT_ECONOMICS',checkpoint_store=store,continuity_reader=lambda:observer_continuity(recorder,observer)))
        engine.add_strategy(strategy)
        inputs=[CustomData(input_type,Input(START_NS+h*HOUR_NS,feature=fixed_feature(h,mode))) for h in range(12)]
        inputs.append(CustomData(input_type,Input(START_NS+invalid_minute*MINUTE_NS,feature=replace(fixed_feature(4 if mode=='btc_trim' else 3,mode),available_ns=START_NS+invalid_minute*MINUTE_NS,hedge_valid=False,hedge_data_known=False,reason='TESTONLY_OPTIONAL_SOL_UNAVAILABLE'))))
        for m in (120,121,122,123,150,181,190,191,192,240,241,250,260,270,271,272,400,450,481,570,571,574,719):
            action='REPLAY' if m==400 else 'DUST_SEED' if m==570 and not emergency_case else 'SAMPLE'
            inputs.append(CustomData(input_type,Input(START_NS+m*MINUTE_NS+1,action=action)))
        clock=witness_clock(mode)
        if mode=='joint':inputs.append(CustomData(input_type,Input(START_NS+clock['submit'],action='LATE_HARVEST')))
        else:
            inputs.extend(CustomData(input_type,Input(START_NS+clock[k],action=action)) for k,action in (('submit','TRIM_PARTIAL'),('cancel','TRIM_PARTIAL_CANCEL')))
        marks=[];quotes=[];bundles=[]
        for m in range(1,721):
            ns=START_NS+m*MINUTE_NS;bp,sp=prices(m,mode)
            for i,px in ((btc,bp),(sol,sp)):
                marks.extend((minute_turnover(i.id,D('1e9'),ns),venue_mark(i.id,px,ns)))
                quotes.append(instrument_quote(i,px,px,ns,size='100000'))
            bar=lambda px:{k:str(px) for k in ('open','high','low','close')}
            bundles.append(SimpleNamespace(open_time_ms=(ns-MINUTE_NS)//1_000_000,btc_mark=bar(bp),sol_mark=bar(sp)))
        for offset,px in ((clock['touch'],clock['price']),(clock['revert'],prices(clock['revert']//MINUTE_NS,mode)[0] if mode=='btc_trim' else D(950))):
            ns=START_NS+offset
            marks.append(venue_mark(btc.id,px,ns))
            quotes.append(instrument_quote(btc,px,px,ns,size='100000'))
        observer.set_week(bundles);recorder.set_week(bundles)
        engine.add_data(inputs,client_id=ClientId('CM2_V4'),sort=False);engine.add_data(marks,client_id=ClientId('CM2_V4'),sort=False);engine.add_data(quotes,sort=False)
        engine.sort_data();engine.run();engine.end()
        coherent=observer.finish_after_engine_end(END_NS);minute_summary=recorder.close();state=strategy.reporting_state()
        fills=state['fill_audit'];orders=engine.cache.orders();partial=[o for o in orders if D(0)<o.filled_qty.as_decimal()<o.quantity.as_decimal()]
        signed=sum((D(r[5]) for r in journal.funding_cash_audit()),D(0));account=engine.cache.account_for_venue(btc.id.venue)
        residue=strategy._snapshot(END_NS)
        def observed(value):return 'PASS' if value else 'NOT_REACHED'
        coverage={}
        # Use native audit/fills, not scheduled events, as proof of actual progress.
        stop_fills=[f for f in fills if f.get('reason')=='PROTECTIVE_STOP']
        coverage['mandatory_stop_between_H1_with_SOL_unavailable']=observed(any(START_NS+invalid_minute*MINUTE_NS < t['ns'] < START_NS+(5 if mode=='btc_trim' else 4)*HOUR_NS and not t['hedge_valid'] and D(t['btc_target'])==0 for t in strategy.stop_transitions))
        coverage['canceled_ADD_retained_actual_hedge']=observed(any(f.get('admission',{}).get('intent')=='FAVORABLE_ADD' for f in fills) and any(v['intent']=='RISK_TRIM' and D(v['sol'])!=0 and D(v['sol_target'])!=0 for k,v in strategy.samples.items() if k in ('122','123')))
        coverage['native_partial_cancel']=observed(any(canceled_native_order(o) for o in partial))
        coverage['bounded_replay']=observed(bool(strategy.replays) and all(r['same_domain'] and r['same_native'] for r in strategy.replays))
        coverage['actual_funding']=observed(len(journal.funding_cash_audit())>0)
        coverage['actual_dust_deadline_unresolved']=observed(residue.sol_qty!=0 and bool(strategy.target_blockers) and (getattr(strategy,'_drain',None) or {}).get('reconcile_required',False))
        oid=(strategy.late_sentinel or {}).get('client_order_id')
        requests=[r['ns'] for r in strategy.cancel_requests if r['oid']==oid]
        outcomes=[r['ns'] for r in strategy.cancel_outcomes if r['oid']==oid]
        late=[f for f in fills if f['client_order_id']==oid and f['original_intent_revoked_at_fill']]
        coverage['forced_native_late_fill']=observed(bool(requests and outcomes and late) and any(min(requests)<int(f['fill_ns'])<min(outcomes) for f in late) and all(f['parent_at_fill']==strategy.late_sentinel['original_parent'] for f in late)) if mode=='joint' else 'NOT_APPLICABLE_JOINT_VARIANT'

        coverage['matched_trim_restore']=observed(any(f.get('admission',{}).get('intent')=='MATCHED_RESTORE' for f in fills)) if mode=='btc_trim' else 'NOT_APPLICABLE_JOINT_VARIANT'
        if mode=='btc_trim':coverage['canceled_ADD_retained_actual_hedge']='NOT_APPLICABLE_NO_SOL_HEDGE_COMPARATOR'
        required=('mandatory_stop_between_H1_with_SOL_unavailable','native_partial_cancel','bounded_replay','actual_funding','actual_dust_deadline_unresolved', 'matched_trim_restore' if mode=='btc_trim' else 'canceled_ADD_retained_actual_hedge')
        if mode=='joint':required=(*required,'forced_native_late_fill')
        emergency_state=asdict(strategy.policy_state) if emergency_case else None
        if emergency_case:
            st=strategy.policy_state;fraction=D(str(policy.emergency_drawdown_fraction))
            trigger_peak=st.emergency_trigger_peak_equity;trigger_equity=st.emergency_trigger_equity
            coverage['seed_initialized_peak']=observed(strategy.initial_emergency_seed['emergency_peak_equity']==seed)
            coverage['dynamic_HWM_emergency_latch']=observed(st.emergency_latched and trigger_peak is not None and trigger_peak>seed
                and trigger_equity is not None and seed*(1-fraction)<trigger_equity<=trigger_peak*(1-fraction)
                and st.emergency_trigger_ns>START_NS and st.emergency_trigger_fraction==fraction)
            coverage['actual_DD_begin_drain']=observed(any(D(o['native_clock_ns'])==st.emergency_trigger_ns
                and o['state']['btc_target']==0 and o['state']['sol_target']==0 and o['actual_drain']
                and set(o['actual_drain']['scoped_zero_ids'])=={str(btc.id),str(sol.id)} for o in strategy.emergency_observations))
            initial_ids={f['client_order_id'] for f in fills if f.get('admission',{}).get('intent')=='INITIAL_ENTRY'}
            coverage['actual_frozen_execution_band']=observed(any(o['oid'] in initial_ids and o['execution_atr']>0
                and D(o['initial_band_width'])==D(str(policy.initial_band_atr))*D(str(o['execution_atr'])) for o in strategy.native_fill_states))
            native_by_id={str(o.client_order_id):o for o in orders}
            reductions={f['instrument'] for f in fills if int(f['fill_ns'])>=st.emergency_trigger_ns
                and native_by_id[f['client_order_id']].is_reduce_only}
            coverage['actual_both_symbol_RO_drain']=observed(reductions=={str(btc.id),str(sol.id)} and residue.btc_qty==0 and residue.sol_qty==0
                and not engine.cache.orders_open() and not engine.cache.orders_inflight())
            after_trigger=[o for o in state['cm2']['order_admission_audit'] if int(o['submit_ns'])>=st.emergency_trigger_ns]
            coverage['post_trigger_no_new_growth_submissions']=observed(bool(after_trigger) and all(o['reduce_only'] for o in after_trigger))
            coverage['native_cash_bridge']=observed(coherent['native_cash_transitions']['status']=='EXACT_OBSERVED_NATIVE_TRANSITIONS')
            coverage['actual_dust_deadline_unresolved']='NOT_APPLICABLE_EMERGENCY_CASE_NO_DUST_SEED'
            coverage['between_mark_cash_trigger']='NOT_OBSERVED_NATIVE_PURE_COUNTEREXAMPLE_CLOSED'
            coverage['same_valuation_MM_breach']='NOT_OBSERVED_NATIVE_PURE_CALLBACK_CASE_CLOSED'
            required=('seed_initialized_peak','dynamic_HWM_emergency_latch','actual_DD_begin_drain','actual_frozen_execution_band',
                'native_partial_cancel','forced_native_late_fill','actual_both_symbol_RO_drain','post_trigger_no_new_growth_submissions',
                'bounded_replay','actual_funding','native_cash_bridge')
        reached=all(coverage[k]=='PASS' for k in required)
        native_orders=[{'client_order_id':str(o.client_order_id),'status':o.status.name,'instrument':str(o.instrument_id),'reduce_only':o.is_reduce_only,'quantity':str(o.quantity),'filled_qty':str(o.filled_qty),'leaves_qty':str(o.leaves_qty),'events':[{'type':type(e).__name__,'ts_event':str(e.ts_event),'last_qty':str(getattr(e,'last_qty','')),'last_px':str(getattr(e,'last_px',''))} for e in o.events]} for o in orders]
        report={'emergency_state':emergency_state,'initial_emergency_seed':strategy.initial_emergency_seed,'emergency_observations':strategy.emergency_observations,'coincident_protective_stop_fills':stop_fills if emergency_case else [],'required_coverage':required,'native_orders':native_orders,'trim_sentinel':strategy.trim_sentinel,'fixture_model_identity':'TESTONLY_STOCK_LIMIT_PARTIAL5_TOUCH1_ZEROIMPACT_MARKET_UNCHANGED','fixture_id':fixture_id,'variant':mode,'status':('PASS_EMERGENCY_COMPONENTS_ENGINEERING_ONLY' if emergency_case else 'PASS_COMPONENTS_EXPECTED_DUST_BLOCKED_NOT_TERMINAL') if reached else 'FAIL_COMPONENT_NOT_REACHED','ranking_eligible':False,'engine_constructors':1,'fixture_policy_test_only':asdict(policy),'coverage':coverage,'samples':strategy.samples,'replays':strategy.replays,'stop_transitions':strategy.stop_transitions,'late_sentinel':strategy.late_sentinel,'cancel_requests':strategy.cancel_requests,'cancel_outcomes':strategy.cancel_outcomes,'native_fill_states':strategy.native_fill_states,'dust_seed':strategy.dust_seed,'native_cash':str(account.balance_total(btc.settlement_currency).as_decimal()),'signed_native_funding':str(signed),'native_residual':{'btc':str(residue.btc_qty),'sol':str(residue.sol_qty),'btc_mark':str(residue.btc_mark),'sol_mark':str(residue.sol_mark)},'terminal_cash_bridge':coherent['native_cash_transitions'] if emergency_case else 'UNKNOWN_NON_FLAT_NO_TERMINAL_TOTAL','native_lifecycles':native_position_lifecycles(engine.cache),'native_adapter':state,'coherent_native_observer':coherent,'minute_native_risk':minute_summary}
        (output/'engineering-report.json').write_text(json.dumps(report,sort_keys=True,default=str)+'\n')
        if not reached:raise ValueError('CM2_V4_REQUIRED_NATIVE_COMPONENT_NOT_REACHED')
        return report
    finally:
        if engine is not None:engine.dispose()
        observer.file.close();recorder.close_writers();journal.close()
