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

    def test_public_types_roundtrip(self):
        example=public_example();self.assertEqual(json.loads(json.dumps(example)),example)
        self.assertEqual(example['nested_examples']['native_fill']['type'],'OrderFilled')
        self.assertFalse(example['qualified'])

if __name__=='__main__':unittest.main()
