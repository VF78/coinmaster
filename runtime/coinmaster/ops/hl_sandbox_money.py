"""Nautilus 1.231 Sandbox monetary policy for public Hyperliquid perps.

This remains the native SandboxExecutionClient/SimulatedExchange path. The
public adapter's USD-quoted, USDC-settled instrument is never rewritten.
A model-only USD/USDC 1:1 cache quote converts native PnL and margin;
commissions are calculated at USDC precision by a native FeeModel.
"""
from __future__ import annotations

import time
from decimal import Decimal

from nautilus_trader.adapters.sandbox.execution import SandboxExecutionClient
from nautilus_trader.adapters.sandbox.factory import SandboxLiveExecClientFactory as NativeSandboxFactory
from nautilus_trader.backtest.engine import SimulatedExchange
from nautilus_trader.backtest.execution_client import BacktestExecClient
from nautilus_trader.backtest.models import FeeModel, FillModel, LatencyModel
from nautilus_trader.common.component import TestClock
from nautilus_trader.common.providers import InstrumentProvider
from nautilus_trader.live.execution_client import LiveExecutionClient
from nautilus_trader.model.currencies import USD, USDC
from nautilus_trader.model.data import QuoteTick
from nautilus_trader.model.enums import LiquiditySide, PriceType, account_type_from_str, book_type_from_str, oms_type_from_str
from nautilus_trader.model.identifiers import AccountId, ClientId, InstrumentId, Symbol, Venue
from nautilus_trader.model.instruments import CryptoPerpetual, CurrencyPair
from nautilus_trader.model.objects import Currency, Money, Price, Quantity

HL_VENUE = Venue("HYPERLIQUID")
HL_IDS = frozenset({
    InstrumentId.from_str("BTC-USD-PERP.HYPERLIQUID"),
    InstrumentId.from_str("SOL-USD-PERP.HYPERLIQUID"),
})
MODEL_FX_ID = InstrumentId.from_str("USD/USDC.HYPERLIQUID")
MAKER_RATE = Decimal("0.00015")
TAKER_RATE = Decimal("0.00045")


def model_fx_pair_and_quote() -> tuple[CurrencyPair, QuoteTick]:
    """Explicit virtual 1:1 peg assumption; this is no public FX observation."""
    pair = CurrencyPair(
        MODEL_FX_ID, Symbol("USD/USDC"), USD, USDC, 5, 5,
        Price.from_str("0.00001"), Quantity.from_str("0.00001"), 0, 0,
    )
    quote = QuoteTick(
        MODEL_FX_ID, Price.from_str("1.00000"), Price.from_str("1.00000"),
        Quantity.from_str("1000.00000"), Quantity.from_str("1000.00000"), 1, 1,
    )
    return pair, quote


def model_fx_ready(cache) -> bool:
    """Require the explicit model pair on both sides before native orders."""
    try:
        return all(
            cache.get_xrate(HL_VENUE, USD, USDC, side) == 1.0
            for side in (PriceType.BID, PriceType.ASK)
        )
    except (RuntimeError, ValueError):
        return False


class HyperliquidUsdcFeeModel(FeeModel):
    """Charge approved public-base assumptions through native fill events."""

    def get_commission(self, order, fill_qty, fill_px, instrument):
        if (
            not isinstance(instrument, CryptoPerpetual)
            or instrument.id not in HL_IDS
            or instrument.is_inverse
            or instrument.quote_currency != USD
            or instrument.settlement_currency != USDC
        ):
            raise RuntimeError("HL_SANDBOX_FEE_INSTRUMENT_CONTRACT_CHANGED")
        if order.liquidity_side == LiquiditySide.MAKER:
            rate = MAKER_RATE
        elif order.liquidity_side == LiquiditySide.TAKER:
            rate = TAKER_RATE
        else:
            raise RuntimeError("HL_SANDBOX_FEE_LIQUIDITY_UNKNOWN")
        # Avoid USD Money precision (2 decimals) before applying the USDC fee.
        notional = fill_qty.as_decimal() * fill_px.as_decimal() * instrument.multiplier.as_decimal()
        return Money(notional * rate, USDC)


class HyperliquidUsdcSandboxExecutionClient(SandboxExecutionClient):
    """Version-pinned 1.231 Sandbox constructor with one native exchange.

    SandboxExecutionClient 1.231 hardcodes MakerTakerFeeModel, and its
    SimulatedExchange.fee_model is readonly. This constructor retains every
    official Sandbox option and substitutes only the fee model.
    """

    def __init__(self, loop, portfolio, msgbus, cache, clock, config) -> None:
        if config.venue != "HYPERLIQUID" or config.base_currency != "USDC":
            raise RuntimeError("HL_SANDBOX_ACCOUNT_CONTRACT_CHANGED")
        venue = Venue(config.venue)
        oms_type = oms_type_from_str(config.oms_type)
        account_type = account_type_from_str(config.account_type)
        base_currency = Currency.from_str(config.base_currency)
        self.test_clock = TestClock()
        LiveExecutionClient.__init__(
            self, loop=loop, client_id=ClientId(config.venue), venue=venue,
            oms_type=oms_type, account_type=account_type, base_currency=base_currency,
            instrument_provider=InstrumentProvider(), msgbus=msgbus, cache=cache,
            clock=clock, config=None,
        )
        self._set_account_id(AccountId(f"{config.venue}-001"))
        self.exchange = SimulatedExchange(
            venue=venue, oms_type=oms_type, account_type=account_type,
            starting_balances=[Money.from_str(b) for b in config.starting_balances],
            base_currency=base_currency, default_leverage=config.default_leverage,
            leverages=config.leverages or {}, modules=[], portfolio=portfolio,
            msgbus=self._msgbus, cache=cache, clock=self.test_clock,
            fill_model=FillModel(), fee_model=HyperliquidUsdcFeeModel(),
            latency_model=LatencyModel(0), book_type=book_type_from_str(config.book_type),
            frozen_account=config.frozen_account, bar_execution=config.bar_execution,
            trade_execution=config.trade_execution, reject_stop_orders=config.reject_stop_orders,
            support_gtd_orders=config.support_gtd_orders,
            support_contingent_orders=config.support_contingent_orders,
            use_position_ids=config.use_position_ids, use_random_ids=config.use_random_ids,
            use_reduce_only=config.use_reduce_only, use_message_queue=False,
        )
        self._client = BacktestExecClient(
            exchange=self.exchange, msgbus=msgbus, cache=cache, clock=self.test_clock,
        )
        self.exchange.register_client(self._client)
        self.exchange.initialize_account()

    def submit_order(self, command):
        if not model_fx_ready(self._cache):
            raise RuntimeError("HL_SANDBOX_MODEL_FX_MISSING")
        if command.order.instrument_id not in HL_IDS:
            raise RuntimeError("HL_SANDBOX_ONLY_BTC_SOL_ORDERS")
        return super().submit_order(command)

    def submit_order_list(self, command):
        if not model_fx_ready(self._cache):
            raise RuntimeError("HL_SANDBOX_MODEL_FX_MISSING")
        if any(order.instrument_id not in HL_IDS for order in command.order_list.orders):
            raise RuntimeError("HL_SANDBOX_ONLY_BTC_SOL_ORDERS")
        return super().submit_order_list(command)


class SandboxLiveExecClientFactory(NativeSandboxFactory):
    @staticmethod
    def create(loop, name, config, portfolio, msgbus, cache, clock):
        return HyperliquidUsdcSandboxExecutionClient(
            loop=loop, portfolio=portfolio, msgbus=msgbus, cache=cache,
            clock=clock, config=config,
        )

MARK_MAX_AGE_NS = 120_000_000_000


def native_equity(cache, marks, *, now_ns: int | None = None) -> Decimal:
    """Current native USDC cash plus open marked PnL; UNKNOWN raises."""
    now_ns = time.time_ns() if now_ns is None else now_ns
    if not model_fx_ready(cache):
        raise ValueError("HL_SANDBOX_MODEL_FX_MISSING")
    account = cache.account_for_venue(HL_VENUE)
    if account is None or account.base_currency != USDC:
        raise ValueError("NATIVE_USDC_ACCOUNT_MISSING")
    balance = account.balance_total(USDC)
    if balance is None or balance.currency != USDC or not balance.as_decimal().is_finite():
        raise ValueError("NATIVE_USDC_BALANCE_MISSING")
    total = balance.as_decimal()
    for position in cache.positions_open():
        if position.instrument_id not in HL_IDS:
            raise ValueError("FOREIGN_SANDBOX_POSITION")
        mark = marks.get(position.instrument_id)
        instrument = cache.instrument(position.instrument_id)
        if mark is None or instrument is None or mark.ts_event > now_ns or now_ns - mark.ts_event > MARK_MAX_AGE_NS:
            raise ValueError("NATIVE_EQUITY_MARK_STALE_OR_MISSING")
        pnl = position.unrealized_pnl(instrument.make_price(mark.price))
        if pnl.currency != USD or not pnl.as_decimal().is_finite():
            raise ValueError("NATIVE_UNREALIZED_CURRENCY_CHANGED")
        total += pnl.as_decimal()  # Same explicit 1:1 model FX as native_money_projection.
    return total


def native_money_projection(cache, marks, *, now_ns: int | None = None) -> dict[str, str | None]:
    """Read current and archived native position cycles against one USDC account.

    The pinned HL instrument quotes PnL in USD, while native commissions and
    cash are USDC. The explicit 1:1 model FX cache quote converts native PnL;
    no fill, realized PnL, or funding cashflow is independently recomputed.
    """
    now_ns = time.time_ns() if now_ns is None else now_ns
    if not model_fx_ready(cache):
        raise ValueError("HL_SANDBOX_MODEL_FX_MISSING")
    account = cache.account_for_venue(HL_VENUE)
    if account is None or account.base_currency != USDC:
        raise ValueError("NATIVE_USDC_ACCOUNT_MISSING")
    result = {}
    for name, getter in (("native_cash", account.balance_total), ("native_free", account.balance_free), ("native_locked", account.balance_locked)):
        value = getter(USDC)
        if value is None or value.currency != USDC or not value.as_decimal().is_finite():
            raise ValueError("NATIVE_USDC_BALANCE_MISSING")
        result[name] = str(value.as_decimal())

    # NETTING replaces a closed cycle on reopen. The old native Position is
    # retained as a closed snapshot; count each fill-trade set only once.
    cycles = {}
    archived = [item for item in cache.position_snapshots() if item.is_closed]
    for position in (*archived, *cache.positions()):
        if position.instrument_id not in HL_IDS:
            continue
        if not position.trade_ids:
            raise ValueError("NATIVE_POSITION_TRADES_MISSING")
        key = (str(position.instrument_id), tuple(sorted(map(str, position.trade_ids))))
        previous = cycles.get(key)
        if previous is None or position.ts_last >= previous.ts_last:
            cycles[key] = position

    gross_realized_usd = Decimal("0")
    fees_usdc = Decimal("0")
    unrealized_usd = Decimal("0")
    marks_ready = True
    for position in cycles.values():
        pnl = position.realized_pnl
        if pnl is not None:
            if pnl.currency != USD or not pnl.as_decimal().is_finite():
                raise ValueError("NATIVE_REALIZED_CURRENCY_CHANGED")
            gross_realized_usd += pnl.as_decimal()
        for commission in position.commissions():
            if commission.currency != USDC or not commission.as_decimal().is_finite():
                raise ValueError("NATIVE_FEE_CURRENCY_CHANGED")
            fees_usdc += commission.as_decimal()
        if not position.is_open:
            continue
        mark = marks.get(position.instrument_id)
        instrument = cache.instrument(position.instrument_id)
        if mark is None or instrument is None or mark.ts_event > now_ns or now_ns - mark.ts_event > MARK_MAX_AGE_NS:
            marks_ready = False
            continue
        value = position.unrealized_pnl(instrument.make_price(mark.price))
        if value.currency != USD or not value.as_decimal().is_finite():
            raise ValueError("NATIVE_UNREALIZED_CURRENCY_CHANGED")
        unrealized_usd += value.as_decimal()
    # The same 1:1 model quote used by the native Sandbox account conversion.
    realized_net_usdc = gross_realized_usd - fees_usdc
    result.update({
        "realized_pnl_net_fees": str(realized_net_usdc),
        "fees": str(fees_usdc),
        "unrealized_pnl": str(unrealized_usd) if marks_ready else None,
        "equity": str(Decimal(result["native_cash"]) + unrealized_usd) if marks_ready else None,
        "mark_state": "CURRENT" if marks_ready else "STALE_OR_MISSING",
    })
    return result
