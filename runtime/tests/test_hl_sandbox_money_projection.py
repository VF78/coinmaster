from decimal import Decimal
from types import SimpleNamespace

from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.objects import Money

from coinmaster.ops.hl_sandbox_money import HL_VENUE, MARK_MAX_AGE_NS, native_money_projection
from coinmaster.ops.hyperliquid_testnet import BTC_PERP


class Account:
    base_currency = USDC

    def __init__(self, cash, free, locked):
        self.cash, self.free, self.locked = cash, free, locked

    def balance_total(self, currency):
        return Money(self.cash, currency)

    def balance_free(self, currency):
        return Money(self.free, currency)

    def balance_locked(self, currency):
        return Money(self.locked, currency)


class Position:
    instrument_id = BTC_PERP

    def __init__(self, realized, fees, quantity):
        self.realized_pnl = Money(realized, USDC)
        self._fees = [Money(fee, USDC) for fee in fees]
        self.quantity = Decimal(quantity)
        self.is_open = self.quantity != 0

    def commissions(self):
        return self._fees

    def unrealized_pnl(self, mark):
        return Money(self.quantity * (Decimal(mark) - Decimal('60000')), USDC)


class Cache:
    def __init__(self, cash, free, locked, position):
        self.account = Account(cash, free, locked)
        self.position = position

    def account_for_venue(self, venue):
        assert venue == HL_VENUE
        return self.account

    def positions(self):
        return [self.position]

    def instrument(self, instrument_id):
        assert instrument_id == BTC_PERP
        return SimpleNamespace(make_price=lambda value: value)


def test_native_money_after_entry_partial_tp_adverse_mark_and_close():
    now = 1_000_000_000_000
    entry = Cache('9999.73', '9999.54', '0.19', Position('-.27', ['.27'], '.01'))
    mark = {BTC_PERP: SimpleNamespace(price=Decimal('60000'), ts_event=now)}
    result = native_money_projection(entry, mark, now_ns=now)
    assert (result['native_cash'], result['native_free'], result['native_locked']) == ('9999.73', '9999.54', '0.19')
    assert result['realized_pnl_net_fees'] == '-0.27'
    assert result['fees'] == '0.27'
    assert Decimal(result["equity"]) == Decimal("9999.73")

    partial = Cache('9999.7349925', '9999.64', '0.0949925', Position('-.2650075', ['.27', '.0450075'], '.005'))
    mark[BTC_PERP] = SimpleNamespace(price=Decimal('59000'), ts_event=now)
    result = native_money_projection(partial, mark, now_ns=now)
    assert result['fees'] == '0.3150075'
    assert Decimal(result["unrealized_pnl"]) == Decimal("-5")
    assert Decimal(result['equity']) == Decimal('9994.7349925')
    assert Decimal(result['equity']) == Decimal(result['native_cash']) + Decimal(result['unrealized_pnl'])

    stale = native_money_projection(partial, {BTC_PERP: SimpleNamespace(price=Decimal('59000'), ts_event=now - MARK_MAX_AGE_NS - 1)}, now_ns=now)
    assert stale['equity'] is None and stale['unrealized_pnl'] is None
    assert stale['mark_state'] == 'STALE_OR_MISSING'

    closed = Cache('9999.739985', '9999.739985', '0', Position('-.260015', ['.27', '.090015'], '0'))
    result = native_money_projection(closed, {}, now_ns=now)
    assert Decimal(result['equity']) == Decimal('9999.739985')
    assert result['native_locked'] == '0'
