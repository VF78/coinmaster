from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.adapters.sandbox.factory import SandboxLiveExecClientFactory

from coinmaster.ops.native_paper_node import (
    EXECUTION_FACTORY_ALLOWLIST,
    BYBIT_FUNDING_INTERVAL_NS,
    HYPERLIQUID_FUNDING_INTERVAL_NS,
    FeedBook,
    MAX_DATA_AGE_NS,
    MAX_WARMUP_STALENESS_NS,
    _load_warmup,
    assert_sandbox_only,
    candidate_hash,
    native_paper_node_config,
    NativePaperNode,
    paper_candidate,
    sandbox_cash_posting_supported,
    scrub_private_execution_environment,
)
from coinmaster.ops.stage_g_config import InstanceConfig, load_candidate
from coinmaster.strategy.wave_overlay import WaveOverlayStrategy


def test_native_node_is_public_data_plus_exactly_one_sandbox_exec_factory() -> None:
    config = native_paper_node_config()
    assert set(config.data_clients) == {"BYBIT-PUBLIC", "HYPERLIQUID-PUBLIC"}
    assert set(config.exec_clients) == {"SANDBOX"}
    assert isinstance(config.exec_clients["SANDBOX"], SandboxExecutionClientConfig)
    assert EXECUTION_FACTORY_ALLOWLIST == (SandboxLiveExecClientFactory,)
    assert_sandbox_only(config, EXECUTION_FACTORY_ALLOWLIST)
    with pytest.raises(RuntimeError, match="PAPER_EXEC_FACTORY"):
        assert_sandbox_only(config, ())


def test_private_execution_environment_is_scrubbed_before_public_adapters() -> None:
    environment = {
        "BYBIT_API_KEY": "must-not-reach-adapter",
        "BYBIT_API_SECRET": "must-not-reach-adapter",
        "HYPERLIQUID_PRIVATE_KEY": "must-not-reach-adapter",
        "HYPERLIQUID_WALLET": "must-not-reach-adapter",
        "HYPERLIQUID_TESTNET_PK": "must-not-reach-adapter",
        "UNRELATED": "kept",
    }
    assert scrub_private_execution_environment(environment) == (
        "BYBIT_API_KEY",
        "BYBIT_API_SECRET",
        "HYPERLIQUID_PRIVATE_KEY",
        "HYPERLIQUID_TESTNET_PK",
        "HYPERLIQUID_WALLET",
    )
    assert environment == {"UNRELATED": "kept"}


def test_missing_native_mark_or_funding_is_stale_and_blocks_ready() -> None:
    from coinmaster.ops.native_paper_node import BYBIT_IDS
    from nautilus_trader.model.data import FundingRateUpdate, MarkPriceUpdate, QuoteTick
    from nautilus_trader.model.objects import Price, Quantity

    book = FeedBook(ids=BYBIT_IDS)
    now = MAX_DATA_AGE_NS + 100
    book.quote(QuoteTick(BYBIT_IDS[0], Price.from_str("100.0"), Price.from_str("100.1"), Quantity.from_str("1.0"), Quantity.from_str("1.0"), 1, 1))
    book.mark(MarkPriceUpdate(BYBIT_IDS[0], Price.from_str("100.0"), 1, 1))
    book.funding_rate(FundingRateUpdate(BYBIT_IDS[0], Decimal("0.0001"), 1, 1))
    assert book.status(now)[str(BYBIT_IDS[0])]["state"] == "DATA_STALE"


def test_scheduled_bybit_funding_stays_ready_between_updates_but_expires_after_settlement_grace() -> None:
    from coinmaster.ops.native_paper_node import BYBIT_IDS
    from nautilus_trader.model.data import FundingRateUpdate, MarkPriceUpdate, QuoteTick
    from nautilus_trader.model.objects import Price, Quantity

    book = FeedBook(ids=(BYBIT_IDS[0],))
    next_funding = BYBIT_FUNDING_INTERVAL_NS
    normal_between_updates = next_funding - 1
    book.funding_rate(FundingRateUpdate(BYBIT_IDS[0], Decimal("0.0001"), 0, 0, next_funding_ns=next_funding))
    for now in (normal_between_updates, next_funding + MAX_DATA_AGE_NS + 1):
        book.quote(QuoteTick(BYBIT_IDS[0], Price.from_str("100.0"), Price.from_str("100.1"), Quantity.from_str("1.0"), Quantity.from_str("1.0"), now, now))
        book.mark(MarkPriceUpdate(BYBIT_IDS[0], Price.from_str("100.0"), now, now))
        expected = "READY" if now == normal_between_updates else "DATA_STALE"
        assert book.status(now)[str(BYBIT_IDS[0])]["state"] == expected


def test_hyperliquid_funding_without_next_timestamp_uses_official_hourly_window_then_expires() -> None:
    from nautilus_trader.model.data import FundingRateUpdate, MarkPriceUpdate, QuoteTick
    from nautilus_trader.model.identifiers import InstrumentId
    from nautilus_trader.model.objects import Price, Quantity

    instrument_id = InstrumentId.from_str("BTC-USD-PERP.HYPERLIQUID")
    book = FeedBook(ids=(instrument_id,))
    book.funding_rate(FundingRateUpdate(instrument_id, Decimal("0.0001"), 0, 0))
    for now in (HYPERLIQUID_FUNDING_INTERVAL_NS, HYPERLIQUID_FUNDING_INTERVAL_NS + MAX_DATA_AGE_NS + 1):
        book.quote(QuoteTick(instrument_id, Price.from_str("100.0"), Price.from_str("100.1"), Quantity.from_str("1.0"), Quantity.from_str("1.0"), now, now))
        book.mark(MarkPriceUpdate(instrument_id, Price.from_str("100.0"), now, now))
        expected = "READY" if now == HYPERLIQUID_FUNDING_INTERVAL_NS else "DATA_STALE"
        assert book.status(now)[str(instrument_id)]["state"] == expected


def test_verified_warmup_hydrates_causal_seed_and_default_is_corrected_v0() -> None:
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / "var/data/paper-warmup-manifest.json"
    # This historical checked-in fixture is intentionally no longer current;
    # evaluate it at its final completed daily session to verify its shape.
    bundle, state = _load_warmup(path, now_ns=1_788_220_800_000_000_000)
    assert state == "READY"
    assert bundle is not None and bundle.rows >= 730
    assert bundle.bars[0].available_at == bundle.bars[0].close_time
    assert bundle.bars[-1].close_time > bundle.bars[0].close_time
    assert paper_candidate("corrected-v0").btc_notional_multiplier == 9.0
    assert paper_candidate("research-6.48").btc_notional_multiplier == 6.48
    assert candidate_hash("label-a", paper_candidate("corrected-v0")) == candidate_hash("label-b", paper_candidate("corrected-v0"))
    assert candidate_hash("corrected-v0", paper_candidate("corrected-v0")) != candidate_hash("research-6.48", paper_candidate("research-6.48"))


def test_stale_hash_valid_warmup_fails_closed_before_a_native_node_can_be_ready() -> None:
    path = Path(__file__).resolve().parents[1] / "var/data/paper-warmup-manifest.json"
    bundle, state = _load_warmup(path, now_ns=1_788_220_800_000_000_000 + MAX_WARMUP_STALENESS_NS + 1)
    assert bundle is None
    assert state == "WARMUP_STALE_LATEST_COMPLETED_SESSION"


def test_funding_normalization_uses_stable_settlement_id_and_causal_mark_only() -> None:
    from coinmaster.ops.native_paper_node import BYBIT_IDS
    from nautilus_trader.model.data import FundingRateUpdate, MarkPriceUpdate
    from nautilus_trader.model.objects import Price

    book = FeedBook(ids=(BYBIT_IDS[0],))
    book.mark(MarkPriceUpdate(BYBIT_IDS[0], Price.from_str("100"), 100, 100))
    book.mark(MarkPriceUpdate(BYBIT_IDS[0], Price.from_str("200"), 300, 300))
    book.funding_rate(FundingRateUpdate(BYBIT_IDS[0], Decimal("0.01"), 101, 101, next_funding_ns=200))
    event = book.due_funding(250)[0]
    assert event["event_id"] == f"bybit:{BYBIT_IDS[0]}:200"
    assert event["mark"] == Decimal("100")


def test_pinned_sandbox_live_client_exposes_native_exchange_cash_adjustment() -> None:
    # The LiveExecutionClient has no direct hook, but its public ``exchange``
    # is a SimulatedExchange with the supported native account adjustment.
    assert sandbox_cash_posting_supported() is True


def test_status_exposes_immutable_instance_identity_and_candidate_hash() -> None:
    class _Node:
        def is_built(self): return True
        def is_running(self): return False
    class _Feed:
        native_event_sink = None
        def status(self, _now): return {}

    root = Path(__file__).resolve().parents[1]
    loaded = load_candidate(root / "configs/stage-g-v1.json")
    instance = InstanceConfig(
        instance_id="paper-stage-g", venue="BYBIT", mode="paper",
        strategy_config=loaded.path, state_db=root / "var/paper/test.sqlite",
        trader_id="COINMASTER-PAPER-G", strategy_id="stage-g-v1", order_id_tag="SG",
        path=root / "configs/instance.json",
    )
    native = NativePaperNode.__new__(NativePaperNode)
    native.node, native.feed, native.instance = _Node(), _Feed(), instance
    native.history_state, native.history_ready, native.prime_error = "READY", True, None
    native.strategy, native.strategy_hash, native.warmup_bundle, native.entries_gate = None, loaded.sha256, None, None
    native.candidate, native.submission_sink = loaded.candidate, None
    native.scrubbed_environment = ()
    status = native.status()
    assert status["instance"] == {
        "instance_id": "paper-stage-g", "venue": "BYBIT", "mode": "paper",
        "strategy_id": "stage-g-v1", "order_id_tag": "SG",
    }
    assert status["strategy"]["config_hash"] == loaded.sha256
    actual = native._wave_strategy_config()
    assert actual.strategy_id == instance.strategy_id
    assert actual.order_id_tag == instance.order_id_tag
    assert WaveOverlayStrategy(actual).config.strategy_id == instance.strategy_id


def test_native_sandbox_lifecycle_has_fills_and_finishes_flat() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "coinmaster.ops.native_sandbox_selftest"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "'fills': 5" in result.stdout
    assert "'open_positions': 0" in result.stdout
    assert "'account_report_present': 1" in result.stdout
