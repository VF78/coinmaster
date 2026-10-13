# CM113 two independent H1/B1 comparisons

Two sequential native24m engines H1 → B1 on source `94e0e6cecbdef93ed3b1422ecfdffd26d3d936a5`. Reused V3 TOTAL5437208.56951095/nativeDD67.2863064484%/conditionalbound68.4920098440%. Seed10000/reserve0; identical genuine Bybit [2024-09-01,2026-09-01), fees/funding/margin/execution/cap30m/three repairs/V3direction; H1 changes the SOL protection lifecycle; B1 changes BTC entry confirmation.

**Eligible winner: none.** Greatest terminal TOTAL among candidates with native global minuteDD<=50. Conditional OHLC bounds remain separate and do not establish an intrabar cap guarantee.

| Variant | TOTAL USDT | ROI % | Loss vs V3 % | Native DD % | Conditional bound % | Seed minimum | BTC/SOL fills |
|---|---:|---:|---:|---:|---:|---:|---:|
| V3 reused | 5437208.56951095 | 54272.085695 | 0 | 67.286306 | 68.492010 | 4514.69512879 | 311/205 |
| H1 | 190593.96574493 | 1805.939657 | 96.494636 | 62.597829 | 62.846007 | 6555.29021953 | 311/62 |
| B1 | 1387384.71961010 | 13773.847196 | 74.483511 | 64.636948 | 65.704504 | 5344.15904289 | 302/184 |

Both runs processed1051200 rows per source/3153600 native observer rows/1051200 strict-later bound samples. Fees/native fills/terminal flat reconciled. JSON retains ACTIVE/reserve, maker/taker fees/notionals, BTC/SOL actual reasons, fundingUNKNOWN, guard/trigger/rearm/protective fill/latency audits and execution diagnostics, exact config differences, input/source hashes and receipts. No additional trace scans.

| Variant | Rank | Native DD % | Peak UTC | Trough UTC | Recovery UTC |
|---|---:|---:|---|---|---|
| V3 reused | 1 | 67.286306 | 2024-09-11T14:00:00+00:00 | 2024-10-03T15:44:00+00:00 | 2024-10-11T03:24:00+00:00 |
| V3 reused | 2 | 62.252701 | 2025-04-11T01:00:00+00:00 | 2025-06-06T15:17:00+00:00 | 2025-09-22T06:01:00+00:00 |
| V3 reused | 3 | 55.833571 | 2025-10-22T21:29:00+00:00 | 2025-11-28T14:28:00+00:00 | 2025-12-01T04:12:00+00:00 |
| H1 | 1 | 62.597829 | 2026-07-06T13:39:00+00:00 | 2026-08-18T03:33:00+00:00 | Not recovered by interval end |
| H1 | 2 | 53.704105 | 2025-04-11T01:00:00+00:00 | 2025-06-20T08:37:00+00:00 | 2025-08-24T19:38:00+00:00 |
| H1 | 3 | 52.735648 | 2025-11-26T12:22:00+00:00 | 2025-11-28T14:28:00+00:00 | 2025-12-01T15:34:00+00:00 |
| B1 | 1 | 64.636948 | 2024-09-11T14:47:00+00:00 | 2024-10-03T15:44:00+00:00 | 2024-10-11T07:27:00+00:00 |
| B1 | 2 | 63.374919 | 2025-08-24T19:38:00+00:00 | 2025-09-18T17:13:00+00:00 | 2025-09-22T00:34:00+00:00 |
| B1 | 3 | 61.731839 | 2025-04-09T18:24:00+00:00 | 2025-05-23T09:19:00+00:00 | 2025-07-30T19:07:00+00:00 |

Seed minimum UTC: V3 2024-10-03T15:44:00+00:00; H1 2024-09-18T16:05:00+00:00; B1 2024-10-03T15:44:00+00:00. Native engine iterations and delivered4internalMTF bar counts remain UNKNOWN_NOT_EXPORTED; legacy event_count/max_batch_events omit2×1051200 source1mBars and are not fullinputcount.

Actual native risk event counts and trigger-to-execution latency (ns):

- H1: events {"H1_ARM":139,"H1_NATIVE_EXPOSURE":197,"H1_STAGE1":31,"H1_NATIVE_FILL":91,"H1_EXIT":12}; latency {"H1_STAGE1":{"count":31,"minimum_ns":60000000000,"maximum_ns":60000000000,"mean_ns":"60000000000"},"H1_STAGE2":{"count":0,"minimum_ns":null,"maximum_ns":null,"mean_ns":null},"H1_NATIVE_FILL":{"count":0,"minimum_ns":null,"maximum_ns":null,"mean_ns":null},"B1_CONFIRMED_ENTRY":{"count":0,"minimum_ns":null,"maximum_ns":null,"mean_ns":null}}
- B1: events {"B1_ARM":104,"B1_CONFIRMED_ENTRY":104}; latency {"H1_STAGE1":{"count":0,"minimum_ns":null,"maximum_ns":null,"mean_ns":null},"H1_STAGE2":{"count":0,"minimum_ns":null,"maximum_ns":null,"mean_ns":null},"H1_NATIVE_FILL":{"count":0,"minimum_ns":null,"maximum_ns":null,"mean_ns":null},"B1_CONFIRMED_ENTRY":{"count":104,"minimum_ns":60000000000,"maximum_ns":60000000000,"mean_ns":"60000000000"}}

Public reports: [comparison JSON](https://github.com/VF78/coinmaster/blob/codex/nautilus-btc-sol-mvp/reports/h1-b1-113/comparison/comparison.json), [CSV](https://github.com/VF78/coinmaster/blob/codex/nautilus-btc-sol-mvp/reports/h1-b1-113/comparison/comparison.csv), [hashes](https://github.com/VF78/coinmaster/blob/codex/nautilus-btc-sol-mvp/reports/h1-b1-113/comparison/SHA256SUMS).

B1 actual latency coverage104/104 arms/confirmed entries/native BTC parent fills: daily arm→completed confirmation min15m, median45m, mean75m, max285m; confirmation→first executable q0 quote60s, q0→actual native entry fill60s, total confirmation→native fill120s for every entry. Daily arm→actual fill min17m, median47m, mean77m, max287m. Unique episode/intent/native order joins retained; native report float price formatting tolerance<0.0000001 disclosed. Minute proxy timing is not venue latency.

Corrected H1:31 stage1 actual filled parent intents;0 stage2 intents/fills. All31 actual SOL hedges exited before any qualifying native BTC reduction after first SOL fill while the cycle was eligible:12 recovery exits and19 REGIME group closes. No rejection/margin block, no fullrun stage2 sample. The native121minute fixture proved stage2 causality; these historical results do not prove its economic value. Native exposure audits are quantity-change snapshots, not complete per-minute maximum beta exposure.

Initial7360fd0 H1 completed diagnostic and B1 interrupted diagnostic are INVALID_SHARED_SIGNAL_ROUTING and excluded from valid comparisons. Raw artifacts, initial GO, log and stop receipts remain preserved; corrected source94e0e6c has the real native streaming H1stage1/TP/stage2 and B1entry pipeline proof. Exactly two valid corrected fullrun comparisons, plus two invalid initial integration attempts; no optimizer/control/combined/grid.

Limitations:

- All outputs NOT_FAITHFUL_DIAGNOSTIC/ranking_eligible=false; no live or venue-faithful ranking.
- Native minute equity global DD preserves all prior peaks; post-boundary settlement included in TOTAL but excluded from interval DD/seed minimum/TOP3.
- Conditional upper-to-strictly-later-lower bound is separate from observed tick DD and does not guarantee an intrabar50% cap or venue survival.
- Historical execution uses minute closes/cached books, no BBO/L2/tape; protective latency/quotes and audit counters remain diagnostic.
- Signed funding remains UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA; native posting counts are actual, unknown signed amounts are not zero.
- Exactly two corrected valid native engines; initial completed H1 and interrupted B1 integration diagnostics are preserved separately. Separate funding journals, no control/refinement/grid; reusable V3 defaultOFF/source proof supplied by implementation review.
- Shared650M/swap0, UID994, PrivateNetwork/env-i/read-only binds; original pilotPID2009732/NRestarts0/release81e6318 preserved, no orders/deploy/restarts.
