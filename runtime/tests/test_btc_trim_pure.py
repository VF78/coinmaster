"""Exact ex-ante risk/lot algebra only, no matcher/PnL/account simulation."""
from decimal import Decimal as D
from fractions import Fraction as F
import pytest
from coinmaster.strategy.btc_trim import variance_target,BTCTrimCap

@pytest.mark.parametrize('rho',['.25','.3','.5','.75','.9','1'])
@pytest.mark.parametrize('qref',['.001','.123','1.817','2','10.037'])
def test_exact_native_lattice_floor_and_declared_variance(rho,qref):
    args=tuple(map(D,(qref,'.001','.1','100','100','2','1',rho,'1')))
    if D(qref)<D('.1'):
        with pytest.raises(ValueError):variance_target(*args)
        return
    result=variance_target(*args);v=F(result['variance_numerator'],result['variance_denominator'])
    target=F(result['target_btc']);q=F(D(qref));lot=F(D('.001'))
    assert 0<=v<=1 and target*target<=q*q*v<(target+lot)*(target+lot)
    assert target/lot==(target/lot).__floor__()
    c=F(result['intended_sol'])*F(100)*F(1)/(q*F(100)*F(2))
    assert v==(1-F(D(rho))*c)**2+c*c*(1-F(D(rho))**2)

@pytest.mark.parametrize('index,value',[(0,'0'),(3,'NaN'),(5,'0'),(6,'-1'),(7,'1.1'),(7,'-0.1'),(8,'0')])
def test_unknown_inputs_are_incomparable(index,value):
    args=list(map(D,('2','.001','.1','100','100','2','1','.75','1')));args[index]=D(value)
    with pytest.raises(ValueError,match='TRIM_INCOMPARABLE'):variance_target(*args)


def test_risk_increase_is_stop_not_negative_cut():
    with pytest.raises(ValueError,match='RISK_INCREASE'):
        variance_target(*map(D,('2','.001','.1','100','100','2','1','.1','1')))


def test_own_btc_cap_does_not_invent_sol_credit_or_restore():
    cap=BTCTrimCap(D(2),D('1.414'))
    assert cap.reconcile(D(2),D(0),sol_reduced=False,btc_reduced=False,active_risk=True)==(D('.586'),D(0))
    assert cap.reconcile(D('1.5'),D(0),sol_reduced=False,btc_reduced=True,active_risk=False)[0]==D('.086')
    assert cap.bmax==D('1.414')and cap.solmax==0
    cap.reconcile(D(1),D(0),sol_reduced=False,btc_reduced=True,active_risk=False)
    assert cap.bmax==1
    with pytest.raises(ValueError,match='UNRELATED_SOL'):
        cap.reconcile(D(1),D('.1'),sol_reduced=False,btc_reduced=False,active_risk=False)
