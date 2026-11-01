"""Fixed SOL V1 source contracts; no Engine or Strategy constructors."""
from dataclasses import asdict,replace
from decimal import Decimal as D
from types import SimpleNamespace as N
import json
import pytest
from coinmaster.strategy.cm2_sol_policy import SolConfig,SolPolicy,MODEL,policy_document
from coinmaster.strategy.cm2_checkpoint import canonical,decode
from coinmaster.strategy.cm2_sol_volatility import DAY_NS
from coinmaster.strategy.cm2_native import CM2Strategy
from coinmaster.research import cm2_runner as runner

NOW=61*DAY_NS


def sol():
    p=SolPolicy(SolConfig(enabled=True))
    for i in range(1,62):
        price="100" if i%2 else "200"
        p.accept_daily(i*DAY_NS,price,price,NOW)
    return p


def parent(side=1,level=0,planref=D(100)):
    return N(id="P",side=side,planref=planref,levels=(level,.02,.03),close_reason=None)


def observe(p,par=None,bid=D(100),ask=D(100),held=D(1),source=NOW):
    return p.observe_wave(par or parent(),native_btc=held,bid=bid,ask=ask,
        source_ns=source,receipt_ns=NOW)


@pytest.mark.parametrize("side,price",[(1,"101"),(-1,"99")])
def test_real_observation_zero_and_positive_threshold_no_initialized_permission(side,price):
    p=sol();assert p.exhaustion is None
    assert not observe(p,parent(side=side,planref=None),held=D(side))
    assert not observe(p,parent(side=side),held=D(0))
    assert not observe(p,parent(side=side,level=.01),held=D(side))
    assert observe(p,parent(side=side,level=.01),bid=D(price),ask=D(price),held=D(side))
    assert p.exhaustion["source_ns"]==NOW
    assert observe(p,parent(side=side),bid=D(90),ask=D(90),held=D(side)) # prior real fact retained


def test_zero_level_needs_quote_and_no_wire_or_q0_fallback():
    p=sol()
    assert not observe(p,bid=D("99.99"),ask=D("99.99"))
    assert observe(p)
    q=sol();assert not observe(q,source=NOW+1)


def test_opportunity_unknown_never_rearms_and_newparent_resets_market_fact():
    p=sol();observe(p)
    assert p.observe_gate("P",True)
    p.commit_opportunity()  # only an accepted grant consumes this opportunity
    assert not p.observe_gate("P",None)
    assert not p.observe_gate("P",True)
    assert not p.observe_gate("P",False)
    assert p.observe_gate("P",True)
    p.sync_parent("NEW");assert p.exhaustion is None and p.gate_truth is False


def opening(p):
    ep=p.opening_candidate(sponsor="P",btc_side=1,native_btc_notional=D(1000),
        sigma=D(".5"),executable_price=D(10),lot=D(".1"),now=NOW)
    assert ep.k==1 and ep.notional==1000 and ep.quantity==100
    p.episode=ep
    return ep


def test_exact_full_budget_totalcap_pending_once_and_no_add_after_completion():
    p=sol();ep=opening(p)
    def remain(nb=1000,price=10,held=80,pending=10):
        return p.remaining(native_btc_notional=D(nb),executable_price=D(price),lot=D(".1"),
            actual_sol=D(held),pending_growth=D(pending))
    assert remain()==10
    assert remain(nb=800,pending=0)==0
    assert remain(price=20,held=30,pending=5)==15
    assert ep.quantity==100 and ep.notional==1000
    p.retire_opening();assert remain(held=0,pending=0)==0


def test_partial_grant_frozen_sigma_hysteresis_and_no_tpflat_forced_exit():
    p=sol();ep=opening(p);p.native_fill()
    p.accept_daily(62*DAY_NS,"180","300",62*DAY_NS)
    assert ep.k==1 and ep.sigma==D(".5")
    assert not p.relative_exit(relative=.5,mu=0,daily_ns=62*DAY_NS,now=62*DAY_NS)
    assert p.remaining(native_btc_notional=D(1000),executable_price=D(10),lot=D(".1"),
        actual_sol=D(20),pending_growth=D(0))==80
    p.retire_opening();p.reconcile(native_flat=False,owners_terminal=True)
    assert p.episode is ep and ep.exit_reason is None
    assert p.relative_exit(relative=.05,mu=0,daily_ns=62*DAY_NS,now=62*DAY_NS)
    assert ep.exit_reason=="SOL_RELATIVE_CONVERGENCE" and not ep.opening_live


def test_only_sponsor_public_regime_or_trail_ends_thesis():
    p=sol();ep=opening(p)
    assert not p.market_end("OTHER","REGIME")
    assert not p.market_end("P","TP_FLAT")
    assert p.market_end("P","TRAIL")
    assert ep.exit_reason=="BTC_MARKET_TRAIL" and not ep.opening_live
    p.reconcile(native_flat=True,owners_terminal=False);assert p.episode is ep
    p.reconcile(native_flat=True,owners_terminal=True);assert p.episode is None


def test_checkpoint_roundtrip_retains_market_fact_frozen_inputs_and_known_gate():
    p=sol();observe(p);p.observe_gate("P",True);p.commit_opportunity();opening(p);p.native_fill()
    state=decode(json.loads(canonical(p.snapshot())))
    q=SolPolicy(p.config);q.restore(state,NOW)
    assert canonical(q.snapshot())==canonical(p.snapshot())
    assert not q.observe_gate("P",True)
    bad=dict(state);bad["daily"]=state["daily"][:-1]+[state["daily"][0]]
    with pytest.raises(ValueError):q.restore(bad,NOW)


def exact_daily():
    return {asset:{i*86400000:{"close":"100.000000000000000000001" if i%2 else "200"}
            for i in range(62)} for asset in ["BTCUSDT","SOLUSDT"]}


def test_exact_source_seed_before_float_conversion_future_and_missing_deny():
    daily=exact_daily();rows=runner.exact_paired_seed(daily,NOW//1000000)
    assert len(rows)==61 and rows[-1][0]==NOW
    assert any(b=="100.000000000000000000001" for _,b,_ in rows)
    daily["BTCUSDT"][60*86400000]["close"]=100.0
    with pytest.raises(ValueError,match="ORIGINAL_EXACT"):runner.exact_paired_seed(daily,NOW//1000000)
    daily=exact_daily();del daily["SOLUSDT"][30*86400000]
    with pytest.raises(ValueError):runner.exact_paired_seed(daily,NOW//1000000)


def test_strict_joint_policy_defaultoff_and_public_kwargs_no_constructor():
    from test_cm2_reference_native_pure import config
    from coinmaster.strategy.cm2_order_contract import MODEL_ID
    base=asdict(config());btc=runner.reference_config(base)
    assert runner.parse_sol_config(base) is None and not btc.candidate.sol_overlay_enabled
    joint={**base,"sol":{"model":MODEL,"enabled":True}}
    cfg=runner.CM2RunConfig(runner.reference_config(joint),sol_policy=runner.parse_sol_config(joint))
    assert json.loads(json.dumps(policy_document(cfg.policy,cfg.sol_policy)))==json.loads(json.dumps(joint))
    req=dict(policy=joint,start_ns=NOW,end_ns=NOW+DAY_NS,request_execution_model_id=MODEL_ID,
        data_root="/synthetic",artifact_dir="/synthetic-out",run_id="SYNTHETIC",initial_active_seed="10000",
        current_hl_execution_inputs="/synthetic-profile")
    assert runner.full_native_kwargs(req)["research_cm2"].sol_policy.enabled
    with pytest.raises(ValueError):runner.reference_config({**joint,"sol":{"model":MODEL,"enabled":1}})
    with pytest.raises(ValueError):runner.reference_config({**joint,"sol":{"model":MODEL,"enabled":True,"lookback":30}})


def test_shared_reachable_reserve_counts_consumed_tp_and_native_pending_once():
    from test_cm2_reference_native_pure import collateral,admit
    # Held4 + remaining(10-6)=8 at 40x, plus newSOL1 IM/fees fits .24;
    # old selected10 reserve would require >.27 and falsely deny.
    f,b,so,ss,balances,_,_=collateral(equity=".24",held="4")
    ss[0]=replace(ss[0],sol_mark=D(1),price_known={b:True,so:True})
    f.reference.parent=N(selected_quantity=D(10),filled_quantity=D(6),split_terminal=False)
    assert admit(f,so,1)
    f.reference.parent.filled_quantity=D(4)
    assert not admit(f,so,1)


def test_actual_send_reserves_whole_sol_parent_before_official_child():
    from test_cm2_reference_native_pure import order_boundary
    f,b,tick,sent=order_boundary(qty=D(1));iid=f.config.sol_id
    instrument=f.cache.instrument(iid)
    tick.bid_price=N(as_decimal=lambda:D(100));tick.ask_price=N(as_decimal=lambda:D(100))
    p=sol();p.episode=p.opening_candidate(sponsor="P",btc_side=1,native_btc_notional=D(1000),
        sigma=D(1),executable_price=D(100),lot=instrument.size_increment.as_decimal(),now=NOW)
    f.sol=p;f._sol_pending_growth=lambda:D(0)
    snap=f._snapshot(100)
    f._snapshot=lambda now:replace(snap,sol_mark=D(100),price_known={b.id:True,iid:True})
    calls=[];f._admit=lambda i,q,*a:calls.append(q) or False
    assert not CM2Strategy._send(f,iid,D(1),-1,"SOL_OPEN",100,tick)
    assert calls==[D(10)] and not sent # frozen N0=1000 /SOL100 caps fullparent10, not child1


def test_actual_btc_market_end_notification_precedes_synchronous_parent_reset():
    from test_cm2_reference_quote_phase_pure import phase_adapter
    f,clock,calls,quote=phase_adapter()
    p=sol();opening(p);p.native_fill();f.sol=p;f._needs_daily=True
    decision=N(action="BTC_CLOSE",parent_id="P",reason="REGIME")
    f.reference.decide_on_day=lambda **kw:decision
    f.reference.stop_entry_remainder=lambda *a,**kw:None
    f.reference.revoke_c1=lambda *a:None
    f._begin_drain=lambda *a:calls.append(("drain",a[1]))
    f._sol_request_exit=lambda now,reason:calls.append(("sol",reason))
    CM2Strategy._evaluate_daily(f,clock[0])
    assert calls[-2:]==[("drain","BTC_ECONOMIC"),("sol","BTC_MARKET_REGIME")]
    assert not p.episode.opening_live


def test_actual_config_constructor_seed_model_pass_through_without_strategy(monkeypatch,tmp_path):
    from pathlib import Path
    from test_cm2_reference_native_pure import config
    from coinmaster.research.current_hl_profile import load_current_hl_diagnostic
    from coinmaster.strategy import cm2_native
    profile=load_current_hl_diagnostic(Path(__file__).parent/"fixtures/hl-current-20261029")
    btc,so=profile.instruments;cfg=runner.CM2RunConfig(config(),sol_policy=SolConfig(enabled=True))
    monkeypatch.setattr(cm2_native,"CM2Strategy",lambda cfg:cfg)
    from coinmaster.ledger.journal import NativeEventJournal
    journal=NativeEventJournal(str(tmp_path/"synthetic.sqlite"))
    exact=runner.exact_paired_seed(exact_daily(),NOW//1000000)
    result=runner.build_strategy(cfg,instruments=(btc,so),minute_bars={btc.id:None,so.id:None},
        margin_policy=profile.margin_policy(120000000000),start_ns=NOW,end_ns=NOW+DAY_NS,
        mark_types=(None,None),mark_client=None,journal=journal,exit_fee_rate=D(".000432"),
        execution_hash="synthetic",seed_days=(),seed_ohlc=(),daily_types=(None,None),h4_type=None,
        signal_client=None,initial_seed=D(10000),seed_paired_closes=exact)
    assert result.sol_policy.enabled and result.seed_paired_closes==exact
    journal.close()


def native_sol_adapter():
    from coinmaster.strategy.cm2_execution import NativeExposure
    p=sol();par=parent();observe(p,par);qty={"BTC":D(10),"SOL":D(0)};owned={};orders=[];calls=[]
    feature=N(z=2.,sigma=.5,relative=1.,mu=0.)
    def position(i):
        q=qty[i]
        return N(quantity=N(as_decimal=lambda:abs(q)),is_long=q>0) if q else None
    f=N(sol=p,reference=N(parent=par,_features=N(bars=[N(close_time=__import__("datetime").datetime.fromtimestamp(NOW/1e9,__import__("datetime").timezone.utc),available_at=__import__("datetime").datetime.fromtimestamp(NOW/1e9,__import__("datetime").timezone.utc))])),config=N(btc_id="BTC",sol_id="SOL"),_owned=owned,
        _quotes={"SOL":N(ts_event=NOW,bid_price=N(as_decimal=lambda:D(10)),ask_price=N(as_decimal=lambda:D(10)))},
        cache=N(instrument=lambda i:N(size_increment=N(as_decimal=lambda:D(".1")))),
        target_blockers={},_persist_checkpoint=lambda:None,_position=position,_orders=lambda i:orders if i=="SOL" else [],
        _sol_daily_feature=lambda now:feature,_scope_for=lambda i:None,
        _snapshot=lambda now:NativeExposure(D(10000),qty["BTC"],qty["SOL"],D(100),D(10),
            False,True,{"BTC":True,"SOL":True}),
        _admit=lambda i,q,*a:calls.append(("admit",q)) or True,
        cancel_order=lambda order:calls.append(("cancel",order)),
        _begin_drain=lambda *a:calls.append(("drain",a[1],a[3])),
        _execute_drain=lambda *a:calls.append(("execute_drain",a[2])))
    for name in ["_sol_reconcile","_sol_pending_growth","_sol_refresh_opening","_sol_request_exit"]:
        setattr(f,name,lambda *a,_name=name: getattr(CM2Strategy,_name)(f,*a))
    def send(i,q,side,purpose,*a,**kw):
        calls.append(("send",q,side,purpose))
        owned["O"]={"instrument_id":"SOL"}
        orders.append(N(leaves_qty=N(as_decimal=lambda:q),is_reduce_only=False,is_pending_cancel=False))
        return True
    f._send=send
    scopes={}
    f._scope_for=lambda i:scopes.get(i)
    def begin(now,scope,ids,reason):
        calls.append(("drain",scope,reason))
        for i in ids:scopes[i]=scope
    f._begin_drain=begin
    return f,p,qty,orders,calls,feature


def test_actual_sol_quote_owns_one_opening_and_tpflat_retires_growth_not_actual_carry():
    f,p,qty,orders,calls,feature=native_sol_adapter();tick=f._quotes["SOL"]
    CM2Strategy._execute_sol(f,tick,NOW)
    assert calls[:2]==[("admit",D(100)),("send",D(100),-1,"SOL_OPEN")]
    CM2Strategy._execute_sol(f,tick,NOW)
    assert sum(c[0]=="send" for c in calls)==1
    qty["SOL"]=D(-20);p.native_fill();qty["BTC"]=D(0)
    CM2Strategy._execute_sol(f,tick,NOW)
    assert p.episode is not None and not p.episode.opening_live and p.episode.exit_reason is None
    assert any(c[0]=="cancel" for c in calls) and not any(c[0]=="drain" for c in calls)
    feature.relative=.05
    CM2Strategy._execute_sol(f,tick,NOW)
    assert calls[-1]==("execute_drain","SOL_SUBORDINATE")
    assert any(c[:2]==("drain","SOL_SUBORDINATE") for c in calls)


def test_actual_paired_daily_callback_preserves_original_decimal_strings():
    from datetime import datetime,timezone
    from coinmaster.venues.signals import DailySignalBar
    from test_cm2_reference_cycle_pure import policy,row,T0
    ref=policy()
    for i in range(35):
        ref.accept_closed_day(row(i),receipt_ns=T0+(i+1)*DAY_NS,btc_high=101,btc_low=99)
    close_ns=T0+36*DAY_NS;p=SolPolicy(SolConfig(enabled=True))
    p.accept_daily(close_ns-DAY_NS,"100","150",close_ns)
    f=N(sol=p,reference=ref,clock=N(timestamp_ns=lambda:close_ns),
        config=N(btc_id="BTC",sol_id="SOL"),_finalize_btc_receipt=lambda now:None,
        _days_pending={},_needs_daily=False,_evaluate_daily=lambda now:None)
    price=D("100.0000000000000000000001")
    CM2Strategy.on_data(f,DailySignalBar("BTC",D(100),D(101),D(99),price,close_ns))
    assert len(p.daily)==1
    CM2Strategy.on_data(f,DailySignalBar("SOL",D(150),D(151),D(149),D("150.0000000000000000000001"),close_ns))
    assert p.daily[-1].btc_close==str(price) and p.daily[-1].sol_close=="150.0000000000000000000001"


def test_real_checkpoint_cas_and_report_identity_keep_joint_model_and_sol_episode(tmp_path):
    import sqlite3
    from pathlib import Path
    from coinmaster.strategy.cm2_checkpoint import NativeCheckpointStore
    from test_cm2_reference_native_pure import config
    from test_cm2_reference_cycle_pure import policy
    from coinmaster.strategy.cm2_execution import SafetyState
    p=sol();observe(p);p.observe_gate("P",True);opening(p)
    db=sqlite3.connect(tmp_path/"joint.sqlite");store=NativeCheckpointStore(N(db=db))
    cfg=N(policy=config(),sol_policy=p.config,checkpoint_store=store,
        continuity_reader=lambda:{"source":42},margin_policy=N(),
        terminal_close_at_ns=NOW+DAY_NS)
    f=N(sol=p,reference=policy(),config=cfg,clock=N(timestamp_ns=lambda:NOW),
        safety=SafetyState(),_owned={},_order_audit={},_seen_trade_ids=set(),_queued_tp={},
        _needs_daily=False,_tp_ready_ns=0,_drain={},_btc_source_frame=None,_restore_failed=False,
        _risk_unknown=False,_liquidating=False,_days_pending={},_checkpoint_revision=0,
        _retained_audit_chain="synthetic",fill_audit=[],cm2_audit=[],
        _native_checkpoint_binding=lambda:{"actual_native_fixture":1},
        _feed_checkpoint_binding=lambda:{"clock":NOW},
        _checkpoint_identity=lambda:{"typed_sol":asdict(p.config),"source":"synthetic"},
        _admission_sources={"cm2_sol_policy.py":"source","cm2_sol_volatility.py":"locked"})
    f._checkpoint_document=lambda:CM2Strategy._checkpoint_document(f)
    saved=CM2Strategy.on_save(f)
    original=canonical(p.snapshot());p.episode=None
    CM2Strategy.on_load(f,saved)
    assert f._checkpoint_loaded and canonical(f.sol.snapshot())==original
    f.cache=N(positions_open=lambda:[],orders_open=lambda:[],orders_inflight=lambda:[])
    f._request_contract_identity=lambda:CM2Strategy._request_contract_identity(f)
    f.liquidation_audit=[];f.pre_submit_gate_blocks=[];f.entry_sizing_audit=[]
    f._capital_last=None;f._capital_unknown=None;f.drain_audit=[];f.child_permission_audit=[]
    f.target_blockers={};f.orphan_intervals=[];f.orphan_started_ns=None
    f._liquidation_checks=0;f._liquidation_unknown=0
    result=CM2Strategy.reporting_state(f)
    assert result["cm2"]["policy"]["sol"]==asdict(p.config)
    assert result["cm2"]["request_contract"]["sol_model"]==asdict(p.config)
    assert result["cm2"]["sol_staging_harvest_context"]["state"]["episode"]["k"]=="1"
    db.close()

@pytest.mark.parametrize("foreign",[None,"old","missing"])
def test_actual_sol_fill_identity_duplicate_and_foreign_safety(foreign):
    from test_cm2_reference_native_pure import ID
    p=sol();ep=opening(p);owner=asdict(ep)
    if foreign=="old":owner["accepted_ns"]-=1
    if foreign=="missing":p.episode=None
    calls=[];btc,so=ID("BTC"),ID("SOL")
    f=N(sol=p,config=N(btc_id=btc,sol_id=so,execution_policy_hash="synthetic"),reference=N(parent=None),
        _owned={},_order_audit={"O":{"purpose":"SOL_OPEN","sol_episode":owner}},_seen_trade_ids=set(),
        fill_audit=[],_liquidating=False,safety=N(global_latched=False),_restore_failed=False,
        clock=N(timestamp_ns=lambda:NOW),_chain_audit=lambda *a:None,
        _terminal_event=lambda *a,**kw:None,_persist_checkpoint=lambda:None,
        _begin_drain=lambda *a:calls.append(a))
    ev=N(trade_id="T",client_order_id="O",instrument_id=so,ts_event=NOW,
        last_qty=N(as_decimal=lambda:D(1)),last_px=N(as_decimal=lambda:D(10)),
        commission=N(as_decimal=lambda:D(".01"),currency="USDC"),
        liquidity_side=N(name="TAKER"),order_side=N(name="SELL"))
    CM2Strategy.on_order_filled(f,ev);CM2Strategy.on_order_filled(f,ev)
    assert len(f.fill_audit)==1 and f.fill_audit[0]["notional"]=="10"
    if foreign is None:
        assert p.episode.native_filled and not calls
    else:
        assert not f.safety.global_latched and not f._restore_failed and calls[0][1]=="SOL_SUBORDINATE"
        assert p.episode is None or not p.episode.native_filled

def test_preaccept_hold_keeps_true_opportunity_unspent_until_actual_request():
    f,p,qty,orders,calls,feature=native_sol_adapter();tick=f._quotes["SOL"]
    f._admit=lambda *a:False
    CM2Strategy._execute_sol(f,tick,NOW)
    assert p.gate_truth is True and not p.gate_spent and p.episode is None
    f._admit=lambda *a:True
    f._send=lambda *a,**kw:False
    CM2Strategy._execute_sol(f,tick,NOW)
    assert p.gate_truth is True and not p.gate_spent and p.episode is None
    def accepted(*a,**kw):
        f._owned["accepted"]={"instrument_id":"SOL"}
        return True
    f._send=accepted
    CM2Strategy._execute_sol(f,tick,NOW)
    assert p.episode is not None and p.gate_spent
    p.retire_opening();p.reconcile(native_flat=True,owners_terminal=True)
    f._owned.clear()
    CM2Strategy._execute_sol(f,tick,NOW)
    assert p.episode is None and p.gate_spent # unchanged knownTRUE never reopens
