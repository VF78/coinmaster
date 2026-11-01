"""v2 contract regressions: explicit examples, no native engine or monetary trial."""
from dataclasses import replace
from decimal import Decimal as D
from types import SimpleNamespace as N
import unittest
from coinmaster.strategy.cm2_policy import *
from coinmaster.strategy.cm2_execution import stage_targets,order_plan
from test_cm2_policy import feat,snap,state,configured,CausalityTests

class RepairV2Tests(unittest.TestCase):
    def test_stop_priority_both_signs_all_optional_hedge_states(self):
        for d in (1,-1):
            for eligible,known in ((True,True),(False,True),(False,False)):
                s=snap(btc_qty=D(d),btc_mark=D(90 if d>0 else 110),data_known=False,core_data_known=True)
                st=state(direction=d,btc_target=D(d),stop=95 if d>0 else 105,last_hour=200*HOUR_NS)
                result=decide(Config(),feat(hedge_valid=eligible,hedge_data_known=known),s,st)
                self.assertEqual((result.btc_target,result.reason),(D(0),'PROTECTIVE_STOP'))
                self.assertTrue(result.state.draining)
                self.assertEqual(s.btc_qty,D(d)) # intent never changes native actual inventory
    def test_unknown_btc_price_or_ownership_does_not_invent_crossing(self):
        for kwargs in ({'btc_price_known':False},{'ownership_known':False},{'unknown_orders':True}):
            s=snap(btc_mark=D(90),**kwargs)
            self.assertIsNone(evaluate_mandatory_risk(s,state(stop=95)))
    def test_known_ineligible_is_not_unknown_and_btc_calendar_survives(self):
        for d in (1,-1):
            st=state(direction=d,btc_target=D(d))
            result=decide(Config(),feat(hedge_valid=False,rho=.2),snap(btc_qty=D(d)),st)
            self.assertEqual(result.btc_target,D(d))
            self.assertNotIn('UNKNOWN',result.reason)
    def test_cancel_add_retains_useful_held_sol(self):
        for d in (1,-1):
            f=feat(close=1000,residual_z=-d*2,btc_return6=-d*.01)
            s=snap(btc_qty=D(d),sol_qty=D(-d),btc_mark=D(999 if d>0 else 1001))
            st=state(direction=d,btc_target=D(2*d),sol_target=D(-d),hedge_active=True,
                btc_intent='FAVORABLE_ADD',intent_hour=f.closed_ns,last_hour=f.closed_ns)
            result=decide(configured(),f,s,st)
            self.assertTrue(result.cancel_increases)
            self.assertEqual(result.sol_target,s.sol_qty)
    def test_default_no_risk_budget_cannot_open_but_existing_stop_works(self):
        result=decide(Config(),feat(close=1020),snap(btc_qty=D(0)),State())
        self.assertEqual(result.btc_target,D(0))
        self.assertIn('UNAPPROVED',result.reason)
    def test_h6_sample_is_entire_causal_prefix_and_one_horizon(self):
        hs=CausalityTests().hours(169)
        f=features(hs,Config(),hs[-1].available_ns)
        self.assertEqual(len(f.downside_scenarios),163)
        self.assertEqual(f.downside_scenarios[0],(hs[6].btc_close/hs[0].btc_close-1,hs[6].sol_close/hs[0].sol_close-1))
        unknown=features(tuple(replace(h,sol_close=0) for h in hs),Config(),hs[-1].available_ns)
        self.assertTrue(unknown.valid)
        self.assertFalse(unknown.hedge_data_known)
    def test_covariance_soft_and_hard_distinct_with_no_microtrim(self):
        f=feat(beta=1.2,beta_guard=1.3,covariance_ratio=.3)
        s=snap(btc_qty=D(100),btc_mark=D(1000),sol_qty=D(-135))
        soft,hard=hedge_limits(Config(),f,s,s.btc_qty)
        self.assertEqual(soft,D(135))
        self.assertGreater(hard,soft)
        st=state(btc_target=D(100),sol_target=D(-135),last_hour=f.closed_ns)
        result=decide(Config(),replace(f,beta_guard=1.301),s,st)
        self.assertEqual(result.sol_target,s.sol_qty)
    def test_incremental_downside_gate_rejects_basis_and_unknown_funding(self):
        f=feat(covariance_ratio=.3)
        s=snap(btc_qty=D(100),sol_qty=D(0))
        self.assertFalse(hedge_change_improves(Config(),f,s,D(-300)))
        self.assertTrue(hedge_change_improves(configured(),f,s,D(-300)))
        self.assertFalse(hedge_change_improves(configured(downside_scenarios=((-0.01,.08),(.01,-.08))),f,s,D(-300)))
        self.assertFalse(hedge_change_improves(configured(),f,replace(s,sol_qty=D(-300)),D(-300)))
    def test_pending_ro_no_growth_and_opposite_nonro_can_reach_zero(self):
        for d in (1,-1):
            reduction,growth=pending_effects(D(d*40),((D(-d*10),True),(D(d*4),False)))
            self.assertEqual((reduction,growth),(D(-d*10),D(4)))
            reduction,growth=pending_effects(D(d*40),((D(-d*60),False),))
            self.assertEqual((reduction,growth),(D(-d*40),D(60)))
    def test_normal_btc_trim_waits_for_actual_sol_not_pending_credit(self):
        for d in (1,-1):
            s=snap(btc_qty=D(d),sol_qty=D(-d*6),sol_pending=D(d*5))
            decision=Decision(D(d)*D('.5'),D(-d),"ORDINARY",state(direction=d))
            btc,sol,wait=stage_targets(decision,s,feat(beta_guard=1))
            self.assertTrue(wait)
            self.assertEqual(btc,s.btc_qty)
    def test_dust_retains_actual_and_execution_block(self):
        for d in (1,-1):
            actual=D(d)*D('.04')
            plan=order_plan(actual=actual,target=ZERO,pending=ZERO,unknown=False,price=D(190),step=D('.01'),min_qty=D('.01'),max_child=D(1000),min_notional=D(10),emergency=True)
            self.assertEqual(plan.action,'HOLD')
            self.assertIn('EXCEPTION_UNKNOWN',plan.reason)
            self.assertEqual(actual,D(d)*D('.04'))
    def test_slow_sma34_ema_wilder_atr_and_availability(self):
        days=tuple(Day((i+1)*24*HOUR_NS,(i+1)*24*HOUR_NS,100+i,102+i,98+i,100+i) for i in range(35))
        now=days[-1].available_ns+1
        h=Hour(days[-1].closed_ns,days[-1].closed_ns,1,2,1,134,1)
        f=slow_features(feat(t=h.closed_ns),days,(h,),now)
        self.assertEqual(f.core_direction,1)
        self.assertEqual(f.daily_atr,4)
        with self.assertRaises(ValueError):slow_features(feat(),days,(h,),now-2)
        self.assertFalse(slow_features(feat(),days[:7],(),now).valid)
        armed=arm_slow_release(State(),f,now)
        self.assertEqual(armed.release_anchor,134)
        self.assertEqual(armed.release_atr,4)
        # Same H4 as arming cannot satisfy the subsequent-H4 release.
        decision=decide(configured(core_signal='slow_d1_h4'),f,snap(btc_qty=ZERO),armed,now_ns=now)
        self.assertEqual(decision.btc_target,ZERO)
    def test_adapter_stop_during_signal_embargo_even_without_sol_mark(self):
        from test_cm2_final_send_contract import FinalSendTest
        from coinmaster.strategy.cm2_native import CM2Strategy
        fake,i,tick,s,_,sent,_=FinalSendTest().fixture(qty=D(1),price=D(90),draining=False)
        fake.policy_state=state(stop=95,btc_intent='HOLD',last_hour=fake.clock.now)
        fake.current_features=replace(fake.current_features,available_ns=fake.clock.now,hedge_valid=False)
        fake._snapshot=lambda ns:replace(s,data_known=False,core_data_known=True,btc_price_known=True)
        CM2Strategy.on_quote_tick(fake,N(**vars(tick),instrument_id=i.id))
        self.assertTrue(fake.policy_state.draining)
        self.assertEqual(fake.policy_state.btc_target,ZERO)
        self.assertEqual(len(sent),1)
        self.assertTrue(sent[0].is_reduce_only)
    def test_decide_retains_held_hedge_at_exact_soft_target(self):
        for d in (1,-1):
            f=feat(residual_z=-d*2,btc_return6=-d*.02,covariance_ratio=.3)
            s=snap(btc_qty=D(d),sol_qty=D(-d)*D('1.35'))
            st=state(direction=d,btc_target=D(d),hedge_active=True,activate_count=2,sol_target=s.sol_qty)
            result=decide(configured(),f,s,st)
            self.assertEqual(result.sol_target,s.sol_qty)
    def test_matched_restore_is_actual_tranche_finite_and_core_gated_both_signs(self):
        for d in (1,-1):
            cfg=configured(mode='btc_trim',restore_band_atr=2,restore_lifetime_ns=HOUR_NS)
            f=feat(residual_z=-d*2,btc_return6=-d*.02)
            s=snap(btc_qty=D(d))
            first=decide(cfg,f,s,state(direction=d,btc_target=D(d),activate_count=1))
            held=first.btc_target
            self.assertLess(abs(held),abs(s.btc_qty))
            # Constructor-free input of a confirmed quantity, not a simulated fill.
            actual=replace(s,btc_qty=held)
            release=replace(f,closed_ns=f.closed_ns+HOUR_NS,available_ns=f.available_ns+HOUR_NS,residual_z=0,btc_return6=d*.01)
            one=decide(cfg,release,actual,first.state)
            release=replace(release,closed_ns=release.closed_ns+HOUR_NS,available_ns=release.available_ns+HOUR_NS)
            result=decide(cfg,release,actual,one.state)
            self.assertEqual(result.btc_target,D(d))
            self.assertEqual(result.state.btc_intent,'MATCHED_RESTORE')
            deadline=result.state.restore_deadline_ns
            self.assertTrue(btc_child_permission(cfg,release,actual,result.state,now_ns=release.available_ns+2,executable_price=s.btc_mark)[0])
            self.assertFalse(btc_child_permission(cfg,release,actual,replace(result.state,core_target_valid=False),now_ns=release.available_ns+2,executable_price=s.btc_mark)[0])
            next_feature=replace(release,closed_ns=release.closed_ns+HOUR_NS,available_ns=release.available_ns+HOUR_NS)
            self.assertFalse(btc_child_permission(cfg,next_feature,actual,result.state,now_ns=deadline+1,executable_price=s.btc_mark)[0])
    def test_release_epoch_not_rearmed_during_partial_drain(self):
        f=replace(feat(),core_direction=1,daily_close=100,daily_atr=4)
        st=arm_slow_release(replace(state(),draining=True),f,100)
        later=arm_slow_release(st,replace(f,daily_close=110,daily_atr=8),200)
        self.assertEqual((later.release_anchor,later.release_atr,later.release_armed_ns),(100,4,100))
    def test_slow_held_budget_trim_does_not_arm_reentry(self):
        for d in (1,-1):
            st=state(direction=d,btc_target=D(d*40),last_hour=200*HOUR_NS,
                stop=800 if d>0 else 1200,release_anchor=123,release_armed_ns=0)
            f=replace(feat(),core_direction=d,daily_close=100,daily_atr=4)
            result=decide(configured(core_signal='slow_d1_h4'),f,snap(btc_qty=D(d*40),equity=D(1000)),st)
            self.assertEqual(result.reason,'HELD_CASH_RISK_TRIM')
            self.assertFalse(result.state.draining)
            self.assertEqual((result.state.release_anchor,result.state.release_armed_ns),(123,0))
    def test_held_budget_enforced_between_signal_hours_both_signs(self):
        for d in (1,-1):
            st=state(direction=d,btc_target=D(d*40),last_hour=200*HOUR_NS,stop=800 if d>0 else 1200)
            s=snap(btc_qty=D(d*40),equity=D(1000))
            result=decide(configured(),feat(),s,st)
            self.assertEqual(result.reason,'HELD_CASH_RISK_TRIM')
            self.assertLess(abs(result.btc_target),abs(s.btc_qty))
    def test_native_margin_account_ro_does_not_consume_growth_margin(self):
        from coinmaster.strategy.cm2_native import CM2Strategy
        from nautilus_trader.accounting.accounts.margin import MarginAccount
        from nautilus_trader.test_kit.stubs.events import TestEventStubs
        from nautilus_trader.model.identifiers import InstrumentId
        from nautilus_trader.model.enums import OrderSide
        account=MarginAccount(TestEventStubs.margin_account_state())
        from nautilus_trader.model.objects import Money,AccountBalance
        from nautilus_trader.model.currencies import USD
        account.update_margin_init(InstrumentId.from_str('BTCUSDC.HYPERLIQUID'),Money(100,USD))
        account.update_balances([AccountBalance(Money(11100,USD),Money(10100,USD),Money(1000,USD))])
        btc=InstrumentId.from_str('BTCUSDC.HYPERLIQUID');sol=InstrumentId.from_str('SOLUSDC.HYPERLIQUID')
        ro=N(side=OrderSide.SELL,leaves_qty=N(as_decimal=lambda:D(10)),is_reduce_only=True)
        projections=[]
        def margin(i,q,t):projections.append(q);return (q*D(1000)/40,ZERO)
        fake=N(config=N(btc_id=btc,sol_id=sol,exit_fee_rate=D('.000432'),limits=N(max_gross_notional=None),margin_policy=N(margin_for=margin)),
            cache=N(account_for_venue=lambda venue:account),_orders=lambda iid:[ro] if iid==btc else [],pre_submit_gate_blocks=[])
        self.assertTrue(CM2Strategy._admit(fake,btc,D(4),D(1000),snap(btc_qty=D(40)),1))
        self.assertEqual(max(projections),D(44))
        inc=N(side=OrderSide.BUY,leaves_qty=N(as_decimal=lambda:D(4)),is_reduce_only=False)
        fake._orders=lambda iid:[ro,inc] if iid==btc else []
        account.update_balances([AccountBalance(Money(10220,USD),Money(10100,USD),Money(120,USD))])
        self.assertTrue(CM2Strategy._admit(fake,btc,D(4),D(1000),snap(btc_qty=D(40)),1))
        account.update_balances([AccountBalance(Money(10200,USD),Money(10100,USD),Money(100,USD))])
        self.assertFalse(CM2Strategy._admit(fake,btc,D(4),D(1000),snap(btc_qty=D(40)),1))
        self.assertEqual(fake.pre_submit_gate_blocks[-1]['reason'],'NATIVE_FREE_MARGIN')
        # BTC order margin cannot fund a pending SOL increase (review counterexample).
        fake._orders=lambda iid:[ro] if iid==btc else [inc]
        cross=snap(btc_qty=D(40),sol_qty=ZERO,sol_mark=D(1000))
        account.update_balances([AccountBalance(Money(10220,USD),Money(10100,USD),Money(120,USD))])
        self.assertFalse(CM2Strategy._admit(fake,sol,D(4),D(1000),cross,1))
        self.assertEqual(fake.pre_submit_gate_blocks[-1]['reason'],'NATIVE_FREE_MARGIN')
        fake._orders=lambda iid:[ro,inc] if iid==btc else []
        # Aggregate projected 52 crosses a test tier; pending and child fees still reserved.
        inc.leaves_qty=N(as_decimal=lambda:D(8))
        fake.config.margin_policy=N(margin_for=lambda i,q,t:(q*D(1000)/(20 if q>50 else 40),ZERO))
        account.update_margin_init(btc,Money(200,USD))
        account.update_balances([AccountBalance(Money(11600,USD),Money(10200,USD),Money(1400,USD))])
        self.assertFalse(CM2Strategy._admit(fake,btc,D(4),D(1000),snap(btc_qty=D(40)),1))
        account.update_balances([AccountBalance(Money(11700,USD),Money(10200,USD),Money(1500,USD))])
        self.assertTrue(CM2Strategy._admit(fake,btc,D(4),D(1000),snap(btc_qty=D(40)),1))

class SeedAndCheckpointV2Tests(unittest.TestCase):
    def test_d1_seed_identity_tamper_rejected_before_restore(self):
        from test_cm2_checkpoint import CheckpointTests
        fixture=CheckpointTests();fixture.setUp()
        try:
            obj=fixture.fake();obj.days=[];obj._seed_days_sha256='original-seed-hash'
            saved=obj.on_save();obj._seed_days_sha256='tampered-seed-hash'
            with self.assertRaisesRegex(ValueError,'SOURCE_CONFIG_IDENTITY'):obj.on_load(saved)
        finally:fixture.tearDown()
    def test_explicit_daily_loader_open_labels_prefix_pin_and_no_positions(self):
        import csv,hashlib
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from coinmaster.research.cm2_runner import CM2RunConfig
        with TemporaryDirectory() as directory:
            path=Path(directory)/'seed.csv'
            with path.open('w') as handle:
                writer=csv.DictWriter(handle,fieldnames=['open_time_ms','open','high','low','close']);writer.writeheader()
                for i in range(40):writer.writerow(dict(open_time_ms=i*86400000,open=100,high=102,low=98,close=100+i))
            cfg=CM2RunConfig(Config(core_signal='slow_d1_h4'),Path(directory),daily_seed_path=path,daily_seed_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            days=cfg.daily_seed(35*24*HOUR_NS)
            self.assertEqual(len(days),35);self.assertEqual(days[-1].closed_ns,35*24*HOUR_NS)
            self.assertEqual(days[0].available_ns,24*HOUR_NS)
            self.assertEqual(State().btc_qty if hasattr(State(),'btc_qty') else State().btc_target,ZERO)
            with self.assertRaisesRegex(ValueError,'PIN_MISMATCH'):replace(cfg,daily_seed_sha256='bad').daily_seed(35*24*HOUR_NS)

if __name__=='__main__':unittest.main()
