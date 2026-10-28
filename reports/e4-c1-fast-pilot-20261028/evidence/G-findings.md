# G: independent audit of existing native outputs

G completed with TOTAL 4482202.31880551, below the working floor by 988194.196181837. It is not selected. Settled and coherent event DD are both 51.80315157406654834417870238%; strict 50% fails. Original S0 net-profit retention is 73.71226752%. Native liquidations are zero and terminal positions/orders are flat. This audit ran no engine, tests or downloads.

G is the standalone C1 global arm: initial arm enabled, consumed by a positive economic claim before submission, rearmed only by fresh DD at or below 35% with no unresolved C1 owner/native inflight order and a new source after any blocked recovery. Per-group credit, single-attempt limits and ordinary exit priority remain unchanged. Config hash: df1c48cd536970122e4335de07840226008e8cb11dceeff7cb71d68494d8ca78.

## First actual difference and arm audit

Before the old C1 cut at 2026-08-10 15:39 UTC, G matches C1 on 526 fills across 17 economic fields and 1020457 complete settled rows. G's actual first admission difference is the preceding 15:38 claim: every other gate is true and global_cut_armed is false. The C1 cut of 203.720 BTC at 64253.2 does not occur in G. G later closes its own full 407.440 BTC through the ordinary REGIME path at August 11 00:00 UTC, price 63946.8.

The first changed settled receipt is August 10 15:40 UTC. G cash is 4795840.38386195 versus C1 4649398.44981475; marked equity is 4517355.14386195 versus 4510155.82981475. These actual observations are not an add-back calculation or a claim that suppressing each cut is profitable.

Native audit records five positive claims and four valid global rearms. Later global-arm denial records cover 2550 receipts, of which 2535 have only the global arm gate false. The remaining 15 also fail parent/competing-owner gates. After the first suppression these are G's own states and changed admission times, not the old C1 quantities or calendar. Five consumes and four rearms imply a disarmed terminal arm by source/audit; c1_terminal_state does not explicitly export the arm flag, so no direct terminal flag is invented.

## Exact native accounting

All 108 unique native lifecycles are closed: 83 BTC and 25 SOL. Native event counts sum to all 537 fills. Independent native realized PnL sums to 4418507.07700471. Native lifecycle commissions sum to 668779.92049538 and equal fill fees exactly; no fee is subtracted twice.

Separately, 537 fill cash pairs and 1248 funding cash pairs form an exact mutation chain. All 2105971 physical snapshots were checked; all 1785 cash changes are owned, with no missing or duplicate pair. The 1051199 retrospective settled copies are excluded from physical mutation counting. Both accounting identities close:

`10000 + 4418507.07700471 + 53695.24180080 = 4482202.31880551`, residual `0E-8`.

Actual signed funding is 44745.91640839 for BTC and 8949.32539241 for SOL. All 1248 unique events agree across report, SQLite cash table, original journal after-total and event cash pairs. No bridge is relabeled funding.

G has five cuts, three restores and two revocations. Its eight intervention fills pay 13353.69392358 on turnover 24279443.4974. Intervention fees are lower than C1 by 17144.34680404, while total portfolio fees decrease by only 2283.45361651. G's observed TOTAL gain over C1 is 93588.93655208; it remains far below the profit floor.

| Frozen receipt UTC window | Maximum global settled DD |
|---|---:|
| OCT [2024-10-03, 2024-10-06) | 50.61423369% |
| JAN [2025-01-10, 2025-01-22) | 51.80315157% |
| NOV [2025-10-22, 2025-12-03) | 47.27309039% |
| FINAL [2026-07-06, 2026-09-01) | 51.68803570% |

The January maximum predates G's first effect. The final window is worse than old C1 despite suppressing repeated cuts. Event sequence indices are joined to actual timestamps in G-analysis.json. G-months.csv contains all 24 months with separately labeled cash and settled bases; global H never resets.

## Additional G combinations

The logical additional-G-arm screen on R and COMBO is a source-bound NO_ACTION_DELTA. All five actual claims remain armed. Before each later claim there is an actual fresh DD35 witness with every prior native order terminal strictly before its source, no open/inflight order or mutation in the source-to-receipt window, and all C1 attempts terminal. The conservative witnesses are October 5, 2024 00:02 UTC; January 13, 2025 15:20 UTC; June 9 21:32 UTC; December 1 15:37 UTC. These dates identify evidence, not new trading signals.

Because G adds only a cut-admission gate and arm/log state, preserves all actual claims, and cannot turn a failed base gate into an admission, the saved financial path remains unchanged by induction under that logical extension. No counterfactual TOTAL is asserted and no native attempt should be spent to rediscover the no-op. The frozen G constructor also explicitly rejects mixed R/COMBO flags with G_STANDALONE_REQUIRES_C1_HALF_RESTORE35. Thus this is an admission screen, not a claim that such mixed configurations currently run; no guard bypass or source change is proposed.

See next-combination-admission.json for the strict zero-order rearm witnesses. Original G data and all existing Q/R/COMBO artifacts remain unchanged. New artifact hashes are in G-artifact-hashes.json. Private account details are excluded.
