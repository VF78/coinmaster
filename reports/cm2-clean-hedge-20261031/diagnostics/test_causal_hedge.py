"""Public/synthetic only: causal prefix and actual-native-schema properties."""
from dataclasses import asdict
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace
import unittest
import causal_hedge as helper
from coinmaster.strategy.cm2_policy import Hour,HOUR_NS,Config,features
from coinmaster.research.current_hl_profile import load_current_hl_diagnostic

ROOT=Path(__file__).resolve().parents[3]


class DiagnosticTests(unittest.TestCase):
    def seed(self):
        start=helper.START_MS*1_000_000
        return tuple(Hour(start+(i-168)*HOUR_NS,start+(i-168)*HOUR_NS,
            10000+i*2,10005+i*2,9995+i*2,10001+i*2,300+i*.03+(i%3)*.01) for i in range(169))
    def minutes(self):
        for i in range(120):
            btc={k:str(v) for k,v in dict(open=10400+i*.01234,high=10402+i*.02345,
                low=10398+i*.00456,close=10400+i*.03456).items()}
            sol={k:str(v) for k,v in dict(open=310+i*.001234,high=311+i*.002345,
                low=309+i*.000456,close=310+i*.003456).items()}
            yield SimpleNamespace(open_time_ms=helper.START_MS+i*60000,btc_execution=btc,sol_execution=sol)
    def test_source_rounding_hour_math_and_prefix(self):
        instruments=load_current_hl_diagnostic(ROOT/'runtime/tests/fixtures/hl-current-20261029').instruments
        minutes=list(self.minutes());seed=self.seed()
        full=list(helper.feature_rows(seed,minutes,instruments))
        prefix=list(helper.feature_rows(seed,minutes[:60],instruments))
        self.assertEqual(full[:2],prefix)
        rounded=[{k:float(instruments[0].make_price(m.btc_execution[k])) for k in ('open','high','low','close')} for m in minutes[:60]]
        t=(helper.START_MS+3600000)*1_000_000
        independent=Hour(t,t,rounded[0]['open'],max(x['high'] for x in rounded),
            min(x['low'] for x in rounded),rounded[-1]['close'],
            float(instruments[1].make_price(minutes[59].sol_execution['close'])))
        expected=asdict(features(tuple((*seed,independent)),Config(),t))
        self.assertEqual(full[1],expected)
        # Beta/stress math is invariant to trend-channel parameter over allowed T.
        common=('beta','beta_guard','rho','residual_z','common_loss','residual_loss','atr')
        for trend in (24,72,168):
            other=asdict(features(tuple((*seed,independent)),Config(trend_hours=trend),t))
            self.assertEqual({k:other[k] for k in common},{k:expected[k] for k in common})
    def test_asof_equality_and_stale(self):
        tape=helper.FeatureTape([{'available_ns':10,'closed_ns':10},{'available_ns':20,'closed_ns':20}])
        self.assertEqual(tape.asof(20)['available_ns'],20)
        self.assertEqual(tape.asof(20,strict=True)['available_ns'],10)
        self.assertIsNone(tape.asof(10,strict=True))
        self.assertIsNone(tape.asof(20+HOUR_NS+1))
    def row(self,seq,ns,btc=0,sol=0,kind='PREQUOTE_DIRECT_NATIVE'):
        positions=[{'instrument_id':s+'-USD-PERP.HYPERLIQUID','position_id':s+'-NATIVE-1',
            'quantity':str(abs(q)),'side':'LONG' if q>0 else 'SHORT','native_price':'100'}
            for s,q in (('BTC',btc),('SOL',sol)) if q]
        return dict(sequence=seq,event_ns=str(ns),receipt_ns=str(ns),epoch=0,state_epoch=0,
            kind=kind,positions=positions,native_id='FILL-'+str(seq))
    def test_native_episode_orphan_clock_and_retrospective_watermark(self):
        tape=helper.FeatureTape([dict(available_ns=0,closed_ns=0,valid=True,hedge_valid=True,
            beta=1,beta_guard=1.1,common_loss=.02,residual_loss=.005)])
        rows=[self.row(1,0),self.row(2,10,btc=2,kind='POST_FILL_COMMITTED_NATIVE'),
            self.row(3,10,btc=2,sol=-1,kind='POST_FILL_COMMITTED_NATIVE'),
            self.row(4,20,sol=-1,kind='POST_FILL_COMMITTED_NATIVE'),
            self.row(5,15,btc=2,kind='SETTLED_PRE_NEXT_SOURCE_WATERMARK'),self.row(6,27)]
        emitted=[];result=helper.audit_rows(rows,tape,D('.000432'),emitted.append)
        self.assertEqual(result['unknown'],[])
        self.assertEqual(len(result['native_inventory_episodes']),1)
        orphan=result['orphan_native_event_intervals'][0]
        self.assertEqual((orphan['start_event_ns'],orphan['end_event_ns'],orphan['native_event_clock_duration_ns']),('20','27','7'))
        self.assertEqual(result['counts']['opposite_sign_rows'],1)
        coex=next(x for x in emitted if x['sequence']==3)
        self.assertTrue(coex['risk_asof_le']['guard_nonflip'])
        self.assertEqual(result['native_inventory_episodes'][0]['business_parent_GUID'],'UNKNOWN')
    def test_missing_native_fields_and_model_flip_stay_limited(self):
        tape=helper.FeatureTape([dict(available_ns=0,closed_ns=0,valid=True,hedge_valid=True,
            beta=1,beta_guard=1.1,common_loss=.02,residual_loss=.005)])
        broken=self.row(1,0,btc=1);del broken['positions'][0]['side']
        result=helper.audit_rows([broken],tape,D('.000432'),lambda _:None)
        self.assertIn('NATIVE_POSITION_FIELDS_UNKNOWN',result['unknown'])
        metric=helper.model_metrics({'BTC':D(1),'SOL':D(-2)},{'BTC':D(100),'SOL':D(100)},tape.rows[0],D('.000432'))
        self.assertEqual(metric['status'],'MODEL_IMPLIED_ONLY')
        self.assertFalse(metric['guard_nonflip'])


if __name__=='__main__':unittest.main()
