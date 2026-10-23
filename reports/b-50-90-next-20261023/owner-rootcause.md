# Owner source, execution and mechanism closeout

Frozen source: bd04c9b3858bcda40060a08eff488849c69af5d8. Eight main native runs completed, zero conditional controls, zero active/reserved engines. No further native launch is authorized this cycle. P0 reproduced original B exactly on all 21 declared parity checks, including the complete uncompressed settled-receipt trace. Each run passed the ten mechanical checks, ended flat with no owned work, and retained 1,051,199/1,051,199 settled receipts. The native artifact's preexisting `NOT_FAITHFUL_DIAGNOSTIC` label is retained; these are bounded research results, not a production attestation.

| Recipe | Native TOTAL | Profit retention % | Global settled DD % |
|---|---:|---:|---:|
| P0/B | 4622034.27336437 | 76.0170 | 57.5854 |
| E4 | 5631617.35953723 | 92.6573 | 57.5854 |
| EP | 3992055.58641779 | 65.6335 | 57.5854 |
| Z | 2517706.78173418 | 41.3328 | 60.2962 |
| S | 4155625.77863239 | 68.3295 | 57.1470 |
| XZ | 4877453.55144460 | 80.2269 | 60.2962 |
| XS | 5406345.11636863 | 88.9443 | 58.9474 |
| XZS | 4696068.73175334 | 77.2373 | 58.7195 |

All liquidations are zero. No recipe reaches 50/90 or the frozen near-Pareto gate (DD <=55%, retention >=85%, nondominated, better than B on both axes). No extra repeat, stress or neighbor control is activated.

E4 improves the subsequent entry calendar and preserves the most profit. It cannot repair the initial October drawdown: its first ordered divergence is parent 6, after that episode. The permission at 2024-10-06 16:00 UTC produces an actual entry at 16:02 (1.289 BTC, P0 62755.4), whereas B enters October 7 at 00:01 (0.742 BTC). See `owner-wait-first-divergence.csv`, E4 row. All E4 combinations inherit this calendar mechanism. EP is a different accepted daily persistence permission; its 106 accepted WAIT observations produce a weaker final path despite the same early global drawdown. Parent-by-parent calendar differences are actual trajectories, not matched fixed-state profit attribution.

S is active before the early 50% crossing: the native cut is 500 SOL at 134.72 on 2024-10-03 15:00 UTC, with a frozen remaining target of 500 and a native fee of 37.048. The surviving 500 exits at the original REGIME close on October 5 at 143.12. No later increase occurs before that cycle is flat. Thus S cuts actual early risk but also relinquishes a subsequent recovery and an ordinary top-up; it lowers standalone DD only to 57.1470% and reduces TOTAL. See `owner-sol-risk-cohort.csv`, S/first cycle, and `owner-critical-window-action-ledger.csv`, S/A. The saved conservative precheck witness was 15:01; runtime closed-H1 CustomData and executable quote were actually accepted at 15:00. The proposal's illustrative 135.84 is not substituted for the native price.

Z acts on the intended November adverse path: Z parent 50 arms at 2025-11-26 04:00 UTC and cuts 44.008 BTC at 87347.4 at 05:07, before the November 28 trough. Its first ordinary exit is TP3 on December 1 at 15:35. But Z also changes capital before October: its first actual cut is September 18 at 05:07. It therefore does not isolate insurance to the November event. Its 15 native cuts retire 780.337 BTC of zero-slot exposure and also retire the associated future SOL entitlement. Across Z/XZ/XZS there are 85 actually retired level rows and zero later SOL_ADD at the same retired levels. See `owner-zero-profitable-fallback-contrast.csv`; comparisons with B's subsequent exit prices are descriptive unit-price contrasts, not a realizable alternative PnL or TOTAL.

The August 19, 2026 counterexample survives in standalone Z: parent 76's first favorable closed 4h bar is 16:00, after its first ordinary TP3 at 14:39; Z has no eligible arm or cut. XZ/XZS have no same-day native parent because their calendars already differ. See `owner-critical-zero-counterexamples.csv`, recipe/day keys. Do not map those paths onto a fabricated shared parent.

Combinations do not combine benefits additively. XZ improves on Z but inherits the worse early capital path; XS gives back profit and worsens DD relative to E4; XZS still fails both gates. `owner-action-mechanism.csv` retains every causal permission/risk/preemption action, and `owner-activation-mechanical-checks.csv` checks actual native fills against policy receipts separately in BTC and SOL units. It does not add unlike quantities.

Two stored-audit/source qualifications are explicit. `armed_ns` is overwritten by subsequent favorable 4h confirmations; it is not an immutable first-arm timestamp. Saved benchmark proofs cover all armed cohorts: Z 26 (15 triggered/11 untriggered), XZ 24 (14/10), XZS 24 (14/10). At every overwrite the same-timestamp native zero-spread quote remains favorable by at least one BTC tick; the first eligible return after the original arm equals the actual trigger, or no eligible return occurs before preemption/ordinary exit. All three proofs pass using integer 0.1 price ticks. This is benchmark-specific equivalence, not proof for live spreads, different event orderings or subminute returns. Also ARM/TRIGGER slot dictionaries alias mutable task leaves; zero terminal leaves are not initial budgets. The saved reconstruction uses native planned parent sizing and actual retired lots; 74/74 armed cohorts exactly reproduce frozen domain initial budgets. See the three `owner-*-arm-equivalence.json` files and `owner-Z-slot-alias-reconstruction.csv`.

TOTAL is native cash after terminal close/settlement. Minute risk and calendar windows stop at the declared boundary before any subsequent terminal settlement; their endpoint equity need not equal TOTAL. Fees, fills and cash remain native. Signed funding attribution and historical owned-queue snapshots not present in saved receipts remain UNKNOWN. The independent verifier owns detailed monthly, global drawdown and asset accounting exports; this closeout does not duplicate that scan or replace it with a second PnL model.

Execution retained the original matching configuration and minute CLOSE quote feed for all flags. H1/4h decisions used CustomData, not matching OHLC Bars. The frozen focused pass had 73 tests passing; no post-result source change, economic rerun, deployment, service action, pilot inspection or real order occurred.
