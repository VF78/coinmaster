# COMBO: independent audit of existing native outputs

COMBO completed with TOTAL 5446657.63139715. It misses the working floor by 23738.883590197 and is not selected. Settled and coherent event DD are both 51.80315157406654834417870238%; strict 50% still fails. Original S0 net-profit retention is 89.60872814%. Native liquidations are zero and terminal positions/orders are flat. This audit ran no engine, tests, or downloads.

This is the preselected native combination of restore DD 40% and BTC quarter cuts, preserving SOL half cuts. Its config hash is 75ca9ae18b7f6be31871e8062bc7f4354cf726abbe5b136d1480201ba632a7ba. It has its own native capital, quantities, funding, fees and admission path.

## Causal prefix against R

Before the first changed BTC cut at 2025-06-06 09:22 UTC, COMBO matches R on 227 native fills across 17 economic fields and 400880 complete settled rows. At that timestamp COMBO actually cuts 6.019 BTC at 103680 with fee 343.227456; R cuts 12.038 BTC at the same price/time with fee 686.454912. The first different settled receipt is 09:23 UTC: COMBO cash 378453.95883639 versus R 364282.98173039; marked equity 336972.51558639 versus R 336628.68623039.

The earlier January restore remains the actual R behavior: 1000 SOL at 177.35 on January 13 at 20:01 UTC. Both policies' January trough precedes this restore. The worst event peak joins sequence 579557 to January 13 00:36 UTC, equity 161044.59427091; trough sequence 582080 joins to 14:36 UTC, equity 77618.41899891; recovery sequence 598415 joins to January 17 09:07 UTC. Sequence indices are explicitly joined to actual event timestamps, not interpreted as Unix nanoseconds.

## Independent native accounting

All 108 unique native lifecycles are closed: 83 BTC and 25 SOL. Composite lifecycle identity has no duplicates; native event counts sum to all 539 fills. Independent native realized PnL sums to 5386454.47311780. Native lifecycle commissions sum to 700929.08118228 and exactly match fill fees; commissions are already included in realized PnL.

Separately, 539 native PRE/POST fill cash pairs and 1248 funding pairs form a complete exact cash chain. All 2105975 physical snapshots were checked. All 1787 physical cash changes are owned; missing and duplicate mutation pairs are zero. The 1051199 retrospective settled watermark copies are excluded from physical mutation counting. Both the lifecycle and observed cash identities close:

`10000 + 5386454.47311780 + 50203.15827935 = 5446657.63139715`, residual `0E-8`.

Actual signed funding is 41314.31237459 for BTC and 8888.84590476 for SOL. All 1248 unique event/instrument records agree across report, SQLite funding cash table, original journal after-total, and event trace cash pairs. No bridge is funding, no fee is subtracted twice, and no trade PnL was reconstructed by an alternative simulator.

## Actions and windows

COMBO has five cuts, three restores and two revocations. Its eight intervention fills pay 8617.19813284 in fees on 15667632.9688 turnover. Total portfolio fees are 700929.08118228, lower than R by 3995.23048144. November's actual BTC cut/restore uses 39.584 BTC at November 27 02:24 and November 29 04:02 UTC; the final cut uses 115.352 BTC at August 10, 2026 16:58 UTC. COMBO-c1-actions.csv contains all actual quantities, prices, fees, order IDs and trade IDs.

| Frozen receipt UTC window | Maximum global settled DD |
|---|---:|
| OCT [2024-10-03, 2024-10-06) | 50.61423369% |
| JAN [2025-01-10, 2025-01-22) | 51.80315157% |
| NOV [2025-10-22, 2025-12-03) | 51.03293697% |
| FINAL [2026-07-06, 2026-09-01) | 47.22439645% |

COMBO improves observed TOTAL over R by 34346.84002582. Standalone Q improved C1 by 411646.82023579, but that amount cannot be added to R: changed quantities, capital and later eligibility interact. This native combination provides the actual result and remains below the floor. No extra combination or threshold search is inferred.

COMBO-months.csv contains all 24 source-quote UTC months; COMBO-windows.csv uses receipt UTC and half-open endpoints. Cash month-end returns and first-to-last settled values are separately labeled; global H never resets. Exact source input hashes and delivered artifact hashes are in COMBO-analysis-input-hashes.json and COMBO-artifact-hashes.json. Existing Q/R artifacts and original COMBO results remain unchanged. Private account details are excluded.
