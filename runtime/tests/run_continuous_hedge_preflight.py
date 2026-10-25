"""One counted connected engineering pass. NEVER collect an old native suite.

Each BacktestEngine construction claims its ledger entry before construction.
Explicitly synthetic native quote fixtures; no candidate ROI or economic replay.
"""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import argparse,json,hashlib,os,sys,traceback
sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_native_market_redesign as md
import test_native_paired_prefix as pair
from test_native_episode_risk import NativeProbe,tick,run_ticks,marks
from test_native_split_cover import cfg
from test_native_btc_sizing import prepare_day
from coinmaster.domain.wave_overlay import Candidate,Episode
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP,SIM,perpetual
from coinmaster.research.qualified_warmup import load_qualified_feed
from coinmaster.research.registered_control import config_for,build_registered_control_kwargs,native_kwargs_json_roundtrip
from nautilus_trader.backtest.engine import BacktestEngine as NativeEngine
from nautilus_trader.backtest.config import BacktestEngineConfig
from nautilus_trader.config import LoggingConfig
from nautilus_trader.model.enums import AccountType,OmsType
from nautilus_trader.model.objects import Money
M=60000000000
CASES=[('F01_R2_PARTIAL_NOCHASE_TERMINAL','R2',1,86400*10**9+10),('F02_R3_PARTIAL_NOCHASE_TERMINAL','R3',1,86400*10**9+10),('F03_R2_SECOND_FILL_THREE_TP','R2',1,20),('F04_R3_SECOND_FILL_THREE_TP','R3',1,20),('F05_QUALIFIED_CLOCK_ALL_PATHS','R2',1725249599999999990,1725249720000000100),('F06_MISSING_FEATURE_FAIL_CLOSED','R2',1725249599999999990,1725249720000000100),('F07_COPRIME_CORRIDOR_REGRESSION','R3',1,2*M),('F08_LATE_NATIVE_ENTRY_OWNERSHIP','R3',1,2*M)]

class Recorder:
    def __init__(self,path,gate):self.path=Path(path);self.gate=gate;self.current=None;self.engines=[]
    def write(self,data):
        p=self.path.with_suffix('.json.tmp');p.write_text(json.dumps(data,indent=2)+'\n');os.replace(p,self.path)
    def claim(self):
        data=json.loads(self.path.read_text())
        if data['physical_started']>=12 or data['status'] not in ('READY_REVIEWED','RUNNING') or self.current is None:raise ValueError('ENGINE_BUDGET_OR_GATE_INVALID')
        if any(x['status']=='STARTED' for x in data['attempts']):raise ValueError('CONCURRENT_ENGINE_FORBIDDEN')
        case=self.current
        entry=dict(fixture_id=case[0],family=case[1],window_start_ns=case[2],window_end_ns=case[3],physical_index=data['physical_started']+1,status='STARTED',started_utc=datetime.now(timezone.utc).isoformat(),source_commit=self.gate['source_commit'],config_sha256=self.gate['config_pins'][case[1]],new_feed_sha256=self.gate['new_feed_sha256'],engine='1.231.0',cleanup='PENDING')
        data['attempts'].append(entry);data['physical_started']+=1;data['status']='RUNNING';self.write(data)
        return entry['physical_index']
    def finish(self,number,status,detail):
        data=json.loads(self.path.read_text());entry=next(a for a in data['attempts'] if a['physical_index']==number)
        entry.update(status=status,finished_utc=datetime.now(timezone.utc).isoformat(),**detail);self.write(data)
REC=None
class CountedEngine:
    def __init__(self,*args,**kwargs):
        self.number=REC.claim();self.disposed=False;self.times=[];REC.engines.append(self)
        try:self.native=NativeEngine(*args,**kwargs)
        except BaseException as error:
            REC.finish(self.number,'FAILED',dict(process_rc=1,result=str(error),cleanup='CONSTRUCTOR_FAILED'));raise
    def __getattr__(self,name):return getattr(self.native,name)
    def add_data(self,data,*args,**kwargs):
        for row in data:
            t=row.ts_event
            if not REC.current[2]<=t<=REC.current[3]:raise ValueError('FIXTURE_WINDOW_EXCEEDED')
            self.times.append(t)
        return self.native.add_data(data,*args,**kwargs)
    def dispose(self):
        self.native.dispose();self.disposed=True

# Every helper engine constructor used by the explicit cases routes here.
pair.BacktestEngine=CountedEngine

def base_engine(strategy):
    e=CountedEngine(BacktestEngineConfig(logging=LoggingConfig(log_level='ERROR')))
    e.add_venue(venue=SIM,oms_type=OmsType.NETTING,account_type=AccountType.MARGIN,starting_balances=[Money(10000,BTC_PERP.quote_currency)],base_currency=BTC_PERP.quote_currency,default_leverage=D(1),liquidity_consumption=True,bar_execution=False)
    for inst in (BTC_PERP,SOL_PERP):e.add_instrument(perpetual(inst.raw_symbol.value,inst.base_currency,str(inst.price_increment),str(inst.size_increment),str(inst.margin_init),maker_fee=D('.00020'),taker_fee=D('.00055')))
    e.add_strategy(strategy);return e
md.native_engine=base_engine

def probe(family,paired=False):
    class ControlProbe(NativeProbe):
        def __init__(self,config):
            self.native_fills=[]
            super().__init__(config.__replace__(research_btc_q_mode='LEGACY_Q_CONTROL' if family=='R2' else 'CLEAN_Q',research_paired_prefix='B2_F0' if paired else None))
        def on_order_filled(self,event):self.native_fills.append(event);return super().on_order_filled(event)
    return ControlProbe

def settled_identity(s,e):
    assert not e.cache.positions_open() and not e.cache.orders_open() and not e.cache.orders_inflight()
    assert all(event.commission.currency==BTC_PERP.quote_currency for event in s.native_fills)
    fees=sum((x.commission.as_decimal() for x in s.native_fills),D(0))
    signed=sum(((-1 if x.order_side.name=='BUY' else 1)*x.last_qty.as_decimal()*x.last_px.as_decimal() for x in s.native_fills),D(0))
    cash=e.cache.account_for_venue(SIM).balance_total().as_decimal()
    assert abs(cash-(D(10000)+signed-fees))<=D('.00000002')
    assert s.terminal_lifecycle['status']=='FLAT'
    return dict(native_terminal_cash=str(cash),native_commissions=str(fees),signed_execution_cash=str(signed),native_fill_count=len(s.native_fills),orders_open=0,inflight=0,positions_open=0,account_identity='PASS')

def control_case(family,partial):
    s,e,ep=md.setup(probe=probe(family))
    try:
        run_ticks(e,[tick(BTC_PERP,3,size='10' if partial else '1000'),tick(BTC_PERP,4)])
        targets=[o for o in e.cache.orders_open() if o.is_reduce_only];second=[o for o in e.cache.orders_open() if not o.is_reduce_only]
        assert len(targets)==3 and all(o.status.name=='ACCEPTED' for o in targets)
        assert sum((o.leaves_qty.as_decimal() for o in targets),D(0))==D(10 if partial else 50)
        assert len(second)==1 and second[0].order_type.name=='LIMIT' and second[0].price.as_decimal()==D('99.5')
        if partial:
            run_ticks(e,[tick(BTC_PERP,86400*10**9+5)])
            assert len([o for o in e.cache.orders() if not o.is_reduce_only])==2
            assert not s._split_parent['fallback'] and s._split_parent['filled']==D(10)
            end=86400*10**9+6
        else:
            run_ticks(e,[tick(BTC_PERP,5,'99'),tick(BTC_PERP,6,'99')])
            assert ep.btc_initial_qty==100 and ep.btc_planref_vwap==D(100)
            targets=[o for o in e.cache.orders_open() if o.is_reduce_only]
            assert len(targets)==3 and sum((o.leaves_qty.as_decimal() for o in targets),D(0))==100
            run_ticks(e,[tick(BTC_PERP,7,'103'),tick(BTC_PERP,8,'103')])
            assert not e.cache.positions_open();assert {0,1,2}<=ep.btc_filled_tps
            end=9
        s._begin_forced_close('TERMINAL_BOUNDARY_SETTLEMENT');run_ticks(e,[tick(BTC_PERP,end)])
        result=settled_identity(s,e);result.update(real_three_tp=True,second_limit_only=True,partial_first=partial)
        return result
    finally:e.end();e.dispose()

def qualified_case(feed,missing=False):
    from dataclasses import replace
    row=feed[0];t=row.decision_ns
    assert t==1725249600000000000 and row.atr_sol==D('3.6889752782254411326488158384814894977173533826523')
    selected=replace(row,valid=False) if missing else row
    config=cfg(True,research_btc_real_u=True,research_btc_q_mode='LEGACY_Q_CONTROL',research_sol_off=True,research_btc_split_planref_v1=True,research_btc_split_tp_ioc=True,research_btc_split_discount=D('.005'))
    config=config.__replace__(candidate=Candidate(sol_overlay_enabled=False,btc_tp_fractions_initial_qty=(.2125,.2125,.575)),research_paired_signal_rows=(selected,))
    s=probe('R2',paired=True)(config);e=base_engine(s)
    bp=str(row.btc_close);sp=str(row.sol_close)
    try:
        run_ticks(e,[tick(BTC_PERP,t-10,bp),tick(SOL_PERP,t-10,sp)])
        prepare_day(s,t-9);marks(s,t-9,btc=bp,sol=sp)
        ep=s._domain.episode=Episode('qualified-clock',-1,10000,1,wave_levels=(0,0,.03),h=10000)
        intent=s._domain._intent(ep,'BTC_ENTRY',-1,None,quantity=.02)
        s._submit_intent(intent,float(bp),float(sp),.01,0,ts_now=t-9)
        run_ticks(e,[tick(BTC_PERP,t-8,bp),tick(BTC_PERP,t-7,bp),tick(SOL_PERP,t-6,sp),tick(BTC_PERP,t,bp),tick(SOL_PERP,t,sp)])
        if missing:
            for dt in (1,2,3):run_ticks(e,[tick(BTC_PERP,t+dt,bp),tick(SOL_PERP,t+dt,sp)])
            assert 'UNHEDGEABLE_UNAVAILABLE_CAUSAL_FEATURE' in s._pair_failures
            assert not any(x['kind']=='ENTRY' for x in s._pair_orders.values())
            assert not e.cache.positions_open() and not e.cache.orders_open() and not e.cache.orders_inflight()
            return dict(missing_feature='NO_ADMISSION_NATIVE_FLAT',hedge_entries=0)
        assert s._pair is not None and s._pair['atr']==row.atr_sol
        run_ticks(e,[tick(BTC_PERP,t+M-1,bp),tick(SOL_PERP,t+M-1,sp)])
        assert not any(x['event']=='SUBMIT' for x in s.paired_prefix_audit)
        for dt in range(6):run_ticks(e,[tick(BTC_PERP,t+M+dt,bp),tick(SOL_PERP,t+M+dt,sp)])
        submissions=[x for x in s.paired_prefix_audit if x['event']=='SUBMIT']
        assert any(x['kind']=='ENTRY' for x in submissions)
        assert any(x['kind']=='TP' for x in submissions) and any(x['kind']=='STOP' for x in submissions)
        assert all(int(x['timestamp_ns'])>=t+M for x in submissions)
        assert not s._pair_failures,s._pair_report()
        s._begin_forced_close('TERMINAL_BOUNDARY_SETTLEMENT')
        for dt in range(6,12):run_ticks(e,[tick(BTC_PERP,t+M+dt,bp),tick(SOL_PERP,t+M+dt,sp)])
        result=settled_identity(s,e);result.update(qualified_atr=str(row.atr_sol),all_hedge_submissions_not_before_ns=t+M,hedge_order_kinds=sorted(set(x['kind'] for x in submissions)))
        return result
    finally:e.end();e.dispose()

def main():
    global REC
    parser=argparse.ArgumentParser();parser.add_argument('--ledger',required=True);parser.add_argument('--gate',required=True)
    args=parser.parse_args();gate=json.loads(Path(args.gate).read_text())
    if gate.get('independent_review')!='PASS' or gate.get('root_go') is not True:raise ValueError('INDEPENDENT_REVIEW_AND_ROOT_GO_REQUIRED')
    import nautilus_trader
    if nautilus_trader.__version__!='1.231.0':raise ValueError('EXACT_NATIVE_VERSION_REQUIRED')
    feed=load_qualified_feed(gate['new_feed_path'],gate['new_feed_sha256'],1725249600000000000,1725264000000000000)
    for family in ('R2','R3'):
        kw=build_registered_control_kwargs(config_for(family),family,Path(gate['data_root']),Path(args.ledger).parent,feed,1725249600000,1725264000000)
        _,restored=native_kwargs_json_roundtrip(kw)
        assert restored==kw
    REC=Recorder(args.ledger,gate)
    actions=[lambda:control_case('R2',True),lambda:control_case('R3',True),lambda:control_case('R2',False),lambda:control_case('R3',False),lambda:qualified_case(feed),lambda:qualified_case(feed,True),lambda:pair.test_native_coprime_actual_1037_1817_single_tp_stable_corridor(1,False),pair.test_native_late_entry_after_btc_flat_cancel_request_never_recreates_btc]
    for case,action in zip(CASES,actions):
        REC.current=case;before=len(REC.engines)
        try:
            result=action();created=REC.engines[before:]
            assert len(created)==1 and created[0].disposed
            e=created[0]
            REC.finish(e.number,'COMPLETED',dict(process_rc=0,result=result or {'assertions':'PASS'},cleanup='END_AND_DISPOSE_CONFIRMED',actual_tick_start_ns=min(e.times),actual_tick_end_ns=max(e.times)))
            print(json.dumps(dict(fixture=case[0],status='PASS',physical_index=e.number)),flush=True)
        except BaseException as error:
            for e in REC.engines[before:]:
                data=json.loads(Path(args.ledger).read_text());entry=next(x for x in data['attempts'] if x['physical_index']==e.number)
                if entry['status']=='STARTED':REC.finish(e.number,'FAILED',dict(process_rc=1,result=type(error).__name__+': '+str(error),cleanup='DISPOSE_CONFIRMED' if e.disposed else 'UNKNOWN'))
            traceback.print_exc();raise
    data=json.loads(Path(args.ledger).read_text());data['status']='CONNECTED_PASS_REVIEW_REQUIRED';REC.write(data)
if __name__=='__main__':main()
