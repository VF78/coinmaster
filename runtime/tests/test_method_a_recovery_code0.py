"""CODE0 focused actual public Cache/Order checks; engine imports blocked."""
import builtins
_original_import=builtins.__import__
def _no_engine(name,*args,**kwargs):
    if name.startswith('nautilus_trader.backtest') or 'matching_engine' in name:
        raise AssertionError('Engine construction/import forbidden by CODE0/native0')
    return _original_import(name,*args,**kwargs)
builtins.__import__=_no_engine
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from dataclasses import replace
from decimal import Decimal as D
from nautilus_trader.cache.cache import Cache
from nautilus_trader.common.component import TestClock
from nautilus_trader.common.factories import OrderFactory
from nautilus_trader.core.uuid import UUID4
from nautilus_trader.model.identifiers import TraderId,StrategyId,AccountId,VenueOrderId,TradeId,PositionId,InstrumentId,Symbol,Venue
from nautilus_trader.model.instruments import CryptoPerpetual
from nautilus_trader.model.currencies import BTC,SOL,USDT
from nautilus_trader.model.objects import Price,Quantity,Money
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.events import OrderSubmitted,OrderAccepted,OrderFilled,OrderTriggered
from nautilus_trader.model.enums import OrderSide,OrderType,TimeInForce,LiquiditySide
from coinmaster.strategy.method_a_risk import State,Features,Liability,evaluate,TAKER,RESERVE
from coinmaster.strategy.method_a_risk_native import MethodARiskResearch
from coinmaster.strategy.paired_prefix import PairedPrefixResearch
from coinmaster.strategy.method_a_recovery_code0 import recovery_limit,prove_flat_route
from coinmaster.venues.bybit_profile import BybitVenueProfile

STATE=State(D(1),-D('132.9'),D('5360.2863425'),D(10000),D(107),D('132.9'))
FEATURE=Features(0,0,0,D('1.205846711019932600346124964'),D('.9956960364932228545501451570'),D('.01108304617753870851535862821'),D('.01342222354156980922129954289'),D('.015672393400768784539637486'),D('.00180796292411156648851052033'),D(0),D(0))


def instrument(base,tick,lot,im,maker_fee=D('.00020')):
    return CryptoPerpetual(InstrumentId(Symbol(base.code+'USDT-PERP'),Venue('P1SIM')),Symbol(base.code+'USDT'),base,USDT,USDT,False,
        len(tick.split('.')[1]),len(lot.split('.')[1]),Price.from_str(tick),Quantity.from_str(lot),0,0,
        margin_init=D(im),margin_maint=D('.005'),maker_fee=maker_fee,taker_fee=TAKER)


class Durable:
    def _record_submission(self,*args):self.checkpoints.append(args);return True


class Probe(MethodARiskResearch,PairedPrefixResearch,Durable):
    def __init__(self,enabled=True,protection=True,sol_maker_fee=D('.00020'),btc_tick='0.1',account_id='SIM-EXAMPLE'):
        self.btc=instrument(BTC,btc_tick,'0.001','.025');self.sol=instrument(SOL,'0.01','0.1','.05',sol_maker_fee)
        profile=BybitVenueProfile.from_raw(Path(__file__).resolve().parents[1])
        self.config=NS(research_method_a_risk='HEDGE',research_method_a_recovery_code0=enabled,
            btc_id=self.btc.id,sol_id=self.sol.id,research_method_a_input_binding=dict(source='b03dacc+CODE0_DIFF',config='TEST',data='CAPTURED70',policy='FROZEN'),
            margin_policy=NS(_profile=profile,_selected_leverage={self.btc.id:D(40),self.sol.id:D(20)}))
        self.id=StrategyId('MethodA-001');self.trader=TraderId('EXAMPLE-001');self.account=AccountId(account_id)
        self.clock=TestClock();self.clock.set_time(70_000_000_000);self.ns=self.clock.timestamp_ns()
        self.cache=Cache();self.cache.add_instrument(self.btc);self.cache.add_instrument(self.sol)
        self.order_factory=OrderFactory(self.trader,self.id,self.clock)
        self.state=STATE;self.feature=FEATURE
        self._pair_orders={};self._ma_owners={};self._ma_commands={};self._pending_by_order={}
        self._latest_marks={self.btc.id:NS(price=STATE.pb),self.sol.id:NS(price=STATE.ps)}
        self._pair=dict(parent='P',generation=0,debt_since=self.ns)
        self._mr_failed=False;self._forced_close_reason=None;self._liquidating=False
        self._mr_last_stock_guard=None;self._mr_last_snapshot='risk:CAPTURED70';self._mr_creation_snapshot=None;self._mr_recovery_ref='recovery:CODE0'
        self._mr_submission_results={};self._mr_denied_intents=set();self.checkpoints=[];self.sent=[];self.logs=[]
        for inst,px in ((self.btc,STATE.pb),(self.sol,STATE.ps)):
            self.cache.add_quote_tick(QuoteTick(inst.id,inst.make_price(px),inst.make_price(px),inst.make_qty(D(1000)),inst.make_qty(D(1000)),self.ns,self.ns))
        btc=self.order_factory.limit(instrument_id=self.btc.id,order_side=OrderSide.SELL,quantity=self.btc.make_qty(D('316.250')),price=self.btc.make_price(D('105.2')),time_in_force=TimeInForce.GTC,reduce_only=True)
        self.accept(btc)
        fill=OrderFilled(self.trader,self.id,self.btc.id,btc.client_order_id,btc.venue_order_id,self.account,TradeId('ACTUAL-MAKER'),PositionId('BTC-POS'),OrderSide.SELL,OrderType.LIMIT,self.btc.make_qty(D('315.250')),btc.price,USDT,Money(D('315.250')*D('105.2')*D('.00020'),USDT),LiquiditySide.MAKER,UUID4(),self.ns-1,self.ns-1)
        btc.apply(fill);self.cache.add_order(btc);self.cache.update_order(btc);self.btc_order=btc
        self._ma_owners[str(btc.client_order_id)]=dict(parent='P',ack=True)
        if protection:
            for kind,price in (('TP',D(80)),('TP',D(60)),('TP',D(20)),('STOP',D(140))):
                kw=dict(instrument_id=self.sol.id,order_side=OrderSide.BUY,quantity=self.sol.make_qty(D('132.9')),reduce_only=True)
                order=(self.order_factory.stop_market(**kw,trigger_price=self.sol.make_price(price),time_in_force=TimeInForce.IOC) if kind=='STOP' else self.order_factory.limit(**kw,price=self.sol.make_price(price),time_in_force=TimeInForce.GTC))
                self.accept(order);self.cache.add_order(order);self.cache.update_order(order)
                self._pair_orders[str(order.client_order_id)]=dict(kind=kind,instrument=self.sol.id,parent='P',accepted=True,pending=None,ack=(D('132.9'),price if kind=='TP' else None,price if kind=='STOP' else None),last_ack_event_id=str(order.events[-1].id))
    def accept(self,order):
        common=(self.trader,self.id,order.instrument_id,order.client_order_id)
        order.apply(OrderSubmitted(*common,self.account,UUID4(),self.ns-3,self.ns-3))
        order.apply(OrderAccepted(*common,VenueOrderId('V-'+str(order.client_order_id)),self.account,UUID4(),self.ns-2,self.ns-2))
    def _pair_work(self,*,instrument=None,kinds=None):
        return [(oid,o,self.cache.order(__import__('nautilus_trader.model.identifiers',fromlist=['ClientOrderId']).ClientOrderId(oid))) for oid,o in self._pair_orders.items() if (instrument is None or o['instrument']==instrument) and (kinds is None or o['kind'] in kinds)]
    def _mr_snapshot(self,ns):return self.state,self.feature
    def _mr_original_second(self):return None
    def _mr_log(self,*args,**kw):self.logs.append((args,kw))
    def _pair_log(self,*args,**kw):self.logs.append((args,kw))
    def _mr_fail(self,*args):raise AssertionError(args)
    def submit_order(self,order):self.sent.append(order)


class Code0(unittest.TestCase):
    def test_buy_sell_tick_directions_and_unmarketable(self):
        price,cost=recovery_limit(side=1,mark=D('132.9'),cost_cap=D('.205995'),fee=TAKER,tick=D('.01'),bid=D('132.9'),ask=D('132.9'))
        self.assertEqual((price,cost),(D('133.03'),D('.2031665')))
        price,cost=recovery_limit(side=-1,mark=D(107),cost_cap=D('.16585'),fee=TAKER,tick=D('.1'),bid=D(107),ask=D(107))
        self.assertEqual(price,D('106.9'));self.assertLessEqual(cost,D('.16585'))
        with self.assertRaisesRegex(ValueError,'UNMARKETABLE'):
            recovery_limit(side=1,mark=D('132.9'),cost_cap=D('.205995'),fee=TAKER,tick=D('.01'),bid=D(134),ask=D(134))

    def test_captured70_baseline_all_partials_full_and_normal_admission(self):
        p=Probe();liabilities=p._mr_liabilities(p.ns);old=p._mr_code0_old(STATE,FEATURE,liabilities,p.ns)
        self.assertEqual(len(old),1);self.assertEqual(old[0].cost_per_unit,D('1.821040'))
        self.assertGreater(evaluate(STATE,FEATURE,p._mr_margin).worst_deficit,0)
        self.assertFalse(p._mr_envelope(STATE,FEATURE,liabilities).safe) # old strict admission is unchanged
        choice=p._mr_code0_choice('SOL',STATE,FEATURE,liabilities,p.ns)
        self.assertIsNotNone(choice);self.assertEqual(choice[0],1329)
        proof=choice[4];self.assertEqual(D(proof['baseline']),D('35.2044175723066680672513309359253634779200290912681790379146920'))
        self.assertLessEqual(D(proof['route']),D(proof['baseline']));self.assertLess(D(proof['full']),0)
        self.assertIsNone(p._mr_code0_choice('BTC',STATE,FEATURE,liabilities,p.ns))
        self.__class__.proof=proof

    def test_actual_limit_ioc_native_payload_checkpoint_no_pending_credit(self):
        p=Probe();p._pair_submit(p.sol.id,1,D('132.9'),'SOL_CAP',p.ns)
        self.assertEqual(len(p.checkpoints),1);self.assertEqual(len(p.sent),1)
        o=p.sent[0];self.assertEqual((o.order_type,o.time_in_force,o.is_reduce_only),(OrderType.LIMIT,TimeInForce.IOC,True))
        self.assertEqual(o.price.as_decimal(),D('133.03'));self.assertEqual(o.quantity.as_decimal(),D('132.9'))
        self.assertEqual(o.status.name,'INITIALIZED');self.assertIsNone(p.cache.order(o.client_order_id))
        self.assertEqual(p.state,STATE);self.assertEqual(p.cache.positions_open(),[])
        payload=o.to_dict();self.assertEqual(json.loads(json.dumps(payload)),payload)
        dispatch=[kw for args,kw in p.logs if args[0]=='BEFORE_NATIVE_DISPATCH'][-1]
        self.assertTrue(dispatch['recovery_code0']['no_pending_credit']);self.assertEqual(dispatch['pending_hedge_credit'],'0')
        self.__class__.payload=payload

    def test_old_sol_crossed_shock_or_current_book_denied(self):
        p=Probe();liabilities=p._mr_liabilities(p.ns)
        # Captured shocks stay strictly inside TP80 / STOP140.
        self.assertLess(max(STATE.ps*(1+s) for b,s in FEATURE.shocks()),D(140))
        with self.assertRaisesRegex(ValueError,'NOT_DORMANT'):
            p._mr_code0_old(STATE,replace(FEATURE,residual=D('.10')),liabilities,p.ns)
        p.cache.add_quote_tick(QuoteTick(p.sol.id,p.sol.make_price(D(141)),p.sol.make_price(D(141)),p.sol.make_qty(D(1000)),p.sol.make_qty(D(1000)),p.ns+1,p.ns+1))
        with self.assertRaisesRegex(ValueError,'NOT_DORMANT'):p._mr_code0_old(STATE,FEATURE,liabilities,p.ns+1)

    def test_pending_unknown_ack_sign_funding_and_tier_guards(self):
        p=Probe();liabilities=p._mr_liabilities(p.ns)
        for changed,feature,pattern in ((replace(STATE,btc=D('-1')),FEATURE,'SIGN_SIZE'),(STATE,replace(FEATURE,fund_s=D('.0001')),'FUNDING'),(replace(STATE,ps=D(1000)),FEATURE,'TIER')):
            with self.assertRaisesRegex(ValueError,pattern):p._mr_code0_old(changed,feature,liabilities,p.ns)
        owner=next(iter(p._pair_orders.values()));owner['pending']={'payload':(D('132.9'),D(80),None)}
        with self.assertRaisesRegex(ValueError,'PROTECTION_ACK'):p._mr_code0_old(STATE,FEATURE,liabilities,p.ns)
        owner['pending']=None;owner['last_ack_event_id']=None
        with self.assertRaisesRegex(ValueError,'PROTECTION_ACK'):p._mr_code0_old(STATE,FEATURE,liabilities,p.ns)
        p._ma_commands[str(p.btc_order.client_order_id)]={'total':D(1)}
        with self.assertRaisesRegex(ValueError,'NATIVE_ACK'):p._mr_code0_old(STATE,FEATURE,liabilities,p.ns)

    def test_wrong_side_and_per_native_fill_fee_rounding(self):
        p=Probe()
        with self.assertRaisesRegex(ValueError,'FULL_ROUTE_ONLY'):p._pair_submit(p.sol.id,-1,D('132.9'),'SOL_CAP',p.ns)
        self.assertEqual(p.sent,[])
        self.assertEqual(p._mr_code0_price('BTC',STATE,p.ns),(D('106.9'),D('.1588')))
        # Per-fill fee ceil at 1e-8 USDT is included for every minimal lot.
        self.assertGreater(D('.1588'),D('.158795'))

    def test_actual_working_tp_leaves_cannot_exceed_actual_btc(self):
        p=Probe();old=p._mr_liabilities(p.ns)
        with self.assertRaisesRegex(ValueError,'CODE0_UNKNOWN_OLD_BTC_TP'):
            p._mr_code0_old(replace(STATE,btc=D('.999')),FEATURE,old,p.ns)
        self.assertEqual(p.sent,[])

    def test_triggered_protection_unknown_fee_and_unmarketable_cap(self):
        p=Probe();stop=next(order for oid,owner,order in p._pair_work() if owner['kind']=='STOP')
        # Pinned native STOP_MARKET rejects a separate TRIGGERED event.
        # Test its actual trigger boundary without constructing a fake status.
        with self.assertRaisesRegex(ValueError,'can only trigger'):
            stop.apply(OrderTriggered(p.trader,p.id,p.sol.id,stop.client_order_id,stop.venue_order_id,p.account,UUID4(),p.ns,p.ns))
        with self.assertRaisesRegex(ValueError,'NOT_DORMANT'):
            p._mr_code0_old(replace(STATE,ps=D(140)),FEATURE,p._mr_liabilities(p.ns),p.ns)
        q=Probe(sol_maker_fee=D('.0003'))
        with self.assertRaisesRegex(ValueError,'UNKNOWN_LINEAR_USDT_FEES'):q._mr_code0_price('SOL',STATE,q.ns)
        r=Probe();r.cache.add_quote_tick(QuoteTick(r.sol.id,r.sol.make_price(D(134)),r.sol.make_price(D(134)),r.sol.make_qty(D(1000)),r.sol.make_qty(D(1000)),r.ns+1,r.ns+1))
        self.assertIsNone(r._mr_code0_choice('SOL',STATE,FEATURE,r._mr_liabilities(r.ns+1),r.ns+1))

    def test_actual_margin_failure_and_pending_debt_block_increases(self):
        p=Probe();old=p._mr_code0_old(STATE,FEATURE,p._mr_liabilities(p.ns),p.ns)
        with self.assertRaisesRegex(ValueError,'ACTUAL_BREACH_MARGIN'):
            prove_flat_route(STATE,FEATURE,old,'SOL',D('.1'),D('.2031665'),lambda leg,q,price:(D(100000),D(100000)),p._mr_tier_boundaries)
        # Even if a submitted increase would have a safe modeled envelope, debt
        # cannot clear until actual safe state is observed by normal callbacks.
        q=Probe(protection=False);q.state=replace(STATE,equity=D(10000))
        order=q.order_factory.market(instrument_id=q.btc.id,order_side=OrderSide.BUY,quantity=q.btc.make_qty(D('.001')),time_in_force=TimeInForce.IOC)
        self.assertFalse(q._record_submission(order,'I','P','BTC_ENTRY'))
        self.assertEqual(q.checkpoints,[]);self.assertEqual(q.sent,[])

    def test_actual_safe_state_never_borrows_new_benchmark(self):
        p=Probe();safe=replace(STATE,equity=D(10000))
        old=p._mr_code0_old(STATE,FEATURE,p._mr_liabilities(p.ns),p.ns)
        with self.assertRaisesRegex(ValueError,'ACTUAL_BREACH'):prove_flat_route(safe,FEATURE,old,'SOL',D('.1'),D('.2031665'),p._mr_margin,p._mr_tier_boundaries)

    def test_default_off_and_ordinary_positive_protection_commands(self):
        p=Probe(enabled=False,protection=False)
        # Test native stock command path directly, preserving MARKET IOC default.
        p._record_submission=lambda *args:Durable._record_submission(p,*args)
        p._pair_submit(p.sol.id,1,D('132.9'),'SOL_CAP',p.ns)
        self.assertEqual(p.sent[0].order_type,OrderType.MARKET)
        q=Probe();PairedPrefixResearch._pair_submit(q,q.sol.id,1,D('1'),'TP',q.ns,price=D(80))
        self.assertEqual((q.sent[0].order_type,q.sent[0].time_in_force),(OrderType.LIMIT,TimeInForce.GTC))
        r=Probe();PairedPrefixResearch._pair_submit(r,r.sol.id,1,D('1'),'STOP',r.ns,stop=D(140))
        self.assertEqual(r.sent[0].order_type,OrderType.STOP_MARKET)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'proof') and hasattr(cls,'payload'):
            target=Path(__file__).resolve().parents[2]/'reports/method-a-verification-20261027/code0-recovery-20261028'
            target.mkdir(exist_ok=True)
            (target/'FOCUSED_TEST_PROOF.json').write_text(json.dumps(dict(scope='ENGINE_FREE_PUBLIC_CACHE_ORDER_ONLY',engine_constructors=0,native_attempts=0,actual_fills=0,financial_qualified=False,route_proof=cls.proof,native_order=cls.payload,backtest_modules_loaded=[k for k in sys.modules if k.startswith('nautilus_trader.backtest')]),indent=2)+'\n')

if __name__=='__main__':unittest.main()
