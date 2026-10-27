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
                self.cache=Cache();self.cache.add_instrument(BTC_PERP);self.cache.add_instrument(SOL_PERP)
                self._domain=NS(episode=None);self._mr_sequence=0;self._mr_episode=0;self._mr_last_snapshot=None;self._mr_inputs_ref=None;self.method_a_risk_audit=[]
        probe=Probe();probe._mr_emit_inputs(0,observations,funding,feature)
        row=json.loads(json.dumps(probe.method_a_risk_audit[0]))
        self.assertEqual(row['inputs_ref'],'risk:1');self.assertEqual(row['event'],'RISK_INPUTS')
        self.assertEqual(len(row['observations']),31);self.assertEqual(len(row['funding_history']),180)
        self.assertEqual(set(row['captured_profile']['tiers']),{'BTCUSDT','SOLUSDT'})
        self.assertEqual(row['input_binding'],binding)
        self.assertFalse(row['effective_flags']['standalone_sol_enabled'])
        self.__class__.header_example=row
