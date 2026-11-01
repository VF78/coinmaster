"""Pure planner residual invariants; synthetic inputs, no native engine."""
from decimal import Decimal as D, ROUND_CEILING
import unittest
from coinmaster.strategy.cm2_execution import order_plan, stage_targets
from coinmaster.strategy.cm2_policy import Snapshot, Features, Decision, State

class ResidualDustTest(unittest.TestCase):
    def plan(self, actual, target, **overrides):
        args=dict(actual=D(str(actual)),target=D(str(target)),pending=D(0),unknown=False,
                  price=D(100),step=D(".01"),min_qty=D(".01"),max_child=D(100),
                  min_notional=D(10))
        args.update(overrides)
        return order_plan(**args)

    def test_capacity_created_dust_shrinks_both_directions(self):
        for sign in (D(1),D(-1)):
            p=self.plan(sign*D("8.48"),0,price=D("141.3"),max_child=D("8.46")*D("141.3"))
            self.assertEqual(p.action,"SUBMIT")
            self.assertEqual(p.signed_quantity,-sign*D("8.40"))
            self.assertEqual(abs(sign*D("8.48")+p.signed_quantity),D(".08"))

    def test_toy_legal_child_cannot_leave_legal_residual(self):
        for sign in (D(1),D(-1)):
            p=self.plan(sign*D(".15"),0,max_child=D(10))
            self.assertEqual((p.action,p.reason),("HOLD","VENUE_RESIDUAL_DUST_PREVENTION"))
            p=self.plan(sign*D(".15"),0,max_child=D(10),emergency=True)
            self.assertEqual(p.signed_quantity,-sign*D(".15"))

    def test_positive_core_partial_shrinks_never_overshoots_target(self):
        for sign in (D(1),D(-1)):
            p=self.plan(sign*D(".35"),sign*D(".05"))
            self.assertEqual(p.signed_quantity,-sign*D(".25"))
            self.assertEqual(sign*D(".35")+p.signed_quantity,sign*D(".10"))
            p=self.plan(sign*D(".15"),sign*D(".05"))
            self.assertEqual(p.reason,"VENUE_RESIDUAL_DUST_PREVENTION")

    def test_minimum_quantity_and_step_ceiling(self):
        p=self.plan(".38",".01",price=D(80),min_qty=D(".16"),step=D(".03"))
        self.assertEqual(p.signed_quantity,D("-.18")) # remainder .20 >= ceil(.16/.03)*.03
        p=self.plan(".25",".01",min_qty=D(".20"))
        self.assertEqual((p.action,p.reason),("HOLD","VENUE_RESIDUAL_DUST_PREVENTION"))

    def test_preexisting_dust_and_price_collapse_stay_blocked(self):
        for price in (D(100),D(50)):
            p=self.plan(".08",0,price=price,emergency=True)
            self.assertEqual((p.action,p.reason),("HOLD","CONSERVATIVE_RESEARCH_MIN_NOTIONAL_REDUCE_EXCEPTION_UNKNOWN"))
        self.assertEqual(self.plan(".15",0,price=D(100),emergency=True).action,"SUBMIT")
        self.assertEqual(self.plan(".15",0,price=D(50),emergency=True).action,"HOLD")

    def test_existing_fullclose_pending_unknown_flip_and_add_semantics(self):
        self.assertEqual(self.plan(".15",0).signed_quantity,D("-.15"))
        self.assertEqual(self.plan(".15","-.5").signed_quantity,D("-.15"))
        self.assertEqual(self.plan(".15",".05",pending=D("-.10")).action,"WAIT")
        self.assertEqual(self.plan(".15",".05",pending=D("-.10"),unknown=True).action,"CANCEL")
        self.assertEqual(self.plan(0,".15").signed_quantity,D(".15"))
        self.assertEqual(self.plan(".15",".30").signed_quantity,D(".15"))
        self.assertEqual(self.plan(".15",".10").reason,"CONSERVATIVE_RESEARCH_MIN_NOTIONAL_REDUCE_EXCEPTION_UNKNOWN")

    def test_factor_staging_cannot_release_btc_after_blocked_sol_child(self):
        s=Snapshot(D(10000),D(1),D("-.15"),D(1000),D(100))
        f=Features(0,0,True,hedge_valid=True,beta_guard=1)
        decision=Decision(D(".005"),D("-.05"),"HARVEST",State())
        kwargs=dict(sol_step=D(".01"),sol_min_qty=D(".01"),sol_min_notional=D(10))
        btc,sol,wait=stage_targets(decision,s,f,**kwargs)
        self.assertEqual((btc,sol,wait),(D(1),D("-.05"),True))
        p=self.plan(s.sol_qty,sol)
        self.assertEqual(p.reason,"VENUE_RESIDUAL_DUST_PREVENTION")
        self.assertEqual(stage_targets(decision,s,f,**kwargs)[0],s.btc_qty)

    def test_grid_submitted_reductions_preserve_all_bounds(self):
        for sign in (D(1),D(-1)):
            for held in (D(".15"),D(".35"),D("8.48")):
                for target in (D(0),D(".01"),held/D(2)):
                    for cap in (D(10),D(20),D(1000)):
                        p=self.plan(sign*held,sign*target,max_child=cap)
                        if p.action!="SUBMIT":continue
                        q=abs(p.signed_quantity);remaining=held-q
                        self.assertLessEqual(q,held-target)
                        self.assertLessEqual(q*D(100),cap)
                        self.assertGreaterEqual(q*D(100),D(10))
                        self.assertTrue(remaining==0 or remaining>=D(".10"))

if __name__=="__main__":unittest.main()
