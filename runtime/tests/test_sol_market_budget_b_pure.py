"""Actual B pure solver/callback gates. Never constructs a backtest engine."""
from decimal import Decimal as D
from types import SimpleNamespace as N
from itertools import product
import pytest
from coinmaster.strategy.sol_market_budget import solve_budget,stress,ClosedD1Wilder14,SolMarketBudgetResearch

def solve(**kw):
    args=dict(b=D('100'),held_qty=D('100'),price=D(1),step=D(1),max_qty=D('150'),
              a=D('.2'),sol_a=D('.2'),beta=D(1),side=1,budget=D('40'))
    args.update({k:D(str(v)) if k not in ('side','beta') or v is not None else None for k,v in kw.items()})
    if 'side' in kw:args['side']=int(kw['side'])
    return solve_budget(**args)

def test_same_direction_budget_caps_increase():
    r=solve();assert r.status=='FEASIBLE' and D(0)<r.target_qty<D(100)
    assert stress(D(100),b=D(100),held=D(100),a=D(".2"),sol_a=D(".2"),beta=D(1),side=1)==D("42.1000")

def test_positive_lower_hedge_bound_and_no_grid_feasible():
    r=solve(b=-100,held_qty=100,max_qty=150,budget=5)
    assert r.status=='FEASIBLE' and r.lower_qty>0 and r.target_qty>r.lower_qty
    r=solve(b=-100,held_qty=100,max_qty=150,budget=0)
    assert r.status=='UNATTAINABLE' and r.target_qty==100

def test_original_demand_bounds_and_negative_budget():
    assert solve(b=0,budget=100,held_qty=10,max_qty=15).target_qty==15
    assert solve(b=100,budget=-1).status=='UNATTAINABLE'

def test_unknown_beta_no_hedge_credit():
    assert solve(b=-100,budget=5,beta=None).status=='UNATTAINABLE'

def test_delta_legal_minimum_preserves_dust_truthfully():
    r=solve(b=0,held_qty=1,max_qty=1,budget=-1,min_notional=10)
    assert r.status=='UNATTAINABLE' and r.target_qty==1

def test_solver_matches_exhaustive_native_lattice():
    for b,beta,side,budget,held,minimum in product((-20,0,20),(None,D('1.5')),(-1,1),(-1,0,2,5,20),(0,8),(0,3)):
        args=dict(b=D(b),held_qty=D(held),price=D('1.25'),step=D('.5'),max_qty=D(12),
                  a=D('.2'),sol_a=D('.3'),beta=beta,side=side,budget=D(budget),min_qty=D(minimum))
        r=solve_budget(**args);valid=[];reachable=[]
        for i in range(25):
            q=D(i)/2
            if q!=held and abs(q-held)<minimum:continue
            g=stress(q*args['price'],b=D(b),held=D(held)*args['price'],a=args['a'],sol_a=args['sol_a'],beta=beta,side=side)
            if g<=budget:valid.append(q)
            if q<=held:reachable.append((g,-q,q))
        if valid:assert r.status=='FEASIBLE' and r.target_qty==max(valid)
        else:assert r.status=='UNATTAINABLE' and r.target_qty==min(reachable)[2]

def test_closed_d1_wilder_and_gap_fail_closed():
    a=ClosedD1Wilder14();day=86_400_000_000_000
    for i in range(15):a.append((i+1)*day,102,98,100)
    assert a.atr==4 and a.valid
    a.append(17*day,103,97,100);assert not a.valid
    a.append(10*day,999,1,2);assert a.ns==17*day

class Gates(SolMarketBudgetResearch):pass

def gate():
    s=Gates();s.config=N(research_sol_market_budget_b=True,sol_id='S',btc_id='B',max_mark_age_ns=1000)
    s._sol_b_armed=True;s.sol_market_budget_audit=[]
    s._sol_b_current=lambda ns:{'positions':{'S':('p',D(100),True)},'E':D(100),'H':D(100),'source':8,'receipt':9,'epoch':0}
    s._sol_b_orders=lambda:[]
    s._sol_b_result=lambda c,q,d:N(status='FEASIBLE',target_qty=D(110),stress=D(1))
    return s

def test_increase_budget_before_native_admission_and_c1_independent():
    s=gate();s._c1_state={'state':'RELEASED'}
    assert s._sol_b_increase_qty(D(50),1,10)==10
    assert s._sol_b_increase_qty(D(50),-1,10)==0
    s._sol_b_current=lambda ns:None
    assert s._sol_b_increase_qty(D(50),1,10)==0

@pytest.mark.parametrize('reduce_only',[True,False])
def test_pending_order_never_credits_budget_or_allows_second_increase(reduce_only):
    s=gate();s._sol_b_orders=lambda:[N(is_reduce_only=reduce_only,leaves_qty=D(50))]
    assert s._sol_b_increase_qty(D(50),1,10)==0

def test_unattainable_never_allows_increase():
    s=gate();s._sol_b_result=lambda *a:N(status='UNATTAINABLE',target_qty=D(110),stress=D(1))
    assert s._sol_b_increase_qty(D(50),1,10)==0

def test_actual_dispatch_b_sizes_before_margin_a_sizes_after():
    from test_sol_capital_staging_a_pure import dispatch
    r=dispatch('10000',enabled=False,b_budget=D(37))
    assert r.gates==[D(37)] and len(r.sent)==1 and r.sent[0].quantity.as_decimal()==37
    assert r.ep.sol_rights=={0} and r.ep.sol_add_filled_notional=={}
    r=dispatch('10000',enabled=False,b_budget=D(0))
    assert r.sent==[]

def test_mutually_exclusive_api_rejects_before_engine(monkeypatch,tmp_path):
    from coinmaster.research import native_baseline as n
    import nautilus_trader.backtest.engine as e
    def forbidden(*a,**kw):raise AssertionError('engine called')
    monkeypatch.setattr(e,'BacktestEngine',forbidden)
    with pytest.raises(ValueError,match='SOL_A_AND_B_ARE_EXCLUSIVE'):
        n.run_native_diagnostic(tmp_path,research_sol_capital_staging_a=True,research_sol_market_budget_b=True)

def test_live_profile_explicitly_unsupported_before_base(monkeypatch):
    from coinmaster.strategy.live_recovery import RecoverableWaveOverlayStrategy
    with pytest.raises(ValueError,match='SOL_B_LIVE_RECEIPT_AND_RECOVERY_NOT_QUALIFIED'):
        RecoverableWaveOverlayStrategy(N(research_sol_market_budget_b=True))

def test_epoch_and_native_position_receipts_cannot_mix():
    s=gate();s._c1_fill_epoch=4;s._last_accepted_session=10
    s._sol_b_atr=[N(valid=True,ns=10,atr=D(1))]*2
    c=dict(source=20,receipt=21,epoch=4,positions={'S':('p',D(10),True)},account_identity=('account',20))
    s._bars=[N(available_at=N(timestamp=lambda:10/1e9))]
    s._sol_b_snapshot=c
    s.cache=N(account_for_venue=lambda v:N(last_event=N(id="account",ts_event=20)),positions_open=lambda:[N(instrument_id='S',id='p',quantity=N(as_decimal=lambda:D(10)),is_long=True)])
    s.config.btc_id=N(venue='V')
    assert SolMarketBudgetResearch._sol_b_current(s,30) is c
    s._c1_fill_epoch=5
    assert SolMarketBudgetResearch._sol_b_current(s,30) is None
    s._c1_fill_epoch=4;s.cache.positions_open=lambda:[N(instrument_id='S',id='p',quantity=N(as_decimal=lambda:D(9)),is_long=True)]
    assert SolMarketBudgetResearch._sol_b_current(s,30) is None

@pytest.mark.parametrize('initial_high,final_money,accepted',[(100,100,True),(100,95,False),(90,100,False)])
def test_receipt_rejects_same_source_same_epoch_cash_change_and_later_hwm(initial_high,final_money,accepted):
    from coinmaster.research.minute_risk import NativeMinuteRiskRecorder
    from nautilus_trader.model.identifiers import InstrumentId
    btc=InstrumentId.from_str('BTC.TEST');sol=InstrumentId.from_str('SOL.TEST')
    bundle=N(btc_mark={'close':'100'},sol_mark={'close':'10'},open_time_ms=0)
    r=NativeMinuteRiskRecorder.__new__(NativeMinuteRiskRecorder)
    r.receipt_pending=None;r.receipt_b_frame=None;r.fill_epoch=3;r.last_fill_ns=10
    r.bundles={10:bundle};r.end_exclusive_ns=1000;r.phase_counts={'post_quote_paired_close':0}
    r.curves={k:N(add=lambda *a:None) for k in ('post_quote_paired_close','all_native_close_samples')}
    r.writer=N(writerow=lambda *a:None);r.rows=0
    r._snapshot=lambda *a:(bundle,D(100),D(100),D(0),D(0),D(100),D(0),D(0),D(0),[])
    r.settled_curve=N(add=lambda *a:None);r.receipt_writer=N(writerow=lambda *a:None);r.receipt_count=0
    got=[];hwm=[D(initial_high)]
    s=N(config=N(btc_id=btc,sol_id=sol,research_sol_market_budget_b=True,research_residual_recovery=False,
                   research_sol_market_budget_high_water_reader=lambda:hwm[0]),
        cache=N(account_for_venue=lambda *a:N(last_event=N(id='account',ts_event=10))),
        _sol_b_observe=lambda *a,**kw:got.append((a,kw)))
    r.capture(s,10,'post_quote_paired_close')
    if initial_high>=100:assert r.receipt_b_frame['H']==100 and r.receipt_b_frame['E']==100
    else:assert r.receipt_b_frame is None  # callback E cannot invent a canonical peak
    hwm[0]=D(999)
    r._snapshot=lambda *a:(bundle,D(final_money),None,None,None,D(final_money),None,None,None,[])
    r.finalize_receipt(s,11)
    assert (got[0][1]['high_water']==100) if accepted else got[0][1]['high_water'] is None
    assert r.receipt_b_frame is None


def test_activation_release_only_flat_terminal_and_recovered():
    s=Gates();s.config=N(research_sol_market_budget_b=True,btc_id='B',sol_id='S')
    s._sol_b_armed=False;s.sol_market_budget_audit=[];s._c1_state={'state':'RELEASED'}
    p=N(id='p',instrument_id='S',quantity=N(as_decimal=lambda:D(10)),is_long=True,
        unrealized_pnl=lambda mark:N(as_decimal=lambda:D(-15)))
    positions=[p];orders=[]
    s.cache=N(positions_open=lambda:positions,instrument=lambda iid:N(make_price=lambda x:N(as_decimal=lambda:D(x))))
    s._latest_marks={'B':N(ts_event=11,price=D(999)),'S':N(ts_event=11,price=D(999))}
    s._sol_b_orders=lambda:orders
    rows=[{'instrument_id':'S','mark_ohlc':{'close':'10'}}]
    s._sol_b_observe(D(50),11,10,0,rows,high_water=D(100),source_marks={'B':D(100),'S':D(10)},account_identity=('account',10))
    assert s._sol_b_armed and s._sol_b_snapshot["marks"]=={"B":D(100),"S":D(10)}
    # C1 state cannot clear it; recovered money with position still held cannot.
    s._sol_b_observe(D(90),11,10,0,rows,high_water=D(100),source_marks={'B':D(100),'S':D(10)},account_identity=('account',10));assert s._sol_b_armed
    positions.clear();orders.append(N())
    s._sol_b_observe(D(90),11,10,0,[],high_water=D(100),source_marks={'B':D(100),'S':D(10)},account_identity=('account',10));assert s._sol_b_armed
    orders.clear();s._sol_b_observe(D(50),11,10,0,[],high_water=D(100),source_marks={'B':D(100),'S':D(10)},account_identity=('account',10));assert s._sol_b_armed
    s._sol_b_observe(D(90),11,10,0,[],high_water=D(100),source_marks={'B':D(100),'S':D(10)},account_identity=('account',10));assert not s._sol_b_armed

def test_pending_increase_whole_leaves_cancel_unknown_no_fake_trim():
    s=gate();s._sol_b_current=lambda ns:None
    orders=[N(is_reduce_only=False,is_pending_cancel=False),N(is_reduce_only=True,is_pending_cancel=False)]
    s._sol_b_orders=lambda:orders;cancel=[];s.cancel_order=cancel.append
    assert not s._sol_b_quote(N(instrument_id='S'),20)
    assert cancel==orders[:1]

@pytest.mark.parametrize('position_first',[False,True])
def test_actual_native_trim_callbacks_no_duplicate_or_target_assumption(position_first):
    from types import MethodType
    from test_sol_staging_all_paths_pure import ordinary
    from coinmaster.research.native_fixture import instrument_quote
    c,_=ordinary('SOL_EXIT','NO_SUBMISSION',4000,requested=0);s=c.s
    s.config=s.config.__replace__(research_sol_capital_staging_a=False,research_sol_market_budget_b=True,max_mark_age_ns=1000)
    for name in ('_sol_b_orders','_sol_b_current','_sol_b_result','_sol_b_quote','_sol_b_log'):
        setattr(s,name,MethodType(getattr(SolMarketBudgetResearch,name),s))
    s._sol_b_armed=True;s._sol_b_last_held=None;s.sol_market_budget_audit=[];s._c1_fill_epoch=0
    s._hb_position=lambda iid:c.position if iid==c.sol.id else None
    s._c1_own_pending=lambda:False;s._has_owned_sol_exit=lambda:bool(s._accepted_reductions)
    s._bars=[N(available_at=N(timestamp=lambda:50/1e9))]
    s._last_accepted_session=50;s._sol_b_atr=[N(valid=True,ns=50,atr=D(1))]*2
    s._current_signals=[N(beta=1)]
    s._sol_b_snapshot=dict(E=D(10000),H=D(20000),source=98,receipt=99,epoch=0,
        positions={c.sol.id:(str(c.position.id),D(4000),True)},marks={c.sol.id:D(100),c.btc.id:D(100)},account_identity=('account',98))
    s.cache.account_for_venue=lambda v:N(last_event=N(id="account",ts_event=98))
    tick=instrument_quote(c.sol,'100','100',100)
    assert s._sol_b_quote(tick,100)
    assert len(c.sent)==1 and c.sent[0].is_reduce_only and c.sent[0].quantity.as_decimal()==3950
    assert not s._sol_b_quote(tick,100) and len(c.sent)==1
    order=c.sent[0];event=c.fill(order,ts=100)
    def epoch(e):s._c1_fill_epoch+=1
    s._c1_native_fill=epoch
    if position_first:c.position.apply(event)
    order.apply(event);s.on_order_filled(event)
    if not position_first:
        # Filled-before-position cannot reuse old snapshot/fill epoch.
        assert not s._sol_b_quote(tick,100)
        c.position.apply(event)
    s.on_order_filled(event)  # native duplicate trade is inert
    assert s._c1_fill_epoch==1 and c.position.quantity.as_decimal()==50
    assert s._domain.episode.sol_qty==50 and not s._sol_b_quote(tick,100)
    assert len(c.sent)==1

@pytest.mark.parametrize('side,held,max_qty,budget,step,status,target',[
    (1,'100','100','20.1','.0001','FEASIBLE','83.3333'),
    (-1,'150','150','5.125','.0001','FEASIBLE','125'),
    (-1,'100','150','5.125','.0001','FEASIBLE','125'),
    (-1,'150','150','1.125','.0001','UNATTAINABLE','100'),
    (-1,'50','50','5.075','.0001','UNATTAINABLE','50'),
    (-1,'180','180','2.24','60','UNATTAINABLE','120'),
])
def test_frozen_independent_math_contract(side,held,max_qty,budget,step,status,target):
    r=solve_budget(b=D(100),held_qty=D(held),price=D(1),step=D(step),max_qty=D(max_qty),
                  a=D('.1'),sol_a=D('.12'),beta=D(1),side=side,budget=D(budget))
    assert r.status==status and r.target_qty==D(target)

def test_actual_c1_restore_budget_precedes_its_native_gate():
    from coinmaster.strategy.residual_recovery import ResidualRecoveryResearch
    from coinmaster.domain.wave_overlay import WaveOverlayState,Candidate,Episode
    from nautilus_trader.model.identifiers import InstrumentId
    class C(ResidualRecoveryResearch):pass
    s=C();sol=InstrumentId.from_str('SOL.TEST');btc=InstrumentId.from_str('BTC.TEST')
    s.config=N(research_residual_recovery=True,research_c1_first_fresh_h4=False,research_c1_restore_dd=D('.35'),
        research_sol_market_budget_b=True,terminal_close_at_ns=None,sol_id=sol,btc_id=btc)
    t=s._c1_state=dict(state='HELD',targets_need_requeue=False,revoked=False,instrument=sol,
        restore_submitted=False,credit=100,side=1,confirmation={'close_ns':10,'close':D(21)},
        cut_value=D(2000),cut_filled=100,step=D(1),claim_ns=1,group='ep',cut_terminal_ns=8,last_cut_fill_ns=7)
    s._forced_close_reason=None;s._liquidating=False;s._mandatory_sol_exit=None
    s._queued_intents=[];s._pending_by_order={};s._c1_intents={};s._c1_terminal_ids=set();s._bars=[N()];s._c1_fill_epoch=0
    s._c1_current_money=lambda ns:dict(E=D(100),H=D(100),DD=D(0),source=9,receipt=11,epoch=0)
    s._c1_btc_postcut_d1_allowed=lambda *a:True;s._discard_queued_intents=lambda *a:None;s._c1_rights=lambda:{};s._c1_log=lambda *a,**kw:None
    s._domain=WaveOverlayState(Candidate());s._domain.episode=Episode('ep',-1,10000,1)
    s.cache=N(orders_open=lambda:[],orders_inflight=lambda:[],instrument=lambda iid:N(min_quantity=None,min_notional=None),
              account_for_venue=lambda v:N(last_event=N(ts_event=9)))
    calls=[];sent=[]
    s._sol_b_increase_qty=lambda q,side,ns:(calls.append(('budget',q)) or D(25))
    s._entries_enabled=lambda:True
    s._tier_allows_increase=lambda iid,side,q,ns:(calls.append(('native',q)) or True)
    def submit(i,*a,**kw):sent.append(i);s._pending_by_order['native']=i
    s._submit_intent=submit
    from nautilus_trader.model.objects import Price
    s._c1_quote(N(instrument_id=sol,ts_event=20,ask_price=Price.from_str('21'),bid_price=Price.from_str('21')),decision_ns=20)
    assert calls==[('budget',D(100)),('native',D(25))]
    assert sent[0].quantity==25 and t['restore_committed']==25 and t['credit']==100

@pytest.mark.parametrize('seed,cap',[('10000','30000000'),('81','243000'),('1234.56','3703680')])
def test_b_factory_scales_shared_ceiling_without_a_children(seed,cap):
    import ast
    from dataclasses import asdict
    from pathlib import Path
    from coinmaster.domain.wave_overlay import Candidate
    from coinmaster.research.effective_config import effective_research_candidate
    fn=next(n for n in ast.parse((Path(__file__).parents[1]/'coinmaster/research/native_baseline.py').read_text()).body
            if isinstance(n,ast.FunctionDef) and n.name=='run_native_diagnostic')
    statement=next(n for n in fn.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='candidate' for t in n.targets))
    env=dict(candidate=Candidate(),effective_research_candidate=effective_research_candidate,
             research_v0_selective_lifecycle_repairs=True,research_sol_capital_staging_a=False,
             research_sol_market_budget_b=True,initial_active_seed=D(seed))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[statement],type_ignores=[])),'actual_B_candidate_assignment','exec'),env)
    expected=asdict(effective_research_candidate(selective_lifecycle_repairs=True));expected['max_parent_notional']=float(D(cap))
    assert asdict(env['candidate'])==expected

def test_closed_d1_boundary_uses_decision_availability_not_old_money_source():
    from datetime import datetime,UTC,timedelta
    from types import MethodType
    from nautilus_trader.model.identifiers import InstrumentId
    at=datetime(2024,10,3,tzinfo=UTC);ns=int(at.timestamp()*1_000_000_000)
    source=ns-60_000_000_000;btc=InstrumentId.from_str('BTC.TEST')
    s=gate();s.config.btc_id=btc;s.config.max_mark_age_ns=120_000_000_000;s._sol_b_armed=False
    s._c1_fill_epoch=7;s._last_accepted_session=ns
    s._bars=[N(available_at=at)];s._sol_b_atr=[N(valid=True,ns=ns,atr=D(1))]*2
    c=dict(source=source,receipt=ns,epoch=7,positions={},account_identity=('source-account',source))
    s._sol_b_snapshot=c
    event=N(id='source-account',ts_event=source)
    s.cache=N(account_for_venue=lambda v:N(last_event=event),positions_open=lambda:[])
    s._sol_b_current=MethodType(SolMarketBudgetResearch._sol_b_current,s)
    assert s._sol_b_current(ns) is c
    assert s._sol_b_increase_qty(D(8),1,ns)==8
    # The same D1 becomes ineligible if its actual availability is later.
    s._bars=[N(available_at=at+timedelta(seconds=1))]
    assert s._sol_b_increase_qty(D(8),1,ns)==0
    assert s._sol_b_increase_qty(D(8),1,ns+1_000_000_000)==8
    # A new publication at the SAME source timestamp invalidates the receipt.
    event.id='funding-commit'
    assert s._sol_b_increase_qty(D(8),1,ns+1_000_000_000)==0
