# Live-82 bounded money/order review

Source: preserved WIP `68118763f55523f7a135c9a1069d3ff3bac83f5f` versus `8113501`. HEAD remained 6811876 during review. Read-only source inspection; no tests, engines, connections, deploys, real orders, or secret contents read. This report is the reviewer's only write. Native acceptance is owned by the engine executor and is not attested here.

## P1: enforce initial 82 on authoritative first bootstrap

`runtime/coinmaster/ops/hl_live_execution.py:716-719` checks first-bootstrap equity only when `runtime.flat_epoch_balance` exists. A fresh journal returns None (`hl_live_epoch.py:22-26`). The worker checks 82 through a preliminary credential Info lookup (`hl_live_worker.py:99-102`), but the later converged native receipt can have changed equity and still release recovery. Thus preflight82 -> bootstrap83 can initialize deposit protection on unapproved initial capital and enable sizing. The same race on an owned-history restart is correctly rejected by the new guard.

Minimal correction: freeze expected startup equity to owned-flat balance or Decimal("82"), and require exact authoritative candidate_money.equity parity for every first bootstrap. Tests: preliminary82/native82 passes; preliminary82/native83 rejects before recovery_confirmed/DP initialization; owned-flat91.227/native91.227 and65.04/native65.04 pass, mismatches reject.

## Other inspected boundaries

- Exact profile seals candidate and strategy/domain bytes; observed hashes match frozen sources. Original EMA34, cap30m, TP fractions, SOL H preserved; approved repair/selective/direction flags only; drawdown/risk variants default off. Direction implementation is fixed5.5 long/7.875 short.
- Approval now requires82, release, candidate, strategy, profile and master fingerprint; validation precedes worker credential/client construction. Technical profile does not itself authorize orders.
- Warmup override replaces the Sandbox approval identity after live seal validation, retains ready-history/public-margin checks, and _entries_enabled retains current money, native health/recovery, feed and deposit checks. Actual live margin/equity/USDC/native-account parity is enforced independently.
- Flat epoch preserves original checkpoint, fills, journal, snapshot and DP state in SQLite plus attempted-transition audit. It filters terminal history only after coherent revision/flat snapshot/pending/ownership checks. Native bootstrap still rejects cache orders, open positions, fresh-window unknown or foreign fills, incomplete receipts and changed owned-flat balance. No recovery of open exposure or reconciliation shortcut identified in this diff.
- Added selective checkpoint fields contain encodable primitive/Decimal/Intent/set/dict values in real producers inspected; native reference price is converted to Decimal. The focused roundtrip test alone is not native acceptance.
- DP uses the existing account-scoped authoritative equity reader and preserved durable state; native reduce-only IOC exits remain configured.

Decision: correction required for the single P1 above, followed by bounded changed-reason review. No P0 or other actionable P1 found in this scoped pass. Not an approval for live orders, deployment, or broad source safety.

## Final bounded changed-diff confirmation

Reviewed only bootstrap correction, completed forced-close marker retirement, and new inactive staging helper. Source remains HEAD68118763f55523f7a135c9a1069d3ff3bac83f5f plus working-tree changes identified below. No tests rerun or native acceptance claimed.

- Original P1 resolved: first authoritative bootstrap now always compares equity to the owned-flat balance or strategy.active_seed (production credential-verified82). Changed bootstrap equity rejects before recovery release.
- Completed-marker retirement preserves all prior flat snapshot/revision/all-TERMINAL/ownership guards. It permits only known BTC/SOL instrument markers with an owned reduce-only FORCED_CLOSE whose native fill quantity equals full positive order quantity. Any active reason/intent/pending/order blocker still rejects; original checkpoint remains audited and unmodified. No held-position rewrite.
- Inactive staging helper has no worker start/connect or approval creation. It uses the qualified wheel hash/venv, committed clean source, exact profile/file identity, immutable release directory; optional atomic pointer selection rechecks inactive unit/MainPID0 and validates a SQLite backup through epoch guards. Original journal/DP/checkpoint remain untouched. This is source review of inactive selection, not deployment or real-order authorization.
- P2 availability note sent to engine: marker evidence calls native_fill_details() with default first100 rows, so a completed close after100 fills cannot be proven and valid restart fails closed. Use complete durable fill details/pagination. This does not permit unsafe restart.

Decision: GO on scoped money/order safety after bootstrap correction; no remaining P0/P1 in these changed reasons. Native proof status belongs to executor. Complete-fill evidence P2 correction remains tracked with executor.

Reviewed working-file SHA256:
- hl_live_execution.py:297d878dd4ecd74b45912db917ccf3219cb211f276d4eee5f88e591d1ed67a63
- hl_live_epoch.py:1b1b2c00f4f5bd1fb022eefbd932bea31ead2918dabdf8ac1e118444b0870521
- stage_live82.py:ba5d76aac8b84b0fab62a2f214fed0202c07e43ba5808f55c5fb1c787d6b7cb3

## Final special-close correction confirmation

Bounded follow-up covers only RecoverableWaveOverlayStrategy.on_order_filled special-close wrapper and complete forced-close fill-evidence read. HEAD remains68118763f55523f7a135c9a1069d3ff3bac83f5f plus frozen working files. No test reruns or new native acceptance attestation.

GO: no P0/P1 identified in these changed hunks. Special-order map membership is captured before the base callback can clear it. A new special fill requires exactly one owned submission matching instrument and reduce-only before base processing; after base updates close state, the wrapper requires the actual native fill detail matching trade/order/instrument/quantity and commits the applied trade ID together with the resulting checkpoint. In-process duplicates retain the existing _seen_trade_ids early return; already-applied IDs are not recommitted. Invalid ownership/detail evidence fails closed, and the atomic commit conflict revokes recovery. Native journal facts/fees remain produced by the base callback; no synthetic fill or PnL path is added.

P2 first100-fill limitation is resolved: marker evidence now queries all quantities for the exact owned client-order/instrument directly from durable SQLite. Existing all-terminal/flat/revision/no-active-decision gates remain intact.

Reviewed final working-file SHA256:
- strategy/live_recovery.py:0c702dfda60f47b5d26e4c250226135bfd670fb401dadc11adbdbbd2260b42bd
- ops/hl_live_epoch.py:9793f97424e01a28d13b9fc685b4ec0df5ce2e896d483908c5b6de44ce77364a

Prior bootstrap P1 remains resolved. This source confirmation does not authorize worker activation or real orders; executor owns the ongoing native-test result.
