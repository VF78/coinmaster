# Native currency MODEL smoke — STATIC ONLY

File: `runtime/tests/e4_c1_live_native_acceptance_currency_model.py`.
Static SHA256: `630471a1b9705ee8e5d31f85be64151f03a08768e611f49357758235fa99f7fa`.
Actual public production API: `coinmaster.ops.hl_unified_instruments.normalize_unified_pyo3_instrument(instrument)`.
Provider source: `runtime/coinmaster/ops/hl_unified_instruments.py` (frozen product268361712edc9412e2b026a353dedb311818149e; product peer pending).

`ROOT_MODEL_GO=False`. No imports, native constructors or execution occurred. Standard-library AST/compile PASS; no Node/Engine call sites or top-level native imports. This is separate from the three physical Node attempts: root allocated ONE future engine-free model execution only, after final source/fixture peer/freeze/GO. Model allocation spent0; Node attempts spent0.

Raw BTC/SOL stock reference preserves default `*-USD-PERP.HYPERLIQUID` IDs, USD quote, USDC settlement, min notional10 USD, zero stock margin/fee rates. Public PyO3 `from_dict` receives the public legacy serialization; the ACTUAL production normalizer creates release instruments. Public legacy `from_dict` consumes normalized public PyO3 serialization. No normalization is copied into the fixture.

Assertions preserve IDs, ticks, lots, minimum quantities and zero rates; release quote, cost currency and min-notional denomination must be USDC, with numeric minimum10 unchanged. Raw BTC negative reference proves USD cost/PnL/helper commission and USDC fee not reflected in raw realized PnL. It is recorded EXPECTED_LIMITATION and never used as production money authority.

Positive cases are BTC LONG and SOL SHORT. Each has positive/negative native unrealized PnL, one partial close, native `MarginAccount.calculate_pnls`, and actual USDC commissions deducted by native Position. Native helper zero margin/fee amounts retain USDC denomination; zero rates do NOT authorize buying power. Reported AccountState USDC total100/locked30/free70 and event identity remain unchanged; the model does not post cash.

At most64 explicitly created/adopted native model objects are bounded by a runtime counter. Static count:22 shared models/identifiers/values (including3 UUID4 event IDs and3 common tick-valid reference Prices) +24 BTC (including raw negative reference and helper checks) +18 SOL =64. Capacity is reserved BEFORE each constructor/native model-returning helper; object65 cannot be constructed first. No claim counts implicit module globals or native implementation allocations. No TradingNode, engine, matcher, external connection, key access, fake FX, private cache mutation or numeric-only currency acceptance. Socket connect is hard denied. The model imports stock model APIs plus the actual production provider helper; it imports no pytest module.

Root approval JSON before the single execution must contain:

```json
{"kind":"E4_C1_ENGINE_FREE_CURRENCY_MODEL","status":"RUNNING","execution_limit":1,"model_object_limit":64,"source_commit":"FINAL_REVIEWED_SOURCE","fixture_sha256":"630471a1b9705ee8e5d31f85be64151f03a08768e611f49357758235fa99f7fa","allocation_path":"CANONICAL_ROOT_P/currency-model-allocation.json","artifact_dir":"APPROVED_CANONICAL_PRIVATE_MODEL_ARTIFACT_DIR"}
```

The script verifies the actual provider file against that commit, binds both canonical root allocation path and approved artifact directory, and atomically creates `currency-model-allocation.json.execution.claim` NEXT TO THE ROOT ALLOCATION before importing native code. Changing artifact directories cannot create another claim. An existing claim prohibits another execution. After importing the production helper, its resolved __file__ and bytes must match the pinned checkout source BEFORE any model construction; a stale installed module is rejected. Root records any failure as the allocated execution; no automatic retry.

Command specification, NOT executed:

```sh
PYTHONPATH=runtime "$QUALIFIED_PYTHON" runtime/tests/e4_c1_live_native_acceptance_currency_model.py --source "$FINAL_REVIEWED_SOURCE" --approval-file "$ROOT_P/currency-model-allocation.json" --artifact-dir "$PRIVATE_MODEL_ARTIFACT_DIR"
```

Before GO: rebase test-only files onto FINAL Unified+provider source; focused peer checks actual serialization API, object plan and cash/currency assertions; freeze exact fixture SHA; root alone clears the model guard and issues the matching allocation. Node A/B guards remain FALSE until a real component model PASS and final Node casemap review. This preparation claims neither model PASS nor native/venue readiness.
