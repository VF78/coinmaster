"""Stock-native full-fill extension; assumed capacity, never observed depth."""
from nautilus_trader.backtest.models import FillModel
from nautilus_trader.model.book import OrderBook
from nautilus_trader.model.data import BookOrder
from nautilus_trader.model.enums import BookType, LiquiditySide, OrderSide


class ZeroImpactFullFillDiagnostic(FillModel):
    """Zero-impact taker BBO/full leaves; maker requires strict crossing."""
    assumption = "ZERO_MARKET_IMPACT_FULL_FILL_DIAGNOSTIC"

    def __init__(self):
        super().__init__(prob_fill_on_limit=0.0, prob_slippage=0.0)

    def get_orderbook_for_fill_simulation(self, instrument, order, best_bid, best_ask):
        book = OrderBook(instrument_id=instrument.id, book_type=BookType.L2_MBP)
        bid, ask = best_bid, best_ask
        if order.liquidity_side == LiquiditySide.MAKER:
            if order.side == OrderSide.BUY:
                if best_ask >= order.price:
                    return book
                ask = order.price
            else:
                if best_bid <= order.price:
                    return book
                bid = order.price
        # Native leaves_qty defines this diagnostic assumption. No magic depth.
        for side, price, identity in ((OrderSide.BUY, bid, 1), (OrderSide.SELL, ask, 2)):
            book.add(BookOrder(side=side, price=price, size=order.leaves_qty, order_id=identity), 0, 0)
        return book


def zero_impact_venue_options(fill_model=None):
    """Use order-sized simulated capacity without re-capping to recorded L1.

    Pinned NT 1.231 applies recorded-book consumption after the custom market
    fill hook. Enabling it would reintroduce the nominal 1000-unit quote cap.
    Real recorded L1/L2 liquidity models must enable consumption separately;
    this helper belongs only to the explicit full-fill/zero-impact diagnostic.
    """
    if fill_model is None:
        fill_model=ZeroImpactFullFillDiagnostic()
    if not isinstance(fill_model,ZeroImpactFullFillDiagnostic):
        raise TypeError("ZERO_IMPACT_FILL_MODEL_REQUIRED")
    return dict(fill_model=fill_model,liquidity_consumption=False)
