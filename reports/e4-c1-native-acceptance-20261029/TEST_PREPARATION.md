# Connected native acceptance — STATIC PREPARATION ONLY / NOT RUN

Current reviewed product base: `8ef2ece80a4c6dc7a38cb95852d7ff3439da6e75` (fresh INIT peer PASS).
Test-only worktree: `/root/.openclaw/workspace/coinmaster/coinmaster/research-worktrees/e4-c1-native-acceptance-20261029`.
Branch: `codex/e4-c1-native-acceptance-20261029`.
Fixture: `runtime/tests/e4_c1_live_native_acceptance.py`.
Fixture SHA256: `d0692451357f769b0c1de63983b8f7e9b7b29f921a44688126097590206750b6`.

Only the two test-preparation files were rebased from the earlier draft. Product files are untouched. Standard-library AST/compile passed; no native imports, constructors, engines, nodes, account queries or pytest execution occurred. One TradingNode call site exists inside the guarded runtime function; module import/help never imports Nautilus. `ROOT_NATIVE_GO=False` and `UNIFIED_SOURCE_WIRED=False` hard-block before native imports. Native physical attempts spent by this preparation: 0.

## Fresh INIT and public controls

Case A now starts without any checkpoint, initialization marker, DP H or manual strategy H seed. It acquires the real runtime account lease, records the existing accepted pause command, sets the explicit one-time `INITIALIZE_FRESH_C1_EPOCH` intent, binds the production full verifier before native startup, and awaits the verifier task scheduled by the actual merged `on_start`. The verifier calls the real `initialize_clean_flat_c1_epoch(view, *, intent, now_ns, history_anchor_ms)` API. Assertions require actual fresh native flat AccountState, canonical checkpoint, atomic initialization marker, initial C1/Next H=actual native equity100, zero C1 rights/pending, command capability FALSE, and preserved original strict history anchor through `durable_management_scope` before fills. No virtual checkpoint is loaded for virgin A.

Synthetic100 USDC is explicitly tagged `SYNTHETIC_APPROVED_100_USDC_NOT_REAL_BUDGET`; it is not a live capital authorization. Existing profile strategy/source flags are reused.

DP uses the exact production `_validated_live_deposit_equity` provider. The fixture calls the writer's forthcoming public virgin-only `initialize_fresh_live_deposit_protection(idempotency_key)` wrapper, requiring prior H=None/latchFalse/no history and actual prepared native flat equity. That wrapper invokes existing RESET(confirm=True) FIRST, then SET55; it must reject any existing H and never reset it. The wrapper is not yet frozen into8ef; final product integration/review is mandatory before clearing the guards. No direct H initialization or scalar reader swap exists in the fixture.

## Native financial contracts

The existing HL instruments are BTC/SOL USD-quoted and USDC-settled; the fixture asserts both currencies. Native fill events use quote USD and commission USDC. No generic USDT instrument, synthetic FX quote, private cache mutation, custom PnL engine or custom OMS is introduced. Fixed fixture seed commands use the public native Strategy -> RiskEngine -> ExecutionEngine -> FAKE-client route; production order capability stays FALSE.

Scripted financial mode is `unifiedAccount`. Synthetic native AccountState USDC total is the equity basis; native UPNL is diagnostic and is never added to E. Perp money summary is zero; paired spot USDC is the sole balance truth. Final Unified receipt/materializer schema, stock projection parity and budget vector await writer freeze/peer. Classic8ef cannot qualify this mode and must not be run early.

A separate stock5024 gate records actual Position settlement/PnL currency, actual native fill commissions and realized fees, native account initial/maintenance margin and commission helper currencies. It fails explicitly if USD is returned where USDC settlement is required. Tagged1.231 source already shows potential get_cost_currency/quote-currency limitations. These must be classified/resolved by root before native GO; substituting USDT/USDC quote metadata or numeric-only `.as_decimal()` acceptance would hide the issue.

## Finite case map

One runner, two fresh processes, exactly one node per process. A covers real startup minute subscribe/backfill requests; partial IOC; fill during pending cancel and terminal remainder; duplicate native fill; lost ACK UNKNOWN/no resend then actual native terminal; real full owned parity and Strategy.query_account with delayed/new AccountState; stale/revision rejection; DTO native Position.unrealized_pnl; funding dedup without cash posting; DP55 latch at45% retained equity/increase denial; actual native flat after owned reduction; reconnect revocation. Synthetic event injection proves native routing/callback/journal behavior, not venue matching.

B reuses the exact durable case-A checkpoint/marker/SQLite, including H55/latch, C1/Next state, signal cursors and fill IDs. It proves loaded receipt/certificate/freshness invalid, command OFF and no automatic resume. Empty current native cache is not called a new venue-flat proof; actual flat was established by A's native close events. C1 flat history retirement must remain forbidden. Marker reuse and no reinitialization are explicit assertions.

Pure closed-bar aggregation/warmup/cursor arithmetic proofs are not repeated. No benchmark, optimization, warmup trading or open-position crash takeover is claimed.

## Root gates and commands — specification, NOT executed

Final Unified source + public DP wrapper -> fixture re-pin/source review -> exact fixture freeze -> root GO -> root ledger claim -> A -> A PASS -> separately claimed B. Maximum3 physical native attempts TOTAL INCLUDING failures; intended A+B leaves only one corrective attempt. Root owns/finalizes `P/native-engine-acceptance-ledger.json`; the fixture never edits it. Historical closed attempts/budgets are not borrowed.

Ledger schema: `{ "attempts": [...] }`, each claim has `attempt_id`, `case`, `status:"RUNNING"`, `source_commit`, `fixture_sha256`. The runner rejects more than3 entries or a mismatched claim. B requires same-source A PASS. Root records failures/crashes even if no result JSON is produced.

Once all gates are met, use the exact qualified1.231.0 interpreter and final source hash:

```sh
PYTHONPATH=runtime:runtime/tests "$QUALIFIED_PYTHON" runtime/tests/e4_c1_live_native_acceptance.py --case A --artifact-dir "$ARTIFACT_DIR" --ledger "$ROOT_P/native-engine-acceptance-ledger.json" --attempt-id A1 --expected-source "$FINAL_REVIEWED_SOURCE"
PYTHONPATH=runtime:runtime/tests "$QUALIFIED_PYTHON" runtime/tests/e4_c1_live_native_acceptance.py --case B --artifact-dir "$ARTIFACT_DIR" --ledger "$ROOT_P/native-engine-acceptance-ledger.json" --attempt-id B1 --expected-source "$FINAL_REVIEWED_SOURCE"
```

Artifacts must be isolated private test output. No real key/HL execution factory is constructed. Network connection attempts and urllib transport are hard denied; synthetic HTTP edge replacements are counted. Results expose per-gate failures, actual node/query/mutation/network counts, timestamps and source hashes; no native PASS is claimed by this preparation. Production, old Sandbox, real orders/transfers and START remain untouched.
