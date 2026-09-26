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
from nautilus_trader.model.identifiers import InstrumentId

from coinmaster.domain.wave_overlay import DailyBar, Episode, Intent
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
        if not self.recovery_confirmed:
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
        if tick.instrument_id not in (self.config.btc_id, self.config.sol_id):
            return
        self._quote_ns[tick.instrument_id] = tick.ts_event
        if self._feeds_fresh(time.time_ns()):
            super().on_quote_tick(tick)

    def _record_submission(self, *args, **kwargs) -> bool:
        # Final pre-submit gate covers queued entries and every reduce-only management action.
        return self._feeds_fresh(time.time_ns()) and super()._record_submission(*args, **kwargs)

    def attach_recovery_runtime(self, runtime) -> None:
        self._recovery_runtime = runtime

    def _after_domain_fill(self, event) -> None:
        if self._recovery_runtime is None:
            raise RuntimeError("RECOVERY_JOURNAL_NOT_ATTACHED")
        checkpoint = self.on_save()[_KEY]
        if not self._recovery_runtime.commit_applied_fills([str(event.trade_id)], checkpoint):
            self.recovery_confirmed = False
            raise RuntimeError("RECOVERY_FILL_CHECKPOINT_CONFLICT")

    def _entries_enabled(self) -> bool:
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
