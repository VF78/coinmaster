"""Read-only public native matching-book witness for standing-TP research.

No order/cache mutation, matching override, synthetic ACK or economic model.
"""
from nautilus_trader.backtest.modules import SimulationModule
from nautilus_trader.backtest.config import SimulationModuleConfig
from nautilus_trader.model.data import QuoteTick


class NativeBookWitness(SimulationModule):
    def __init__(self, *, detailed=False):
        super().__init__(SimulationModuleConfig()); self.strategy=None; self.current={}; self.epochs={}; self.audit=[]; self.detailed=detailed

    def __repr__(self): return 'NativeBookWitness(stock-public-read-only)'

    def bind(self, strategy):
        if self.strategy is not None: raise ValueError('NATIVE_BOOK_WITNESS_ALREADY_BOUND')
        if self.exchange is None or self.exchange.oms_type.name != 'NETTING' or not self.exchange.use_message_queue:
            raise ValueError('STANDING_NATIVE_TRANSPORT_OR_OMS_UNKNOWN')
        latency=self.exchange.latency_model
        if latency is not None and (latency.base_latency_nanos or latency.insert_latency_nanos or latency.update_latency_nanos):
            raise ValueError('STANDING_NATIVE_INSERT_UPDATE_MUST_BE_ZERO')
        self.strategy=strategy

    def pre_process(self,data):
        if isinstance(data,QuoteTick):
            if self.strategy is not None:self.strategy._tp_settled('BEFORE_NATIVE_MATCHING_INPUT',data.ts_event)
            key=data.instrument_id;self.current[key]=data;self.epochs[key]=self.epochs.get(key,0)+1

    def process(self,ts_now):
        # process() is a settlement observation, not a new matching input. A
        # zero-latency modify enqueued by the current drain can still be waiting
        # for the next stock drain pass. Before-input is the strict barrier.
        if self.strategy is not None:
            self.strategy._tp_transient_boundary('NATIVE_SETTLEMENT_PASS',ts_now)

    def matching(self,instrument_id):
        quote=self.current.get(instrument_id);book=self.exchange.get_book(instrument_id)
        if quote is None or book is None:raise ValueError('NATIVE_MATCHING_BOOK_UNKNOWN')
        bid=book.best_bid_price();ask=book.best_ask_price()
        if bid is None or ask is None or book.ts_last!=quote.ts_event or bid!=quote.bid_price or ask!=quote.ask_price:
            raise ValueError('NATIVE_MATCHING_BOOK_TICK_IDENTITY_UNKNOWN')
        return dict(epoch=self.epochs[instrument_id],tick_identity=id(quote),timestamp_ns=quote.ts_event,
            book_timestamp_ns=book.ts_last,sequence=book.sequence,bid=str(bid),ask=str(ask),bid_size=str(book.best_bid_size()),ask_size=str(book.best_ask_size()))
