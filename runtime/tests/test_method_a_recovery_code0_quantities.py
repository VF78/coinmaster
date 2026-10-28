"""New owner-authorized quantity delta only; actual Cache/Position/Account."""
import json
import unittest
from decimal import Decimal as D
from dataclasses import replace
from types import SimpleNamespace as NS
from pathlib import Path
from test_method_a_recovery_code0 import Probe,STATE,FEATURE,UUID4,OrderFilled,OrderSide,OrderType,USDT,Money,LiquiditySide,TradeId,PositionId,VenueOrderId
from nautilus_trader.model.events import OrderUpdated,AccountState
from nautilus_trader.model.enums import OmsType,AccountType
from nautilus_trader.model.objects import AccountBalance,MarginBalance
from nautilus_trader.model.position import Position
from nautilus_trader.accounting.accounts.margin import MarginAccount
from coinmaster.strategy.method_a_risk_native import MethodARiskResearch
from coinmaster.strategy.method_a_risk import evaluate,DAY


def large_actual_cache():
    p=Probe(account_id='P1SIM-EXAMPLE');btc=p.btc_order
    p.config.research_method_a_input_binding=dict(source='a4ed258+APPROVED_QUANTITY_DIFF',config='CODE0_ENGINE_FREE',data='SYNTHETIC_NATIVE_CACHE_BTC2_SOL200',policy='FROZEN_PROFILE')
    # Current native remaining TP2BTC <= actual held2BTC. Original completed
    #315.25BTC fills keep their existing maker-price/fee provenance unchanged.
    e=OrderUpdated(p.trader,p.id,p.btc.id,btc.client_order_id,btc.venue_order_id,p.account,p.btc.make_qty(D('317.250')),btc.price,None,UUID4(),p.ns,p.ns)
    btc.apply(e);p.cache.update_order(btc)
    for oid,owner,order in p._pair_work(instrument=p.sol.id,kinds={'TP','STOP'}):
        e=OrderUpdated(p.trader,p.id,p.sol.id,order.client_order_id,order.venue_order_id,p.account,p.sol.make_qty(D(200)),order.price if owner['kind']=='TP' else None,order.trigger_price if owner['kind']=='STOP' else None,UUID4(),p.ns,p.ns)
        order.apply(e);p.cache.update_order(order)
        owner['ack']=(D(200),owner['ack'][1],owner['ack'][2]);owner['last_ack_event_id']=str(e.id)
    # Construct actual native positions from public fill events. BTC's prior
    #TP fills are applied to its original317.25 entry, yielding exactly2BTC.
    for inst,side,qty,price,posid in ((p.btc,OrderSide.BUY,D('317.250'),D(107),'BTC-POS'),(p.sol,OrderSide.SELL,D(200),D('132.9'),'SOL-POS')):
        order=p.order_factory.market(instrument_id=inst.id,order_side=side,quantity=inst.make_qty(qty))
        fill=OrderFilled(p.trader,p.id,inst.id,order.client_order_id,VenueOrderId('ORIGINAL-'+posid),p.account,TradeId('ORIGINAL-'+posid),PositionId(posid),side,OrderType.MARKET,inst.make_qty(qty),inst.make_price(price),USDT,Money(qty*price*D('.00055'),USDT),LiquiditySide.TAKER,UUID4(),p.ns-4,p.ns-4)
        position=Position(inst,fill)
        if inst.id==p.btc.id:
            position.apply(next(e for e in btc.events if type(e).__name__=='OrderFilled'))
        p.cache.add_position(position,OmsType.NETTING)
    margins=[];locked=D(0)
    for leg,inst,qty,price in (('BTC',p.btc,D(2),D(107)),('SOL',p.sol,D(200),D('132.9'))):
        im,mm=p._mr_margin(leg,qty,price);locked+=im+mm
        margins.append(MarginBalance(Money(im,USDT),Money(mm,USDT),inst.id))
    account=MarginAccount(AccountState(p.account,AccountType.MARGIN,USDT,False,[AccountBalance(Money(D(5500),USDT),Money(locked,USDT),Money(D(5500)-locked,USDT))],margins,{},UUID4(),p.ns,p.ns))
    p.cache.add_account(account)
    p._mr_peak=D(10000);p._mr_cached_feature_key=p.ns//DAY;p._mr_cached_feature=FEATURE
    p.config.research_method_a_peak_source=NS(unknown=False,events=NS(peak={'equity':'10000'}),sequence=1,epoch='TEST')
    for mark in p._latest_marks.values():mark.ts_event=p.ns;mark.ts_init=p.ns
    state,feature=MethodARiskResearch._mr_snapshot(p,p.ns)
    p.state=state;p.feature=feature
    return p,state,feature


class ActualQuantityDelta(unittest.TestCase):
    def test_larger_actual_cache_snapshot_and_native_limit_dispatch(self):
        p,state,feature=large_actual_cache()
        self.assertEqual((state.btc,state.sol,state.equity,state.peak,state.cushion),(D(2),-D(200),D(5500),D(10000),D(500)))
        self.assertEqual(len(p.cache.positions_open()),2)
        liabilities=p._mr_liabilities(p.ns);old=p._mr_code0_old(state,feature,liabilities,p.ns)
        self.assertEqual((old[0].lots,old[0].lot),(2000,D('.001')))
        self.assertGreater(evaluate(state,feature,p._mr_margin).worst_deficit,0)
        self.assertFalse(p._mr_envelope(state,feature,liabilities).safe)
        choice=p._mr_recovery_choice('SOL',state,feature,liabilities,evaluate(state,feature,p._mr_margin).worst_deficit,p.ns)
        self.assertIsNotNone(choice);self.assertEqual(choice[0],2000)
        proof=choice[4];self.assertLessEqual(D(proof['route']),D(proof['baseline']));self.assertLess(D(proof['full']),0)
        p._pair_submit(p.sol.id,1,D(200),'SOL_CAP',p.ns)
        self.assertEqual(len(p.sent),1);native=p.sent[0]
        self.assertEqual((native.order_type.name,native.time_in_force.name,native.is_reduce_only,str(native.quantity),str(native.price)),('LIMIT','IOC',True,'200.0','133.03'))
        self.assertEqual(json.loads(json.dumps(native.to_dict())),native.to_dict())
        self.assertEqual((p.state.btc,p.state.sol,p.state.equity),(D(2),-D(200),D(5500)))
        self.__class__.proof=proof;self.__class__.native=native.to_dict()
        self.__class__.snapshot=next(kw for args,kw in p.logs if args[0]=='NATIVE_SNAPSHOT')

    def test_original_captured70_regression(self):
        p=Probe();liabilities=p._mr_liabilities(p.ns)
        choice=p._mr_recovery_choice('SOL',STATE,FEATURE,liabilities,evaluate(STATE,FEATURE,p._mr_margin).worst_deficit,p.ns)
        self.assertEqual(choice[0],1329)
        self.assertEqual(D(choice[4]['baseline']),D('35.2044175723066680672513309359253634779200290912681790379146920'))
        self.assertEqual(choice[4]['native_price'],'133.03')

    def test_quantity_tier_crossing_and_unresolved_universe_remain_unknown(self):
        p,state,feature=large_actual_cache();liabilities=p._mr_liabilities(p.ns)
        for state in (replace(state,sol=-D(400)),replace(state,btc=D(3000))):
            with self.assertRaisesRegex(ValueError,'CODE0_UNKNOWN_TIER'):p._mr_code0_old(state,feature,liabilities,p.ns)
        p._ma_commands[str(p.btc_order.client_order_id)]={'total':D('317.250'),'price':D('105.2')}
        with self.assertRaisesRegex(ValueError,'CODE0_UNKNOWN_NATIVE_ACK'):p._mr_code0_old(p.state,feature,liabilities,p.ns)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls,'proof'):
            target=Path(__file__).resolve().parents[2]/'reports/method-a-verification-20261027/code0-quantity-generalization-20261028'
            target.mkdir(exist_ok=True)
            (target/'LARGER_ACTUAL_CACHE_PROOF.json').write_text(json.dumps(dict(scope='ENGINE_FREE_PUBLIC_NATIVE_CACHE_POSITION_ACCOUNT_ORDER_ONLY',native_attempts=0,engine_constructors=0,positions={'BTC':'2','SOL':'-200'},equity='5500',peak='10000',cushion='500',known_working_BTC_TP_leaves='2',route_proof=cls.proof,native_order=cls.native,native_snapshot=cls.snapshot,financial_qualified=False),indent=2)+'\n')

if __name__=='__main__':unittest.main()
