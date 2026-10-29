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
