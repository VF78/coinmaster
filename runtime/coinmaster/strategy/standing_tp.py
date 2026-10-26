"""Opt-in standing BTC protection using stock orders/cache and queued commands.

This owns no position/cash model. Integer rights are derived from genuine fills
and existing target_lots only at inventory-changing entry/debt transitions.
"""
from decimal import Decimal as D
from nautilus_trader.model.identifiers import ClientOrderId
from coinmaster.strategy.market_redesign import target_lots, u_prices


def standing_after_fill(rights, level, lots):
    if type(lots) is not int or lots <= 0 or level not in rights or lots > rights[level]:
        raise ValueError('STANDING_TP_FILL_EXCEEDS_PRE_FILL_RIGHT')
    result = dict(rights); result[level] -= lots
    return result


def marketable(side, price, bid, ask):
    if side not in (-1, 1) or any(not v.is_finite() or v <= 0 for v in (price, bid, ask)) or bid > ask:
        raise ValueError('STANDING_UNKNOWN_MATCHING_BBO')
    return price <= bid if side == -1 else price >= ask


class StandingTPResearch:
    def _tp_enabled(self):
        return bool(self.config.research_btc_standing_tp)

    def _tp_init(self):
        self._tp_owners = {}; self._tp_commands = {}; self._tp_seq = 0
        self._tp_seen_events = set(); self._tp_seen_trades = set(); self.standing_tp_audit = []
        self._tp_audit_counts = {}; self._tp_audit_state = {}

    def _tp_log(self, event, ts, **data):
        self._tp_audit_counts[event]=self._tp_audit_counts.get(event,0)+1
        if event in {'SETTLED','NATIVE_BOUNDARY'} and not getattr(self.config.research_native_book,'detailed',False):
            # Runtime guards still execute on EVERY boundary. Long prefixes keep
            # state changes/counters; the bounded engineering witness logs all.
            state={k:v for k,v in data.items() if k!='book'}
            key=(event,data.get('label'));fingerprint=repr(state)
            if self._tp_audit_state.get(key)==fingerprint:return
            self._tp_audit_state[key]=fingerprint
        self.standing_tp_audit.append(dict(event=event, timestamp_ns=str(ts), **data))

    def _tp_plan(self):
        ep = self._domain.episode
        return (ep, self._md_plans.get(ep.id)) if ep else (None, None)

    def _tp_held_lots(self):
        positions = [p for p in self.cache.positions_open() if p.instrument_id == self.config.btc_id]
        ep = self._domain.episode
        if len(positions) > 1 or (positions and (not ep or positions[0].is_long != (ep.side == 1))):
            raise ValueError('STANDING_NATIVE_POSITION_UNKNOWN')
        step = self.cache.instrument(self.config.btc_id).size_increment.as_decimal()
        quantity = positions[0].quantity.as_decimal() if positions else D(0)
        lots = quantity / step
        if lots != lots.to_integral_value(): raise ValueError('STANDING_NONINTEGRAL_NATIVE_POSITION')
        return int(lots)

    def _tp_book(self):
        provider = self.config.research_native_book
        if provider is None: raise ValueError('STANDING_NATIVE_BOOK_PROVIDER_REQUIRED')
        return provider.matching(self.config.btc_id)

    def _tp_owned_order(self, oid, owner):
        order = self.cache.order(ClientOrderId(oid))
        intent = self._pending_by_order.get(oid)
        if order is None or intent is None or intent.id != owner['intent_id'] or intent.episode_id != owner['parent'] or intent.level != owner['level']:
            raise ValueError('STANDING_CURRENT_OWNER_UNKNOWN')
        if order.strategy_id != self.id or order.instrument_id != self.config.btc_id or not order.is_reduce_only or order.side.name != owner['side'] or order.exec_algorithm_id is not None:
            raise ValueError('STANDING_NATIVE_ORDER_CONFORMANCE')
        # NETTING may put a position ID on an actual fill without indexing the
        # order. Explicitly linked/cache-associated protective orders are outside
        # this registered route; never equate the two native properties.
        if self.cache.position_id(order.client_order_id) is not None:
            raise ValueError('STANDING_UNEXPECTED_PROTECTIVE_POSITION_LINK')
        return order

    def _tp_bind_order(self, order, intent):
        if not self._tp_enabled() or intent.action != 'BTC_REDUCE': return
        m = self._md_plans[intent.episode_id]; oid = str(order.client_order_id)
        self._tp_owners[oid] = dict(parent=intent.episode_id, level=intent.level, intent_id=intent.id,
            generation=m['generation'], side=order.side.name, ack_generation=None, ack_sequence=None,
            initialized_event_id=str(order.init_event.id), strategy_id=str(order.strategy_id))
        m['order_generation'][oid] = m['generation']

    def _tp_native_event(self, event, route):
        if not self._tp_enabled(): return
        oid = str(event.client_order_id); owner = self._tp_owners.get(oid)
        if owner is None: return
        eid = str(event.id); name = type(event).__name__
        self._tp_log('NATIVE_ROUTE', event.ts_event, event_id=eid, event_type=name, order_id=oid, route=route)
        if eid in self._tp_seen_events: return
        self._tp_seen_events.add(eid)
        if event.instrument_id != self.config.btc_id or str(event.strategy_id) != owner['strategy_id']:
            raise ValueError('STANDING_FOREIGN_EVENT_OWNER')
        if name == 'OrderInitialized':
            # Public submit publishes this exact bound initialization BEFORE
            # cache.add_order. It earns neither ACK nor protection.
            if eid != owner['initialized_event_id'] or event.side.name != owner['side']:
                raise ValueError('STANDING_PRE_CACHE_INITIALIZATION_UNKNOWN')
            return
        order = self.cache.order(ClientOrderId(oid))
        if name in {'OrderFilled','OrderCanceled','OrderExpired','OrderRejected','OrderDenied'}:
            # Generic delivery can follow typed terminal ownership cleanup and
            # even a current-parent rollover. Only actual cache event history is
            # credited; immutable old history never restores an intent/right.
            if order is None or order.strategy_id != self.id or order.instrument_id != self.config.btc_id or order.side.name != owner['side'] or not order.is_reduce_only:
                raise ValueError('STANDING_TERMINAL_NATIVE_HISTORY_UNKNOWN')
            if not any(str(e.id)==eid for e in order.events):
                raise ValueError('STANDING_TERMINAL_EVENT_NOT_IN_NATIVE_HISTORY')
            if not order.is_closed:
                self._tp_owned_order(oid,owner)
            if order.exec_algorithm_id is not None or self.cache.position_id(order.client_order_id) is not None:
                raise ValueError('STANDING_UNEXPECTED_HISTORICAL_PROTECTIVE_LINK')
            return
        order = self._tp_owned_order(oid, owner)
        if name == 'OrderModifyRejected':
            raise ValueError('STANDING_VALID_MODIFY_REJECTED')
        if name == 'OrderUpdated':
            command = self._tp_commands.get(oid)
            if command is None: raise ValueError('STANDING_UNEXPECTED_NATIVE_UPDATE')
            if order.quantity.as_decimal() != command['total'] or command['generation'] != owner['generation']:
                raise ValueError('STANDING_ACK_QUANTITY_OR_GENERATION_UNKNOWN')
            owner['ack_generation'] = command['generation']; owner['ack_sequence'] = command['sequence']
            del self._tp_commands[oid]
            self._tp_log('LATEST_MODIFY_ACK', event.ts_event, order_id=oid, generation=owner['generation'], sequence=owner['ack_sequence'], native_event_id=eid, total=str(order.quantity), filled=str(order.filled_qty), leaves=str(order.leaves_qty))
        if name == 'OrderAccepted':
            owner['ack_generation'] = owner['generation']; owner['ack_sequence'] = 0
        if name != 'OrderFilled': self._tp_transient_boundary('NATIVE_'+name,event.ts_event)

    def _tp_before_fill(self, event):
        if not self._tp_enabled(): return
        oid = str(event.client_order_id); owner = self._tp_owners.get(oid)
        if owner is None: return
        trade = str(event.trade_id)
        if trade in self._tp_seen_trades: raise ValueError('STANDING_DUPLICATE_NATIVE_FILL_DELIVERY')
        self._tp_seen_trades.add(trade)
        order = self._tp_owned_order(oid, owner); ep, m = self._tp_plan()
        if ep is None or ep.id != owner['parent'] or 'standing' not in m:
            raise ValueError('STANDING_FILL_PARENT_UNKNOWN')
        step = self.cache.instrument(self.config.btc_id).size_increment.as_decimal()
        raw = event.last_qty.as_decimal() / step
        if raw != raw.to_integral_value(): raise ValueError('STANDING_FILL_LOTS_UNKNOWN')
        pre = dict(m['standing']); m['standing'] = standing_after_fill(pre, owner['level'], int(raw))
        if oid in self._tp_commands: raise ValueError('STANDING_FILL_BEFORE_REQUIRED_MODIFY_ACK')
        self._tp_debt_observe(event.ts_event,'ORDINARY_TP_NATIVE_FILL')
        self._tp_log('ACTUAL_TP_FILL', event.ts_event, parent=ep.id, order_id=oid, native_trade_id=trade, level=owner['level'], quantity=str(event.last_qty), pre_fill_lots=pre, remaining_lots=dict(m['standing']), raw_position_id=None if order.position_id is None else str(order.position_id), cache_position_id=None)

    def _tp_reconcile(self, ts):
        ep, m = self._tp_plan()
        if not m or m['p0'] is None or self._forced_close_reason or self._liquidating: return
        inst = self.cache.instrument(self.config.btc_id); step = inst.size_increment.as_decimal(); held = self._tp_held_lots()
        if not held:
            self._split_stop('BTC_FLAT'); self._md_coverage(ts, True, ep.id, 'NATIVE_FLAT'); return
        if 'standing' not in m or m.get('standing_inventory_dirty') or m.get('standing_entry') != ep.btc_entry_qty_exact:
            if self._tp_commands: raise ValueError('STANDING_INVENTORY_CHANGE_WITH_MODIFY_INFLIGHT')
            m['standing'] = target_lots(held, m['consumed']); m['standing_inventory_dirty'] = False
            m['standing_entry'] = ep.btc_entry_qty_exact
            m['generation'] += 1
            m['generations'][m['generation']] = dict(required=set(m['standing']), accepted=set(), authorized=False)
            self._tp_log('INVENTORY_ALLOCATION', ts, parent=ep.id, held_lots=held, generation=m['generation'], desired=dict(m['standing']))
        desired = {k:v for k,v in m['standing'].items() if k not in m['consumed']}
        if sum(desired.values()) != held or any(v <= 0 for v in desired.values()): raise ValueError('STANDING_INVENTORY_RIGHTS_MISMATCH')
        prices = u_prices(m['p0'],m['d3'],ep.side,inst.price_increment.as_decimal(),D(str(inst.taker_fee)),max(D(str(inst.maker_fee)),D(str(inst.taker_fee))))
        m['prices'] = prices; self._bind_native_lots()
        live = {owner['level']:(oid,owner) for oid,owner in self._tp_owners.items() if owner['parent']==ep.id and not self.cache.order(ClientOrderId(oid)).is_closed}
        if set(live)-set(desired): raise ValueError('STANDING_LIVE_CONSUMED_TARGET')
        for level,lots in desired.items():
            ep.btc_tp_target_lots[level] = ep.btc_tp_filled_lots.get(level,0)+lots
            ep.btc_tp_target_qty[level] = float(D(ep.btc_tp_target_lots[level])*step)
            if level not in live:
                ep.btc_tp_target_lots[level] = ep.btc_tp_filled_lots.get(level,0)+lots
                ep.btc_tp_target_qty[level] = float(D(ep.btc_tp_target_lots[level])*step); ep.btc_tps.add(level)
                intent = self._domain._intent(ep,'BTC_REDUCE',-ep.side,level,quantity=float(D(lots)*step),reason=f'BTC_TP{level+1}',limit_price=float(prices[level]))
                ep.resting_reductions.add(intent.id); m['intent_generation'][intent.id]=m['generation']
                self._submit_intent(intent,float(m['p0']),float(m['p0']),None,len(self._bars)-1,ts_now=ts)
                continue
            oid,owner=live[level]; order=self._tp_owned_order(oid,owner)
            if order.price.as_decimal()!=prices[level] or order.is_pending_cancel: raise ValueError('STANDING_TARGET_PRICE_OR_CANCEL_UNKNOWN')
            if order.leaves_qty.as_decimal()==D(lots)*step and oid not in self._tp_commands:
                owner['generation']=m['generation']; m['order_generation'][oid]=m['generation']
                if order.status.name in {'ACCEPTED','PARTIALLY_FILLED'} and owner['ack_generation'] is not None:
                    owner['ack_generation']=m['generation']
                continue
            if oid in self._tp_commands:
                if self._tp_commands[oid]['desired_lots']!=lots: raise ValueError('STANDING_OVERLAPPING_MODIFY_INTENT')
                continue
            book=self._tp_book()
            if marketable(-ep.side,prices[level],D(book['bid']),D(book['ask'])):
                raise ValueError('STANDING_EXECUTABLE_ALLOCATION_DRIFT')
            self._tp_seq+=1; owner['generation']=m['generation'];m['order_generation'][oid]=m['generation']
            total=order.filled_qty.as_decimal()+D(lots)*step
            command=dict(sequence=self._tp_seq,generation=m['generation'],total=total,desired_lots=lots)
            self._tp_commands[oid]=command
            self._tp_log('MODIFY_SUBMIT',ts,order_id=oid,generation=m['generation'],sequence=self._tp_seq,total=str(total),filled=str(order.filled_qty),desired_leaves=str(D(lots)*step),book=book)
            self.modify_order(order,quantity=inst.make_qty(total))
            self._tp_log('PUBLIC_MODIFY_RETURN',ts,order_id=oid,sequence=command['sequence'],ack_received=oid not in self._tp_commands)
            self._tp_transient_boundary('PUBLIC_MODIFY_RETURN',ts)
        self._tp_refresh(ts)

    def _tp_refresh(self, ts):
        ep,m=self._tp_plan()
        if not m or 'standing' not in m:return
        required={k for k,v in m['standing'].items() if v>0 and k not in m['consumed']}
        accepted=set()
        for oid,owner in self._tp_owners.items():
            if owner['parent']!=ep.id or owner['level'] not in required:continue
            order=self.cache.order(ClientOrderId(oid))
            if order is not None and order.status.name in {'ACCEPTED','PARTIALLY_FILLED'} and oid not in self._tp_commands and owner['ack_generation']==m['generation']:
                accepted.add(owner['level'])
        m['accepted']=accepted
        hist=m['generations'][m['generation']];hist['accepted']=set(accepted);hist['required']=required;hist['authorized']=accepted==required
        self._md_coverage(ts,accepted==required,ep.id,'STANDING_CURRENT_NATIVE_ACK' if accepted==required else 'STANDING_NATIVE_ACK_PENDING')

    def _tp_transient_boundary(self, label, ts):
        if not self._tp_enabled():return
        ep,m=self._tp_plan()
        if not m or 'standing' not in m or self._forced_close_reason or self._liquidating:return
        book=self._tp_book();drift=[]
        for oid,owner in self._tp_owners.items():
            if owner['parent']!=ep.id:continue
            order=self.cache.order(ClientOrderId(oid))
            if order is None:raise ValueError('STANDING_NATIVE_BOUNDARY_ORDER_UNKNOWN')
            wanted=m['standing'].get(owner['level'],0)
            if order.status.name=='FILLED':continue # genuine cache-post-fill consumed state
            actual=order.leaves_qty.as_decimal()/self.cache.instrument(self.config.btc_id).size_increment.as_decimal()
            if actual!=wanted:
                if marketable(-ep.side,order.price.as_decimal(),D(book['bid']),D(book['ask'])):
                    raise ValueError('STANDING_EXECUTABLE_BOUNDARY_MISALLOCATION')
                drift.append(dict(order_id=oid,actual_lots=str(actual),desired_lots=wanted))
        self._tp_log('NATIVE_BOUNDARY',ts,label=label,book=book,nonexecutable_drift=drift,pending_sequences={k:v['sequence'] for k,v in self._tp_commands.items()})

    def _tp_settled(self, label, ts):
        if not self._tp_enabled():return
        ep,m=self._tp_plan()
        if not m or 'standing' not in m or self._forced_close_reason or self._liquidating:return
        if self._tp_commands:raise ValueError('STANDING_UNRESOLVED_COMMAND_BEFORE_MATCH')
        self._tp_refresh(ts)
        held=self._tp_held_lots()
        if not held:return
        desired={k:v for k,v in m['standing'].items() if v>0 and k not in m['consumed']}
        actual={}
        for oid,owner in self._tp_owners.items():
            if owner['parent']!=ep.id or owner['level'] not in desired:continue
            order=self._tp_owned_order(oid,owner)
            if order.is_closed:continue
            if order.status.name not in {'ACCEPTED','PARTIALLY_FILLED'}:raise ValueError('STANDING_NATIVE_PENDING_BEFORE_MATCH')
            actual[owner['level']]=int(order.leaves_qty.as_decimal()/self.cache.instrument(self.config.btc_id).size_increment.as_decimal())
        if actual!=desired or sum(actual.values())!=held:raise ValueError('STANDING_REQUIRED_NATIVE_COVERAGE_OR_ALLOCATION')
        self._tp_log('SETTLED',ts,label=label,parent=ep.id,generation=m['generation'],held_lots=held,leaves=actual)

    def _tp_debt_clock(self, ts, safe):
        p=self._pair
        if not p or p['debt_since'] is None:return None
        if not safe:
            p['standing_debt_deferred']=True;p['standing_safe_since']=None
            return None
        if p.get('standing_debt_deferred'):
            p['standing_safe_since']=ts
        elif p.get('standing_safe_since') is None:
            p['standing_safe_since']=p['debt_since']
        p['standing_debt_deferred']=False
        # This is the executable-residual service clock only. Absolute debt_since
        # and elapsed exposure stay unchanged in every debt audit record.
        return p['standing_safe_since']

    def _tp_debt_observe(self, ts, cause):
        if not self._tp_enabled() or not self._pair:return None
        p=self._pair;held=self._pair_qty(self.config.btc_id);cap=p['caps'].bmax
        debt=max(D(0),held-cap);since=p['debt_since']
        state=dict(actual_held=str(held),absolute_cap=str(cap),residual_debt=str(debt),
            debt_since_ns=None if since is None else str(since),duration_ns=str(max(0,ts-since)) if since is not None else '0')
        previous=p.get('standing_debt_observed')
        if debt:
            if previous is None or any(previous[k]!=state[k] for k in ('actual_held','absolute_cap','residual_debt')):
                self._tp_log('ACTUAL_DEBT_RESIDUAL',ts,parent=p['parent'],cause=cause,**state)
            p['standing_debt_observed']=state
        elif previous is not None:
            self._tp_log('ACTUAL_DEBT_RESOLVED',ts,parent=p['parent'],cause=cause,
                previous_residual_debt=previous['residual_debt'],native_flat=held==0,**state)
            p['standing_debt_observed']=None
        return state

    def _tp_debt_safe(self, ts):
        ep,m=self._tp_plan()
        if not m:return False
        self._tp_settled('DEBT_DISPATCH_BARRIER',ts)
        state=self._tp_debt_observe(ts,'MATCHING_BTC_DECISION')
        book=self._tp_book()
        for oid,owner in self._tp_owners.items():
            if owner['parent']!=ep.id:continue
            order=self.cache.order(ClientOrderId(oid))
            if order is not None and not order.is_closed and marketable(-ep.side,order.price.as_decimal(),D(book['bid']),D(book['ask'])):
                self._tp_log('MARKETABLE_DEBT_DEFER',ts,parent=ep.id,order_id=oid,book=book,**state)
                return False
        self._tp_log('DEBT_DISPATCH_SAFE',ts,parent=ep.id,book=book,**state)
        self._tp_debt_witness=book
        return True
