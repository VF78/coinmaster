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
from coinmaster.research.method_a_risk_rows import wire
from dataclasses import asdict
from coinmaster.research.method_a_receipt_codec import receipt_owner_values


class MethodABookWitness(NativeBookWitness):
    """Existing strict barrier plus small complete causal input receipts."""
    def bind_receipt_source(self,engine):
        # Public native getters only. Registration precedes first engine.run.
        self.receipt_engine=engine
        self.receipt_ordinal=0
        self.receipt_episode=None

    def receipt_snapshot(self):
        if not hasattr(self,'receipt_engine'):
            return dict(schema='coinmaster.method-a-native-receipt.v1',
                availability='UNKNOWN_UNBOUND_PRODUCER',financial_qualification=False)
        self.receipt_ordinal+=1
        ep=self.strategy._domain.episode
        key=(None if ep is None else ep.id,self.strategy._mr_episode)
        previous=self.receipt_episode
        self.receipt_episode=key
        if key[1]<=0 or key==previous:
            return dict(schema='coinmaster.method-a-native-receipt.v1',
                receipt_ordinal=self.receipt_ordinal,availability='NOT_CAPTURED_NO_NEW_RISK_EPISODE',
                financial_qualification=False)
        try:
            raw=native_receipt_snapshot(self.strategy,self.receipt_engine,self.receipt_ordinal)
        except Exception as error:
            # Evidence failure is UNKNOWN, never a trading-state exception.
            # Strict native/risk pre_process errors remain outside this catch.
            return dict(schema='coinmaster.method-a-native-receipt.v1',
                receipt_ordinal=self.receipt_ordinal,parent=key[0],risk_episode_id=str(key[0])+':'+str(key[1]),
                previous_receipt_parent=None if previous is None else previous[0],
                previous_receipt_episode=None if previous is None else previous[1],
                risk_sequence_before_receipt=self.strategy._mr_sequence,
                availability='UNKNOWN_COLLECTOR_EXCEPTION',collection_error_type=type(error).__name__,
                complete_command_universe='UNKNOWN',financial_qualification=False)
        raw['previous_receipt_parent']=None if previous is None else previous[0]
        raw['previous_receipt_episode']=None if previous is None else previous[1]
        return raw

    def pre_process(self,data):
        super().pre_process(data)
        if isinstance(data,QuoteTick) and self.strategy is not None:
            strategy=self.strategy
            held=strategy._pair_qty(strategy.config.sol_id)
            if held and not strategy._pair:raise ValueError('METHOD_A_SOL_WITHOUT_NATIVE_OWNER')
            strategy._mr_log('SOL_BOUNDARY_RECEIPT',data.ts_event,
                quote_instrument=str(data.instrument_id),native_input_epoch=self.epochs[data.instrument_id],global_input_index=sum(self.epochs.values()),native_quote=data.to_dict(data),
                sol_native_held=str(held),boundary_state_ref=strategy._mr_last_sol_boundary,
                native_receipt_snapshot=self.receipt_snapshot(),
                boundary_counters=dict(strategy._pair_sol_boundary_counts))


def native_receipt_snapshot(strategy,engine,ordinal):
    """Raw receipt facts; coverage/financial qualification require source review.

    No native command/event is created, no order/cache/factory is mutated.
    All cached orders are retained, including foreign and terminal orders.
    Generic counters are observations, never an asserted SOL command count.
    """
    cache=strategy.cache
    orders=list(cache.orders())
    indexed={str(o.client_order_id):o for o in orders}
    def resolve(oid):
        key=str(oid);order=indexed.get(key)
        return dict(client_order_id=key,resolved=order is not None,
                    instrument=None if order is None else str(order.instrument_id))
    pending=[dict(**resolve(oid),intent=asdict(intent)) for oid,intent in strategy._pending_by_order.items()]
    owners=[]
    for oid,owner in strategy._pair_orders.items():
        # Preserve the complete existing owner mapping; instrument is the sole
        # native identifier in this mapping. Existing wire owns Decimal tuples.
        values=receipt_owner_values(owner)
        owners.append(dict(**resolve(oid),owner=values))
    ep=strategy._domain.episode
    kernel=engine.kernel
    return wire(dict(schema='coinmaster.method-a-native-receipt.v1',
        receipt_ordinal=ordinal,risk_sequence_before_receipt=strategy._mr_sequence,
        parent=None if ep is None else ep.id,
        risk_episode_id=str(None if ep is None else ep.id)+':'+str(strategy._mr_episode),
        input_binding=strategy.config.research_method_a_input_binding,
        high_watermarks=dict(exec_command_count=kernel.exec_engine.command_count,
            exec_event_count=kernel.exec_engine.event_count,
            factory_client_order_id_count=strategy.order_factory.get_client_order_id_count(),
            factory_order_list_id_count=strategy.order_factory.get_order_list_id_count()),
        producer_inventory=dict(strategy_ids=[str(v) for v in kernel.trader.strategy_ids()],
            actor_ids=[str(v) for v in kernel.trader.actor_ids()],
            exec_algorithm_ids=[str(v) for v in kernel.trader.exec_algorithm_ids()]),
        native_positions=[p.to_dict() for p in cache.positions()],
        native_orders=[o.to_dict() for o in orders],
        native_init_events=[type(o.init_event).to_dict(o.init_event) for o in orders],
        native_open_ids=[resolve(o.client_order_id) for o in cache.orders_open()],
        native_inflight_ids=[resolve(o.client_order_id) for o in cache.orders_inflight()],
        native_emulated_ids=[resolve(o.client_order_id) for o in cache.orders_emulated()],
        pending_by_order=pending,paired_owners=owners,
        domain_pending={} if ep is None else {str(k):asdict(v) for k,v in ep.pending.items()},
        queued_intents=[dict(intent=asdict(intent),sigma=sigma,decision_index=index)
            for intent,sigma,index in strategy._queued_intents],
        mandatory_sol_exit=None if strategy._mandatory_sol_exit is None else
            dict(intent=asdict(strategy._mandatory_sol_exit[0]),sigma=strategy._mandatory_sol_exit[1],
                 decision_index=strategy._mandatory_sol_exit[2]),
        native_control_state=dict(liquidating=strategy._liquidating,
            forced_close_reason=strategy._forced_close_reason,
            exiting=strategy.is_exiting(),method_a_failed=strategy._mr_failed),
        unresolved_ids=sorted({r['client_order_id'] for r in pending+owners if not r['resolved']}),
        complete_command_universe='UNKNOWN_REQUIRES_SEALED_SOURCE_PROOF',
        raw_native_queue_visibility='NOT_EXPOSED_BY_PUBLIC_API',
        financial_qualification=False))
