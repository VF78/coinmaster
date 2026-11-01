"""Purpose-only protective exits: exact native-fee callback fakes, engine zero."""
import ast
from copy import deepcopy
from dataclasses import replace
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace as N
import unittest
from coinmaster.strategy.cm2_policy import Config,Features,Snapshot,State,decide,positive_harvest,HOUR_NS
from coinmaster.strategy.cm2_native import CM2Strategy
from nautilus_trader.model.enums import OrderSide

class StopPurposeTests(unittest.TestCase):
    def inputs(self,d,consumed=False):
        f=Features(201*HOUR_NS,201*HOUR_NS,True,close=990 if d>0 else 1010,
            channel_high=1100,channel_low=900,atr=10,execution_atr=10,beta=1,beta_guard=1,rho=.8,hedge_valid=True)
        s=Snapshot(D(10000),D(d),D(0),D(1001 if d>0 else 999),D(100),
            btc_vwap=D(1000),btc_entry_fees=D('.432'),btc_signed_funding=D(0))
        st=State(direction=d,parent=1,btc_target=D(d)*D('.75'),unhedged_btc_target=D(d),initial_r=30,
            stop=1040 if d>0 else 960,extreme=1070 if d>0 else 930,last_hour=200*HOUR_NS,
            btc_intent='POSITIVE_HARVEST',intent_hour=200*HOUR_NS,harvest_target=D(d)*D('.75'),
            harvest_start_qty=D(d),harvested=consumed)
        return f,s,st
    def test_pending_harvest_stop_is_risk_callback_not_false_quarantine_both_sides(self):
        class ID(str):venue='SIM'
        btc=ID('BTC')
        cfg=Config(parent_risk_fraction=1,initial_band_atr=1,mode="btc_only")
        for d in (1,-1):
            for consumed in (False,True):
                f,s,st=self.inputs(d,consumed);self.assertTrue(positive_harvest(s))
                decision=decide(cfg,f,s,st,now_ns=f.available_ns+1)
                self.assertEqual(decision.reason,'PROTECTIVE_STOP');self.assertTrue(decision.state.draining)
                self.assertEqual(decision.btc_target,D(0));self.assertEqual(decision.state.btc_intent,'RISK_TRIM')
                self.assertEqual(decision.state.intent_hour,0)
                self.assertIsNone(decision.state.harvest_target);self.assertIsNone(decision.state.harvest_start_qty)
                self.assertEqual(decision.state.harvested,consumed)
                old={'reduce_only':True,'admission':{'parent':1,'intent':'POSITIVE_HARVEST'}};before=deepcopy(old)
                fake=N(config=N(btc_id=btc,execution_policy_hash='PURE_RISK_CALLBACK'),policy_state=decision.state,
                    _seen_trade_ids=set(),_order_audit={'old-harvest':old,'new-stop':{'reduce_only':True,
                        'reason':decision.reason,'admission':{'parent':1,'intent':decision.state.btc_intent}}},
                    fill_audit=[],_entry_fees=D('.432'),_btc_cost_qty=D(1),_parent_funding=D(0),_parent_cost_known=True,
                    _restore_failed=False,_liquidating=False,_sync_funding=lambda:None,_terminal_event=lambda *a,**k:None,
                    _persist_checkpoint=lambda:None,_chain_audit=lambda *a:None)
                fake._actual_harvest_fill_geometry=lambda *a:(_ for _ in ()).throw(AssertionError('RISK_EXIT_MISCLASSIFIED'))
                price=D(999 if d>0 else 1001)
                event=N(trade_id='PURE_CALLBACK_NO_NATIVE_FILL',client_order_id='new-stop',instrument_id=btc,
                    commission=N(as_decimal=lambda:price*D('.000432'),currency='USDC'),
                    order_side=OrderSide.SELL if d>0 else OrderSide.BUY,
                    last_qty=N(as_decimal=lambda:D(1)),last_px=N(as_decimal=lambda:price),liquidity_side='TAKER',ts_event=f.available_ns+1)
                from test_cm2_order_contract import Clock
                fake.clock=Clock(event.ts_event);fake.id='PURE_CALLBACK'
                fake._orders=lambda iid:[]
                if not hasattr(fake.config,'sol_id'):fake.config.sol_id='SOL'
                CM2Strategy.on_order_filled(fake,event)
                self.assertFalse(fake._restore_failed)
                self.assertNotIn('actual_harvest_geometry',fake.fill_audit[0])
                self.assertEqual(fake._order_audit['old-harvest'],before)
                self.assertEqual(fake.policy_state.harvested,consumed)
                fresh=replace(f,closed_ns=202*HOUR_NS,available_ns=202*HOUR_NS,
                    close=1100 if d>0 else 900,channel_high=1090 if d>0 else 1100,channel_low=900 if d>0 else 910)
                notflat=decide(cfg,fresh,s,fake.policy_state,now_ns=fresh.available_ns+1)
                self.assertEqual(notflat.btc_target,D(0));self.assertTrue(notflat.state.draining)
                flat=replace(s,btc_qty=D(0),btc_vwap=None,btc_entry_fees=D(0))
                clean=decide(cfg,f,flat,fake.policy_state,now_ns=f.available_ns+2)
                self.assertEqual(clean.reason,'DRAIN_COMPLETE');self.assertEqual(clean.state.parent,1)
                self.assertFalse(clean.state.draining)
                entry=decide(cfg,fresh,replace(flat,btc_mark=D(str(fresh.close))),clean.state,now_ns=fresh.available_ns+1)
                self.assertEqual(entry.reason,'BTC_BREAKOUT_ENTRY');self.assertGreater(entry.btc_target*D(d),0)
    def test_slow_regime_exit_revokes_populated_hour_and_harvest_rights(self):
        from coinmaster.strategy.cm2_policy import btc_child_permission
        for d in (1,-1):
            f,s,st=self.inputs(d)
            cfg=Config(core_signal="slow_d1_h4",parent_risk_fraction=1,initial_band_atr=1,mode="btc_only")
            f=replace(f,core_direction=-d,daily_close=1000,daily_atr=10)
            # Known stop stays unbreached: opposite slow regime is the sole exit.
            st=replace(st,stop=900 if d>0 else 1100)
            original=deepcopy(st)
            result=decide(cfg,f,s,st,now_ns=f.available_ns+1)
            self.assertEqual(result.reason,"SLOW_REGIME_EXIT")
            self.assertEqual((result.btc_target,result.sol_target),(D(0),D(0)))
            self.assertTrue(result.state.draining)
            self.assertEqual((result.state.btc_intent,result.state.intent_hour),("RISK_TRIM",0))
            self.assertIsNone(result.state.harvest_target);self.assertIsNone(result.state.harvest_start_qty)
            self.assertEqual(btc_child_permission(cfg,f,s,result.state,now_ns=f.available_ns+1,
                executable_price=s.btc_mark),(True,"SAFETY_OR_NO_ORDINARY_INTENT"))
            growth=replace(result.state,btc_target=s.btc_qty*2)
            self.assertEqual(btc_child_permission(cfg,f,s,growth,now_ns=f.available_ns+1,
                executable_price=s.btc_mark),(False,"NO_CURRENT_ORDINARY_INCREASE_RIGHT"))
            self.assertEqual(st,original)
            self.assertEqual((result.state.stop,result.state.initial_cash_risk,result.state.emergency_peak_equity),
                (st.stop,st.initial_cash_risk,st.emergency_peak_equity))

    def test_all_explicit_draining_replacements_revoke_ordinary_purpose(self):
        for name in ('cm2_policy.py','cm2_native.py'):
            tree=ast.parse((Path(__file__).parents[1]/'coinmaster/strategy'/name).read_text())
            count=0
            for call in ast.walk(tree):
                if not isinstance(call,ast.Call) or not isinstance(call.func,ast.Name) or call.func.id!='replace':continue
                kw={k.arg:k.value for k in call.keywords}
                if 'draining' not in kw or not isinstance(kw['draining'],ast.Constant) or kw['draining'].value is not True:continue
                count+=1
                self.assertEqual(ast.literal_eval(kw['btc_intent']),'RISK_TRIM')
                self.assertEqual(ast.literal_eval(kw['intent_hour']),0)
                self.assertIsNone(ast.literal_eval(kw['harvest_target']))
                self.assertIsNone(ast.literal_eval(kw['harvest_start_qty']))
            self.assertGreater(count,0)

if __name__=='__main__':unittest.main()
