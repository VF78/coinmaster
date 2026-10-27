"""Risk-owner-only timing of the existing captured-Bybit margin module.

No new margin/cash formula. Portfolio(10) first applies its native stock account
update; this subscriber(5) reapplies the SAME existing captured-tier process
before Strategy(default0) reads a joint snapshot. The process body only updates
IM/MM and native locked/free balances (total cash unchanged), plus its bounded
observed ring. Repeated same cache/marks calls are financially idempotent.

Frozen OFF diagnostics retain their exact original module registration.
"""
from coinmaster.research.native_fixture import BybitTierMarginModule


class MethodATierMarginModule(BybitTierMarginModule):
    def register_venue(self,exchange):
        super().register_venue(exchange)
        self.msgbus.subscribe(topic='events.order.*',handler=self.on_native_margin_boundary,priority=5)
        self.msgbus.subscribe(topic='events.position.*',handler=self.on_native_margin_boundary,priority=5)

    def on_native_margin_boundary(self,event):
        if event.instrument_id in self._selected_leverage:
            self.process(event.ts_event)


from coinmaster.research.native_book import NativeBookWitness
from nautilus_trader.model.data import QuoteTick


class MethodABookWitness(NativeBookWitness):
    """Existing strict barrier plus small complete causal input receipts."""
    def pre_process(self,data):
        super().pre_process(data)
        if isinstance(data,QuoteTick) and self.strategy is not None:
            strategy=self.strategy
            held=strategy._pair_qty(strategy.config.sol_id)
            if held and not strategy._pair:raise ValueError('METHOD_A_SOL_WITHOUT_NATIVE_OWNER')
            strategy._mr_log('SOL_BOUNDARY_RECEIPT',data.ts_event,
                quote_instrument=str(data.instrument_id),native_input_epoch=self.epochs[data.instrument_id],
                sol_native_held=str(held),boundary_state_ref=strategy._mr_last_sol_boundary,
                boundary_counters=dict(strategy._pair_sol_boundary_counts))
