# Native currency MODEL smoke — STATIC ONLY

File: `runtime/tests/e4_c1_live_native_acceptance_currency_model.py`.
Static SHA256: `e5873af65dd57f15ff0b934d243e969e8441c2a86a8a65935f4c3bcecd931354`.
Actual public production API: `coinmaster.ops.hl_unified_instruments.normalize_unified_pyo3_instrument(instrument)`.
Provider source: `runtime/coinmaster/ops/hl_unified_instruments.py` (WIP API received directly from the source owner; final product commit/peer pending).

`ROOT_MODEL_GO=False`. No imports, native constructors or execution occurred. Standard-library AST/compile PASS; no Node/Engine call sites or top-level native imports. This is separate from the three physical Node attempts: root allocated ONE future engine-free model execution only, after final source/fixture peer/freeze/GO. Model allocation spent0; Node attempts spent0.

Raw BTC/SOL stock reference preserves default `*-USD-PERP.HYPERLIQUID` IDs, USD quote, USDC settlement, min notional10 USD, zero stock margin/fee rates. Public PyO3 `from_dict` receives the public legacy serialization; the ACTUAL production normalizer creates release instruments. Public legacy `from_dict` consumes normalized public PyO3 serialization. No normalization is copied into the fixture.

Assertions preserve IDs, ticks, lots, minimum quantities and zero rates; release quote, cost currency and min-notional denomination must be USDC, with numeric minimum10 unchanged. Raw BTC negative reference proves USD cost/PnL/helper commission and USDC fee not reflected in raw realized PnL. It is recorded EXPECTED_LIMITATION and never used as production money authority.

Positive cases are BTC LONG and SOL SHORT. Each has positive/negative native unrealized PnL, one partial close, native `MarginAccount.calculate_pnls`, and actual USDC commissions deducted by native Position. Native helper zero margin/fee amounts retain USDC denomination; zero rates do NOT authorize buying power. Reported AccountState USDC total100/locked30/free70 and event identity remain unchanged; the model does not post cash.

At most64 explicitly created/adopted native model objects are bounded by a runtime counter. Static count:16 shared models/identifiers/values +27 BTC (including raw negative reference and helper checks) +21 SOL =64. No claim counts implicit module globals or native implementation allocations. No TradingNode, engine, matcher, external connection, key access, fake FX, private cache mutation or numeric-only currency acceptance. Socket connect is hard denied. The model imports stock model APIs plus the actual production provider helper; it imports no pytest module.

Root approval JSON before the single execution must contain:

```json
{"kind":"E4_C1_ENGINE_FREE_CURRENCY_MODEL","status":"RUNNING","execution_limit":1,"model_object_limit":64,"source_commit":"FINAL_REVIEWED_SOURCE","fixture_sha256":"e5873af65dd57f15ff0b934d243e969e8441c2a86a8a65935f4c3bcecd931354"}
```

The script verifies the actual provider file against that commit and atomically creates `currency-model-execution.claim` before importing native code. An existing claim prohibits another execution. Root records any failure as the allocated execution; no automatic retry.

Command specification, NOT executed:

```sh
PYTHONPATH=runtime "$QUALIFIED_PYTHON" runtime/tests/e4_c1_live_native_acceptance_currency_model.py --source "$FINAL_REVIEWED_SOURCE" --approval-file "$ROOT_P/currency-model-allocation.json" --artifact-dir "$PRIVATE_MODEL_ARTIFACT_DIR"
```

Before GO: rebase test-only files onto FINAL Unified+provider source; focused peer checks actual serialization API, object plan and cash/currency assertions; freeze exact fixture SHA; root alone clears the model guard and issues the matching allocation. Node A/B guards remain FALSE until a real component model PASS and final Node casemap review. This preparation claims neither model PASS nor native/venue readiness.
