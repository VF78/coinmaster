"""Bounded SYNTHETIC engineering case; actual CM2Strategy/native fills only.

No native class is constructed at import or plan preparation. run_fixture is an
existing runner engineering leaf and requires its separate physical admission.
"""
from dataclasses import asdict
from datetime import datetime,timedelta,timezone
from decimal import Decimal as D
from math import sin
from pathlib import Path
from types import SimpleNamespace
import hashlib,json
from coinmaster.domain.wave_overlay import DailyBar,FeatureState,completed_wave_levels
from coinmaster.strategy.cm2_reference_policy import selected_btc_candidate,DAY,HOUR

FIXTURE_ID='cm2-btc-reference-cycle-native-v1'
TERMINAL_FIXTURE_ID='cm2-btc-reference-terminal-native-v1'
SOL_FIXTURE_ID='cm2-btc-sol-wave-native-v1'
FIXTURE_IDS=(FIXTURE_ID,TERMINAL_FIXTURE_ID,SOL_FIXTURE_ID)
START_NS=1_725_148_800_000_000_000
END_NS=START_NS+4*DAY
MINUTE=60_000_000_000


def fixture_interval(fixture_id):
    if fixture_id==SOL_FIXTURE_ID:return START_NS,START_NS+2*DAY+HOUR
    if fixture_id not in FIXTURE_IDS:raise ValueError("UNKNOWN_BTC_REFERENCE_FIXTURE")
    return START_NS,START_NS+DAY+HOUR if fixture_id==TERMINAL_FIXTURE_ID else END_NS


def fixture_protocol(fixture_id=FIXTURE_ID):
    if fixture_id==SOL_FIXTURE_ID:return joint_fixture_protocol()
    if fixture_id==TERMINAL_FIXTURE_ID:
        return {"schema":"CM2_BTC_REFERENCE_ENGINEERING_TERMINAL_V1","fixture_id":fixture_id,
            "interval":list(fixture_interval(fixture_id)),"engine_count":1,"initial_usdc":"10000",
            "strategy":"ACTUAL_CM2Strategy_NO_NEW_QUOTES_AFTER_END",
            "data":"EXISTING_SYNTHETIC_PAIRED_D1_SEED_AND_M1_MARK_QUOTES",
            "mandatory":["position_open_before_boundary","standing_protection_canceled_at_boundary",
                "native_callback_progress","actual_RO_drain_fill_at_boundary","no_quote_after_boundary",
                "terminal_native_flat_orders_zero","native_fee_currency_and_profile","exact_native_cash_bridge","zero_liquidations"],
            "not_claimed":["actual_partial_fill","actual_late_fill_after_cancel","historical_ROI","new_C1_evidence"],
            "missing_component_policy":"NOT_OBSERVED_IS_NOT_PASS;ROOT_CASE_ACCEPTANCE_REQUIRED",
            "native_constructor_authority":"NONE_FROM_THIS_SOURCE_OR_PREPARATION"}
    if fixture_id!=FIXTURE_ID:raise ValueError("UNKNOWN_BTC_REFERENCE_FIXTURE")
    return {'schema':'CM2_BTC_REFERENCE_ENGINEERING_F01_V1','fixture_id':FIXTURE_ID,
        'interval':[START_NS,END_NS],'engine_count':1,'initial_usdc':'10000',
        'strategy':'ACTUAL_CM2Strategy_ONE_BTC_REFERENCE_OWNER',
        'data':'SYNTHETIC_PAIRED_D1_SEED_AND_INDEPENDENT_CLOSED_D1_SIGNALS;SYNTHETIC_M1_EXECUTION_MARKS',
        'fill':'STOCK_NATIVE_ZERO_IMPACT_ORDER_LEAVES_STRICT_MAKER_TRADE_THROUGH',
        'funding':'SYNTHETIC_INSTRUCTION_POSTED_ONLY_BY_EXISTING_NATIVE_FUNDING_MODULE',
        'mandatory':['entry_ioc','entry_discount_maker','first_completed_PLANREF','positive_tp_ioc',
            'conditional_zero_tp_ioc','tp_maker','native_c1_quarter_cut','actual_cut_credit_restore',
            'native_fee_currency_and_profile','signed_funding_posting','exact_native_cash_bridge',
            'terminal_native_flat_orders_zero','zero_liquidations'],
        'not_claimed':['actual_partial_fill','actual_late_fill_after_cancel','live_capacity','historical_ROI'],
        'missing_component_policy':'NOT_OBSERVED_IS_NOT_PASS;ROOT_CASE_ACCEPTANCE_REQUIRED',
        'native_constructor_authority':'NONE_FROM_THIS_SOURCE_OR_PREPARATION'}


def prepare_plan():
    cfg=selected_btc_candidate();state=FeatureState(cfg);bars=[];signals=[];ohlc=[]
    start=datetime.fromtimestamp(START_NS/1e9,timezone.utc)
    counts={-1:0,1:0};previous=None;forced_open_side=None
    for i in range(730):
        close=60000+(4000+500*((i//32)%5))*sin(i/5)
        sol=150+(close-60000)*.003+.2*sin(i/11)
        opened=start-timedelta(days=730-i)
        op=close*(1+.20*forced_open_side) if forced_open_side is not None else close
        row=DailyBar(opened,opened+timedelta(days=1),opened+timedelta(days=1),op,close,sol)
        feature=state.append(row);bars.append(row);signals.append(feature)
        ohlc.append((int(row.close_time.timestamp()*1e9),max(op,close)*1.001,min(op,close)*.999))
        forced_open_side=None
        if previous is not None and feature.side!=previous:
            counts[feature.side]+=1
            if counts[feature.side]%4==0:forced_open_side=feature.side
        previous=feature.side
    live=DailyBar(start,start+timedelta(days=1),start+timedelta(days=1),60000,60000,150)
    feature=state.append(live)
    levels=completed_wave_levels(bars+[live],signals+[feature],730,cfg,feature.side)
    if feature.beta is None or not .2<feature.beta<4 or levels is None:
        raise ValueError('SYNTHETIC_REFERENCE_FEATURE_PRECONDITION_NOT_MET')
    if not levels[0]==0<levels[1]<levels[2]:
        raise ValueError('SYNTHETIC_CASE_TARGET_CLASSES_NOT_SEPARATE')
    return {'seed':tuple(bars),'seed_ohlc':tuple(ohlc),'side':feature.side,'levels':levels,
        'candidate':cfg,'live_first':live}


def execution_price(plan,minute_index,terminal_case=False):
    side=plan['side'];base=D(60000);q1=D(str(plan['levels'][1]));q2=D(str(plan['levels'][2]))
    elapsed=minute_index-1440
    if terminal_case:return base*(1-D(side)*D('.0035')) if elapsed==3 else base
    if elapsed<3:return base
    if elapsed==3:return base*(1-D(side)*D('.0035'))
    if elapsed<60:return base*(1+D(side)*(q1+D('.001')))
    if elapsed<4*60:return base*(1-D(side)*D('.20'))
    if minute_index<3*1440+120:return base*(1+D(side)*q1/D(2))
    return base*(1+D(side)*(q2+D('.002')))


def run_fixture(request):
    from coinmaster.research.cm2_runner import reference_config,CM2RunConfig,build_strategy
    fixture_id=request.get('fixture_id');start_ns,end_ns=fixture_interval(fixture_id)
    terminal_case=fixture_id==TERMINAL_FIXTURE_ID
    joint_case=fixture_id==SOL_FIXTURE_ID
    if (request.get('start_ns'),request.get('end_ns'))!=(start_ns,end_ns):
        raise ValueError('EXACT_BTC_REFERENCE_FIXTURE_CONTRACT_REQUIRED')
    if joint_case:
        from coinmaster.strategy.cm2_sol_policy import parse_sol_config
        cfg=CM2RunConfig(reference_config(request['policy']),sol_policy=parse_sol_config(request['policy']))
        if cfg.sol_policy is None or not cfg.sol_policy.enabled:raise ValueError('JOINT_ENABLED_SOL_V1_REQUIRED')
        plan=prepare_joint_plan()
    else:
        cfg=CM2RunConfig(reference_config(request['policy']));plan=prepare_plan()
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    current=load_current_hl_diagnostic(Path(request['current_hl_execution_inputs']))
    if any(i.maker_fee!=D('.000144') or i.taker_fee!=D('.000432') for i in current.instruments):
        raise ValueError('ACTUAL_NATIVE_FIXTURE_FEE_PROFILE_MISMATCH')
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.config import LoggingConfig
    # The existing API-boundary probe intercepts HERE, before a Strategy,
    # account, SimulationModule or funding journal is constructed.
    engine=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR')))
    journal=risk=observer=None
    try:
        output=Path(request['artifact_dir']);output.mkdir(parents=True,exist_ok=True)
        if any((output/name).exists() for name in ('fixture-funding.sqlite','fixture-result.json')):
            raise ValueError('FIXTURE_ARTIFACT_EXISTS_NO_REPLAY')
        from coinmaster.ledger.journal import NativeEventJournal
        from coinmaster.research.native_fixture import FundingInstruction,PerpetualFundingModule,BybitTierMarginModule,instrument_quote
        from coinmaster.research.native_full_fill import zero_impact_venue_options
        from coinmaster.research.minute_risk import NativeMinuteRiskRecorder
        from coinmaster.research.paired_observer import CommittedNativeObserver
        from coinmaster.research.native_accounting import native_position_lifecycles
        from coinmaster.venues.marks import venue_mark,venue_mark_data_type
        from coinmaster.venues.signals import daily_signal,daily_signal_data_type
        from coinmaster.strategy.next_band import next_bar_type,next_closed_bar
        from nautilus_trader.backtest.models import MakerTakerFeeModel
        from nautilus_trader.model.enums import OmsType,AccountType,BarAggregation,PriceType,AggregationSource
        from nautilus_trader.model.data import BarType,BarSpecification
        from nautilus_trader.model.identifiers import ClientId,ClientOrderId
        from nautilus_trader.model.objects import Money
        btc,sol=current.instruments;venue=btc.id.venue;seed=D(10000)
        journal=NativeEventJournal(str(output/'fixture-funding.sqlite'))
        funding_time=START_NS+DAY+12*HOUR
        funding_mark=D(149) if joint_case else execution_price(plan,(funding_time-START_NS)//MINUTE-1)
        funding=FundingInstruction('SOL-V1-SYNTHETIC-FUNDING' if joint_case else 'F01-SYNTHETIC-BTC-FUNDING',
            sol.id if joint_case else btc.id,D('.0001'),funding_time,
            settlement_mark=funding_mark,basis='synthetic_mid',synthetic=True)
        risk=NativeMinuteRiskRecorder(output/'minute-native-risk.csv.gz',seed,current.instruments,
            dict(current.selected_leverage),end_ns,margin_policy=current.margin_policy(120_000_000_000))
        observer=CommittedNativeObserver(output/'coherent-native-events.jsonl.gz',seed,current.instruments,journal,end_ns)
        modules=[PerpetualFundingModule((funding,),journal),
            BybitTierMarginModule((),current.selected_leverage,120_000_000_000,
                margin_policy=current.margin_policy(120_000_000_000),settlement_currency=btc.settlement_currency),observer]
        engine.add_venue(venue=venue,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,
            starting_balances=[Money(seed,btc.settlement_currency)],base_currency=btc.settlement_currency,
            default_leverage=D(1),leverages=dict(current.selected_leverage),modules=modules,
            fee_model=MakerTakerFeeModel(),bar_execution=False,**zero_impact_venue_options())
        for instrument in current.instruments:engine.add_instrument(instrument)
        mark_client,signal_client=ClientId('CM2_FIXTURE_MARK'),ClientId('CM2_FIXTURE_SIGNAL')
        minute_bars={i.id:BarType(i.id,BarSpecification(1,BarAggregation.MINUTE,PriceType.LAST),AggregationSource.EXTERNAL) for i in current.instruments}
        strategy=build_strategy(cfg,**fixture_strategy_inputs(plan,current,end_ns=end_ns,
            journal=journal,mark_client=mark_client,signal_client=signal_client,
            minute_bars=minute_bars,risk=risk,observer=observer))
        engine.add_strategy(strategy)
        bundles=[];marks=[];signals=[];h4=[];quotes=[];acc=[];daily_btc=[]
        for index in range((end_ns-START_NS)//MINUTE):
            opened=START_NS+index*MINUTE;ns=opened+MINUTE
            price=joint_execution_price(index) if joint_case else execution_price(plan,index,terminal_case)
            sol_price='149' if joint_case else '150'
            b=dict(open=str(price),high=str(price),low=str(price),close=str(price),turnover='1000000000')
            a=dict(open=sol_price,high=sol_price,low=sol_price,close=sol_price,turnover='1000000000')
            bundles.append(SimpleNamespace(open_time_ms=opened//1_000_000,btc_mark=b,sol_mark=a,btc_execution=b,sol_execution=a))
            marks.extend((venue_mark(btc.id,price,ns),venue_mark(sol.id,D(sol_price),ns)))
            acc.append(price)
            if joint_case:daily_btc.append(price)
            if ns%(4*HOUR)==0:
                h4.append(next_closed_bar(btc.id,4,acc[0],max(acc),min(acc),acc[-1],ns));acc=[]
            if ns%DAY==0:
                # Independent synthetic reference signal stream, fully closed at ns.
                # It is intentionally not a claim about historical D1/M1 parity.
                if joint_case:
                    signals.extend((daily_signal(btc.id,daily_btc[0],max(daily_btc),min(daily_btc),daily_btc[-1],ns),
                        daily_signal(sol.id,D(149),D(149),D(149),D(149),ns)))
                    daily_btc=[]
                else:
                    signals.extend((daily_signal(btc.id,D(60000),D(75000),D(45000),D(60000),ns),
                        daily_signal(sol.id,D(150),D(151),D(149),D(150),ns)))
            quotes.extend((instrument_quote(btc,price,price,ns),instrument_quote(sol,D(sol_price),D(sol_price),ns)))
        risk.set_week(bundles);observer.set_week(bundles)
        engine.add_data(marks,client_id=mark_client,sort=False)
        engine.add_data(signals,client_id=signal_client,sort=False)
        engine.add_data(h4,client_id=signal_client,sort=False)
        engine.add_data(quotes,sort=False);engine.sort_data();engine.run();engine.end()
        coherent=observer.finish_after_engine_end(end_ns);risk_report=risk.close();risk=None
        report=strategy.reporting_state();fills=report['fill_audit'];cycle=report['cm2']['btc_reference']
        cash=engine.cache.account_for_venue(venue).balance_total(btc.settlement_currency).as_decimal()
        life=native_position_lifecycles(engine.cache)
        posted=journal.funding_cash_audit();signed=sum((D(r[5]) for r in posted),D(0))
        realized=sum((D(p['realized_pnl']) for p in life['positions']),D(0)) if not life['unknown'] and all(p['closed'] and p['realized_pnl'] is not None for p in life['positions']) else None
        def seen(action,liquidity=None,reason=None):
            return any(f['action']==action and (liquidity is None or f['native_liquidity_side']==liquidity)
                and (reason is None or f['reason']==reason) for f in fills)
        events=report['cm2']['c1_audit'];kinds={(r['event'],r.get('kind')) for r in events}
        claims=[r for r in events if r['event']=='CLAIM']
        cut_lots=sum(r['lots'] for r in events if r['event']=='ACTUAL_FILL' and r.get('kind')=='CUT')
        restored_lots=sum(r['lots'] for r in events if r['event']=='ACTUAL_FILL' and r.get('kind')=='RESTORE')
        first_fills=[f for f in fills if f['action']=='ENTRY_IOC']
        first_qty=sum((D(f['qty']) for f in first_fills),D(0))
        first_value=sum((D(f['qty'])*D(f['px']) for f in first_fills),D(0))
        parent=cycle['parent']
        planref_exact=parent is not None and first_qty>0 and D(parent['first_quantity'])==first_qty and D(parent['planref'])==first_value/first_qty
        checks={'entry_ioc':seen('ENTRY_IOC','TAKER'),'entry_discount_maker':seen('ENTRY_DISCOUNT','MAKER'),
            'first_completed_PLANREF':planref_exact,
            'positive_tp_ioc':seen('TP_IOC','TAKER','BTC_POSITIVE_TP_CATCHUP'),
            'conditional_zero_tp_ioc':any(f['action']=='TP_IOC' and f['reason']=='BTC_CONDITIONAL_TP' and f['level']==0 and f['native_liquidity_side']=='TAKER' for f in fills),
            'tp_maker':seen('TP_GTC','MAKER'),'native_c1_quarter_cut':bool(claims) and all(r['cut_lots']==r['held_lots']//4 for r in claims) and cut_lots==sum(r['cut_lots'] for r in claims),
            'actual_cut_credit_restore':cut_lots>0 and cut_lots==restored_lots and cycle['c1'] is not None and cycle['c1']['credit']==0,
            'native_fee_currency_and_profile':bool(fills) and all(f['commission_currency']=='USDC' for f in fills),
            'signed_funding_posting':bool(posted) and all(D(r[4])-D(r[3])==D(r[5]) for r in posted),
            'exact_native_cash_bridge':realized is not None and cash-seed-realized-signed==0,
            'terminal_native_flat_orders_zero':not engine.cache.positions_open() and not engine.cache.orders_open() and not engine.cache.orders_inflight() and not strategy._owned,
            'zero_liquidations':len(strategy.liquidation_audit)==0}
        if terminal_case:
            entries=[f for f in fills if f['action'].startswith('ENTRY')]
            reductions=[f for f in fills if not f['action'].startswith('ENTRY')]
            protection=[]
            for oid,info in strategy._order_audit.items():
                if info['purpose']!='TP_GTC':continue
                order=engine.cache.order(ClientOrderId(oid))
                if order is None:continue
                accepted=any(type(e).__name__=='OrderAccepted' and e.ts_event<end_ns for e in order.events)
                canceled=any(type(e).__name__=='OrderCanceled' and e.ts_event==end_ns for e in order.events)
                protection.append(accepted and canceled and order.filled_qty.as_decimal()==0)
            drains=[f for f in fills if f['action']=='DRAIN']
            checks={'position_open_before_boundary':bool(entries) and all(int(f['fill_ns'])<end_ns for f in entries)
                    and not any(int(f['fill_ns'])<end_ns for f in reductions),
                'standing_protection_canceled_at_boundary':any(protection),
                'native_callback_progress':any(r['event']=='NATIVE_CALLBACK_PROGRESS' and r['timestamp_ns']==end_ns for r in strategy.drain_audit),
                'actual_RO_drain_fill_at_boundary':bool(drains) and all(int(f['fill_ns'])==end_ns and
                    strategy._order_audit[f['client_order_id']]['reduce_only'] is True for f in drains),
                'no_quote_after_boundary':max(q.ts_event for q in quotes)==end_ns,
                'terminal_native_flat_orders_zero':checks['terminal_native_flat_orders_zero'],
                'native_fee_currency_and_profile':checks['native_fee_currency_and_profile'],
                'exact_native_cash_bridge':checks['exact_native_cash_bridge'],'zero_liquidations':checks['zero_liquidations']}
        result={'status':'CASE_COMPONENT_GATES_PASS' if all(checks.values()) else 'CASE_COMPONENTS_NOT_OBSERVED_OR_FAILED',
            'fixture_id':fixture_id,'fixture_protocol':fixture_protocol(fixture_id),'checks':checks,
            'native_engine_constructions':1,'terminal_cash':str(cash),'native_realized':str(realized) if realized is not None else None,
            'signed_funding':str(signed),'native_commissions':str(sum((D(f['commission']) for f in fills),D(0))),
            'native_strategy_events':report,'native_position_lifecycles':life,'funding_cash_audit':posted,
            'coherent_native_observer':coherent,'minute_risk_observations':risk_report,
            'actual_partial_and_latefill':'NOT_OBSERVED_IN_FULL_FILL_CASE;PURE_EVENT_FIXTURES_SEPARATE',
            'economic_claim':'NONE_SYNTHETIC_ENGINEERING_ONLY',
            'source_sha256':{'fixture':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'actual_strategy':hashlib.sha256(Path(__file__).parents[1].joinpath('strategy/cm2_native.py').read_bytes()).hexdigest()}}
        if joint_case:
            result['status']='NATIVE_EXPORTS_COMPLETE_JOINT_GATES_PENDING'
            result['checks']={name:False for name in joint_fixture_protocol()['mandatory']}
            result['joint_profile']={'btc_id':str(btc.id),'sol_id':str(sol.id),'sol_lot':str(sol.size_increment.as_decimal())}
            result['joint_native_orders']={}
            for oid in strategy._order_audit:
                order=engine.cache.order(ClientOrderId(oid))
                if order is not None:
                    result['joint_native_orders'][oid]={'quantity':str(order.quantity.as_decimal()),
                        'filled_quantity':str(order.filled_qty.as_decimal()),'closed':bool(order.is_closed),
                        'reduce_only':bool(order.is_reduce_only)}
            (output/'fixture-result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        else:
            (output/'fixture-result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
            if not all(checks.values()):raise ValueError('F01_MANDATORY_COMPONENT_NOT_PROVEN:'+','.join(k for k,v in checks.items() if not v))
            return result
    finally:
        try:
            if risk is not None:risk.close_writers()
        finally:
            try:
                if observer is not None:observer.close()
            finally:
                try:engine.dispose()
                finally:
                    if journal is not None:journal.close()

    # The joint leaf reads complete artifacts only AFTER the unchanged cleanup.
    return finalize_joint_fixture(result,output,plan,end_ns)


def joint_fixture_protocol():
    return {'schema':'CM2_BTC_SOL_WAVE_ENGINEERING_V1','fixture_id':SOL_FIXTURE_ID,
        'interval':list(fixture_interval(SOL_FIXTURE_ID)),'engine_count':1,'initial_usdc':'10000',
        'strategy':'ACTUAL_CM2Strategy_SHARED_NATIVE_BTC_SOL_V1',
        'data':'DECLARED_SYNTHETIC_PRICE_STRINGS_730D_SEED_61_EXACT_PAIRS_AND_CONSISTENT_CLOSED_D1_M1',
        'fill':'EXISTING_STOCK_NATIVE_ZERO_IMPACT_ORDER_LEAVES',
        'funding':'ONE_SYNTHETIC_SOL_EVENT_EXISTING_NATIVE_FUNDING_MODULE_ONLY',
        'mandatory':['genuine_PLANREF_exhaustion_entry_context','SOL_current_BTC_over_K_full_parent_lot_permission',
            'actual_SOL_native_entry','BTC_TP_flat_SOL_held_quote','frozen_episode_K',
            'pure_REGIME_SOL_scoped_exit','actual_SOL_funding_posting','native_fee_currency_and_profile',
            'exact_native_cash_bridge','new_BTC_GLOBAL_terminal_drain','terminal_native_flat_orders_zero',
            'zero_liquidations','gzip_EOF_CRC_schema'],
        'not_claimed':['actual_partial_fill','actual_late_fill_after_cancel','historical_ROI','live_capacity'],
        'missing_component_policy':'NOT_OBSERVED_IS_NOT_PASS;ROOT_CASE_ACCEPTANCE_REQUIRED',
        'native_constructor_authority':'NONE_FROM_SOURCE_OR_PREPARATION'}


def declared_joint_closes():
    """Synthetic generator strings are the declared sources, NOT str(seed floats)."""
    result=[]
    for i in range(730):
        generated_btc=60000+(4000+500*((i//32)%5))*sin(i/5)
        generated_sol=150+(generated_btc-60000)*.003+.2*sin(i/11)
        btc_source,sol_source=repr(generated_btc),repr(generated_sol)
        result.append((START_NS-(729-i)*DAY,btc_source,sol_source))
    return tuple(result)


def prepare_joint_plan():
    from coinmaster.strategy.cm2_sol_volatility import PairedDailyClose,daily_volatility_coefficient
    sources=declared_joint_closes()  # Capture strings before float API conversion.
    plan=prepare_plan()
    if not all(float(b)==row.btc_close and float(s)==row.sol_close for (_,b,s),row in zip(sources,plan['seed'])):
        raise ValueError('DECLARED_SYNTHETIC_SEED_DRIFT')
    state=FeatureState(plan['candidate']);features=[]
    for row in plan['seed']:features.append(state.append(row))
    start=datetime.fromtimestamp(START_NS/1e9,timezone.utc)
    first=DailyBar(start,start+timedelta(days=1),start+timedelta(days=1),float('60000'),float('60000'),float('149'))
    second=DailyBar(start+timedelta(days=1),start+timedelta(days=2),start+timedelta(days=2),float('60000'),float('65000'),float('149'))
    f1=state.append(first)
    levels=completed_wave_levels(list(plan['seed'])+[first],features+[f1],730,plan['candidate'],f1.side)
    if levels!=plan['levels']:raise ValueError('FIXED_JOINT_SOURCE_WAVE_LEVEL_DRIFT')
    f2=state.append(second)
    history=[PairedDailyClose(*r) for r in sources[-60:]]+[PairedDailyClose(START_NS+DAY,'60000','149')]
    k=daily_volatility_coefficient(history,decision_ns=START_NS+DAY+MINUTE)
    if (f1.side!=-1 or f1.z is None or f1.side*f1.z<1.25 or f1.sigma is None or f1.sigma<=0
            or k is None or f2.side!=1):raise ValueError('FIXED_JOINT_MARKET_PRECONDITIONS_NOT_MET')
    plan.update(seed_paired_closes=sources[-61:],joint_first=asdict(f1),joint_second=asdict(f2),
        joint_k=str(k),joint_source='DECLARED_FIXED_SIN_SYNTHETIC_STRINGS_BEFORE_FLOAT_API')
    return plan


def joint_execution_price(minute_index):
    if minute_index>=2*1440-1:return D(65000)
    if minute_index==1440+3:return D(60210)
    if minute_index>=1440+5:return D(54500)
    return D(60000)


def fixture_strategy_inputs(plan,current,*,end_ns,journal,mark_client,signal_client,minute_bars,risk,observer):
    """One actual leaf/config seam reused by the constructor-free boundary test."""
    from coinmaster.venues.marks import venue_mark_data_type
    from coinmaster.venues.signals import daily_signal_data_type
    from coinmaster.strategy.next_band import next_bar_type
    btc,sol=current.instruments
    result=dict(instruments=current.instruments,minute_bars=minute_bars,
        margin_policy=current.margin_policy(120_000_000_000),start_ns=START_NS,end_ns=end_ns,
        mark_types=tuple(venue_mark_data_type(i.id) for i in current.instruments),mark_client=mark_client,
        journal=journal,exit_fee_rate=D('.000432'),execution_hash='SYNTHETIC_F01_ZERO_IMPACT',
        seed_days=plan['seed'],seed_ohlc=plan['seed_ohlc'],
        daily_types=tuple(daily_signal_data_type(i.id) for i in current.instruments),
        h4_type=next_bar_type(btc.id,4),signal_client=signal_client,initial_seed=D(10000),
        risk_recorder=risk,coherent_observer=observer)
    if 'seed_paired_closes' in plan:
        result.update(seed_paired_closes=plan['seed_paired_closes'],execution_hash='SYNTHETIC_SOL_WAVE_V1_ZERO_IMPACT')
    return result


def joint_native_checks(result,rows,plan):
    """Read actual native facts only. No fill/state/PnL synthesis or mutation."""
    from decimal import localcontext,ROUND_HALF_EVEN
    from coinmaster.strategy.cm2_sol_policy import floor_lot
    fills=result['native_strategy_events']['fill_audit'];profile=result['joint_profile']
    btc,sol=profile['btc_id'],profile['sol_id'];orders=result['joint_native_orders']
    audits={r['client_order_id']:r for r in result['native_strategy_events']['cm2']['order_admission_audit']}
    opened=sorted((f for f in fills if f['instrument']==sol and f['action']=='SOL_OPEN'),key=lambda f:int(f['fill_ns']))
    sol_orders=[a for a in audits.values() if a['instrument_id']==sol and 'sol_episode' in a]
    carry=[r for r in rows if r['kind']=='PREQUOTE_DIRECT_NATIVE' and START_NS+DAY<int(r['event_ns'])<START_NS+2*DAY
        and any(p['instrument_id']==sol for p in r['positions']) and not any(p['instrument_id']==btc for p in r['positions'])]
    context=size=False;episode=None;entry_proof={}
    if opened:
        first=opened[0];admission=audits[first['client_order_id']];episode=admission['sol_episode'];accepted=int(episode['accepted_ns'])
        prior=next((r for r in rows if r['kind']=='PRE_FILL_LAST_COMMITTED_NATIVE_COPY' and r['native_id']==first['trade_id']),None)
        bp=next((p for p in prior['positions'] if p['instrument_id']==btc),None) if prior else None
        entries=[f for f in fills if f['instrument']==btc and f['action']=='ENTRY_IOC' and f['parent_id']==episode['sponsor'] and int(f['fill_ns'])<=accepted]
        complete=bool(entries) and all(orders[f['client_order_id']]['closed'] and
            D(orders[f['client_order_id']]['filled_quantity'])==D(orders[f['client_order_id']]['quantity']) for f in entries)
        qty=sum((D(f['qty']) for f in entries),D(0));value=sum((D(f['qty'])*D(f['px']) for f in entries),D(0))
        if bp and complete and qty>0:
            planref=value/qty;side=int(episode['btc_side']);mark=D(bp['raw_mark'])
            wave=any(r['kind']=='PREQUOTE_DIRECT_NATIVE' and max(int(f['fill_ns']) for f in entries)<=int(r['event_ns'])<=accepted
                and any(p['instrument_id']==btc and D(side)*(D(p['raw_mark'])/planref-1)>=D(str(plan['levels'][0])) for p in r['positions']) for r in rows)
            context=(side==plan['joint_first']['side']==-1 and plan['joint_first']['z']*side>=1.25 and wave
                and admission['parent_id']==episode['sponsor'] and bp['side']=='SHORT' and int(first['fill_ns'])>=accepted)
            permission=episode.get('permission')
            try:
                exhaustion=permission['exhaustion']
                signed_btc=D(bp['quantity'])*D(-1 if bp['side']=='SHORT' else 1)
                context=context and (permission['decision_ns']==accepted
                    and permission['daily_close_ns']==START_NS+DAY
                    and permission['daily_close_ns']<=permission['daily_available_ns']<=accepted
                    and D(str(permission['z']))*D(side)>=D('1.25')
                    and D(str(permission['sigma']))==D(episode['sigma'])
                    and D(permission['actual_btc_qty'])==signed_btc
                    and D(permission['coherent_btc_mark'])==mark
                    and D(permission['actual_btc_notional'])==abs(signed_btc*mark)
                    and exhaustion['parent_id']==episode['sponsor'] and exhaustion['side']==side
                    and D(exhaustion['planref'])==planref
                    and exhaustion['source_ns']<=exhaustion['receipt_ns']<=accepted
                    and D(side)*(D(exhaustion['executable_price'])/planref-1)>=D(exhaustion['level'])
                    and D(exhaustion['level'])==D(str(plan['levels'][0])))
            except (KeyError,TypeError,ValueError):context=False
            with localcontext() as ctx:
                ctx.prec=50;ctx.rounding=ROUND_HALF_EVEN
                n=abs(D(bp['quantity'])*mark)/D(episode['k'])
                q=floor_lot(n/D(first['px']),D(profile['sol_lot']))
            native_order=orders[first['client_order_id']]
            size=(D(episode['k'])==D(plan['joint_k']) and D(episode['notional'])==n and D(episode['quantity'])==q
                and D(admission['quantity'])==q==D(native_order['quantity']) and not native_order['reduce_only'])
            entry_proof=dict(native_btc_quantity=bp['quantity'],coherent_btc_mark=str(mark),actual_PLANREF=str(planref),
                actual_episode=episode,expected_notional=str(n),expected_quantity=str(q),native_sol_lot=profile['sol_lot'])
    tp=[f for f in fills if f['instrument']==btc and f['action'].startswith('TP_') and episode is not None and f['parent_id']==episode['sponsor']]
    sponsor_fills=[f for f in fills if episode is not None and f['instrument']==btc and f['parent_id']==episode['sponsor']]
    entry_total=sum((D(f['qty']) for f in sponsor_fills if f['action'].startswith('ENTRY')),D(0))
    tp_total=sum((D(f['qty']) for f in tp),D(0))
    only_tp_reductions=all(f['action'].startswith(('ENTRY','TP_')) for f in sponsor_fills)
    tp_closed_exact=bool(tp) and entry_total>0 and tp_total==entry_total and only_tp_reductions
    carry_after_tp=[r for r in carry if tp_closed_exact and int(r['event_ns'])>max(int(f['fill_ns']) for f in tp)]
    exits=[f for f in fills if f['instrument']==sol and f['action']=='DRAIN']
    drains=result['native_strategy_events']['cm2']['drain_lifecycle']
    scoped=[d for d in drains if d['event']=='START' and d['scope']=='SOL_SUBORDINATE' and d['reason']=='BTC_MARKET_REGIME'
        and d['timestamp_ns']==START_NS+2*DAY and d['state']['scoped_zero_ids']==[sol]]
    posting=[r for r in result['funding_cash_audit'] if r[0]=='SOL-V1-SYNTHETIC-FUNDING' and r[1]==sol]
    funding_state=[r for r in rows if r['kind']=='PRE_FUNDING_COMMITTED_NATIVE_COPY' and r['native_id']=='SOL-V1-SYNTHETIC-FUNDING'
        and any(p['instrument_id']==sol for p in r['positions'])]
    terminal=fixture_interval(SOL_FIXTURE_ID)[1]
    checks={'genuine_PLANREF_exhaustion_entry_context':bool(context),
        'SOL_current_BTC_over_K_full_parent_lot_permission':bool(size),
        'actual_SOL_native_entry':bool(opened) and all(f['order_side']=='BUY' and f['native_liquidity_side']=='TAKER' for f in opened),
        'BTC_TP_flat_SOL_held_quote':bool(tp and carry_after_tp),
        'frozen_episode_K':len(sol_orders)>=2 and episode is not None and all(a['sol_episode']['k']==episode['k'] and a['sol_episode']['sponsor']==episode['sponsor'] and a['sol_episode'].get('permission')==episode.get('permission') for a in sol_orders),
        'pure_REGIME_SOL_scoped_exit':bool(scoped and exits) and plan['joint_second']['side']!=plan['joint_first']['side']
            and all(f['reason']=='BTC_MARKET_REGIME' and START_NS+2*DAY<=int(f['fill_ns'])<terminal and audits[f['client_order_id']]['reduce_only'] for f in exits),
        'actual_SOL_funding_posting':bool(posting and funding_state) and all(int(r[2])==START_NS+DAY+12*HOUR and D(r[5])!=0 and D(r[4])-D(r[3])==D(r[5]) for r in posting),
        'native_fee_currency_and_profile':bool(fills) and all(f['commission_currency']=='USDC' for f in fills),
        'exact_native_cash_bridge':result['native_realized'] is not None and D(result['terminal_cash'])-D(10000)-D(result['native_realized'])-D(result['signed_funding'])==0,
        'new_BTC_GLOBAL_terminal_drain':any(f['instrument']==btc and f['action'].startswith('ENTRY') and int(f['fill_ns'])>=START_NS+2*DAY for f in fills)
            and any(f['instrument']==btc and f['action']=='DRAIN' and int(f['fill_ns'])==terminal for f in fills)
            and any(d['scope']=='GLOBAL' and d['event']=='START' and d['timestamp_ns']==terminal for d in drains),
        'terminal_native_flat_orders_zero':result['native_strategy_events']['terminal_lifecycle']['status']=='FLAT' and result['native_strategy_events']['terminal_open_orders']==0,
        'zero_liquidations':not result['native_strategy_events']['liquidations']}
    evidence={'entry':entry_proof,'carry_quote_count_after_BTC_TP_flat':len(carry_after_tp),
        'opening_and_exit_K_observations':[a['sol_episode']['k'] for a in sol_orders],
        'pure_first_D1':plan['joint_first'],'pure_second_D1':plan['joint_second'],
        'synthetic_source':plan['joint_source']}
    return checks,evidence


def finalize_joint_fixture(result,output,plan,end_ns):
    import gzip
    from coinmaster.research.cm2_runner import engineering_artifact_integrity
    try:
        artifacts=engineering_artifact_integrity(output,result,end_ns)
        with gzip.open(output/'coherent-native-events.jsonl.gz','rt') as stream:rows=[json.loads(line) for line in stream]
        checks,evidence=joint_native_checks(result,rows,plan)
        checks['gzip_EOF_CRC_schema']=set(artifacts)=={'coherent-native-events.jsonl.gz','minute-native-risk.csv.gz','minute-native-settled-receipts.csv.gz'}
        if set(checks)!=set(joint_fixture_protocol()['mandatory']):raise ValueError('JOINT_GATE_SCHEMA_DRIFT')
        result.update(checks=checks,joint_component_evidence=evidence,joint_artifact_integrity=artifacts,
            status='CASE_COMPONENT_GATES_PASS' if all(checks.values()) else 'CASE_COMPONENTS_NOT_OBSERVED_OR_FAILED')
    except BaseException as error:
        result.update(status='JOINT_ARTIFACT_OR_EVIDENCE_FAILED',joint_evidence_error={'type':type(error).__name__,'message':str(error)})
        (output/'fixture-result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        raise
    (output/'fixture-result.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    if not all(checks.values()):raise ValueError('JOINT_MANDATORY_COMPONENT_NOT_PROVEN:'+','.join(k for k,v in checks.items() if not v))
    return result
