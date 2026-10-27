"""One root-gated native constructor per immutable M2..M8 case.

prepare() is engine-free. No helper engine, private strategy setter, synthetic
fill/ACK, cash patch or alternate matcher. All outcomes remain unqualified until
root accepts the actual case witnesses and independent consumer result.
"""
from pathlib import Path
from decimal import Decimal as D
from dataclasses import replace as dr,fields
from types import SimpleNamespace as NS
from msgspec.structs import replace
import argparse,json,hashlib,traceback,platform
from importlib.metadata import version
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.models import LatencyModel,MakerTakerFeeModel
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.enums import OmsType,AccountType
from nautilus_trader.model.objects import Money
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP,SIM,perpetual
from coinmaster.research.method_a_margin import MethodATierMarginModule,MethodABookWitness
from coinmaster.research.method_a_risk_rows import MethodARiskRows,wire
from coinmaster.research.paired_observer import CommittedNativeObserver
from coinmaster.research.paired_signal_feed import PairedSignal
from coinmaster.strategy.wave_overlay import MethodAWaveOverlayStrategy
from coinmaster.strategy.native_account_snapshot import native_account_snapshot
from coinmaster.strategy.method_a_risk import DAY,State,evaluate
from coinmaster.strategy import method_a_risk_native
from run_continuous_hedge_preflight import snapshot_config
from run_method_a_m1 import config as m1_config,seed,source_inventory,verify_source,lifecycle,write_json,domain_context
from method_a_sol_public import load_case,prepare_case,native_inputs,canonical

ENGINEERING_CASE_READINESS={'M2':'M2_SOURCE_READY_REQUIRES_EXACT_ROOT_PREFLIGHT_GO_AND_CLAIM'}


def selection(rows):
    decimals={'btc_close','sol_close','a','atr_sol','k_long','k_short','open_o','sigma_btc','sigma_sol','rho'}
    result=[]
    legal={f.name for f in fields(PairedSignal)}
    for raw in rows:
        if set(raw)-legal:raise ValueError('SOL_UNKNOWN_SELECTION_FIELD')
        values={k:D(v) if k in decimals and v is not None else v for k,v in raw.items()}
        item=PairedSignal(**values)
        if item.available_ns<item.decision_ns or item.not_before_ns<item.available_ns+60_000_000_000:raise ValueError('SOL_NONCAUSAL_SELECTION')
        result.append(item)
    if any(a.not_before_ns>b.not_before_ns for a,b in zip(result,result[1:])):raise ValueError('SOL_UNSORTED_SELECTION')
    return tuple(result)


def funding():
    # Declared fixture data only: complete signed zero8h intervals, not a
    # substitution for economic historical funding or native settlement.
    return tuple((leg,t,t,'0',DAY//3) for leg in ('BTC','SOL') for t in range(-31*DAY+DAY//3,1,DAY//3))


def config_for(case,binding,observer=None,book=None):
    cfg,_=m1_config()
    return replace(cfg,candidate=dr(cfg.candidate,sol_overlay_enabled=False),research_sol_off=True,
        research_method_a_risk=case['risk_mode'],research_method_a_funding=funding(),
        research_method_a_selection=selection(case['selection_rows']),research_method_a_input_binding=binding,
        research_method_a_peak_source=observer,research_native_book=book,
        terminal_close_at_ns=case.get('terminal_close_at_ns'))


def prepare(case_path):
    case=load_case(case_path);proof=prepare_case(case_path)
    runtime_versions=dict(python=platform.python_version(),nautilus=version('nautilus_trader'))
    assert runtime_versions['nautilus']=='1.231.0' and runtime_versions['python'].startswith('3.12.'),'SOL_FROZEN_NATIVE_RUNTIME_VERSION'
    sources=source_inventory();binding=dict(source={r['path']:r['sha256'] for r in sources},
        config=dict(case_id=case['case_id'],risk_mode=case['risk_mode'],seed='10000',method_a_tp=True,sol_off=True,standalone_sol_enabled=False),
        data=dict(recipe_sha256=proof['recipe_sha256'],native_input_sha256=proof['native_input_sha256'],seed_sha256=proof['seed_sha256'],expected_quote_universe=proof['quote_universe'],funding_declaration=case['funding_history']),
        policy=dict(BASE_maker='.00020',BASE_taker='.00055',BTC_leverage='40',SOL_leverage='20',stress_consumption=True,stress_bar_execution=False,queue=True,insert_ns=0,update_ns=0,cancel_ns=case['cancel_latency_ns']))
    cfg=config_for(case,binding)
    assert not cfg.candidate.sol_overlay_enabled and cfg.research_method_a_tp and not cfg.research_btc_real_u
    # Observer set_week consumes source timestamps in milliseconds. Every
    # declared fixture mark must roundtrip exactly; no lost native clock bits.
    assert all(r['ns']%1_000_000==0 for r in case['rows'] if r.get('marks')),'SOL_OBSERVER_SOURCE_CLOCK_NOT_EXACT_MS'
    proof.update(runtime_versions=runtime_versions,native_config=snapshot_config(cfg),input_binding=binding,source_inventory_sha256=canonical(sources),required_witnesses=case['required_witnesses'],root_GO_required=True,ready_to_launch=False)
    return proof


class Probe(MethodAWaveOverlayStrategy):
    def __init__(self,cfg):
        super().__init__(cfg);self.native_fill_receipts=[];self.native_ack_receipts=[];self.case_latest_snapshot=None;self.case_safe_btc_after_sol_tp=None
    def _mr_log(self,event,ns,**fields):
        row=super()._mr_log(event,ns,**fields)
        if event=='NATIVE_SNAPSHOT':self.case_latest_snapshot=row
        return row
    def on_order_filled(self,event):
        intent=self._pending_by_order.get(str(event.client_order_id))
        owner=self._pair_orders.get(str(event.client_order_id))
        self.native_fill_receipts.append(wire(dict(native_fill=type(event).to_dict(event),action=None if intent is None else intent.action,level=None if intent is None else intent.level,owner_kind=None if owner is None else owner['kind'],owner_level=None if owner is None else owner.get('level'),parent=None if self._domain.episode is None else self._domain.episode.id)))
        result=super().on_order_filled(event)
        if owner is not None and owner['kind']=='TP' and event.instrument_id==self.config.sol_id and not self._pair_qty(self.config.sol_id) and self._pair_qty(self.config.btc_id):
            row=self.case_latest_snapshot
            if row is None or row['snapshot_ref']!=self._mr_last_snapshot:raise ValueError('M2_MISSING_POST_SOL_TP_SNAPSHOT')
            position=self._pair_position(self.config.btc_id);qty=position.quantity.as_decimal()*(1 if position.is_long else -1)
            prices={r['instrument']:D(r['raw_price']) for r in row['marks']}
            state=State(qty,D(0),D(row['equity']),D(row['peak']),prices[str(self.config.btc_id)],prices[str(self.config.sol_id)])
            risk=evaluate(state,self._mr_feature,self._mr_margin)
            self.case_safe_btc_after_sol_tp=wire(dict(snapshot_ref=row['snapshot_ref'],actual_native_fill_id=str(event.id),actual_trade_id=str(event.trade_id),actual_btc_position=position.to_dict(),actual_sol_held='0',signed_deficit=risk.worst_deficit,margin_pass=risk.margin_pass,known_safe=risk.worst_deficit<=0 and risk.margin_pass,owned_BTC_risk_reductions=[oid for oid,owner,order in self._pair_work(instrument=self.config.btc_id,kinds={'BTC_DEBT'})],native_stop_boundary_ref=self._mr_last_sol_boundary))
        return result
    def on_order_accepted(self,event):
        self.native_ack_receipts.append(type(event).to_dict(event));return super().on_order_accepted(event)


def assert_m2_before_cleanup(engine,strategy):
    from nautilus_trader.model.identifiers import ClientOrderId
    assert not strategy._mr_failed and not strategy._pair_failures,'M2_UNEXPECTED_OWNER_NO_GO'
    fills=strategy.native_fill_receipts
    entries=[r for r in fills if r['owner_kind']=='ENTRY' and r['native_fill']['instrument_id']==str(SOL_PERP.id)]
    assert entries,'M2_NO_ACTUAL_SOL_ENTRY'
    entry_ids={r['native_fill']['client_order_id'] for r in entries};assert len(entry_ids)==1,'M2_AUTOMATIC_SOL_READD'
    entry=engine.cache.order(ClientOrderId(next(iter(entry_ids))))
    assert entry.order_type.name=='MARKET' and entry.time_in_force.name=='IOC' and not entry.is_reduce_only and D(0)<entry.filled_qty.as_decimal()<entry.quantity.as_decimal(),'M2_NOT_PARTIAL_ACTUAL_IOC'
    sol_tps=[r for r in fills if r['owner_kind']=='TP' and r['native_fill']['instrument_id']==str(SOL_PERP.id)]
    assert {r['owner_level'] for r in sol_tps}=={0,1,2},'M2_NOT_THREE_ACTUAL_SOL_TP_FILLS'
    first_tp_ns=min(int(r['native_fill']['ts_event']) for r in sol_tps);protected=[]
    for order in engine.cache.orders():
        owner=strategy._pair_orders.get(str(order.client_order_id))
        if owner is None or owner['kind'] not in ('TP','STOP') or order.instrument_id!=SOL_PERP.id:continue
        accepted=[e for e in order.events if type(e).__name__=='OrderAccepted' and e.ts_event<=first_tp_ns]
        if accepted and order.is_reduce_only and order.side.name=='BUY' and order.quantity.as_decimal()>0:
            protected.append(dict(kind=owner['kind'],level=owner['level'],native_order=order.to_dict(),native_accepted_events=[type(e).to_dict(e) for e in accepted]))
    assert {r['level'] for r in protected if r['kind']=='TP'}=={0,1,2} and any(r['kind']=='STOP' and D(r['native_order']['trigger_price'])>0 for r in protected),'M2_MISSING_NATIVE_ACCEPTED_3TP_STOP'
    witness=strategy.case_safe_btc_after_sol_tp
    assert witness and witness['known_safe'] and not witness['owned_BTC_risk_reductions'],'M2_SAFE_BTC_DID_NOT_SURVIVE_SOL_TP'
    assert not any(r['action']=='PAIRED_BTC_DEBT' for r in fills),'M2_RATIO_OR_RISK_BTC_TRIM'
    btc_tps=[r for r in fills if r['action']=='BTC_REDUCE']
    assert {r['level'] for r in btc_tps}=={0,1,2} and all(int(r['native_fill']['ts_event'])>max(int(x['native_fill']['ts_event']) for x in sol_tps) for r in btc_tps),'M2_BTC_NOT_OWN_REAL_TP_AFTER_SOL_TPS'
    return dict(case='M2',partial_native_entry=entry.to_dict(),native_accepted_protection=protected,safe_btc_after_sol_tp=witness,actual_SOL_TP_levels=[0,1,2],actual_BTC_TP_levels=[0,1,2],financial_qualification=False)


def launch(case_path,gate_path):
    case=load_case(case_path);proof=prepare(case_path);gate=json.loads(Path(gate_path).read_text());source=verify_source(gate)
    assert ENGINEERING_CASE_READINESS.get(case['case_id'])=='M2_SOURCE_READY_REQUIRES_EXACT_ROOT_PREFLIGHT_GO_AND_CLAIM','SOL_ENGINEERING_CASE_NOT_SOURCE_READY'
    assert gate.get('purpose')=='METHOD_A_REGISTERED_ENGINEERING_CASE','SOL_ENGINEERING_PURPOSE_REQUIRED'
    assert gate['root_go']is True and gate['case_id']==case['case_id'] and gate['source_commit']==source
    assert gate['runtime_versions']==proof['runtime_versions'],'SOL_ROOT_PREFLIGHT_RUNTIME_VERSION_MISMATCH'
    for name,value in (('recipe_sha256',proof['recipe_sha256']),('native_input_sha256',proof['native_input_sha256']),('native_config_sha256',proof['native_config']['sha256'])):assert gate[name]==value,'SOL_IMMUTABLE_'+name
    claim=json.loads(Path(gate['claim_receipt']).read_text())
    assert claim['attempt_id']==gate['attempt_id'] and claim['case']==gate['case'] and claim['status']=='STARTED' and claim['source_commit']==source
    accepted=Path(gate['preflight_receipt']);assert hashlib.sha256(accepted.read_bytes()).hexdigest()==gate['preflight_sha256']
    preflight=json.loads(accepted.read_text());assert preflight['root_accepted']is True and preflight['source_commit']==source and preflight['case_id']==case['case_id'] and preflight['recipe_sha256']==proof['recipe_sha256']
    out=Path(gate['namespace']);assert not out.exists();out.mkdir(parents=True)
    engine=strategy=observer=None;streams=();error=None;result=None;current_ns=None;stopped_at_expected_negative=False
    def capture(label):
        if engine is None:return
        account=engine.cache.account_for_venue(SIM)
        payload=dict(label=label,timestamp_ns=current_ns,lifecycle=lifecycle(engine),native_account=None if account is None else native_account_snapshot(account,(BTC_PERP.id,SOL_PERP.id)),native_positions=[p.to_dict() for p in engine.cache.positions_open()],native_orders=[o.to_dict() for o in engine.cache.orders()],native_orders_inflight=[str(o.client_order_id) for o in engine.cache.orders_inflight()],native_orders_open=[str(o.client_order_id) for o in engine.cache.orders_open()],domain_context=None if strategy is None else domain_context(strategy),native_pending_ids=[] if strategy is None else list(strategy._pending_by_order),native_fill_receipts=[] if strategy is None else strategy.native_fill_receipts,native_ack_receipts=[] if strategy is None else strategy.native_ack_receipts,coherent=None if observer is None else observer.report())
        write_json(out/(label+'.json'),wire(payload))
    try:
        instruments=tuple(perpetual(i.raw_symbol.value,i.base_currency,str(i.price_increment),str(i.size_increment),str(i.margin_init),maker_fee=D('.00020'),taker_fee=D('.00055')) for i in (BTC_PERP,SOL_PERP))
        observer=CommittedNativeObserver(out/'coherent-native-events.jsonl.gz',D(10000),instruments)
        # Existing public source binding API. These exact paired mark inputs
        # are declared fixture sources; future rows cannot be selected by
        # observer._pair before their native timestamp.
        observer.set_week(tuple(NS(open_time_ms=r['ns']//1_000_000-60000,btc_mark={'close':r['marks']['BTC']},sol_mark={'close':r['marks']['SOL']}) for r in case['rows'] if r.get('marks')))
        book=MethodABookWitness();module=MethodATierMarginModule((),((BTC_PERP.id,D(40)),(SOL_PERP.id,D(20))),120_000_000_000)
        engine=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR')))
        engine.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,default_leverage=D(1),liquidity_consumption=True,bar_execution=False,use_message_queue=True,use_market_order_acks=False,use_reduce_only=True,modules=[module,observer,book],fee_model=MakerTakerFeeModel(),latency_model=LatencyModel(base_latency_nanos=0,insert_latency_nanos=0,update_latency_nanos=0,cancel_latency_nanos=case['cancel_latency_ns']))
        for instrument in instruments:engine.add_instrument(instrument)
        cfg=config_for(case,proof['input_binding'],observer,book);strategy=Probe(cfg)
        streams=(MethodARiskRows(out/'risk.jsonl.gz','RISK'),MethodARiskRows(out/'paired.jsonl.gz','PAIRED'))
        strategy.method_a_risk_audit,strategy.paired_prefix_audit=streams
        book.bind(strategy);engine.add_strategy(strategy)
        for row in case['rows']:
            current_ns=row['ns']
            for client,inputs,sort in native_inputs(row):
                if client is None:engine.add_data(inputs,sort=sort)
                else:engine.add_data(inputs,client_id=client,sort=sort)
            engine.run(streaming=True);engine.clear_data()
            assert not strategy.liquidation_audit,'SOL_UNEXPECTED_LIQUIDATION'
            if strategy._mr_failed:
                start=case.get('expected_negative_not_before_ns')
                assert case['case_id']=='M3' and start is not None and current_ns>=start,'SOL_UNEXPECTED_EARLY_NO_GO'
                stopped_at_expected_negative=True
        capture('BEFORE_END')
        mechanism_case_witnesses=assert_m2_before_cleanup(engine,strategy) if case['case_id']=='M2' else None
        received={a:book.epochs.get(i.id,0) for a,i in (('BTC',BTC_PERP),('SOL',SOL_PERP))}
        assert received==proof['quote_universe'],'SOL_EXPECTED_NATIVE_INPUT_UNIVERSE_MISMATCH'
        if not stopped_at_expected_negative:
            assert not engine.cache.positions_open() and not engine.cache.orders_open() and not engine.cache.orders_inflight() and not strategy._pending_by_order,'SOL_NOT_NATIVE_FLAT_BEFORE_CLEANUP'
            assert not observer.unknown,'SOL_COHERENT_OBSERVER_UNKNOWN'
        result=dict(status='NATIVE_EXECUTED_REQUIRES_CASE_WITNESS_AND_CONSUMER_ACCEPTANCE',case_id=case['case_id'],engine_constructors=1,qualified=False,expected_negative_observed=stopped_at_expected_negative,received_quote_universe=received,expected_quote_universe=proof['quote_universe'],input_binding=proof['input_binding'],mechanism_case_witnesses=mechanism_case_witnesses,risk_report=None)
    except BaseException:
        error=traceback.format_exc();capture('FAILURE_BEFORE_END')
    finally:
        if engine is not None:
            try:
                if any(x['running'] for x in lifecycle(engine).values()):engine.end()
                capture('AFTER_END')
                if observer is not None and not stopped_at_expected_negative:observer.finish_after_engine_end(current_ns)
                assert all(x['state']=='STOPPED' and not x['running'] for x in lifecycle(engine).values())
            except BaseException:error=(error or '')+'\nEND:'+traceback.format_exc()
            try:
                capture('BEFORE_DISPOSE');engine.dispose();write_json(out/'AFTER_DISPOSE.json',lifecycle(engine))
                assert all(x['disposed'] for x in lifecycle(engine).values())
            except BaseException:error=(error or '')+'\nDISPOSE:'+traceback.format_exc()
        refs=[stream.finish() for stream in streams]
        if observer is not None:observer.close()
        write_json(out/'result.json',dict(case_id=case['case_id'],attempt_id=gate['attempt_id'],source_commit=source,result=result,error=error,audit_references=refs,qualified=False))
    return 0 if error is None else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True);parser.add_argument('--prepare',action='store_true');parser.add_argument('--gate');args=parser.parse_args()
    if args.prepare:print(json.dumps(prepare(args.case),sort_keys=True));raise SystemExit(0)
    if args.gate:raise SystemExit(launch(args.case,args.gate))
    parser.error('Specify engine-free --prepare or exact root --gate')
