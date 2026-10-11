# CM113 four individual V3 risk comparisons

Four sequential native24m engines B25 → S10_15 → R2 → T3 on source `250020911a1ac671740cd3346c27f0235792703c`. Reused V3 TOTAL5437208.56951095/nativeDD67.2863064484%/conditionalbound68.4920098440%. Seed10000/reserve0; identical genuine Bybit [2024-09-01,2026-09-01), fees/funding/margin/execution/cap30m/three repairs/V3direction/SOL H.

**Eligible winner: B25.** Greatest terminal TOTAL among candidates with native global minuteDD<=50. B25 sacrifices55.96152893% of V3 TOTAL; its nativeDD46.48498057% qualifies, while conditionalOHLC59.46109682% remains above50. This is not an intrabar cap guarantee.

| Variant | TOTAL USDT | ROI % | Loss vs V3 % | Native DD % | Conditional bound % | Seed minimum | BTC/SOL fills |
|---|---:|---:|---:|---:|---:|---:|---:|
| B25 | 2394463.52298288 | 23844.635230 | 55.961529 | 46.484981 | 59.461097 | 7385.40871767 | 322/197 |
| S10_15 | 1147671.51274638 | 11376.715127 | 78.892266 | 62.030309 | 68.937141 | 6489.68391849 | 311/135 |
| R2 | 2248382.68295321 | 22383.826830 | 58.648217 | 92.127683 | 94.166853 | 6472.47794826 | 251/151 |
| T3 | 466727.71769381 | 4567.277177 | 91.416042 | 92.780742 | 92.806654 | 1556.27751464 | 339/213 |

All four processed1051200 rows per source/3153600 native observer rows/1051200 strict-later bound samples. Fees/native fills/terminal flat reconciled. JSON retains ACTIVE/reserve, maker/taker fees/notionals, BTC/SOL actual reasons, fundingUNKNOWN, guard/trigger/rearm/protective fill/latency audits and execution diagnostics, exact config differences, input/source hashes and receipts. No additional trace scans.

| Variant | Rank | Native DD % | Peak UTC | Trough UTC | Recovery UTC |
|---|---:|---:|---|---|---|
| B25 | 1 | 46.484981 | 2024-09-11T14:00:00+00:00 | 2024-10-03T15:44:00+00:00 | 2024-10-11T15:15:00+00:00 |
| B25 | 2 | 45.997360 | 2026-05-15T00:34:00+00:00 | 2026-08-18T03:33:00+00:00 | Not recovered by interval end |
| B25 | 3 | 44.965883 | 2025-04-11T01:00:00+00:00 | 2025-09-18T17:13:00+00:00 | 2025-09-22T06:00:00+00:00 |
| S10_15 | 1 | 62.030309 | 2026-07-06T13:39:00+00:00 | 2026-08-18T03:33:00+00:00 | Not recovered by interval end |
| S10_15 | 2 | 60.155879 | 2025-03-25T20:12:00+00:00 | 2025-06-06T15:17:00+00:00 | 2025-08-02T18:15:00+00:00 |
| S10_15 | 3 | 55.834449 | 2025-10-22T21:29:00+00:00 | 2025-11-28T14:28:00+00:00 | 2025-12-01T04:12:00+00:00 |
| R2 | 1 | 92.127683 | 2025-01-13T00:36:00+00:00 | 2025-01-13T14:36:00+00:00 | 2025-01-21T03:11:00+00:00 |
| R2 | 2 | 61.658328 | 2026-03-29T22:50:00+00:00 | 2026-08-19T06:13:00+00:00 | Not recovered by interval end |
| R2 | 3 | 56.666794 | 2024-10-03T04:00:00+00:00 | 2024-10-03T15:44:00+00:00 | 2024-10-04T16:25:00+00:00 |
| T3 | 1 | 92.780742 | 2026-03-02T14:04:00+00:00 | 2026-08-18T03:33:00+00:00 | Not recovered by interval end |
| T3 | 2 | 89.166140 | 2024-09-11T14:50:00+00:00 | 2024-10-03T15:44:00+00:00 | 2024-11-24T12:31:00+00:00 |
| T3 | 3 | 68.107553 | 2025-01-13T00:36:00+00:00 | 2025-01-13T14:36:00+00:00 | 2025-01-14T14:41:00+00:00 |

Actual native risk event counts and trigger-to-execution latency (ns):

- B25: events {"PROTECTIVE_TRIGGER":13,"PROTECTIVE_SUBMIT":13,"PROTECTIVE_FILL":13,"B25_REARM":12}; latency {"PROTECTIVE_SUBMIT":{"count":13,"minimum_ns":0,"maximum_ns":0,"mean_ns":"0"},"PROTECTIVE_FILL":{"count":13,"minimum_ns":0,"maximum_ns":0,"mean_ns":"0"}}
- S10_15: events {"SOL_CYCLE_ANCHOR":26,"PROTECTIVE_TRIGGER":16,"PROTECTIVE_SUBMIT":29,"PROTECTIVE_FILL":29,"SOL_NEW_EPISODE_REARM":9}; latency {"PROTECTIVE_SUBMIT":{"count":29,"minimum_ns":0,"maximum_ns":120000000000,"mean_ns":"31034482758.62068965517241379"},"PROTECTIVE_FILL":{"count":29,"minimum_ns":0,"maximum_ns":120000000000,"mean_ns":"31034482758.62068965517241379"}}
- R2: events {"R2_REGIME_CLOSE_WAIT":44,"R2_REARM":44}; latency {"PROTECTIVE_SUBMIT":{"count":0,"minimum_ns":null,"maximum_ns":null,"mean_ns":null},"PROTECTIVE_FILL":{"count":0,"minimum_ns":null,"maximum_ns":null,"mean_ns":null}}
- T3: events {"T3_TRIGGER":53,"PROTECTIVE_SUBMIT":49,"PROTECTIVE_FILL":49}; latency {"PROTECTIVE_SUBMIT":{"count":49,"minimum_ns":0,"maximum_ns":360000000000,"mean_ns":"105306122448.9795918367346939"},"PROTECTIVE_FILL":{"count":49,"minimum_ns":0,"maximum_ns":360000000000,"mean_ns":"105306122448.9795918367346939"}}

Public reports: [comparison JSON](https://github.com/VF78/coinmaster/blob/codex/nautilus-btc-sol-mvp/reports/v3-risk-four-113/comparison/comparison.json), [CSV](https://github.com/VF78/coinmaster/blob/codex/nautilus-btc-sol-mvp/reports/v3-risk-four-113/comparison/comparison.csv), [hashes](https://github.com/VF78/coinmaster/blob/codex/nautilus-btc-sol-mvp/reports/v3-risk-four-113/comparison/SHA256SUMS).

Limitations:

- All outputs NOT_FAITHFUL_DIAGNOSTIC/ranking_eligible=false; no live or venue-faithful ranking.
- Native minute equity global DD preserves all prior peaks; post-boundary settlement included in TOTAL but excluded from interval DD/seed minimum/TOP3.
- Conditional upper-to-strictly-later-lower bound is separate from observed tick DD and does not guarantee an intrabar50% cap or venue survival.
- Historical execution uses minute closes/cached books, no BBO/L2/tape; protective latency/quotes and audit counters remain diagnostic.
- Signed funding remains UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA; native posting counts are actual, unknown signed amounts are not zero.
- Exactly four individual native engines, separate funding journals, no control/repeat/refinement/grid; reusable V3 defaultOFF/source proof supplied by implementation review.
- Shared900M/swap0, UID994, PrivateNetwork/env-i/read-only binds; original pilotPID2009732/NRestarts0/release81e6318 preserved, no orders/deploy/restarts.
