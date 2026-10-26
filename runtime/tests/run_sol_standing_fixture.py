"""CM137 separately counted registered lifecycle fixtures. No legacy budgets.

No alternate matcher, native cache mutation, domain/position reset, tier bypass,
explicit position linkage, execution algorithm, transport swap, retry or hidden
constructor. All quantities are native registered sizing/fills; N752 is pure-only.
"""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timedelta,timezone
from inspect import signature
import argparse,ast,copy,hashlib,json,math,os,traceback,uuid
from dataclasses import asdict,is_dataclass
from coinmaster.research.registered_control import config_for,build_registered_control_kwargs,native_kwargs_json_roundtrip,validate_native_control
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.backtest.models import LatencyModel
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.enums import OmsType,AccountType
from nautilus_trader.model.identifiers import ClientId,ClientOrderId
from nautilus_trader.model.objects import Money
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP,SIM,perpetual,BybitTierMarginModule
from coinmaster.research.native_book import NativeBookWitness
from coinmaster.research.a0_family import build_a0_kwargs,validate_native_a0
from coinmaster.research.native_baseline import build_native_strategy_config,run_native_diagnostic
from coinmaster.research.paired_signal_feed import PairedSignal
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from coinmaster.domain.wave_overlay import DailyBar,features_for,completed_wave_levels
from coinmaster.venues.marks import venue_mark
from coinmaster.venues.signals import daily_signal

S=1_000_000_000;M=60*S;DAY=86400*S;END=90600*S

def snapshot_config(config):
    def plain(value):
        if type(value).__name__=='TierMarginPolicy':return {'type':'TierMarginPolicy','marks':plain(value._marks),'selected_leverage':plain(value._selected_leverage),'max_mark_age_ns':value._max_mark_age_ns,'profile':plain(value._profile)}
        if is_dataclass(value):return {k:plain(v) for k,v in asdict(value).items()}
        if hasattr(value,'__struct_fields__'):return {k:plain(getattr(value,k)) for k in value.__struct_fields__}
        if isinstance(value,dict):return {str(k):plain(v) for k,v in value.items()}
        if isinstance(value,(set,frozenset)):return sorted([plain(v) for v in value],key=str)
        if isinstance(value,(list,tuple)):return [plain(v) for v in value]
        if value is None or type(value) in (str,int,float,bool):return value
        return {'type':type(value).__name__,'value':str(value)}
    payload=plain(config);serialized=json.dumps(payload,sort_keys=True,allow_nan=False)
    return dict(sha256=hashlib.sha256(serialized.encode()).hexdigest(),payload=payload)

def registered_fixture_context(family,start_ms=-86400000,end_ms=86400001,paired=False,feed=()):
    from datetime import timedelta
    from nautilus_trader.model.data import BarType,BarSpecification
    from nautilus_trader.model.enums import BarAggregation,PriceType,AggregationSource
    from nautilus_trader.model.identifiers import ClientId
    from coinmaster.strategy.next_band import next_bar_type
    config=config_for(family)
    kwargs=build_registered_control_kwargs(config,family,Path('.'),Path('.'),feed,1725249600000,1725264000000)
    _,restored=native_kwargs_json_roundtrip(kwargs);assert restored==kwargs
    bound=signature(run_native_diagnostic).bind(**kwargs);bound.apply_defaults();validate_native_control(bound.arguments)
    context=dict(bound.arguments)
    def kind(instrument,price_type):return BarType(instrument,BarSpecification(1,BarAggregation.DAY,price_type),AggregationSource.EXTERNAL)
    context.update(max_mark_age_ns=2*M,btc_instrument=BTC_PERP,sol_instrument=SOL_PERP,kind=kind,mark_client=ClientId('BYBIT_MARK'),signal_client=ClientId('BYBIT_SIGNAL'),selected_leverage=((BTC_PERP.id,D(40)),(SOL_PERP.id,D(20))),policy=kwargs['execution_policy'],seed_bars=(),daily={'BTCUSDT':{}},next_bar_types=(next_bar_type(BTC_PERP.id,4),next_bar_type(SOL_PERP.id,1)),confirmation_bars=(),h4_bar_type=None,h4_seed=(),cover_hour_seed=(),trading_start_ms=start_ms,trading_end_ms=end_ms,start_at=datetime.fromtimestamp(start_ms/1000,timezone.utc),end_at=datetime.fromtimestamp(end_ms/1000,timezone.utc))
    if paired:
        if family!='R3':raise ValueError('R2_PAIRED_NOT_ADMITTED')
        context['research_paired_prefix']='B2_F0'
    strategy_config=build_native_strategy_config(context)
    receipt=snapshot_config(strategy_config)
    receipt.update(archived_registry_config_sha256=__import__('coinmaster.research.registered_control',fromlist=['CONFIG_PINS']).CONFIG_PINS[family],registered_kwargs_sha256=hashlib.sha256(native_kwargs_json_roundtrip(kwargs)[0].encode()).hexdigest(),fixture_context_deltas=['synthetic instrument identities and quote prices','finite deterministic seed bars/daily observations instead of historical warmup','fixture trading/terminal/reporting timestamps','static native margin marks; same existing BTC40/SOL20 selected leverage, default1','B2_F0 existing paired policy on R3 only' if paired else 'OFF control'],margin_policy='existing BTC40/SOL20/default1',maker_fee='0.00020',taker_fee='0.00055')
    return strategy_config,context,receipt

def seed():
    epoch=datetime(1970,1,1,tzinfo=timezone.utc);bars=[]
    for i in range(731):
        btc=100*math.exp(.05*math.sin(2*math.pi*i/20)+.0001*i)
        sol=100*(btc/100)**1.2*math.exp(.002*math.sin(2*math.pi*i/7));close=epoch+timedelta(days=i-729)
        bars.append(DailyBar(close-timedelta(days=1),close,close,bars[-1].btc_close if bars else btc,btc,sol))
    return tuple(bars)

def feed():
    return tuple(PairedSignal(t,t,t+60*S,D(100),D(100),D(1),D(2),True,side==1,side==-1,False,False,D(120),D('99.2'),D(100),D(2),D(1),D('.75'),t-DAY,t)for t,side in((70*S,1),(DAY+70*S,-1)))

def fixture_config(witness, case="E5"):
    variant="R2_C0" if case in ("E1","E2","E3") else "R2_A0"
    kwargs=build_a0_kwargs(Path('.'),Path('.'),variant,feed(),start_ms=-86400000,end_ms=90600000,standing_tp=True,sol_standing=case!="E3",trim_control=case=="E3")
    bound=signature(run_native_diagnostic).bind(**kwargs);bound.apply_defaults();validate_native_a0(bound.arguments)
    _,context,_=registered_fixture_context('R2',start_ms=-86400000,end_ms=90600000)
    context.update(bound.arguments);context.update(seed_bars=seed()[:729],research_native_book=witness)
    return build_native_strategy_config(context),kwargs

class RegisteredProbe(WaveOverlayStrategy):
    def __init__(self,config):
        super().__init__(config);self.stage='BOOT';self.events=[];self.fills=[];self.routes={};self.actual_pending=[];self.margin_checks=[];self.diag=None;self.rejected=[];self.parents=[];self.journal_path=None

    def trace(self,event,**data):
        row=dict(sequence=len(self.events)+1,event=event,stage=self.stage,timestamp_ns=self.clock.timestamp_ns(),**data);self.events.append(row)
        if self.journal_path is not None:
            with self.journal_path.open('a')as stream:stream.write(json.dumps(row)+'\n');stream.flush();os.fsync(stream.fileno())

    def quantity(self,instrument):
        pos=[p for p in self.cache.positions_open()if p.instrument_id==instrument]
        assert len(pos)<=1
        return pos[0].quantity.as_decimal()if pos else D(0)

    def orders(self):
        return [dict(id=str(o.client_order_id),instrument=str(o.instrument_id),side=o.side.name,status=o.status.name,quantity=str(o.quantity),filled=str(o.filled_qty),leaves=str(o.leaves_qty),price=str(getattr(o,'price',None)),reduce_only=o.is_reduce_only,strategy=str(o.strategy_id),exec_algorithm_id=None if o.exec_algorithm_id is None else str(o.exec_algorithm_id),raw_position_id=None if o.position_id is None else str(o.position_id),cache_position_id=None if self.cache.position_id(o.client_order_id)is None else str(self.cache.position_id(o.client_order_id)))for o in self.cache.orders()]

    def positions(self):
        return [dict(id=str(p.id),instrument=str(p.instrument_id),quantity=str(p.quantity),side='LONG'if p.is_long else'SHORT',indexed=[str(o.client_order_id)for o in self.cache.orders_for_position(p.id)])for p in self.cache.positions_open()]

    def route(self,event,route):
        self.routes.setdefault(str(event.id),[]).append(route)
        self.trace('NATIVE_CALLBACK',event_id=str(event.id),event_type=type(event).__name__,order_id=str(event.client_order_id),route=route)

    def on_order_event(self,event):
        self.route(event,'generic');return super().on_order_event(event)

    def on_order_updated(self,event):
        self.route(event,'typed_updated');return super().on_order_updated(event)

    def on_order_pending_update(self,event):
        self.route(event,'typed_pending_update')
        order=self.cache.order(event.client_order_id);assert order.status.name=='PENDING_UPDATE'
        if self.diag and str(event.client_order_id)==self.diag['order_id']:
            self.diag['actual_pending_update_event_id']=str(event.id)
        ep,m=self._tp_plan()
        if str(event.client_order_id)in self._tp_owners and ep and m:
            ready=self._a0_targets_ready(ep,m,self.quantity(self.config.btc_id));assert ready is False
            self.actual_pending.append(dict(event_id=str(event.id),order_id=str(event.client_order_id),status=order.status.name,a0_ready=ready))

    def on_order_pending_cancel(self,event):
        self.route(event,'typed_pending_cancel')
        order=self.cache.order(event.client_order_id);assert order.status.name=='PENDING_CANCEL'

    def on_order_modify_rejected(self,event):
        self.route(event,'typed_modify_rejected')
        if self.diag and str(event.client_order_id)==self.diag['order_id']:
            order=self.cache.order(event.client_order_id)
            assert not order.is_closed and order.leaves_qty.as_decimal()>0 and order.quantity.as_decimal()==D(self.diag['quantity']) and order.filled_qty.as_decimal()==D(self.diag['filled'])
            assert 'below filled quantity'in str(event.reason)and self.diag.get('actual_pending_update_event_id')
            self.rejected.append(dict(event_id=str(event.id),order_id=str(event.client_order_id),status=order.status.name,quantity=str(order.quantity),filled=str(order.filled_qty),leaves=str(order.leaves_qty),reason=str(event.reason),old_working_protection=True))
        return super().on_order_modify_rejected(event)

    def _tier_allows_increase(self,*args,**kwargs):
        # Trace the actual stock result; never replace it with a fixture answer.
        result=super()._tier_allows_increase(*args,**kwargs)
        self.margin_checks.append(dict(stage=self.stage,args=[str(x)for x in args],allowed=result))
        return result

    def on_order_filled(self,event):
        self.route(event,'typed_filled');oid=str(event.client_order_id);owner=self._pair_orders.get(oid)
        order=self.cache.order(event.client_order_id);pre_pending=order.is_pending_cancel
        self.fills.append(dict(trade_id=str(event.trade_id),order_id=oid,instrument=str(event.instrument_id),quantity=str(event.last_qty),price=str(event.last_px),commission=str(event.commission),liquidity=event.liquidity_side.name,stage=self.stage,pair_kind=None if owner is None else owner['kind'],pair_level=None if owner is None else owner['level'],pending_cancel=pre_pending,native_status=order.status.name,raw_position_id=None if order.position_id is None else str(order.position_id),cache_position_id=None if self.cache.position_id(event.client_order_id)is None else str(self.cache.position_id(event.client_order_id))))
        result=super().on_order_filled(event)
        if self._domain.episode and self._domain.episode.id not in self.parents:self.parents.append(self._domain.episode.id)
        return result

def integration_fixture(e,s,capture,case):
    from nautilus_trader.model.data import QuoteTick
    last=-1
    def advance(second,btc='100',bsize='1000',sol='100',ssize='1000',fresh=True,quotes=True,session=None,expected_fault=False):
        nonlocal last
        ns=int(D(str(second))*S);assert 0<=ns<=END and ns>last;last=ns
        if fresh:e.add_data([venue_mark(i.id,D(price),ns)for i,price in((BTC_PERP,btc),(SOL_PERP,sol))],client_id=ClientId('BYBIT_MARK'),sort=not quotes)
        if session is not None:
            row=seed()[session];e.add_data([daily_signal(i.id,D(str(open_)),D(str(close)),D(str(close)),D(str(close)),ns)for i,open_,close in((BTC_PERP,row.btc_open,row.btc_close),(SOL_PERP,row.sol_close,row.sol_close))],client_id=ClientId('BYBIT_SIGNAL'),sort=False)
        if quotes:
            e.add_data([QuoteTick(i.id,i.make_price(D(price)),i.make_price(D(price)),i.make_qty(D(size)),i.make_qty(D(size)),ns,ns)for i,price,size in((BTC_PERP,btc,bsize),(SOL_PERP,sol,ssize))],sort=True)
        else:
            # CustomData still causes stock advance_time/drain/iterate; runtime
            # witness checks actual current book on every native settle pass.
            assert fresh
        e.run(streaming=True);e.clear_data();s._tp_settled('AFTER_COMPLETE_NATIVE_STREAM',ns);capture('AT_'+str(second).replace('.','_'))
        assert set(s._pair_failures).issubset({"PARTIAL_NATIVE_STOP"}if expected_fault else set())and not s._forced_close_reason and not s._liquidating
    def targets():
        ep,m=s._tp_plan();assert ep and m
        return {o['level']:s.cache.order(ClientOrderId(oid))for oid,o in s._tp_owners.items()if o['parent']==ep.id and not s.cache.order(ClientOrderId(oid)).is_closed}
    def held():return s.quantity(s.config.btc_id)
    def debt_fills():return [f for f in s.fills if f['pair_kind']=='BTC_DEBT']
    s.stage='P1_NATURAL_ENTRY';advance(0,bsize='2',session=729);advance(1,bsize='2');advance(2)
    assert held()==D(2)and s._split_parent['first_quantity']>held() and len(targets())==3 and len(s.parents)==1
    parent1=s.parents[0];capture('P1_REGISTERED_SIZING_AND_THREE_TP')
    advance(70);advance(72.01,quotes=False);advance(130);advance(131)
    assert s._pair and s._pair['entry_terminal']and s.quantity(s.config.sol_id)==D(2)
    s.stage='P1_PARTIAL_TP';advance(135,btc=str(targets()[0].price),bsize='.050')
    assert any(o.filled_qty.as_decimal()==D('.050')for o in targets().values())
    before_debt_ids={k:str(o.client_order_id)for k,o in targets().items()}
    s.stage='P1_SOL_RELIEF';advance(137,sol='99',ssize='.2');advance(139.01,quotes=False)
    assert s._pair['debt_since']is not None
    s.stage='P1_SAFE_DEBT';advance(140);advance(141)
    assert {k:str(o.client_order_id)for k,o in targets().items()}==before_debt_ids
    assert debt_fills()and len([x for x in s.standing_tp_audit if x['event']=='LATEST_MODIFY_ACK'])>=3
    assert any(D(x['filled'])>0 and D(x['total'])==D(x['filled'])+D(x['desired_leaves'])for x in s.standing_tp_audit if x['event']=='MODIFY_SUBMIT')
    before={k:o.leaves_qty.as_decimal()for k,o in targets().items()};tp0=targets()[0]
    realloc_before_ordinary=len([x for x in s.standing_tp_audit if x['event']=='INVENTORY_ALLOCATION'])
    s.stage='P1_FULL_TP0';advance(143,btc=str(tp0.price),bsize=str(tp0.leaves_qty))
    assert {k:o.leaves_qty.as_decimal()for k,o in targets().items()}=={k:v for k,v in before.items()if k!=0}
    tp1=targets()[1];s.stage='P1_FULL_TP1';advance(145,btc=str(tp1.price),bsize=str(tp1.leaves_qty));assert set(targets())=={2}
    assert len([x for x in s.standing_tp_audit if x['event']=='INVENTORY_ALLOCATION'])==realloc_before_ordinary
    s.stage='P1_MARKETABLE_DEBT';advance(150,btc=str(targets()[2].price),bsize='.010',sol='96',ssize='.9');advance(152.01,quotes=False)
    prior=len(debt_fills());advance(153,btc=str(targets()[2].price),bsize='.020',sol='96')
    assert s._pair['debt_since']is not None and s._pair['standing_debt_deferred']and len(debt_fills())==prior
    defers=[x for x in s.standing_tp_audit if x['event']=='MARKETABLE_DEBT_DEFER'];assert defers
    assert all(D(x['residual_debt'])==D(x['actual_held'])-D(x['absolute_cap'])>0 and int(x['duration_ns'])>=0 for x in defers)
    s.stage='P1_CONSUMED_TP3_FLAT';advance(154,btc=str(targets()[2].price),bsize='10',sol='96');assert held()==0
    advance(156.01,quotes=False);advance(157,sol='96');advance(160)
    assert held()==s.quantity(s.config.sol_id)==0 and not e.cache.orders_open()and not e.cache.orders_inflight() and s._pair is None and len(debt_fills())==prior
    capture('P1_FLAT_NO_LATE_DEBT')
    if case=='E2':return c0_stress_second(e,s,capture,advance,targets)
    s.stage='P2_NATURAL_ENTRY';advance(86400,bsize='2',session=730);advance(86401,bsize='2');advance(86402)
    assert held()==D(2)and len(s.parents)==2 and s.parents[1]!=parent1 and s._domain.episode.side==-1 and len(targets())==3
    advance(86470);advance(86472.01,quotes=False);advance(86530);advance(86531)
    advance(86540,sol='101',ssize='.2');advance(86542.01,quotes=False);advance(86543);advance(86544)
    assert held()==s._pair['caps'].bmax and held()<2
    s.stage='P2_OFF';advance(86700,btc='99');advance(86702.01,quotes=False);advance(86703,btc='99')
    assert s._pair['risk']=='INACTIVE_RISK'and s.quantity(s.config.sol_id)==0
    s.stage='P2_CROSS';advance(86760,btc='101.6')
    assert any(x['event']=='A0_DENY'and x['reason']=='POST_ONLY_CROSS'for x in s.market_redesign_audit)
    s.stage='P2_STALE_MARGIN';advance(86881,btc='100',fresh=False)
    assert any(x['event']=='A0_DENY'and x['reason']=='NATIVE_MARGIN'for x in s.market_redesign_audit)
    s.stage='P2_FRESH_RECOVERY';advance(86882)
    m=s._md_plans[s.parents[1]];a=m['a0'];release=s.cache.order(ClientOrderId(a['order_id']))
    assert a['attempted']and release.status.name=='ACCEPTED'and release.is_post_only and release.price.as_decimal()==a['price']
    cap=a['granted_cap'];old_orders={oid:s.cache.order(ClientOrderId(oid)).status.name for oid in a['old_orders']};assert all(v=='CANCELED'for v in old_orders.values())
    s.stage='P2_RELEASE_PARTIAL';advance(86885,btc='102',bsize='1');assert release.filled_qty.as_decimal()>0 and not release.is_closed
    advance(86886)
    s.stage='P2_ORDINARY_TP_CANCEL';advance(86887,btc=str(targets()[0].price),bsize='.050')
    if case=='E4':
        assert release.is_pending_cancel
        closed_cap=s._pair['caps'].bmax
        s.stage='P2_PENDING_CANCEL_LATE_FILL';prior_filled=release.filled_qty.as_decimal();advance(86887.5,btc='102',bsize='2')
        assert release.filled_qty.as_decimal()>prior_filled and s._pair['caps'].bmax==closed_cap and s._pair['debt_since']is not None
        capture('ACTUAL_A0_PENDING_CANCEL_LATE_FILL')
        advance(86889.01,quotes=False);assert release.status.name=='CANCELED'
        s.stage='P2_EXCESS_DEBT';advance(86890);advance(86891);assert held()<=closed_cap and a['granted_cap']==cap
    else:
        assert release.status.name=='CANCELED'
        advance(86889.01,quotes=False);advance(86890);advance(86891)
    assert len([x for x in s.market_redesign_audit if x['event']=='A0_SUBMIT'and x['episode_id']==s.parents[1]])==1
    for second,level in((86892,0),(86893,1),(86894,2)):
        o=targets()[level];s.stage='P2_TERMINAL_TP'+str(level);advance(second,btc=str(o.price),bsize='1000')
    advance(86900);assert not e.cache.positions_open()and not e.cache.orders_open()and not e.cache.orders_inflight()
    assert s.actual_pending and any(not x['allowed']for x in s.margin_checks)and any(x['allowed']for x in s.margin_checks)
    assert len({f['trade_id']for f in s.fills})==len(s.fills)
    assert not s.liquidation_audit
    updated=[eid for eid,routes in s.routes.items()if 'typed_updated'in routes];assert updated and all('generic'in s.routes[eid]for eid in updated)
    rejected=[eid for eid,routes in s.routes.items()if 'typed_modify_rejected'in routes];assert rejected and all('generic'in s.routes[eid]for eid in rejected)
    for parent in s.parents:
        assert s._md_plans[parent]['consumed']=={0,1,2}
    commands=[(i,x)for i,x in enumerate(s.standing_tp_audit)if x['event']=='MODIFY_SUBMIT']
    allocations=[x for x in s.standing_tp_audit if x['event']=='INVENTORY_ALLOCATION'];assert len(commands)<=3*len(allocations)
    for index,command in commands:
        returned=[i for i,x in enumerate(s.standing_tp_audit)if x['event']=='PUBLIC_MODIFY_RETURN'and x['sequence']==command['sequence']]
        acked=[(i,x)for i,x in enumerate(s.standing_tp_audit)if x['event']=='LATEST_MODIFY_ACK'and x['sequence']==command['sequence']]
        assert len(returned)==len(acked)==1 and index<returned[0]<acked[0][0]
        assert acked[0][1]['native_event_id']in updated
    assert any(f['raw_position_id']is not None and f['cache_position_id']is None for f in s.fills if f['order_id']in s._tp_owners)
    assert any(x['event']=='ACTUAL_DEBT_RESOLVED'for x in s.standing_tp_audit)
    assert not s._tp_commands and all(s.cache.order(ClientOrderId(oid)).status.name=='CANCELED'for oid in a['old_orders'])
    return dict(status=case+'_NATIVE_REQUIRES_ROOT_ACCEPTANCE',native_flat=True,native_open_orders=0,native_inflight_orders=0,parents=s.parents,actual_modify_rejections=len(s.rejected),native_pending_proofs=len(s.actual_pending),a0_actual_releases=s._md_report()['a0_release_audit']['actual_releases'],stock_auto='NOT_EXPECTED_UNLINKED_NETTING_NO_EXEC_ALGO',N752='PURE_ONLY',late_debt='SOURCE_EXCLUDED_INSERT0_ACTUAL_FLAT_NO_SUBMIT',prefix_authority=False)


def lifecycle(engine):
    return {n:dict(state=getattr(engine.kernel,n).state.name,
        running=bool(getattr(engine.kernel,n).is_running),disposed=bool(getattr(engine.kernel,n).is_disposed))
        for n in ('trader','data_engine','risk_engine','exec_engine','emulator')}


def write(path,value):
    p=Path(path);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(value,indent=2,default=str)+'\n')
    with tmp.open('rb') as f:os.fsync(f.fileno())
    os.replace(tmp,p)


def ordinary_fixture(e,s,capture,case):
    from nautilus_trader.model.data import QuoteTick
    last=-1
    def advance(second,btc='100',bsize='1000',sol='100',ssize='1000',quotes=True,session=None):
        nonlocal last
        ns=int(D(str(second))*S);assert ns>last and ns<=END;last=ns
        e.add_data([venue_mark(i.id,D(px),ns)for i,px in((BTC_PERP,btc),(SOL_PERP,sol))],client_id=ClientId('BYBIT_MARK'),sort=not quotes)
        if session is not None:
            row=seed()[session]
            e.add_data([daily_signal(i.id,D(str(op)),D(str(cl)),D(str(cl)),D(str(cl)),ns)
                for i,op,cl in((BTC_PERP,row.btc_open,row.btc_close),(SOL_PERP,row.sol_close,row.sol_close))],client_id=ClientId('BYBIT_SIGNAL'),sort=False)
        if quotes:e.add_data([QuoteTick(i.id,i.make_price(D(px)),i.make_price(D(px)),i.make_qty(D(size)),i.make_qty(D(size)),ns,ns)
            for i,px,size in((BTC_PERP,btc,bsize),(SOL_PERP,sol,ssize))],sort=True)
        e.run(streaming=True);e.clear_data();s._tp_settled('AFTER_COMPLETE_NATIVE_STREAM',ns);capture('AT_'+str(second).replace('.','_'))
        assert not s._pair_failures and not s._forced_close_reason and not s._liquidating
    def protection():return {(o['kind'],o['level']):oid for oid,o in s._pair_orders.items()
        if o['kind']in('TP','STOP')and not s.cache.order(ClientOrderId(oid)).is_closed}
    s.stage=case+'_NATURAL_ENTRY'
    advance(0,bsize='2',session=729);advance(1,bsize='2');advance(2)
    assert s.quantity(BTC_PERP.id)==D(2)and s._split_parent['first_quantity']>D(2)
    advance(70);advance(72.01,quotes=False);advance(130);advance(131)
    assert s._pair['entry_terminal']and s.quantity(SOL_PERP.id)==D(2)
    original=protection();assert set(original)=={('TP',0),('TP',1),('TP',2),('STOP',None)}
    if case=='E1':
        s.stage='E1_PARTIAL';advance(135,sol='99',ssize='.2')
        assert protection()==original and s.quantity(SOL_PERP.id)==D('1.8')
        s.stage='E1_MULTIPLE';advance(136,sol='98',ssize='.7')
        assert all(oid==original[key]for key,oid in protection().items())
        s.stage='E1_ACTUAL_FULL_NATIVE_STOP';advance(137,sol='102',ssize='10');advance(138);advance(139);advance(140)
        assert any(f['pair_kind']=='STOP'for f in s.fills)
        stops=[s.cache.order(ClientOrderId(oid))for oid,o in s._pair_orders.items()if o['kind']=='STOP']
        assert stops and all(o.is_closed and o.filled_qty==o.quantity for o in stops)
        assert any(x['event']=='SOL_LATEST_MODIFY_ACK'for x in s.paired_prefix_audit)
    else:
        s.stage='E2_MULTIPLE_150';advance(150,sol='96',ssize='.9');advance(152.01,quotes=False)
        assert all(oid==original[key]for key,oid in protection().items())
        assert not any(s.cache.order(ClientOrderId(oid)).is_pending_cancel for oid in protection().values())
        # A genuine riskOFF/ordinary BTC close starts cancellation at153.
        s.stage='E2_REAL_CLOSE_153';advance(153,btc='120',sol='100')
        pending=[oid for oid in protection().values()if s.cache.order(ClientOrderId(oid)).is_pending_cancel]
        assert pending
        s.stage='E2_PENDING_CANCEL_FILL';advance(153.5,btc='120',sol='96',ssize='.2')
        assert any(f['pending_cancel']and f['pair_kind']=='TP'for f in s.fills)
        advance(155.01,quotes=False);advance(156,btc='120');advance(157,btc='120');advance(160,btc='120')
        assert all(s.cache.order(ClientOrderId(oid)).is_closed for oid in pending)
    assert not e.cache.positions_open()and not e.cache.orders_open()and not e.cache.orders_inflight()and s._pair is None
    assert not s.liquidation_audit and len({f['trade_id']for f in s.fills})==len(s.fills)
    return dict(status=case+'_NATIVE_REQUIRES_ROOT_ACCEPTANCE',native_flat=True,
        original_sol_oids={str(key):oid for key,oid in original.items()},actual_sol_acks=sum(x['event']=='SOL_LATEST_MODIFY_ACK'for x in s.paired_prefix_audit))



def c0_stress_second(e,s,capture,advance,targets):
    s.stage='E2_P2_NATURAL_ENTRY';advance(86400,bsize='2',session=730);advance(86401,bsize='2');advance(86402)
    assert s.quantity(BTC_PERP.id)==D(2)and len(s.parents)==2
    advance(86470);advance(86472.01,quotes=False);advance(86530);advance(86531)
    assert s.quantity(SOL_PERP.id)==D(2)and not s.config.research_a0_original_second
    s.stage='E2_P2_RISK_OFF_CANCEL';advance(86540,btc='99',sol='100')
    pending=[oid for oid,o in s._pair_orders.items()if o['kind']=='TP'and s.cache.order(ClientOrderId(oid)).is_pending_cancel]
    stops=[oid for oid,o in s._pair_orders.items()if o['kind']=='STOP'and not s.cache.order(ClientOrderId(oid)).is_closed]
    assert pending and len(stops)==1 and s._pair['risk']=='INACTIVE_RISK'
    s.stage='E2_P2_NATIVE_PENDING_TP_FILL';advance(86540.25,btc='99',sol='101',ssize='.2')
    assert any(f['pending_cancel']and f['pair_kind']=='TP'and f['stage']==s.stage for f in s.fills)
    before_stop_ids=set(s._pair_orders)
    s.stage='E2_EXPECTED_PARTIAL_IOC_STOP';advance(86540.5,btc='100',sol='98',ssize='.1',expected_fault=True)
    stop=s.cache.order(ClientOrderId(stops[0]))
    assert stop.is_closed and D(0)<stop.filled_qty.as_decimal()<stop.quantity.as_decimal()
    assert s._pair_failures==['PARTIAL_NATIVE_STOP']and s._pair['failed']and s._pair['close_sol']
    assert not s._entries_enabled()and not s.liquidation_audit
    capture('E2_UNSAFE_PARTIAL_STOP_BEFORE_NATIVE_RECOVERY')
    first_stop_fill_ns=min(x['timestamp_ns']for x in s.paired_prefix_audit if x['event']=='SOL_STOP_FILL_CLOSING_BARRIER'and x['order_id']==stops[0])
    # Fresh public quotes before final cancelACK replenish only explicit stock
    # books; no manual close/cache state or matching route is called.
    s.stage='E2_NATIVE_CONSERVATIVE_RECOVERY';advance(86541.5,btc='100',sol='100',expected_fault=True)
    advance(86542.01,quotes=False,expected_fault=True);advance(86543,expected_fault=True)
    advance(86545.01,quotes=False,expected_fault=True);advance(86546,expected_fault=True)
    assert all(s.cache.order(ClientOrderId(oid)).is_closed for oid in pending)
    assert not e.cache.positions_open()and not e.cache.orders_open()and not e.cache.orders_inflight()and s._pair is None
    assert s._pair_failures==['PARTIAL_NATIVE_STOP']and not s.liquidation_audit
    later=[x for x in s.paired_prefix_audit if int(x['timestamp_ns'])>=int(first_stop_fill_ns)]
    assert not any(x['event']=='SOL_MODIFY_SUBMIT'for x in later)
    assert not any(x['event']=='SUBMIT'and x['kind']in('ENTRY','TP','STOP')for x in later)
    assert all(s.cache.order(ClientOrderId(oid)).is_reduce_only for oid in set(s._pair_orders)-before_stop_ids)
    assert any(x['event']=='MARKETABLE_DEBT_DEFER'for x in s.standing_tp_audit)
    assert not any(x['event']=='A0_GRANT_ONCE'for x in s.market_redesign_audit)
    return dict(status='E2_EXPECTED_NEGATIVE_TEST_PASS_REQUIRES_ROOT_REVIEW',native_flat=True,
        expected_faults=['PARTIAL_NATIVE_STOP'],fault_free_financial_pass=False,economic_admission=False,
        parents=s.parents,healthy_defer_before_fault=True,real_SOL_pending_cancel_fill=True,
        partial_STOP_actual_canceled=True,no_STOP_resurrection=True,no_modify_after_STOP_fill=True)


def trim_fixture(e,s,capture):
    from nautilus_trader.model.data import QuoteTick
    last=-1
    def advance(second,btc='100',bsize='1000',session=None,quotes=True):
        nonlocal last
        ns=int(D(str(second))*S);assert ns>last;last=ns
        e.add_data([venue_mark(i.id,D(100),ns)for i in(BTC_PERP,SOL_PERP)],client_id=ClientId('BYBIT_MARK'),sort=not quotes)
        if session is not None:
            row=seed()[session]
            e.add_data([daily_signal(i.id,D(str(op)),D(str(cl)),D(str(cl)),D(str(cl)),ns)
                for i,op,cl in((BTC_PERP,row.btc_open,row.btc_close),(SOL_PERP,row.sol_close,row.sol_close))],client_id=ClientId('BYBIT_SIGNAL'),sort=False)
        if quotes:e.add_data([QuoteTick(i.id,i.make_price(D(px)),i.make_price(D(px)),i.make_qty(D(sz)),i.make_qty(D(sz)),ns,ns)
            for i,px,sz in((BTC_PERP,btc,bsize),(SOL_PERP,'100','1000'))],sort=True)
        e.run(streaming=True);e.clear_data();s._tp_settled('AFTER_COMPLETE_NATIVE_STREAM',ns);capture('TRIM_'+str(second).replace('.','_'))
        assert not s._pair_failures and not s._forced_close_reason and not s._liquidating
    def targets():
        ep,m=s._tp_plan();assert ep and m
        return {o['level']:s.cache.order(ClientOrderId(oid))for oid,o in s._tp_owners.items()if o['parent']==ep.id and not s.cache.order(ClientOrderId(oid)).is_closed}
    assert s.config.research_btc_trim_control and not s.config.research_sol_standing_protection and not s.config.research_a0_original_second
    s.stage='E3_FIXED_TRIM_NATIVE_PARENT';advance(0,bsize='2',session=729);advance(1,bsize='2');advance(2)
    assert s.quantity(BTC_PERP.id)==D(2)and len(targets())==3
    original={level:str(o.client_order_id)for level,o in targets().items()}
    advance(70);advance(72.01,quotes=False);assert s._pair['role']=='BTC_TRIM'and not s._pair['trim_activated']
    advance(130);advance(131)
    cap=s._pair['caps'].bmax
    assert s._pair['trim_activated']and s.quantity(BTC_PERP.id)==cap<D(2)
    assert any(f['pair_kind']=='BTC_DEBT'for f in s.fills)
    assert not any(f['instrument']==str(SOL_PERP.id)for f in s.fills)
    assert {level:str(o.client_order_id)for level,o in targets().items()}==original
    s.stage='E3_PARTIAL_ORDINARY';advance(135,btc=str(targets()[0].price),bsize='.050')
    assert sum(o.leaves_qty.as_decimal()for o in targets().values())==s.quantity(BTC_PERP.id)
    before_deadline_cap=s._pair['caps'].bmax
    s.stage='E3_NOMINAL_HORIZON_NO_RESTORE';advance(14530)
    assert s._pair['risk']=='INACTIVE_RISK'and s._pair['caps'].bmax==before_deadline_cap
    for second,level in((14540,0),(14542,1),(14544,2)):
        o=targets()[level];advance(second,btc=str(o.price),bsize='1000')
    advance(14547);advance(14550,quotes=False);advance(14551)
    assert not e.cache.positions_open()and not e.cache.orders_open()and not e.cache.orders_inflight()and s._pair is None
    assert not any(o.instrument_id==SOL_PERP.id for o in s.cache.orders())and not s.liquidation_audit
    return dict(status='E3_FIXED_TRIM_REQUIRES_ROOT_REVIEW',native_flat=True,absolute_cap=str(cap),
        no_SOL_orders=True,original_btc_tp_oids=original,actual_native_debt=True)


def prepare_proof():
    configs={};bars=seed();features=None
    for case in('E1','E2','E3','E4','E5'):
        witness=NativeBookWitness(detailed=True);cfg,kwargs=fixture_config(witness,case)
        configs[case]=dict(config=snapshot_config(cfg),registered_kwargs=snapshot_config(kwargs),
            transport=dict(base=0,insert=0,update=0,cancel=2*S if case in('E2','E3','E4')else 0))
        assert cfg.research_btc_trim_control==(case=='E3')
        assert cfg.research_a0_original_second==(case in('E4','E5'))
        assert cfg.research_sol_standing_protection==(case!='E3')
        features=features_for(bars,cfg.candidate)
        assert len(cfg.seed_bars)==729 and cfg.trading_start_open_ns==-DAY and cfg.terminal_close_at_ns==END
        assert [features[i].side for i in(729,730)]==[1,-1]
        assert all(completed_wave_levels(bars,features,i,cfg.candidate,features[i].side)for i in(729,730))
    tree=ast.parse(Path(__file__).read_text())
    constructors=[n for n in ast.walk(tree)if isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=='BacktestEngine']
    assert len(constructors)==1
    assert not any(isinstance(n,ast.ImportFrom)and n.module and n.module.startswith(('run_','test_'))for n in ast.walk(tree))
    assert RegisteredProbe._entries_enabled is WaveOverlayStrategy._entries_enabled
    return dict(status='ENGINE_FREE_CONFIG_AST_PASS',engine_constructors=0,declared_constructor_sites=1,
        configs=configs,processed_data_ns=[0,END],config_guard_ns=[-DAY,END],native_reachability='NOT_RUN_UNKNOWN')

def child(gate_path,ledger_path,attempt):
    # Outer stdlib supervisor has already durably claimed even import failures.
    g=json.loads(Path(gate_path).read_text());ledger=json.loads(Path(ledger_path).read_text())
    row=next(x for x in ledger['attempts']if x['attempt_id']==attempt)
    assert row['status']=='STARTED'and row['gate_sha256']==hashlib.sha256(Path(gate_path).read_bytes()).hexdigest()
    assert g['root_go']is True and not row.get('engine_constructor_claimed',False)
    namespace=Path(g['namespace']);case=g.get('scenario',g['fixture_id']);assert case in ('E1','E2','E3','E4','E5')
    stress=case in ('E2','E3','E4');cancel=2*S if stress else 0
    witness=NativeBookWitness(detailed=True);cfg,kwargs=fixture_config(witness,case)
    config_pin=snapshot_config(cfg);kwargs_pin=snapshot_config(kwargs)
    assert config_pin['sha256']==g['native_config_sha256']and kwargs_pin['sha256']==g['registered_kwargs_sha256']
    assert g['transport']==dict(base=0,insert=0,update=0,cancel=cancel)
    write(namespace/'config.json',dict(config=config_pin,kwargs=kwargs_pin,
        data_ns=[0,END],config_ns=[-DAY,END],previous_config_day_guard=True,transport=dict(base=0,insert=0,update=0,cancel=cancel)))
    assert END<=48*3600*S and cfg.trading_start_open_ns==-DAY and cfg.terminal_close_at_ns==END
    # This process has exactly one native constructor. Record intent before it.
    row.update(engine_constructor_claimed=True,child_pid=os.getpid(),engine_constructor_count=1)
    write(ledger_path,ledger);write(namespace/'ENGINE_INTENT.json',dict(attempt_id=attempt,pid=os.getpid(),source_commit=g['source_commit'],constructor_count=1))
    e=s=None;rc=1;errors=[];result=None
    def capture(label):
        if e is None:return
        account=e.cache.account_for_venue(SIM)
        write(namespace/(label+'.json'),dict(label=label,attempt_id=attempt,pid=os.getpid(),lifecycle=lifecycle(e),
            cash=None if account is None else str(account.balance_total()),orders=[]if s is None else s.orders(),
            positions=[]if s is None else s.positions(),events=[]if s is None else s.events,fills=[]if s is None else s.fills,
            standing=[]if s is None else s.standing_tp_audit,paired=None if s is None else s._pair_report(),
            market_redesign=None if s is None else s._md_report(),margin_checks=[]if s is None else s.margin_checks))
    try:
        e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR')))
        module=BybitTierMarginModule((),((BTC_PERP.id,D(40)),(SOL_PERP.id,D(20))),120*S)
        e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,
            starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,
            default_leverage=D(1),liquidity_consumption=True,bar_execution=False,use_message_queue=True,
            use_reduce_only=True,modules=[module,witness],latency_model=LatencyModel(base_latency_nanos=0,
                insert_latency_nanos=0,update_latency_nanos=0,cancel_latency_nanos=cancel))
        for i in(BTC_PERP,SOL_PERP):e.add_instrument(perpetual(i.raw_symbol.value,i.base_currency,str(i.price_increment),str(i.size_increment),str(i.margin_init),maker_fee=D('.00020'),taker_fee=D('.00055')))
        s=RegisteredProbe(cfg);s.journal_path=namespace/'native-events.jsonl';witness.bind(s);e.add_strategy(s)
        result=ordinary_fixture(e,s,capture,case)if case=='E1'else trim_fixture(e,s,capture)if case=='E3'else integration_fixture(e,s,capture,case)
        capture('BEFORE_TERMINAL');rc=0
    except BaseException as error:
        errors.append(dict(stage='FIXTURE',type=type(error).__name__,error=str(error),traceback=traceback.format_exc()));capture('FAILURE_BEFORE_END')
    finally:
        if e is not None:
            capture('BEFORE_END')
            try:
                if any(x['running']for x in lifecycle(e).values()):e.end()
                capture('AFTER_END')
                if not all(x['state']=='STOPPED'and not x['running']for x in lifecycle(e).values()):raise AssertionError('FIVE_COMPONENTS_NOT_STOPPED')
            except BaseException as error:errors.append(dict(stage='END',error=repr(error)));rc=1
            capture('BEFORE_DISPOSE')
            try:
                e.dispose()
                if not all(x['disposed']for x in lifecycle(e).values()):raise AssertionError('NOT_ALL_DISPOSED')
            except BaseException as error:errors.append(dict(stage='DISPOSE',error=repr(error)));rc=1
            write(namespace/'AFTER_DISPOSE.json',dict(lifecycle=lifecycle(e)))
        write(namespace/'result.json',dict(child_exit_code=rc,result=result,errors=errors,attempt_id=attempt,fixture_id=g['fixture_id']))
    return rc

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--gate',required=True);p.add_argument('--ledger',required=True);p.add_argument('--attempt',required=True);a=p.parse_args()
    raise SystemExit(child(a.gate,a.ledger,a.attempt))
