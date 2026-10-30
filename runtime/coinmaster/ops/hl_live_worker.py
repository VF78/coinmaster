"""Isolated mainnet composition. No Sandbox account or automatic restart takeover."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import signal
import threading
import time
import uuid
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from nautilus_trader.adapters.bybit import BybitLiveDataClientFactory
from nautilus_trader.adapters.hyperliquid import HyperliquidLiveDataClientFactory
from nautilus_trader.adapters.hyperliquid.config import HyperliquidExecClientConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.enums import TimeInForce, BarAggregation, PriceType, AggregationSource
from nautilus_trader.model.data import BarType, BarSpecification
from nautilus_trader.model.identifiers import ClientId

from coinmaster.ops.hl_live_credential_preflight import check_live_credential, _read_json
from coinmaster.ops.hl_live_execution import ScopedHyperliquidExecClientFactory,ReadinessInfoBudget
from coinmaster.ops.hyperliquid_testnet import (
    BTC_PERP, SOL_PERP, TESTNET_IDS, LifecycleHooks, HyperliquidTestnetNode,
    cross_venue_stage_g_gate, hyperliquid_testnet_node_config, load_stageg_warmup_bundle,
)
from coinmaster.ops.hyperliquid_testnet_worker import TestnetWorker, create_status_server
from coinmaster.ops.live_recovery import NativeLiveRecoveryScope, LiveRecoverySubmissionSink, durable_management_scope
from coinmaster.ops.native_paper_node import BYBIT_IDS, FeedBook, FeedObserver, FeedObserverConfig, bybit_daily_bar_type
from coinmaster.ops.hl_live_epoch import LiveEpochRuntime as PaperRuntime
from coinmaster.ops.hl_live_profile import load_live_profile, require_profile_deposit_parity,initial_capital_limit,actual_initial_capital,staging_a_epoch_seed
from coinmaster.ops.stage_g_config import load_candidate, load_testnet_instance_config
from coinmaster.strategy.live_recovery import RecoverableWaveOverlayStrategy
from coinmaster.strategy.wave_overlay import WaveOverlayStrategyConfig
from coinmaster.venues.marks import venue_mark_data_type

SEALED_V0_SHA = "0edecde9548533004292d5a6174ef6aeb77596817080c4a160f72aa2dc7dd511"


def require_live_order_approval(path: Path, fingerprint_path: Path, release_root: Path,*,profile=None) -> dict:
    """Exact immutable release authorization; source preparation never impliesSTART."""
    try:
        approval=json.loads(path.read_text());fingerprint=json.loads(fingerprint_path.read_text())
        identity=json.loads((release_root/'live-release.json').read_text())
        selected=profile is not None and profile.get('profile_id') in ('E4_C1_INPUT_READINESS_ONLY','E4_C1_ACTIVE_SELECTED')
        active=selected and profile['profile_id']=='E4_C1_ACTIVE_SELECTED'
        if (approval.get('instance_id')!='hl-stageg-live'
            or approval.get('release_commit')!=identity['source_commit']
            or approval.get('master_address_sha256')!=fingerprint['master_address_sha256']
            or approval.get('strategy_sha256')!=identity['strategy_sha256']
            or approval.get('candidate_sha256')!=identity['candidate_sha256']
            or approval.get('profile_sha256')!=identity['profile_sha256']):raise ValueError
        if selected:
            actual = actual_initial_capital(profile)
            if actual:
                policy=profile['initial_capital_policy']
                if (identity.get('initial_capital_policy')!=policy or approval.get('initial_capital_policy')!=policy
                    or 'initial_capital_limit_usdc' in identity or 'initial_capital_limit_usdc' in approval):raise ValueError
            else:
                cap=profile['initial_capital_usdc'];initial_capital_limit(cap)
                if identity.get('initial_capital_limit_usdc')!=cap or approval.get('initial_capital_limit_usdc')!=cap:raise ValueError
            if (approval.get('schema')!='coinmaster-live-order-approval-v2'
                or profile['profile_sha256']!=identity['profile_sha256']
                or identity.get('account_mode')!=profile['account_mode'] or approval.get('account_mode')!=profile['account_mode']
                or identity.get('equity_basis')!=profile['equity_basis'] or approval.get('equity_basis')!=profile['equity_basis']
                or identity.get('money_currency')!='USDC' or identity.get('research_source')!=profile['research_source']
                or identity.get('economic_config_sha256')!=profile['economic_config_sha256']):raise ValueError
            if active or profile.get('initialization_intent') is not None:
                if (approval.get('authorization')!='START_LIVE_E4_C1' or approval.get('start_approved') is not True
                    or approval.get('orders_approved') is not True):raise ValueError
            elif approval.get('authorization')!='PREPARE_ONLY' or approval.get('orders_approved') is not False:raise ValueError
        else:
            if approval.get('schema')!='coinmaster-live-order-approval-v1' or approval.get('orders_approved') is not True:raise ValueError
            # Legacy profile remains exact-bound; no source literal private amount.
            cap=identity.get('initial_capital_limit_usdc',approval.get('pilot_capital_usdc'))
            initial_capital_limit(cap)
            if approval.get('pilot_capital_usdc')!=cap:raise ValueError
        return approval
    except (OSError,ValueError,KeyError,TypeError,RuntimeError):
        raise RuntimeError('LIVE_OWNER_ORDER_APPROVAL_REQUIRED') from None


class LiveSubmissionHooks(LifecycleHooks):
    def __init__(self, runtime):
        super().__init__(runtime)
        self.strategy = None

    def __call__(self, **request):
        if self.strategy is None:
            raise RuntimeError("LIVE_STRATEGY_NOT_BOUND")
        return LiveRecoverySubmissionSink(
            self.runtime, self.strategy, frozenset(map(str, TESTNET_IDS)),
        )(**request)


class ClosedTradeClock:
    """True Bybit trade1m -> BTC/SOL H4 + SOL1H, actual availability."""
    MINUTE=60_000_000_000
    H4=14_400_000_000_000
    DAY=86_400_000_000_000
    def __init__(self,state):self.state=state
    def minute(self,instrument,close_ns,init_ns,available_ns,values):
        if (type(close_ns) is not int or close_ns<=0 or close_ns%self.MINUTE or not close_ns<=init_ns<=available_ns
            or len(values)!=4 or not all(v.is_finite() for v in values)
            or not 0<values[2]<=min(values[0],values[3])<=max(values[0],values[3])<=values[1]):
            raise ValueError('LIVE_CLOSED_MINUTE_INVALID')
        for hours in ((1,4) if instrument.startswith('SOL') else (4,)):
            span=hours*60*self.MINUTE;start=((close_ns-1)//span)*span;key=(instrument,hours,start)
            buckets=self.state.setdefault('minute_buckets',{});bucket=buckets.setdefault(key,{})
            record=(tuple(values),available_ns)
            if close_ns in bucket:
                if bucket[close_ns][0]!=record[0]:raise ValueError('LIVE_CLOSED_MINUTE_CONFLICT')
                continue
            bucket[close_ns]=record
            if len(bucket)==hours*60:
                expected=list(range(start+self.MINUTE,start+span+self.MINUTE,self.MINUTE))
                if sorted(bucket)!=expected:raise ValueError('LIVE_CLOSED_AGGREGATE_GAP')
                rows=[bucket[ns][0] for ns in expected]
                bar=dict(instrument=instrument,hours=hours,close_ns=start+span,
                    available_ns=max(bucket[ns][1] for ns in expected),
                    OHLC=(rows[0][0],max(r[1] for r in rows),min(r[2] for r in rows),rows[-1][3]))
                published=self.state.setdefault('last_closed',{}).get((instrument,hours),0)
                if bar['close_ns']>published:self.state.setdefault('pending_h4',[]).append(bar)
            starts=sorted(k[2] for k in buckets if k[:2]==(instrument,hours))
            for old in starts[:-3]:buckets.pop((instrument,hours,old))
    def daily(self,instrument,close_ns,available_ns):
        if close_ns%self.DAY or close_ns>available_ns:raise ValueError('LIVE_CLOSED_D1_INVALID')
        days=self.state.setdefault('daily_seen',{});old=days.get(instrument)
        if old is None or close_ns>old[0]:days[instrument]=(close_ns,available_ns)
    def drain(self,quote_available_ns,instruments):
        remaining=[];ready=[];days=self.state.get('daily_seen',{})
        published=dict(self.state.get('last_closed',{}));h4=dict(self.state.get('last_h4',{}))
        for bar in sorted(self.state.get('pending_h4',[]),key=lambda b:(b['close_ns'],b['instrument'],b['hours'])):
            available=bar['available_ns'];hours=bar['hours']
            if hours==4 and bar['close_ns']%self.DAY==0:
                if any(i not in days or days[i][0]<bar['close_ns'] for i in instruments):remaining.append(bar);continue
                available=max(available,*(days[i][1] for i in instruments))
            if available>=quote_available_ns:remaining.append(bar);continue
            bar=dict(bar,available_ns=available);key=(bar['instrument'],hours)
            last=published.get(key,0)
            if last and bar['close_ns']>last+hours*60*self.MINUTE:
                raise ValueError('LIVE_CLOSED_AGGREGATE_COVERAGE_GAP')
            if bar['close_ns']>last:
                ready.append(bar);published[key]=bar['close_ns']
                if hours==4:h4[bar['instrument']]=bar['close_ns']
        self.state['pending_h4']=remaining
        self.state['last_closed']=published;self.state['last_h4']=h4
        return ready


class HyperliquidLiveNode:
    # Reuse only public feature/warmup, native cache projection and lifecycle helpers.
    def _refresh_warmup_readiness(self):
        HyperliquidTestnetNode._refresh_warmup_readiness(self)
        self.gate = replace(
            self.gate,
            attachable=(self.gate.warmup_state == "READY"
                        and self.gate.approval_state == "SEALED_LIVE_TECHNICAL_PROFILE_MATCH"
                        and self.gate.margin_policy_state == "READY_PUBLIC_HL_MAINNET_TIERS_LOCAL_SANDBOX_LEVERAGE"),
        )

    native_snapshot = HyperliquidTestnetNode.sandbox_snapshot
    strategy_restartable = HyperliquidTestnetNode.strategy_restartable
    start = HyperliquidTestnetNode.start
    stop = HyperliquidTestnetNode.stop

    def __init__(self, *, instance, candidate, state, credential_path, fingerprint_path,order_approval=None,readiness_budget=None):
        if instance.mode != "live" or instance.instance_id != "hl-stageg-live":
            raise RuntimeError("LIVE_INSTANCE_REQUIRED")
        self.instance, self.candidate, self.state = instance, candidate, state
        self.profile_root = Path(__file__).resolve().parents[2]
        source = self.profile_root / "coinmaster/strategy/wave_overlay.py"
        self.profile = load_live_profile(self.profile_root, candidate)
        self.input_readiness=self.profile.get('input_readiness',False) is True
        self.account_mode=self.profile.get('account_mode','disabled')
        self.active_c1=self.profile.get('profile_id')=='E4_C1_ACTIVE_SELECTED'
        if self.active_c1 and (not isinstance(order_approval,dict) or order_approval.get('authorization')!='START_LIVE_E4_C1' or order_approval.get('start_approved') is not True or order_approval.get('orders_approved') is not True or order_approval.get('profile_sha256')!=self.profile.get('profile_sha256')):
            raise RuntimeError('LIVE_OWNER_START_REQUIRED')
        if self.input_readiness and not self.active_c1 and self.profile.get('manage_only_readiness',False) is not True:
            raise RuntimeError('INPUT_READINESS_REQUIRES_MANAGE_ONLY')
        # Qualification never implies order authorization: main checks approval before this read.
        self.readiness_budget=readiness_budget if readiness_budget is not None else ReadinessInfoBudget()
        self.account_context={}
        equity=check_live_credential(credential_path,fingerprint_path,account_mode=self.account_mode,readiness_budget=self.readiness_budget,context_out=self.account_context)
        if self.active_c1 and not actual_initial_capital(self.profile) and state.strategy_checkpoint() is None and equity>initial_capital_limit(self.profile['initial_capital_usdc']):
            raise RuntimeError('LIVE_INITIAL_CAPITAL_LIMIT_EXCEEDED')
        prior_balance = getattr(state, "flat_epoch_balance", None)
        if not self.input_readiness and self.profile.get("manage_only_readiness",False) is not True and equity != (prior_balance if prior_balance is not None else initial_capital_limit(self.profile["initial_capital_usdc"])):
            raise RuntimeError("LIVE_INITIAL_OR_OWNED_FLAT_BALANCE_REQUIRED")
        record = _read_json(credential_path)
        self.master = record["master_address"]
        self.gate = cross_venue_stage_g_gate(
            candidate=candidate, warmup_manifest=instance.signal_warmup_manifest,
            strategy_path=source, profile_root=self.profile_root,
        )
        self.gate = replace(
            self.gate, approval_state="SEALED_LIVE_TECHNICAL_PROFILE_MATCH",
            attachable=(self.gate.warmup_state == "READY" and self.gate.margin_policy_state ==
                        "READY_PUBLIC_HL_MAINNET_TIERS_LOCAL_SANDBOX_LEVERAGE"),
        )
        self.candidate_hash = self.gate.candidate_hash
        self.warmup_bundle, self.warmup_state = load_stageg_warmup_bundle(instance.signal_warmup_manifest)
        if self.warmup_bundle is None or not self.gate.attachable:
            raise RuntimeError("LIVE_WARMUP_OR_SEAL_NOT_READY")
        self._warmup_verified_day = time.time_ns() // 86_400_000_000_000
        self._warmup_verified_target = instance.signal_warmup_manifest.resolve()
        self._warmup_checked_at_ns = time.time_ns()
        self.hooks = LiveSubmissionHooks(state)
        self.feed = FeedBook(ids=TESTNET_IDS, native_event_sink=self.hooks.record_event)
        self.loop = asyncio.new_event_loop()
        self.config = hyperliquid_testnet_node_config(trader_id=instance.trader_id, execution_mode="live")
        execution = self.config.exec_clients["HYPERLIQUID-LIVE"]
        self.config.exec_clients["HYPERLIQUID-LIVE"] = HyperliquidExecClientConfig(
            instrument_provider=execution.instrument_provider, routing=execution.routing,
            environment=execution.environment, private_key=record["agent_private_key"],
            account_address=self.master, vault_address=None, include_builder_attribution=False,
        )
        del record
        strategy_flags=dict(self.profile['strategy_flags'])
        for key in ('research_c1_restore_dd','research_regime_reentry_band','research_btc_split_discount'):
            if key in strategy_flags:strategy_flags[key]=Decimal(str(strategy_flags[key]))
        if self.input_readiness:
            from coinmaster.ops.stage_g_warmup import load_stageg_bybit_warmup
            rows,warmup_state=load_stageg_bybit_warmup(instance.signal_warmup_manifest)
            if warmup_state!='READY':raise RuntimeError('C1_DAILY_OHLC_WARMUP_UNKNOWN')
            strategy_flags['research_band_daily_seed']=tuple(((int(row['open_time_ms'])+86_400_000)*1_000_000,float(row['high']),float(row['low'])) for row in rows['BTCUSDT'])
        self.strategy = RecoverableWaveOverlayStrategy(WaveOverlayStrategyConfig(
            strategy_id=instance.strategy_id, order_id_tag=instance.order_id_tag,
            btc_id=BTC_PERP, sol_id=SOL_PERP,
            btc_bar_type=bybit_daily_bar_type(BYBIT_IDS[0]), sol_bar_type=bybit_daily_bar_type(BYBIT_IDS[1]),
            btc_mark_data_type=venue_mark_data_type(BTC_PERP), sol_mark_data_type=venue_mark_data_type(SOL_PERP),
            mark_client_id=ClientId("HYPERLIQUID-MAINNET-DATA"), live_mark_client_id=ClientId("HYPERLIQUID-MAINNET-DATA"),
            active_seed=staging_a_epoch_seed(self.profile,state,equity), candidate=candidate, seed_bars=self.warmup_bundle.bars,
            live_start_approved=self.active_c1,live_initial_capital_limit_usdc=self.profile.get("initial_capital_usdc","0"),
            live_initial_capital_policy=self.profile.get("initial_capital_policy",""),
            live_account_mode=self.account_mode,live_equity_basis=self.profile.get('equity_basis','HYPERLIQUID_CLASSIC_PERPS_ACCOUNT_VALUE_V1'),
            **strategy_flags,
            max_mark_age_ns=120_000_000_000, entries_gate=self._entries_enabled,
            event_sink=self.hooks.record_event, native_fill_sink=state.record_native_fill, submission_sink=self.hooks,
            btc_signal_id=BYBIT_IDS[0], sol_signal_id=BYBIT_IDS[1],
            execution_policy_hash="hl-mainnet-native-owned-v1", execution_policy_version="hl-mainnet-native-owned-v1",
            market_exit_time_in_force=TimeInForce.IOC, market_exit_reduce_only=True,
            deposit_runtime=state, deposit_instance_id=instance.instance_id, deposit_account_id="HYPERLIQUID-master",
            deposit_equity_reader=lambda strategy: strategy._validated_live_deposit_equity(),
            deposit_high_water_allowed=lambda:self.strategy._capital_high_water_allowed(),
            deposit_initialization_allowed=lambda: (self.strategy.recovery_confirmed or (self.input_readiness and state.c1_initialization() is not None and state.coherent_snapshot() and state.recovery_state()=='FLAT_RESTART')) and not state.all_submissions(),
        ))
        self.hooks.strategy = self.strategy
        if self.active_c1:
            state.bind_live_health(self._live_health_current)
        # Paused preparation must reach the existing explicit flat-only setter.
        # Readiness checks below retain strict profile/durable parity; construction
        # never changes/reset the persisted control or high-water anchor.
        self.strategy._input_readiness_preparation=self.input_readiness
        if self.input_readiness:
            self.strategy._live_minute_bar_types=tuple(BarType(i,BarSpecification(1,BarAggregation.MINUTE,PriceType.LAST),AggregationSource.EXTERNAL) for i in BYBIT_IDS)
            self.config.data_clients['BYBIT-PUBLIC-SIGNAL']=replace(self.config.data_clients['BYBIT-PUBLIC-SIGNAL'],bars_timestamp_on_close=True)
        self.manage_only_readiness=self.profile.get("manage_only_readiness",False) is True
        if self.input_readiness:
            if self.active_c1:
                state.entry_control_command('pause-new-entries','active-node-start:'+uuid.uuid4().hex)
            else:self.strategy.enable_manage_only_preparation()
            checkpoint=state.strategy_checkpoint()
            if checkpoint is None:
                intent=self.profile.get('initialization_intent')
                if (intent!='INITIALIZE_FRESH_C1_EPOCH' or state.c1_initialization() is not None
                    or state.all_submissions() or state.applied_fill_ids() or state.pending_submissions()
                    or state.pending_native_funding()):raise RuntimeError('MANAGEMENT_POLICY_LOAD_REQUIRED')
                state.entry_control_command('pause-new-entries','c1-init-prepare')
                self.strategy._fresh_c1_init_intent=intent
                scope=NativeLiveRecoveryScope(self.master,"",time.time_ns()//1_000_000,None,(),frozenset({"BTC","SOL"}))
            else:
                self.strategy.on_load({"wave_overlay_live_recovery_v1":checkpoint[0]})
                from nautilus_trader.core import nautilus_pyo3
                def cloid_for(client_id):
                    return str(nautilus_pyo3.hyperliquid_cloid_from_client_order_id(nautilus_pyo3.ClientOrderId(client_id)))
                scope=durable_management_scope(state,self.master,"",cloid_for)
        else:
            scope=NativeLiveRecoveryScope(self.master,"",time.time_ns()//1_000_000,None,(),frozenset({"BTC","SOL"}))
        factory = ScopedHyperliquidExecClientFactory.bind(scope, state, self.strategy, account_lock_root=Path("/run/coinmaster-hl-live"),readiness_budget=self.readiness_budget,account_context=self.account_context)
        self.node = TradingNode(config=self.config, loop=self.loop)
        self.node.add_data_client_factory("BYBIT", BybitLiveDataClientFactory)
        if self.account_mode=='unifiedAccount':
            from coinmaster.ops.hl_unified_instruments import UnifiedHyperliquidDataClientFactory
            self.node.add_data_client_factory('HYPERLIQUID',UnifiedHyperliquidDataClientFactory)
        else:self.node.add_data_client_factory("HYPERLIQUID", HyperliquidLiveDataClientFactory)
        self.node.add_exec_client_factory("HYPERLIQUID", factory)
        self.node.build()
        self.feed_observer = FeedObserver(FeedObserverConfig(
            instrument_ids=TESTNET_IDS, client_ids=(ClientId("HYPERLIQUID-MAINNET-DATA"),) * 2, feed=self.feed,
        ))
        self.node.trader.add_strategy(self.feed_observer)
        self.node.trader.add_strategy(self.strategy)
        self._thread = None
        self.prime_error = None

    def _live_health_current(self):
        """Current LIVE authority plus only acknowledged, owned standing BTC TPs.

        The selected dispatcher creates standing LIMIT/GTC protection only for
        BTC_REDUCE. SOL exits are IOC and remain blocked while nonterminal.
        This reader must never call runtime.health (also used by submission).
        """
        strategy, runtime = self.strategy, self.state
        if (strategy._recovery_runtime is not runtime or not self.active_c1
            or not strategy._active_c1_authorized or strategy._manage_only_preparation
            or not strategy._owned_chain_current() or not strategy._capital_basis_verified
            or strategy._live_context_current is None or not strategy._live_context_current()
            or strategy._live_increase_headroom is None or not strategy._live_increase_headroom()
            or strategy.deposit_projection()['state'] != 'ARMED'):
            return False
        revision = runtime.native_revision()
        view, positions, pending_openings = strategy._current_owned_money()
        if pending_openings or view.native_revision != revision:
            return False
        rows = runtime.pending_submissions()
        orders = strategy.cache.orders(venue=strategy.config.btc_id.venue)
        opened = [order for order in orders if not order.is_closed]
        native = {str(order.client_order_id): order for order in opened}
        records = {row['client_order_id']: row for row in rows}
        if len(native) != len(opened) or len(records) != len(rows) or set(native) != set(records):
            return False
        chain = strategy._owned_effect_chain
        episode = strategy._domain.episode
        held = positions.get('BTC', Decimal(0))
        reserved = Decimal(0)
        def name(value): return getattr(value, 'name', str(value))
        for client, row in records.items():
            order = native[client]
            body = row['body']; shape = body.get('shape') or {}
            intent = strategy._pending_by_order.get(client)
            if (row['state'] != 'ACKED' or row['action'] != 'BTC_REDUCE'
                or row['instrument_id'] != str(strategy.config.btc_id)
                or body.get('reduce_only') is not True or episode is None
                or row['episode_id'] != episode.id or intent is None
                or (intent.id, intent.episode_id, intent.action) != (row['intent_id'], row['episode_id'], row['action'])
                or intent.limit_price is None or not str(intent.reason or '').startswith('BTC_TP')
                or str(order.strategy_id) != str(strategy.id) or str(order.account_id) != chain[0]
                or str(order.instrument_id) != row['instrument_id'] or order.venue_order_id is None
                or name(order.status) not in ('ACCEPTED', 'PARTIALLY_FILLED')
                or order.is_pending_cancel or order.is_pending_update
                or not order.is_reduce_only or not order.is_post_only or not order.has_price
                or shape.get('kind') != 'LIMIT' or name(order.order_type) != 'LIMIT'
                or shape.get('tif') != 'GTC' or name(order.time_in_force) != 'GTC'
                or shape.get('post_only') is not True
                or shape.get('side') not in ('BUY', 'SELL') or name(order.side) != shape['side']
                or (shape['side'] == 'SELL') != (held > 0)
                or order.quantity.as_decimal() != Decimal(body['quantity'])
                or order.price.as_decimal() != Decimal(shape['price'])):
                return False
            leaves = order.quantity.as_decimal() - order.filled_qty.as_decimal()
            if not leaves.is_finite() or leaves <= 0:
                return False
            reserved += leaves
        if reserved > abs(held):
            return False
        if records and strategy._owned_reduce_capacity(strategy.config.btc_id, next(iter(native.values())).side) is None:
            return False
        return runtime.native_revision() == revision and strategy._owned_chain_current()

    def _entries_enabled(self):
        try:
            self._refresh_warmup_readiness()
            self.strategy._validated_live_money()
            if self.input_readiness:
                require_profile_deposit_parity(self.profile, self.strategy.deposit_projection())
            return (self.state.entry_control_state() != "PAUSED" and self.gate.attachable
                    and self.node.is_running() and self.strategy.recovery_confirmed
                    and self.strategy.deposit_projection()["state"] == "ARMED"
                    and self.state.health(time.time_ns()).safe_for_increase
                    and all(row["state"] == "READY" for row in self.feed.status(time.time_ns()).values()))
        except Exception:
            return False

    def status(self):
        return {"instance_id": self.instance.instance_id, "mode": "live", "environment": "mainnet",
                "profile": self.profile,
                "state": "PUBLIC_FEEDS_READY" if self._entries_enabled() else "RECOVERY_REQUIRED/PAUSED",
                "orders_enabled": self._entries_enabled(), "live_order_capability": not self.manage_only_readiness,
                "recovery_required": not self.strategy.recovery_confirmed,
                "recovery_capability": "MANAGE_ONLY_PREPARATION_NO_ORDER_AUTHORIZATION" if self.manage_only_readiness else "MANUAL_CLEAN_FLAT_ONLY", "feeds": self.feed.status(time.time_ns()),
                "warmup": {"state": self.warmup_state, "rows": self.warmup_bundle.rows},
                "prime_error": self.prime_error,
                "signal_seal": {"state": self.gate.approval_state, "strategy_sha256": self.gate.strategy_code_hash},
                "margin_policy": "NATIVE_SELECTED_ACCOUNT_CROSS_MARGIN",
                "accounting": "NATIVE_ACCOUNT_AND_CONFIRMED_INFO_NO_MODEL_FX"}


class LiveWorker:
    deposit_control = TestnetWorker.deposit_control

    def __init__(self, environment=None):
        environment = os.environ if environment is None else environment
        self.instance = load_testnet_instance_config(Path(environment["COINMASTER_HL_LIVE_INSTANCE_CONFIG"]))
        root = Path(__file__).resolve().parents[2]
        fingerprints = root / "configs/hl-stageg-live.account-fingerprint.json"
        self.candidate=load_candidate(self.instance.strategy_config)
        selected_profile=load_live_profile(root,self.candidate.candidate)
        self.order_approval=require_live_order_approval(Path(environment.get('COINMASTER_LIVE_ORDER_APPROVAL','/etc/coinmaster/live-order-approval.json')),fingerprints,root,profile=selected_profile)
        self.release_identity = json.loads((root / "live-release.json").read_text())
        self.master_address_sha256 = json.loads(fingerprints.read_text())["master_address_sha256"]
        self.candidate = load_candidate(self.instance.strategy_config)
        self.run_epoch = uuid.uuid4().hex
        self.control_available = bool(environment.get("COINMASTER_HL_STAGEG_CONTROL_TOKEN"))
        self._warmup_thread = None
        self._warmup_refresh_after = 0
        self.runtime = PaperRuntime(self.instance.state_db, self.instance.instance_id, int(120e9), require_native_cash=True)
        self.runtime.acquire()
        self.recovery_marker = self.instance.state_db.parent / "manual-recovery-required"
        try:
            profile=load_live_profile(root,self.candidate.candidate)
            manage_preparation=profile.get("input_readiness",False) is True
            if self.recovery_marker.exists() and not manage_preparation:
                raise RuntimeError("LIVE_RESTART_MANUAL_RECOVERY_REQUIRED")
            # Even a flat native cache cannot erase a previous episode or ambiguous result.
            identity = json.loads((root / "live-release.json").read_text())
            if not manage_preparation:
                self.runtime.prepare_flat_epoch(release_commit=identity["source_commit"])
            elif self.runtime.strategy_checkpoint() is None and profile.get('initialization_intent')!='INITIALIZE_FRESH_C1_EPOCH':
                raise RuntimeError("MANAGEMENT_POLICY_LOAD_REQUIRED")
            from coinmaster.ops.stage_g_refresh import refresh_stageg_warmup
            refresh_stageg_warmup(self.instance.signal_warmup_manifest.parent.parent)
            self.native = HyperliquidLiveNode(
                instance=self.instance, candidate=self.candidate.candidate, state=self.runtime,
                credential_path=Path(environment["CREDENTIALS_DIRECTORY"]) / "connection.json",fingerprint_path=fingerprints,order_approval=self.order_approval,
            )
        except BaseException:
            self.runtime.close()
            raise

    def refresh_warmup(self):
        if time.monotonic() < self._warmup_refresh_after or (self._warmup_thread and self._warmup_thread.is_alive()):
            return
        self._warmup_refresh_after = time.monotonic() + 900
        def refresh():
            from coinmaster.ops.stage_g_refresh import refresh_stageg_warmup
            try:
                refresh_stageg_warmup(self.instance.signal_warmup_manifest.parent.parent)
            except Exception:
                # The native admission gate keeps stale/invalid history closed.
                pass
        self._warmup_thread = threading.Thread(target=refresh, name="hl-live-public-warmup", daemon=True)
        self._warmup_thread.start()

    def start(self):
        self.native.start()

    def poll(self):
        self.runtime.heartbeat(time.time_ns())
        if getattr(self.native,'input_readiness',False):
            self.native.loop.call_soon_threadsafe(self.native.strategy.request_live_input_observation)
        if not self.native.strategy.recovery_confirmed:
            return
        try:
            money = self.native.strategy._validated_live_money()
            revision = self.runtime.native_revision()
            if money.native_revision != revision:
                self.native.loop.call_soon_threadsafe(self.native.strategy._request_live_refresh)
                return
            positions, orders = self.native.native_snapshot()
            committed = self.runtime.snapshot(ts_ns=time.time_ns(), positions=positions, orders=orders,
                                  funding_event_ids=self.runtime.funding_event_ids(), reconciled=True,
                                  expected_revision=revision, native_account_total=str(money.raw_usd),
                                  strategy_restartable=self.native.strategy_restartable(), run_epoch=self.run_epoch)
            if not committed:
                self.native.loop.call_soon_threadsafe(self.native.strategy._request_live_refresh)
                return
            self.runtime.record_native_equity_observation(run_epoch=self.run_epoch, observed_at_ns=time.time_ns(), equity_usdc=str(money.equity))
        except ValueError as error:
            if str(error) in ("LIVE_MONEY_STALE_OR_UNKNOWN","LIVE_MONEY_REFRESH_PENDING"):
                self.native.loop.call_soon_threadsafe(self.native.strategy._request_live_refresh)
                return
            self._manual_recovery()
        except Exception:
            self._manual_recovery()

    def _manual_recovery(self):
        self.native.strategy.recovery_confirmed = False
        for client in self.native.node.kernel.exec_engine._clients.values():
            fail = getattr(client, "_cm_fail", None)
            if callable(fail):
                fail("LIVE_WORKER_SNAPSHOT_FAILED")
        # Minimal process/restart latch, deliberately no automatic clearing.
        with self.recovery_marker.open("w") as stream:
            stream.write("LIVE_WORKER_SNAPSHOT_FAILED\n")
            stream.flush()
            os.fsync(stream.fileno())
        directory = os.open(self.recovery_marker.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def projection(self):
        self.poll()
        status = self.native.status()
        positions, orders = self.native.native_snapshot()
        events, cursor = self.runtime.projection_events(100)
        account = {}
        strategy=self.native.strategy
        basis=strategy.config.live_equity_basis
        try:
            if strategy._input_readiness_preparation:
                equity=strategy._validated_live_deposit_equity()
                observation=strategy._last_live_input_observation
                total,free,hold=equity,observation.free_collateral,observation.margin_used
            else:
                money=strategy._validated_live_money()
                total,free,hold=money.equity,money.free_collateral,money.margin_used
            account=dict(equity=str(total),reported_total=str(total),native_cash=str(total),
                native_free=str(free),available=str(free),free_collateral=str(free),
                native_locked=str(hold),locked=str(hold),hold=str(hold),margin_used=str(hold),
                currency='USDC',money_currency='USDC',equity_basis=basis,
                margin_basis='HYPERLIQUID_SPOT_USDC_HOLD_PROXY_NOT_LIQUIDATION_MM_V1' if strategy._live_account_mode=='unifiedAccount' else 'CLASSIC_PERPS_MARGIN_USED',
                reason=None,**self.runtime.funding_projection())
        except (ValueError,RuntimeError):
            status["orders_enabled"]=False
        capital=strategy._live_c1_input
        checkpoint=strategy._c1_checkpoint
        c1=None if capital is None or checkpoint is None or checkpoint['epoch']!=capital.fill_epoch else dict(
            state=(strategy._c1_state or {}).get('state','IDLE'),
            E=str(checkpoint['E']),H=str(checkpoint['H']),DD=str(checkpoint['DD']),cushion=str(checkpoint['C']),
            source_available_ns=checkpoint['source'],decision_ns=checkpoint['receipt'],
            currency='USDC',equity_basis=basis,rights=strategy._c1_rights())
        protection={**strategy.deposit_projection(), 'currency':'USDC',
            'retained_equity_floor_fraction':'0.45','high_water_basis':'INITIAL_AND_HIGHER_VALID_UTC_DAILY_CLOSE'}
        return {**status, "version": "hl-stageg-live-projection-v1", "run_epoch": self.run_epoch,
                "observed_at_ns": time.time_ns(),
                "release_commit": self.release_identity["source_commit"],
                "master_address_sha256": self.master_address_sha256,
                "real_order_approval": self.order_approval.get("orders_approved") is True,
                "native_thread_alive": bool(getattr(self.native, "_thread", None) and self.native._thread.is_alive()),
                "money_currency":"USDC","equity_basis":basis,"c1":c1,
                "account": account, "account_state": "CURRENT" if account else "UNAVAILABLE", "positions": positions, "orders": orders, "events": events, "event_cursor": cursor,
                "deposit_protection": protection,
                "entry_control": {"state": self.runtime.entry_control_state(), "capability": "READY" if self.control_available else "UNAVAILABLE"},
                "provenance": "NATIVE_MAINNET_OWNED_ACCOUNT"}

    def close(self):
        if self.native.stop():
            self.runtime.close()


def main():
    worker = LiveWorker()
    server = create_status_server(worker, int(os.getenv("COINMASTER_HL_STAGEG_STATUS_PORT", "18185")), os.getenv("COINMASTER_HL_STAGEG_CONTROL_TOKEN"))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    try:
        worker.start()
        while not stopped.wait(5):
            worker.refresh_warmup()
            worker.poll()
    finally:
        server.shutdown()
        server.server_close()
        worker.close()


if __name__ == "__main__":
    main()
