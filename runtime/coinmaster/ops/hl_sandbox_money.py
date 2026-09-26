"""Nautilus 1.231 Sandbox monetary policy for public Hyperliquid perps.

This remains the native SandboxExecutionClient/SimulatedExchange path. The
public adapter's USD-quoted, USDC-settled instrument is never rewritten.
A model-only USD/USDC 1:1 cache quote converts native PnL and margin;
commissions are calculated at USDC precision by a native FeeModel.
"""
from __future__ import annotations

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
