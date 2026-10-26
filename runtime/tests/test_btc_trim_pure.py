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


@pytest.mark.parametrize('changed',['quantity','parent','side','position_side'])
def test_changed_eligible_state_refuses_without_target_order_or_reanchor(changed):
    from types import SimpleNamespace as N
    from coinmaster.strategy.paired_prefix import PairedPrefixResearch
    h=PairedPrefixResearch();h.config=N(btc_id='BTC')
    cap=BTCTrimCap(D(2),D(2));p=dict(role='BTC_TRIM',parent='p',side=1,risk='ACTIVE_RISK',
        eligible_ns=130,signal_ns=70,nominal_deadline_ns=1000,boundary=D(120),
        trim_activated=False,caps=cap,failed=False,close_sol=False)
    h._pair=p;h._pair_failures=[];h.paired_prefix_audit=[]
    ep=N(id='p',side=1);position=N(quantity=N(as_decimal=lambda:D(2)),is_long=True)
    if changed=='quantity':position.quantity=N(as_decimal=lambda:D('1.999'))
    if changed=='parent':ep.id='other'
    if changed=='side':ep.side=-1
    if changed=='position_side':position.is_long=False
    h._domain=N(episode=ep);h._pair_position=lambda _:position
    with pytest.raises(ValueError,match='TRIM_INCOMPARABLE_CHANGED_NATIVE_PARENT_SIDE_OR_QUANTITY'):
        h._pair_trim_quote(N(ts_event=130,bid_price=N(as_decimal=lambda:D(100))))
    assert cap.qref==cap.bmax==2 and not p['trim_activated']
    assert p['failed']and p['risk']=='UNKNOWN_RISK'
    assert not any(x['event']in('TRIM_NATIVE_ABSOLUTE_CAP','SUBMIT')for x in h.paired_prefix_audit)
