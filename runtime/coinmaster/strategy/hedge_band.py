"""Default-off research policies; native executor remains the only order owner."""
from decimal import Decimal as D
from math import isfinite

H4_NS = 14_400_000_000_000


class HedgeBandResearch:
    def _hedge_band_init(self):
        c = self.config
        if c.research_sol_btc_open_only and c.research_h4_ema is not None:
            raise ValueError("C0_AND_H4_ARE_EXCLUSIVE")
        if c.research_h4_ema not in (None, 13, 34, 89) or c.research_h4_gamma not in (D('.5'), D('1')):
            raise ValueError("H4_FIXED_GRID_REQUIRED")
        if c.research_regime_reentry_band not in (None, D('0'), D('.5')):
            raise ValueError("B_FIXED_HALF_ATR_REQUIRED")
        enabled = c.research_sol_btc_open_only or c.research_h4_ema is not None or c.research_regime_reentry_band is not None
        if enabled and (c.research_h1_b1 or c.research_v3_risk or c.research_sol_cover is not None or c.research_conditional_sol or c.research_sol_risk_first or c.research_immediate_sol or c.research_alpha_cushion or c.research_chop_pair):
            raise ValueError("HEDGE_BAND_REQUIRES_EXCLUSIVE_S0_PIPELINE")
        self.hedge_band_audit = []
        self._hb_wait_regime = False
        self._hb_daily_ohlc = {int(ns): (float(h), float(l)) for ns, h, l in c.research_band_daily_seed}
        self._hb_ema = None
        self._hb_count = 0
        self._hb_bar_ns = None
        self._hb_side = None
        self._hb_cycle = None
        self._hb_eligible = False
        self._hb_quote_seq = 0
        self._hb_last_submit_seq = -1
        self._hb_cancel_ids = set()
        self._hb_exit_pending = False
        for ns, close in c.research_h4_seed:
            self._hedge_h4_close(int(ns), float(close))
        if c.research_h4_ema is not None and self._hb_count < 730:
            raise ValueError("H4_REQUIRES_730_CLOSED_4H_WARMUP_BARS")

    def _hb_log(self, event, ns, **fields):
        self.hedge_band_audit.append(dict(event=event, timestamp_ns=int(ns), **fields))

    def _hb_position(self, instrument):
        return next((p for p in self.cache.positions_open() if p.instrument_id == instrument), None)

    def _hedge_h4_close(self, ns, close):
        if self._hb_bar_ns is not None and ns <= self._hb_bar_ns:
            return
        period = self.config.research_h4_ema
        if period is None:
            return
        if ns % H4_NS or not isfinite(close) or close <= 0:
            raise ValueError("INVALID_CLOSED_UTC_H4_BAR")
        if self._hb_bar_ns is not None and ns != self._hb_bar_ns + H4_NS:
            raise ValueError("H4_CAUSAL_BAR_GAP")
        alpha = 2 / (period + 1)
        self._hb_ema = close if self._hb_ema is None else alpha * close + (1-alpha) * self._hb_ema
        self._hb_count += 1
        self._hb_side = 1 if close > self._hb_ema else -1
        self._hb_bar_ns = ns

    def _hedge_h4_bar(self, bar):
        # Called by its own explicitly typed branch, never legacy HOUR/1h.
        self._hedge_h4_close(bar.ts_event, float(bar.close))
        self._hb_log('H4_SIGNAL', bar.ts_event, side=self._hb_side, ema=self._hb_ema,
                     receipt_ns=self.clock.timestamp_ns(), quote_sequence=self._hb_quote_seq)
        self._hedge_refresh(self.clock.timestamp_ns())

    def _hedge_band_allowed(self):
        if self.config.research_regime_reentry_band is None or not self._hb_wait_regime or self._domain.episode is not None:
            return True
        # Rebuild only the original accepted seed/closed daily chain. EMA seed is
        # exactly FeatureState's first close, and TR needs a previous close.
        ema = previous = atr = None
        trs = []
        for row in self._bars:
            close = row.btc_close
            ema = close if ema is None else 2/(self._candidate.ema_period+1)*close + (1-2/(self._candidate.ema_period+1))*ema
            ns = int(row.close_time.timestamp()*1_000_000_000)
            hl = self._hb_daily_ohlc.get(ns)
            if previous is not None:
                if hl is None:
                    self._daily_decision_reason = 'B_OHLC_UNAVAILABLE'
                    return False
                high, low = hl
                tr = max(high-low, abs(high-previous), abs(low-previous))
                if not isfinite(tr) or low <= 0 or high < max(low, close) or low > close:
                    self._daily_decision_reason = 'B_OHLC_INVALID'
                    return False
                if atr is None:
                    trs.append(tr)
                    if len(trs) == 14:
                        atr = sum(trs)/14
                else:
                    atr = (13*atr+tr)/14
            previous = close
        band = self.config.research_regime_reentry_band
        if band == 0:
            return True  # Permission-only short oracle; no ATR gate at zero.
        if atr is None or not isfinite(atr) or atr <= 0:
            self._daily_decision_reason = 'B_ATR_UNAVAILABLE'
            return False
        side = 1 if close > ema else -1
        allowed = side*(close-ema) >= float(band)*atr
        self._daily_decision_reason = 'B_ENTRY_ALLOWED' if allowed else 'WAIT_REGIME_REENTRY'
        self._hb_log(self._daily_decision_reason, ns, side=side, close=close, ema=ema, atr14=atr)
        return allowed

    def _hedge_btc_flat(self, intent, ns):
        if not (self.config.research_sol_btc_open_only or self.config.research_h4_ema is not None):
            return
        ep = self._domain.episode
        if ep is None or ep.btc_open_qty > 0:
            return
        ep.sol_rights.clear()
        ep.sol_right_fraction.clear()
        ep.sol_right_decision_index.clear()
        if self._hb_cycle is not None:
            self._hb_log('H4_BTC_FLAT_CANCEL_BUILD', ns, activation_ns=self._hb_cycle.get('activation_ns'), target=str(self._hb_cycle['target']))
        self._hb_cycle = None
        self._hb_eligible = False
        # True terminal cause, never fabricated REGIME/same-session restart.
        ep.close_reason = ep.close_reason or intent.reason or 'BTC_TP_FLAT'
        close = self._domain._intent(ep, 'CLOSE_ALL', -ep.side, None, reason=ep.close_reason)
        self._group_close_reconciliation_pending = True
        self._begin_forced_close(ep.close_reason, close)
        self._hb_log('BTC_FLAT_INVALIDATE_RIGHTS', ns, reason=ep.close_reason)

    def _hedge_refresh(self, ns):
        if self.config.research_h4_ema is None:
            return
        ep = self._domain.episode
        btc = self._hb_position(self.config.btc_id)
        side = (1 if btc.is_long else -1) if btc is not None else None
        eligible = bool(ep is not None and btc is not None and self._hb_side == -side and self._forced_close_reason is None and not self._liquidating)
        cycle = self._hb_cycle
        key = (ep.id, side) if ep is not None else None
        new = eligible and (not self._hb_eligible or cycle is None or cycle['key'] != key)
        if not eligible:
            if cycle is not None:
                self._hb_exit_pending = True
                cycle['exit'] = True
                cycle['target'] = D(0)
            self._hb_eligible = False
            return
        if new:
            beta = self._current_signals[-1].beta if self._current_signals else None
            bm, sm = self._latest_marks.get(self.config.btc_id), self._latest_marks.get(self.config.sol_id)
            self._hb_eligible = True
            if beta is None or not isfinite(beta) or beta <= 0 or bm is None or sm is None or bm.price <= 0 or sm.price <= 0:
                self._hb_cycle = dict(key=key, side=-side, invalid=True, target=D(0), exit=True, deadline_ns=ns+H4_NS)
                self._hb_log('H4_ACTIVATION_INVALID', ns, beta=beta)
                return
            ratio = self.config.research_h4_gamma * D(str(bm.price)) / (D(str(beta))*D(str(sm.price)))
            cycle = self._hb_cycle = dict(key=key, side=-side, activation_ns=ns, deadline_ns=ns+H4_NS,
                beta=beta, pb0=str(bm.price), ps0=str(sm.price), ratio=ratio, target=D(0), initial_target=None,
                ready_sequence=self._hb_quote_seq+1, exit=False, invalid=False, first_fill_ns=None, half_fill_ns=None)
            self._hb_log('H4_ACTIVATION', ns, episode_id=ep.id, beta0=beta, r0=str(ratio), deadline_ns=ns+H4_NS)
        if cycle is None or cycle.get('invalid'):
            return
        step = self.cache.instrument(self.config.sol_id).size_increment.as_decimal()
        target = (cycle['ratio']*btc.quantity.as_decimal()//step)*step
        if cycle['initial_target'] is None:
            cycle['initial_target'] = target
        if target != cycle['target']:
            self._hb_log('H4_TARGET', ns, previous=str(cycle['target']), target=str(target), actual_btc=str(btc.quantity))
        if target < cycle['target']:
            self._hedge_cancel_openers()
        cycle['target'] = target

    def _hedge_cancel_openers(self):
        self._discard_queued_intents(lambda i: i.action == 'SOL_ADD')
        for order in list(self.cache.orders_open()):
            if order.instrument_id == self.config.sol_id and not order.is_reduce_only:
                oid = str(order.client_order_id)
                if oid not in self._hb_cancel_ids:
                    self._hb_cancel_ids.add(oid)
                    self.cancel_order(order)

    def _hedge_quote(self, tick):
        if self.config.research_h4_ema is None or tick.instrument_id != self.config.sol_id:
            return
        self._hb_quote_seq += 1
        self._hedge_refresh(tick.ts_event)
        cycle = self._hb_cycle
        ep = self._domain.episode
        if ep is None or cycle is None:
            return
        held = self._hb_position(self.config.sol_id)
        qty = held.quantity.as_decimal() if held is not None else D(0)
        target = cycle['target'] if not cycle['exit'] and not self._hb_exit_pending else D(0)
        expired = tick.ts_event >= cycle['deadline_ns']
        if cycle['exit'] or self._hb_exit_pending or expired or qty >= target:
            self._hedge_cancel_openers()
        # Every child remains owned until a native terminal receipt. The
        # sequence is consumed before submit (including synchronous callbacks).
        busy = any(i.action.startswith('SOL') for i in self._pending_by_order.values()) or any(o.instrument_id == self.config.sol_id for o in self.cache.orders_open()+self.cache.orders_inflight())
        if busy or self._hb_last_submit_seq == self._hb_quote_seq:
            return
        if self._hb_exit_pending and qty == 0:
            self._hb_exit_pending = False
            return  # Complete old mandatory exit before considering pending activation.
        wrong = held is not None and (1 if held.is_long else -1) != cycle['side']
        reduction = qty if wrong or cycle['exit'] or self._hb_exit_pending else max(D(0), qty-target)
        if reduction > 0:
            intent = self._domain._intent(ep, 'SOL_EXIT', -1 if held.is_long else 1, None,
                quantity=float(reduction), reason='H4_TARGET_REDUCTION')
        elif qty < target and not self._hb_exit_pending and not expired and not cycle['exit'] and self._hb_quote_seq >= cycle['ready_sequence'] and self._forced_close_reason is None and not self._liquidating and not self._split_unfinished() and not any(i.action.startswith('BTC') for i,_,_ in self._queued_intents):
            intent = self._domain._intent(ep, 'SOL_ADD', cycle['side'], None,
                quantity=float(target-qty), reason='H4_INCREASE')
        else:
            return
        self._hb_last_submit_seq = self._hb_quote_seq
        self._hb_log('H4_NATIVE_CHILD', tick.ts_event, action=intent.action, quantity=intent.quantity, activation_ns=cycle.get('activation_ns'), deadline_ns=cycle['deadline_ns'], target=str(target), initial_target=str(cycle.get('initial_target')), held=str(qty))
        self._submit_intent(intent, float(tick.bid_price), float(tick.ask_price), None, len(self._bars)-1, ts_now=tick.ts_event)

    def _hedge_sol_fill(self, intent, quantity, ns):
        ep = self._domain.episode
        if ep is None:
            raise ValueError('H4_FILL_WITHOUT_OWNED_EPISODE')
        ep.sol_qty = max(0.0, ep.sol_qty + quantity if intent.action == 'SOL_ADD' else ep.sol_qty-quantity)
        cycle = self._hb_cycle
        if cycle and not cycle.get('invalid') and intent.action == 'SOL_ADD':
            if cycle['first_fill_ns'] is None:
                cycle['first_fill_ns'] = ns
                self._hb_log('H4_FIRST_FILL', ns, delay_ns=ns-cycle['activation_ns'])
            if cycle['half_fill_ns'] is None and D(str(ep.sol_qty)) >= cycle['initial_target']/2:
                cycle['half_fill_ns'] = ns
                self._hb_log('H4_HALF_INITIAL_TARGET_FILL', ns, delay_ns=ns-cycle['activation_ns'], initial_target=str(cycle['initial_target']))

    def _hedge_terminal(self, intent, ns, outcome):
        if self.config.research_h4_ema is None or intent is None or not intent.action.startswith('SOL'):
            return
        c = self._hb_cycle
        self._hb_log('H4_NATIVE_CHILD_TERMINAL', ns, action=intent.action, outcome=outcome,
            activation_ns=c.get('activation_ns') if c else None,
            time_from_activation_ns=ns-c['activation_ns'] if c and 'activation_ns' in c else None,
            target=str(c['target']) if c else '0',
            actual_sol=str(self._hb_position(self.config.sol_id).quantity) if self._hb_position(self.config.sol_id) else '0')
