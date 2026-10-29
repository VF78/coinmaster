"""Actual split quote/DP/source publication/sink/forward; no native or HTTP calls."""
import asyncio
import time
from dataclasses import replace
from decimal import Decimal as D
from types import SimpleNamespace as N
import sys
import pytest
from coinmaster.ops.hl_info_receipt import IncompleteInfoReport
from coinmaster.ops.hl_unified_account import EQUITY_BASIS
from test_e4_c1_manage_only_pure import code,nodes,run_ast,Q,ACCOUNT,ACCOUNT_ID
from test_e4_c1_prepared_dispatch_pure import prepared,source_method
from test_e4_c1_unified_pure import money_source,native_source,spot,state


def parking(prepared,code):
    c=prepared;s=c.s;r=c.r;m=money_source()
    # Real base gate must reach real DP; no always-True admission substitute.
    run_ast([source_method('WaveOverlayStrategy','_entries_enabled')],code.env)
    code.env['WaveOverlayStrategy']._entries_enabled=code.env['_entries_enabled']
    del s.__dict__['_entries_enabled'];del s.__dict__['_current_owned_money'];del s.__dict__['_validated_live_money']
    code.env['LivePerpsMoneyView']=m.LivePerpsMoneyView
    sys.modules['coinmaster.ops.hl_live_money'].CheapPortfolioObservation=m.CheapPortfolioObservation
    s.config.live_equity_basis=EQUITY_BASIS;s.config.entries_enabled=True;s.config.entries_gate=None
    s._capital_basis_verified=True;s.terminal_lifecycle={}
    s.establish_owned_effect_chain(account_id=ACCOUNT_ID,ws_epoch=4,
        policy_sha256=code.env['recovery_policy_hash'](s.config,s._candidate))
    full=m.LivePerpsMoneyView(ACCOUNT,'',time.time_ns()//1_000_000,D(100),D(100),D(0),D(100),(),(),r.native_revision(),'unifiedAccount',EQUITY_BASIS)
    latest=[full];s._live_money_provider=lambda:latest[0]
    generation_started=time.monotonic_ns();s.accept_live_financial_authority(started_ns=generation_started)
    deadline=s._live_financial_deadline_ns
    # Source producer creates an old revision observation, like A14 rev15 vs19.
    type(c.account.balance_total('USDC')).currency='USDC'
    c.account.margin_init_for_currency=lambda currency:N(currency='USDC',as_decimal=lambda:D(0))
    c.account.margin_maint_for_currency=lambda currency:N(currency='USDC',as_decimal=lambda:D(0))
    old=m.cheap_unified_observation(spot(),[['',state()]],account_id=ACCOUNT_ID,native_account=c.account,
        native_positions=(),strategy_id=s.id,revision=r.native_revision()-1,fill_epoch=s._c1_fill_epoch,ws_epoch=4,
        started_ns=time.monotonic_ns(),completed_ns=time.monotonic_ns(),available_ns=time.time_ns())
    s._last_live_input_observation=old
    refresh=[]
    def request():
        refresh.append(True);latest[0]=None;s.suspend_live_financial_authority()
    s._live_refresh=request
    s._split_parent=dict(intent=c.intent,episode_id='episode',side=1,quantity=D(20),first_quantity=D(20),
        filled=D(0),closed=False,start_ns=time.time_ns(),deadline_ns=time.time_ns()+3_600_000_000_000,fallback=True,
        sigma=None,decision_index=0)
    # Actual existing split-check calls the recoverable dispatcher on each quote.
    env=dict(D=D,DAY=86_400_000_000_000)
    split=next(n for n in nodes('strategy/split_cover.py',{'SplitCoverResearch'}))
    methods=[n for n in split.body if getattr(n,'name',None) in ('_split_check','_split_stop')]
    run_ast(methods,env)
    for name in ('_split_check','_split_stop'):setattr(s,name,env[name].__get__(s,type(s)))
    s._split_unfinished=lambda:True
    class Price(Q):
        def __float__(self):return float(self.value)
    def quote():
        return s._split_check(N(instrument_id=s.config.btc_id,ts_event=time.time_ns(),bid_price=Price('100'),ask_price=Price('100')))
    # Actual unified portfolio collector and real source producer. Transport
    # callbacks return local synthetic public-shaped rows; nothing is sent.
    native=native_source();client=object.__new__(native.QualifiedHyperliquidExecutionClient)
    native.QualifiedHyperliquidExecutionClient._cm_collect_portfolio_observation.__globals__['cheap_unified_observation']=m.cheap_unified_observation
    client._cm_money_lock=asyncio.Lock();client._cm_runtime=r;client._cm_ws_epoch=4;client._cache=s.cache
    client._cm_unified=True;client._cm_scope=N(account_ref=ACCOUNT,dex='');client.account_id=ACCOUNT_ID
    client.venue=s.config.btc_id.venue;client._clock=N(timestamp_ns=time.time_ns)
    client.recovery_healthy=lambda:True;client._cm_account_refresh_wait=None
    client._cm_unified_discovery_current=lambda:True;client._cm_unified_discovery=dict(dex_names=('',))
    client._cm_inputs_budget=native.ReadinessInfoBudget();client._cm_require_healthy=lambda:None
    client.request_unified_directory_refresh=lambda:False
    s.cache.orders_open=lambda venue=None:[]
    async def local_state(body):return state()
    client._cm_qualified_info=local_state
    async def account_event():
        # Native-shaped AccountState publication from the public account path.
        c.account.last_event=N(id='new-cheap-account',ts_init=time.time_ns())
        client._cm_unified_mode_proof=dict(ws_epoch=4,started_ns=time.monotonic_ns(),native_spot_money=(D(100),D(0),D(100)))
    client._update_account_state=account_event
    async def publish():await client._cm_collect_portfolio_observation(s)
    return N(c=c,s=s,r=r,full=full,latest=latest,original_deadline=deadline,generation_started=generation_started,
        old=old,refresh=refresh,quote=quote,publish=publish,client=client)


def test_DP_pending_quote_preserves_original_full_then_actual_publication_allows_next_quote(prepared,code):
    p=parking(prepared,code);s=p.s
    s._live_inputs_dirty=True # Cheap lane dirtiness is not full-money invalidity.
    p.quote()
    assert p.refresh==[] and p.c.sent==[] and p.c.created==[]
    assert p.latest[0] is p.full and s._live_financial_deadline_ns==p.original_deadline
    assert not s._live_financial_suspended and p.r.native_revision()==p.full.native_revision
    assert not s._entries_enabled() # DP remains strictly denied while pending.
    asyncio.run(p.publish())
    assert s._last_live_input_observation is not None and s._last_live_input_observation is not p.old
    assert s._last_live_input_observation.native_revision==p.r.native_revision()
    assert not s._live_inputs_dirty and s._entries_enabled()
    assert p.latest[0] is p.full and s._live_financial_deadline_ns==p.original_deadline
    p.quote()
    assert len(p.c.sent)==1 and p.refresh==[]
    assert s._prepared_order_dispatch is None and s._prepared_deposit_dispatch is None


@pytest.mark.parametrize('gate',['headroom','feed'])
def test_other_temporary_gate_denial_never_requests_full_refresh(prepared,code,gate):
    p=parking(prepared,code)
    if gate=='headroom':p.s._live_increase_headroom=lambda:False
    else:p.s._feeds_fresh=lambda now:False
    p.quote()
    assert p.c.sent==[] and p.refresh==[] and p.latest[0] is p.full
    assert p.s._live_financial_deadline_ns==p.original_deadline


@pytest.mark.parametrize('fault',['stale','revision','unknown_view','unknown_ACK','foreign','context','missing_context'])
def test_invalid_actual_full_or_context_still_requests_recovery_and_denies(prepared,code,fault):
    p=parking(prepared,code)
    if fault=='stale':p.s._live_financial_deadline_ns=time.monotonic_ns()-1
    elif fault=='revision':p.r._bump_native_revision();p.r.db.commit()
    elif fault=='unknown_view':p.latest[0]=None
    elif fault=='unknown_ACK':
        from test_e4_c1_manage_only_pure import order
        o=order('UNKNOWN',side='BUY',reduce=False);p.s.cache.orders=lambda venue=None:[o]
        p.r.record_submission(client_order_id='UNKNOWN',intent_id='unknown',episode_id='episode',action='BTC_ENTRY',instrument_id=str(p.s.config.btc_id),quantity='1',reduce_only=False)
    elif fault=='foreign':p.s.cache.positions_open=lambda:[N(strategy_id='foreign',instrument_id=p.s.config.btc_id)]
    elif fault=='context':p.s._live_context_current=lambda:False
    elif fault=='missing_context':p.s._live_context_current=None
    p.quote()
    assert p.c.sent==[] and p.refresh==[True] and p.latest[0] is None and p.s._live_financial_suspended


@pytest.mark.parametrize('fault',['expiry_after_publish','ws','pause','pending_ACK'])
def test_next_quote_cannot_reuse_authority_after_other_barrier_moves(prepared,code,fault):
    p=parking(prepared,code);p.quote();assert not p.refresh
    asyncio.run(p.publish());assert p.s._entries_enabled()
    if fault=='expiry_after_publish':p.s._live_financial_deadline_ns=time.monotonic_ns()-1
    elif fault=='ws':p.s._live_input_ws_epoch=lambda:5
    elif fault=='pause':p.r.entry_control_command('pause-new-entries','owner-pause')
    elif fault=='pending_ACK':
        from test_e4_c1_manage_only_pure import order
        o=order('UNKNOWN',side='BUY',reduce=False);p.s.cache.orders=lambda venue=None:[o]
        p.r.record_submission(client_order_id='UNKNOWN',intent_id='unknown',episode_id='episode',action='BTC_ENTRY',instrument_id=str(p.s.config.btc_id),quantity='1',reduce_only=False)
    p.quote()
    assert p.c.sent==[]
