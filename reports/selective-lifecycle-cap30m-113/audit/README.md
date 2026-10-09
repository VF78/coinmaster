# CM-113 actual economics and lifecycle audit — cap30m

Completed diagnostic native run: reviewed commit `d7d18cdc22c0ebb918f202eb9168fcc3159ed9e1`, result SHA256 `8e4a387260688729563258b84befe34b0bef2479f2fbe369c621fab9cc3281e2`. Archived selective control SHA256 `0ccad5771c23e380ba6115cc7bc8530b47ee39ec6fe99c08595640e17b9faee1`. Audit-only: no source changes, new run, optimizer, deployment, credentials, orders or pilot action.

## Authoritative outcome

| Native measure | Selective 10m control | Lifecycle + cap30m |
|---|---:|---:|
| ACTIVE = TOTAL, USDT | 3,747,041.97080334 | 5,146,884.95718200 |
| RESERVE | 0 | 0 |
| ROI on 10,000 seed | 37,370.41970803% | 51,368.84957182% |
| Native fees, USDT | 597,517.54289494 | 1,144,089.96955003 |
| Correct cash-relative maximum DD | 62.46697029% | 62.30510948% |
| BTC fills / entries | 311 / 105 | 311 / 105 |
| SOL fills / adds | 221 / 110 | 191 / 95 |
| Generic SOL admission blocks | 2 | 17 |
| Liquidations / rejections / terminal positions | 0 / 0 / 0 | 0 / 0 / 0 |

TOTAL increases **1,399,842.98637866 USDT / 37.35861507% versus control**, after expenses. Fees increase 546,572.42665509. This is a combined treatment: no ablation isolates cap, margin, fresh marks or individual lifecycle fixes.

Only two config differences exist: new `research_v0_selective_lifecycle_repairs=true` and `candidate.max_parent_notional=10m→30m`. Data hash `7ab5ae2cdaa14885da28d188c7ad14dfc8168ee600b78535f7317409ea94e9cc`, policy hash `c9540fbef259039c95829a774ef54e0eea2dcf2b6748d6455e171bf28e889834`, interval, warmup and seed match. Funding logic, fee policy/floor, positive TP2, EMA/z, fractions/multipliers and disabled deposit protection remain unchanged. Exact config/source/result/fill/order receipts are in ../comparison.json; compact stage numbers in ../comparison.csv.

Cash DD is recomputed as the largest `(running_peak - current_native_total) / running_peak` over exported native cash events. New worst relative loss: 1,095,942.11640240 on 2025-04-10 → 413,114.18091703 on 2025-06-08; amount 682,827.93548537. The harness's ratio associated with maximum *dollar* DD is not necessarily maximum relative DD. Full marked-equity DD remains unknown; exported marked checkpoints are incomplete. DD is descriptive, not an objective penalty.

## Fill, fee and quantity reconciliation

All 502 fill-audit rows match actual native execution rows at sub-tick price precision; binary-float avg_px presentation differences are normalized below the native tick. Actual commissions sum exactly to native fees. All 556 orders are terminal: 341 FILLED / 215 CANCELED. Of the canceled orders, 161 SOL IOC orders had real partial fills (92 adds, 69 reductions); 54 BTC resting limits had zero fills. Cancellation does not mean no execution.

| Native liquidity | Count | Notional, USDT | Fees, USDT |
|---|---:|---:|---:|
| MAKER | 78 | 398,066,217.3193 | 79,613.24346386 |
| TAKER | 424 | 1,935,412,229.2471 | 1,064,476.72608617 |

BTC entry and exit quantity both equal 15,530.038 BTC; SOL entry and exit both equal 94,163.0 SOL. Native terminal lifecycle is FLAT/locked; final BTC settlement closes 220.598 BTC, notional 17,322,435.8902. All order statuses are terminal; no residual exposure or quantity over-allocation appears.

Action counts: BTC entries105, zero/planned-market reductions77, TP2=24, TP3=54, REGIME48, TRAIL2, terminal1. SOL adds95, REGIME42, TRAIL40, half1, full1, timeout12. All BTC entries remain q0→q1 60 seconds; branches remain 45 passive / 60 full fallback. Omitted rights remain 76 levels and 76 activations.

Confirmed-fill average/proportional entry-basis attribution reproduces the prior audited control totals, then gives new BTC net 4,547,444.48035402 and SOL net 563,392.91809595, sum 5,110,837.39844997. Native cash gain is 5,136,884.95718200. **Residual +26,047.55873203 is unallocated native cash/funding/other**, not assigned invented per-trade funding. Control residual was −1,523.93290172. Attributed BTC delta +1,594,058.42524491, SOL delta −221,786.9305, residual delta +27,571.49163375 exactly explain the native comparison arithmetic. These are attribution, not authoritative closed-position PnL or another backtest engine.

Funding event counts match: 1,321 (BTC900/SOL421). Signed funding remains `UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA`; unchanged logic/counts do not imply identical funding dollars under changed exposure.

## First divergence and cap/admission behavior

First fill divergence is **2024-12-23 00:03 UTC**: control executes two 1,000-SOL adds at180.12, levels0/1; new run executes level0 only and exports a generic SOL admission block at that timestamp. Native end-of-timestamp cash is control109,204.41327345 / new109,303.47927345: +99.066 equals the missing level1 commission. The archived level1 IOC parent requested10,462 SOL but filled1,000. The exported gate reason combines minimum, entry-enable and tier/gross/freshness/budget checks; it does not expose which subpredicate failed. Source changes place fresh native unrealized PnL and bounded actual-reservation credit in the gate, but labeling all17 records specifically as margin rejection would overclaim.

The first matched BTC entry quantity changes 2024-12-25 00:02 UTC: 10.156→9.113 at98,648.9. Both are below10m. Thus SOL admissions/cash compounding diverge before any parent-cap constraint. The Dec23 SOL episode was profitable in both runs, but one fewer add reduces attributed episode net40,142.2575→23,449.6845. Aggregate SOL reductions are not demonstrated ROI improvements: four changed profitable SOL episodes lose229,629.7325 attributed net, two changed losing episodes improve7,842.802; net−221,786.9305.

New gross q0 reference binds30m in30/105 entries, versus47 old10m bindings. New first binding is2026-03-05; old first binding2025-04-11. At q1, nine full-fallback entries require floor-clamping to admitted quantity; actual admitted and confirmed quantities agree. Maximum actual BTC fill notional29,999,986.8278; zero30m breaches, versus11 old10m breaches. Nine entries lie within one0.001BTC lot of30m. All clamps are mechanical cap compliance, not whole-trade denial.

**Reporting caveat:** `net_submitted_btc_qty` retains the pre-clamp q0-plan quantity in those nine exported records; `admitted_net_quantity` and `confirmed_native_entry_qty` show the actual q1 quantity. Use the latter for cap/fill analysis. This is a field-meaning inconsistency, not evidence that actual submitted/fill quantities breached the cap. Source lines943–953 update domain net denominator and explicit admitted audit field before submit; real quantities are independently reconciled above.

Larger exposure amplifies winners and losers. For example, BTC episode2026-05-15 attributed loss grows−462,840.22210888→−1,388,243.05823077; April8 gain329,072.49613099→987,007.31420746. This does not identify a causal rule for removing the losing trade. All48 opposite-regime BTC close/reentries remain intentional; suppressing them or selecting trades by future result is not justified.

## Observed paths versus focused native proof

- **Observed:** nine q1 clamps; zero cap violations; actual admissions differ;76 once-only omitted-right activations; quantities flat; terminal native close complete.
- **Focused native proof, reused:** ordinary SOL partial half/full completion with fixed accepted targets; conditional BTC zero-fallback residual waits through adverse quotes; earned-before-touch; native actual-reservation budget/fresh marked equity; terminal unsubmitted cleanup/unknown ACK preservation. Existing98 relevant tests and four corrected native margin cases belong to reviewed source verification; no tests were rerun here.
- **Not exercised by this 24m result:** ordinary SOL half/full each fill500 completely; no partial zero-BTC market fallback; no pre-fill-touch race or flat-at-terminal q0 orphan. They cannot explain this run's gain. Mandatory SOL timeout still completes12 partial fills over11minutes, unchanged−120,525.836 attributed loss; losing hold is not a stuck exit.

105 BTC episodes keep median47.9833h/max379.6h;26 SOL episodes median108h/max336.1833h; none close within1h. SOL adds followed by an actual exit within24h:15/95, fees1,278.4976281 (control17/110, fees1,488.7076281); within48h30/95; within1h0. This is a churn screen, not evidence those adds should be removed. Positive TP2 remains untouched: six of24 legs are fee-negative, new aggregate−655.81565502 (control−774.70890156). No TP2 repricing/fee-floor proposal is included.

## Bounded next hypotheses — unmeasured, no action taken

1. **Separate cap and admission effects before choosing another cap.** Thirty q0 bindings and amplified late winners/losses support treating the cap as an active compounding control. One-variable authorized comparisons with lifecycle fixed could estimate cap contribution and how caps within the approved 30m ceiling affect native TOTAL. A ceiling above30m would require a separate explicit scope and verified native venue/child-order constraints; it is not recommended by this result alone. Current result does not isolate cap-only gain. Preserve current economic rules and real-fill rights.
2. **Investigate all-or-nothing SOL parent affordability with reason evidence.** Seventeen generic blocks,15 fewer actual adds, and the first10,462-parent/1,000-fill case identify a possible lost affordable-exposure path. First export native free/IM/MM credit/fresh policy gross and each denial predicate at the decision. A bounded future sizing policy could submit only a genuinely affordable normalized child while preserving H, entitlement and completion ownership. No fabricated collateral, unconditional retry, or assumption that future liquidity always supplies1,000. SOL's lower net shows potential opportunity; it does not prove every blocked add was affordable/profitable.
3. **Consider a causal SOL add guard as timeout approaches.** The unchanged14-day losing episode has12 real add fills and−120,525.836 net;15 adds precede exits within24h. A separate proposal could use already-known position age/accepted exit ownership/current causal regime or trail distance. Compare against profitable late adds as well; measure native TOTAL and missed exposure. Future exit time/PnL is prohibited as an entry label. Existing accepted-exit ownership already blocks competing adds, so this is a new sizing/eligibility hypothesis, not another demonstrated lifecycle defect.

All hypotheses require separate scope before tests/runs/changes. No blanket flip suppression, hindsight trade removal, duplicate-order fee-saving claim, or new fee-floor experiment follows from this audit.

## Diagnostic limits and evidence

Real Bybit1m close inputs drive native execution, but quotes are synthetic zero-spread with size1,000: no historical BBO/L2, impact, queue or slippage evidence. Current fixed fees/historical margin tiers and funding/liquidation mark applicability remain unvalidated. Result status stays `NOT_FAITHFUL_DIAGNOSTIC`, ranking_eligible=false; this is not live/promotion approval or proof of realistic multi-million execution capacity. Funding signed attribution and full marked-equity DD remain unknown.

Evidence: `findings.json` contains exact reconciliation, both attribution summaries, per-episode/action records, cap clamps and evidence classifications; `economics.csv` contains302 confirmed closing-fill legs; ../comparison.json and ../comparison.csv contain numerical comparison and exact identity receipt. Native TOTAL alone remains the objective authority.
