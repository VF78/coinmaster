"""Single last-slot registered R2_A0 native integration/API fixture.

No alternate matcher, native cache mutation, domain/position reset, tier bypass,
explicit position linkage, execution algorithm, transport swap, retry or hidden
constructor. All quantities are native registered sizing/fills; N752 is pure-only.
"""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timedelta,timezone
from inspect import signature
import argparse,ast,copy,hashlib,json,math,os,traceback,uuid
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
from run_continuous_hedge_preflight import registered_fixture_context,snapshot_config
from run_queued_standing_tp import digest,canonical,raw_rows,write,now,lifecycle
from test_standing_tp_pure import proof as product_pure

PROTOCOL='54ecd880f4e072dc55624735222f9c789e1e355f53ae0656e92f47b7e0c4d4c6'
OWNER='1629dc8e5c7044c1a3751d4e8f5a98847ccd7585a5241a5e6b8a644370d318d9'
LEDGER='1130c9614a6eac88fe1d2256fa44af2eef418fc37f20d15dbbe2599c2ac24f7a'
BASE='763d985617abd7a7afef5eec13912303983d8837'
CASE='F4_REGISTERED_R2_QUEUED_STANDING_TP';S=1_000_000_000;DAY=86400*S;END=90600*S


def seed():
    epoch=datetime(1970,1,1,tzinfo=timezone.utc);bars=[]
    for i in range(731):
        btc=100*math.exp(.05*math.sin(2*math.pi*i/20)+.0001*i)
        sol=100*(btc/100)**1.2*math.exp(.002*math.sin(2*math.pi*i/7));close=epoch+timedelta(days=i-729)
        bars.append(DailyBar(close-timedelta(days=1),close,close,bars[-1].btc_close if bars else btc,btc,sol))
    return tuple(bars)


def feed():
    return tuple(PairedSignal(t,t,t+60*S,D(100),D(100),D(1),D(2),True,side==1,side==-1,False,False,D(120),D('99.2'),D(100))for t,side in((70*S,1),(DAY+70*S,-1)))


def fixture_config(witness):
    kwargs=build_a0_kwargs(Path('.'),Path('.'),'R2_A0',feed(),start_ms=-86400000,end_ms=90600000,standing_tp=True)
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
        # Deliberately invalid API diagnostic ONLY on the genuine partial SOL TP.
        # Protective BTC controller commands never receive a fixture exemption.
        if self.stage=='P1_SOL_RELIEF' and owner and owner['kind']=='TP' and event.instrument_id==self.config.sol_id and self.diag is None:
            assert order.filled_qty.as_decimal()>=D('.2') and order.status.name=='PARTIALLY_FILLED'and not order.is_pending_cancel
            self.diag=dict(order_id=oid,quantity=str(order.quantity),filled=str(order.filled_qty),invalid_total='.1',pre_request_status=order.status.name)
            self.modify_order(order,quantity=self.cache.instrument(self.config.sol_id).make_qty(D('.1')))
            assert order.status.name=='PENDING_UPDATE'and self.diag.get('actual_pending_update_event_id')
            self.diag['public_return_status']=order.status.name
        result=super().on_order_filled(event)
        if self._domain.episode and self._domain.episode.id not in self.parents:self.parents.append(self._domain.episode.id)
        return result


def pure_preconditions():
    out=product_pure();witness=NativeBookWitness(detailed=True);cfg,kwargs=fixture_config(witness);bars=seed();features=features_for(bars,cfg.candidate)
    assert len(cfg.seed_bars)==729 and [features[i].side for i in(729,730)]==[1,-1]
    assert cfg.trading_start_open_ns==-DAY and cfg.terminal_close_at_ns==END and END<=48*3600*S
    assert kwargs['research_btc_q_mode']=='LEGACY_Q_CONTROL' and kwargs['research_paired_prefix']=='B2_F0'and kwargs['research_a0_original_second']is True
    assert all(completed_wave_levels(bars,features,i,cfg.candidate,features[i].side)for i in(729,730))
    assert RegisteredProbe._entries_enabled is WaveOverlayStrategy._entries_enabled
    method=ast.parse(__import__('inspect').getsource(RegisteredProbe)).body[0]
    tier=next(n for n in method.body if isinstance(n,ast.FunctionDef)and n.name=='_tier_allows_increase')
    assert any(isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr=='_tier_allows_increase'for n in ast.walk(tier))
    tree=ast.parse(Path(__file__).read_text());constructors=[n for n in ast.walk(tree)if isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=='BacktestEngine'];assert len(constructors)==1
    for n in ast.walk(tree):
        if isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr=='submit_order':assert not any(k.arg in('position_id','exec_algorithm_id')for k in n.keywords)
        if isinstance(n,ast.ImportFrom):assert n.module not in('run_tp_continuity_feasibility','run_tp_continuity_stress')
    return dict(status='ENGINE_FREE_PRECONDITIONS_PASS',engine_constructors=0,product=out,config=snapshot_config(cfg),registered_kwargs=snapshot_config(kwargs),seed_bars=729,sides=[1,-1],clock=dict(data_ns=[0,END],config_ns=[-DAY,END]),explicit_position_id=False,latency=dict(base=0,insert=0,update=0,cancel=2*S),unknown_essential='STOP_NO_PREFIX')


def verify(gate_path,ledger_path,go=False):
    g=json.loads(Path(gate_path).read_text());raw=Path(ledger_path).read_text();l=json.loads(raw)
    assert g['protocol_sha256']==PROTOCOL and g['fixture_id']==CASE and g['expected_before']==3
    assert digest(ledger_path)==LEDGER and l['physical_max']==4 and l['physical_started']==3 and len(l['attempts'])==3 and l['active']==0
    for row,text,pin in zip(l['attempts'],raw_rows(raw),g['preserved_failed_attempts']):
        assert row['status']=='FAILED'and row['actual_process_exit_code']==1
        assert canonical(row)==pin['canonical_entry_sha256']and hashlib.sha256(text.encode()).hexdigest()==pin['raw_entry_sha256']
    assert len(g['preserved_failed_attempts'])==3 and g['source_base']==BASE
    approval=g['owner_approval'];assert approval['sha256']==OWNER and digest(approval['path'])==OWNER
    a=json.loads(Path(approval['path']).read_text());assert type(a.get('exact_human_answer'))is str and a['exact_human_answer'].strip()and a['status']=='APPROVED_BY_OWNER'and a['protocol_sha256']==PROTOCOL
    assert a['engineering_total_max']==4 and a['engineering_already_started']==3 and a['remaining_instances']==1 and a['prefix_already_started']==0
    for pin in g['immutable_pins']:assert digest(pin['path'])==pin['sha256'],pin['path']
    proof=pure_preconditions()
    assert proof['config']['sha256']==g['native_config_sha256'] and proof['registered_kwargs']['sha256']==g['registered_kwargs_sha256']
    assert not Path(g['namespace']).exists(),'FRESH_NAMESPACE_REQUIRED'
    if go:assert g['root_go']is True,'ROOT_GO_REQUIRED'
    return g,l,raw


def run_fixture(e,s,capture):
    from nautilus_trader.model.data import QuoteTick
    last=-1
    def advance(second,btc='100',bsize='1000',sol='100',ssize='1000',fresh=True,quotes=True,session=None):
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
        assert not s._pair_failures and not s._forced_close_reason and not s._liquidating
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
    assert s.rejected and s.diag and s._pair['debt_since']is not None
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
    s.stage='P2_ORDINARY_TP_CANCEL';advance(86887,btc=str(targets()[0].price),bsize='.050');assert release.is_pending_cancel
    closed_cap=s._pair['caps'].bmax
    s.stage='P2_PENDING_CANCEL_LATE_FILL';prior_filled=release.filled_qty.as_decimal();advance(86887.5,btc='102',bsize='2')
    assert release.filled_qty.as_decimal()>prior_filled and s._pair['caps'].bmax==closed_cap and s._pair['debt_since']is not None
    capture('ACTUAL_A0_PENDING_CANCEL_LATE_FILL')
    advance(86889.01,quotes=False);assert release.status.name=='CANCELED'
    s.stage='P2_EXCESS_DEBT';advance(86890);advance(86891);assert held()<=closed_cap and a['granted_cap']==cap
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
    return dict(status='F4_REGISTERED_NATIVE_PASS_REQUIRES_ROOT_ACCEPTANCE',native_flat=True,native_open_orders=0,native_inflight_orders=0,parents=s.parents,actual_modify_rejections=len(s.rejected),native_pending_proofs=len(s.actual_pending),a0_actual_releases=s._md_report()['a0_release_audit']['actual_releases'],stock_auto='NOT_EXPECTED_UNLINKED_NETTING_NO_EXEC_ALGO',N752='PURE_ONLY',late_debt='SOURCE_EXCLUDED_INSERT0_ACTUAL_FLAT_NO_SUBMIT',prefix_authority=False)


def launch(gate_path,ledger_path):
    g,l,raw=verify(gate_path,ledger_path,True);namespace=Path(g['namespace']);namespace.mkdir(parents=True)
    # Exact raw prior ledger saved durably BEFORE the sole constructor/claim.
    before=namespace/'LEDGER_BEFORE_CLAIM.json';before.write_text(raw)
    with before.open('rb')as f:os.fsync(f.fileno())
    attempt=str(uuid.uuid4());entry=dict(attempt_id=attempt,physical_index=4,fixture_id=CASE,status='STARTED',started_utc=now(),source_commit=g['source_commit'],gate_sha256=digest(gate_path),protocol_sha256=PROTOCOL,namespace=str(namespace),ledger_before_sha256=digest(before))
    # Preserve old attempt text byte-for-byte within the append-mutated ledger.
    prior=raw_rows(raw);l['attempts'].append(entry);l.update(physical_started=4,active=1,authorized_remaining=0,status='RUNNING');write(ledger_path,l)
    text=Path(ledger_path).read_text()
    for old,new in zip(prior,raw_rows(text)):assert old==new,'FAILED_RAW_ROW_PRESERVATION'
    e=s=witness=None;rc=1;result=None;errors=[]
    def capture(label):
        if e is None:return
        account=e.cache.account_for_venue(SIM)
        write(namespace/(label+'.json'),dict(label=label,attempt_id=attempt,physical_index=4,lifecycle=lifecycle(e),cash=None if account is None else str(account.balance_total()),orders=[]if s is None else s.orders(),positions=[]if s is None else s.positions(),events=[]if s is None else s.events,fills=[]if s is None else s.fills,standing=[]if s is None else s.standing_tp_audit,market_redesign=None if s is None else s._md_report(),paired=None if s is None else s._pair_report(),actual_pending=[]if s is None else s.actual_pending,modify_rejections=[]if s is None else s.rejected,margin_checks=[]if s is None else s.margin_checks))
    try:
        witness=NativeBookWitness(detailed=True);cfg,_=fixture_config(witness)
        e=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR')))
        module=BybitTierMarginModule((),((BTC_PERP.id,D(40)),(SOL_PERP.id,D(20))),120*S)
        e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,default_leverage=D(1),liquidity_consumption=True,bar_execution=False,use_message_queue=True,use_reduce_only=True,modules=[module,witness],latency_model=LatencyModel(base_latency_nanos=0,insert_latency_nanos=0,update_latency_nanos=0,cancel_latency_nanos=2*S))
        for i in(BTC_PERP,SOL_PERP):e.add_instrument(perpetual(i.raw_symbol.value,i.base_currency,str(i.price_increment),str(i.size_increment),str(i.margin_init),maker_fee=D('.00020'),taker_fee=D('.00055')))
        s=RegisteredProbe(cfg);s.journal_path=namespace/'native-events.jsonl';witness.bind(s);e.add_strategy(s)
        result=run_fixture(e,s,capture);capture('BEFORE_TERMINAL');rc=0
    except BaseException as error:
        errors.append(dict(stage='FIXTURE',type=type(error).__name__,error=str(error),traceback=traceback.format_exc()));capture('FAILURE_BEFORE_END')
    finally:
        if e is not None:
            capture('BEFORE_END')
            if any(x['running']for x in lifecycle(e).values()):
                try:e.end()
                except BaseException as error:errors.append(dict(stage='END',error=repr(error)));rc=1
                capture('AFTER_END')
                if not all(x['state']=='STOPPED'and not x['running']for x in lifecycle(e).values()):rc=1;errors.append(dict(stage='END',error='FIVE_NATIVE_COMPONENTS_NOT_STOPPED'))
            else:
                capture('END_NOT_APPLICABLE')
                if rc==0:rc=1;errors.append(dict(stage='END',error='PASS_REQUIRES_ACTUAL_STARTED_THEN_STOPPED'))
            capture('BEFORE_DISPOSE')
            try:e.dispose()
            except BaseException as error:errors.append(dict(stage='DISPOSE',error=repr(error)));rc=1
            write(namespace/'AFTER_DISPOSE.json',dict(lifecycle=lifecycle(e)))
            if not all(x['disposed']for x in lifecycle(e).values()):rc=1
        write(namespace/'result.json',dict(actual_process_exit_code=rc,result=result,errors=errors,attempt_id=attempt,fixture_id=CASE))
        l=json.loads(Path(ledger_path).read_text());row=l['attempts'][3];row.update(status='COMPLETED'if rc==0 else'FAILED',finished_utc=now(),actual_process_exit_code=rc,result_path=str(namespace/'result.json'),result_sha256=digest(namespace/'result.json'));l.update(active=0,authorized_remaining=0,status='CLOSED_4_OF_4_NO_MORE_ENGINE');write(ledger_path,l)
    return rc


def main():
    p=argparse.ArgumentParser();p.add_argument('--pure-proof');p.add_argument('--gate');p.add_argument('--ledger');p.add_argument('--prepare',action='store_true');p.add_argument('--launch',action='store_true');a=p.parse_args()
    if a.pure_proof:write(a.pure_proof,pure_preconditions());return 0
    if a.prepare:
        g,l,_=verify(a.gate,a.ledger);print(json.dumps(dict(status='PREPARED_NO_ENGINE',root_go=g['root_go'],physical_started=l['physical_started'],proof=pure_preconditions())));return 0
    if a.launch:return launch(a.gate,a.ledger)
    p.error('Choose --pure-proof, --prepare or --launch')
if __name__=='__main__':raise SystemExit(main())
