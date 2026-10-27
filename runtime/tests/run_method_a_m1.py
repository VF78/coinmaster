"""One registered Method-A M1 constructor. prepare() is engine-free.

Only public native inputs/events. No domain fill, private cache write, matcher,
order injection or adaptive quote price. Root must claim the unified ledger
before process launch and supply the exact UUID/source/recipe gate.
"""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime, timedelta, timezone
from dataclasses import asdict
from inspect import signature
import argparse, hashlib, json, math, os, subprocess, traceback
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.models import LatencyModel, MakerTakerFeeModel
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.enums import OmsType, AccountType, PriceType, AggregationSource, BarAggregation
from nautilus_trader.model.data import QuoteTick, BarType, BarSpecification
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.model.objects import Money
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP, SIM, perpetual, BybitTierMarginModule
from coinmaster.research.method_a_controls import build_method_a_kwargs, E4_SHA
from coinmaster.research.native_baseline import run_native_diagnostic, build_native_strategy_config
from coinmaster.domain.wave_overlay import DailyBar, features_for, completed_wave_levels
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from coinmaster.strategy.next_band import next_bar_type, next_closed_bar
from coinmaster.venues.marks import venue_mark
from coinmaster.venues.signals import daily_signal
from run_continuous_hedge_preflight import snapshot_config

CASE='M1_TP_ONLY_ORIGINAL_E4_SECOND'; S=10**9; DAY=86400*S; END=129600*S


def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def write_json(path, payload):
    encoded=json.dumps(payload,indent=2,allow_nan=False)
    Path(path).write_text(encoded+chr(10))
    assert json.loads(Path(path).read_text())==json.loads(encoded)


def source_inventory(source_root=None):
    root=Path(source_root) if source_root is not None else Path(__file__).resolve().parents[2]
    paths=set((root/'runtime/coinmaster').rglob('*.py'))|set((root/'runtime/tests').rglob('*.py'))
    paths.update((root/'runtime/coinmaster/research/control_configs').glob('*.json'))
    for name in ('runtime/pyproject.toml','runtime/uv.lock'):
        if (root/name).is_file():paths.add(root/name)
    if not paths:raise ValueError('M1_SOURCE_INVENTORY_EMPTY')
    return [dict(path=str(path.relative_to(root)),sha256=hashlib.sha256(path.read_bytes()).hexdigest()) for path in sorted(paths)]


def source_seal(source_commit, source_root=None):
    # Caller binds these bytes to the root gate's exact seal SHA before Popen.
    return dict(schema='METHOD_A_IMMUTABLE_SOURCE_SEAL_V1',source_commit=source_commit,files=source_inventory(source_root))


def verify_source(gate, source_root=None):
    root=Path(source_root) if source_root is not None else Path(__file__).resolve().parents[2]
    seal_path=Path(gate['source_seal_path'])
    assert hashlib.sha256(seal_path.read_bytes()).hexdigest()==gate['source_seal_sha256'],'M1_BOUND_SOURCE_SEAL_SHA'
    seal=json.loads(seal_path.read_text())
    assert seal['schema']=='METHOD_A_IMMUTABLE_SOURCE_SEAL_V1'
    assert seal['source_commit']==gate['source_commit'] and len(seal['source_commit'])==40
    assert seal['files']==source_inventory(root),'M1_IMMUTABLE_SOURCE_BYTES_OR_INVENTORY_CHANGED'
    if (root/'.git').exists():
        actual=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
        assert actual==gate['source_commit'],'M1_CANONICAL_GIT_HEAD_MISMATCH'
    return seal['source_commit']


def domain_context(strategy):
    ep=strategy._domain.episode
    return dict(retained_episode_id=None if ep is None else ep.id,
        btc_open_qty=None if ep is None else str(ep.btc_open_qty),
        sol_qty=None if ep is None else str(ep.sol_qty),
        historical_domain_pending=[] if ep is None else sorted(ep.pending),
        owned_native_pending=sorted(strategy._pending_by_order))


def seed():
    epoch=datetime(1970,1,1,tzinfo=timezone.utc); bars=[]
    for i in range(731):
        btc=100*math.exp(.05*math.sin(2*math.pi*i/20)+.0001*i)
        sol=100*(btc/100)**1.2*math.exp(.002*math.sin(2*math.pi*i/7))
        close=epoch+timedelta(days=i-729)
        bars.append(DailyBar(close-timedelta(days=1),close,close,bars[-1].btc_close if bars else btc,btc,sol))
    return tuple(bars)


def recipe():
    # All prices/depth/ordering/latency are immutable before constructor.
    rows=[]
    def row(second,btc='100',depth='1000',session=None,sol_only=False,h4=None):
        rows.append(dict(second=second,btc=btc,depth=depth,sol='100',sol_depth='1000',
            session=session,sol_only=sol_only,h4=h4))
    row(0,session=729);row(1,depth='2');row(2,'101.8');row(3,'102')
    row(4,depth='.2');row(5);row(6,'110');row(7,'110');row(8,'110')
    row(86400,session=730,sol_only=True);row(86401,sol_only=True)
    row(100800,depth='2',h4='50');row(100801,depth='2');row(100802,depth='2')
    row(100803,'98.3');row(100804,'98');row(100805,depth='.2');row(100806)
    row(100807,'90');row(100808,'90');row(100809,'90')
    row(129600,'90');row(129601,'90')
    return dict(case=CASE,rows=rows,window_ns=[0,129601*S],
        latency=dict(base=0,insert=0,update=0,cancel=0),liquidity_consumption=True,
        bar_execution=False,use_message_queue=True,use_reduce_only=True,
        fee_maker='.00020',fee_taker='.00055',venue_model='DECLARED_STRESS_FIXTURE_ONLY_NOT_ECONOMICS',
        expected=['natural_parent1_long','partial_FIRST','three_real_accepted_TP',
        'actual_TP0_before_completed_FIRST','remaining_FIRST_completion_original_PLANREF',
        'original_SECOND_limit_price_.0025','original_SECOND_actual_partial_and_remainder_before_deadline',
        'cumulative_new_rights_only_native_cache_conservation','old_SOL_raw_eligibility_actual_fills',
        'natural_regime_parent1_close_and_ACK','natural_parent2_short',
        'both_parents_native_flat_ACK_before_cleanup'])


def config():
    kwargs=build_method_a_kwargs(Path('.'),Path('.'),'P1',start_ms=-86400000,end_ms=129600000)
    bound=signature(run_native_diagnostic).bind(**kwargs);bound.apply_defaults();context=dict(bound.arguments)
    def kind(iid,price_type):
        return BarType(iid,BarSpecification(1,BarAggregation.DAY,price_type),AggregationSource.EXTERNAL)
    bars=seed()
    daily={int(row.open_time.timestamp()*1000):dict(high=str(max(row.btc_open,row.btc_close)*1.01),
        low=str(min(row.btc_open,row.btc_close)*.99)) for row in bars[:729]}
    context.update(btc_instrument=BTC_PERP,sol_instrument=SOL_PERP,kind=kind,
        max_mark_age_ns=120*S,mark_client=ClientId('BYBIT_MARK'),signal_client=ClientId('BYBIT_SIGNAL'),
        selected_leverage=((BTC_PERP.id,D(40)),(SOL_PERP.id,D(20))),policy=kwargs['execution_policy'],
        seed_bars=bars[:729],daily={'BTCUSDT':daily},cover_hour_seed=(),confirmation_bars=(),
        h4_bar_type=None,h4_seed=(),next_bar_types=(next_bar_type(BTC_PERP.id,4),next_bar_type(SOL_PERP.id,1)),
        start_at=datetime.fromtimestamp(-86400,timezone.utc),end_at=datetime.fromtimestamp(129600,timezone.utc))
    return build_native_strategy_config(context),kwargs


def native_inputs(row):
    ns=row['second']*S;groups=[]
    groups.append((ClientId('BYBIT_MARK'),[venue_mark(i.id,D(price),ns) for i,price in ((BTC_PERP,row['btc']),(SOL_PERP,row['sol']))],True))
    if row['session'] is not None:
        day=seed()[row['session']]
        groups.append((ClientId('BYBIT_SIGNAL'),[daily_signal(i.id,D(str(open_)),D(str(close)),D(str(close)),D(str(close)),ns)
            for i,open_,close in ((BTC_PERP,day.btc_open,day.btc_close),(SOL_PERP,day.sol_close,day.sol_close))],False))
    if row['h4'] is not None:
        groups.append((ClientId('BYBIT_SIGNAL'),[next_closed_bar(BTC_PERP.id,4,D('100'),D('100'),D(row['h4']),D(row['h4']),ns)],False))
    quotes=[QuoteTick(i.id,i.make_price(D(price)),i.make_price(D(price)),i.make_qty(D(depth)),i.make_qty(D(depth)),ns,ns)
        for i,price,depth in ((BTC_PERP,row['btc'],row['depth']),(SOL_PERP,row['sol'],row['sol_depth'])) if not row['sol_only'] or i.id==SOL_PERP.id]
    groups.append((None,quotes,True))
    return groups


def lifecycle(engine):
    return {n:dict(state=getattr(engine.kernel,n).state.name,running=bool(getattr(engine.kernel,n).is_running),disposed=bool(getattr(engine.kernel,n).is_disposed)) for n in ('trader','data_engine','risk_engine','exec_engine','emulator')}


def prepare():
    cfg,kwargs=config();bars=seed();features=features_for(bars,cfg.candidate)
    assert [features[i].side for i in (729,730)]==[1,-1]
    levels={str(i):list(completed_wave_levels(bars,features,i,cfg.candidate,features[i].side)) for i in (729,730)}
    assert 0<float(levels['729'][2])/3 < .018 < min(levels['729'])
    assert 0<float(levels['730'][2])/3 < .017 < min(levels['730'])
    assert cfg.candidate.sol_overlay_enabled and not cfg.research_btc_real_u
    assert cfg.research_wait_4h and cfg.research_regime_reentry_band==D('.5')
    assert cfg.research_btc_split_discount==D('.0025') and cfg.research_method_a_tp
    assert recipe()['window_ns'][1] <= 48*3600*S
    static=[]
    for row in recipe()['rows']:
        for client,group,sort in native_inputs(row):
            for event in group:
                data=getattr(event,'data',event)
                record=dict(type=type(data).__name__,client=None if client is None else str(client),sort=sort,
                    instrument=str(data.instrument_id),ts_event=data.ts_event,ts_init=data.ts_init)
                for name in ('price','open','high','low','close','hours','bid_price','ask_price','bid_size','ask_size'):
                    if hasattr(data,name):record[name]=str(getattr(data,name))
                assert record['ts_event']==row['second']*S and record['ts_init']>=record['ts_event']
                static.append(record)
    assert len(static)==95
    instruments=[]
    for i in (BTC_PERP,SOL_PERP):
        actual=perpetual(i.raw_symbol.value,i.base_currency,str(i.price_increment),str(i.size_increment),str(i.margin_init),maker_fee=D('.00020'),taker_fee=D('.00055'))
        instruments.append(dict(id=str(actual.id),price_increment=str(actual.price_increment),size_increment=str(actual.size_increment),
            min_quantity=None if actual.min_quantity is None else str(actual.min_quantity),min_notional=None if actual.min_notional is None else str(actual.min_notional),maker_fee=str(actual.maker_fee),taker_fee=str(actual.taker_fee)))
    step=BTC_PERP.size_increment.as_decimal();gross_lots=int(D(str(float(D(55000)/D(100))))//step)
    assert gross_lots==550000
    first_quantity=D(gross_lots//2)*step
    assert first_quantity==D(275)
    first_reference=(D(2)*D(100)+(first_quantity-D(2))*D('101.8'))/first_quantity
    original_second_price=(first_reference*D('.9975')//D('.1'))*D('.1')
    assert original_second_price==D('101.5') and D('100')<original_second_price<D('102')
    payload=recipe();return dict(case=CASE,engine_constructors=0,ready_to_launch=False,
        input_event_count=len(static),native_input_sha256=canonical(static),static_public_inputs=static,
        public_instruments=instruments,first_q0_q1=dict(requested_notional='55000',q0='100',q1_bid='100',q1_ask='100',
        branch='MARKETABLE_FULL_ENTRY_FALLBACK',gross_lots=gross_lots,net_parent_lots=gross_lots,first_quantity=str(first_quantity),
        actual_initial_partial='2',initial_TP_lots={'0':425,'1':425,'2':1150},first_completed_PLANREF=str(first_reference),original_SECOND_price=str(original_second_price),
        original_SECOND_quantity='275',original_deadline_ns=str(1*S+4*3600*S),raw_positive_fraction=str(levels['729'][0]),U1='101.8',
        unknown='Synthetic source input reachability only. Exact native initial account/own Q and event order remain M1 assertions; no PnL generated.'),
        root_GO_required=True,E4_config_canonical_sha256=E4_SHA,recipe=payload,recipe_sha256=canonical(payload),
        config=snapshot_config(cfg),kwargs=snapshot_config(kwargs),seed_bars=729,
        natural_sides=[1,-1],raw_levels=levels,
        reachability='TP1 at101.8 precedes raw positive5.1796%; FIRST retries unmodified. Next quote102 keeps buySECOND passive, quote100 depth.2 gives genuine SECOND partial. Both are before4h. ClosedH4 at100800 close50 supports unchanged E4 reentry for SHORT; static quotes then cover both parents. Native witness required; pure calculation is not matching evidence.')


class Probe(WaveOverlayStrategy):
    def __init__(self,cfg):
        super().__init__(cfg);self.events=[];self.parents=[];self.fills=[];self.acks=[]
    def trace(self,kind,event,intent=None):
        ep=self._domain.episode;p=self._split_parent
        if ep is not None and ep.id not in self.parents:self.parents.append(ep.id)
        row=dict(sequence=len(self.events)+1,kind=kind,timestamp_ns=str(event.ts_event),
            order_id=str(event.client_order_id),parent=None if intent is None else intent.episode_id,
            action=None if intent is None else intent.action,level=None if intent is None else intent.level,
            parent_filled=None if p is None else str(p['filled']),
            first_quantity=None if p is None else str(p['first_quantity']))
        self.events.append(row);return row
    def on_order_accepted(self,event):
        intent=self._pending_by_order.get(str(event.client_order_id));self.acks.append(self.trace('ACCEPTED',event,intent))
        return super().on_order_accepted(event)
    def on_order_filled(self,event):
        intent=self._pending_by_order.get(str(event.client_order_id))
        row=self.trace('FILL_BEFORE_CALLBACK',event,intent)
        row.update(quantity=str(event.last_qty),price=str(event.last_px),trade_id=str(event.trade_id),
            liquidity=event.liquidity_side.name,commission=str(event.commission))
        self.fills.append(row)
        return super().on_order_filled(event)


def run_case(engine,strategy):
    bars=seed()
    for row in recipe()['rows']:
        ns=row['second']*S
        for client,inputs,sort in native_inputs(row):
            if client is None:engine.add_data(inputs,sort=sort)
            else:engine.add_data(inputs,client_id=client,sort=sort)
        engine.run(streaming=True);engine.clear_data()
        assert not strategy.liquidation_audit,'M1_UNEXPECTED_LIQUIDATION'
        assert strategy._forced_close_reason in (None,'REGIME','TERMINAL_BOUNDARY_SETTLEMENT'),'M1_UNEXPECTED_FORCE_CLOSE'
    assert len(strategy.parents)==2 and len(set(strategy.parents))==2,'M1_TWO_NATURAL_PARENTS'
    first=strategy.parents[0];fills=[x for x in strategy.fills if x['parent']==first]
    entries=[x for x in fills if x['action']=='BTC_ENTRY'];tps=[x for x in fills if x['action']=='BTC_REDUCE']
    assert D(entries[0]['quantity'])==2 and D(entries[0]['quantity'])<D(entries[0]['first_quantity'])
    tp0=next(x for x in tps if x['level']==0)
    second=[x for x in entries if D(x['parent_filled'])>=D(x['first_quantity'])]
    assert second and tp0['sequence']<second[0]['sequence'] and D(second[0]['quantity'])==D('.2')
    assert len({x['level'] for x in strategy.acks if x['parent']==first and x['action']=='BTC_REDUCE' and x['sequence']<tp0['sequence']})==3
    parent=strategy.split_parent_audit[0]
    assert parent['first_filled']==parent['first_quantity'] and parent['filled']==parent['quantity']
    assert int(second[-1]['timestamp_ns'])<parent['deadline_ns'] and not parent['fallback']
    audit=[x for x in strategy.method_a_tp_audit if x.get('episode_id')==first and x['event']=='ENTITLEMENT']
    assert any(x['actual_tp_filled'].get(0,0)>0 and x['leaves'][0]>0 for x in audit)
    assert all(sum(x['leaves'].values())==x['actual_held_lots'] for x in audit)
    assert any(x['event']=='ACTUAL_TP_FILL' and x['old_sol_rights'] for x in strategy.method_a_tp_audit)
    assert not engine.cache.positions_open() and not engine.cache.orders_open() and not engine.cache.orders_inflight()
    assert not strategy._pending_by_order
    # Old alpha intentionally retains a historical domain episode after TP-flat.
    # Native terminal orders, actual inventory and owned work are authority.
    terminal_names={'OrderFilled','OrderCanceled','OrderExpired','OrderRejected','OrderDenied'}
    assert all(o.is_closed and any(type(event).__name__ in terminal_names for event in o.events) for o in engine.cache.orders())
    return dict(status='M1_NATIVE_PASS_REQUIRES_ROOT_ACCEPTANCE',parents=strategy.parents,
        fills=len(strategy.fills),actual_native_flat=True,actual_open_orders=0,actual_inflight=0,
        engine_constructors=1,financial_authority=False,domain_context=domain_context(strategy))


def launch(gate_path):
    gate=json.loads(Path(gate_path).read_text());proof=prepare()
    source=verify_source(gate)
    assert gate['root_go'] is True and gate['case']==CASE and gate['source_commit']==source
    assert gate['recipe_sha256']==proof['recipe_sha256'] and gate['native_config_sha256']==proof['config']['sha256']
    assert gate['native_input_sha256']==proof['native_input_sha256']
    claim=json.loads(Path(gate['claim_receipt']).read_text())
    assert claim['attempt_id']==gate['attempt_id'] and claim['case']==CASE and claim['status']=='STARTED' and claim['source_commit']==source
    out=Path(gate['namespace']);assert not out.exists();out.mkdir(parents=True)
    e=s=None;result=None;error=None
    def capture(label):
        if e is None:return
        account=e.cache.account_for_venue(SIM)
        payload=dict(label=label,lifecycle=lifecycle(e),domain_context=None if s is None else domain_context(s),native_cash=None if account is None else str(account.balance_total()),positions=[dict(instrument=str(p.instrument_id),quantity=str(p.quantity),side='LONG' if p.is_long else 'SHORT') for p in e.cache.positions_open()],
            orders=[dict(id=str(o.client_order_id),instrument=str(o.instrument_id),status=o.status.name,quantity=str(o.quantity),filled=str(o.filled_qty),leaves=str(o.leaves_qty),price=str(getattr(o,'price',None)),native_event_history=[dict(type=type(event).__name__,id=str(event.id),timestamp_ns=str(event.ts_event)) for event in o.events]) for o in e.cache.orders()],
            fills=[] if s is None else s.fills,events=[] if s is None else s.events,
            tp_audit=[] if s is None else s.method_a_tp_audit,
            split=[] if s is None else [{k:str(v) for k,v in p.items() if k!='intent'} for p in s.split_parent_audit])
        write_json(out/(label+'.json'),payload)
    try:
        cfg,_=config()
        e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR')))
        module=BybitTierMarginModule((),((BTC_PERP.id,D(40)),(SOL_PERP.id,D(20))),120*S)
        e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,
            starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,
            default_leverage=D(1),liquidity_consumption=True,bar_execution=False,use_message_queue=True,
            use_reduce_only=True,modules=[module],fee_model=MakerTakerFeeModel(),
            latency_model=LatencyModel(base_latency_nanos=0,insert_latency_nanos=0,update_latency_nanos=0,cancel_latency_nanos=0))
        for i in (BTC_PERP,SOL_PERP):
            e.add_instrument(perpetual(i.raw_symbol.value,i.base_currency,str(i.price_increment),str(i.size_increment),str(i.margin_init),maker_fee=D('.00020'),taker_fee=D('.00055')))
        s=Probe(cfg);e.add_strategy(s);result=run_case(e,s);capture('PASS_BEFORE_END')
    except BaseException:
        error=traceback.format_exc();capture('FAILURE_BEFORE_END')
    finally:
        if e is not None:
            capture('BEFORE_END')
            try:
                if any(x['running'] for x in lifecycle(e).values()):e.end()
                capture('AFTER_END')
                assert all(x['state']=='STOPPED' and not x['running'] for x in lifecycle(e).values())
            except BaseException:
                error=(error or '')+chr(10)+'END:'+traceback.format_exc()
            try:
                capture('BEFORE_DISPOSE');e.dispose()
                write_json(out/'AFTER_DISPOSE.json',lifecycle(e))
                assert all(x['disposed'] for x in lifecycle(e).values())
            except BaseException:
                error=(error or '')+chr(10)+'DISPOSE:'+traceback.format_exc()
        write_json(out/'result.json',dict(case=CASE,attempt_id=gate['attempt_id'],result=result,error=error))
    return 0 if error is None else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--gate');args=parser.parse_args()
    if args.prepare:print(json.dumps(prepare(),sort_keys=True));raise SystemExit(0)
    if args.gate:raise SystemExit(launch(args.gate))
    parser.error('Specify --prepare or root-gated --gate')
