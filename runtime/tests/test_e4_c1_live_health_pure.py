"""Actual worker -> LIVE runtime -> current authority, SQLite only; no native imports."""
import ast
import json
import time
from dataclasses import replace
from decimal import Decimal as D
from types import SimpleNamespace as N
import pytest
from coinmaster.domain.wave_overlay import Episode, Intent
from coinmaster.ops.paper import PaperRuntime
from test_e4_c1_manage_only_pure import code, nodes, run_ast, order, Q, ACCOUNT_ID, ROOT
from test_e4_c1_input_bridge_pure import fresh_init_fixture


def worker_source():
    env=dict(time=time, Decimal=D, HyperliquidTestnetNode=N(sandbox_snapshot=None,
        strategy_restartable=None,start=None,stop=None))
    run_ast(nodes('ops/hl_live_worker.py',{'HyperliquidLiveNode'}),env)
    return env['HyperliquidLiveNode']


def active(code,tmp_path):
    s,r,initial,now=fresh_init_fixture(code,tmp_path)
    s.initialize_clean_flat_c1_epoch(initial,intent='INITIALIZE_FRESH_C1_EPOCH',now_ns=now,history_anchor_ms=0)
    assert r._fresh_c1_epoch_active and not r._local_sandbox_active
    s._active_c1_authorized=True;s._manage_only_preparation=False;s.recovery_confirmed=True
    s._capital_basis_verified=True;s._recovery_health=lambda:True;s._live_input_ws_epoch=lambda:4
    s._live_context_current=lambda:True;s._live_increase_headroom=lambda:True
    s.deposit_projection=lambda:dict(state='ARMED')
    s._domain.episode=Episode('episode',1,100000,1)
    cfg=s.config;code.env['OrderSide']=N(SELL='SELL',BUY='BUY')
    s.establish_owned_effect_chain(account_id=ACCOUNT_ID,ws_epoch=4,
        policy_sha256=code.env['recovery_policy_hash'](cfg,s._candidate))
    # A11 durable shape: terminal .00079 entry, terminal .000395 original TP
    # after .000237 fills and a replacement acknowledged .000237 BTC TP.
    entry=order('ENTRY',side='BUY',quantity='.00079',reduce=False,closed=True)
    old=order('OLD-TP',side='SELL',quantity='.000395',reduce=True,closed=True)
    tp=order('TP',side='SELL',quantity='.000237',reduce=True)
    tp.order_type=N(name='LIMIT');tp.time_in_force=N(name='GTC')
    tp.is_pending_update=False;tp.is_post_only=True;tp.has_price=True;tp.price=Q('101000')
    code.env['OrderSide']=N(SELL=tp.side,BUY=entry.side)
    pos=N(instrument_id=cfg.btc_id,strategy_id=str(s.id),account_id=ACCOUNT_ID,
          is_long=True,quantity=Q('.000553'),events=[N(client_order_id='ENTRY',trade_id='101'),N(client_order_id='OLD-TP',trade_id='102')])
    intent=Intent('tp-intent','episode','BTC_REDUCE',1,-1,quantity=.000237,limit_price=101000,reason='BTC_TP1')
    s._pending_by_order={'TP':intent}
    for client,action,quantity,reduce in [('ENTRY','BTC_ENTRY','.00079',False),('OLD-TP','BTC_REDUCE','.000395',True),('TP','BTC_REDUCE','.000237',True)]:
        r.record_submission(client_order_id=client,intent_id=intent.id if client=='TP' else client,
            episode_id='episode',action=action,instrument_id=str(cfg.btc_id),quantity=quantity,reduce_only=reduce,
            order_shape=dict(side='SELL' if reduce else 'BUY',kind='LIMIT',tif='GTC',post_only=True,price='101000'))
        if client!='TP':r.terminal_submission(client)
    r.db.execute("UPDATE paper_intents SET state='ACKED' WHERE client_order_id='TP'");r.db.commit()
    for tid,client,quantity in [('101','ENTRY','.00079'),('102','OLD-TP','.000237')]:
        r.record_native_fill(trade_id=tid,native_event_id='native-'+tid,client_order_id=client,
            venue_order_id='100',instrument_id=str(cfg.btc_id),quantity=quantity,price='100000',
            order_side='BUY' if client=='ENTRY' else 'SELL',commission_amount='0',commission_currency='USDC',
            liquidity_side='MAKER',ts_event_ns=int(tid)*1_000_000,ts_init_ns=int(tid)*1_000_000)
        r.db.execute('INSERT INTO paper_recovered_fills VALUES (?)',(tid,));r.db.commit()
    r.db.commit()
    orders=[entry,old,tp]
    account=s.cache.account_for_venue(cfg.btc_id.venue);account.balance_free=account.balance_total
    s.cache=N(orders=lambda venue=None:list(orders),positions_open=lambda:[pos],account_for_venue=lambda venue:account)
    view=replace(initial,end_ms=time.time_ns()//1_000_000,native_revision=r.native_revision(),position_sizes=(('BTC',D('.000553')),))
    s._live_money_provider=lambda:view;s.accept_live_financial_authority(started_ns=time.monotonic_ns())
    node=object.__new__(worker_source());node.state=r;node.strategy=s;node.active_c1=True
    node.input_readiness=False;node._refresh_warmup_readiness=lambda:None
    node.gate=N(attachable=True);node.node=N(is_running=lambda:True)
    node.feed=N(status=lambda now:dict(BTC=dict(state='READY'),SOL=dict(state='READY')))
    r.bind_live_health(node._live_health_current)
    r.entry_control_command('resume-new-entries','resume-after-actual-init')
    return N(s=s,r=r,node=node,view=view,tp=tp,pos=pos,orders=orders)


def test_actual_worker_live_health_uses_fresh_authority_not_stale_paper_snapshot(code,tmp_path):
    c=active(code,tmp_path)
    try:
        before=c.r.db.execute('SELECT body FROM paper_snapshot').fetchone()[0]
        assert json.loads(before)['native_revision']==0
        assert c.r.recovery_state()=='MANAGE_ONLY_PENDING_INTENT'
        assert not PaperRuntime.health(c.r,time.time_ns()).safe_for_increase
        calls=[];current=c.s._current_owned_money
        def read():
            assert not calls # Detect indirect runtime.health recursion on real call chain.
            calls.append(1)
            try:return current()
            finally:calls.pop()
        c.s._current_owned_money=read
        assert c.node._live_health_current()
        assert c.node._entries_enabled()
        assert c.r.health(time.time_ns()).safe_for_increase
        assert c.r.db.execute('SELECT body FROM paper_snapshot').fetchone()[0]==before
        assert not c.r._local_sandbox_active
        # An actual partial replacement fill still reserves only its leaves.
        c.tp.filled_qty=Q('.0001')
        assert c.node._entries_enabled()
        # Once native/journal are terminal, stale paper revision must not block.
        c.tp.is_closed=True;c.r.terminal_submission('TP');c.s._pending_by_order={}
        c.s._live_money_provider=lambda:replace(c.view,native_revision=c.r.native_revision())
        assert c.node._entries_enabled()
    finally:c.r.close()


@pytest.mark.parametrize('fault',['pause','flatten','cashflow','funding','command','ws','policy','context','budget','capital','dp','feed','stale','suspended','revision','unknown_ack','pending_cancel','pending_update','foreign','missing_native','foreign_open','nonreduce','sol','quantity','price','tif','kind','postonly','overreserved','episode','pending_intent','position','account'])
def test_actual_live_health_fails_closed(code,tmp_path,fault):
    c=active(code,tmp_path)
    try:
        if fault=='pause':c.r.entry_control_command('pause-new-entries','owner-pause')
        elif fault=='flatten':c.r.db.execute("INSERT INTO paper_commands VALUES ('flatten','flatten-paper')");c.r.db.commit()
        elif fault=='cashflow':c.r.db.execute("INSERT INTO live_evidence_cursors VALUES ('external_cashflow_quarantine','{}')");c.r.db.commit()
        elif fault=='funding':c.r.pending_native_funding=lambda:[{'unknown':'cash'}]
        elif fault=='command':c.r.db.execute("INSERT INTO paper_command_audit VALUES ('manage','x','MANAGE_SUBMITTING',1)");c.r.db.commit()
        elif fault=='ws':c.s._live_input_ws_epoch=lambda:5
        elif fault=='policy':c.s.config.research_c1_restore_dd=D('.41')
        elif fault=='context':c.s._live_context_current=lambda:False
        elif fault=='budget':c.s._live_increase_headroom=lambda:False
        elif fault=='capital':c.s._capital_basis_verified=False
        elif fault=='dp':c.s.deposit_projection=lambda:dict(state='LATCHED')
        elif fault=='feed':c.node.feed.status=lambda now:dict(BTC=dict(state='STALE'))
        elif fault=='stale':c.s._live_financial_deadline_ns=time.monotonic_ns()-1
        elif fault=='suspended':c.s.suspend_live_financial_authority()
        elif fault=='revision':c.r._bump_native_revision();c.r.db.commit()
        elif fault=='unknown_ack':c.r.db.execute("UPDATE paper_intents SET state='SUBMITTING' WHERE client_order_id='TP'");c.r.db.commit()
        elif fault=='pending_cancel':c.tp.is_pending_cancel=True
        elif fault=='pending_update':c.tp.is_pending_update=True
        elif fault=='foreign':c.tp.strategy_id='FOREIGN'
        elif fault=='missing_native':c.orders.remove(c.tp)
        elif fault=='foreign_open':c.orders.append(order('FOREIGN'))
        elif fault=='nonreduce':c.tp.is_reduce_only=False
        elif fault=='sol':c.tp.instrument_id=c.s.config.sol_id
        elif fault=='quantity':c.tp.quantity=Q('.000238')
        elif fault=='price':c.tp.price=Q('100999')
        elif fault=='tif':c.tp.time_in_force=N(name='IOC')
        elif fault=='kind':c.tp.order_type=N(name='MARKET')
        elif fault=='postonly':c.tp.is_post_only=False
        elif fault=='overreserved':c.tp.filled_qty=Q('-.001')
        elif fault=='episode':c.s._domain.episode.id='different'
        elif fault=='pending_intent':c.s._pending_by_order={}
        elif fault=='position':c.pos.quantity=Q('.000552')
        elif fault=='account':c.tp.account_id='FOREIGN'
        assert not c.node._entries_enabled()
    finally:c.r.close()


def test_restart_durable_init_and_callback_cannot_regrant_process_authority(code,tmp_path):
    c=active(code,tmp_path);path=tmp_path/'fresh.sqlite'
    assert c.node._entries_enabled();c.r.close()
    restarted=code.Runtime(path,'fresh-owner',10**20);restarted.acquire()
    try:
        assert restarted.c1_initialization() and not restarted._fresh_c1_epoch_active
        restarted.bind_live_health(lambda:pytest.fail('durable bytes must never consult LIVE proof'))
        assert restarted.recovery_state()=='MANAGE_ONLY_PENDING_INTENT'
        assert not restarted.health(time.time_ns()).safe_for_increase
    finally:restarted.close()


def test_failed_initialization_never_sets_process_marker(code,tmp_path):
    s,r,view,now=fresh_init_fixture(code,tmp_path)
    try:
        with pytest.raises(ValueError):
            s.initialize_clean_flat_c1_epoch(view,intent='wrong',now_ns=now,history_anchor_ms=0)
        assert not r._fresh_c1_epoch_active and r.c1_initialization() is None
    finally:r.close()
