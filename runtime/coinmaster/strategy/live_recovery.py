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
from datetime import datetime,timezone,timedelta
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
from coinmaster.strategy.next_band import NextClosedBar


_SCHEMA = "coinmaster-wave-overlay-live-recovery-v1"
_KEY = "wave_overlay_live_recovery_v1"
_DATACLASSES = {item.__name__: item for item in (DailyBar, Episode, Intent)}
_FIELDS = (
    "_bars", "_pending_by_order", "_sigma_by_order", "_decision_index_by_order",
    "_last_sol_close", "_day", "_marks_by_session", "_current_btc", "_current_sol",
    "_current_btc_mark", "_current_sol_mark", "_latest_marks",
    "_queued_intents", "_queued_intent_ready_ns", "_mandatory_sol_exit",
    "_deferred_entry_session", "_deferred_selective_entries", "_selected_entry_audits",
    "_mandatory_sol_retry_after_ns", "_accepted_reductions",
    "_queued_close_submitted", "_group_close_reconciliation_pending",
    "_liquidating", "_liquidation_waiting", "_liquidation_orders",
    "_liquidation_submitted", "liquidation_audit", "pre_submit_gate_blocks",
    "marked_equity_checkpoints", "_terminal_order_ids", "_order_audit",
    "fill_audit", "_forced_close_reason", "_forced_close_intent",
    "_forced_close_submitted", "_forced_close_orders", "terminal_lifecycle",
)


_C1_SCHEMA = "coinmaster-wave-overlay-e4-c1-recovery-v3"
_C1_FIELDS = (
    "_live_signal_clock_state", "_c1_peak", "_c1_state", "_c1_checkpoint", "_c1_fill_epoch", "_c1_intents",
    "_c1_last_bars", "_c1_sol_levels", "_c1_terminal_ids", "_c1_blocked_ids",
    "_next_enabled", "_next_bars", "_next_last_bar", "_next_daily_ns", "_next_daily_side",
    "_next_count", "_next_wait", "_next_release", "_next_peak", "_next_equity", "_next_equity_ns",
    "_next_z", "_next_s", "_next_risk_intents", "_next_entry_terminal",
    "_hb_wait_regime", "_hb_daily_ohlc", "_hb_ema", "_hb_count", "_hb_bar_ns", "_hb_side",
    "_hb_cycle", "_hb_eligible", "_hb_quote_seq", "_hb_last_submit_seq", "_hb_cancel_ids", "_hb_exit_pending",
    "_split_parent", "_split_child_submit", "_seen_trade_ids", "_last_accepted_session", "_latest_seen_session",
)


def recovery_fields(config):
    return _FIELDS + _C1_FIELDS if config.research_residual_recovery else _FIELDS


def recovery_policy_hash(config, candidate):
    # Pin every research policy input plus the native execution/clock contract.
    names=getattr(type(config), "__struct_fields__", None)
    if names is None:names=tuple(vars(config))
    names=sorted(name for name in names if name.startswith("research_") or name in (
        "btc_id","sol_id","btc_signal_id","sol_signal_id","max_mark_age_ns",
        "execution_policy_hash","execution_policy_version","market_exit_time_in_force","market_exit_reduce_only",
        "tp_fee_floor_v1","freeze_sigma_on_first_sol_fill","max_gross_to_active"))
    def value(item):
        if hasattr(item,"type") and hasattr(item,"metadata"):
            return {"type":item.type.__module__+"."+item.type.__qualname__,"metadata":_encode(dict(item.metadata))}
        if isinstance(item,(tuple,list)):return [value(x) for x in item]
        if hasattr(item,"name") and not isinstance(item,(str,bytes)):
            return {"enum":type(item).__name__,"name":item.name}
        return _encode(item)
    body={name:value(getattr(config,name)) for name in names}
    if config.research_residual_recovery:
        body['live_deposit_limit_percent']=55
        body['retained_equity_floor_fraction']='0.45'
        body['live_input_clock_contract']='BYBIT_NATIVE_CONFIRMED_LAST_1M_UTC240_H4_ACTUAL_AVAILABILITY_V1'
        root=Path(__file__).resolve().parents[1]
        body['economic_source_pins']={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('strategy/residual_recovery.py','strategy/wave_overlay.py','strategy/next_band.py','strategy/hedge_band.py','domain/wave_overlay.py','strategy/c1_inputs.py')}
    body["candidate_sha256"]=hashlib.sha256(canonical_candidate_json(candidate).encode()).hexdigest()
    return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def checkpoint_structure(document):
    if not isinstance(document,dict):raise ValueError("RECOVERY_CHECKPOINT_STRUCTURE_UNKNOWN")
    c1=document.get("schema")==_C1_SCHEMA
    keys={"schema","candidate_sha256","strategy_id","domain","state"} | ({"policy_sha256"} if c1 else set())
    expected=_FIELDS+_C1_FIELDS if c1 else _FIELDS
    if (set(document)!=keys or document.get("schema") not in (_SCHEMA,_C1_SCHEMA)
        or not isinstance(document.get("state"),dict) or set(document["state"])!=set(expected)
        or not isinstance(document.get("domain"),dict)
        or set(document["domain"])!={"episode","locked_after_liquidation","decision_index"}
        or (c1 and (not isinstance(document["policy_sha256"],str) or len(document["policy_sha256"])!=64))):
        raise ValueError("RECOVERY_CHECKPOINT_STRUCTURE_UNKNOWN")
    return c1


# Public feed buffers may advance while the strict Info generation awaits.
# They are needed for restart/input continuity, but do not grant ownership of
# an order, fill, episode decision, exit or durable submission.
_PUBLIC_INPUT_FIELDS = frozenset({
    "_bars", "_last_sol_close", "_day", "_marks_by_session",
    "_current_btc", "_current_sol", "_current_btc_mark", "_current_sol_mark",
    "_latest_marks", "marked_equity_checkpoints",
})


def durable_decision_checkpoint(snapshot: bytes) -> bytes:
    """Compare exact owned decisions while allowing public input caches to move."""
    try:
        document = json.loads(snapshot)
        checkpoint_structure(document)
        document["state"] = {
            name: value for name, value in document["state"].items()
            if name not in _PUBLIC_INPUT_FIELDS
        }
        return json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        raise ValueError("RECOVERY_CHECKPOINT_STRUCTURE_UNKNOWN") from exc


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
    if isinstance(value, NextClosedBar):
        return {"t":"next_closed_bar","v":[_encode(value.instrument_id),value.hours,_encode(value.open),_encode(value.high),_encode(value.low),_encode(value.close),value.ts_event,value.ts_init]}
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
    if kind == "next_closed_bar":
        return NextClosedBar(*[_decode(item) for item in body])
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
        self._input_readiness_preparation=False
        self._live_signal_clock_state={}
        self._live_minute_bar_types=()
        self._live_input_request=None
        self._live_input_ws_epoch=None
        self._live_c1_input=None
        self._last_live_input_observation=None
        self._live_inputs_dirty=True
        self._live_inputs_reason='NO_NATIVE_OBSERVATION'
        self._live_history_cutoff_ns=None
        self._live_refresh = None
        self._manage_only_preparation = False
        self._management_certificate = None
        self._management_dispatch_enabled = False
        self._checkpoint_policy_valid = False
        self._loaded_policy_sha256 = None

    def request_live_input_observation(self):
        if self._input_readiness_preparation and self._live_input_request is not None:return self._live_input_request()
        return False

    def _start_live_inputs(self):
        if self._input_readiness_preparation:
            cutoff=self.clock.timestamp_ns()//60_000_000_000*60_000_000_000
            self._live_history_cutoff_ns=cutoff
            end=datetime.fromtimestamp(cutoff/1e9,tz=timezone.utc)
            # Native REST backfill has actual NOW availability; forming bar is
            # excluded by the fixed request cutoff, even if response is delayed.
            watermarks=self._live_signal_clock_state.get('last_h4',{})
            recent=cutoff//14_400_000_000_000*14_400_000_000_000-14_400_000_000_000
            # Persisted clocks determine missing coverage; downtime is never
            # silently truncated to the last two H4 windows.
            start_ns=min([recent,*watermarks.values()]) if watermarks else recent
            start=datetime.fromtimestamp(start_ns/1e9,tz=timezone.utc)
            for kind in self._live_minute_bar_types:
                self.subscribe_bars(kind)
                self.request_bars(kind,start=start,end=end)

    def _live_clock(self):
        from coinmaster.ops.hl_live_worker import ClosedTradeClock
        return ClosedTradeClock(self._live_signal_clock_state)

    def _accept_live_minute(self,bar,*,historical=False):
        if historical and (self._live_history_cutoff_ns is None or bar.ts_event>self._live_history_cutoff_ns):return
        source=bar.bar_type.instrument_id
        if source not in (self.config.btc_signal_id,self.config.sol_signal_id):raise ValueError('LIVE_MINUTE_SOURCE_SCOPE')
        instrument=self.config.btc_id if source==self.config.btc_signal_id else self.config.sol_id
        values=tuple(getattr(bar,key).as_decimal() for key in ('open','high','low','close'))
        available=self.clock.timestamp_ns()
        if self._recovery_runtime is not None:
            self._recovery_runtime.append_evidence('Bybit1m:'+str(source)+':'+str(bar.ts_event),'signal',
                dict(source='BYBIT_TRADE_CLOSED_1M',instrument=str(source),close_ns=bar.ts_event,OHLC=tuple(map(str,values)),received_ns=available))
        self._live_clock().minute(str(instrument),bar.ts_event,bar.ts_init,available,values)
        self._persist_transient_checkpoint()

    def on_historical_data(self,data):
        if self._input_readiness_preparation and isinstance(data,Bar) and data.bar_type in self._live_minute_bar_types:
            self._accept_live_minute(data,historical=True)
            return
        return super().on_historical_data(data)

    def on_bar(self,bar):
        if self._input_readiness_preparation:
            if bar.bar_type in self._live_minute_bar_types:
                self._accept_live_minute(bar);return
            if bar.bar_type in (self.config.btc_bar_type,self.config.sol_bar_type):
                available=self.clock.timestamp_ns()
                if not bar.ts_event<=bar.ts_init<=available or bar.ts_event%86_400_000_000_000:raise ValueError('LIVE_D1_SOURCE_INVALID')
                signal_id=bar.bar_type.instrument_id
                instrument=self.config.btc_id if signal_id==self.config.btc_signal_id else self.config.sol_id
                actual=DailySignalBar(signal_id,bar.open.as_decimal(),bar.high.as_decimal(),bar.low.as_decimal(),bar.close.as_decimal(),bar.ts_event,available)
                # Same actual DailySignal dispatch as the selected research core.
                if instrument==self.config.btc_id:self._hb_daily_ohlc[bar.ts_event]=(float(bar.high),float(bar.low))
                self.on_data(actual)
                self._live_clock().daily(str(instrument),bar.ts_event,available)
                self._persist_transient_checkpoint();return
        return super().on_bar(bar)

    def on_order_event(self,event):
        if self._input_readiness_preparation and self._recovery_runtime is not None:
            native=event.to_dict(event) if callable(getattr(event,'to_dict',None)) else {key:str(getattr(event,key,None)) for key in ('client_order_id','venue_order_id','instrument_id','ts_event','ts_init')}
            self._recovery_runtime.append_evidence(str(getattr(event,'id',None)) or str(getattr(event,'client_order_id',''))+':'+type(event).__name__+':'+str(getattr(event,'ts_event','')),'ACK',dict(native_type=type(event).__name__,native=native,received_ns=self.clock.timestamp_ns()))
        return super().on_order_event(event)

    def _materialize_live_c1_observation(self,now_ns):
        from coinmaster.ops.hl_live_money import materialize_live_c1_input
        observation=self._last_live_input_observation
        if observation is None or self._live_inputs_dirty or self._live_input_ws_epoch is None:
            raise ValueError('C1_LIVE_OBSERVATION_UNAVAILABLE')
        account=self.cache.account_for_venue(self.config.btc_id.venue)
        event=getattr(account,'last_event',None)
        account_event_id=getattr(event,'id',None) or getattr(event,'event_id',None)
        value=materialize_live_c1_input(observation,native_positions=tuple(self.cache.positions_open()),
            native_marks=self._latest_marks,native_cache=self.cache,account_event_id=account_event_id,
            strategy_id=str(self.id),account_id=str(account.id),decision_ns=now_ns,monotonic_ns=time.monotonic_ns(),
            revision=self._recovery_runtime.native_revision(),fill_epoch=self._c1_fill_epoch,
            ws_epoch=self._live_input_ws_epoch(),max_mark_age_ns=self.config.max_mark_age_ns)
        self._live_c1_input=value
        self._c1_observe(value.equity,value.decision_ns,value.source_available_ns,value.fill_epoch,value.positions)
        return value

    def _c1_current_money(self,ns):
        if not self._input_readiness_preparation:return super()._c1_current_money(ns)
        value=self._live_c1_input;c=self._c1_checkpoint
        if value is None or c is None or self._last_live_input_observation is None:return None
        try:
            self._last_live_input_observation.require_current(now_ns=time.monotonic_ns(),
                revision=self._recovery_runtime.native_revision(),fill_epoch=self._c1_fill_epoch,
                ws_epoch=self._live_input_ws_epoch())
            account=self.cache.account_for_venue(self.config.btc_id.venue);event=account.last_event
            event_id=getattr(event,'id',None) or getattr(event,'event_id',None)
            if str(event_id)!=value.account_event_id or self._live_inputs_dirty:return None
            if not c['source']<c['receipt']<=ns or c['epoch']!=self._c1_fill_epoch:return None
        except (ValueError,AttributeError,TypeError):return None
        return c

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
            self._current_owned_money()
        except (ValueError, RuntimeError):
            if self._current_btc is not None:
                self._deferred_entry_session = self._current_btc.ts_event
                self._daily_decision_reason = "DEFERRED_LIVE_MONEY"
            self._persist_transient_checkpoint()
            self._request_live_refresh()
            return
        super()._advance_current_day()
        self._persist_transient_checkpoint()

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

    def _current_owned_money(self, *, max_age_ms: int = 9_000):
        self._require_recovery_confirmed()
        view = self._validated_live_money()
        view.require_fresh(time.time_ns() // 1_000_000, max_age_ms)
        if self._recovery_runtime is None:
            return view, {}, ()  # Unbound source probes cannot submit live orders.
        if view.native_revision != self._recovery_runtime.native_revision():
            raise ValueError("LIVE_OWNED_MONEY_OBSOLETE")
        account = self.cache.account_for_venue(self.config.btc_id.venue)
        if account is None or account.balance_total(USDC) is None or account.balance_free(USDC) is None:
            raise ValueError("LIVE_OWNED_MONEY_OBSOLETE")
        projected_total = view.raw_usd if view.raw_usd < 0 else max(view.raw_usd, view.free_collateral)
        if (
            account.balance_total(USDC).as_decimal() != projected_total
            or account.balance_free(USDC).as_decimal() != view.free_collateral
        ):
            raise ValueError("LIVE_OWNED_MONEY_OBSOLETE")
        positions = {}
        for position in self.cache.positions_open():
            if (
                str(position.strategy_id) != str(self.id)
                or position.instrument_id not in (self.config.btc_id, self.config.sol_id)
            ):
                raise ValueError("LIVE_OWNED_MONEY_OBSOLETE")
            coin = "BTC" if position.instrument_id == self.config.btc_id else "SOL"
            if coin in positions:
                raise ValueError("LIVE_OWNED_MONEY_OBSOLETE")
            positions[coin] = position.quantity.as_decimal() * (1 if position.is_long else -1)
        if tuple(sorted(positions.items())) != view.position_sizes:
            raise ValueError("LIVE_OWNED_MONEY_OBSOLETE")
        journal = {row["client_order_id"]: row for row in self._recovery_runtime.all_submissions()}
        pending = []
        for order in self.cache.orders(venue=self.config.btc_id.venue):
            if str(order.strategy_id) != str(self.id) or str(order.client_order_id) not in journal:
                raise ValueError("LIVE_OWNED_MONEY_OBSOLETE")
            if order.is_closed or order.is_reduce_only:
                continue
            if order.venue_order_id is None:
                raise ValueError("LIVE_OWNED_MONEY_OBSOLETE")  # A forwarded order without venue proof is an unknown ACK.
            leaves = order.quantity.as_decimal() - order.filled_qty.as_decimal()
            if leaves <= 0:
                raise ValueError("LIVE_OWNED_MONEY_OBSOLETE")
            order_coin = "BTC" if order.instrument_id == self.config.btc_id else "SOL" if order.instrument_id == self.config.sol_id else ""
            pending.append((order_coin, order.side.name, leaves))
        return view, positions, tuple(pending)

    def _tier_allows_increase(self, instrument_id: InstrumentId, side: OrderSide, quantity: Decimal, ts_now: int) -> bool:
        try:
            view, positions, pending = self._current_owned_money()
            coin = "BTC" if instrument_id == self.config.btc_id else "SOL" if instrument_id == self.config.sol_id else ""
            return prospective_cross_margin_ok(
                view, positions=positions, pending_openings=pending,
                coin=coin, side=side.name, quantity=quantity,
                max_gross_multiple=self.config.max_gross_to_active,
            )
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return False

    def _persist_transient_checkpoint(self) -> None:
        runtime = self._recovery_runtime
        if runtime is None:
            return
        revision = runtime.native_revision()
        body = self.on_save()[_KEY]
        checkpoint = runtime.strategy_checkpoint()
        if (
            checkpoint is not None and checkpoint[1] == revision
            and durable_decision_checkpoint(checkpoint[0]) == durable_decision_checkpoint(body)
        ):
            return
        if not runtime.persist_strategy_checkpoint(body, revision):
            self.recovery_confirmed = False
            raise RuntimeError("LIVE_TRANSIENT_CHECKPOINT_REVISION_MOVED")

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
        self._start_live_inputs()
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
        if self._manage_only_preparation or self.config.research_residual_recovery:
            raise RuntimeError("MANAGE_ONLY_NORMAL_DISPATCH_FORBIDDEN")
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
        if self._input_readiness_preparation:
            now_ns=self.clock.timestamp_ns()
            if tick.instrument_id not in (self.config.btc_id,self.config.sol_id):return
            if not tick.ts_event<=tick.ts_init<=now_ns:raise ValueError('LIVE_QUOTE_CLOCK_INVALID')
            try:self._materialize_live_c1_observation(now_ns)
            except ValueError as error:
                self._live_c1_input=None;self._live_inputs_reason=str(error)
                self.request_live_input_observation()
            for bar in self._live_clock().drain(self.clock.timestamp_ns(),(str(self.config.btc_id),str(self.config.sol_id))):
                o,h,l,c=bar['OHLC'];instrument=self.config.btc_id if bar['instrument']==str(self.config.btc_id) else self.config.sol_id
                self.on_data(NextClosedBar(instrument,bar['hours'],o,h,l,c,bar['close_ns'],bar['available_ns']))
            current=self._c1_current_money(now_ns)
            if current is not None:self._c1_first_fresh_quote(tick,current,decision_ns=now_ns)
            # Observe selected policy only: no ordinary quote command callback,
            # dispatch, queued historical quote or ownership authority here.
            self._persist_transient_checkpoint()
            return
        if self._liquidating:
            self.recovery_confirmed = False
            raise RuntimeError("LIVE_LOCAL_LIQUIDATION_FORBIDDEN")
        if tick.instrument_id not in (self.config.btc_id, self.config.sol_id):
            return
        self._quote_ns[tick.instrument_id] = tick.ts_event
        if self._feeds_fresh(time.time_ns()):
            if self.config.deposit_runtime is None or not self._deposit.latched:
                try:
                    self._current_owned_money()
                except (ValueError, RuntimeError):
                    self._request_live_refresh()
                    return
            super().on_quote_tick(tick)
            self._persist_transient_checkpoint()

    def _submit_intent(
        self, intent: Intent, bid_price: float, ask_price: float,
        sigma: float | None, decision_index: int,
        only_instrument: InstrumentId | None = None, ts_now: int | None = None,
    ) -> None:
        if intent.action != "CLOSE_ALL":
            try:
                self._current_owned_money()
            except (ValueError, RuntimeError):
                if not any(item[0].id == intent.id for item in self._queued_intents):
                    self._queued_intents.append((intent, sigma, decision_index))
                self._queued_intent_ready_ns[intent.id] = (ts_now or time.time_ns()) + 1
                self._persist_transient_checkpoint()
                self._request_live_refresh()
                return
        return super()._submit_intent(
            intent, bid_price, ask_price, sigma, decision_index,
            only_instrument=only_instrument, ts_now=ts_now,
        )

    def _record_submission(self, *args, **kwargs) -> bool:
        # Final pre-submit gate covers queued entries and every reduce-only management action.
        try:
            self._require_recovery_confirmed()
        except RuntimeError:
            return False
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

    def on_order_filled(self, event) -> None:
        # The base callback returns early for native group/DP closes. Those
        # actual fills still need the same atomic applied-ID/checkpoint commit
        # as an ordinary domain fill, after its native close state is updated.
        trade_id, order_id = str(event.trade_id), str(event.client_order_id)
        if self._input_readiness_preparation:
            self._live_inputs_dirty=True;self._last_live_input_observation=None;self._live_c1_input=None
        duplicate = trade_id in self._seen_trade_ids
        special = any(order_id in getattr(self, name) for name in (
            "_forced_close_orders", "_deposit_exit_orders", "_terminal_order_ids",
            "_liquidation_orders", "_v3_orders"))
        if special and not duplicate:
            if self._recovery_runtime is None:
                raise RuntimeError("RECOVERY_JOURNAL_NOT_ATTACHED")
            owned = [row for row in self._recovery_runtime.all_submissions()
                     if row["client_order_id"] == order_id]
            if (len(owned) != 1 or owned[0]["instrument_id"] != str(event.instrument_id)
                    or owned[0]["body"].get("reduce_only") is not True):
                self.recovery_confirmed = False
                raise RuntimeError("RECOVERY_SPECIAL_FILL_OWNERSHIP_UNKNOWN")
        WaveOverlayStrategy.on_order_filled(self, event)
        if special and not duplicate and trade_id in self._seen_trade_ids:
            detail = self._recovery_runtime.db.execute(
                "SELECT client_order_id,instrument_id,quantity FROM paper_native_fill_details WHERE trade_id=?",
                (trade_id,)).fetchone()
            if (detail is None or detail[0] != order_id or detail[1] != str(event.instrument_id)
                    or Decimal(detail[2]) != event.last_qty.as_decimal()):
                self.recovery_confirmed = False
                raise RuntimeError("RECOVERY_SPECIAL_FILL_JOURNAL_MISMATCH")
            if not self._recovery_runtime.has_applied_fill(trade_id):
                self._after_domain_fill(event)

    def _after_domain_fill(self, event) -> None:
        if self._recovery_runtime is None:
            raise RuntimeError("RECOVERY_JOURNAL_NOT_ATTACHED")
        checkpoint = self.on_save()[_KEY]
        if not self._recovery_runtime.commit_applied_fills([str(event.trade_id)], checkpoint):
            self.recovery_confirmed = False
            raise RuntimeError("RECOVERY_FILL_CHECKPOINT_CONFLICT")

    def _entries_enabled(self) -> bool:
        if self._manage_only_preparation or self.config.research_residual_recovery:return False
        try:
            self._validated_live_money()
        except ValueError:
            return False
        return self._feeds_fresh(time.time_ns()) and super()._entries_enabled()

    def on_save(self) -> dict[str, bytes]:
        document = {
            "schema": _C1_SCHEMA if self.config.research_residual_recovery else _SCHEMA,
            "candidate_sha256": hashlib.sha256(canonical_candidate_json(self._candidate).encode()).hexdigest(),
            "strategy_id": str(self.id),
            "domain": {
                "episode": _encode(self._domain.episode),
                "locked_after_liquidation": self._domain.locked_after_liquidation,
                "decision_index": self._domain._decision_index,
            },
            "state": {name: _encode(getattr(self, name)) for name in recovery_fields(self.config)},
        }
        if self.config.research_residual_recovery:document["policy_sha256"]=recovery_policy_hash(self.config,self._candidate)
        return {_KEY: json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()}

    def on_load(self, state: dict[str, bytes]) -> None:
        self._checkpoint_policy_valid=False
        self._loaded_policy_sha256=None
        self._management_certificate=None
        self.recovery_confirmed=False
        if set(state) != {_KEY}:
            raise ValueError("RECOVERY_STATE_KEY_MISMATCH")
        document = json.loads(state[_KEY])
        expected_hash = hashlib.sha256(canonical_candidate_json(self._candidate).encode()).hexdigest()
        self._checkpoint_policy_valid=False
        self._management_certificate=None
        c1=checkpoint_structure(document)
        if c1!=bool(self.config.research_residual_recovery) or (c1 and document["policy_sha256"]!=recovery_policy_hash(self.config,self._candidate)):
            raise ValueError("RECOVERY_POLICY_IDENTITY_MISMATCH")
        if document.get("schema") not in (_SCHEMA,_C1_SCHEMA) or document.get("candidate_sha256") != expected_hash:
            raise ValueError("RECOVERY_STATE_IDENTITY_MISMATCH")
        if document.get("strategy_id") != str(self.id) or set(document.get("state", {})) != set(recovery_fields(self.config)):
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
        self._checkpoint_policy_valid=c1
        self._loaded_policy_sha256=document.get("policy_sha256") if c1 else None
        self._quote_ns={}  # Saved inputs never grant new live freshness/authority.
        self._management_certificate=None

    def enable_manage_only_preparation(self) -> None:
        if not self.config.research_residual_recovery:
            raise RuntimeError("MANAGE_ONLY_REQUIRES_E4_C1_CHECKPOINT")
        self._manage_only_preparation=True
        self.recovery_confirmed=False
        self._management_dispatch_enabled=False
        self._management_certificate=None

    def revoke_management(self) -> None:
        self._management_certificate=None
        self.recovery_confirmed=False

    def dispatch_manage_only(self, command_id, kind, order, *, now_ns=None):
        """One explicit owned action, never a replay/automatic close loop.

        The outer immutable release approval remains independently required.
        Preparation leaves dispatch disabled; no persisted field enables it.
        """
        from coinmaster.ops.live_recovery import reserve_managed_action
        now_ns=time.time_ns() if now_ns is None else now_ns
        if not self._management_dispatch_enabled:raise RuntimeError("LIVE_ORDER_CAPABILITY_FALSE")
        cert=self._management_certificate
        self._management_certificate=None  # Consume before reservation, even on failure.
        if cert is None:raise RuntimeError("MANAGEMENT_CERTIFICATE_REQUIRED")
        order=reserve_managed_action(self,cert,command_id,kind,order,now_ns=now_ns)
        if kind=="CANCEL":return WaveOverlayStrategy.cancel_order(self,order)
        return WaveOverlayStrategy.submit_order(self,order)
