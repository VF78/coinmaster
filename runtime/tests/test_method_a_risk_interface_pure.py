"""Actual public objects/callbacks only; no native engine or economic results."""
import json
import unittest
from decimal import Decimal as D
from types import SimpleNamespace as NS
from dataclasses import replace as dr
from msgspec.structs import replace
from nautilus_trader.common.component import TestClock
from nautilus_trader.common.factories import OrderFactory
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.cache.cache import Cache
from nautilus_trader.model.identifiers import TraderId,StrategyId,AccountId,VenueOrderId,TradeId,PositionId
from nautilus_trader.model.enums import OrderSide,OrderType,TimeInForce,LiquiditySide,AccountType
from nautilus_trader.model.events import OrderSubmitted,OrderAccepted,OrderUpdated,OrderFilled,AccountState
from nautilus_trader.model.objects import Money,AccountBalance,MarginBalance
from nautilus_trader.model.currencies import USDT
from nautilus_trader.model.position import Position
from nautilus_trader.accounting.accounts.margin import MarginAccount
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
from coinmaster.strategy.method_a_risk_native import MethodARiskResearch
from coinmaster.strategy.paired_prefix import PairedPrefixResearch
from coinmaster.strategy.native_account_snapshot import native_account_snapshot
from coinmaster.research.method_a_risk_rows import wire,SCHEMA


def objects():
    trader=TraderId('EXAMPLE-001');strategy=StrategyId('MethodA-001');account=AccountId('SIM-EXAMPLE')
    clock=TestClock();factory=OrderFactory(trader,strategy,clock)
    entry=factory.market(instrument_id=SOL_PERP.id,order_side=OrderSide.SELL,quantity=SOL_PERP.make_qty(D('.4')),time_in_force=TimeInForce.IOC)
    fill=OrderFilled(trader,strategy,SOL_PERP.id,entry.client_order_id,VenueOrderId('EXAMPLE-VENUE-ENTRY'),account,TradeId('EXAMPLE-TRADE'),PositionId('EXAMPLE-SOL-POSITION'),OrderSide.SELL,OrderType.MARKET,SOL_PERP.make_qty(D('.4')),SOL_PERP.make_price(D(100)),USDT,Money(D('.022'),USDT),LiquiditySide.TAKER,UUID4(),1,1)
    position=Position(SOL_PERP,fill)
    initial=Money(D(2),USDT);maintenance=Money(D('.2'),USDT)
    state=AccountState(account,AccountType.MARGIN,USDT,False,[AccountBalance(Money(D(10000),USDT),Money(D('2.2'),USDT),Money(D('9997.8'),USDT))],[MarginBalance(initial,maintenance,SOL_PERP.id)],{},UUID4(),1,1)
    native_account=MarginAccount(state)
    target=factory.limit(instrument_id=SOL_PERP.id,order_side=OrderSide.BUY,quantity=SOL_PERP.make_qty(D('.4')),price=SOL_PERP.make_price(D(99)),time_in_force=TimeInForce.GTC,reduce_only=True)
    common=(trader,strategy,SOL_PERP.id,target.client_order_id)
    target.apply(OrderSubmitted(*common,account,UUID4(),2,2))
    target.apply(OrderAccepted(*common,VenueOrderId('EXAMPLE-VENUE-TP'),account,UUID4(),3,3))
    update=OrderUpdated(*common,VenueOrderId('EXAMPLE-VENUE-TP'),account,SOL_PERP.make_qty(D('.3')),SOL_PERP.make_price(D(98)),None,UUID4(),4,4)
    target.apply(update);clock.set_time(4)
    return trader,strategy,account,clock,fill,position,native_account,target,update


def public_example():
    trader,strategy,account,clock,fill,position,native_account,target,update=objects()
    return wire(dict(schema=SCHEMA,scope='ENGINE_FREE_PUBLIC_TYPE_ROUNDTRIP_ONLY_NOT_NATIVE_RESULT',qualified=False,engine_constructors=0,
        nested_examples=dict(native_account=native_account_snapshot(native_account,(BTC_PERP.id,SOL_PERP.id)),native_positions=[position.to_dict()],native_fill=OrderFilled.to_dict(fill),native_order=target.to_dict(),native_updated=OrderUpdated.to_dict(update)),
        exact_zero_shock_example=dict(leg='SOL',native_position_id=str(position.id),native_initial=str(native_account.margin_init(SOL_PERP.id).as_decimal()),native_maintenance=str(native_account.margin_maint(SOL_PERP.id).as_decimal()),scenario_zero_initial='2',scenario_zero_maintenance='.2',exact_equal=True),
        reference_shape=dict(schema=SCHEMA,kind='risk',path='EXAMPLE_ONLY_NOT_A_NATIVE_REPORT.jsonl.gz',rows=0,sha256=None,completeness='ALL_EMITTED_ROWS_NO_SAMPLING',native_state_mutations=0),
        identity_semantics=dict(snapshot_ref='risk:<monotone-risk-sequence>',boundary_state_ref='paired:<monotone-paired-sequence>',risk_episode_id='<native-parent-id>:<risk-episode-counter>',coherent_peak_source='actual observer sequence/epoch/native peak; this example has no observed peak'),
        trim_mapping=dict(action='PAIRED_BTC_DEBT',level=None,writer='MethodARiskResearch._pair_fill -> btc_risk_retired_lots; then existing _ma_reconcile',genuine_tp_action='BTC_REDUCE',genuine_tp_levels=[0,1,2]),
        qualification_limit='Public nested types only. No lifecycle/once-episode/closed-cash/coherent-peak evidence; consumer must return UNKNOWN.'))


class RiskInterface(unittest.TestCase):
    def test_actual_bound_method_dispatch(self):
        from run_method_a_m1 import config
        from coinmaster.strategy.wave_overlay import WaveOverlayStrategy,MethodAWaveOverlayStrategy
        cfg,_=config();off=WaveOverlayStrategy(cfg)
        oncfg=replace(cfg,research_method_a_risk='HEDGE',research_sol_off=True,candidate=dr(cfg.candidate,sol_overlay_enabled=False))
        on=MethodAWaveOverlayStrategy(oncfg)
        for name in ('_record_submission','on_order_filled','_deny_local_entry','_tier_allows_increase'):
            self.assertIs(getattr(off,name).__func__,getattr(WaveOverlayStrategy,name))
            self.assertIs(getattr(on,name).__func__,getattr(MethodARiskResearch,name))
        self.assertFalse(hasattr(off,'_mr_peak'))
        self.assertTrue(on._mr_enabled())

    def test_actual_native_updated_callback_and_UUID_dedup(self):
        trader,strategy,account,clock,fill,position,native_account,order,update=objects()
        cache=Cache();cache.add_instrument(SOL_PERP);cache.add_order(order)
        oid=str(order.client_order_id);logs=[];protection=[]
        owner=dict(instrument=SOL_PERP.id,kind='TP',level=0,accepted=True,pending=dict(payload=(D('.3'),D(98),None),sequence=1,generation=0))
        context=NS(config=NS(sol_id=SOL_PERP.id,research_sol_standing_protection=False),id=strategy,cache=cache,clock=clock,
            _mr_enabled=lambda:True,_pair_sol_v2=lambda:True,_pair_orders={oid:owner},_pair_sol_events=set(),
            _pair_log=lambda *args,**kw:logs.append((args,kw)),_pair_fail=lambda *args:(_ for _ in ()).throw(AssertionError(args)),
            _pair_sol_retire_check=lambda ns:None,_pair_protect=lambda ns:protection.append(ns),
            _pair_sol_payload_matches=PairedPrefixResearch._pair_sol_payload_matches)
        MethodARiskResearch._pair_sol_native_event(context,update,'typed_updated')
        self.assertIsNone(owner['pending']);self.assertEqual(owner['ack'],(D('.3'),D(98),None));self.assertEqual(owner['last_ack_event_id'],str(update.id))
        self.assertEqual(protection,[4]);count=len(logs)
        MethodARiskResearch._pair_sol_native_event(context,update,'generic_duplicate')
        self.assertEqual(len(logs),count);self.assertEqual(protection,[4])

    def test_protected_SOL_recovery_dispatch_and_owner_blockers(self):
        class Probe:
            _mr_recover=MethodARiskResearch._mr_recover
            _mr_recovery_ready=MethodARiskResearch._mr_recovery_ready
            _pair_work=PairedPrefixResearch._pair_work
            def __init__(self,blocker=None):
                self.id='STRATEGY';self.config=NS(btc_id='BTC',sol_id='SOL');self.submitted=[];self.cancelled=[];self.verified=[]
                stop=NS(client_order_id='positive-stop',instrument_id='SOL',strategy_id=self.id,is_closed=False,is_reduce_only=True)
                self.orders={'positive-stop':stop};self._pair_orders={'positive-stop':dict(instrument='SOL',kind='STOP',parent='P')}
                self._pair=dict(parent='P',side=1,debt_since=None,protection_since=None);self._mr_sequence=0;self.blocker=blocker
                if blocker in ('SOL_CAP','ENTRY','FOREIGN'):
                    order=NS(client_order_id='blocker',instrument_id='SOL',strategy_id=self.id if blocker!='FOREIGN' else 'OTHER',is_closed=False,is_reduce_only=blocker!='ENTRY',side=OrderSide.SELL)
                    self.orders['blocker']=order
                    if blocker!='FOREIGN':self._pair_orders['blocker']=dict(instrument='SOL',kind=blocker,parent='P')
                self.cache=NS(instrument=lambda iid:NS(size_increment=NS(as_decimal=lambda:D(1))),order=lambda oid:self.orders.get(str(oid)),orders_open=lambda:list(self.orders.values()),orders_inflight=lambda:[])
            def _mr_liabilities(self,ns):return ()
            def _mr_recovery_choice(self,leg,*args):return (1,D(-2),D(1),D(100),((1,1),)) if leg=='SOL' else None
            def _mr_log(self,*args,**kw):pass
            def _mr_fail(self,*args):raise AssertionError(args)
            def _pair_submit(self,*args):self.submitted.append(args)
            def _pair_cancel(self,work):self.cancelled.extend(work);return bool(work)
            def _pair_sol_retire_busy(self):return self.blocker=='RETIRING'
            def _pair_sol_protect(self,ns):pass
            def _pair_sol_positive(self,order,exact=False):self.verified.append((order.client_order_id,exact));return exact
        state=NS(cushion=D(50),btc=D(1),sol=D(-2));initial=NS(worst_deficit=D(10));tick=NS(ts_event=1,instrument_id='SOL')
        normal=Probe();normal._mr_recover(tick,state,None,initial)
        self.assertEqual(len(normal.submitted),1);self.assertEqual(normal.submitted[0][3],'SOL_CAP')
        self.assertEqual(normal.cancelled,[]);self.assertEqual(normal.verified,[('positive-stop',True)])
        for blocker in ('SOL_CAP','ENTRY','FOREIGN','RETIRING'):
            probe=Probe(blocker);probe._mr_recover(tick,state,None,initial)
            self.assertEqual(probe.submitted,[],blocker)
            self.assertFalse(any(owner['kind']=='STOP' for oid,owner,order in probe.cancelled))

    def test_actual_fill_starts_immutable_recovery_deadline(self):
        from coinmaster.strategy.method_a_risk import State,Features,MINUTE
        feature=Features(0,0,0,D(1),D(1),D('.1'),D('.1'),D('.1'),D('.01'),D(0),D(0))
        unsafe=State(D(10),D(-2),D(100),D(100),D(100),D(100));failures=[]
        ctx=NS(_mr_after_busy=False,_forced_close_reason=None,_liquidating=False,_mr_sequence=0,
            _pair=dict(caps=NS(bmax=D(10)),debt_since=None),_pair_qty=lambda iid:D(10),config=NS(btc_id='BTC',sol_id='SOL'),cache=NS(instrument=lambda iid:NS(size_increment=NS(as_decimal=lambda:D(1)))),
            _mr_snapshot=lambda ns:(unsafe,feature),_mr_margin=lambda *args:(D(0),D(0)),_mr_liabilities=lambda ns:(),
            _pair_cancel_btc_increases=lambda ns:None,_mr_recovery_ready=lambda *args:False,
            _mr_recovery_choice=lambda leg,*args:(1,D(-2),D(10),D(100),((1,1),)) if leg=='SOL' else None,
            _mr_log=lambda *args,**kwargs:None,_mr_fail=lambda reason,ns:failures.append((reason,ns)))
        MethodARiskResearch._mr_after_actual(ctx,1)
        self.assertEqual(ctx._pair['debt_since'],1);self.assertEqual(failures,[])
        MethodARiskResearch._mr_after_actual(ctx,MINUTE+2)
        self.assertEqual(failures[-1],('RECOVERY_DEADLINE',MINUTE+2));self.assertEqual(ctx._pair['debt_since'],1)
        safe=State(D('.1'),D(0),D(100),D(100),D(100),D(100));ctx._mr_snapshot=lambda ns:(safe,feature)
        MethodARiskResearch._mr_after_actual(ctx,MINUTE+3);self.assertIsNone(ctx._pair['debt_since'])
        breach=State(D('.1'),D(0),D(50),D(100),D(100),D(100));ctx._mr_snapshot=lambda ns:(breach,feature)
        MethodARiskResearch._mr_after_actual(ctx,MINUTE+4);self.assertEqual(failures[-1][0],'CUSHION_BREACH')

    @staticmethod
    def denial_actor(state,feature,stock_allowed=True,liabilities=()):
        from run_method_a_m1 import config
        from coinmaster.strategy.wave_overlay import MethodAWaveOverlayStrategy
        from copy import deepcopy
        cfg,_=config();cfg=replace(cfg,research_method_a_risk='HEDGE',research_sol_off=True,candidate=dr(cfg.candidate,sol_overlay_enabled=False))
        actor=MethodAWaveOverlayStrategy(cfg)
        actor._mr_snapshot=lambda ns:(state,feature)
        actor._mr_last_snapshot='risk:1'
        actor._tier_allows_increase=lambda *args:stock_allowed
        actor._mr_liabilities=lambda ns,proposed=None:tuple(liabilities)+(() if proposed is None else (proposed,))
        actor._pair=dict(parent='ORIGINAL',caps=NS(sol_lot=D('.1'),bmax=abs(state.btc)),entry_sent=True,entry_terminal=False,entry_band='MEDIUM',quantity=D(0),generation=0,atr=D(2),consumed=set(),tp_lots={})
        actor._split_parent=dict(episode_id='ORIGINAL',quantity=D(550),first_quantity=D(275),filled=D(275),first_filled=D(275),deadline_ns=14_400_000_000_000,fallback=False,closed=False)
        actor._pair_arm_btc_debt=lambda ns:None
        actor._test_forced=[];actor._begin_forced_close=lambda reason,*args:actor._test_forced.append(reason)
        return actor,deepcopy(actor._split_parent)

    def test_known_benefit_and_stock_denials_create_no_entry_or_allocation(self):
        from coinmaster.strategy.method_a_risk import State,Features
        state=State(D(275),D(0),D(10000),D(10000),D(100),D(100))
        normal=Features(0,0,0,D(1),D(1),D('.095'),D('.1'),D('.1'),D('.01'),D('.0003'),D('.0003'))
        adverse=dr(normal,residual=D('.4'))
        for feature,stock,reason in ((adverse,True,'FULL_TARGET_BENEFIT_HURDLE'),(normal,False,'CURRENT_NATIVE_STOCK_GUARD')):
            actor,original=self.denial_actor(state,feature,stock)
            decision=actor._pair_submit(actor.config.sol_id,-1,D('130.6'),'ENTRY',123)
            self.assertEqual((decision.status,decision.reason),('DENY',reason))
            self.assertIsNone(decision.native_order_id);self.assertFalse(actor._mr_allocated);self.assertFalse(actor._mr_failed)
            self.assertEqual(actor._pair_orders,{});self.assertEqual(actor._pair_seen_fills,set());self.assertEqual(actor._split_parent,original)
            self.assertEqual(actor._test_forced,[])

    def test_known_all_partial_envelope_denial_is_not_transport_fault(self):
        from coinmaster.strategy.method_a_risk import State,Features,Liability,TAKER,RESERVE
        state=State(D(550),D(0),D('5982.295375'),D(10000),D('92.6'),D(100))
        feature=Features(0,0,0,D('1.205846711019932600346124964'),D('.9956960364932228545501451570'),D('.01108304617753870851535862821'),D('.01342222354156980922129954289'),D('.015672393400768784539637486'),D('.00180796292411156648851052033'),D(0),D(0))
        rights=(Liability('BTC_TP_NATIVE_LOTS','BTC',-1,550000,D('.001'),True,state.pb*(TAKER+RESERVE)),)
        actor,original=self.denial_actor(state,feature,True,rights)
        decision=actor._pair_submit(actor.config.sol_id,-1,D('420.5'),'ENTRY',123)
        self.assertEqual((decision.status,decision.reason),('DENY','JOINT_EXECUTION_ENVELOPE'))
        self.assertFalse(actor._mr_allocated);self.assertFalse(actor._mr_failed);self.assertEqual(actor._pair_orders,{})
        self.assertEqual(actor._split_parent,original);self.assertEqual(actor._test_forced,[])

    def test_unknown_current_margin_still_fails_closed_without_entry(self):
        from coinmaster.strategy.method_a_risk import State,Features
        state=State(D(275),D(0),D(10000),D(10000),D(100),D(100))
        feature=Features(0,0,0,D(1),D(1),D('.095'),D('.1'),D('.1'),D('.01'),D(0),D(0))
        actor,original=self.denial_actor(state,feature)
        def unknown(ns):raise ValueError('UNKNOWN_NATIVE_MARGIN')
        actor._mr_snapshot=unknown
        decision=actor._pair_submit(actor.config.sol_id,-1,D('130.6'),'ENTRY',123)
        self.assertEqual((decision.status,decision.reason),('UNKNOWN','UNKNOWN_NATIVE_MARGIN'))
        self.assertTrue(actor._mr_failed);self.assertFalse(actor._mr_allocated);self.assertEqual(actor._pair_orders,{})
        self.assertEqual(actor._pair_seen_fills,set());self.assertEqual(actor._test_forced,['METHOD_A_UNKNOWN_NATIVE_MARGIN'])

    def test_durable_checkpoint_false_remains_transport_failure(self):
        from coinmaster.strategy.method_a_risk import State,Features
        class DurableBase:
            def _record_submission(self,*args):return False
            def _pair_fail(self,reason,ns):self.failures.append(reason)
        class Probe(MethodARiskResearch,DurableBase):
            def __init__(self):
                self.config=NS(research_method_a_risk='HEDGE',btc_id=BTC_PERP.id,sol_id=SOL_PERP.id)
                self.clock=TestClock();self.cache=Cache();self.cache.add_instrument(SOL_PERP)
                self._mr_failed=False;self._forced_close_reason=None;self._liquidating=False;self._mr_allocated=False
                self._mr_last_snapshot='risk:1';self._mr_creation_snapshot='risk:1';self._mr_recovery_ref=None
                self._mr_submission_results={};self._mr_denied_intents=set();self._pair_orders={};self._ma_commands={};self._pair={'parent':'P'}
                self._domain=NS(episode=None);self.failures=[];self.forced=[];self.logs=[]
            def _mr_snapshot(self,ns):return State(D(275),D(0),D(10000),D(10000),D(100),D(100)),Features(0,0,0,D(1),D(1),D('.095'),D('.1'),D('.1'),D('.01'),D(0),D(0))
            def _mr_liabilities(self,ns,proposed=None,exclude=None):return (proposed,)
            def _mr_margin(self,*args):return D(0),D(0)
            def _mr_envelope(self,*args):return NS(safe=True,states=2,worst_deficit=D(-100),margin_pass=True)
            def _mr_original_second(self):return None
            def _mr_log(self,*args,**kwargs):self.logs.append((args,kwargs))
            def _begin_forced_close(self,reason):self.forced.append(reason)
        probe=Probe();factory=OrderFactory(TraderId('EXAMPLE-001'),StrategyId('MethodA-001'),probe.clock)
        order=factory.market(instrument_id=SOL_PERP.id,order_side=OrderSide.SELL,quantity=SOL_PERP.make_qty(D('130.6')),time_in_force=TimeInForce.IOC)
        self.assertFalse(probe._record_submission(order,'I','P','PAIRED_ENTRY'))
        self.assertEqual(probe._mr_submission_results[str(order.client_order_id)].status,'TRANSPORT_FAILURE')
        self.assertTrue(probe._mr_failed);self.assertFalse(probe._mr_allocated)
        self.assertEqual(probe.forced,['METHOD_A_DURABLE_SUBMIT_DENIED']);self.assertIsNone(probe.cache.order(order.client_order_id))

    def test_full_allow_native_factory_checkpoint_and_transport_call(self):
        from run_method_a_m1 import config
        from coinmaster.strategy.method_a_risk import State,Features
        from coinmaster.research.native_fixture import perpetual
        class DurableBase:
            def _record_submission(self,*args):self.checkpoints.append(args);return True
        class Probe(MethodARiskResearch,DurableBase):
            _pair_work=PairedPrefixResearch._pair_work
            _pair_valid_allocations=PairedPrefixResearch._pair_valid_allocations
            def __init__(self):
                cfg,_=config();self.config=replace(cfg,research_method_a_risk='HEDGE',research_sol_off=True)
                self.id=StrategyId('MethodA-001');self.clock=TestClock();self.clock.set_time(123)
                self.cache=Cache()
                for base in (BTC_PERP,SOL_PERP):
                    self.cache.add_instrument(perpetual(base.raw_symbol.value,base.base_currency,str(base.price_increment),str(base.size_increment),str(base.margin_init),D('.00020'),D('.00055')))
                from nautilus_trader.model.data import QuoteTick
                sol=self.cache.instrument(SOL_PERP.id)
                self.cache.add_quote_tick(QuoteTick(sol.id,sol.make_price(D(100)),sol.make_price(D(100)),sol.make_qty(D(1000)),sol.make_qty(D(1000)),123,123))
                self.order_factory=OrderFactory(TraderId('EXAMPLE-001'),self.id,self.clock)
                self._mr_failed=False;self._forced_close_reason=None;self._liquidating=False;self._mr_allocated=False;self._mr_submission_results={}
                self._mr_last_snapshot='risk:1';self._mr_creation_snapshot='risk:1';self._mr_recovery_ref=None;self._mr_denied_intents=set()
                self._pair_orders={};self._pending_by_order={};self._ma_commands={}
                self._pair=dict(parent='P',side=1,generation=0,caps=NS(sol_lot=D('.1')),entry_sent=False,entry_terminal=True,entry_band='MEDIUM',atr=D(2),tp_lots={},consumed=set())
                self.checkpoints=[];self.sent=[];self.logs=[];self.guards=[]
            def _mr_snapshot(self,ns):return State(D(1),D(0),D(5014),D(10000),D(100),D(100)),Features(0,0,0,D(1),D(1),D('.095'),D('.1'),D('.1'),D('.01'),D('.0003'),D('.0003'))
            def _tier_allows_increase(self,*args):self.guards.append(args);return True
            def _mr_original_second(self):return None
            def _mr_log(self,*args,**kw):self.logs.append((args,kw))
            def _pair_log(self,*args,**kw):self.logs.append((args,kw))
            def _mr_fail(self,*args):raise AssertionError(args)
            def submit_order(self,order):self.sent.append(order)  # No engine or fill.
        probe=Probe();decision=probe._pair_submit(SOL_PERP.id,-1,D('.4'),'ENTRY',123)
        self.assertEqual(decision.status,'ALLOW');self.assertEqual(len(probe.guards),1);self.assertEqual(len(probe.checkpoints),1);self.assertEqual(len(probe.sent),1)
        order=probe.sent[0];oid=str(order.client_order_id)
        self.assertEqual(order.order_type,OrderType.MARKET);self.assertEqual(order.time_in_force,TimeInForce.IOC);self.assertFalse(order.is_reduce_only)
        self.assertEqual(order.quantity.as_decimal(),D('.4'));self.assertEqual(order.status.name,'INITIALIZED')
        self.assertTrue(probe._mr_allocated);self.assertFalse(probe._pair_orders[oid]['accepted']);self.assertIsNone(probe._pair_orders[oid]['ack'])
        self.assertEqual(probe._pair_orders[oid]['initialized_event_id'],str(order.init_event.id));self.assertEqual(probe._mr_submission_results[oid].status,'ALLOW')
        self.assertIsNone(probe.cache.order(order.client_order_id));self.assertEqual(probe.cache.positions_open(),[])
        from dataclasses import asdict
        self.__class__.allow_example=wire(dict(schema=SCHEMA,scope='ENGINE_FREE_ALLOW_FACTORY_CHECKPOINT_WITH_TRANSPORT_SPY_ONLY',qualified=False,engine_constructors=0,decision=asdict(decision),native_order=order.to_dict(),native_initialized_event_id=str(order.init_event.id),durable_checkpoint_calls=len(probe.checkpoints),stock_guard_calls=len(probe.guards),transport_spy_calls=len(probe.sent),native_registered_order=False,native_fills=0,native_ACK_credit=False,allocation_used=probe._mr_allocated))

    def test_public_types_roundtrip(self):
        example=public_example();self.assertEqual(json.loads(json.dumps(example)),example)
        self.assertEqual(example['nested_examples']['native_fill']['type'],'OrderFilled')
        self.assertFalse(example['qualified'])

if __name__=='__main__':unittest.main()
