"""Public-data and report-only bindings. No native engine construction."""
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace as NS
from decimal import Decimal as D
from dataclasses import replace as dr
from msgspec.structs import replace
from nautilus_trader.cache.cache import Cache
from nautilus_trader.model.data import QuoteTick
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
from coinmaster.strategy.method_a_risk import Observation,Funding,lagged_features,DAY,MINUTE
from coinmaster.strategy.method_a_risk_native import MethodARiskResearch
from method_a_sol_public import prepare_case,native_inputs,SCHEMA
from run_method_a_m1 import config,seed


class PublicInputs(unittest.TestCase):
    def test_exact_public_rows_and_complete_quote_universe(self):
        case=dict(schema=SCHEMA,case_id='M2',risk_mode='HEDGE',cancel_latency_ns=0,selection_rows=[],funding_history='KNOWN_ZERO_8H_FEATURE_ONLY_W30',required_witnesses=[],rows=[dict(ns=0,marks={'BTC':'100','SOL':'100'},daily_session=729,quotes=[dict(asset='SOL',bid='100',ask='100',bid_depth='10',ask_depth='10'),dict(asset='BTC',bid='100',ask='100',bid_depth='275',ask_depth='275')])])
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'case.json';path.write_text(json.dumps(case));prepared=prepare_case(path)
        self.assertEqual(prepared['quote_universe'],{'BTC':1,'SOL':1})
        self.assertEqual(prepared['quote_count'],2);self.assertEqual(prepared['engine_constructors'],0)
        self.assertEqual([r['global_input_index'] for r in prepared['public_inputs'] if r['type']=='QuoteTick'],[1,2])
        groups=native_inputs(case['rows'][0]);daily=[type(x.data).__name__ for _,events,_ in groups for x in events if hasattr(x,'data') and type(x.data).__name__=='DailySignalBar']
        self.assertEqual(daily,['DailySignalBar','DailySignalBar'])
        quote=groups[-1][1][0];payload=quote.to_dict(quote)
        self.assertEqual(QuoteTick.from_dict(payload).to_dict(QuoteTick.from_dict(payload)),payload)

    def test_shared_runner_root_go_false_cannot_construct_engine(self):
        import run_method_a_sol as runner
        from unittest.mock import patch
        from run_method_a_m1 import source_seal
        import subprocess
        case=Path(__file__).resolve().parents[2]/'reports/method-a-verification-20261027/recipe-drafts-owner/M2.json'
        proof=runner.prepare(case)
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        with tempfile.TemporaryDirectory() as temp:
            seal=Path(temp)/'seal.json';seal.write_text(json.dumps(source_seal(commit)))
            import hashlib
            gate=Path(temp)/'gate.json';gate.write_text(json.dumps(dict(source_seal_path=str(seal),source_seal_sha256=hashlib.sha256(seal.read_bytes()).hexdigest(),source_commit=commit,case_id='M2',purpose='METHOD_A_REGISTERED_ENGINEERING_CASE',root_go=False)))
            with patch.object(runner,'BacktestEngine',side_effect=AssertionError('FORBIDDEN_ENGINE_CONSTRUCTOR')) as constructor:
                with self.assertRaises(AssertionError):runner.launch(case,gate)
                constructor.assert_not_called()
        self.assertEqual(proof['engine_constructors'],0)

    def test_actual_selection_consumption_binds_intraday_raw_row(self):
        from coinmaster.research.paired_signal_feed import PairedSignal
        from coinmaster.strategy.method_a_risk import State,Features
        class CapturedTransition(Exception):pass
        signals=tuple(PairedSignal(t,t,t+MINUTE,D(100),D(100),D('.5'),D(2),True,True,True,False,False,D(110),D(90),D(100)) for t in (0,4*3600*10**9))
        class Probe(MethodARiskResearch):
            def __init__(self):
                self.config=NS(btc_id=BTC_PERP.id,sol_id=SOL_PERP.id,research_method_a_selection=signals)
                self._pair=None;self._mr_parent='P';self._domain=NS(episode=NS(id='P'))
                self._mr_on=False;self._mr_allocated=False;self._mr_last_episode_day=None;self._mr_selection=None;self._mr_selection_ref=None;self._mr_signal_index=0
                self._forced_close_reason=None;self._liquidating=False;self.terminal_lifecycle={};self._pair_last_quote={}
                self._mr_sequence=0;self._mr_episode=0;self._mr_last_snapshot='risk:old';self._mr_inputs_ref='risk:header';self._mr_off_since=None;self.method_a_risk_audit=[]
            def _pair_sol_retire_check(self,*args):pass
            def _pair_qty(self,*args):return D(275)
            def _pair_work(self,*args,**kwargs):return []
            def _mr_snapshot(self,*args):return State(D(275),D(0),D(5530),D(10000),D('83.8'),D(100)),Features(0,0,0,D(1),D(1),D('.01'),D('.012'),D('.015'),D('.002'),D(0),D(0))
            def _mr_log(self,event,ns,**fields):
                row=super()._mr_log(event,ns,**fields)
                if event=='RISK_BAND_TRANSITION':raise CapturedTransition
                return row
        probe=Probe()
        with self.assertRaises(CapturedTransition):probe._mr_quote(NS(ts_event=5*3600*10**9,instrument_id=BTC_PERP.id))
        rows=probe.method_a_risk_audit;self.assertEqual([r['event'] for r in rows],['RISK_SELECTION_INPUT','RISK_SELECTION_INPUT','RISK_BAND_TRANSITION'])
        self.assertEqual(rows[1]['input_index'],1);self.assertEqual(rows[1]['raw_selection']['decision_ns'],4*3600*10**9)
        self.assertEqual(rows[-1]['selection_ref'],'risk:2');self.assertEqual(rows[-1]['inputs_ref'],'risk:header')

    def test_header_binds_raw_inputs_and_native_fee_profile(self):
        cfg,_=config();bars=seed()[:729]
        observations=tuple(Observation(int(b.close_time.timestamp()*10**9),int(b.close_time.timestamp()*10**9)+MINUTE,D(str(b.btc_close)),D(str(b.sol_close))) for b in bars)
        first=observations[-31].end_ns;last=observations[-1].end_ns;step=DAY//3
        funding=tuple(Funding(leg,t,t,D(0),step) for leg in ('BTC','SOL') for t in range(first+step,last+1,step))
        feature=lagged_features(observations,funding,0)
        binding=dict(source={'fixture':'actual immutable test source'},config={'variant':'P3'},data={'seed_sha256':__import__('run_method_a_m1').SEED_SHA256},policy={'BASE':'maker .00020 / taker .00055'})
        class Probe(MethodARiskResearch):
            def __init__(self):
                self.config=replace(cfg,research_method_a_risk='HEDGE',research_method_a_input_binding=binding,candidate=dr(cfg.candidate,sol_overlay_enabled=False))
                from coinmaster.research.native_fixture import perpetual
                self.cache=Cache()
                for base in (BTC_PERP,SOL_PERP):self.cache.add_instrument(perpetual(base.raw_symbol.value,base.base_currency,str(base.price_increment),str(base.size_increment),str(base.margin_init),maker_fee=D('.00020'),taker_fee=D('.00055')))
                self._domain=NS(episode=None);self._mr_sequence=0;self._mr_episode=0;self._mr_last_snapshot=None;self._mr_inputs_ref=None;self._mr_selection_ref=None;self.method_a_risk_audit=[]
        probe=Probe();probe._mr_emit_inputs(0,observations,funding,feature)
        row=json.loads(json.dumps(probe.method_a_risk_audit[0]))
        self.assertEqual(row['inputs_ref'],'risk:1');self.assertEqual(row['event'],'RISK_INPUTS')
        self.assertEqual(len(row['observations']),31);self.assertEqual(len(row['funding_history']),180)
        self.assertEqual(set(row['captured_profile']['tiers']),{'BTCUSDT','SOLUSDT'})
        self.assertEqual(row['input_binding'],binding)
        self.assertTrue(all(D(i['maker_fee'])==D('.00020') and D(i['taker_fee'])==D('.00055') for i in row['native_instruments']))
        self.assertFalse(row['effective_flags']['standalone_sol_enabled'])
        self.__class__.header_example=row
