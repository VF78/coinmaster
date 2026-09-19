from __future__ import annotations

from decimal import Decimal

import pytest
from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.adapters.sandbox.factory import SandboxLiveExecClientFactory

from coinmaster.ops.native_paper_node import (
    EXECUTION_FACTORY_ALLOWLIST,
    BYBIT_FUNDING_INTERVAL_NS,
    FeedBook,
    MAX_DATA_AGE_NS,
    _load_warmup,
    assert_sandbox_only,
    candidate_hash,
    native_paper_node_config,
    paper_candidate,
    sandbox_cash_posting_supported,
    scrub_private_execution_environment,
)


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
        "UNRELATED": "kept",
    }
    assert scrub_private_execution_environment(environment) == (
        "BYBIT_API_KEY",
        "BYBIT_API_SECRET",
        "HYPERLIQUID_PRIVATE_KEY",
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


def test_verified_warmup_hydrates_causal_seed_and_default_is_corrected_v0() -> None:
    from pathlib import Path
    bundle, state = _load_warmup(Path(__file__).resolve().parents[1] / "var/data/paper-warmup-manifest.json")
    assert state == "READY"
    assert bundle is not None and bundle.rows >= 730
    assert bundle.bars[0].available_at == bundle.bars[0].close_time
    assert bundle.bars[-1].close_time > bundle.bars[0].close_time
    assert paper_candidate("corrected-v0").btc_notional_multiplier == 9.0
    assert paper_candidate("research-6.48").btc_notional_multiplier == 6.48
    assert candidate_hash("corrected-v0", paper_candidate("corrected-v0")) != candidate_hash("research-6.48", paper_candidate("research-6.48"))


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


def test_pinned_sandbox_live_client_has_no_supported_cash_adjustment_hook() -> None:
    # Nautilus 1.231's adapters/sandbox/execution.py exposes submit/cancel and
    # feeds SimulatedExchange, but no LiveExecutionClient.adjust_account API.
    assert sandbox_cash_posting_supported() is False


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
