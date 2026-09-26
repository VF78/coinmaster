"""Versioned, fail-closed WaveOverlay state for isolated live recovery proofs.

This subclass keeps the sealed strategy's decision and execution methods. It
does not enable entries on load: native venue reconciliation must first prove
the episode, orders, fills, account, and fresh public feeds coherent.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import time
from dataclasses import fields, is_dataclass
from datetime import datetime
from decimal import Decimal

from nautilus_trader.model.data import Bar, BarType
from nautilus_trader.model.enums import OrderSide
from nautilus_trader.model.currencies import USDC
from nautilus_trader.model.identifiers import InstrumentId

from coinmaster.domain.wave_overlay import DailyBar, Episode, Intent
from coinmaster.ops.hl_live_money import LivePerpsMoneyView, prospective_cross_margin_ok
from coinmaster.ops.stage_g_config import canonical_candidate_json
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy
from coinmaster.venues.marks import VenueMark
from coinmaster.venues.signals import DailySignalBar


_SCHEMA = "coinmaster-wave-overlay-live-recovery-v1"
_KEY = "wave_overlay_live_recovery_v1"
_DATACLASSES = {item.__name__: item for item in (DailyBar, Episode, Intent)}
_FIELDS = (
    "_bars", "_pending_by_order", "_sigma_by_order", "_decision_index_by_order",
    "_last_sol_close", "_day", "_marks_by_session", "_current_btc", "_current_sol",
    "_current_btc_mark", "_current_sol_mark", "_latest_marks",
    "_queued_intents", "_queued_intent_ready_ns", "_mandatory_sol_exit",
    "_queued_close_submitted", "_group_close_reconciliation_pending",
    "_liquidating", "_liquidation_waiting", "_liquidation_orders",
    "_liquidation_submitted", "liquidation_audit", "pre_submit_gate_blocks",
    "marked_equity_checkpoints", "_terminal_order_ids", "_order_audit",
    "fill_audit", "_forced_close_reason", "_forced_close_intent",
    "_forced_close_submitted", "_forced_close_orders", "terminal_lifecycle",
)


def _encode(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("NONFINITE_RECOVERY_STATE")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("NONFINITE_RECOVERY_STATE")
        return {"t": "decimal", "v": str(value)}
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("NAIVE_RECOVERY_TIME")
        return {"t": "datetime", "v": value.isoformat()}
    if isinstance(value, InstrumentId):
        return {"t": "instrument", "v": str(value)}
    if isinstance(value, BarType):
        return {"t": "bar_type", "v": str(value)}
    if isinstance(value, Bar):
        return {"t": "bar", "v": _encode(Bar.to_dict(value))}
    if isinstance(value, DailySignalBar):
        return {"t": "daily_signal", "v": [
            _encode(value.instrument_id), _encode(value.open), _encode(value.high),
            _encode(value.low), _encode(value.close), value.ts_event, value.ts_init,
        ]}
    if isinstance(value, VenueMark):
        return {"t": "venue_mark", "v": [
            _encode(value.instrument_id), _encode(value.price), value.ts_event, value.ts_init,
        ]}
    if is_dataclass(value) and type(value).__name__ in _DATACLASSES:
        return {"t": type(value).__name__, "v": {f.name: _encode(getattr(value, f.name)) for f in fields(value)}}
    if isinstance(value, set):
        encoded = [_encode(item) for item in value]
        return {"t": "set", "v": sorted(encoded, key=lambda item: json.dumps(item, sort_keys=True))}
    if isinstance(value, tuple):
        return {"t": "tuple", "v": [_encode(item) for item in value]}
    if isinstance(value, list):
        return [_encode(item) for item in value]
    if isinstance(value, dict):
        pairs = [[_encode(k), _encode(v)] for k, v in value.items()]
        return {"t": "dict", "v": sorted(pairs, key=lambda pair: json.dumps(pair[0], sort_keys=True))}
    raise TypeError(f"UNSUPPORTED_RECOVERY_STATE_TYPE:{type(value).__name__}")


def _decode(value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict) or set(value) != {"t", "v"}:
        raise ValueError("INVALID_RECOVERY_ENCODING")
    kind, body = value["t"], value["v"]
    if kind == "decimal":
        result = Decimal(body)
        if not result.is_finite():
            raise ValueError("NONFINITE_RECOVERY_STATE")
        return result
    if kind == "datetime":
        result = datetime.fromisoformat(body)
        if result.tzinfo is None:
            raise ValueError("NAIVE_RECOVERY_TIME")
        return result
    if kind == "instrument":
        return InstrumentId.from_str(body)
    if kind == "bar_type":
        return BarType.from_str(body)
    if kind == "bar":
        return Bar.from_dict(_decode(body))
    if kind == "daily_signal":
        return DailySignalBar(*[_decode(item) for item in body])
    if kind == "venue_mark":
        return VenueMark(*[_decode(item) for item in body])
    if kind in _DATACLASSES:
        cls = _DATACLASSES[kind]
        expected = {f.name for f in fields(cls)}
        # The target-size map was added after earlier fail-closed checkpoints.
        # It is derivable from immutable confirmed entry size and candidate
        # fractions on the first later fill, so retain compatibility without
        # weakening any native reconciliation requirement.
        if kind == "Episode" and set(body) == expected - {"btc_tp_target_qty"}:
            body = {**body, "btc_tp_target_qty": _encode({})}
        if set(body) != expected:
            raise ValueError(f"RECOVERY_FIELDS_MISMATCH:{kind}")
        return cls(**{name: _decode(item) for name, item in body.items()})
    if kind == "set":
        return {_decode(item) for item in body}
    if kind == "tuple":
        return tuple(_decode(item) for item in body)
    if kind == "dict":
        return {_decode(k): _decode(v) for k, v in body}
    raise ValueError(f"UNSUPPORTED_RECOVERY_ENCODING:{kind}")


class RecoverableWaveOverlayStrategy(WaveOverlayStrategy):
    """Versioned state hooks; native reconciliation remains an external gate."""

    def __init__(self, config):
        super().__init__(config)
        self.recovery_confirmed = False
        self._recovery_runtime = None
        # Process-local evidence: a restored checkpoint never grants feed freshness.
        self._quote_ns = {}
        self._post_drain_verifier = None
        self._post_drain_task = None
        self._recovery_health = None
        self._live_money_provider = None
        self._live_refresh = None

    def attach_live_money_view(self, provider) -> None:
        if not callable(provider) or self._live_money_provider is not None:
            raise RuntimeError("LIVE_MONEY_PROVIDER_INVALID")
        self._live_money_provider = provider

    def attach_live_refresh(self, refresh) -> None:
        if not callable(refresh) or self._live_refresh is not None:
            raise RuntimeError("LIVE_REFRESH_BINDING_INVALID")
        self._live_refresh = refresh

    def _request_live_refresh(self) -> None:
        if self._live_refresh is not None:
            self._live_refresh()

    def _validated_live_money(self) -> LivePerpsMoneyView:
        if not self.recovery_confirmed or self._live_money_provider is None:
            raise ValueError("LIVE_MONEY_UNCONFIRMED")
        view = self._live_money_provider()
        if not isinstance(view, LivePerpsMoneyView):
            raise ValueError("LIVE_MONEY_VIEW_UNKNOWN")
        view.require_fresh(time.time_ns() // 1_000_000, 10_000)
        return view

    def _halt_on_deferred_daily_decision(self) -> bool:
        return True

    def _advance_current_day(self) -> None:
        # A native open position cannot bypass a stale venue money view.
        try:
            self._validated_live_money()
        except ValueError:
            if self._current_btc is not None:
                self._deferred_entry_session = self._current_btc.ts_event
                self._daily_decision_reason = "DEFERRED_LIVE_MONEY"
            self._request_live_refresh()
            return
        super()._advance_current_day()

    def _retry_deferred_daily_decision(self) -> None:
        if self._current_btc is None or self._deferred_entry_session != self._current_btc.ts_event:
            return
        if not self._entries_enabled():
            return
        self._deferred_entry_session = None
        self._advance_current_day()

    def _active_marked(self, btc_mark: VenueMark, sol_mark: VenueMark) -> float:
        # Venue accountValue is already marked; do not add native UPNL twice.
        return float(self._validated_live_money().equity)

    def _free_margin_for_increase(self, account) -> Decimal:
        return self._validated_live_money().free_collateral

    def _tier_allows_increase(self, instrument_id: InstrumentId, side: OrderSide, quantity: Decimal, ts_now: int) -> bool:
        try:
            self._require_recovery_confirmed()
            view = self._validated_live_money()
            if self._recovery_runtime is None or view.native_revision != self._recovery_runtime.native_revision():
                return False
            account = self.cache.account_for_venue(self.config.btc_id.venue)
            if account is None or account.balance_total(USDC) is None or account.balance_free(USDC) is None:
                return False
            projected_total = view.raw_usd if view.raw_usd < 0 else max(view.raw_usd, view.free_collateral)
            if (
                account.balance_total(USDC).as_decimal() != projected_total
                or account.balance_free(USDC).as_decimal() != view.free_collateral
            ):
                return False
            positions = {}
            for position in self.cache.positions_open():
                if (
                    str(position.strategy_id) != str(self.id)
                    or position.instrument_id not in (self.config.btc_id, self.config.sol_id)
                ):
                    return False
                coin = "BTC" if position.instrument_id == self.config.btc_id else "SOL"
                if coin in positions:
                    return False
                positions[coin] = position.quantity.as_decimal() * (1 if position.is_long else -1)
            if tuple(sorted(positions.items())) != view.position_sizes:
                return False
            journal = {row["client_order_id"]: row for row in self._recovery_runtime.all_submissions()}
            pending = []
            for order in self.cache.orders(venue=self.config.btc_id.venue):
                if str(order.strategy_id) != str(self.id) or str(order.client_order_id) not in journal:
                    return False
                if order.is_closed or order.is_reduce_only:
                    continue
                if order.venue_order_id is None:
                    return False  # A forwarded order without venue proof is an unknown ACK.
                leaves = order.quantity.as_decimal() - order.filled_qty.as_decimal()
                if leaves <= 0:
                    return False
                order_coin = "BTC" if order.instrument_id == self.config.btc_id else "SOL" if order.instrument_id == self.config.sol_id else ""
                pending.append((order_coin, order.side.name, leaves))
            coin = "BTC" if instrument_id == self.config.btc_id else "SOL" if instrument_id == self.config.sol_id else ""
            return prospective_cross_margin_ok(
                view, positions=positions, pending_openings=pending,
                coin=coin, side=side.name, quantity=quantity,
                max_gross_multiple=self.config.max_gross_to_active,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False

    def _check_mark_first_liquidation(self, ts_now: int) -> None:
        # The live venue owns liquidation. The Sandbox policy is not a live order source.
        return

    def attach_recovery_health(self, healthy) -> None:
        if not callable(healthy) or self._recovery_health is not None:
            raise RuntimeError("RECOVERY_HEALTH_BINDING_INVALID")
        self._recovery_health = healthy

    def attach_post_drain_verifier(self, verifier) -> None:
        """Install one async verifier; it cannot grant readiness by return value."""
        if self._post_drain_verifier is not None or self._post_drain_task is not None:
            raise RuntimeError("RECOVERY_VERIFIER_ALREADY_ATTACHED")
        if not callable(verifier):
            raise TypeError("RECOVERY_VERIFIER_REQUIRED")
        self._post_drain_verifier = verifier

    def on_start(self) -> None:
        self.recovery_confirmed = False
        super().on_start()
        if self._post_drain_verifier is not None:
            # Kernel starts the Trader only after native execution reconciliation.
            # The verifier owns fresh Info/cache/domain/account parity and may
            # confirm recovery explicitly; a successful return proves nothing.
            self._post_drain_task = asyncio.get_running_loop().create_task(
                self._run_post_drain_verifier()
            )

    async def _run_post_drain_verifier(self) -> None:
        try:
            await self._post_drain_verifier()
        except BaseException:
            self.recovery_confirmed = False
            raise

    def on_stop(self) -> None:
        self.recovery_confirmed = False
        if self._post_drain_task is not None and not self._post_drain_task.done():
            self._post_drain_task.cancel()
        super().on_stop()

    def _require_recovery_confirmed(self) -> None:
        if not self.recovery_confirmed or (self._recovery_health is not None and not self._recovery_health()):
            self.recovery_confirmed = False
            raise RuntimeError("RECOVERY_NOT_CONFIRMED")

    def submit_order(self, *args, **kwargs):
        self._require_recovery_confirmed()
        return super().submit_order(*args, **kwargs)

    def submit_order_list(self, *args, **kwargs):
        self._require_recovery_confirmed()
        return super().submit_order_list(*args, **kwargs)

    def modify_order(self, *args, **kwargs):
        self._require_recovery_confirmed()
        return super().modify_order(*args, **kwargs)

    def cancel_order(self, *args, **kwargs):
        self._require_recovery_confirmed()
        return super().cancel_order(*args, **kwargs)

    def cancel_orders(self, *args, **kwargs):
        self._require_recovery_confirmed()
        return super().cancel_orders(*args, **kwargs)

    def cancel_all_orders(self, *args, **kwargs):
        self._require_recovery_confirmed()
        return super().cancel_all_orders(*args, **kwargs)

    def close_position(self, *args, **kwargs):
        self._require_recovery_confirmed()
        return super().close_position(*args, **kwargs)

    def close_all_positions(self, *args, **kwargs):
        self._require_recovery_confirmed()
        return super().close_all_positions(*args, **kwargs)

    def _feeds_fresh(self, now_ns: int) -> bool:
        age = self.config.max_mark_age_ns
        if not self.recovery_confirmed or age <= 0:
            return False
        for instrument_id in (self.config.btc_id, self.config.sol_id):
            quote_ns = self._quote_ns.get(instrument_id)
            mark = self._latest_marks.get(instrument_id)
            if quote_ns is None or mark is None:
                return False
            if not (0 <= now_ns - quote_ns <= age and 0 <= now_ns - mark.ts_event <= age):
                return False
        return True

    def on_quote_tick(self, tick) -> None:
        if self._liquidating:
            self.recovery_confirmed = False
            raise RuntimeError("LIVE_LOCAL_LIQUIDATION_FORBIDDEN")
        if tick.instrument_id not in (self.config.btc_id, self.config.sol_id):
            return
        self._quote_ns[tick.instrument_id] = tick.ts_event
        if self._feeds_fresh(time.time_ns()):
            super().on_quote_tick(tick)

    def _submit_intent(
        self, intent: Intent, bid_price: float, ask_price: float,
        sigma: float | None, decision_index: int,
        only_instrument: InstrumentId | None = None, ts_now: int | None = None,
    ) -> None:
        if intent.action in {"BTC_ENTRY", "SOL_ADD"}:
            try:
                view = self._validated_live_money()
                # Leave a small margin for order construction and final submit.
                view.require_fresh(time.time_ns() // 1_000_000, 9_000)
            except ValueError:
                if not any(item[0].id == intent.id for item in self._queued_intents):
                    self._queued_intents.append((intent, sigma, decision_index))
                self._queued_intent_ready_ns[intent.id] = (ts_now or time.time_ns()) + 1
                self._request_live_refresh()
                return
        return super()._submit_intent(
            intent, bid_price, ask_price, sigma, decision_index,
            only_instrument=only_instrument, ts_now=ts_now,
        )

    def _record_submission(self, *args, **kwargs) -> bool:
        # Final pre-submit gate covers queued entries and every reduce-only management action.
        try:
            self._validated_live_money()
        except ValueError:
            return False
        if not self._feeds_fresh(time.time_ns()):
            return False
        if args and getattr(args[0], "is_reduce_only", True) is False:
            order = args[0]
            if not self._tier_allows_increase(
                order.instrument_id, order.side, order.quantity.as_decimal(), time.time_ns(),
            ):
                return False
        return super()._record_submission(*args, **kwargs)

    def attach_recovery_runtime(self, runtime) -> None:
        self._recovery_runtime = runtime

    def _terminal_submission(self, client_order_id: str) -> None:
        if self._recovery_runtime is None:
            return super()._terminal_submission(client_order_id)
        if getattr(self, "_terminal_checkpoint_deferred", None) != client_order_id:
            try:
                self._recovery_runtime.terminal_submission(client_order_id, self.on_save()[_KEY])
            except BaseException:
                self.recovery_confirmed = False
                raise

    def _terminal_without_fill(self, client_order_id: str) -> None:
        # The base callback removes pending/domain state after its terminal hook.
        # Commit the journal transition and the resulting checkpoint together.
        self._terminal_checkpoint_deferred = client_order_id
        try:
            super()._terminal_without_fill(client_order_id)
        finally:
            self._terminal_checkpoint_deferred = None
        self._terminal_submission(client_order_id)

    def on_order_canceled(self, event) -> None:
        client_order_id = str(event.client_order_id)
        self._terminal_checkpoint_deferred = client_order_id
        try:
            super().on_order_canceled(event)
        finally:
            self._terminal_checkpoint_deferred = None
        self._terminal_submission(client_order_id)

    def _after_domain_fill(self, event) -> None:
        if self._recovery_runtime is None:
            raise RuntimeError("RECOVERY_JOURNAL_NOT_ATTACHED")
        checkpoint = self.on_save()[_KEY]
        if not self._recovery_runtime.commit_applied_fills([str(event.trade_id)], checkpoint):
            self.recovery_confirmed = False
            raise RuntimeError("RECOVERY_FILL_CHECKPOINT_CONFLICT")

    def _entries_enabled(self) -> bool:
        try:
            self._validated_live_money()
        except ValueError:
            return False
        return self._feeds_fresh(time.time_ns()) and super()._entries_enabled()

    def on_save(self) -> dict[str, bytes]:
        document = {
            "schema": _SCHEMA,
            "candidate_sha256": hashlib.sha256(canonical_candidate_json(self._candidate).encode()).hexdigest(),
            "strategy_id": str(self.id),
            "domain": {
                "episode": _encode(self._domain.episode),
                "locked_after_liquidation": self._domain.locked_after_liquidation,
                "decision_index": self._domain._decision_index,
            },
            "state": {name: _encode(getattr(self, name)) for name in _FIELDS},
        }
        return {_KEY: json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()}

    def on_load(self, state: dict[str, bytes]) -> None:
        if set(state) != {_KEY}:
            raise ValueError("RECOVERY_STATE_KEY_MISMATCH")
        document = json.loads(state[_KEY])
        expected_hash = hashlib.sha256(canonical_candidate_json(self._candidate).encode()).hexdigest()
        if document.get("schema") != _SCHEMA or document.get("candidate_sha256") != expected_hash:
            raise ValueError("RECOVERY_STATE_IDENTITY_MISMATCH")
        if document.get("strategy_id") != str(self.id) or set(document.get("state", {})) != set(_FIELDS):
            raise ValueError("RECOVERY_STATE_FIELDS_MISMATCH")
        domain = document.get("domain")
        if not isinstance(domain, dict) or set(domain) != {"episode", "locked_after_liquidation", "decision_index"}:
            raise ValueError("RECOVERY_DOMAIN_FIELDS_MISMATCH")
        decoded = {name: _decode(item) for name, item in document["state"].items()}
        episode = _decode(domain["episode"])
        if episode is not None and not isinstance(episode, Episode):
            raise ValueError("RECOVERY_EPISODE_INVALID")
        self._domain.episode = episode
        self._domain.locked_after_liquidation = bool(domain["locked_after_liquidation"])
        self._domain._decision_index = int(domain["decision_index"])
        for name, item in decoded.items():
            setattr(self, name, item)
        from coinmaster.domain.wave_overlay import features_for
        self._current_signals = features_for(self._bars, self._candidate)
        self.recovery_confirmed = False
