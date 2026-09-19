from __future__ import annotations

from decimal import Decimal

import pytest
from nautilus_trader.adapters.sandbox.config import SandboxExecutionClientConfig
from nautilus_trader.adapters.sandbox.factory import SandboxLiveExecClientFactory

from coinmaster.ops.native_paper_node import (
    EXECUTION_FACTORY_ALLOWLIST,
    FeedBook,
    MAX_DATA_AGE_NS,
    assert_sandbox_only,
    native_paper_node_config,
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
