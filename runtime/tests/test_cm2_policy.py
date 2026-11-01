"""Constructor-free CM2 economic/causal invariants; no engine/account fixtures."""
import ast
from dataclasses import replace
from decimal import Decimal as D
from math import exp,sin
from pathlib import Path
import subprocess
import unittest
from coinmaster.strategy.cm2_policy import (
    Config,Features,Snapshot,State,Hour,HOUR_NS,MINUTE_NS,PairedHourBuilder,features,decide,positive_harvest)
from coinmaster.strategy.cm2_execution import order_plan,stage_targets

def configured(**kwargs):
    # TEST-ONLY explicit acceptance inputs, not trading recommendations/defaults.
    values=dict(parent_risk_fraction=.9,initial_band_atr=100,hedge_future_cost_rate=.000432,
        downside_scenarios=((-0.02,-0.04),(-0.01,0.005),(0.02,0.04),(0.01,-0.005)))
    values.update(kwargs)
    return Config(**values)

def feat(t=200*HOUR_NS,**kwargs):
    return replace(Features(t,t,True,close=1000,channel_high=1010,channel_low=990,
        atr=10,execution_atr=10,beta=1.5,beta_guard=1.8,rho=.8,residual_z=0,btc_return6=.01,
        common_loss=.02,residual_loss=.001,hedge_valid=True,covariance_ratio=1/1.8),**kwargs)

def snap(**kwargs):
    return replace(Snapshot(D("10000"),D("1"),D("0"),D("1000"),D("100"),
        btc_vwap=D("1000"),btc_entry_fees=D(".4"),btc_signed_funding=D("0")),**kwargs)

def state(**kwargs):
    if kwargs.get("direction",1)<0 and "stop" not in kwargs: kwargs["stop"]=1200
    return replace(State(direction=1,parent=1,btc_target=D("1"),unhedged_btc_target=D("1"),
        initial_r=100,stop=800,extreme=1000,last_hour=199*HOUR_NS),**kwargs)

class PolicyTests(unittest.TestCase):
    def test_parameter_bounds(self):
        for name,value in (("load",9),("trend_hours",23),("stop_atr",1.9),("hedge_fraction",1),("core",.95)):
            with self.assertRaises(ValueError): configured(**{name:value})
    def test_entry_target_is_finite_and_no_callback_add(self):
        s=snap(btc_qty=D(0),btc_vwap=None)
        f=feat(close=1020)
        first=decide(configured(),f,s,State())
        self.assertEqual(first.btc_target,D(40))
        again=decide(configured(),f,replace(s,btc_pending=D(40)),first.state)
        self.assertEqual(again.btc_target,D(40))
    def test_entry_long_short_scale(self):
        for close,sign in ((1020,1),(980,-1)):
            f=feat(close=close)
            a=decide(configured(),f,snap(btc_qty=D(0)),State())
            b=decide(configured(),f,snap(equity=D(20000),btc_qty=D(0)),State())
            self.assertEqual(a.btc_target,D(sign*40))
            self.assertEqual(b.btc_target,a.btc_target*2)
    def test_prior_channel_rolling_cannot_average_down(self):
        cases=((1,D(30),D(990),990,980,970,950,1000),
               (-1,D(-30),D(1010),1010,1030,1020,1050,1000))
        for d,q,mark,c,hi,lo,stop,extreme in cases:
            s=snap(btc_qty=q,btc_mark=mark)
            st=state(direction=d,btc_target=q,unhedged_btc_target=q,stop=stop,extreme=extreme)
            result=decide(configured(),feat(close=c,channel_high=hi,channel_low=lo),s,st)
            self.assertEqual(result.btc_target,q)
    def test_unknown_basis_cannot_add(self):
        result=decide(configured(),feat(close=1020),snap(btc_vwap=None),state())
        self.assertEqual(result.btc_target,D(1))
    def test_harvest_requires_actual_positive_net_costs(self):
        s=snap(btc_mark=D(1001),btc_entry_fees=D(5))
        self.assertFalse(positive_harvest(s))
        self.assertFalse(positive_harvest(replace(s,btc_signed_funding=None)))
        self.assertFalse(positive_harvest(replace(s,btc_signed_funding=D(100))))
        self.assertTrue(positive_harvest(replace(s,btc_mark=D(1100))))
    def test_harvest_reduces_once_no_add(self):
        f=feat(close=1250,channel_high=1240)
        s=snap(btc_mark=D(1250))
        a=decide(configured(),f,s,state(initial_r=100))
        self.assertEqual(a.reason,"POSITIVE_NET_HARVEST")
        self.assertEqual(a.btc_target,D(".75"))
        b=decide(configured(),replace(f,closed_ns=f.closed_ns+HOUR_NS,close=1260),replace(s,btc_qty=D(".75")),a.state)
        self.assertEqual(b.btc_target,D(".75"))
    def test_two_close_hedge_hysteresis_and_opposite_sign(self):
        for d in (1,-1):
            q=D(d)
            st=state(direction=d,btc_target=q,unhedged_btc_target=q,stop=800 if d>0 else 1200)
            s=snap(btc_qty=q)
            f=feat(residual_z=-d*2,btc_return6=-d*.02)
            a=decide(configured(),f,s,st)
            self.assertEqual(a.sol_target,D(0))
            f=replace(f,closed_ns=f.closed_ns+HOUR_NS)
            b=decide(configured(),f,s,a.state)
            self.assertLess(b.sol_target*q,0)
            self.assertGreater(abs(q)*s.btc_mark-D(str(f.beta_guard))*abs(b.sol_target)*s.sol_mark,0)
            release=replace(f,closed_ns=f.closed_ns+HOUR_NS,residual_z=0,btc_return6=d*.01)
            c=decide(configured(),release,s,b.state)
            self.assertNotEqual(c.sol_target,D(0))
            e=decide(configured(),replace(release,closed_ns=release.closed_ns+HOUR_NS),s,c.state)
            self.assertEqual(e.sol_target,D(0))
    def test_small_unknown_beta_has_finite_latched_trim(self):
        for f in (feat(valid=False),):
            a=decide(configured(),f,snap(),state())
            self.assertEqual(a.btc_target,D(".5"))
            b=decide(configured(),f,snap(btc_qty=D(".5")),a.state)
            self.assertEqual(b.btc_target,D(".5"))
            self.assertEqual(b.sol_target,D(0))
    def test_bad_residual_risk_denies_sol(self):
        f=feat(residual_z=-2,btc_return6=-.02,residual_loss=.2)
        a=decide(configured(downside_scenarios=((-0.01,.08),(.01,-.08))),f,snap(),state(activate_count=1))
        self.assertEqual(a.sol_target,D(0))
    def test_buffer_changes_ordinary_inventory_not_hard_cap_or_drain(self):
        s=snap(sol_qty=D("-2.1"))
        st=state(last_hour=200*HOUR_NS,sol_target=D("-2.5"))
        a=decide(configured(buffer=.08),feat(),s,st)
        b=decide(configured(buffer=.03),feat(),s,st)
        self.assertEqual(a.sol_target,D("-2.1"))
        self.assertEqual(b.sol_target,D("-2.5"))
        c=decide(configured(buffer=.20),feat(),snap(sol_qty=D("-3")),st)
        self.assertEqual(c.sol_target,D("-3")) # safely inside no-factor-flip cap; h is soft
        d=decide(configured(buffer=.20),feat(),s,replace(st,sol_target=D(0)))
        self.assertEqual(d.sol_target,D(0))
    def test_matched_trim_not_geometric(self):
        f=feat(residual_z=-2,btc_return6=-.02)
        a=decide(configured(mode="btc_trim"),f,snap(),state(activate_count=1))
        s=snap(btc_qty=a.btc_target)
        b=decide(configured(mode="btc_trim"),replace(f,closed_ns=f.closed_ns+HOUR_NS),s,a.state)
        self.assertEqual(a.btc_target,b.btc_target)
    def test_flat_parent_drains_sol_and_blocks_new_parent(self):
        a=decide(configured(),feat(close=1100),snap(btc_qty=D(0),sol_qty=D(-1)),state())
        self.assertEqual((a.btc_target,a.sol_target),(D(0),D(0)))
        self.assertTrue(a.state.draining)
        b=decide(configured(),feat(),snap(btc_qty=D(0),sol_qty=D(0),unknown_orders=True),a.state)
        self.assertTrue(b.state.draining)
    def test_terminal_emergency_bypasses_ordinary_staging(self):
        a=decide(configured(),feat(),snap(sol_qty=D(-2)),state(),terminal=True)
        b,sol,wait=stage_targets(a,snap(sol_qty=D(-2)),feat())
        self.assertEqual((b,sol,wait),(D(0),D(0),False))
    def test_ordinary_reduction_stages_sol_before_btc(self):
        f=feat()
        a=decide(configured(),f,snap(),state())
        a=replace(a,btc_target=D(".1"),sol_target=D(-1))
        b,sol,wait=stage_targets(a,snap(sol_qty=D(-5),sol_pending=D(-1)),f)
        self.assertTrue(wait)
        self.assertEqual(b,D(1))
        self.assertLessEqual(abs(sol),D(".1")*D(1000)/D("1.8")/D(100))
    def test_proposed_sol_and_pending_btc_reduction_capped(self):
        f=feat(beta=1,beta_guard=1)
        s=snap(btc_qty=D(100),sol_qty=D(0),btc_pending=D(-70))
        decision=decide(configured(),f,s,state(btc_target=D(100),unhedged_btc_target=D(100)))
        decision=replace(decision,btc_target=D(50),sol_target=D(-750))
        btc,sol,wait=stage_targets(decision,s,f)
        self.assertEqual(btc,D(50))
        self.assertLessEqual(abs(sol)*s.sol_mark,D(30)*s.btc_mark)
        # Either BTC-first or SOL-first fill leaves the beta factor nonnegative.
        for actual_btc in (D(100),D(50),D(30)):
            self.assertGreaterEqual(actual_btc*s.btc_mark-abs(sol)*s.sol_mark,0)

    def test_held_sol_cap_after_btc_fill(self):
        a=decide(configured(),feat(),snap(btc_qty=D(".1")),state(last_hour=200*HOUR_NS,sol_target=D(-4)))
        self.assertLessEqual(abs(a.sol_target),D(".1")*D(1000)/D("1.8")/D(100))
    def test_pending_counted_once(self):
        kwargs=dict(actual=D(1),target=D(3),pending=D(2),unknown=False,price=D(1000),step=D(".001"),min_qty=D(".001"),max_child=D(1000))
        self.assertEqual(order_plan(**kwargs).action,"WAIT")
        self.assertEqual(order_plan(**{**kwargs,"pending":D(3)}).action,"CANCEL")
        self.assertEqual(order_plan(**{**kwargs,"unknown":True}).action,"CANCEL")
    def test_e01_guard_trim_rounds_target_toward_flat_and_progresses(self):
        f=feat(beta=1,beta_guard=1)
        s=snap(btc_qty=D(40),sol_qty=D(-300),btc_mark=D(1070),sol_mark=D(90))
        decision=decide(configured(),f,s,state(btc_target=D(40),unhedged_btc_target=D(40)))
        decision=replace(decision,btc_target=D(20),sol_target=-D(40)*D(1070)*D(".75")/D(90))
        args=dict(sol_step=D(".01"),sol_min_qty=D(".01"),sol_min_notional=D(10))
        btc,sol,wait=stage_targets(decision,s,f,**args)
        self.assertEqual((btc,sol,wait),(D(40),D("-237.77"),True))
        plan=order_plan(actual=s.sol_qty,target=sol,pending=D(0),unknown=False,price=D(90),
            step=D(".01"),min_qty=D(".01"),max_child=D(100000),min_notional=D(10))
        self.assertEqual(plan.signed_quantity,D("62.23"))
        # A hypothetical confirmed quantity input, not an executed/fake native fill.
        after=replace(s,sol_qty=D("-237.77"))
        btc2,sol2,wait2=stage_targets(decision,after,f,**args)
        self.assertEqual(btc2,D(20))
        self.assertFalse(wait2)
        self.assertGreaterEqual(D(20)*D(1070)-abs(after.sol_qty)*D(90),0)
    def test_preexisting_dust_over_guard_uses_legal_minimum_reduce(self):
        f=feat(beta=1,beta_guard=1)
        s=snap(btc_qty=D(40),sol_qty=D("-237.78"),btc_mark=D(1070),sol_mark=D(90))
        decision=replace(decide(configured(),f,s,state()),btc_target=D(20),sol_target=D(-300))
        btc,sol,wait=stage_targets(decision,s,f,sol_step=D(".01"),sol_min_qty=D(".01"),sol_min_notional=D(10))
        self.assertEqual((btc,sol,wait),(D(40),D("-237.66"),True))
        plan=order_plan(actual=s.sol_qty,target=sol,pending=D(0),unknown=False,price=D(90),
            step=D(".01"),min_qty=D(".01"),max_child=D(100000),min_notional=D(10))
        self.assertEqual(plan.signed_quantity,D(".12"))
        self.assertGreaterEqual(plan.signed_quantity*D(90),D(10))
        _,_,after_wait=stage_targets(decision,replace(s,sol_qty=sol),f,
            sol_step=D(".01"),sol_min_qty=D(".01"),sol_min_notional=D(10))
        self.assertFalse(after_wait)
    def test_native_min_notional_applies_to_reduce_only_without_waiver(self):
        plan=order_plan(actual=D("-237.78"),target=D("-237.77"),pending=D(0),unknown=False,
            price=D(90),step=D(".01"),min_qty=D(".01"),max_child=D(100000),min_notional=D(10))
        self.assertEqual((plan.action,plan.reason),("HOLD","CONSERVATIVE_RESEARCH_MIN_NOTIONAL_REDUCE_EXCEPTION_UNKNOWN"))
        dust=order_plan(actual=D("-.06"),target=D(0),pending=D(0),unknown=False,
            price=D(90),step=D(".01"),min_qty=D(".01"),max_child=D(100000),min_notional=D(10),emergency=True)
        self.assertEqual(dust.action,"HOLD")

    def test_emergency_reduction_exempts_child_cap(self):
        args=dict(actual=D(10),target=D(0),pending=D(0),unknown=False,price=D(1000),step=D(".001"),min_qty=D(".001"),max_child=D(1))
        self.assertEqual(order_plan(**args).signed_quantity,D("-.001"))
        self.assertEqual(order_plan(**args,emergency=True).signed_quantity,D(-10))

class CausalityTests(unittest.TestCase):
    def hours(self,n=210):
        result=[]
        b,s=1000.,100.
        for i in range(n):
            b*=exp(.001*sin(i*.6)+.0002)
            s*=exp(.0015*sin(i*.6)+.0003*sin(i*.9))
            t=(i+1)*HOUR_NS
            result.append(Hour(t,t,b,b*1.002,b*.998,b,s))
        return tuple(result)
    def test_prefix_features_and_decisions(self):
        hs=self.hours()
        for n in (169,180,210):
            prefix=hs[:n]
            a=features(prefix,configured(),prefix[-1].available_ns)
            b=features(tuple(x for x in hs if x.available_ns<=prefix[-1].available_ns),configured(),prefix[-1].available_ns)
            self.assertEqual(a,b)
            self.assertEqual(decide(configured(),a,snap(),state()),decide(configured(),b,snap(),state()))
    def test_future_availability_rejected(self):
        hs=self.hours()
        with self.assertRaises(ValueError): features(hs,configured(),hs[-2].available_ns)
    def test_channel_excludes_decision_hour(self):
        hs=self.hours()
        f=features(hs,configured(),hs[-1].available_ns)
        self.assertEqual(f.channel_high,max(h.btc_close for h in hs[-73:-1]))
    def test_paired_barrier_and_duplicate(self):
        builder=PairedHourBuilder()
        out=None
        for i in range(60):
            t=(i+1)*MINUTE_NS
            self.assertIsNone(builder.add("BTC",t,t,1,2,1,2))
            out=builder.add("SOL",t,t,1,2,1,2)
            self.assertIsNone(builder.add("SOL",t,t,1,2,1,2))
        self.assertEqual(out.closed_ns,HOUR_NS)
    def test_gap_is_unknown_not_forwardfill(self):
        builder=PairedHourBuilder()
        for symbol in ("BTC","SOL"): builder.add(symbol,MINUTE_NS,MINUTE_NS,1,2,1,2)
        builder.add("BTC",3*MINUTE_NS,3*MINUTE_NS,1,2,1,2)
        with self.assertRaises(ValueError): builder.add("SOL",3*MINUTE_NS,3*MINUTE_NS,1,2,1,2)
    def test_original_default_strategy_ast_unchanged(self):
        root=Path(__file__).parents[2]
        old=subprocess.check_output(["git","show","5b56f7d02e09d4495ac018ec1ce701f6f0dfb737:runtime/coinmaster/research/native_baseline.py"],cwd=root,text=True)
        new=(root/"runtime/coinmaster/research/native_baseline.py").read_text()
        def legacy_assignment(source):
            return next(ast.dump(node) for node in ast.walk(ast.parse(source)) if isinstance(node,ast.Assign)
                        and any(isinstance(t,ast.Name) and t.id=="strategy" for t in node.targets)
                        and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name)
                        and node.value.func.id=="strategy_type")
        self.assertEqual(legacy_assignment(old),legacy_assignment(new))
    def test_no_legacy_import_in_new_policy_adapter(self):
        root=Path(__file__).parents[1]/"coinmaster/strategy"
        for name in ("cm2_policy.py","cm2_native.py","cm2_execution.py"):
            source=(root/name).read_text()
            for node in ast.walk(ast.parse(source)):
                if isinstance(node,ast.ImportFrom):
                    self.assertNotIn("wave_overlay",node.module or "")
                    self.assertNotIn("c1_",node.module or "")

if __name__=="__main__": unittest.main()
