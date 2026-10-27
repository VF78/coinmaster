"""Engine-free risk reference/finite-reduction checks. No engine imports."""
import unittest
from decimal import Decimal as D
from fractions import Fraction
from coinmaster.strategy.method_a_risk import *


def f():return Features(0,30*DAY,30*DAY+MINUTE,D(1),D('.95'),D('.095'),D('.1'),D('.1'),D('.01'),D('.0003'),D('.0003'))

def margin(leg,q,p):
    n=q*p
    if n<=D(250):return n/D(40),max(D(0),n*D('.01'))
    if n<=D(500):return n*D('.04'),max(D(0),n*D('.02')-D('2.5'))
    return n*D('.06'),max(D(0),n*D('.04')-D('12.5'))

def boundaries(leg,p):return (Fraction(250)/Fraction(p),Fraction(500)/Fraction(p),Fraction(D('2.5'))/Fraction(D('.02'))/Fraction(p),Fraction(D('12.5'))/Fraction(D('.04'))/Fraction(p))


class RiskPure(unittest.TestCase):
    def test_constructive_witness_both_sides(self):
        for sign in (-1,1):
            s=State(sign*D('.5'),D(0),D(10000),D(10000),D(70000),D(170))
            on,band,target=hedge_target(s,f(),False,True)
            self.assertTrue(on);self.assertEqual(band,'MEDIUM')
            self.assertEqual(target*D(170),D(16625))
            good,benefit,cost=useful_hedge(s,f(),target)
            self.assertTrue(good);self.assertGreaterEqual(benefit,2*cost)
            self.assertLess(evaluate(s,f(),margin).loss,s.cushion)
            hedged=State(s.btc,-sign*target,s.equity,s.peak,s.pb,s.ps)
            self.assertLess(evaluate(hedged,f(),margin).loss,s.cushion)

    def test_bad_basis_denied(self):
        bad=Features(0,0,0,D(1),D('.1'),D('.095'),D('.1'),D('.1'),D('.4'),D('.01'),D('.01'))
        s=State(D('.5'),D(0),D(10000),D(10000),D(70000),D(170))
        self.assertFalse(useful_hedge(s,bad,D(100))[0])

    def test_feature_causality_and_funding_completeness(self):
        obs=[];pb=D(100);ps=D(100)
        for i in range(33):
            if i:pb*=1+D(i%3-1)/100;ps*=1+D(i%3-1)/90+D(i%2)/10000
            obs.append(Observation(i*DAY,i*DAY+MINUTE,pb,ps))
        rates=tuple(Funding(leg,n*DAY//3,n*DAY//3+MINUTE,D('-.0001'),DAY//3) for leg in ('BTC','SOL') for n in range(1,97))
        result=lagged_features(obs,rates,32*DAY+MINUTE)
        self.assertEqual(result.end_ns,31*DAY)
        self.assertEqual(result.start_ns,DAY)
        self.assertEqual(result.fund_b,D('.0003'))
        with self.assertRaisesRegex(ValueError,'FUNDING'):
            lagged_features(obs,tuple(r for r in rates if not(r.leg=='SOL' and r.effective_ns==10*DAY)),32*DAY+MINUTE)
        with self.assertRaisesRegex(ValueError,'D1_GAP'):
            lagged_features(tuple(r for r in obs if r.end_ns!=10*DAY),rates,32*DAY+MINUTE)
        late=list(obs);late[31]=Observation(31*DAY,33*DAY,pb,ps)
        with self.assertRaisesRegex(ValueError,'UNAVAILABLE'):lagged_features(late,rates,32*DAY+MINUTE)

    def test_partial_pending_zero_credit_and_modify_dedup(self):
        s=State(D(3),D(-2),D(1000),D(1000),D(100),D(100))
        orders=(Liability('BTC-original','BTC',1,2,D(1),False,D('.155')),
            Liability('SOL-maximum-old-new','SOL',-1,3,D(1),False,D('.155')))
        e=execution_envelope(s,f(),orders,margin)
        self.assertEqual(e.states,24)
        self.assertGreaterEqual(e.worst_deficit,evaluate(s,f(),margin).worst_deficit)
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):execution_envelope(s,f(),orders+(orders[1],),margin)

    def test_partition_dominates_every_exhaustive_native_lot(self):
        # Both sides, two independent opening owners, TP+STOP reduction overlap,
        # tier transitions and actual NETTING clipping. No endpoint assumption.
        for sign in (-1,1):
            for h in (1,3,5):
                for opening in (0,2):
                    s=State(sign*D(h),-sign*D(2),D(1000),D(1000),D(100),D(100))
                    orders=(Liability('bo','BTC',sign,opening,D(1),False,D('.155')),
                        Liability('btp','BTC',-sign,2,D(1),True,D('.2')),
                        Liability('so','SOL',-sign,2,D(1),False,D('.155')),
                        Liability('stp','SOL',sign,1,D(1),True,D('.17')),
                        Liability('stop','SOL',sign,3,D(1),True,D('.155')))
                    direct=execution_envelope(s,f(),orders,margin)
                    reduced=tier_partition_envelope(s,f(),orders,margin,boundaries)
                    self.assertEqual(reduced.worst_deficit,direct.worst_deficit)
                    self.assertEqual(reduced.safe,direct.safe)
                    self.assertEqual(reduced.margin_pass,direct.margin_pass)
                    self.assertLess(reduced.states,direct.states)

    def test_partition_catches_discontinuous_initial_margin(self):
        # A favorable BTC shock may make equity recover after a tier jump.
        # The forbidden global endpoint shortcut would miss this interior.
        def jump(leg,q,p):return (D(150) if D(2)<q<=D(3) else D(0),D(0))
        def cuts(leg,p):return (D(2),D(3))
        s=State(D(1),D(0),D(100),D(100),D(1),D(1))
        orders=(Liability('open','BTC',1,4,D(1),False,D(0)),)
        result=tier_partition_envelope(s,f(),orders,jump,cuts)
        self.assertFalse(result.margin_pass)

    def test_normal_and_recovery_deficits_distinct(self):
        s=State(D(10),D(0),D(100),D(100),D(100),D(100))
        initial=evaluate(s,f(),margin)
        self.assertGreater(initial.worst_deficit,0)
        order=Liability('reduce','BTC',-1,10,D(1),True,D('.155'))
        route=execution_envelope(s,f(),(order,),margin)
        self.assertFalse(route.safe)  # Zero-fill cannot PASS an existing breach.
        final=State(D(0),D(0),s.equity,s.peak,s.pb,s.ps)
        self.assertLess(evaluate(final,f(),margin,unpaid=D('1.55')).worst_deficit,initial.worst_deficit)

    def test_unknown_nonpositive_and_crossing(self):
        with self.assertRaises(ValueError):State(D('NaN'),D(0),D(100),D(100),D(1),D(1))
        s=State(D(1),D(0),D(100),D(100),D(1),D(1))
        bad=Features(0,0,0,D(1),D(1),D(1),D(1),D(2),D(0),D(0),D(0))
        with self.assertRaisesRegex(ValueError,'NONPOSITIVE'):evaluate(s,bad,margin)
        with self.assertRaisesRegex(ValueError,'CROSSING'):
            tier_partition_envelope(s,f(),(Liability('bad','BTC',-1,2,D(1),False,D(0)),),margin,boundaries)

    def test_original_residual_no_restore_or_expiry_extension(self):
        args=dict(original=D(10),filled=D(4),retired=D(2),now=3*MINUTE,expiry=4*MINUTE,off_since=MINUTE,drained=True,parent_live=True,known_off=True)
        self.assertEqual(lawful_residual(**args),D(4))
        for key,value in (('now',4*MINUTE),('drained',False),('parent_live',False),('known_off',False)):
            self.assertEqual(lawful_residual(**{**args,key:value}),0)
        with self.assertRaises(ValueError):lawful_residual(**{**args,'filled':D(11)})

if __name__=='__main__':unittest.main()
