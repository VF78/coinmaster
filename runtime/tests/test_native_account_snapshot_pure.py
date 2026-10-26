"""Real populated native AccountState/MarginBalance/MarginAccount, no engine."""
from decimal import Decimal as D
import json
import pytest
from nautilus_trader.accounting.accounts.margin import MarginAccount
from nautilus_trader.model.events import AccountState
from nautilus_trader.model.enums import AccountType
from nautilus_trader.model.identifiers import AccountId
from nautilus_trader.model.objects import AccountBalance,MarginBalance,Money
from nautilus_trader.core.uuid import UUID4
from coinmaster.research.native_fixture import BTC_PERP,SOL_PERP
from coinmaster.strategy.native_account_snapshot import native_account_snapshot

def populated_account():
    c=BTC_PERP.quote_currency
    money=lambda x:Money(D(x),c)
    event=AccountState(account_id=AccountId('P1SIM-UNIT001'),account_type=AccountType.MARGIN,
        base_currency=c,reported=False,
        balances=[AccountBalance(money('10000.12345678'),money('25'),money('9975.12345678'))],
        margins=[MarginBalance(money('12'),money('3'),BTC_PERP.id),MarginBalance(money('8'),money('2'),SOL_PERP.id)],
        info={},event_id=UUID4(),ts_event=1,ts_init=1)
    account=MarginAccount(event,calculate_account_state=True)
    account.set_leverage(BTC_PERP.id,D(40));account.set_leverage(SOL_PERP.id,D(20))
    account.update_commissions(money('.00001234'))
    return account

def test_populated_real_native_leverage_margin_balances_roundtrip_without_export():
    a=populated_account();before=(a.balances_total(),a.margins_init(),a.margins_maint(),a.leverage(BTC_PERP.id))
    # The actual installed failing export path is demonstrated on this object.
    with pytest.raises(AttributeError,match='to_str'):type(a).to_dict(a)
    x=native_account_snapshot(a,(BTC_PERP.id,SOL_PERP.id))
    assert x['complete']and x['status']=='KNOWN'and not x['errors']
    assert x['balances_total']['USDT']['amount']=='10000.12345678'
    assert x['balances_free']['USDT']['amount']=='9975.12345678'
    assert x['commissions']['USDT']['amount']=='0.00001234'
    assert x['instruments'][str(BTC_PERP.id)]['margin_init']['amount']=='12'
    assert x['instruments'][str(SOL_PERP.id)]['margin_maint']['amount']=='2'
    assert x['instruments'][str(BTC_PERP.id)]['leverage']=='40'
    assert json.loads(json.dumps(x,allow_nan=False))==x
    assert before==(a.balances_total(),a.margins_init(),a.margins_maint(),a.leverage(BTC_PERP.id))

def test_public_getter_error_is_explicit_unknown_not_throw_and_keeps_other_facts():
    actual=populated_account()
    class ReadFailure:
        def __getattr__(self,k):return getattr(actual,k)
        def balances_free(self):raise RuntimeError('UNIT public getter unavailable')
    x=native_account_snapshot(ReadFailure(),(BTC_PERP.id,SOL_PERP.id))
    assert not x['complete']and x['status']=='UNKNOWN'and x['balances_free']=='UNKNOWN'
    assert x['errors']==[dict(field='balances_free',type='RuntimeError',message='UNIT public getter unavailable')]
    assert x['balances_total']['USDT']['amount']=='10000.12345678'
    json.dumps(x,allow_nan=False)

def test_absent_account_never_becomes_zero_or_complete():
    x=native_account_snapshot(None,(BTC_PERP.id,SOL_PERP.id))
    assert not x['complete']and x['status']=='UNKNOWN'and x['errors']
    assert 'balances_total'not in x

def test_observer_real_cache_populated_account_and_capture_failure_coverage():
    from test_sol_standing_pure import owner
    h=owner();h.cache.add_instrument(BTC_PERP);h.cache.add_account(populated_account())
    h.config.research_paired_prefix='B2_F0';h.config.btc_id=BTC_PERP.id;h.config.margin_policy=None
    h.config.research_btc_split_discount=D('.0025');h._pair_observed_rights={};h._pair_observed_marks={}
    h._pair_predecisions=[];h._pair_last_quote={};h._pending_by_order={}
    from types import SimpleNamespace as N
    h._pair.update(caps=N(bmax=D(2)),risk='ACTIVE_RISK',entry_terminal=True,debt_since=None)
    h._split_parent=dict(episode_id='P',quantity=D(4),first_quantity=D(2),side=1)
    h._md_plans={'P':dict(entry_orders={},p0=D(100),first_filled=D(2),second_filled=D(0),touched=set())}
    h._a0_enabled=lambda:False;h._entries_enabled=lambda **kw:True
    h._pair_observe_lock(1)
    row=h._pair_predecisions[-1]
    assert row['native_account_capture']['complete']and row['native_account']['status']=='KNOWN'
    json.dumps(row,allow_nan=False)
    # Separate missing-account source behavior is the established engine-free case.
    from test_sol_standing_pure import test_disabled_a0_still_observes_and_does_not_create_right_or_call_margin_gate
    test_disabled_a0_still_observes_and_does_not_create_right_or_call_margin_gate()
