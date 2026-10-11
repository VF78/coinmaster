"""Read-only native risk observations. OHLC envelopes are conditional bounds.

No synthetic execution events, account mutations or independent PnL engine.
"""
from __future__ import annotations
import csv
import gzip
import json
from decimal import Decimal
from pathlib import Path

D = Decimal


class DrawdownTracker:
    """Constant-memory top three nonoverlapping high-water excursions."""
    def __init__(self, seed):
        self.seed = D(seed)
        self.peak = None
        self.minimum = None
        self.current = None
        self.top = []
        self.count = 0

    def add(self, timestamp, value):
        value = D(value)
        point = {"timestamp_ns": str(timestamp), "equity": str(value)}
        self.count += 1
        if self.minimum is None or value < D(self.minimum["equity"]):
            self.minimum = point
        if self.peak is None or value >= D(self.peak["equity"]):
            if self.current:
                self.current["recovery"] = point
                self._retain(self.current)
                self.current = None
            self.peak = point
        elif self.current is None:
            self.current = {"peak": self.peak, "trough": point, "recovery": None}
        elif value < D(self.current["trough"]["equity"]):
            self.current["trough"] = point

    def _retain(self, episode):
        peak, trough = D(episode["peak"]["equity"]), D(episode["trough"]["equity"])
        episode = {**episode, "drawdown_amount": str(peak-trough),
                   "drawdown_peak_percent": str((peak-trough)/peak*100) if peak > 0 else "UNDEFINED_NONPOSITIVE_PEAK"}
        self.top = sorted(self.top + [episode], key=lambda x: D(x["drawdown_peak_percent"]) if x["drawdown_peak_percent"] != "UNDEFINED_NONPOSITIVE_PEAK" else D("Infinity"), reverse=True)[:3]

    def summary(self):
        if self.current:
            self._retain(self.current)
            self.current = None
        loss = max(D(0), self.seed-D(self.minimum["equity"])) if self.minimum else None
        return {"samples": self.count, "minimum": self.minimum,
                "maximum_loss_below_seed_amount": str(loss) if loss is not None else None,
                "maximum_loss_below_seed_percent": str(loss/self.seed*100) if loss is not None else None,
                "top3_distinct_excursions": self.top}


class ConditionalUpperToLaterLowerTracker:
    """Prior-bar favorable upper to later-bar adverse lower; no same-bar ordering."""
    def __init__(self, seed):
        self.peak = {"timestamp_ns": None, "equity": str(seed), "basis": "INITIAL_SEED"}
        self.maximum = None
        self.count = 0

    def add(self, timestamp, lower, upper):
        lower, upper = D(lower), D(upper)
        peak = D(self.peak["equity"])
        fraction = max(D("0"), (peak - lower) / peak)
        if self.maximum is None or fraction > D(self.maximum["drawdown_fraction"]):
            self.maximum = {"peak": dict(self.peak), "trough": {"timestamp_ns": str(timestamp), "equity": str(lower)},
                            "drawdown_fraction": str(fraction), "drawdown_peak_percent": str(fraction * 100)}
        # Only a subsequent completed bar may use this favorable upper.
        if upper > peak:
            self.peak = {"timestamp_ns": str(timestamp), "equity": str(upper), "basis": "PRIOR_BAR_FAVORABLE_UPPER"}
        self.count += 1

    def summary(self):
        return {"samples": self.count, "maximum": self.maximum,
                "basis": "PRIOR_COMPLETED_BAR_FAVORABLE_UPPER_TO_STRICTLY_LATER_BAR_ADVERSE_LOWER",
                "same_bar_extrema_order_assumed": False, "actual_intrabar_path_proven": False}


class NativeMinuteRiskRecorder:
    def __init__(self, path: Path, seed, instruments, leverage, end_exclusive_ns):
        from coinmaster.research.native_fixture import TierMarginPolicy
        self.path = path
        self.end_exclusive_ns = end_exclusive_ns
        self.post_boundary_settlement = []
        self.phase_counts = {phase: 0 for phase in ("pre_quote_paired_close","post_btc_quote_paired_close","post_quote_paired_close")}
        self.file = gzip.open(path, "wt", newline="", compresslevel=1)
        self.writer = csv.writer(self.file)
        self.writer.writerow(["bar_open_ms", "close_available_ns", "phase", "cash", "free_cash", "native_initial_margin", "native_maintenance_margin", "paired_close_equity", "conditional_adverse_equity", "conditional_favorable_equity", "conditional_high_mark_mm_upper", "conditional_margin_breach", "native_positions_and_mark_ohlc_json"])
        self.instruments = instruments
        self.margin_policy = TierMarginPolicy((), leverage, 120_000_000_000)
        # High notional is a maintenance upper bound only for monotone tiers.
        # Validate the actual captured profile rather than assume that property.
        for tiers in self.margin_policy._profile.tiers.values():
            if any(t.mm < 0 for t in tiers) or any(
                a.cap*b.mm-b.deduction < a.cap*a.mm-a.deduction
                for a,b in zip(tiers,tiers[1:])
            ):
                raise ValueError("RISK_OBSERVER_NONMONOTONE_MAINTENANCE_PROFILE")
        self.bundles = {}
        self.curves = {phase: DrawdownTracker(seed) for phase in ("pre_quote_paired_close", "post_btc_quote_paired_close", "post_quote_paired_close", "all_native_close_samples", "conditional_ohlc_adverse")}
        self.upper_to_later_lower = ConditionalUpperToLaterLowerTracker(seed)
        self.rows = 0
        self.expected_minutes = 0
        self.potential = 0
        self.potential_first = []
        self.last_post_cash = D(seed)

    def set_week(self, week):
        self.expected_minutes += len(week)
        self.bundles = {(minute.open_time_ms+60000)*1000000: minute for minute in week}
        if self.rows == 0:
            self.upper_to_later_lower.peak["timestamp_ns"] = str(week[0].open_time_ms*1000000)
            for curve in self.curves.values():
                curve.add(week[0].open_time_ms*1000000,curve.seed)

    def _snapshot(self, strategy, timestamp):
        from coinmaster.strategy.wave_overlay import _native_account_money
        bundle = self.bundles[timestamp]
        account = strategy.cache.account_for_venue(strategy.config.btc_id.venue)
        cash = _native_account_money(account)
        free = _native_account_money(account, free=True)
        close_equity = cash
        adverse = min(cash, self.last_post_cash)
        favorable = max(cash, self.last_post_cash)
        mm_upper = D(0)
        details = []
        by_id = {strategy.config.btc_id: bundle.btc_mark, strategy.config.sol_id: bundle.sol_mark}
        from coinmaster.research.native_fixture import MarkPriceUpdate
        for position in strategy.cache.positions_open():
            if position.instrument_id not in by_id:
                raise ValueError("RISK_OBSERVER_FOREIGN_POSITION")
            instrument = strategy.cache.instrument(position.instrument_id)
            bar = by_id[position.instrument_id]
            o,h,l,c = (D(bar[key]) for key in ("open", "high", "low", "close"))
            if not all(x.is_finite() and x>0 for x in (o,h,l,c)) or not l<=min(o,c)<=max(o,c)<=h:
                raise ValueError("RISK_OBSERVER_INVALID_OHLC")
            # Native position method is the sole PnL implementation. Take both
            # endpoints, avoiding assumptions about side strings or rounding.
            low_pnl = position.unrealized_pnl(instrument.make_price(l)).as_decimal()
            high_pnl = position.unrealized_pnl(instrument.make_price(h)).as_decimal()
            close_equity += position.unrealized_pnl(instrument.make_price(c)).as_decimal()
            adverse += min(low_pnl, high_pnl)
            favorable += max(low_pnl, high_pnl)
            self.margin_policy.update_mark(MarkPriceUpdate(position.instrument_id, h, timestamp))
            mm_upper += self.margin_policy.margin_for(position.instrument_id, position.quantity.as_decimal(), timestamp)[1]
            details.append({"instrument_id": str(position.instrument_id), "side": str(position.side), "quantity": str(position.quantity), "avg_px_open": str(position.avg_px_open), "mark_ohlc": bar, "low_native_pnl": str(low_pnl), "high_native_pnl": str(high_pnl)})
        native_initial = sum((v.as_decimal() for v in account.margins_init().values()), D(0))
        native_maintenance = sum((v.as_decimal() for v in account.margins_maint().values()), D(0))
        return bundle, cash, free, native_initial, native_maintenance, close_equity, adverse, favorable, mm_upper, details

    def capture(self, strategy, timestamp, phase):
        if timestamp not in self.bundles:
            return
        snapshot = self._snapshot(strategy, timestamp)
        bundle,cash,free,initial,maintenance,equity,adverse,favorable,upper,details = snapshot
        self.phase_counts[phase] += 1
        post_boundary = timestamp >= self.end_exclusive_ns and phase != "pre_quote_paired_close"
        row_phase = phase
        if post_boundary:
            row_phase = "post_boundary_" + phase
            self.post_boundary_settlement.append({"timestamp_ns": str(timestamp), "phase": phase, "cash": str(cash), "paired_close_equity": str(equity), "native_positions": details})
        else:
            self.curves[phase].add(timestamp,equity)
            self.curves["all_native_close_samples"].add(timestamp,equity)
        if phase == "pre_quote_paired_close":
            self.curves["conditional_ohlc_adverse"].add(timestamp, adverse)
            self.upper_to_later_lower.add(timestamp, adverse, favorable)
            breach = bool(details) and adverse<=upper
            self.potential += int(breach)
            if breach and len(self.potential_first)<10:
                self.potential_first.append({"bar_open_ms":bundle.open_time_ms,"lower_equity":str(adverse),"upper_maintenance":str(upper)})
        else:
            # A post-close entry did not exist during this bar. Its adverse
            # extrema are deliberately NOT sampled or exported as an envelope.
            adverse=favorable=upper="NOT_APPLICABLE_POST_CLOSE_EXPOSURE"
            breach="NOT_APPLICABLE"
            if phase == "post_quote_paired_close":
                self.last_post_cash=cash
        self.writer.writerow([bundle.open_time_ms,timestamp,row_phase,cash,free,initial,maintenance,equity,adverse,favorable,upper,breach,json.dumps(details,separators=(",",":"))])
        self.rows += 1

    def close(self):
        self.file.close()
        if self.rows != self.expected_minutes*3 or any(
            count != self.expected_minutes for count in self.phase_counts.values()
        ):
            raise ValueError("RISK_OBSERVER_INCOMPLETE_NATIVE_TRACE")
        summary={"trace_path":str(self.path), "rows":self.rows,
                 "end_exclusive_ns": str(self.end_exclusive_ns),
                 "post_boundary_settlement_excluded_from_interval_curves": self.post_boundary_settlement,
                 "curves":{key:curve.summary() for key,curve in self.curves.items()},
                 "conditional_upper_to_later_lower_bound": self.upper_to_later_lower.summary(),
                 "potential_conditional_intrabar_margin_breach_count":self.potential,
                 "first_potential_conditional_breaches":self.potential_first,
                 "basis":"NATIVE_ACCOUNT_CASH_PLUS_NATIVE_POSITION_UNREALIZED_PNL",
                 "limitations":["Final prequote at end_exclusive is the completed-last-bar left-limit observation; post-boundary BTC/SOL quotes and terminal settlement are exported separately and excluded from interval close/DD/minimum/TOP3.","Maintenance breach uses the existing diagnostic native equity <= tier maintenance model only; no extra liquidation-fee reserve or actual venue liquidation safety claim.","Close equity sampled before paired-close execution quotes and after each BTC and SOL quote callback; native callback cache finalization must be checked against replay fills/account parity.","OHLC interval is [open_time_ms,open_time_ms+60000); exposure is native positions immediately before close quotes. New close-quote entries never receive this bar's extrema.","Conditional envelope holds pre-quote exposure fixed and cash between previous postquote cash and current prequote cash. Funding at boundary is included in that cash range, never set to zero.","Captured maintenance tiers validated monotonic at every boundary, so each high-mark requirement upper-bounds maintenance for fixed quantity.","Asset extrema are not synchronized; summed adverse extrema give a conservative conditional bound, not actual observed portfolio equity or liquidation.","Postquote positions and boundary fills are separate samples. Historical tick path, intrabar execution, venue margin/fee applicability remain unvalidated.","Adverse-bound excursion percentages describe the conditional lower-envelope series, not exact historical maximum drawdown."]}
        output=self.path.with_name("minute-risk-summary.json")
        output.write_text(json.dumps(summary,indent=2)+"\n")
        return {"summary_path":str(output),**summary}


def observed_strategy_type(base, recorder):
    """Preserve strategy class name/order identity; attach read-only callbacks."""
    def on_data(self, data):
        base.on_data(self, data)
        mark=getattr(data,"data",data)
        timestamp=getattr(mark,"ts_event",None)
        if timestamp in recorder.bundles and getattr(mark,"instrument_id",None)==self.config.sol_id:
            # Signals have no SOL execution instrument id in this feed; only
            # paired explicit marks trigger this sampling point.
            from coinmaster.venues.marks import VenueMark
            if isinstance(mark,VenueMark) and all(self._latest_marks.get(i) is not None and self._latest_marks[i].ts_event==timestamp for i in (self.config.btc_id,self.config.sol_id)):
                recorder.capture(self,timestamp,"pre_quote_paired_close")
                # Opt-in protection may cancel/fill against the previous native
                # book. Record held completed-bar exposure before any action.
                if self.config.research_portfolio_protect_45:
                    self._research_check_portfolio_protection(timestamp, after_observation=True)
                if self.config.research_btc_episode_loss_20:
                    self._research_check_btc_episode_loss(timestamp, after_observation=True)
    def on_quote_tick(self,tick):
        base.on_quote_tick(self,tick)
        if tick.instrument_id==self.config.sol_id:
            recorder.capture(self,tick.ts_event,"post_quote_paired_close")
        elif tick.instrument_id==self.config.btc_id:
            recorder.capture(self,tick.ts_event,"post_btc_quote_paired_close")
    return type(base.__name__,(base,),{"on_data":on_data,"on_quote_tick":on_quote_tick,"_research_protection_defer_to_recorder":True})
