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
