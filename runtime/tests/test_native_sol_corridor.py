"""Bounded native corridor integration; no historical/economic replay."""
from decimal import Decimal as D
import json
import pytest
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
from coinmaster.strategy.risk_first_sol import SolRiskFirstResearch
from coinmaster.domain.wave_overlay import Episode,DailyBar,Features
from datetime import datetime,UTC,timedelta
from nautilus_trader.model.enums import OrderSide,TimeInForce
from test_native_alpha_cushion import config
from test_native_sol_risk_first import engine
from test_native_btc_sizing import prepare_day
from test_native_alpha_cushion import setup as alpha_setup,history,advance,original,close
from test_native_alpha_cushion import Observed as AlphaObserved
from test_native_episode_risk import NativeProbe,tick,run_ticks,marks

class Observed(AlphaObserved):
    def __init__(self,c):
        super().__init__(c.__replace__(research_alpha_cushion=False,research_sol_risk_first='alpha-corridor-v1'))
    def on_quote_tick(self,q):
        self._corridor_finalize_checkpoint(q.ts_event)
        NativeProbe.on_quote_tick(self,q)
        for name,iid in (('btc_action',BTC_PERP.id),('sol_action',SOL_PERP.id)):
            action=getattr(self,name,None)
            if action is not None and q.instrument_id==iid:
                setattr(self,name,None);action(q)
        if q.instrument_id==SOL_PERP.id and all(i in self._latest_marks for i in (BTC_PERP.id,SOL_PERP.id)):
            self._corridor_queue_checkpoint(q.ts_event)

def setup(side=1,probe=Observed):return alpha_setup(side,probe=probe)
def last(s,known=True):return [x for x in s.risk_first_sol_audit if x['event']=='CORRIDOR_BUDGET' and (not known or 'target' in x)][-1]
def stress(s,a='.5',u='0',beta='2'):
    f=dict(beta=D(beta),a=D(a),u=D(u),closed=0)
    s._corridor_estimate=lambda ts:f
    return f

def test_convex_interval_pending_BTC_kink_and_infeasibility():
    solve=SolRiskFirstResearch._corridor_interval
    loss=lambda q:max(abs(D(10)-q),abs(D(20)-q))
    interval,best=solve(loss,[D(0),D(10),D(15),D(20),D(50)],D(6))
    assert interval==(D(14),D(16)) and best==15
    assert solve(loss,[D(0),D(10),D(15),D(20),D(50)],D(4))[0] is None

@pytest.mark.parametrize('side',[1,-1])
def test_native_healthy_alpha_and_completed_account_peak(side):
    s,e,ep=setup(side)
    try:
        original(s,e,ep,20,ts=30);advance(s,e,31);advance(s,e,32)
        assert ep.sol_qty==20
        assert s._rf_equity[0]==s._v3_equity()
        peak=s._rf_peak
        close(s,e)
        assert s._rf_peak>=peak and s._rf_peak>=10000
        assert last(s)['status']=='FEASIBLE'
    finally:e.end();e.dispose()

@pytest.mark.parametrize('side',[1,-1])
def test_native_BTC_only_hedge_and_known_residual_failure(side):
    s,e,ep=setup(side)
    try:
        f=stress(s);advance(s,e,20);advance(s,e,21)
        assert any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
        assert D(last(s)['target'])>0 and ep.sol_qty==0
        f.update(u=D(1));advance(s,e,22)
        assert last(s)['status']=='SOL_RISK_INFEASIBLE'
        assert s._rf_equity[0]-D('.55')*s._rf_peak==D(last(s)['C']) or s._rf_equity[1]>int(last(s)['timestamp_ns'])
    finally:e.end();e.dispose()

def test_native_excess_alpha_trim_preserves_actual_fill_rights():
    s,e,ep=setup()
    try:
        original(s,e,ep,200,ts=30);advance(s,e,31)
        before=dict(ep.sol_add_filled_notional);stress(s,a='1',u='.1')
        advance(s,e,32);advance(s,e,33)
        assert D(last(s)['target'])<200
        assert ep.sol_add_filled_notional==before
        assert last(s)['status'] in {'FEASIBLE','SOL_RISK_INFEASIBLE'}
    finally:e.end();e.dispose()

def test_native_SOL_only_budget_keeps_lawful_alpha_and_no_flat_entry():
    s,e,ep=setup()
    try:
        original(s,e,ep,20,ts=30);advance(s,e,31)
        i=s._domain._intent(ep,'BTC_REDUCE',-ep.side,None,quantity=100)
        s._submit_intent(i,100,100,None,len(s._bars)-1,ts_now=32)
        advance(s,e,32);advance(s,e,33)
        assert not any(p.instrument_id==BTC_PERP.id for p in e.cache.positions_open())
        assert ep.sol_qty==20 and D(last(s)['target'])==20
        stress(s,a='5');advance(s,e,34);advance(s,e,35)
        assert D(last(s)['target'])<20
    finally:e.end();e.dispose()

def test_native_unknown_ACK_serializes_and_Daily90_SOLonly_refresh():
    s,e,ep=setup()
    try:
        first=s._corridor_estimate(10);assert abs(first['beta']-2)<D('1e-12')
        i=s._domain._intent(ep,'SOL_ADD',-ep.side,None,quantity=1)
        s._pending_by_order['missing-native-ack']=i
        advance(s,e,20);assert last(s,False)['status']=='DATA_UNKNOWN'
        assert not any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
        del s._pending_by_order['missing-native-ack']
        # Risk estimator is not initialized/frozen by a BTC entry.
        s._rf_daily=None;s._domain.episode=Episode('sol-only',1,10000,1,h=10000)
        assert s._corridor_estimate(21)['closed']==0
    finally:e.end();e.dispose()

def test_native_Q2_hypothetical_endpoint_and_original_reserve():
    s,e,ep=setup()
    try:
        from nautilus_trader.model.enums import OrderSide,TimeInForce
        i=s._domain._intent(ep,'BTC_ENTRY',ep.side,None,quantity=10)
        o=s.order_factory.market(instrument_id=BTC_PERP.id,order_side=OrderSide.BUY,quantity=BTC_PERP.make_qty(10),time_in_force=TimeInForce.IOC)
        e.cache.add_order(o);s._pending_by_order[str(o.client_order_id)]=i
        actual,lo,hi,unknown=s._corridor_btc_endpoints(e.cache.positions_open()[0],20)
        assert hi==actual+10 and lo==actual and not unknown
        s._pending_by_order.pop(str(o.client_order_id))
        p=s._split_parent;p.update(closed=False,quantity=D(100),filled=D(50),cancelled=D(0))
        assert s._split_cover_margin_reserve(BTC_PERP.id,D(50),20)==100
    finally:e.end();e.dispose()

def test_negative_C_not_clamped_and_invalid_risk_unknown():
    s,e,ep=setup()
    try:
        s._rf_peak=D(100000);advance(s,e,20)
        assert D(last(s)['C'])<0 and last(s)['status']=='SOL_RISK_INFEASIBLE'
        s._corridor_estimate=lambda ts:None;advance(s,e,21)
        assert last(s,False)['status']=='DATA_UNKNOWN'
    finally:e.end();e.dispose()


def test_healthy_original_native_partial_half_full_two_episode_OFF_ON_parity():
    outputs=[]
    for enabled in (False,True):
        s=Observed(config(enabled)) if enabled else AlphaObserved(config(False));e=engine(s,bar_execution=not enabled)
        try:
            run_ticks(e,[tick(BTC_PERP,1),tick(SOL_PERP,1)])
            snapshots=[]
            for cycle in range(2):
                minute=60_000_000_000;t=cycle*1000*minute+2;prepare_day(s,t);history(s);marks(s,t,'100','1')
                ep=s._domain.episode=Episode('healthy-'+str(cycle),1,10000,1,wave_levels=(10,20,30),h=10000)
                i=s._domain._intent(ep,'BTC_ENTRY',1,None,quantity=100)
                s.btc_action=lambda q:s._submit_intent(i,100,100,.01,0,ts_now=q.ts_event)
                run_ticks(e,[tick(BTC_PERP,t+1),tick(BTC_PERP,t+2),tick(BTC_PERP,t+3,'99'),tick(SOL_PERP,t+4,'1')])
                for k,q in enumerate([3505,2505,1505,505]):
                    now=t+(10+k*10)*minute;marks(s,now,'100','1');original(s,e,ep,q,now,price='1');advance(s,e,now+minute,sol='1')
                    snapshots.append((ep.sol_qty,ep.sol_first_fill_at,ep.sol_first_owned_at,ep.fixed_sigma,dict(ep.sol_add_filled_notional)))
                    assert not any(i.action=='SOL_ADD' for i in s._pending_by_order.values())
                for half,z in [(True,.3),(False,0.)]:
                    now=t+(60 if half else 80)*minute;s._domain._decision_index=100+now
                    when=datetime.fromtimestamp(now/1e9,UTC);b=DailyBar(when-timedelta(days=1),when,when,100,100,1)
                    intents=s._domain._sol_exits(ep,Features(100+now,1,1.,1.,0.,1.,0.),b,100+now,z=z);assert len(intents)==1
                    logical=intents[0]
                    s.sol_action=lambda q:s._submit_intent(logical,1,1,None,100+now,ts_now=q.ts_event)
                    for dt in range(3):advance(s,e,now+dt*minute,sol='1')
                assert ep.sol_qty==0
                s.btc_action=lambda q:s._begin_forced_close('REGIME')
                for dt in range(4):advance(s,e,t+(90+dt)*minute,sol='1')
                assert not e.cache.positions_open() and s._domain.episode is None and not s._pending_by_order
            fills=[{k:x[k] for k in ('fill_ns','instrument','px','qty','commission','native_liquidity_side','order_type','post_only')} for x in s.fill_audit]
            native_orders=getattr(s,"_test_full_native_orders",lambda:e.cache.orders())()
            orders=[(str(o.quantity),str(o.filled_qty),int(o.order_type),int(o.time_in_force),o.is_post_only,o.is_reduce_only,int(o.status),o.ts_init,o.ts_last) for o in native_orders]
            cash=e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal();fees=sum(D(x['commission']) for x in s.fill_audit)
            flow=sum(o.filled_qty.as_decimal()*D(str(o.avg_px))*(1 if o.side==OrderSide.SELL else -1) for o in native_orders if o.filled_qty.as_decimal()>0)
            assert cash==D(10000)+flow-fees
            outputs.append((fills,orders,cash,fees,snapshots))
        finally:e.end();e.dispose()
    first_fill=next(((a,b) for a,b in zip(outputs[0][0],outputs[1][0]) if a!=b),None)
    print(json.dumps(dict(first_fill=first_fill,first_order=next(((a,b) for a,b in zip(outputs[0][1],outputs[1][1]) if a!=b),None)),default=str))
    assert outputs[0]==outputs[1], dict(first_fill=first_fill,fill_counts=[len(x[0]) for x in outputs],cash=[str(x[2]) for x in outputs],first_order=next(((a,b) for a,b in zip(outputs[0][1],outputs[1][1]) if a!=b),None))


def test_actual_native_RiskEngine_throttle_Denied_retains_forced_residual_then_next_quote_flat():
    class Throttle(Observed):
        denials=None
        def on_order_denied(self,event):
            if self.denials is None:self.denials=[]
            self.denials.append(event);assert len(self.denials)==1
            super().on_order_denied(event)
    s=Throttle(config());e=engine(s,rate='2/00:00:01')
    try:
        run_ticks(e,[tick(SOL_PERP,1)])
        s._domain.episode=Episode('alpha-native-denied',1,10000,1)
        marks(s,1)
        s.submit_order(s.order_factory.market(SOL_PERP.id,OrderSide.BUY,SOL_PERP.make_qty(D(1)),time_in_force=TimeInForce.IOC))
        run_ticks(e,[tick(SOL_PERP,2)])
        assert e.cache.positions_open()[0].quantity.as_decimal()==1
        s._begin_forced_close('REGIME')
        run_ticks(e,[tick(SOL_PERP,3,size='.4')])
        assert len(s.denials)==1 and e.cache.order(s.denials[0].client_order_id).status.name=='DENIED'
        assert e.cache.positions_open()[0].quantity.as_decimal()==D('.6')
        assert s._rf_last_fill_ns==3 and s._rf_dirty
        checkpoint=s._rf_equity
        s._corridor_finalize_checkpoint(3)
        assert s._rf_equity==checkpoint and s._rf_dirty
        run_ticks(e,[tick(SOL_PERP,2_000_000_003)])
        assert len(s.denials)==1 and not e.cache.positions_open() and not e.cache.orders_open()
        assert not s._pending_by_order and s._domain.episode is None
        account=e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()
        fees=sum(o.commissions()[0].as_decimal() for o in e.cache.orders() if o.commissions())
        assert account==D(10000)-fees
    finally:e.end();e.dispose()


def test_hysteresis_requires_new_reverse_and_does_not_spend_required_hedge():
    s,e,ep=setup()
    try:
        f=stress(s);advance(s,e,20);advance(s,e,21)
        held=next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)
        f['a']=D('.45')
        advance(s,e,22);assert D(last(s)['target'])==held
        s._rf_reverse=(23,23);advance(s,e,24)
        assert D(last(s)['target'])==held  # alpha0 exceeds .8C; protection still useful.
        f['a']=D('.1');s._rf_reverse=(25,25);advance(s,e,26);advance(s,e,27)
        assert not any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
    finally:e.end();e.dispose()

def test_dirty_fill_never_uses_provisional_account_and_global_peak_no_reset():
    s,e,ep=setup()
    try:
        peak=s._rf_peak;s._rf_dirty=True;s._rf_last_fill_ns=20;advance(s,e,20)
        assert last(s,False)['status']=='DATA_UNKNOWN'
        advance(s,e,21)
        assert not s._rf_dirty and s._rf_equity[0]==s._v3_equity()
        s._conditional=None
        assert s._rf_peak>=peak
    finally:e.end();e.dispose()

def test_tiny_runner_raw_native_survives_boundary_metadata_assertion(tmp_path,monkeypatch):
    from test_native_baseline import write_streaming_fixture
    from coinmaster.research import native_baseline as nb
    from coinmaster.domain.wave_overlay import Candidate
    start,end=write_streaming_fixture(tmp_path,trading_days=1)
    def fail(result):raise ValueError('INJECTED_PACKAGING_METADATA')
    monkeypatch.setattr(nb,'assert_report_boundaries',fail)
    with pytest.raises(ValueError,match='INJECTED_PACKAGING_METADATA'):
        nb.run_native_diagnostic(tmp_path,candidate=Candidate(),trading_start_ms=start,trading_end_ms=start+2*nb.MINUTE_MS,warmup_start_ms=0,artifact_dir=tmp_path/'raw',artifact_label='fault')
    raw=json.loads((tmp_path/'raw/fault-raw-native.json').read_text())
    assert raw['raw_audit_state']=='NATIVE_COMPLETE_PACKAGING_NOT_VALIDATED'
    assert 'native_order_events' in raw and 'native_carry_counts' in raw
    for info in raw['execution_artifacts'].values():
        from pathlib import Path
        assert Path(info['path']).exists()

def test_BTC_flat_pure_protection_exits_even_with_unknown_risk():
    s,e,ep=setup()
    try:
        stress(s);advance(s,e,20);advance(s,e,21)
        assert ep.sol_qty==0 and any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
        s._corridor_estimate=lambda ts:None
        i=s._domain._intent(ep,'BTC_REDUCE',-ep.side,None,quantity=100)
        s._submit_intent(i,100,100,None,90,ts_now=30)
        advance(s,e,30);advance(s,e,31);advance(s,e,32)
        assert not e.cache.positions_open()
    finally:e.end();e.dispose()

def test_healthy_protection_does_not_release_only_because_L_decreases():
    s,e,ep=setup()
    try:
        f=stress(s);advance(s,e,20);advance(s,e,21)
        held=next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)
        f['a']=D('.01');advance(s,e,22);advance(s,e,23)
        assert D(last(s)['target'])==held
        s._rf_reverse=(24,24);advance(s,e,25);advance(s,e,26)
        assert not any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
    finally:e.end();e.dispose()

def test_nonpositive_daily_prices_are_DATA_UNKNOWN():
    s,e,ep=setup()
    try:
        from dataclasses import replace
        from types import SimpleNamespace
        s._bars=[SimpleNamespace(**{**b.__dict__,"btc_close":-b.btc_close,"sol_close":-b.sol_close}) for b in s._bars]
        s._rf_daily=None
        assert s._corridor_estimate(20) is None
    finally:e.end();e.dispose()

def test_real_production_tiny_corridor_and_raw_identity(tmp_path):
    from test_native_baseline import write_streaming_fixture
    from coinmaster.research.native_baseline import run_native_diagnostic,TRADING_START_MS,MINUTE_MS
    from coinmaster.domain.wave_overlay import Candidate
    import pyarrow as pa
    import pyarrow.parquet as pq
    start,end=write_streaming_fixture(tmp_path,trading_days=1);shift=TRADING_START_MS-start
    for path in (tmp_path/'normalized').glob('*.parquet'):
        rows=pq.read_table(path).to_pylist()
        for row in rows:row['open_time_ms']+=shift
        pq.write_table(pa.Table.from_pylist(rows),path)
    result=run_native_diagnostic(tmp_path,candidate=Candidate(btc_notional_multiplier=7.875,max_parent_notional=30_000_000),trading_start_ms=TRADING_START_MS,trading_end_ms=TRADING_START_MS+2*MINUTE_MS,warmup_start_ms=shift,
        research_v0_execution_repairs=True,research_v0_deferred_selective_zero_tp=True,research_v0_selective_lifecycle_repairs=True,research_btc_direction_sizing=True,research_btc_split50=True,research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,
        research_sol_risk_first="alpha-corridor-v1",observe_minute_risk=True,artifact_dir=tmp_path/'production')
    assert result['config']['research_sol_risk_first']=='alpha-corridor-v1' and result['config']['candidate']['sol_overlay_enabled']
    assert result['risk_first_sol_audit']['schema']=='coinmaster.native-audit.sqlite.v1' and 'risk_first_sol' in result['source_hashes']
    assert result['minute_risk_observations']['curves']['pre_quote_paired_close']['samples']==3
    json.dumps(result)

    raw=json.loads(next((tmp_path/'production').glob('*-raw-native.json')).read_text())
    assert raw['raw_audit_state']=='NATIVE_COMPLETE_BEFORE_WRAPPER_METADATA'
    assert 'native_order_events' in raw and 'native_carry_counts' in raw
    assert raw['terminal_total']==result['terminal_total']

def test_final_receipt_strictly_after_fill_and_never_backdated():
    s,e,ep=setup()
    try:
        stress(s);advance(s,e,20)
        # Fill callback made state dirty after the strategy quote wrapper returned.
        epoch=s._rf_fill_epoch;assert s._rf_dirty and s._rf_last_fill_ns==20
        previous=s._rf_equity
        s._corridor_finalize_checkpoint(20)
        assert s._rf_equity==previous and s._rf_dirty
        advance(s,e,22)
        r=s._rf_final_receipt
        assert r['receipt_ns']>r['source_quote_ns'] and r['receipt_ns']==22
        assert r['final_fill_epoch']>=epoch
        assert s._rf_equity[1]==r['receipt_ns'] and r['source_quote_ns']==20
        assert s._rf_equity[0]==s._v3_equity()
        assert sum(D(x['commission']) for x in s.fill_audit)>0
    finally:e.end();e.dispose()

def test_outer_wrapper_metadata_failure_keeps_real_native_raw(tmp_path,monkeypatch):
    import hashlib
    from dataclasses import asdict
    from pathlib import Path
    from test_native_baseline import write_streaming_fixture
    from coinmaster.research import native_baseline as nb
    from coinmaster.domain.wave_overlay import Candidate
    start,end=write_streaming_fixture(tmp_path,trading_days=1)
    policy=nb.ExecutionPolicy();fees=nb.FixedBaseFeePolicy()
    manifest=tmp_path/'bybit-1m/manifest.json'
    config={**nb.BASELINE_CONFIG,'candidate':asdict(Candidate()),'execution_policy':asdict(policy),'fixed_base_fee_policy':asdict(fees),'fee_policy_hash':fees.hash,'tp_fee_floor_v1':False,
        'run_interval':{'start':datetime.fromtimestamp(nb.TRADING_START_MS/1000,UTC).isoformat(),'end_exclusive':datetime.fromtimestamp(nb.TRADING_END_MS/1000,UTC).isoformat(),'initial_active_seed':'10000'}}
    control={'status':'NOT_FAITHFUL_DIAGNOSTIC','config':config,'policy':asdict(policy),'summary':{'terminal_total':'3386491.65211338'},'data_hash':hashlib.sha256(json.dumps(json.loads(manifest.read_text()),sort_keys=True,separators=(',',':')).encode()).hexdigest()}
    cp=tmp_path/'wrapper-control.json';cp.write_text(json.dumps(control))
    real_run=nb.run_native_diagnostic;real_sha=nb.sha256_file
    def bounded(*args,**kw):
        kw.update(trading_start_ms=start,trading_end_ms=start+2*nb.MINUTE_MS,warmup_start_ms=0,include_funding=False)
        return real_run(*args,**kw)
    def fail_only_metadata(path):
        if Path(path)==cp:raise ValueError('OUTER_METADATA_FAILURE')
        return real_sha(path)
    monkeypatch.setattr(nb,'run_native_diagnostic',bounded)
    monkeypatch.setattr(nb,'sha256_file',fail_only_metadata)
    with pytest.raises(ValueError,match='OUTER_METADATA_FAILURE'):
        nb.run_research_v0_repairs_cli(tmp_path,tmp_path/'outer',cp)
    raw=json.loads(next((tmp_path/'outer').glob('*-raw-native.json')).read_text())
    assert raw['raw_audit_state']=='NATIVE_COMPLETE_BEFORE_WRAPPER_METADATA'
    assert 'native_order_events' in raw and 'native_carry_counts' in raw
    for info in raw['execution_artifacts'].values():assert Path(info['path']).exists()

def test_native_risk_cancel_latepartial_retires_only_unfilled_no_IOC_resurrection():
    class Delayed(Observed):
        delay=False;requests=None
        def cancel_order(self,o,*a,**kw):
            if self.delay and o.instrument_id==SOL_PERP.id:
                if self.requests is None:self.requests=[]
                self.requests.append(o.client_order_id);return
            return super().cancel_order(o,*a,**kw)
    s,e,ep=alpha_setup(probe=Delayed,qty=1)
    try:
        ep.sol_rights.add(0);ep.sol_right_fraction[0]=1
        logical=s._domain._intent(ep,'SOL_ADD',-1,0,quantity=.9,reason='SOL_ADD')
        c=s._conditional_state(10);c['adds']=[dict(intent=logical,remaining=D('.9'),sigma=.02,index=90,price=D(100))];c['original_target']=D('.9')
        physical=s._domain._intent(ep,'SOL_ADD',-1,None,quantity=.9,reason='CONDITIONAL_NET_ADD')
        c['original_attempts'][physical.id]=(logical.id,)
        o=s.order_factory.limit(SOL_PERP.id,OrderSide.SELL,SOL_PERP.make_qty(D('.9')),SOL_PERP.make_price(101),time_in_force=TimeInForce.GTC)
        s._pending_by_order[str(o.client_order_id)]=physical;s._sigma_by_order[str(o.client_order_id)]=.02;s._decision_index_by_order[str(o.client_order_id)]=90
        s.submit_order(o);run_ticks(e,[tick(SOL_PERP,10)])
        s.delay=True;stress(s,a='1',u='3');s._rf_peak=D(1000000)
        advance(s,e,21)
        assert s.requests and not ep.sol_risk_retired_notional and str(o.client_order_id) in s._pending_by_order
        run_ticks(e,[tick(SOL_PERP,22,'101',size='.3')])
        assert o.filled_qty.as_decimal()==D('.3') and o.leaves_qty.as_decimal()==D('.6')
        s.delay=False;s.cancel_order(o);advance(s,e,23)
        assert ep.sol_risk_retired_notional[0]==60
        assert ep.sol_add_filled_notional[0]==pytest.approx(30.3)
        assert logical.id not in ep.pending and not c['adds']
        before=len([x for x in s.fill_audit if x['instrument']==str(SOL_PERP.id) and x['side']=='SELL']) if s.fill_audit and 'side' in s.fill_audit[0] else None
        advance(s,e,24);advance(s,e,25)
        assert not any(i.action=='SOL_ADD' for i in s._pending_by_order.values())
        assert ep.sol_add_filled_notional[0]==pytest.approx(30.3)
    finally:e.end();e.dispose()

def test_mathematically_feasible_but_margin_insufficient_is_distinct():
    s,e,ep=setup()
    try:
        stress(s);s._alpha_margin=lambda target,held,ts:target<=held
        advance(s,e,20)
        assert last(s)['status']=='SOL_MARGIN_INSUFFICIENT'
        assert not any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
    finally:e.end();e.dispose()


def test_inner_headroom_only_on_breach_holds_marks_then_corrects_new_breach():
    s,e,ep=setup()
    try:
        f=stress(s);advance(s,e,20);advance(s,e,21)
        acquired=[x for x in s.risk_first_sol_audit if x['event']=='CORRIDOR_BUDGET' and x.get('inner_correction')]
        assert acquired and D(acquired[0]['L'])<=D('.8')*D(acquired[0]['C'])
        assert D(acquired[0]['held_L'])>D(acquired[0]['C'])
        held=next(p.quantity.as_decimal() for p in e.cache.positions_open() if p.instrument_id==SOL_PERP.id)
        count=len(e.cache.orders());advance(s,e,22,btc='100.01');advance(s,e,23,btc='100.02')
        assert len(e.cache.orders())==count and D(last(s)['target'])==held
        f['a']=D(1);advance(s,e,24);advance(s,e,25)
        assert len(e.cache.orders())>count
        corrected=[x for x in s.risk_first_sol_audit if x['event']=='CORRIDOR_BUDGET' and x.get('inner_correction')][-1]
        assert D(corrected['held_L'])>D(corrected['C']) and D(corrected['L'])<=D('.8')*D(corrected['C'])
    finally:e.end();e.dispose()


def test_positive_outer_feasible_inner_infeasible_keeps_outer_fallback():
    s,e,ep=setup()
    try:
        stress(s,u='.8');advance(s,e,20)
        row=last(s)
        assert row['status']=='FEASIBLE' and not row['inner_correction']
        assert D('.8')*D(row['C'])<D(row['L'])<=D(row['C'])
    finally:e.end();e.dispose()


def test_nonpositive_budget_never_uses_inner_and_preserves_infeasible_fallback():
    s,e,ep=setup()
    try:
        stress(s);s._rf_peak=D(100000);advance(s,e,20)
        row=last(s)
        assert D(row['C'])<0 and row['status']=='SOL_RISK_INFEASIBLE'
        assert not row['inner_correction']
    finally:e.end();e.dispose()


def test_inner_protection_partial_fills_preserve_fees_rights_and_mandatory_exit():
    s,e,ep=setup()
    try:
        stress(s);rights=dict(ep.sol_add_filled_notional)
        for ts in range(20,28):advance(s,e,ts,size='5')
        assert ep.sol_qty==0 and ep.sol_add_filled_notional==rights
        assert any(p.instrument_id==SOL_PERP.id for p in e.cache.positions_open())
        close(s,e,ts=40)
        orders=e.cache.orders()
        fees=sum((fee.as_decimal() for o in orders for fee in o.commissions()),D(0))
        flow=sum((o.filled_qty.as_decimal()*D(str(o.avg_px))*(1 if o.side==OrderSide.SELL else -1) for o in orders if o.filled_qty.as_decimal()>0),D(0))
        assert e.cache.account_for_venue(BTC_PERP.id.venue).balance_total().as_decimal()==D(10000)+flow-fees
        assert not s._pending_by_order and not e.cache.positions_open()
    finally:e.end();e.dispose()
