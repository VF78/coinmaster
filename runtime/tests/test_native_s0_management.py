from decimal import Decimal as D
from datetime import UTC, datetime
import pytest
from nautilus_trader.model.enums import OrderSide, TimeInForce
from coinmaster.domain.wave_overlay import Episode
from coinmaster.research.native_fixture import BTC_PERP, SOL_PERP
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from test_native_episode_risk import tick, run_ticks
from test_wave_native_integration import lifecycle_config, native_engine

class Probe(WaveOverlayStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.opened = set()
        self.reopen = False
    def _advance_current_day(self):
        pass
    def on_quote_tick(self, quote):
        if quote.instrument_id not in self.opened or self.reopen:
            self.opened.add(quote.instrument_id)
            self.reopen = False
            inst = self.cache.instrument(quote.instrument_id)
            self.submit_order(self.order_factory.market(inst.id, OrderSide.BUY, inst.make_qty(D('4')), time_in_force=TimeInForce.IOC))
            return
        return super().on_quote_tick(quote)


def setup(fraction=D('.5'), assets=(BTC_PERP,)):
    strategy = Probe(lifecycle_config(research_s0_management_fraction=fraction))
    engine = native_engine(strategy)
    run_ticks(engine, [tick(a, 1) for a in assets])
    ep = Episode('s0-test', 1, 10000, 1.)
    ep.btc_entry_vwap = 100.; ep.btc_initial_qty = ep.btc_open_qty = 4.; ep.h = 100.
    ep.sol_qty = 4. if SOL_PERP in assets else 0.
    ep.sol_add_filled_notional = {0:400.}
    strategy._domain.episode = ep
    return strategy, engine, ep


def receipt(strategy, source, dd, btc='90', sol='90'):
    strategy._s0_receipt(source, source+1, D(10000)*(1-D(dd)), D(10000), 0, 1,
        ((str(BTC_PERP.id),D(btc)), (str(SOL_PERP.id),D(sol))))

@pytest.mark.parametrize('fraction,remaining', [(D('.5'),D('2')), (D('.75'),D('1'))])
@pytest.mark.parametrize('asset',[BTC_PERP,SOL_PERP])
def test_native_fresh_cross_reduces_exact_once_no_false_tp_or_sol_credit(fraction,remaining,asset):
    s,e,ep=setup(fraction,(asset,))
    try:
        receipt(s,2,'.20');receipt(s,3,'.25')
        assert len(s._s0_targets)==1
        run_ticks(e,[tick(asset,5,'90')])
        assert s._s0_position(asset.id).quantity.as_decimal()==remaining
        assert not ep.btc_filled_tps and ep.sol_add_filled_notional=={0:400.}
        receipt(s,6,'.10');receipt(s,7,'.30');run_ticks(e,[tick(asset,9,'90')])
        assert s._s0_position(asset.id).quantity.as_decimal()==remaining
        assert len([r for r in s.s0_management_audit if r['event']=='SUBMIT'])==1
    finally:e.end();e.dispose()

def test_already_underwater_new_entry_requires_later_fresh_cross_and_zero_loss_never_triggers():
    s,e,ep=setup()
    try:
        receipt(s,2,'.30');receipt(s,3,'.40');assert not s._s0_targets
        receipt(s,4,'.20');receipt(s,5,'.25',btc='100');assert not s._s0_targets
        receipt(s,6,'.20');receipt(s,7,'.25',btc='99');assert s._s0_targets
    finally:e.end();e.dispose()

def test_ineligible_gap_discards_crossing_and_preserves_profitable_other_leg():
    s,e,ep=setup(assets=(BTC_PERP,SOL_PERP))
    try:
        receipt(s,2,'.20')
        s._s0_last_increase[BTC_PERP.id]=3
        receipt(s,3,'.25',sol='110')
        receipt(s,4,'.30',sol='110')
        assert not s._s0_targets
        receipt(s,5,'.20',sol='110');receipt(s,6,'.30',sol='110')
        assert set(s._s0_targets)=={BTC_PERP.id}
        run_ticks(e,[tick(BTC_PERP,8,'90'),tick(SOL_PERP,8,'110')])
        assert s._s0_position(SOL_PERP.id).quantity.as_decimal()==4
    finally:e.end();e.dispose()

def test_forced_exit_between_claim_and_quote_owns_all_leaves_without_management_child():
    s,e,ep=setup()
    try:
        receipt(s,2,'.20');receipt(s,3,'.30');s._begin_forced_close('REGIME')
        run_ticks(e,[tick(BTC_PERP,5,'90')])
        assert not [r for r in s.s0_management_audit if r['event']=='SUBMIT']
        assert not e.cache.positions_open()
    finally:e.end();e.dispose()

def test_native_netting_two_cycles_have_distinct_opening_identity_and_split_fill_is_same_cycle():
    s,e,ep=setup()
    try:
        p=s._s0_position(BTC_PERP.id);first=s._s0_cycle(p)
        inst=e.cache.instrument(BTC_PERP.id)
        s.submit_order(s.order_factory.market(inst.id,OrderSide.BUY,inst.make_qty(D('1')),time_in_force=TimeInForce.IOC))
        run_ticks(e,[tick(BTC_PERP,2)])
        assert s._s0_cycle(s._s0_position(inst.id))==first
        s.submit_order(s.order_factory.market(inst.id,OrderSide.SELL,inst.make_qty(D('5')),time_in_force=TimeInForce.IOC,reduce_only=True))
        run_ticks(e,[tick(BTC_PERP,3)])
        assert not e.cache.positions_open()
        s.reopen=True;run_ticks(e,[tick(BTC_PERP,4)])
        second=s._s0_cycle(s._s0_position(inst.id))
        assert first!=second and first[2:]!=second[2:]
        receipt(s,5,'.20');receipt(s,6,'.30');assert s._s0_targets
    finally:e.end();e.dispose()

@pytest.mark.parametrize('reason',['CANCELED','DENIED','REJECTED'])
def test_terminal_incomplete_claim_does_not_retry_or_clear_new_cycle(reason):
    s,e,ep=setup()
    try:
        receipt(s,2,'.20');receipt(s,3,'.30')
        owner=s._s0_targets[BTC_PERP.id];owner['orders'].add('old');s._s0_orders['old']=owner
        newer=dict(owner);newer['cycle']=('new',);s._s0_targets[BTC_PERP.id]=newer
        s._s0_terminal('old',4,reason)
        assert s._s0_targets[BTC_PERP.id] is newer
        assert not s._s0_orders
    finally:e.end();e.dispose()

def test_default_off_never_changes_native_quantity():
    s,e,ep=setup(None)
    try:
        receipt(s,2,'.20');receipt(s,3,'.50');run_ticks(e,[tick(BTC_PERP,5,'90')])
        assert s._s0_position(BTC_PERP.id).quantity.as_decimal()==4 and not s.s0_management_audit
    finally:e.end();e.dispose()

@pytest.mark.parametrize('late_fill',[False,True])
def test_resting_native_tp_cancel_ack_or_late_fill_reconciles_fixed_target(late_fill):
    s,e,ep=setup()
    try:
        ep.wave_levels=(.1,.2,.3)
        intent=s._domain._intent(ep,'BTC_REDUCE',-1,0,quantity=1.,limit_price=110.)
        ep.resting_reductions.add(intent.id)  # Same durable state as plan_confirmed_btc_targets.
        s._submit_intent(intent,100.,100.,None,0,ts_now=2)
        run_ticks(e,[tick(BTC_PERP,2)])
        assert e.cache.orders_open()
        if late_fill:
            s.cancel_order=lambda *a,**kw:None  # Delay venue cancel ACK, permit original TP match.
        receipt(s,3,'.20');receipt(s,4,'.30')
        assert s._s0_targets
        run_ticks(e,[tick(BTC_PERP,6,'111' if late_fill else '90')])
        run_ticks(e,[tick(BTC_PERP,7,'111' if late_fill else '90')])
        assert s._s0_position(BTC_PERP.id).quantity.as_decimal()==2
        protective=[r for r in s.s0_management_audit if r['event']=='FILL']
        assert sum(D(r['quantity']) for r in protective)==(1 if late_fill else 2)
        assert (0 in ep.btc_filled_tps)==late_fill
    finally:e.end();e.dispose()


def test_native_ioc_partial_cancel_is_one_attempt_and_no_right_refill():
    s,e,ep=setup(assets=(SOL_PERP,))
    try:
        receipt(s,2,'.20');receipt(s,3,'.30')
        run_ticks(e,[tick(SOL_PERP,5,'90',size='.5')])
        run_ticks(e,[tick(SOL_PERP,6,'90')])
        submitted=[r for r in s.s0_management_audit if r['event']=='SUBMIT']
        assert len(submitted)==1
        assert not s._s0_orders and not s._s0_targets
        assert ep.sol_add_filled_notional=={0:400.} and not ep.sol_rights
    finally:e.end();e.dispose()


def test_opt_in_receipt_delivery_after_commit_immutable_marks_and_gap_invalidation(tmp_path):
    from types import SimpleNamespace
    from coinmaster.research.minute_risk import NativeMinuteRiskRecorder
    s,e,ep=setup()
    r=NativeMinuteRiskRecorder(tmp_path/'risk.csv.gz',D(10000),(BTC_PERP,SOL_PERP),{BTC_PERP.id:D(40),SOL_PERP.id:D(20)},999_000_000_000)
    try:
        bundle=SimpleNamespace(open_time_ms=-60000,btc_mark={k:'100' for k in ('open','high','low','close')},sol_mark={k:'100' for k in ('open','high','low','close')})
        r.set_week([bundle]);r.receipt_pending=(1,bundle)
        delivered=[]
        def callback(*args):
            assert r.receipt_pending is None and r.receipt_count==1
            assert r.settled_curve.peak is not None
            delivered.append(args)
        s._s0_receipt=callback
        r.finalize_receipt(s,1);assert not delivered
        r.finalize_receipt(s,2);assert len(delivered)==1
        source,receipt_ns,equity,peak,epoch,account_ns,marks=delivered[0]
        assert source<receipt_ns and isinstance(marks,tuple) and isinstance(marks[0],tuple)
        assert equity==r._snapshot(s,1,bundle)[5]
        s._s0_previous[BTC_PERP.id]=('sentinel',D('.1'))
        r.receipt_pending=(1,bundle);r.note_fill(2);r.finalize_receipt(s,3)
        assert not s._s0_previous and r.receipt_unavailable==1 and len(delivered)==1
    finally:r.file.close();r.receipt_file.close();e.end();e.dispose()


@pytest.mark.parametrize('action',['CLOSE_ALL','BTC_REDUCE'])
@pytest.mark.parametrize('pending_child',[False,True])
def test_queued_native_exit_preempts_claim_before_pending_child_or_cancel_ack_wait(action,pending_child):
    s,e,ep=setup()
    try:
        receipt(s,2,'.20');receipt(s,3,'.30')
        owner=s._s0_targets[BTC_PERP.id]
        if pending_child:
            owner['orders'].add('unknown-ack-child')
            s._s0_orders['unknown-ack-child']=owner
        intent=s._domain._intent(ep,action,-1,None if action=='CLOSE_ALL' else 0,quantity=1.,reason='REGIME' if action=='CLOSE_ALL' else None)
        s._queued_intents.append((intent,None,0))
        run_ticks(e,[tick(BTC_PERP,5,'90'),tick(BTC_PERP,6,'90')])
        assert not [r for r in s.s0_management_audit if r['event']=='SUBMIT']
        assert not s._s0_targets
        if pending_child:assert s._s0_orders['unknown-ack-child'] is owner
        if action=='CLOSE_ALL':
            if pending_child:
                s._submit_forced_closes_from_cache()  # Ordinary cancel callback continuation.
                assert s._s0_position(BTC_PERP.id).quantity.as_decimal()==4
                s._s0_terminal('unknown-ack-child',7,'CANCELED')
                run_ticks(e,[tick(BTC_PERP,8,'90')])
            assert not e.cache.positions_open()
        else:
            if pending_child:
                assert s._s0_position(BTC_PERP.id).quantity.as_decimal()==4 and s._queued_intents
                s._s0_terminal('unknown-ack-child',7,'CANCELED')
                run_ticks(e,[tick(BTC_PERP,8,'90')])
            assert s._s0_position(BTC_PERP.id).quantity.as_decimal()==3
    finally:e.end();e.dispose()


def test_mandatory_sol_timeout_waits_unknown_management_child_then_closes_actual_leaves():
    s,e,ep=setup(assets=(SOL_PERP,))
    try:
        receipt(s,2,'.20');receipt(s,3,'.30')
        owner=s._s0_targets[SOL_PERP.id];owner['orders'].add('unknown');s._s0_orders['unknown']=owner
        timeout=s._domain._intent(ep,'SOL_EXIT',-1,None,quantity=4.,reason='SOL_HARD_TIMEOUT')
        s._mandatory_sol_exit=(timeout,None,0)
        run_ticks(e,[tick(SOL_PERP,5,'90')])
        assert s._s0_position(SOL_PERP.id).quantity.as_decimal()==4
        s._s0_terminal('unknown',6,'CANCELED')
        run_ticks(e,[tick(SOL_PERP,7,'90')])
        assert not e.cache.positions_open()
        assert not [r for r in s.s0_management_audit if r['event']=='SUBMIT']
    finally:e.end();e.dispose()
