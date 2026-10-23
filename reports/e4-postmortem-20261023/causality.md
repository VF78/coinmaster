# E4 / residual SOL causality memo — saved evidence only, 2026-10-23

Scope: analysis of existing compact reports/CSVs in the two completed studies. No engine, replay, training, new data or hypothetical portfolio P&L was run. Values below are actual native paths or explicitly labelled arithmetic. Neither pilot nor VPS/product state was inspected or changed. Funding by asset remains UNKNOWN; unallocated cash bridge is not automatically funding.

## What E4 is relative to B and S0

S0 is the saved aggressive control. B changes the post-REGIME re-entry calendar with a WAIT/distance gate. E4 retains B's direction and frozen EMA34/ATR14 distance >=0.5 gate, but permits a qualifying **closed 4h** entry during active WAIT rather than waiting for the next daily decision. It is neither removal of all WAIT nor restoration of S0's calendar. First E4/B divergence occurs only on 2024-10-06 16:02: native E4 1.289 BTC at 62755.4 versus B 2024-10-07 00:01 0.742 BTC. The Oct3 DD therefore predates E4's economic effect. 29 E4 entry intents are not 29 added independent trades.

| Actual recipe | TOTAL | profit retained vs S0 | global settled DD |
|---|---:|---:|---:|
| S0 | 6077107.23887483 | 100% | 66.2569148647% |
| B | 4622034.27336437 | 76.0170224751% | 57.5854104596% |
| E4 | 5631617.35953723 | 92.6572934712% | 57.5854104596% |
| XS=E4+old H1 S | 5406345.11636863 | 88.9442843830% | 58.9474368842% |
| R2C | 2610652.32119763 | 42.8647824870% | 61.7586863916% |

The 90%-profit floor is 5470396.514987347; E4 has only 161220.844549883 terminal headroom over it. B−S0 is −1455072.96551046. E4−B is +1009583.08617286 and E4−S0 is −445489.87933760. E4 recovers about 69.38% of B's terminal shortfall; this is terminal arithmetic, not attribution of individual trades.

The B calendar contains 77 BTC parents versus S0 105; only 51 dates match, 54 original dates disappear and 26 new dates appear. Inside WAIT, 28 historically losing and 22 winning original entries are skipped. Quantity differs in 39/51 matched parents. Thus B's lower turnover is not a clean pruning of bad trades. Matched-parent actual fill-net delta −705981.09 has a symmetric accounting quantity component −709196.21 and unit component +3215.12; those are not isolated causal estimates because capital, caps, split/admission and BTC/SOL sequencing co-move. Early S0 Dec/Jan SOL cycles earned 176722.777176 versus B 49370.3575 before January BTC sizing, giving direct evidence for earlier capital divergence.

Actual E4−B accounting: BTC fill-net +912145.82239455; SOL +81751.32832620; unallocated bridge +15685.93545211. Fees rise +114665.21267926, so E4's gain is participation/path benefit rather than fee saving. December/January first-to-last receipt returns are not restored: E4 +2.15%/+134.19% versus B +7.39%/+135.61%; March2026 improves to +50.09% versus +7.98%. No fixed-state causal attribution of that gain is available.

Sources: [comparison](../b-50-90-next-20261023/comparison.csv), [mechanism/results](../b-50-90-next-20261023/REPORT.md), [B/S0 attribution](../b-50-90-next-20261023/attribution-findings.md).

## E4's actual DD failures, with correct clocks

| E4 global-peak episode UTC | peak equity | trough equity | DD | recovery | gap to half that actual peak* |
|---|---:|---:|---:|---|---:|
| Oct3 2024 04:01→15:45 | 14743.45772484 | 6253.37707805 | 57.5854104596% | Oct4 16:26 | 1118.35178437 |
| Jan13 2025 00:37→14:37 | 174073.90411259 | 84574.29784059 | 51.4147176329% | Jan14 14:42 | 2462.654215705 |
| Oct22 2025 21:30→Nov28 14:29 | 1998630.2254772 | 903525.72689772 | 54.7927517867% | Dec1 03:33 | 95789.38584088 |

*Arithmetic peak/2−actual trough; these are neither executable hedge sizes nor guaranteed savings of a new policy. Do not add gaps to TOTAL.

Oct3 is dominated by SOL long1000 at140.09 versus BTC short0.940 at60887.25. Peak and trough cash are 12526.05072484 and12536.66807805: cash barely changes while the opposing marks produce the tail. SOL later recovers, and the uncut E4 SOL cycle Oct3–5 makes +3214.10099625 ex funding. A stop therefore has a measurable recovery opportunity cost.

January E4 peak/trough are SOL-only4000 at187.23; cash155873.90411259→155854.29784059. XS has the **same**4000SOL and prices at both endpoints, but lower cash133629.51287244→133609.90660044. Its DD is therefore58.9474%, versus E4's51.4147%, without a new January S fill. Old S requires an open opposing BTC and cannot act in this residual-flat episode. Earlier October cutting altered capital and raised relative load in January. E4/XS recover Jan14 with5000SOL; R2C's add ban removes that later participation.

November E4 is BTC-only: global peak Oct22 has short130.015 at108337.9010; trough Nov28 and recovery Dec1 retain short163.477 at87414.8507. Trough cash1807528.90619772 and marked equity903525.72689772 show a large open squeeze. The saved recovery returns equity to2003973.67486071 with the same trough/recovery position. This supports treating recovery preservation as a design objective; it does not prove a proposed stop/re-entry rule. **B's Nov26 peak/54.6783% is a different path and cannot substitute for E4's Oct22 peak/54.7928%.**

E4's Apr11→Jun6 DD48.3401%, Sep6→Sep18 DD35.7041%, Feb8 2026 DD35.9376%, and Jul6→Aug19 2026 DD46.3347140686% are below50%. E4 summer peak9633370.06642245→5169775.59097283 remains unrecovered at end. **R2C61.7587% summer DD is introduced on its altered capital path, not an E4 baseline failing the target.**

Source: [all E4 episodes and native endpoint snapshots](../b-50-90-next-20261023/verifier-E4-DD-ge30-episodes.csv), [XS episodes](../b-50-90-next-20261023/verifier-XS-DD-ge30-episodes.csv).

## What the residual study changes, and what it does not establish

New P0 exactly reproduces XS, not E4. R2C vs XS combines **minute cadence instead of H1** with **coverage of confirmed native BTC-flat residual SOL**. Its October mixed-position improvement already occurs before the residual extension matters. It is not an isolated residual-only A/B against E4. R1 H1 has a domain-float dust admission defect and equals XS; it is not a working H1 residual guard control. The repaired R2C exactly equals R2 economically, including minute trace/native fills/orders/funding/four triggers: correction benefit is zero on the actual minute history. A repaired H1 historical run does not exist.

The rule keeps DD40/adverse SOL2%/half reduction, freezes remaining and bans increases until native SOL flat. Four triggers generate15 actual child fills/13500SOL, not15 decisions. Executed quantities/prices are native, not threshold marks or ideal prices.

| trigger UTC | native BTC | SOL held→remaining | fill VWAP | fees | next SOL flat; later increases |
|---|---|---:|---:|---:|---|
| Oct3 2024 09:03 | short0.940 | 1000→500 | 135.5 | 37.2625 | Oct5 00:00;0 |
| Jan13 2025 11:43 | flat | 4000→2000 | 176.225 | 193.8475 | Jan15 00:00;0 |
| May23 2025 09:07 | flat | 7000→3500 | 186.94 | 359.8595 | May24 00:00;0 |
| Sep18 2025 17:07 | long15.013 | 15000→7500 | 252.1886667 | 1040.27825 | Sep23 00:00;0 |

R2C October DD49.9363% passes locally, vs XS52.5801% and E457.5854%. Earlier sell at135.5 instead of H1 134.72 improves actual Oct cycle by389.7855 vs XS. XS Oct floor gap was380.39978437; R2C actual floor cushion is9.38571563. R2C January DD49.4068% passes locally (153953.41110258→77889.95733058), but recovery is Jan21 16:12 rather than E4/XS Jan14 14:42.

Sources: [guard report and correction limits](../e4-sol-residual-20261023/REPORT.md), [15 filled orders](../e4-sol-residual-20261023/verifier-risk-cut-timeline.csv), [R2C episodes](../e4-sol-residual-20261023/verifier-R2C-DD-ge30-episodes.csv), [R2/R2C identity](../e4-sol-residual-20261023/verifier-correction-economic-delta.json).

## Recovery cost in the four actually protected SOL cycles

All figures are whole actual zero-to-zero SOL cycle fill-net **excluding unallocated funding**. Recipe cycle dates match, but quantities and subsequent entry/add histories need not. Their differences are descriptive actual-path outcomes, not isolated stop effects or additive promised terminal gains.

| SOL cycle UTC | E4 net | XS net | R2C net | R2C−XS |
|---|---:|---:|---:|---:|
| Oct3–5 2024 | +3214.10099625 | −1323.4555 | −933.67 | +389.7855 |
| Jan10–15 2025 | +4502.1215 | +4502.1215 | −22401.9375 | −26904.059 |
| May10–24 2025 | +2258.297 | +2258.297 | −43091.63175 | −45349.92875 |
| Sep11–23 2025 | +388251.182 | +388251.182 | +6940.67375 | −381310.50825 |

The four differences sum−453174.7105; actual full-history SOL difference is−459145.51134265, so these matched date cycles explain most of the descriptive SOL aggregate decline. October's modest earlier-fill gain is overwhelmed by recovery loss in other cycles. January total adds5000→4000, September22000→15000. May total adds stay7000 but the partial short cover crystallizes loss before ordinary exit. January remaining SOL exits187.44; taking half out at176.225 and banning the add sacrifices the recovery. September remains positive, but far below the uncut path. No assertion that every stop was unprofitable is needed.

Sources: [E4 cycles](../b-50-90-next-20261023/verifier-E4-closed-cycle-ledger.csv), [XS cycles](../b-50-90-next-20261023/verifier-XS-closed-cycle-ledger.csv), [R2C cycles](../e4-sol-residual-20261023/verifier-R2C-closed-cycle-ledger.csv).

## Why terminal ROI and global DD deteriorate beyond the cuts

XS→R2C TOTAL−2795692.79517100 consists of actual BTC fill-net−2348093.13843387, SOL−459145.51134265 and unallocated bridge+11545.85460552. R2C−E4 TOTAL−3020965.03833960 includes XS's earlier−225272.24316860 as well. Fees decline185071.88705175 vs E4, but reduced participation/path profit is larger.

All337 BTC fill rows retain XS calendar, prices, sides, reasons, levels and liquidity;292 quantities change. This is strong evidence against lost BTC signals as the residual policy's ROI mechanism. It supports the capital/sizing channel, but the realized−2.348m BTC delta is an accounting attribution, not a separately controlled estimate of reinvestment. Native caps, lot rounding, admission and SOL add eligibility prevent simple proportional scaling. First change is actually an increase0.446→0.463BTC after R2C's better October exit, so the path is not uniformly smaller from the first divergence.

At Jul6 2026 13:40 all E4/XS/R2C hold the same BTC short275.755 despite cash9278487.16917245/9063280.42146123/5904122.8946154. By Aug19 trough, R2C holds only new long120.624 vs E4260.536/XS250.043. R2C cash loss3433276.87697803 and aggregate unrealized drop432202.88125 sum its equity loss3865479.75822803;61.7587% of its reduced peak6259005.7918654. E4 cash loss3941708.00219961 is **larger in dollars** but summer DD46.3347% of its higher peak. Thus smaller absolute exposure/loss does not ensure smaller percentage global DD. The guard leaves a much smaller denominator while earlier capped BTC size can remain equal. R2C summer is a realized-loss/capital path plus final marked long, not a sudden residual SOL loss. Closing that final long cannot recover earlier realized losses.

Sources: [BTC calendar/quantity proof](../e4-sol-residual-20261023/owner-btc-calendar-comparison.json), [asset attribution](../e4-sol-residual-20261023/asset_fill_net.csv), [comparison](../e4-sol-residual-20261023/comparison.csv), [R2C endpoint snapshots](../e4-sol-residual-20261023/verifier-R2C-DD-ge30-episodes.csv).

## At most three experiments motivated by evidence; none authorized or run here

1. **E4-based SOL risk budget at admission/adds, narrowly covering mixed and residual SOL:** target the Oct/Jan exposure-to-equity load before large tail loss; preserve ordinary recovery participation where budget permits. Test a single predeclared budget rule against E4 with unchanged BTC entry/TP engine, inspect blocked adds, all four protected cycles, all global episodes and 90% terminal floor. This is a hypothesis: endpoint gaps1118/2463 are far smaller than the observed long-path cost of unconditional half-cut/add lockout, but do not prove an executable budget exists.
2. **Recovery-compatible SOL intervention ablation:** only if the first design needs an emergency cut, isolate the permanent add ban from the cut with explicit rights conservation and native execution, rather than repeat R2C unchanged. January5000→4000 and September22000→15000 identify the mechanism worth testing; a revised rule must neither recreate consumed rights nor assume a free profitable re-entry. Predeclare conditions; compare whole cycle losses/recoveries and portfolio effects, not hypothetical recovered P&L.
3. **Bounded E4 BTC November exposure/recovery experiment:** E4's third genuine >50% episode is BTC-only54.7928%, gap95789.39 at its actual global peak. Test one predeclared local budget/add or reversible reduction design that explicitly preserves/requalifies the observed squeeze recovery. Z's broad zero-slot retirement already harms capital, so do not generalize it or redesign summer as if E4 summer already failed50%. Summer46.3347% remains a mandatory regression check: any local fix must avoid inducing R2C's61.7587% capital failure.

These are experiment hypotheses, not threshold optimization, predictions, approval to run, or a claim that combining benefits will pass50/90. E4 has only161220.84 terminal cushion; every native-path intervention must be judged on its own full actual path. Reused diagnostic synthetic1m CLOSE data and settled-minute DD do not establish fresh OOS or intraminute/live risk bounds.

### Proposal evidence grades and rights constraint

Direct evidence supports the actual four SOL cuts, locked-out increases, preserved BTC fill calendar, observed recovery outcomes and E4's three >50% episodes. The suggested risk budget, minimum necessary trim and reversible/add-right design are **mechanistic hypotheses**, not demonstrated improvements. A minimum trim cannot be computed from hindsight floor gaps and declared executable; execution lag, liquidity and changing peak must be specified causally. Cadence and residual coverage were changed together; corrected H1 remains untested.

A general 20% BTC trim with no TP-right retirement is **not established** by these saved compact outputs. The precheck exports describe original B parents, while the risk-retirement export covers Z/XZ/XZS and explicitly records retired zero-slot leaves/zero SOL grants; neither is a complete as-of E4 native cache ledger proving an unreserved trailing20% after TP reservations at every candidate action. E4-specific unreserved trailing quantity is therefore **UNKNOWN**. Any future BTC test first needs an exact as-of ownership/working-order/partial-fill inventory proof or an explicit policy for reducing/canceling reserved TP leaves and conserving SOL entitlement. Calling a trim rights-neutral now would be unsupported.

This is not permission to repeat blanket M1, Z, TEMP_CAP or permanent broad reduction. Existing Z evidence shows retirement can destroy profitable future participation; current R2C shows add lock and crystallized losses can create new global DD. A proposal that only renames a constant reduction or reuses hindsight trigger dates does not address those failures. The next study should isolate a single causal mechanism, conserve ordinary TP/fallback/rights unless explicitly tested, and grade every resulting native path versus E4.

Sources for the UNKNOWN boundary: [B parent precheck](../b-50-90-next-20261023/owner-btc-parent-precheck.csv), [Z-family risk/rights retirement ledger](../b-50-90-next-20261023/owner-risk-retirement-rights.csv), [actual E4 risk-action ledger](../b-50-90-next-20261023/owner-critical-window-action-ledger.csv).
