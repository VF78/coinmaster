"""Fresh actual admission boundary, no engine/account/journal constructors."""
from dataclasses import replace
from decimal import Decimal as D
from types import SimpleNamespace as N
import pytest
from coinmaster.strategy.cm2_native import CM2Strategy
from coinmaster.strategy.cm2_policy import Config, State, Snapshot

class ID(str):
    venue="V"

def boundary(equity="100", held="3000", locked="0", order_im="0", position_mm="0"):
    btc,sol=ID("BTC"),ID("SOL")
    current=[Snapshot(D(equity),D(held),D(0),D(1),D(1))]
    balances=N(total=D(equity),locked=D(locked))
    margins={btc:(D(order_im),D(position_mm)),sol:(D(0),D(0))}
    money=lambda x:N(currency="USDC",as_decimal=lambda:x)
    account=N(base_currency="USDC",balance_total=lambda c:money(balances.total),
        balance_free=lambda c:money(balances.total-balances.locked),balance_locked=lambda c:money(balances.locked),
        margin_init=lambda i:money(margins[i][0]),margin_maint=lambda i:money(margins[i][1]),
        total_margin_init=lambda c:money(sum((m[0] for m in margins.values()),D(0))),
        total_margin_maint=lambda c:money(sum((m[1] for m in margins.values()),D(0))))
    calls=[]
    def snapshot(now):calls.append(now);return current[0]
    fake=N(clock=N(timestamp_ns=lambda:100),policy_state=State(),
        config=N(policy=Config(),btc_id=btc,sol_id=sol,exit_fee_rate=D('.000432'),limits=N(max_gross_notional=None),
            margin_policy=N(margin_for=lambda i,q,t:(q/40,q/80,D(1)))),
        cache=N(account_for_venue=lambda v:account,instrument=lambda i:N(settlement_currency="USDC")),
        _snapshot=snapshot,_latest_marks={i:N(ts_event=100) for i in (btc,sol)},_orders=lambda i:[],pre_submit_gate_blocks=[])
    return fake,btc,sol,current,balances,margins,calls

def admit(f,btc,q,s=None):
    return CM2Strategy._admit(f,btc,D(q),D(1),s or f._snapshot(100),-999)

def test_zero_native_fields_do_not_erase_held_tier_im():
    f,btc,_,current,_,_,calls=boundary()
    assert not admit(f,btc,2000,current[0])
    assert f.pre_submit_gate_blocks[-1]['reason']=='NATIVE_AGGREGATE_COLLATERAL'
    assert calls==[100]  # native clock/current snapshot, never caller now

def test_stale_caller_cash_and_positions_cannot_authorize_growth():
    f,btc,_,current,balances,_,_=boundary(equity='200',held='0')
    stale=current[0]
    assert admit(f,btc,2000,stale)
    current[0]=replace(stale,equity=D(100),btc_qty=D(3000));balances.total=D(100)
    assert not admit(f,btc,2000,stale)
    assert f.pre_submit_gate_blocks[-1]['reason']=='NATIVE_AGGREGATE_COLLATERAL'

@pytest.mark.parametrize('kind',['unknown','unpaired','stale','future','currency','balance','margin','nonfinite'])
def test_unknown_or_inconsistent_collateral_fails_closed(kind):
    f,btc,sol,current,balances,margins,_=boundary(equity='1000')
    if kind=='unknown':current[0]=replace(current[0],data_known=False)
    if kind=='unpaired':f._latest_marks[sol].ts_event=99
    if kind=='stale':f._latest_marks={i:N(ts_event=-120_000_000_000) for i in (btc,sol)}
    if kind=='future':f._latest_marks={i:N(ts_event=101) for i in (btc,sol)}
    if kind=='currency':f.cache.instrument=lambda i:N(settlement_currency='OTHER')
    if kind=='balance':f.cache.account_for_venue('V').balance_total=lambda c:N(currency='USDC',as_decimal=lambda:D(999))
    if kind=='margin':margins[btc]=(D(1),D(0))
    if kind=='nonfinite':current[0]=replace(current[0],equity=D('NaN'))
    assert not admit(f,btc,1,current[0])

def test_projected_portfolio_and_fees_boundary_exact():
    fee=D(2000)*D('.000432');needed=D(125)+fee
    f,btc,sol,current,balances,_,_=boundary(equity=str(needed),held='1500')
    current[0]=replace(current[0],sol_qty=D(1500))
    assert admit(f,btc,2000,current[0])
    current[0]=replace(current[0],equity=needed-D('.00000001'));balances.total=current[0].equity
    assert not admit(f,btc,2000,current[0])
    assert f.pre_submit_gate_blocks[-1]['reason']=='NATIVE_AGGREGATE_COLLATERAL'

def test_matching_native_locks_count_once_opaque_lock_stays_reserved():
    f,btc,_,current,balances,_,_=boundary(locked='37.5',position_mm='37.5')
    assert admit(f,btc,800,current[0])  # held75 + new20 + fee, native MM already locked
    balances.locked+=D(30)
    assert not admit(f,btc,800,current[0])
    assert f.pre_submit_gate_blocks[-1]['reason']=='NATIVE_AGGREGATE_COLLATERAL'

def test_pending_growth_credit_per_asset_and_ro_never_releases_held():
    f,btc,sol,current,_,margins,_=boundary(equity='130',locked='47.5',order_im='10',position_mm='37.5')
    inc=N(side=N(name='BUY'),leaves_qty=N(as_decimal=lambda:D(400)),is_reduce_only=False)
    # Real enum boundary; RO may reach flat, never reduces full held projection.
    from nautilus_trader.model.enums import OrderSide
    inc.side=OrderSide.BUY
    ro=N(side=OrderSide.SELL,leaves_qty=N(as_decimal=lambda:D(3000)),is_reduce_only=True)
    f._orders=lambda i:[ro,inc] if i==btc else []
    assert admit(f,btc,1600,current[0])
    # Same total exposure but BTC lock cannot reserve pending SOL growth.
    f._orders=lambda i:[ro] if i==btc else [inc]
    current[0]=replace(current[0],equity=D('125.9'))
    assert not admit(f,btc,1600,current[0])
    assert f.pre_submit_gate_blocks[-1]['reason']=='NATIVE_AGGREGATE_COLLATERAL'


def test_mandatory_exit_does_not_call_growth_collateral_gate():
    from coinmaster.strategy.cm2_policy import decide
    from runtime.tests.test_cm2_policy import feat,snap,state,configured
    d=decide(configured(),feat(),snap(btc_qty=D(1),btc_mark=D(90),data_known=False,core_data_known=True),state(stop=95))
    assert d.btc_target==0 and d.reason=='PROTECTIVE_STOP'

@pytest.mark.parametrize('fee',[D(-1),D('NaN'),D('Infinity')])
def test_invalid_fee_reserve_cannot_mint_collateral_or_raise_decimal(fee):
    f,btc,_,current,_,_,_=boundary()
    f.config.exit_fee_rate=fee
    assert not admit(f,btc,2000,current[0])
    assert f.pre_submit_gate_blocks[-1]['reason']=='NATIVE_FEE_RESERVE_UNKNOWN'

@pytest.mark.parametrize('kind',['balance','initial','maintenance','total_initial','total_maintenance'])
def test_money_currency_mismatch_is_unknown_even_when_numeric_amount_is_zero(kind):
    f,btc,_,current,_,_,_=boundary(equity='1000')
    account=f.cache.account_for_venue('V');wrong=N(currency='OTHER',as_decimal=lambda:D(0))
    if kind=='balance':account.balance_locked=lambda c:wrong
    if kind=='initial':account.margin_init=lambda i:wrong
    if kind=='maintenance':account.margin_maint=lambda i:wrong
    if kind=='total_initial':account.total_margin_init=lambda c:wrong
    if kind=='total_maintenance':account.total_margin_maint=lambda c:wrong
    assert not admit(f,btc,1,current[0])
    assert 'CURRENCY_UNKNOWN' in f.pre_submit_gate_blocks[-1]['reason']
