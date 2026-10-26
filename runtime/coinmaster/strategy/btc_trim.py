"""Causal variance-matched BTC quantity, no fills/accounting/execution engine."""
from dataclasses import dataclass
from decimal import Decimal as D, localcontext
from fractions import Fraction as F
from math import isqrt


def variance_target(qref,lot,sol_lot,PB,PS,sigma_b,sigma_s,rho,a):
    values=(qref,lot,sol_lot,PB,PS,sigma_b,sigma_s,rho,a)
    if any(not isinstance(v,D)or not v.is_finite()for v in values)or any(v<=0 for v in values[:7])or not 0<=rho<=1 or a<=0:
        raise ValueError('TRIM_INCOMPARABLE_INPUT')
    qlots=F(qref)/F(lot)
    if qlots.denominator!=1:raise ValueError('TRIM_INCOMPARABLE_NATIVE_LOT')
    intended_lots=(F(a)*F(qref)*F(PB)/F(PS)/F(sol_lot)).__floor__()
    intended=D(intended_lots)*sol_lot
    if not intended_lots:raise ValueError('TRIM_INCOMPARABLE_ZERO_INTENDED')
    c=F(intended)*F(PS)*F(sigma_s)/(F(qref)*F(PB)*F(sigma_b))
    factor=1-F(rho)*c;orthogonal_sq=c*c*(1-F(rho)*F(rho));variance=factor*factor+orthogonal_sq
    if variance<0 or variance>1:raise ValueError('TRIM_INCOMPARABLE_RISK_INCREASE')
    target_lots=isqrt((int(qlots)**2*variance.numerator)//variance.denominator)
    with localcontext()as ctx:
        ctx.prec=80
        dec=lambda v:D(v.numerator)/D(v.denominator)
        result=dict(intended_sol=intended,c=dec(c),factor_loading=dec(factor),
            orthogonal_risk=dec(orthogonal_sq).sqrt(),total_risk_ratio=dec(variance).sqrt(),
            variance_numerator=variance.numerator,variance_denominator=variance.denominator,
            target_btc=D(target_lots)*lot,actual_qref=qref)
    return result


@dataclass
class BTCTrimCap:
    """Own BTC-only absolute ceiling; no synthetic SOL hedge credit."""
    qref:D
    bmax:D
    initialized:bool=True
    @property
    def solmax(self):return D(0)
    def reconcile(self,actual_btc,actual_sol,*,sol_reduced,btc_reduced,active_risk):
        if actual_sol:raise ValueError('TRIM_UNRELATED_SOL_OWNERSHIP')
        if btc_reduced:self.bmax=min(self.bmax,actual_btc)
        return max(D(0),actual_btc-self.bmax),D(0)
