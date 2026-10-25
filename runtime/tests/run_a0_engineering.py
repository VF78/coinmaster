"""Finite six-instance A0 connected pass. Requires external root GO before any engine."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
from inspect import signature
import argparse,hashlib,json,subprocess,traceback
from unittest.mock import patch
import run_continuous_hedge_preflight as pre
from coinmaster.research.a0_family import build_a0_kwargs,validate_native_a0
from coinmaster.research.native_baseline import build_native_strategy_config,run_native_diagnostic
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP,SIM
from coinmaster.research.paired_signal_feed import PairedSignal
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from test_native_episode_risk import tick,run_ticks
from coinmaster.venues.marks import venue_mark
from nautilus_trader.model.identifiers import ClientId
M=60_000_000_000
CASES=['A02_PARTIAL_FIRST_CLOSED_CAP','A03_ORDINARY_TP_KILLS','A04_CANCEL_RACE_LATE_FILL','A05_CROSS_MARGIN_UNKNOWN','A06_C0_NO_RELEASE']

class Recorder(pre.Recorder):
    def claim(self):
        data=json.loads(self.path.read_text())
        if not self.gate.get('root_go') or data['physical_started']>=6:
            raise ValueError('A0_GATE_OR_SIX_ENGINE_CAP')
        return super().claim()

class CountedEngine(pre.CountedEngine):
    def capture(self,label):
        if not hasattr(self,'strategy'):return
        s=self.strategy;a=self.native.cache.account_for_venue(SIM)
        payload=dict(physical_index=self.number,fixture=pre.REC.current[0],stage=label,
            native_cash=str(a.balance_total()) if a else None,
            orders=[dict(id=str(o.client_order_id),status=o.status.name,quantity=str(o.quantity),filled=str(o.filled_qty),leaves=str(o.leaves_qty),side=o.side.name,price=str(getattr(o,'price',None)),reduce_only=o.is_reduce_only) for o in self.native.cache.orders()],
            positions=[dict(instrument=str(p.instrument_id),quantity=str(p.quantity),side='LONG' if p.is_long else 'SHORT') for p in self.native.cache.positions_open()],
            fills=[dict(order_id=str(e.client_order_id),trade_id=str(e.trade_id),quantity=str(e.last_qty),price=str(e.last_px),commission=str(e.commission),ts=e.ts_event) for e in s.native_fills],
            md=s._md_report(),pair=s._pair_report(),split=s._split_cover_report(),stock_margin_calls=s.stock_margin_calls,terminal=s.terminal_lifecycle,
            cap=str(s._pair['caps'].bmax) if s._pair else None)
        artifact=pre.REC.path.parent/f'a0-fixture-{self.number:02d}-{label}.json'
        artifact.write_text(json.dumps(pre.snapshot_config(payload)['payload'],indent=2)+'\n')
        data=json.loads(pre.REC.path.read_text());entry=data['attempts'][self.number-1]
        entry.setdefault('native_snapshots',[]).append(dict(path=str(artifact),sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),stage=label));pre.REC.write(data)

class StockProbe(pre.ControlProbe):
    def __init__(self,cfg):
        self.stock_margin_calls=[];self.cancel_calls=[];self.delay_cancel=False;self.delay_target_ack=False;self.held_target_acks=[];self.inside_tp_fill=False;super().__init__(cfg)
    def _tier_allows_increase(self,*args):
        result=WaveOverlayStrategy._tier_allows_increase(self,*args)
        self.stock_margin_calls.append(dict(instrument=str(args[0]),side=str(args[1]),quantity=str(args[2]),timestamp=args[3],allowed=result))
        return result
    def cancel_order(self,order,*args,**kwargs):
        self.cancel_calls.append(dict(order_id=str(order.client_order_id),inside_tp_fill=self.inside_tp_fill,ts=self.clock.timestamp_ns()))
        if self.delay_cancel and not order.is_reduce_only:return
        return super().cancel_order(order,*args,**kwargs)
    def on_order_accepted(self,event):
        intent=self._pending_by_order.get(str(event.client_order_id))
        if self.delay_target_ack and intent and intent.action=='BTC_REDUCE':
            self.held_target_acks.append(event);return
        return super().on_order_accepted(event)
    def on_order_filled(self,event):
        intent=self._pending_by_order.get(str(event.client_order_id))
        self.inside_tp_fill=bool(intent and intent.action=='BTC_REDUCE')
        try:return super().on_order_filled(event)
        finally:self.inside_tp_fill=False

pre.CountedEngine=CountedEngine

def advance(e,s,ns,btc='99',sol='100',btcsize='1000',solsize='1000',fresh=True):
    if fresh:
        e.add_data([venue_mark(BTC_PERP.id,D(btc),ns),venue_mark(SOL_PERP.id,D(sol),ns)],client_id=ClientId('BYBIT_MARK'),sort=False)
    run_ticks(e,[tick(BTC_PERP,ns,btc,size=btcsize),tick(SOL_PERP,ns,sol,size=solsize)])

def fixture_configuration(case):
    variant='R2_C0' if case=='A06_C0_NO_RELEASE' else 'R2_A0'
    signal=PairedSignal(10,10,10+M,D(99),D(100),D(1),D(2),True,True,False,True,False,D('99.2'),D(90),D('99.2'))
    kwargs=build_a0_kwargs(Path('.'),Path('.'),variant,(signal,),start_ms=-86400000,end_ms=3600000)
    bound=signature(run_native_diagnostic).bind(**kwargs);bound.apply_defaults();validate_native_a0(bound.arguments)
    _,context,_=pre.registered_fixture_context('R2',start_ms=-86400000,end_ms=3600000)
    context.update(bound.arguments)
    # Only synthetic native instruments, causal finite seed, marks/time adapters differ.
    return build_native_strategy_config(context)


def assert_daily_fixture_preconditions(strategy):
    # Keep the actual stock daily-open admission guard; adapt the synthetic
    # fixture's first open, as source06 did, rather than bypassing the guard.
    assert strategy._current_btc.ts_event - 86_400_000_000_000 >= strategy.config.trading_start_open_ns
    assert all(int(row.available_at.timestamp()*10**9)<=strategy._current_btc.ts_event for row in strategy._bars)


def setup(case):
    conf=fixture_configuration(case)
    pre.REC.effective_config=pre.snapshot_config(conf)
    s=StockProbe(conf);e=pre.base_engine(s)
    advance(e,s,1,btc='100')
    pre.prepare_completed_day(s,2)
    assert_daily_fixture_preconditions(s)
    with patch('coinmaster.domain.wave_overlay.completed_wave_levels',lambda *args:(0,0,.03)):
        WaveOverlayStrategy._advance_current_day(s)
    intent=s._queued_intents[0][0];ep=s._domain.episode
    assert D(str(intent.requested_notional))==D('5.5')*D(str(ep.active_entry))
    advance(e,s,3,btc='100')
    advance(e,s,4,btcsize='10' if case=='A02_PARTIAL_FIRST_CLOSED_CAP' else '1000')
    advance(e,s,5);advance(e,s,6)
    assert s.stock_margin_calls and all(x['allowed'] for x in s.stock_margin_calls)
    second=[o for o in e.cache.orders_open() if not o.is_reduce_only]
    assert len(second)==1 and second[0].price.as_decimal()==D('98.5')
    if case=='A04_CANCEL_RACE_LATE_FILL':s.delay_cancel=True
    advance(e,s,10)
    assert s._pair and s._pair['risk']=='ACTIVE_RISK'
    return s,e,ep,second[0]

def run_case(case):
    s=e=None
    try:
        s,e,ep,old=setup(case)
        rights=s._md_plans[ep.id].get('a0')
        if case!='A06_C0_NO_RELEASE':
            assert rights and rights['original_second']==s._split_parent['quantity']-s._split_parent['first_quantity']
        advance(e,s,M+10)
        if case=='A02_PARTIAL_FIRST_CLOSED_CAP':
            # Genuine SOL TP -> actual BTC debt/cut, no closed BTC refund.
            for ns in (M+11,M+12,M+13):advance(e,s,ns,sol='98.9')
        advance(e,s,M+14,btc='99.3')
        assert s._pair['risk']=='INACTIVE_RISK'
        if case=='A04_CANCEL_RACE_LATE_FILL':
            advance(e,s,2*M+14,btc='99.3')
            assert not rights['submitted'] and not old.is_closed
            # Actual venue cancel-race fill opens debt; no ACK fiction.
            advance(e,s,2*M+15,btc='98',btcsize='1')
            assert old.filled_qty.as_decimal()>0 and not rights['submitted']
            s.delay_cancel=False;WaveOverlayStrategy.cancel_order(s,old)
            for ns in range(2*M+16,2*M+24):advance(e,s,ns,btc='99.3')
        if case=='A05_CROSS_MARGIN_UNKNOWN':
            s.delay_target_ack=True
            target=next(o for o in e.cache.orders_open() if o.instrument_id==BTC_PERP.id and o.is_reduce_only)
            s.cancel_order(target)
            advance(e,s,M+15,btc='99.3')
            assert s.held_target_acks
            advance(e,s,2*M+14,btc='99.3')
            assert not rights['submitted'] and rights['denial_counts']['CURRENT_THREE_TP_ACK_UNKNOWN']
            e.capture('CURRENT_TARGET_ACK_HELD')
            s.delay_target_ack=False
            for event in s.held_target_acks:WaveOverlayStrategy.on_order_accepted(s,event)
            s.held_target_acks=[]
            advance(e,s,2*M+15,btc='98.4')
            assert not rights['submitted'] and rights['denial_counts']['POST_ONLY_CROSS']
            frozen=rights['locked_cap']
            s.config.margin_policy._marks.clear()
            advance(e,s,2*M+16,btc='99.3',fresh=False)
            assert not rights['submitted'] and rights['denial_counts']['NATIVE_MARGIN']
            for _ in range(2):s._a0_check(tick(BTC_PERP,2*M+16,price='99.3'))
            assert rights['locked_cap']==frozen and not rights['submitted']
        advance(e,s,2*M+25,btc='99.3')
        if case=='A06_C0_NO_RELEASE':
            assert not rights
        else:
            assert rights['submitted'] and rights['attempted']
            assert old.status.name=='CANCELED' and rights['order_id']!=str(old.client_order_id)
            assert rights['granted_cap']<=rights['locked_cap']+rights['original_second']
            release=e.cache.order(__import__('nautilus_trader.model.identifiers',fromlist=['ClientOrderId']).ClientOrderId(rights['order_id']))
            advance(e,s,2*M+26,btc='98',btcsize='1')
            if case=='A03_ORDINARY_TP_KILLS':
                assert not release.is_closed and release.filled_qty.as_decimal()>0
                s.delay_cancel=True
                advance(e,s,2*M+27,btc='100')
                assert rights['dead'] and any(c['order_id']==rights['order_id'] and c['inside_tp_fill'] for c in s.cancel_calls)
                assert s._split_parent['closed'] and old.status.name=='CANCELED'
                tp_cap=s._pair['caps'].bmax
                e.capture('ORDINARY_TP_IMMEDIATE_CANCEL_REQUEST')
                # Delayed venue transport can still fill; actual excess owns
                # corrective BTC debt and cannot reopen the spent right.
                before=release.filled_qty.as_decimal()
                advance(e,s,2*M+28,btc='98',btcsize='1')
                assert release.filled_qty.as_decimal()>before
                s.delay_cancel=False;WaveOverlayStrategy.cancel_order(s,release)
                for ns in range(2*M+29,2*M+40):advance(e,s,ns,btc='99.3')
                assert release.is_closed and s._pair_qty(BTC_PERP.id)<=s._pair['caps'].bmax
                assert s._pair['caps'].bmax<=tp_cap
                assert rights['dead'] and rights['attempted']
                e.capture('LATE_FILL_CORRECTED_NO_CAP_REANCHOR')
            else:
                advance(e,s,2*M+27,btc='98')
                advance(e,s,2*M+28,btc='99')
                assert s._pair_qty(BTC_PERP.id)<=s._pair['caps'].bmax
            assert len([x for x in s._md_report()['events'] if x['event']=='A0_SUBMIT'])==1
            assert s._md_plans[ep.id]['second_filled']<=rights['original_second']
            for ns in range(2*M+41,2*M+55):
                advance(e,s,ns,btc='103',btcsize=str(1000+ns%100))
                if not e.cache.positions_open():break
            assert {0,1,2}<=ep.btc_filled_tps
        e.capture('BEFORE_TERMINAL')
        natural=not e.cache.positions_open()
        if not natural:
            s._begin_forced_close('TERMINAL_BOUNDARY_SETTLEMENT')
            for ns in range(3*M,3*M+10):advance(e,s,ns,btc='99',sol='100')
        result=pre.settled_identity(s,e,'NATURAL_TP_FLAT' if natural else 'FORCED_TERMINAL_FLAT')
        result.update(case=case,stock_margin_calls=s.stock_margin_calls,a0=s._md_report()['a0_rights'],cancel_calls=s.cancel_calls)
        return result
    finally:
        if e is not None:e.dispose()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ledger',required=True);ap.add_argument('--gate',required=True);args=ap.parse_args()
    gate=json.loads(Path(args.gate).read_text())
    source_root=Path(__file__).resolve().parents[2]
    pin=source_root/'.source-commit'
    head=pin.read_text().strip() if pin.is_file() else subprocess.check_output(['git','rev-parse','HEAD'],cwd=source_root,text=True).strip()
    if gate.get('source_commit')!=head or not gate.get('root_go'):raise ValueError('ROOT_REVIEW_SOURCE_GO_REQUIRED')
    global_rec=Recorder(args.ledger,gate);pre.REC=global_rec
    for case in CASES:
        global_rec.current=(case,'R2',0,3600*10**9);global_rec.effective_config=None
        before=len(global_rec.engines)
        try:
            result=run_case(case)
            e=global_rec.engines[-1];global_rec.finish(e.number,'COMPLETED',dict(process_rc=0,result=result,cleanup='DISPOSED'))
        except BaseException as error:
            if len(global_rec.engines)>before:
                e=global_rec.engines[-1]
                if not e.disposed:
                    try:e.dispose()
                    except BaseException:pass
                global_rec.finish(e.number,'FAILED',dict(process_rc=1,error=str(error),traceback=traceback.format_exc(),cleanup='DISPOSED' if e.disposed else 'FAILED'))
            raise
    print(json.dumps({'status':'PASS','physical_started':len(global_rec.engines)}))
if __name__=='__main__':main()
