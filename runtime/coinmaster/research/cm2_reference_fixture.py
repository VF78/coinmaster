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
FIXTURE_IDS=(FIXTURE_ID,)
START_NS=1_725_148_800_000_000_000
END_NS=START_NS+4*DAY
MINUTE=60_000_000_000


def fixture_protocol():
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


def execution_price(plan,minute_index):
    side=plan['side'];base=D(60000);q1=D(str(plan['levels'][1]));q2=D(str(plan['levels'][2]))
    elapsed=minute_index-1440
    if elapsed<3:return base
    if elapsed==3:return base*(1-D(side)*D('.0035'))
    if elapsed<60:return base*(1+D(side)*(q1+D('.001')))
    if elapsed<4*60:return base*(1-D(side)*D('.20'))
    if minute_index<3*1440+120:return base*(1+D(side)*q1/D(2))
    return base*(1+D(side)*(q2+D('.002')))


def run_fixture(request):
    from coinmaster.research.cm2_runner import reference_config,CM2RunConfig,build_strategy
    if request.get('fixture_id')!=FIXTURE_ID or (request.get('start_ns'),request.get('end_ns'))!=(START_NS,END_NS):
        raise ValueError('EXACT_BTC_REFERENCE_FIXTURE_CONTRACT_REQUIRED')
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
        from nautilus_trader.model.identifiers import ClientId
        from nautilus_trader.model.objects import Money
        btc,sol=current.instruments;venue=btc.id.venue;seed=D(10000)
        journal=NativeEventJournal(str(output/'fixture-funding.sqlite'))
        funding_time=START_NS+DAY+12*HOUR
        funding_mark=execution_price(plan,(funding_time-START_NS)//MINUTE-1)
        funding=FundingInstruction('F01-SYNTHETIC-BTC-FUNDING',btc.id,D('.0001'),funding_time,
            settlement_mark=funding_mark,basis='synthetic_mid',synthetic=True)
        risk=NativeMinuteRiskRecorder(output/'minute-native-risk.csv.gz',seed,current.instruments,
            dict(current.selected_leverage),END_NS,margin_policy=current.margin_policy(120_000_000_000))
        observer=CommittedNativeObserver(output/'coherent-native-events.jsonl.gz',seed,current.instruments,journal,END_NS)
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
        strategy=build_strategy(cfg,instruments=current.instruments,minute_bars=minute_bars,
            margin_policy=current.margin_policy(120_000_000_000),start_ns=START_NS,end_ns=END_NS,
            mark_types=tuple(venue_mark_data_type(i.id) for i in current.instruments),mark_client=mark_client,
            journal=journal,exit_fee_rate=D('.000432'),execution_hash='SYNTHETIC_F01_ZERO_IMPACT',
            seed_days=plan['seed'],seed_ohlc=plan['seed_ohlc'],
            daily_types=tuple(daily_signal_data_type(i.id) for i in current.instruments),
            h4_type=next_bar_type(btc.id,4),signal_client=signal_client,initial_seed=seed,
            risk_recorder=risk,coherent_observer=observer)
        engine.add_strategy(strategy)
        bundles=[];marks=[];signals=[];h4=[];quotes=[];acc=[]
        for index in range(4*1440):
            opened=START_NS+index*MINUTE;ns=opened+MINUTE;price=execution_price(plan,index)
            b=dict(open=str(price),high=str(price),low=str(price),close=str(price),turnover='1000000000')
            a=dict(open='150',high='150',low='150',close='150',turnover='1000000000')
            bundles.append(SimpleNamespace(open_time_ms=opened//1_000_000,btc_mark=b,sol_mark=a,btc_execution=b,sol_execution=a))
            marks.extend((venue_mark(btc.id,price,ns),venue_mark(sol.id,D(150),ns)))
            acc.append(price)
            if ns%(4*HOUR)==0:
                h4.append(next_closed_bar(btc.id,4,acc[0],max(acc),min(acc),acc[-1],ns));acc=[]
            if ns%DAY==0:
                # Independent synthetic reference signal stream, fully closed at ns.
                # It is intentionally not a claim about historical D1/M1 parity.
                signals.extend((daily_signal(btc.id,D(60000),D(75000),D(45000),D(60000),ns),
                    daily_signal(sol.id,D(150),D(151),D(149),D(150),ns)))
            quotes.extend((instrument_quote(btc,price,price,ns),instrument_quote(sol,150,150,ns)))
        risk.set_week(bundles);observer.set_week(bundles)
        engine.add_data(marks,client_id=mark_client,sort=False)
        engine.add_data(signals,client_id=signal_client,sort=False)
        engine.add_data(h4,client_id=signal_client,sort=False)
        engine.add_data(quotes,sort=False);engine.sort_data();engine.run();engine.end()
        coherent=observer.finish_after_engine_end(END_NS);risk_report=risk.close();risk=None
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
        result={'status':'CASE_COMPONENT_GATES_PASS' if all(checks.values()) else 'CASE_COMPONENTS_NOT_OBSERVED_OR_FAILED',
            'fixture_id':FIXTURE_ID,'fixture_protocol':fixture_protocol(),'checks':checks,
            'native_engine_constructions':1,'terminal_cash':str(cash),'native_realized':str(realized) if realized is not None else None,
            'signed_funding':str(signed),'native_commissions':str(sum((D(f['commission']) for f in fills),D(0))),
            'native_strategy_events':report,'native_position_lifecycles':life,'funding_cash_audit':posted,
            'coherent_native_observer':coherent,'minute_risk_observations':risk_report,
            'actual_partial_and_latefill':'NOT_OBSERVED_IN_FULL_FILL_CASE;PURE_EVENT_FIXTURES_SEPARATE',
            'economic_claim':'NONE_SYNTHETIC_ENGINEERING_ONLY',
            'source_sha256':{'fixture':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                'actual_strategy':hashlib.sha256(Path(__file__).parents[1].joinpath('strategy/cm2_native.py').read_bytes()).hexdigest()}}
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
