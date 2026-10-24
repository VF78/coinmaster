# CM05 native event reconstruction proof

2026-09-26. Restricted disposable native Sandbox proof on pinned Nautilus 1.231.0; no production runtime hook, deployment, service action, real exchange client/order, host migration, rc5, or second accounting engine.

## Decision

Native factual-fill reconstruction is feasible for the tested BTC market-entry / independent reduce-only post-only limit-TP configuration. The earlier blanket no-go is narrowed: complete historical market-input replay is not required for this fixture. This is NOT production restart acceptance or proof for all matcher/order configurations.

The native boundary is MessageBus endpoint `ExecEngine.process`, intercepted with supported `deregister/register` before `LiveExecutionEngine.process` enqueues an order event. The test copies the native event plus its original `OrderInitialized` definition; crash runs append the record and SHA-256, flush and fsync before forwarding. Native account events are observed after derivation for evidence, not reapplied as a second economic source. The fixture uses a fixed original account seed, instrument order, native fee model, model USD/USDC FX and a single known boundary quote.

A fresh native TradingNode/Sandbox uses OrderUnpacker for original order definitions, original OrderSubmitted events, `exchange.get_matching_engine(...).accept_order` for recorded acceptance, and `fill_order` with recorded quantity/price/liquidity/position facts at the recorded TestClock time. All fee, cash, margin and position calculations remain native. It reconstructs from inception of this short event history; it does not inject a prefilled cache order into an empty matcher. Native generated event UUIDs are not asserted identical. Native client/venue/trade IDs, fill timestamps/economics, order quantities/status and balances are asserted identical.

## Evidence

`runtime/tests/test_hl_sandbox_factual_reconstruction.py` creates no real data/execution client. Four tests cover the uninterrupted comparison plus SIGKILL before partial-fill append, after fsync/before native delivery, and after native application. Each crash prefix is reconstructed twice into independent fresh nodes. Incomplete last records and checksum-corrupt records reject before node creation.

- Entry 0.03 BTC at 60000, fee 0.81 USDC.
- Recorded TP partial fill 0.005 at 60010, fee 0.0450075 USDC.
- Restored open quantity / TP leaves: 0.025 / 0.025; TP PARTIALLY_FILLED.
- Native total/free/locked: 9999.1949925 / 9998.7249925 / 0.47 USDC.
- Next quote gives HOLD_WORKING_PARTIAL_TP; next 0.025 trade closes once, three total fills, final native cash/free 9999.219955, locked zero.
- Kill before append restores the earlier committed 0.03 position and ACCEPTED TP. The uncommitted native matcher mutation is discarded; the next 0.025 trade leaves 0.005 open. This rule is local Sandbox-only, never permission to discard an exchange fill.

Disposable precursor: four tests passed in 89.51 seconds. Final checked-in test additionally checks the native next strategy HOLD decision: `PYTHONPATH=.:tests .venv/bin/python -m pytest -q tests/test_hl_sandbox_factual_reconstruction.py` from runtime passed 4 tests in 89.49 seconds. The canonical test interpreter reports 1.231.0.

## Limits / next integration contract

The journal here is test-only: no durable directory/manifest/root hash, sequence-chain/gap detection, power-loss/VPS reboot proof, disk failure fencing, production ingress ownership, cancellation/replacement replay, funding postings, stochastic/queue-state model, bar-generated ID-counter handling, or full sealed strategy state/outbox recovery. Partial-line/hash rejection does not detect deletion of an entire valid trailing record. Repeated reconstruction is tested; crash during recovery itself is not. Fixed asyncio waits schedule this bounded fixture and are not a production completion barrier. The test supplies strategy step and latest quote context; production must persist/reconcile those facts, configuration identities and command intents without duplicating strategy decisions.

One production node can share a recovery supervisor and durable command/native-event journal. Planned restart, disconnected/reconnected feed and crash must all enter RECOVERING, fence new exposure, restore/reconcile, compare economic/order identity invariants, and only then resume. Sandbox reconstruction uses committed native local facts and refreshed market context; never interpret a fresh empty cache as flat. Offline virtual fills are not invented.

Live Hyperliquid uses authoritative venue account, positions, open orders and fills (native adapter report/reconciliation APIs) against durable client IDs and pending intents. It must not replay Sandbox fills into live holdings or resend uncertain orders blindly. Venue-side TP persists independently; account/fill reconciliation and fresh data are required after reconnect/reboot. Live access remains read-only until separately authorized. This test does not authorize or accept production activation.

## Production cutover gate checked 2026-09-26

The checked-in event fixture proves only a fixed native event prefix after a manually controlled startup. It does not establish a production recovery cutover. In pinned Nautilus 1.231, SandboxExecutionClient.connect subscribes to the live Hyperliquid data topic and its on_data method directly advances the SimulatedExchange matcher. The current TradingNode starts public data, the sealed WaveOverlay strategy, and execution in one kernel lifecycle. Trader.add_strategy refuses late attachment to a running trader without a controller. Although the matcher can be constructed before node start by adding its instrument, this does not prove that LiveExecutionEngine and strategy state can be replayed then activated without racing public ingress.

The earlier pinned dispatch probe showed that LiveDataEngine.process returns before downstream decisions/fills and that its queue join cannot serve as a completion barrier. There is no supported input-scoped transitive completion receipt across the data, risk, execution, MessageBus and clock paths. A pre-ExecEngine.process append cannot by itself prove that an in-flight strategy decision, durable intent, matcher fill and domain checkpoint form one recoverable prefix at startup or reconnect. The current production sink also persists intent metadata without the full OrderInitialized definition or a strategy checkpoint, and the running BTC/TP predates any native event journal. Installing only the native-event capture would therefore falsely advertise production recovery. No production hook, strategy seal, installed release, worker or service was changed in this gate check.

Next proof must establish a feed-isolated native replay phase and a bounded cutover that rejects untracked in-flight work, or compare a native BacktestEngine streaming host with an ordered input journal. Either path must include the actual sealed strategy/domain state, exact order identities, native account digest, repeated crash recovery and corrupt-prefix rejection before source integration.

## Disposable native streaming host comparison, 2026-09-26

Test-only runtime/tests/test_hl_backtest_streaming_recovery_probe.py uses pinned BacktestEngine with the same WaveOverlayStrategy subclass, HL BTC/SOL instruments, native SimulatedExchange, native USDC fee model and model FX. It commits each explicit input to a SQLite FULL-synchronous SHA-linked sequence before add_data, then runs streaming=True and clear_data on the same engine. A fresh engine rebuilt from the committed prefix matches the open 0.025 BTC position, partially filled TP with 0.025 leaves, native order/trade IDs, fees and total/free/locked 9999.1949925/9998.7249925/0.47 USDC. A following noncrossing quote gives HOLD_WORKING_PARTIAL_TP in both; the next 0.025 trade closes once with three fills and native total/free 9999.219955 USDC. A mutated input row fails chain validation. Focused test: 1 passed, 4 existing Pandas warnings.

This proves a synchronous native streaming host can make this fixed input prefix and next decision deterministic. It does not establish production public-adapter ingress capture, a durable epoch/seed/config manifest, source-wide strategy checkpoint, SIGKILL-before/after-commit replay, funding/cancel/replace coverage, or live Hyperliquid account takeover. The production TradingNode remains unchanged; the installed open BTC/TP remains unrecoverable from its missing prior input stream. A host switch requires the owner's separate decision and an end-to-end crash/restart acceptance before release.
