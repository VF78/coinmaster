"""Live reservation guard on actual native Cache/Orders/Position + SQLite; no engines."""
import ast,json,time
from decimal import Decimal as D
from types import SimpleNamespace as N
import pytest
from coinmaster.strategy import live_recovery as REAL
from coinmaster.ops.hl_live_epoch import LiveEpochRuntime
from coinmaster.research.native_fixture import instrument_quote
from nautilus_trader.cache.cache import Cache
from nautilus_trader.model.enums import OrderSide
from test_sol_staging_all_paths_pure import forced
from test_e4_c1_manage_only_pure import code,config

@pytest.fixture
def live(tmp_path,monkeypatch):
    c=forced('REGIME',4000,start=False);s=c.s;Base=type(s)
    cache=Cache();cache.add_instrument(c.btc);cache.add_instrument(c.sol)
    cache.add_position(c.position,oms_type=__import__('nautilus_trader.model.enums',fromlist=['OmsType']).OmsType.HEDGING)
    cache.add_quote_tick(c.latest[c.sol.id]);s.cache=cache
    now=[100];monkeypatch.setattr(time,'time_ns',lambda:now[0])
    s.config.max_mark_age_ns=120;s._domain=N(episode=N(id='episode'));s._quote_ns={c.sol.id:100,c.btc.id:100}
    s._latest_marks={i:N(ts_event=100) for i in (c.sol.id,c.btc.id)}
    s.recovery_confirmed=True;s._active_c1_authorized=True;s._staging_a_forced_parent=None
    s._owned_reduce_allowed=lambda o:True
    s.refreshes=[];s._request_live_refresh=lambda:s.refreshes.append(now[0])
    r=LiveEpochRuntime(tmp_path/'live.sqlite','owner',10**20);r.acquire();s._recovery_runtime=r
    s.on_save=lambda:{REAL._KEY:json.dumps(s._staging_a_forced_parent).encode()}
    s._persist_transient_checkpoint=lambda:r.persist_strategy_checkpoint(s.on_save()[REAL._KEY],r.native_revision())
    def record(self,order,intent,episode,action,*rest):
        self._order_audit[str(order.client_order_id)]={}
        return r.record_submission(client_order_id=str(order.client_order_id),intent_id=intent,episode_id=episode,
            action=action,instrument_id=str(order.instrument_id),quantity=str(order.quantity),reduce_only=True,
            strategy_state=self.on_save()[REAL._KEY])
    Base._record_submission=record;s.__dict__.pop('_record_submission')
    cls=next(n for n in ast.parse(REAL.Path(REAL.__file__).read_text()).body if isinstance(n,ast.ClassDef) and n.name=='RecoverableWaveOverlayStrategy')
    names={'_record_submission','_staging_a_live_forced_allowed','_feeds_fresh','on_position_event',
        'on_order_filled','_after_domain_fill','_terminal_submission','_staging_a_forced_child_ready'}
    node=ast.ClassDef(name='Live',bases=[ast.Name(id='Base',ctx=ast.Load())],keywords=[],body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names],decorator_list=[])
    env=dict(Base=Base,WaveOverlayStrategy=Base,Decimal=D,time=time,OrderSide=OrderSide,_KEY=REAL._KEY)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'live_guard','exec'),env)
    s.__class__=env['Live'];s.__dict__.pop('_terminal_submission')
    s._input_readiness_preparation=False
    def submit(order):
        cache.add_order(order);c.orders[str(order.client_order_id)]=order;c.sent.append(order)
        from nautilus_trader.test_kit.stubs.events import TestEventStubs
        order.apply(TestEventStubs.order_accepted(order,ts_event=100))
    s.submit_order=submit
    def record_fill(e):
        r.record_native_fill(trade_id=str(e.trade_id),native_event_id=str(e.id),client_order_id=str(e.client_order_id),
            venue_order_id=str(e.venue_order_id),instrument_id=str(e.instrument_id),order_side=str(e.order_side),
            quantity=str(e.last_qty),price=str(e.last_px),commission_amount=str(e.commission.as_decimal()),
            commission_currency=str(e.commission.currency),liquidity_side=str(e.liquidity_side),ts_event_ns=e.ts_event,ts_init_ns=e.ts_init)
    s._record_native_fill=record_fill
    c.now=now;c.runtime=r
    yield c
    r.close()

def complete(c):
    o=c.sent[-1];e=c.fill(o);o.apply(e);c.position.apply(e);c.s.cache.update_position(c.position);c.s.cache.update_order(o);c.s.on_order_filled(e);c.s.on_position_event(c.event())

@pytest.mark.parametrize('stale',[False,True])
def test_positive_fill_fresh_same_quote_allowed_stale_quote_held(live,stale):
    c=live;s=c.s;s._submit_forced_close_on_quote(c.latest[c.sol.id]);assert len(c.sent)==1
    # The parent is still in time; stale BTC input alone must hold a SOL continuation.
    c.now[0]=101
    if stale:s._quote_ns[c.btc.id]=-20
    complete(c)
    assert len(c.sent)==(1 if stale else 2)
    assert len(c.runtime.applied_fill_ids())==1
    assert s._staging_a_forced_parent['decision_ns']==100

@pytest.mark.parametrize('size',['0','1'])
def test_executable_side_depth_and_deadline_tombstone(live,size):
    c=live;s=c.s
    from nautilus_trader.model.data import QuoteTick
    q=c.latest[c.sol.id]
    q=QuoteTick(q.instrument_id,q.bid_price,q.ask_price,c.sol.make_qty(size),q.ask_size,100,100)
    s.cache.add_quote_tick(q);s._submit_forced_close_on_quote(q)
    assert len(c.sent)==(0 if size=='0' else 1)
    original=dict(s._staging_a_forced_parent)
    c.now[0]=220;s._forced_close_reason='TRAIL';s._forced_close_decision_ns=219
    q=instrument_quote(c.sol,'101','101',220);s.cache.add_quote_tick(q)
    # Direct final reservation retries also cannot reset the bound.
    order=s.order_factory.market(c.sol.id,OrderSide.SELL,c.sol.make_qty(1000),reduce_only=True)
    assert not s._record_submission(order,'retry','forced','FORCED_CLOSE')
    assert s._staging_a_forced_parent=={**original,'expired':True}
    assert not s.recovery_confirmed and s.refreshes
    persisted=json.loads(c.runtime.strategy_checkpoint()[0]);assert persisted['expired']
    s._staging_a_forced_parent=json.loads(json.dumps(persisted));s.recovery_confirmed=True;c.now[0]=221
    assert not s._record_submission(order,'retry','forced','FORCED_CLOSE')
    assert s._staging_a_forced_parent['deadline_ns']==220 and not s.recovery_confirmed

@pytest.mark.parametrize('reason,action,instrument',[('SOL_HARD_TIMEOUT','SOL_EXIT','sol'),('REGIME','C1_CUT','sol'),('LIQUIDATION','LIQUIDATION_CLOSE','sol'),('RESEARCH_PORTFOLIO_45','FORCED_CLOSE','sol'),('REGIME','FORCED_CLOSE','btc')])
def test_unrelated_reductions_unchanged(live,reason,action,instrument):
    c=live;s=c.s;s._forced_close_reason=reason;c.now[0]=10000
    native=c.sol if instrument=='sol' else c.btc
    order=s.order_factory.market(native.id,OrderSide.SELL,native.make_qty(1),reduce_only=True)
    assert s._record_submission(order,'other','forced',action)
    assert s._staging_a_forced_parent is None

def snapshot(code):
    cfg=config();cfg.research_sol_capital_staging_a=True;cfg.active_seed=D(10000)
    s=code.Strategy(cfg);s._staging_a_initial_seed=cfg.active_seed;s._staging_a_forced_children={}
    s._forced_close_reason='REGIME';s._forced_close_decision_ns=100
    s._staging_a_forced_parent=dict(episode_id='episode',position_id='native-sol',decision_ns=100,
        deadline_ns=100+cfg.max_mark_age_ns,reason='REGIME',expired=True)
    return s,cfg

def test_real_checkpoint_load_preserves_tombstone_and_never_authorizes(code):
    s,cfg=snapshot(code);body=s.on_save();restored=code.Strategy(cfg);restored.on_load(body)
    assert restored._staging_a_forced_parent==s._staging_a_forced_parent
    assert not restored.recovery_confirmed and not restored._quote_ns

@pytest.mark.parametrize('field,value',[('deadline_ns',999),('decision_ns',101),('episode_id','other'),('expired',1),('reason','TIMEOUT')])
def test_checkpoint_corruption_or_rebase_denied(code,field,value):
    s,cfg=snapshot(code);s._staging_a_forced_parent[field]=value
    with pytest.raises(ValueError,match='STAGING_A_FORCED_PARENT_INVALID'):code.Strategy(cfg).on_load(s.on_save())

def test_legacy_missing_parent_only_allowed_without_active_forced_close(code):
    s,cfg=snapshot(code)
    for active in (False,True):
        s._forced_close_reason='REGIME' if active else None
        doc=json.loads(s.on_save()[REAL._KEY]);doc['state'].pop('_staging_a_forced_parent')
        state={REAL._KEY:json.dumps(doc).encode()};restored=code.Strategy(cfg)
        if active:
            with pytest.raises(ValueError,match='STAGING_A_FORCED_PARENT_MISSING'):restored.on_load(state)
        else:
            restored.on_load(state);assert restored._staging_a_forced_parent is None

def test_native_full_flat_clears_parent_only_after_position_receipt(live):
    c=live;s=c.s;s._submit_forced_close_on_quote(c.latest[c.sol.id])
    for index in range(4):
        assert len(c.sent)==index+1
        order=c.sent[-1];event=c.fill(order);order.apply(event);c.position.apply(event);s.cache.update_position(c.position);s.cache.update_order(order)
        s.on_order_filled(event)
        assert s._staging_a_forced_parent is not None
        s.on_position_event(c.event())
    assert c.position.is_closed and s._staging_a_forced_parent is None
    assert json.loads(c.runtime.strategy_checkpoint()[0]) is None
    s.on_position_event(c.event());s.on_order_filled(event)
    assert len(c.sent)==4 and s._staging_a_forced_parent is None

def test_unowned_reduce_cannot_bind_or_expire_parent(live):
    c=live;s=c.s;s._owned_reduce_allowed=lambda o:False;c.now[0]=10000
    s._submit_forced_close_on_quote(c.latest[c.sol.id])
    assert not c.sent and s._staging_a_forced_parent is None and s.recovery_confirmed
    assert not s.refreshes and c.runtime.strategy_checkpoint() is None
