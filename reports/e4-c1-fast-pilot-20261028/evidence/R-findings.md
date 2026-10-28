# R: independent audit of existing native outputs

R completed with TOTAL 5412310.79137133, settled DD and coherent event DD both 51.80315157406654834417870238%. It misses the working profit floor by 58085.723616017 and is not selected. It retains 89.04261254% of original S0 net profit. Native liquidations are zero and terminal inventory/orders are flat. This audit started no engine and ran no tests.

R improves observed TOTAL over C1 by 1023697.40911790 and over Q by 612050.58888211. These are comparisons of separate native paths, not additive policy effects. R's config hash is c4b53b97fde42c9f09d1d02e5a96a6c8577b4a5be3182d3c95d21911a115ca1c. The only economic policy change is restore DD 35% to 40% at the closed H4 and fresh quote checks.

## First causal difference

Before 2025-01-13 20:01 UTC, R and archived C1 match exactly on 102 native fills across 17 economic fields and on 194159 complete settled rows. October's restore remains 2024-10-04 12:02 UTC. The first changed action is the January SOL restore: actual R fills 1000 SOL at 177.35, fee 97.5425, at 20:01 UTC; C1 restores at 2025-01-14 04:01 UTC at 184.55, fee 101.5025. The actual native R record confirms the earlier source-bound witness: closed H4 16:00-20:00, close 177.53 above cut VWAP 175.58, fresh quote DD 36.69594603%, native admission passed.

The first changed settled receipt is 20:02 UTC. R cash is 130950.21436636 versus C1 131047.75686636; marked equity is 101390.21436636 versus 101467.75686636. The first immediate equity difference is therefore not presented as profit. Later capital and sizing evolve natively.

The January maximum drawdown already occurred at 14:36 UTC, before this first changed action. Its event peak joins sequence 579557 to 00:36 UTC and equity 161044.59427091; trough sequence 582080 joins to 14:36 UTC and equity 77618.41899891. Event recovery joins sequence 598415 to 2025-01-17 09:07 UTC. These summary timestamp fields are sequence indices; they are not Unix timestamps. Settled receipt availability for a completed source mark is separately named and can be one minute later.

## Two exact native accounting checks

The independent full lifecycle sum has 108 unique closed native lifecycles: 83 BTC and 25 SOL, comprising 106 cache snapshots plus two current cache entries. The original composite identity has no duplicates. Their native event counts sum to 539, matching all native fills. Native realized PnL sums to 5351229.30963637; native commissions sum to 704924.31166372 and match all fill fees exactly. Commissions are already included in realized PnL and are not subtracted again.

The second check uses 539 unique PRE/POST fill cash pairs and 1248 unique PRE/POST funding cash pairs. Every cash-before equals the prior mutation's cash-after, with no missing or duplicate pair. All 2105975 physical snapshots were checked; all 1787 physical cash changes belong to these mutations. The 1051199 retrospective settled watermark copies are excluded from physical mutation counting.

Both independent identities close exactly:

`10000 + 5351229.30963637 + 51081.48173496 = 5412310.79137133`, residual `0E-8`.

Actual signed funding is 42192.63583020 for BTC and 8888.84590476 for SOL. All 1248 unique funding records agree across report cash audit, SQLite cash table, original journal after-total, and native event cash pairs. No bridge is relabeled funding. R's original JSON already contains the complete native lifecycle export and remains unchanged.

## Actions and calendar diagnostics

R has five cuts, three restores and two revocations. The eight intervention fills pay 17006.92024796 in native fees on 30921673.1781 turnover. Intervention fees decrease by 13491.12047966 versus C1, but total portfolio fees increase by 33860.93755183 to 704924.31166372. Actual matched cut/restore pair cashflow before fees is -38322.0088; it is not an amount that can be added back to terminal wealth.

The November BTC restore occurs 2025-11-29 04:02 UTC at 90628.2, versus C1 2025-12-01 04:02 UTC. R restores its own 79.592 BTC, not C1's old quantity. June's cut occurs at 09:22 UTC with 12.038 BTC and the final cut at 2026-08-10 16:57 UTC with 230.705 BTC. These changed quantities and times are actual native path consequences. All eight action records, order/trade IDs and amounts are in R-c1-actions.csv.

| Frozen receipt UTC window | Maximum global settled DD |
|---|---:|
| OCT [2024-10-03, 2024-10-06) | 50.61423369% |
| JAN [2025-01-10, 2025-01-22) | 51.80315157% |
| NOV [2025-10-22, 2025-12-03) | 48.36328673% |
| FINAL [2026-07-06, 2026-09-01) | 47.45992814% |

R-months.csv contains all 24 source-quote UTC months and explicitly separates first-to-last settled values from the original report's cash month-end returns. Global H never resets. R-windows.csv uses receipt UTC and half-open boundaries.

Q changes BTC cut size and first diverges in June; R changes restoration timing and first diverges after the January trough. Both mechanisms have real observed action deltas, supporting an informative preselected combination. A combination still needs its own native capital, quantities, fees, funding, and admission path. Neither mechanism acts before the unchanged January maximum, so Q plus R cannot repair that strict 50% prefix by these changes alone. No combination result is asserted here.

Original R files and existing Q/R evidence hashes were not changed. New evidence includes R-analysis.json, R-months.csv, R-windows.csv, R-c1-actions.csv, R-native-cash-transitions.csv and R-analysis-input-hashes.json. No private account identity, balance, live budget or account history is included.
