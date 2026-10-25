"""Amendment4 F1 public-position stock stress only. Monetary package remains763.

Exactly one native constructor, reached only after verified owner/root GO and
an atomic durable ledger claim. Never collected by pytest or legacy suites.
The probe owns real native orders; expected leaves are assertions, not fills.
"""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime, timezone
import argparse, ast, copy, hashlib, inspect, json, os, subprocess, traceback, uuid
from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.enums import AccountType, OmsType, OrderSide, TimeInForce
from nautilus_trader.model.identifiers import ClientId
from nautilus_trader.model.objects import Money, Quantity
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP, SIM, perpetual, BybitTierMarginModule, MarkPriceUpdate
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from coinmaster.domain.wave_overlay import WaveOverlayState, Episode
from coinmaster.strategy.market_redesign import target_lots
from coinmaster.venues.marks import venue_mark
from run_continuous_hedge_preflight import registered_fixture_context, prepare_completed_day, snapshot_config
from test_native_episode_risk import tick

BASE='763d985617abd7a7afef5eec13912303983d8837'
PROTOCOL='6f89de510dc9550bdd998dfd9d8b2889d590969d1307ddb2bc920ae4546acdda'
PARENT_LEDGER_SHA='d160413ad3dec803e3023438c827fd46029e92c42598d58bb969aa3f4f708d94'
CASE='F1_PUBLIC_POSITION_STOCK_STRESS'
M=60_000_000_000
END=3600_000_000_000
PRICES={0:D('101'),1:D('102'),2:D('103')}
STEP=D('.001')

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def write(path,data):
    path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w') as stream:
        json.dump(data,stream,indent=2,ensure_ascii=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(tmp,path)
def config():return registered_fixture_context('R2',start_ms=-86400000,end_ms=3600000)[0]

def pure_preconditions():
    """Real installed class/config/APIs; deliberately no BacktestEngine instance."""
    import nautilus_trader
    from nautilus_trader.model.events import OrderUpdated, OrderModifyRejected
    cfg=config(); policy=cfg.margin_policy
    add_signature=inspect.signature(BacktestEngine.add_data)
    assert add_signature.parameters['sort'].default is True
    first_batch=[venue_mark(BTC_PERP.id,D(100),1),venue_mark(SOL_PERP.id,D(100),1)]
    second_batch=[tick(BTC_PERP,1),tick(SOL_PERP,1)]
    schedule=first_batch+second_batch
    assert all(x.ts_init==1 and x.ts_event==1 for x in schedule)
    assert sorted(schedule,key=lambda x:x.ts_init)==schedule
    assert [str((getattr(x,'data',x)).instrument_id)for x in schedule]==[str(BTC_PERP.id),str(SOL_PERP.id),str(BTC_PERP.id),str(SOL_PERP.id)]
    tree=ast.parse(Path(__file__).read_text());advance=next(n for n in ast.walk(tree)if isinstance(n,ast.FunctionDef)and n.name=='advance')
    adds=sorted([n for n in ast.walk(advance)if isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr=='add_data'],key=lambda n:n.lineno)
    assert len(adds)==2 and next(k.value.value for k in adds[0].keywords if k.arg=='sort')is False and next(k.value.value for k in adds[-1].keywords if k.arg=='sort')is True
    run=next(n for n in ast.walk(advance)if isinstance(n,ast.Call)and isinstance(n.func,ast.Attribute)and n.func.attr=='run');assert adds[-1].lineno<run.lineno
    dummy={'physical_max':4,'physical_started':2,'active':0,'attempts':[{'physical_index':i,'status':'FAILED','actual_process_exit_code':1,'error':'PRESERVED'+str(i)}for i in(1,2)]}
    raw=json.dumps(dummy,indent=2)
    resume_gate={'expected_before':2,'preserved_failed_attempts':[{'canonical_entry_sha256':canonical(row),'raw_entry_sha256':hashlib.sha256(rawrow.encode()).hexdigest()}for row,rawrow in zip(dummy['attempts'],raw_attempt_rows(raw))]}
    assert resume_state(resume_gate,dummy,raw)==2
    for key,value in [('physical_started',0),('physical_max',3),('active',1)]:
        changed=copy.deepcopy(dummy);changed[key]=value
        try:resume_state(resume_gate,changed,json.dumps(changed,indent=2))
        except AssertionError:pass
        else:raise AssertionError('AMEND4_GUARD_DID_NOT_REJECT_'+key)
    for i in(0,1):
        changed=copy.deepcopy(dummy);changed['attempts'][i]['error']='MUTATED'
        try:resume_state(resume_gate,changed,json.dumps(changed,indent=2))
        except AssertionError:pass
        else:raise AssertionError('AMEND4_FAILED_ROW_CHANGED')
    assert 'position_id'in inspect.signature(WaveOverlayStrategy.submit_order).parameters or 'kwargs'in inspect.signature(WaveOverlayStrategy.submit_order).parameters
    from nautilus_trader.trading.strategy import Strategy
    from nautilus_trader.cache.cache import Cache
    assert 'position_id'in inspect.signature(Strategy.submit_order).parameters
    assert callable(Cache.position_id)and callable(Cache.orders_for_position)
    assert FeasibilityProbe._tier_allows_increase is WaveOverlayStrategy._tier_allows_increase
    assert FeasibilityProbe._entries_enabled is WaveOverlayStrategy._entries_enabled
    assert all(c.__name__!='NativeProbe'for c in FeasibilityProbe.__mro__)
    import_nodes=[n.module for n in ast.walk(tree)if isinstance(n,ast.ImportFrom)]
    assert 'run_tp_continuity_feasibility'not in import_nodes,'DIRTY_OLD_DRAFT_DEPENDENCY_FORBIDDEN'
    assert Path(inspect.getfile(registered_fixture_context)).parent==Path(__file__).parent
    assert Path(inspect.getfile(tick)).parent==Path(__file__).parent
    assert sum(isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=='BacktestEngine'for n in ast.walk(tree))==1
    policy.update_mark(MarkPriceUpdate(BTC_PERP.id,D('100'),1))
    initial,maintenance,mark=policy.margin_for(BTC_PERP.id,D('1'),1)
    assert initial>0 and maintenance>0 and mark==D('100')
    assert target_lots(1000,set())=={0:212,1:212,2:576}
    assert target_lots(750,set())=={0:159,1:159,2:432}
    assert target_lots(175,{0,1})=={2:175}
    assert Quantity.from_str('0.159').as_decimal()==159*STEP
    assert allocation_window({0:D('.212')},{0:D('.159')},D(100))[0]=='NONMARKETABLE_TRANSIENT'
    assert allocation_window({0:D('.212')},{0:D('.159')},D(101))[0]=='MARKETABLE_ALLOCATION_NOT_PROVEN'
    assert allocation_window({0:D('.212')},{0:D('.159')},None)[0]=='UNKNOWN_BOOK_NOT_PROVEN'
    assert allocation_window({0:D('.212')},{0:D('.159')},D(101),True)[0]=='NONMATCHING_PENDING_UPDATE_PRE_APPLY'
    assert allocation_window({0:D('.212')},{0:D('.159')},(D(100),D('100.5')))[0]=='NONMARKETABLE_TRANSIENT'
    assert allocation_window({0:D('.212')},{0:D('.159')},(D(104),D(100)))[0]=='MARKETABLE_ALLOCATION_NOT_PROVEN'
    assert allocation_window({0:D('.212')},{0:D('.159')},(D(100),D(104)))[0]=='MARKETABLE_ALLOCATION_NOT_PROVEN'
    assert allocation_window({0:D('.212')},{0:D('.159')},(None,D(100)))[0]=='UNKNOWN_BOOK_NOT_PROVEN'
    domain=WaveOverlayState(cfg.candidate);domain.set_execution_lots(btc=STEP,sol=D('.1'));ep=Episode('PURE_ENTITLEMENT',1,10000.,1.,btc_initial_qty=1.,btc_open_qty=1.)
    domain.episode=ep;ep.btc_tp_target_lots={0:159,1:159,2:432};ep.btc_tp_target_qty={0:.159,1:.159,2:.432}
    intent=domain._intent(ep,'BTC_REDUCE',-1,0,quantity=.159)
    domain.on_fill(intent.id,.05,101.,datetime.fromtimestamp(1,timezone.utc));assert 0 not in ep.btc_filled_tps
    domain.on_fill(intent.id,.109,101.,datetime.fromtimestamp(2,timezone.utc));assert 0 in ep.btc_filled_tps
    return dict(engine_constructors=0,actual_add_data_signature=str(add_signature),real_data_schedule=[dict(type=type(x).__name__,instrument=str((getattr(x,'data',x)).instrument_id),ts_init=x.ts_init)for x in schedule],AST_final_batch_sorted=True,failed_row_resume_rejections=5,native_version=nautilus_trader.__version__,config=snapshot_config(cfg),actual_policy_type=type(policy).__name__,positive_initial=str(initial),positive_maintenance=str(maintenance),native_event_classes=[OrderUpdated.__name__,OrderModifyRejected.__name__],native_modify_signature=str(inspect.signature(WaveOverlayStrategy.modify_order)),data_window_ns=[1,END],config_window_ns=[-86400_000_000_000,END],contract='synthetic L1 API feasibility, not financial/parity/venue admission')

def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def raw_attempt_rows(text):
    decoder=json.JSONDecoder();i=text.index('[',text.index('"attempts"'))+1;rows=[]
    while True:
        while text[i].isspace()or text[i]==',':i+=1
        if text[i]==']':return rows
        _,end=decoder.raw_decode(text,i);rows.append(text[i:end]);i=end
def resume_state(gate,ledger,raw):
    assert type(gate.get('expected_before'))is int and gate['expected_before']==2,'EXACT_PHYSICAL3_ONLY'
    assert ledger['physical_max']==4 and ledger['physical_started']==2 and len(ledger['attempts'])==2 and ledger['active']==0,'AMEND4_RESUME_COUNT_MISMATCH'
    expected=gate['preserved_failed_attempts'];assert len(expected)==2
    rows=raw_attempt_rows(raw)
    for i,(row,pin)in enumerate(zip(ledger['attempts'],expected)):
        assert row['physical_index']==i+1 and row['status']=='FAILED'and row['actual_process_exit_code']==1,'PRIOR_FAILURES_MUST_STAY_FAILED'
        assert canonical(row)==pin['canonical_entry_sha256'],'FAILED_ROW_CHANGED'
        assert hashlib.sha256(rows[i].encode()).hexdigest()==pin['raw_entry_sha256'],'FAILED_ROW_RAW_CHANGED'
    return 2

def verify(gate_path,ledger_path,require_go=False):
    gate=json.loads(Path(gate_path).read_text());raw_ledger=Path(ledger_path).read_text();ledger=json.loads(raw_ledger)
    assert gate['protocol_sha256']==PROTOCOL and gate['fixture_id']==CASE
    assert gate['source_base']==BASE and gate['engineering_physical_max']==4
    assert gate['native_engine']=='1.231.0' and gate['fixture_window_ns']==[1,END]
    assert gate['product_patch_allowed'] is False
    approval=gate['owner_approval'];assert digest(approval['path'])==approval['sha256']
    owner=json.loads(Path(approval['path']).read_text());reply=owner.get('exact_human_answer')
    assert type(reply)is str and reply.strip() and owner['status']=='APPROVED_BY_OWNER'
    assert owner['approved_protocol_sha256']==PROTOCOL and owner['engineering_total_max']==4 and owner['engineering_already_started']==2
    assert owner['before_amendment_ledger_sha256']==PARENT_LEDGER_SHA and owner['prefix_max_unchanged']==3 and owner['prefix_already_started']==0
    resume_state(gate,ledger,raw_ledger)
    parent=gate['preserved_failed_ledger'];assert parent['ledger_sha256']==PARENT_LEDGER_SHA and digest(parent['ledger_path'])==PARENT_LEDGER_SHA
    assert json.loads(Path(parent['ledger_path']).read_text())['attempts']==ledger['attempts']
    assert ledger['protocol_sha256']==PROTOCOL and ledger['source_base']==BASE
    assert ledger['before_amendment_ledger']['sha256']==PARENT_LEDGER_SHA and ledger['owner_amendment4']['sha256']==approval['sha256']
    for item in gate['immutable_pins']:assert digest(item['path'])==item['sha256'],item['path']
    assert not Path(gate['namespace']).exists(),'FRESH_NAMESPACE_REQUIRED'
    if require_go:assert gate['root_go'] is True,'ROOT_GO_REQUIRED'
    return gate,ledger

def allocation_window(actual,wanted,book,pre_apply_pending=False):
    mismatch=sorted(k for k in set(actual)|set(wanted) if actual.get(k,D(0))!=wanted.get(k,D(0)))
    if not mismatch:return 'EXACT',[]
    if pre_apply_pending:return 'NONMATCHING_PENDING_UPDATE_PRE_APPLY',mismatch
    candidates=book if isinstance(book,tuple) else (book,)
    if not candidates or any(b is None for b in candidates):return 'UNKNOWN_BOOK_NOT_PROVEN',mismatch
    marketable=[k for k in mismatch if actual.get(k,D(0))>0 and any(PRICES[k]<=b for b in candidates)]
    return ('MARKETABLE_ALLOCATION_NOT_PROVEN' if marketable else 'NONMARKETABLE_TRANSIENT'),mismatch


class FeasibilityProbe(WaveOverlayStrategy):
    """Fixture transport; no change to production money/order functions.

    Increases call the inherited real margin gate. Native cache is the only
    order/position/fill authority. Bounded updates compare actual total quantity
    against actual filled plus planned leaves; no ACK/fill fabrication.
    """
    def __init__(self,cfg):
        super().__init__(cfg)
        self.events=[];self.fills=[];self.targets={};self.kinds={};self.expected={}
        self.consumed=set();self.guard_calls=[];self.debt_cap=None;self.tp_active=False
        self.correcting=set();self.modify_count={};self.max_depth=0;self.depth=0
        self.rejections=[];self.boundary_violations=[];self.transient_allocation_drift=[]
        self.native_coverage_gaps=[];self.stage='BOOT';self.suppress_correction=False;self.event_routes={};self.book=(None,);self.settled_book=None;self.book_trace=[];self.nonexecutable_transients=[];self.auto_updates=[];self.pre_fill_checks=[];self.same_oid_overlap=[]
        self.oracle_domain=WaveOverlayState(self._domain.config);self.oracle_domain.set_execution_lots(btc=STEP,sol=D('.1'));self.oracle_intents={};self.command_stack=[];self.commands=[];self.native_trade_ids=set();self.quote_context=None;self.quote_sell_filled=D(0);self.book_refinements=[];self.native_acknowledged_ids=set()
    def held(self,inst=BTC_PERP):
        positions=[p for p in self.cache.positions_open() if p.instrument_id==inst.id]
        if not positions:return D(0)
        assert len(positions)==1
        return positions[0].quantity.as_decimal()*(1 if positions[0].is_long else -1)
    def order_rows(self):
        return [dict(id=str(o.client_order_id),instrument=str(o.instrument_id),kind=self.kinds.get(str(o.client_order_id)),native_position_id=None if o.position_id is None else str(o.position_id),cache_position_id=None if self.cache.position_id(o.client_order_id)is None else str(self.cache.position_id(o.client_order_id)),status=o.status.name,quantity=str(o.quantity),filled=str(o.filled_qty),leaves=str(o.leaves_qty),side=o.side.name,reduce_only=o.is_reduce_only,price=str(getattr(o,'price',None))) for o in self.cache.orders()]
    def native_position_index(self):
        return [dict(position_id=str(p.id),instrument=str(p.instrument_id),quantity=str(p.quantity),side='LONG'if p.is_long else'SHORT',indexed_order_ids=[str(o.client_order_id)for o in self.cache.orders_for_position(p.id)])for p in self.cache.positions_open()]
    def record(self,event,**extra):
        account=self.cache.account_for_venue(SIM)
        row=dict(sequence=len(self.events)+1,event=event,stage=self.stage,ts_ns=self.clock.timestamp_ns(),btc=str(self.held()),sol=str(self.held(SOL_PERP)),cash=str(account.balance_total())if account else None,expected_leaves={str(k):str(v)for k,v in self.expected.items()},consumed=sorted(self.consumed),domain_consumed=[]if self.oracle_domain.episode is None else sorted(self.oracle_domain.episode.btc_filled_tps),book_bid_candidates=[None if b is None else str(b)for b in self.book],command_stack=[{'command_id':c['command_id'],'order_id':c['order_id']}for c in self.command_stack],orders=self.order_rows(),native_position_index=self.native_position_index(),**extra)
        self.events.append(row)
        if self.tp_active and self.held()>0:
            missing=[]
            for level,leaves in self.expected.items():
                if leaves<=0:continue
                oid=self.targets.get(level);order=self.cache.order(oid) if oid else None
                # Raw entry snapshots remain, but native FILLED/domain-consumed
                # targets are not required merely because actor expected is stale.
                domain_consumed=self.oracle_domain.episode and level in self.oracle_domain.episode.btc_filled_tps
                if domain_consumed or (order is not None and order.status.name=='FILLED'):continue
                if order is None or str(oid)not in self.native_acknowledged_ids or order.is_closed or order.leaves_qty.as_decimal()<=0 or not order.is_reduce_only or order.price.as_decimal()!=PRICES[level]:missing.append(level)
            if missing:self.native_coverage_gaps.append(dict(sequence=row['sequence'],event=event,missing=missing,ts_ns=row['ts_ns']));raise AssertionError('ACTUAL_REQUIRED_TARGET_GAP')
        return row
    def boundary(self,label,pre_apply_pending=False):
        self.record('BOUNDARY_OBSERVATION',label=label,pre_apply_pending=pre_apply_pending)
        if self.tp_active and self.held()>0:
            actual={level:self.cache.order(oid).leaves_qty.as_decimal() for level,oid in self.targets.items() if level not in self.consumed and not self.cache.order(oid).is_closed}
            wanted={k:v for k,v in self.expected.items() if v>0}
            classification,mismatch=allocation_window(actual,wanted,self.book,pre_apply_pending)
            row=dict(label=label,classification=classification,mismatch=mismatch,book_bid_candidates=[None if b is None else str(b)for b in self.book],actual={str(k):str(v)for k,v in actual.items()},wanted={str(k):str(v)for k,v in wanted.items()},held=str(self.held()))
            if classification in ('MARKETABLE_ALLOCATION_NOT_PROVEN','UNKNOWN_BOOK_NOT_PROVEN'):
                self.boundary_violations.append(row);raise AssertionError(classification)
            elif classification!='EXACT':self.nonexecutable_transients.append(row)
            if sum(wanted.values(),D(0))!=self.held():
                self.boundary_violations.append(dict(label=label,classification='ORACLE_NATIVE_INVENTORY_MISMATCH',wanted_sum=str(sum(wanted.values(),D(0))),held=str(self.held())));raise AssertionError('ORACLE_NATIVE_INVENTORY_MISMATCH')
            position=next(p for p in self.cache.positions_open()if p.instrument_id==BTC_PERP.id)
            for level,oid in self.targets.items():
                order=self.cache.order(oid)
                if level in self.consumed and not order.is_closed and order.leaves_qty.as_decimal()>0:raise AssertionError('CONSUMED_TARGET_REMAINS_LIVE')
                if level not in self.consumed and not order.is_closed:assert self.cache.position_id(oid)==position.id,'NATIVE_TP_POSITION_ASSOCIATION_CHANGED'
        assert self.held()>=0,'NATIVE_BTC_REVERSED'
    def market(self,inst,side,qty,kind,reduce=False):
        qty=D(qty)
        if not reduce:
            enabled=WaveOverlayStrategy._entries_enabled(self)
            admitted=enabled and WaveOverlayStrategy._tier_allows_increase(self,inst.id,side,qty,self.clock.timestamp_ns())
            self.guard_calls.append(dict(instrument=str(inst.id),quantity=str(qty),allowed=admitted,entries_enabled=enabled,ts_ns=self.clock.timestamp_ns()))
            assert admitted,'ACTUAL_STOCK_MARGIN_DENIED'
        order=self.order_factory.market(inst.id,side,inst.make_qty(qty),time_in_force=TimeInForce.IOC,reduce_only=reduce)
        self.kinds[str(order.client_order_id)]=kind;self.submit_order(order);return order
    def install_targets(self):
        assert self.held()==D('1')
        native_positions=[p for p in self.cache.positions_open()if p.instrument_id==BTC_PERP.id]
        assert len(native_positions)==1 and native_positions[0].is_long
        actual_position_id=native_positions[0].id
        self.expected={k:D(v)*STEP for k,v in target_lots(1000,set()).items()}
        self.oracle_domain.episode=Episode(CASE,1,10000.,1.,btc_initial_qty=1.,btc_open_qty=1.,btc_entry_qty_exact=D('1'))
        self.sync_oracle_allocation()
        for level,leaves in self.expected.items():
            o=self.order_factory.limit(BTC_PERP.id,OrderSide.SELL,BTC_PERP.make_qty(leaves),BTC_PERP.make_price(PRICES[level]),time_in_force=TimeInForce.GTC,post_only=False,reduce_only=True)
            self.targets[level]=o.client_order_id;self.kinds[str(o.client_order_id)]='TP'+str(level)
            self.oracle_intents[str(o.client_order_id)]=self.oracle_domain._intent(self.oracle_domain.episode,'BTC_REDUCE',-1,level,quantity=float(leaves)).id
            self.submit_order(o,position_id=actual_position_id)
    def sync_oracle_allocation(self):
        ep=self.oracle_domain.episode
        for level,leaves in self.expected.items():
            ep.btc_tp_target_lots[level]=ep.btc_tp_filled_lots.get(level,0)+int(leaves/STEP)
            ep.btc_tp_target_qty[level]=float(D(ep.btc_tp_target_lots[level])*STEP)
    def effective_consumed(self):
        ep=self.oracle_domain.episode
        return set(ep.btc_filled_tps if ep else ())|{level for level,oid in self.targets.items() if self.cache.order(oid).status.name=='FILLED'}
    def correct(self,order,trigger_event=None):
        oid=str(order.client_order_id);level=next((i for i,x in self.targets.items()if str(x)==oid),None)
        if level is None or level in self.consumed or order.is_closed or self.suppress_correction:return
        wanted=order.filled_qty.as_decimal()+self.expected[level]
        if order.quantity.as_decimal()==wanted:return
        self.transient_allocation_drift.append(dict(order_id=oid,actual_total=str(order.quantity),wanted_total=str(wanted),ts_ns=self.clock.timestamp_ns()))
        if oid in self.correcting:
            self.same_oid_overlap.append(dict(order_id=oid,ts_ns=self.clock.timestamp_ns(),wanted_total=str(wanted)));return
        n=self.modify_count.get((self.stage,oid),0)+1;self.modify_count[(self.stage,oid)]=n
        assert n<=8,'NONCONVERGENT_NATIVE_QUANTITY_UPDATE'
        limit=order.price.as_decimal();q=self.quote_context
        context=dict(command_id='MODIFY-'+str(len(self.commands)+1),order_id=oid,level=level,requested_total=str(wanted),actual_total_before=str(order.quantity),actual_filled_before=str(order.filled_qty),limit_price=str(limit),book_candidates=[None if b is None else str(b)for b in self.book],marketable=bool(self.book and all(b is not None and b>=limit for b in self.book)),trigger_native_event_id=None if trigger_event is None else str(trigger_event.id),trigger_is_auto=bool(trigger_event is not None and any(a['event_id']==str(trigger_event.id)for a in self.auto_updates)),fresh_quote=None if q is None else dict(q),fresh_depth_before=str(D(0)if q is None or not q['stream_active']else max(D(0),D(q['bid_size'])-self.quote_sell_filled)),actor_updates=[],nested_fills=[])
        self.commands.append(context);self.command_stack.append(context)
        self.correcting.add(oid);self.depth+=1;self.max_depth=max(self.max_depth,self.depth)
        try:
            context['start_sequence']=self.record('MODIFY_COMMAND',command_id=context['command_id'],order_id=oid,requested_total=str(wanted))['sequence']
            self.modify_order(order,quantity=BTC_PERP.make_qty(wanted),price=order.price)
        finally:
            context['return_sequence']=self.record('MODIFY_RETURN',command_id=context['command_id'],order_id=oid)['sequence']
            self.depth-=1;self.correcting.remove(oid);assert self.command_stack.pop()is context
            self.boundary('MODIFY_RETURN_'+oid)
    def on_quote_tick(self,tick):
        self.boundary('PRE_STRATEGY_QUOTE_'+str(tick.instrument_id))
        if tick.instrument_id==BTC_PERP.id and self.debt_cap is not None:
            debt=max(D(0),self.held()-self.debt_cap)
            if debt and not any(self.kinds.get(str(o.client_order_id))=='DEBT' for o in self.cache.orders_open()+self.cache.orders_inflight()):
                self.market(BTC_PERP,OrderSide.SELL,debt,'DEBT',True)
    def on_position_event(self,event):self.record(type(event).__name__,native_id=str(event.position_id))
    def route(self,event,route):
        eid=str(event.id);self.event_routes.setdefault(eid,[]).append(route)
        self.record('CALLBACK_ENTRY',route=route,native_event_id=eid,native_event_type=type(event).__name__,order_id=str(event.client_order_id))
    def on_order_event(self,event):
        self.route(event,'generic')
        if type(event).__name__=='OrderAccepted':self.native_acknowledged_ids.add(str(event.client_order_id))
        self.boundary('GENERIC_RETURN_'+type(event).__name__,pre_apply_pending=type(event).__name__=='OrderPendingUpdate' and str(event.client_order_id)in self.correcting)
    def on_order_updated(self,event):
        self.route(event,'typed_updated')
        row=self.record('TYPED_OrderUpdated',order_id=str(event.client_order_id),native_event_id=str(event.id),event_quantity=str(event.quantity))
        order=self.cache.order(event.client_order_id);oid=str(event.client_order_id)
        for context in self.command_stack:
            if context['order_id']==oid and event.quantity.as_decimal()==D(context['requested_total']):context['actor_updates'].append(dict(event_id=str(event.id),sequence=row['sequence'],quantity=str(event.quantity)))
        if order is not None:
            if oid not in self.correcting and any(str(x)==oid for x in self.targets.values()):self.auto_updates.append(dict(event_id=str(event.id),order_id=oid,quantity=str(event.quantity),ts_ns=event.ts_event,sequence=row['sequence']))
            self.correct(order,event)
        self.boundary('TYPED_UPDATED_RETURN_'+oid)
    def on_order_modify_rejected(self,event):
        self.route(event,'typed_modify_rejected');self.rejections.append(dict(order_id=str(event.client_order_id),reason=event.reason,ts_ns=event.ts_event));self.record('TYPED_OrderModifyRejected',order_id=str(event.client_order_id),reason=event.reason);self.boundary('MODIFY_REJECT_RETURN')
    def on_order_filled(self,event):
        self.route(event,'typed_filled');reallocated=False
        oid=str(event.client_order_id);kind=self.kinds.get(oid);qty=event.last_qty.as_decimal();trade=str(event.trade_id)
        self.fills.append(dict(order_id=oid,trade_id=trade,kind=kind,instrument=str(event.instrument_id),qty=str(qty),price=str(event.last_px),ts_ns=event.ts_event,commission=str(event.commission)))
        assert trade not in self.native_trade_ids,'DUPLICATE_NATIVE_TRADE_ID';self.native_trade_ids.add(trade)
        actual_order=self.cache.order(event.client_order_id)
        if event.instrument_id==BTC_PERP.id and event.order_side==OrderSide.SELL:
            depth_before=D(0)if self.quote_context is None or not self.quote_context['stream_active']else max(D(0),D(self.quote_context['bid_size'])-self.quote_sell_filled)
            if actual_order.order_type.name=='LIMIT'and None not in self.book:
                compatible=tuple(dict.fromkeys(b for b in self.book if b>=actual_order.price.as_decimal()))
                assert compatible,'NATIVE_LIMIT_FILL_CONTRADICTS_BOOK_ENVELOPE'
                if compatible!=self.book:
                    self.book_refinements.append(dict(native_trade_id=trade,order_id=oid,limit_price=str(actual_order.price),prior_candidates=[str(b)for b in self.book],compatible_candidates=[str(b)for b in compatible],reason='REAL_SELL_LIMIT_FILL_RULES_OUT_NONMARKETABLE_PRIOR_BID'))
                    self.book=compatible
            self.quote_sell_filled+=qty
        else:depth_before=D(0)
        if kind and kind.startswith('TP'):
            level=int(kind[2:]);allowance=self.expected.get(level,D(0))
            self.pre_fill_checks.append(dict(native_trade_id=str(event.trade_id),level=level,quantity=str(qty),pre_fill_frozen_entitlement=str(allowance),within_entitlement=qty<=allowance))
            assert qty>0 and qty<=allowance,'ACTUAL_TP_OVERFILL_PRE_FILL_ENTITLEMENT'
            for context in self.command_stack:
                if context['order_id']==oid:
                    context['nested_fills'].append(dict(native_trade_id=trade,order_id=oid,quantity=str(qty),sequence=len(self.events),pre_fill_entitlement=str(allowance),fresh_depth_before_fill=str(depth_before),native_event_ns=event.ts_event))
            self.oracle_domain.on_fill(self.oracle_intents[oid],float(qty),float(event.last_px.as_decimal()),datetime.fromtimestamp(event.ts_event/1e9,timezone.utc))
            self.expected[level]-=qty
            order=self.cache.order(event.client_order_id)
            if level in self.oracle_domain.episode.btc_filled_tps or order.status.name=='FILLED':
                self.consumed.add(level);self.expected={k:D(v)*STEP for k,v in target_lots(int(self.held()/STEP),self.consumed).items()};self.sync_oracle_allocation();reallocated=True
        if kind=='DEBT':
            self.expected={k:D(v)*STEP for k,v in target_lots(int(self.held()/STEP),self.consumed).items()};self.sync_oracle_allocation();reallocated=True
        if reallocated:
            for level,target_id in self.targets.items():
                target=self.cache.order(target_id)
                if level in self.expected and self.expected[level]>0 and level not in self.consumed and target is not None and not target.is_closed:self.correct(target)
        if kind=='SOL_RELIEF':self.debt_cap=D('.750')
        self.record('TYPED_OrderFilled',order_id=oid,kind_owned=kind,trade_id=str(event.trade_id))
        self.boundary('TYPED_FILLED_RETURN_'+oid)
    def on_order_canceled(self,event):self.record('TYPED_OrderCanceled',order_id=str(event.client_order_id))
    def on_order_denied(self,event):self.record('TYPED_OrderDenied',order_id=str(event.client_order_id),reason=event.reason)
    def on_order_rejected(self,event):self.record('TYPED_OrderRejected',order_id=str(event.client_order_id),reason=event.reason)

def lifecycle(engine):
    return {name:dict(state=getattr(engine.kernel,name).state.name,running=bool(getattr(engine.kernel,name).is_running),disposed=bool(getattr(engine.kernel,name).is_disposed)) for name in ('trader','data_engine','risk_engine','exec_engine','emulator')}

def run_fixture(engine,s,snapshot):
    def advance(ns,btc='100',sol='100',btcsize='1000',solsize='1000'):
        assert 1<=ns<=END
        s.quote_context=dict(ts_ns=ns,bid=btc,ask=btc,bid_size=btcsize,ask_size=btcsize,stream_active=True);s.quote_sell_filled=D(0)
        s.book=(s.settled_book,D(btc));s.book_trace.append(dict(ts_ns=ns,prior_settled_bid=None if s.settled_book is None else str(s.settled_book),incoming_bid=btc,candidate_bids=[None if b is None else str(b)for b in s.book],btc_depth=btcsize,source='PRIOR_OR_INCOMING_NATIVE_MATCHING_BOOK_ENVELOPE',order='time-handlers/marks may use settledprior; exchange BTCquote_match before DataEngine/strategyquote; SOLquote afterBTC'));s.record('BEFORE_NATIVE_STREAM',incoming_btc_quote=btc)
        engine.add_data([venue_mark(BTC_PERP.id,D(btc),ns),venue_mark(SOL_PERP.id,D(sol),ns)],client_id=ClientId('BYBIT_MARK'),sort=False)
        engine.add_data([tick(BTC_PERP,ns,btc,btcsize),tick(SOL_PERP,ns,sol,solsize)],sort=True)
        engine.run(streaming=True);engine.clear_data();s.quote_context['stream_active']=False;s.settled_book=D(btc);s.book=(s.settled_book,);s.record('STREAM_COMPLETED_SETTLED_BOOK',settled_bid=btc);s.boundary('AFTER_NATIVE_STREAM_'+str(ns));snapshot('AT_'+str(ns))
    advance(1)
    prepare_completed_day(s,2)
    assert s._current_btc.ts_event-86400_000_000_000>=s.config.trading_start_open_ns
    assert all(int(b.available_at.timestamp()*1e9)<=s._current_btc.ts_event for b in s._bars)
    s.stage='ACTUAL_ENTRY';s.market(BTC_PERP,OrderSide.BUY,'1.000','ENTRY_BTC');s.market(SOL_PERP,OrderSide.SELL,'10.0','ENTRY_SOL')
    advance(3);advance(4)
    assert s.held()==D('1') and s.held(SOL_PERP)==D('-10')
    s.stage='TARGET_INSTALL';s.install_targets();advance(5)
    assert all(s.cache.order(oid).status.name=='ACCEPTED' for oid in s.targets.values())
    position=next(p for p in engine.cache.positions_open()if p.instrument_id==BTC_PERP.id)
    assert all(engine.cache.position_id(oid)==position.id for oid in s.targets.values())
    assert set(s.targets.values())<=set(o.client_order_id for o in engine.cache.orders_for_position(position.id))
    s.tp_active=True;s.boundary('ALL_THREE_ACCEPTED');snapshot('ALL_THREE_ACCEPTED')
    # Genuine native SOL reduction is the causal relief. Protection survives
    # the interval before the NEXT executable BTC quote and residual debt IOC.
    s.stage='SOL_RELIEF';s.market(SOL_PERP,OrderSide.BUY,'2.5','SOL_RELIEF',True)
    s.record('PROTECTION_WHILE_RELIEF_PENDING');snapshot('PROTECTION_WHILE_RELIEF_PENDING')
    advance(6);assert s.debt_cap==D('.750')
    s.stage='DEBT_NEXT_QUOTE';advance(M+6);advance(M+7)
    assert s.held()==D('.750') and any(f['kind']=='DEBT' for f in s.fills)
    assert {k:s.cache.order(oid).leaves_qty.as_decimal() for k,oid in s.targets.items()}==s.expected
    assert all(s.cache.order(oid).price.as_decimal()==PRICES[k] for k,oid in s.targets.items())
    # Native deliberate modify rejection: unchanged limit price, invalid total
    # below actual filled quantity is only attempted AFTER a real partial fill.
    s.stage='PARTIAL_TP';advance(2*M+7,btc='101',btcsize='.050')
    tp0=s.cache.order(s.targets[0]);assert D(0)<tp0.filled_qty.as_decimal()<tp0.quantity.as_decimal()
    s.stage='REAL_MODIFY_REJECT';before=tp0.quantity.as_decimal();s.modify_order(tp0,quantity=BTC_PERP.make_qty(D('.001')),price=tp0.price)
    advance(2*M+8,btc='100')
    assert s.rejections and tp0.quantity.as_decimal()==before
    s.boundary('AFTER_ACTUAL_MODIFY_REJECTION');snapshot('AFTER_ACTUAL_MODIFY_REJECTION')
    # Flush remaining original levels through actual native matching. Increasing
    # displayed sizes makes each stock shared-liquidity fill independently real.
    s.stage='NATIVE_TP_TERMINAL';advance(3*M+8,btc='104',btcsize='1');advance(3*M+9,btc='104',btcsize='2')
    assert s.held()==0
    s.tp_active=False;s.debt_cap=None
    s.stage='SOL_TERMINAL';sol=-s.held(SOL_PERP)
    if sol:s.market(SOL_PERP,OrderSide.BUY,sol,'SOL_TERMINAL',True)
    advance(4*M+10,btc='100');advance(4*M+11,btc='100')
    assert not engine.cache.positions_open() and not engine.cache.orders_open() and not engine.cache.orders_inflight()
    assert all(s.guard_calls) and len(s.guard_calls)==2 and all(x['allowed']for x in s.guard_calls)
    assert not s.native_coverage_gaps,'ACTUAL_REQUIRED_TARGET_GAP'
    assert not s.boundary_violations,'PLANNED_ALLOCATION_DRIFT_AT_EXECUTABLE_BOUNDARY'
    assert not s.same_oid_overlap,'SAME_OID_NONCONVERGENT_OR_UNPROVEN_UPDATE'
    assert all(n<=8 for n in s.modify_count.values()),'UNBOUNDED_UPDATE_COUNT'
    assert {int(f['kind'][2:])for f in s.fills if f['kind']and f['kind'].startswith('TP')}=={0,1,2},'ACTUAL_THREE_TP_LEVEL_FILLS_REQUIRED'
    assert s.auto_updates,'NATIVE_AUTO_UPDATE_NOT_EXERCISED_FEASIBILITY_NOT_PROVEN'
    witnesses=[]
    for command in s.commands:
        if not command['trigger_is_auto']or not command['marketable']or not command['fresh_quote']or not command['fresh_quote']['stream_active']:continue
        if D(command['requested_total'])==D(command['actual_total_before'])or D(command['requested_total'])<D(command['actual_filled_before']):continue
        for fill in command['nested_fills']:
            updates=[u for u in command['actor_updates']if u['sequence']<fill['sequence']]
            if updates and command['start_sequence']<fill['sequence']<command['return_sequence']and D(fill['quantity'])>0 and D(fill['quantity'])<=D(fill['pre_fill_entitlement'])and D(fill['quantity'])<=D(fill['fresh_depth_before_fill']):
                witnesses.append(dict(command_id=command['command_id'],order_id=command['order_id'],native_trade_id=fill['native_trade_id'],actor_updated_event_id=updates[-1]['event_id'],updated_sequence=updates[-1]['sequence'],fill_sequence=fill['sequence'],modify_return_sequence=command['return_sequence'],marketable_limit=command['limit_price'],fresh_depth_before_fill=fill['fresh_depth_before_fill'],actual_fill_quantity=fill['quantity']))
    assert witnesses,'NO_ACTUAL_MARKETABLE_SAME_OID_FILL_AFTER_UPDATED_BEFORE_PUBLIC_MODIFY_RETURN'
    update_routes=[v for v in s.event_routes.values() if 'typed_updated'in v]
    reject_routes=[v for v in s.event_routes.values() if 'typed_modify_rejected'in v]
    assert update_routes and reject_routes
    assert all(v.count('typed_updated')==1 and v.count('generic')==1 for v in update_routes),'UPDATED_TYPED_GENERIC_SAME_ID_REQUIRED'
    assert all(v.count('typed_modify_rejected')==1 and v.count('generic')==1 for v in reject_routes),'REJECT_TYPED_GENERIC_SAME_ID_REQUIRED'
    assert all(x['within_entitlement']for x in s.pre_fill_checks)
    assert len({f['trade_id']for f in s.fills})==len(s.fills)
    assert all(sum(D(f['qty']) for f in s.fills if f['kind']=='DEBT')<=D('.250') for _ in (0,))
    return dict(status='PASS_REQUIRES_INDEPENDENT_NATIVE_WINDOW_ADMISSION',marketable_nested_fill_witnesses=witnesses,native_coverage_gaps=0,boundary_allocation_violations=0,transient_auto_resize_events=len(s.transient_allocation_drift),max_correction_call_depth=s.max_depth,stock_margin_calls=s.guard_calls,real_modify_rejections=s.rejections,actual_native_TP_fill_levels=sorted({int(f['kind'][2:])for f in s.fills if f['kind']and f['kind'].startswith('TP')}),limitation='API feasibility only; same-stack auto-resize mutations retained and require independent admission review, not silently treated as valid per-level allocation')

def launch(gate_path,ledger_path):
    gate,ledger=verify(gate_path,ledger_path,True);namespace=Path(gate['namespace']);namespace.mkdir(parents=True)
    attempt=str(uuid.uuid4());number=ledger['physical_started']+1;entry=dict(attempt_id=attempt,physical_index=number,fixture_id=CASE,status='STARTED',started_utc=now(),source_commit=gate['source_commit'],gate_sha256=digest(gate_path),namespace=str(namespace),window_ns=[1,END])
    ledger['attempts'].append(entry);ledger.update(physical_started=number,active=1,authorized_remaining=4-number,status='RUNNING');write(ledger_path,ledger)
    engine=s=None;rc=1;result=None;errors=[]
    def snapshot(stage,**facts):
        if engine is None:return
        payload=dict(stage=stage,attempt_id=attempt,physical_index=number,**facts,lifecycle=lifecycle(engine),events=[]if s is None else s.events,orders=[]if s is None else s.order_rows(),native_position_index=[]if s is None else s.native_position_index(),stock_margin_calls=[]if s is None else s.guard_calls,fills=[]if s is None else s.fills,transient_allocation_drift=[]if s is None else s.transient_allocation_drift,book_trace=[]if s is None else s.book_trace,nonexecutable_transients=[]if s is None else s.nonexecutable_transients,auto_updates=[]if s is None else s.auto_updates,pre_fill_checks=[]if s is None else s.pre_fill_checks,commands=[]if s is None else s.commands,book_refinements=[]if s is None else s.book_refinements,event_routes={}if s is None else s.event_routes,boundary_violations=[]if s is None else s.boundary_violations,native_coverage_gaps=[]if s is None else s.native_coverage_gaps)
        write(namespace/(stage+'.json'),payload)
    try:
        # The ONLY physical native constructor in this file; durable claim above.
        engine=BacktestEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR')))
        selected=((BTC_PERP.id,D(40)),(SOL_PERP.id,D(20)))
        module=BybitTierMarginModule(tuple(MarkPriceUpdate(inst.id,D(100),1)for inst in(BTC_PERP,SOL_PERP)),selected,2*M)
        engine.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,default_leverage=D(1),liquidity_consumption=True,bar_execution=False,modules=[module])
        for inst in (BTC_PERP,SOL_PERP):engine.add_instrument(perpetual(inst.raw_symbol.value,inst.base_currency,str(inst.price_increment),str(inst.size_increment),str(inst.margin_init),maker_fee=D('.00020'),taker_fee=D('.00055')))
        s=FeasibilityProbe(config());engine.add_strategy(s)
        result=run_fixture(engine,s,snapshot);snapshot('BEFORE_TERMINAL');rc=0
    except BaseException as error:
        errors.append(dict(stage='FIXTURE',type=type(error).__name__,error=str(error),traceback=traceback.format_exc()));snapshot('FAILURE_BEFORE_END')
    finally:
        if engine is not None:
            snapshot('BEFORE_END')
            started=any(x['running']for x in lifecycle(engine).values())
            if started:
                try:engine.end()
                except BaseException as error:errors.append(dict(stage='END',error=repr(error)));rc=1
                snapshot('AFTER_END',end_applicable=True)
                if not all(x['state']=='STOPPED'and not x['running']for x in lifecycle(engine).values()):rc=1;errors.append(dict(stage='END',error='ACTUAL_FIVE_NATIVE_COMPONENTS_NOT_STOPPED'))
            else:
                snapshot('END_NOT_APPLICABLE',end_applicable=False,reason='NO_NATIVE_COMPONENT_RUNNING_READY_PREINIT_IS_NOT_STOPPED')
                if rc==0:rc=1;errors.append(dict(stage='END',error='F1_PASS_REQUIRES_ACTUAL_STARTED_THEN_FIVE_STOPPED'))
            snapshot('BEFORE_DISPOSE')
            try:engine.dispose()
            except BaseException as error:errors.append(dict(stage='DISPOSE',error=repr(error)));rc=1
            write(namespace/'AFTER_DISPOSE.json',dict(lifecycle=lifecycle(engine)))
            if not all(x['disposed']for x in lifecycle(engine).values()):rc=1;errors.append(dict(stage='DISPOSE',error='NATIVE_COMPONENT_NOT_DISPOSED'))
        write(namespace/'result.json',dict(actual_process_exit_code=rc,result=result,errors=errors,fixture=CASE,attempt_id=attempt))
        ledger=json.loads(Path(ledger_path).read_text());row=next(a for a in ledger['attempts']if a['physical_index']==number);row.update(status='COMPLETED'if rc==0 else'FAILED',finished_utc=now(),actual_process_exit_code=rc,result_path=str(namespace/'result.json'),result_sha256=digest(namespace/'result.json'));ledger.update(active=0,authorized_remaining=4-ledger['physical_started'],status='F1_STRESS_COMPLETE_ROOT_REVIEW_REQUIRED'if rc==0 else'STOP_FIRST_FAILURE');write(ledger_path,ledger)
    return rc

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--pure-proof');parser.add_argument('--gate');parser.add_argument('--ledger');parser.add_argument('--prepare',action='store_true');parser.add_argument('--launch',action='store_true');args=parser.parse_args()
    if args.pure_proof:write(args.pure_proof,pure_preconditions());return 0
    if args.prepare:
        gate,ledger=verify(args.gate,args.ledger);print(json.dumps(dict(status='PREPARED_NO_ENGINE',physical_started=ledger['physical_started'],root_go=gate['root_go'],proof=pure_preconditions())));return 0
    if args.launch:return launch(args.gate,args.ledger)
    parser.error('Choose --pure-proof, --prepare or --launch')
if __name__=='__main__':raise SystemExit(main())
