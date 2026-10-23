# Conditional SOL hedge + BTC reentry band — v2

Проверка завершена: **ни один вариант не достиг DD ≤50% при сохранении ≥90% чистой прибыли S0**. Лучший по капиталу новый вариант B: **4 622 034,27 USDT**, ROI **+46 120,34%**, DD **57,59%**, сохранено **76,02%** прибыли. C0, шесть H4 и комбинация X ликвидированы в общей модели. Контролем остаётся S0 **6 077 107,24 USDT**. Выполнено 10 из максимум 11 полных запусков; повтор R не требуется. Пилот и production не менялись.

**NO_GO for this bounded family.** No candidate meets both settled minute DD <=50% and >=90% of S0 net profit. Research is complete; the economic objective is not achieved. Retain exact S0. Pilot, production and real orders were untouched.

Interval `[2024-09-01, 2026-09-01)`, initial10,000USDT, shared reinvested capital, RESERVE=0, DP OFF. Minimum TOTAL: **5,470,396.514987347USDT**, rounded upward to cents5,470,396.52. Selection and budget were frozen before results.

| Recipe | TOTAL USDT | ROI | S0 net profit retained | Minute DD | Fills |
|---|---:|---:|---:|---:|---:|
| S0_ARCHIVE | 6,077,107.24 | 60,671.07% | 100.00% | 66.26% | 621 |
| C0 | 306.48 | -96.94% | -0.16% | 97.53% | 6 |
| H4_4H_E34_G050 | 437.07 | -95.63% | -0.16% | >=96.48% | 12 |
| H4_4H_E13_G050 | 316.85 | -96.83% | -0.16% | >=97.10% | 24 |
| H4_4H_E89_G050 | 447.08 | -95.53% | -0.16% | >=96.40% | 14 |
| H4_4H_E34_G100 | 455.92 | -95.44% | -0.16% | >=96.33% | 10 |
| H4_4H_E13_G100 | 483.07 | -95.17% | -0.16% | >=95.96% | 22 |
| H4_4H_E89_G100 | 540.33 | -94.60% | -0.16% | >=95.65% | 12 |
| BTC_REGIME_REENTRY_BAND_05 | 4,622,034.27 | 46,120.34% | 76.02% | 57.59% | 484 |
| X_H4_4H_E89_G100_B05 | 540.33 | -94.60% | -0.16% | >=95.65% | 12 |

Exact values, maker/taker turnover/fees, BTC/SOL fills, funding counts, liquidations and hashes: `comparison.json/csv`. Liquidation is the actual common-model economic outcome, without an additional ranking penalty.

C0 changes only original SOL lifecycle at actual BTC-flat. It invalidates remaining rights/orders, closes SOL and reconciles the group; it does not proportionally cut SOL at each BTC TP. H4 replaces original SOL with opposite-BTC4h EMA13/34/89 x gamma0.5/1.0, frozen daily beta270 quantity ratio,4h build deadline, no ownTP/SL/z/14d timeout. B keeps **fully original SOL** and gates only post-REGIME BTC reentry by0.5 Wilder ATR14. Initial/post-TP/post-TRAIL entries and REGIME exits are preserved.

C0 closes the first group after BTC TP3 September6, preserving its true reason rather than inventing REGIME. Next BTC short opens September7 and is liquidated September13. There are0SOL fills. Earlier group release changes the BTC calendar and subsequent capital; candidates are not forced onto S0's105 original entries.

All6H4 recipes are also liquidated early. FirstE34/G0.5 exits SOL September13 12:01UTC; BTC liquidation follows15:50UTC. Own-EMA eligibility leaves the critical move unprotected; the saved admission/minimum gate also blocks some builds; its exact component is not separately recorded. H4-C0 changes signal/sizing/exits together, not just one EMA. These results reject the6recipes, not every possible SOL insurance policy.

B lowers globalDD by8.67percentage points but loses1,455,072.97USDT against S0 and retains only76.02% net profit.124WAIT events=41REGIME latches+83weak-band refusals;41entries allowed. Its effect varies across identical calendar windows:

| Window | S0 local DD | B local DD |
|---|---:|---:|
| A | 66.26% | 57.59% |
| B | 59.84% | 44.36% |
| C | 55.10% | 54.68% |
| D | 40.79% | 48.17% |

A `[2024-09-01,2024-10-04)`; B `[2025-04-11,2025-06-07)`; C `[2025-10-22,2025-11-29)`; D `[2026-07-06,2026-08-19)`. These are local rebased diagnostics, never a global peak reset. D worsens in percentage terms despite smaller capital. E1-E4 include all remaining calendar. Monthly returns, recoveries, quantities, original winners and required counterexamples are retained.

The frozen fallback picks E89/G1 for X as maximum-TOTAL validH4, explicitly **ROI_FAIL**. X exactly reproduces its ordered native fills, fees, account, funding and risk. No REGIME event occurs before liquidation, so B never acts. Standalone outcomes were not added together.

Selected E89/G1 last exits SOL September11 04:01UTC; BTC liquidates September13 15:23UTC. Two later activations target629.8/631.0SOL but receive zero fills and239 local admission denials each before their4h deadlines. These targets are below quote capacity: the known admission/size gate and conditional timing explain the missing protection. The stored reason is PRE_SUBMIT_INCREASE_GATE_OR_MINIMUM; a specific available-margin shortfall is not independently proven. See `owner-mechanistic-findings.md` and activation/latency/action CSVs.

B's wait intervals include50 absent S0 entry dates:28 historical losing labels and22 winning labels. It has77actual BTC parents versus105S0;51same-day matches,54absent original dates,26new dates.39matched quantities change with native capital/admission. These are diagnostics, not the sum of hypothetical removed-trade profits. All131original BTC/SOL episodes and6mandatory counterexamples are retained for every compared recipe.

Maximum native equity is9,361,910.09938506 for S0 and7,290,323.10477185 for B. Maximum dollar drawdown is3,818,310.32850109 and3,676,819.60707685 respectively. Dollar DD, percentage DD and their peak/trough timestamps are separate in `global-risk.csv`; smaller capital is not claimed as lower percentage risk. Fixed-state factor/residual and matched-beta BTC-reduction diagnostics are not alternative native TOTAL/PnL accounts; see `owner-factor-diagnostic.csv`.

Source `25a085f596292df58e51188dd91e996adbe5724c`:47focused tests+3original split regressions PASS; independent source review GO. Independent saved-output audit verifies TOTAL/fees/turnover/fills/funding/settledDD/source/input pins for all9candidates. B has134natural partially filled terminal orders. H4 has0: actual targets/fills stay below1000SOL synthetic quote capacity. Focused native fixtures test partial/cancel/late-fill separately. H4_NATIVE_CHILD includes locally blocked proposals; it is not the native order count.

C0/B have1,051,199settled receipts/0missing; E13/G1 has28missing, otherH4/X32. Missing receipts coincide with real native funding cash mutations; they are not filled with zero/synthetic equity. H4DD is an **observed lower bound**, already>50%, sufficient for rejection. Incomplete coverage cannot prove positive acceptance. Signed per-asset funding is **UNKNOWN**, not0; native account totals include actual applied cash changes.

P0 is required by Linux-to-Mac arm64 change. TOTAL6,077,107.23887483, fees945,927.73761825,621fills/710orders/1320funding rows and native account/risk paths match exactly. **Strict full-artifact repeat FAIL remains:** BTC3 beta-1ULP/H+2ULP from `math.log`/libm rounding. No SOL fills or observed economic-action difference in that interval. Predeclared economic parity was accepted; no widened tolerance or universal bitwise portability claim.

**10physical full runs of maximum11**:P0+8core+X. Commands, fresh engines/journals, resources and prelaunch incidents are preserved. C0 measurement wrapper fails sysctl after native COMPLETED:RSS UNKNOWN, native outcome valid, no rerun. R is **NOT_RUN_GATE_FAILED**; unused budget is not spent on another hypothesis.

Benchmark remains **NOT_FAITHFUL_DIAGNOSTIC**:Bybit1m CLOSE synthetic quotes, limited liquidity model and unqualified historical margin/liquidation applicability. Comparative native economics are not promised live performance/tickDD. Repeatedly studied history is not independent OOS; genuinely untouched data must be future after freeze. No forward trading is launched here.

No new winner/deployment. Default-OFF modules, source patch and exact configs/CLI are retained. S0 remains control. Intraday post-entry wave-MFE for TP stays backlog, requiring identical full prehistory; no newTP/SL/AI/grid.

Evidence:`selection.json`, `manifest.json`, `validation.json`, `policy-freeze.json`, `spec-diff.md`, `comparison.json/csv`, `monthly.csv`, `windows.csv`, `episode-comparison.csv`, `signal-events.csv`, `action-audit.csv`, `owner-factor-diagnostic.csv`, `owner-hedge-latency-shortfall.csv`, `best-tested-nonpassing-config.json`, `retained-control.json`.

Interval/monthly/global receipt endpoints are preterminal observations; TOTAL is settled native cash after boundary close. `terminal-settlement.csv` preserves the bridge for all10recipes. For B, last observed equity4,629,999.26206236 versus terminal TOTAL4,622,034.27336437 is explicitly separated, not silently substituted. Full native runs used1,489.92seconds wall time in total; maximum measured RSS457,441,280bytes; C0 RSS remains unknown.

Existing [Project2](https://github.com/users/VF78/projects/2) / [issue123](https://github.com/VF78/coinmaster/issues/123) is Done/closed(completed), read back exactly. This closes the bounded research package, not the unmet economic goal. No issue body/comment/message was published. Source [25a085f](https://github.com/VF78/coinmaster/commit/25a085f596292df58e51188dd91e996adbe5724c) is published in a separate research branch;0CI check runs, no CI-green claim or deployment.
