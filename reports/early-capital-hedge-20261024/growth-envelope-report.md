# Three fixed R3 scalar growth scenarios

2026-10-24. ARITHMETIC ONLY; not a native candidate, executable policy, or global bound. Even the perfect oracle that halves all29 negative endpoint returns while retaining54 winners yields1,037,982.53 USDT equivalent (16.9435% original S0 net). It still needs4.1012x to70% and5.2702x to90%. This fixed loss-halving class alone does not close the gap; this is not a general impossibility result for SOL hedging.

| Scenario | Algebraic TOTAL-equivalent USDT | S0 net retained % | Required x70 | ln gap70 | Required x90 | ln gap90 | Cycle-boundary DD % |
|---|---:|---:|---:|---:|---:|---:|---:|
| observed | 120,718.40 | 1.8249 | 35.2637 | 3.562854 | 45.3153 | 3.813646 | 63.1153 |
| uniformhalf | 44,053.08 | 0.5613 | 96.6328 | 4.570919 | 124.1774 | 4.821711 | 38.3035 |
| oraclelosshalving | 1,037,982.53 | 16.9435 | 4.1012 | 1.411280 | 5.2702 | 1.662072 | 38.1172 |

Original absolute floors remain70%=4256975.067212381,90%=5470396.514987347. Oracle absolute shortfall=3218992.536419235 /4432413.984194201 respectively. Uniformhalf lowers positive returns along with losses and yields lower growth. The roughly38% cycle-boundary DD is NOT global marked/event DD: all intracycle peaks/troughs and margin dynamics are absent.

| Cumulative boundary / closed cycles | observed | uniformhalf | oraclelosshalving |
|---|---:|---:|---:|
| early_starts_before_2025-01-15 /19 | 19,544.07 | 14,985.62 | 34,649.79 |
| first_year_starts_before_2025-09-01 /43 | 49,136.13 | 25,744.16 | 155,316.41 |
| second-year endpoint /83 | 120,718.40 | 44,053.08 | 1,037,982.53 |

Early cohort: starts<2025-01-15 (19cycles); first-year: starts<2025-09-01 (43cycles); final second-year endpoint83cycles. No early/year boundary is crossed by an open cycle, so start-cohort and completed-before-boundary endpoints coincide. These are cumulative scalar endpoints, not annual strategy returns.

## Money and chronology checks

All83 cycle inclusive nets equal ex-funding net plus signed funding, independently reconciled to parentCSV. Signed funding sum4063.32156049. Seed10000+all nets=120718.40416503 exactly; residual to saved nativeTOTAL=0E-8. Maximum absolute A_i minus own pre-entry settledcash=1E-8. Tolerance1E-6USDT concerns saved report precision only, not any engine guard. First-fill receipt already contains execution/fee and is not substituted for pre-entry cash. A_i/r_i are ex-post arithmetic, never causal features.

All82 actual transitions satisfy previous actual last-flat-fill<next actual first-entry-fill. Seven previous exit timestamps equal next decision timestamp: next cycles7/16/23/34/46/56/74; next actual entry is60s later. Callback order at tied decisions is UNKNOWN. Exact tie values are preserved in growth-envelope-decision-ties.json. Known pre-entry flat-boundary cash remains reconciled; no causal trading admission is inferred.

The initial stricter previousflat<nextdecision assertion failed BEFORE products. One correction allowed equality at decision while retaining strictly separated actual flat/entry fills and cash checks. Initial script/error retained. This did not alter the three predeclared scenarios.

## Arithmetic and independent verification

Decimal80 main pass computed exactly the three products in GROWTH_ENVELOPE_PROTOCOL.md: observed(1+r), uniformhalf(1+.5r), oracle(1+r for nonnegative r,1+.5r otherwise), using actual A=seed+prior nets. No coefficient, sign, cutoff, or signal selection. Oracle knows future losing cycles and favorably halves their endpoint costs too. It cannot be traded.

One independent exact Fraction verification loaded parent ex-funding cash+funding separately and used rational numerator/denominator products. All three terminal products, early/year endpoints, and cycle-boundary DD passed; maximum terminal difference<2.35E-73USDT. Main observed product minus savedTOTAL=-3E-74 (Decimal rounding). This is independent arithmetic, not another native money audit.

## Inputs and artifacts

- protocol: SHA256 `ab0f5b9b23139bef4a09bdf5a5132b093828c8868327d828dd0fa8c1cc5f8aff`; `/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021/reports/early-capital-hedge-20261024/GROWTH_ENVELOPE_PROTOCOL.md`
- cycles: SHA256 `e2ae632991b74f35c9ca666dc08e79e42b2b937fa7d74a2b6748eab6520ba22b`; `/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021/reports/market-redesign-20261024/native-analysis-attribution-R3-cycles.csv`
- parents: SHA256 `289290ac6e4ec4ca66071d9bfcff49ec31f94e6b7a09e2f5d28c5947fe96cbf3`; `/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021/reports/new-system-plan-20261024/btc-participation-parents.csv`

Reproduction: growth-envelope-calculate.py and growth-envelope-verify.py. Full precision results and all83 A/r/residuals: growth-envelope-results.json. Exact verification and both script hashes: growth-envelope-verification.json. Preserved initial failure: growth-envelope-calculate-initial.py /growth-envelope-initial-failure.json; seven ties: growth-envelope-decision-ties.json.

Conditional proportional transfer of historical owncapital returns is not a recalculation of quantities, fills, commissions, minimumlots, quote capacity, admission, exits, calendar, or liquidation. A real hedge has costs and imperfect predictions; half-volatility size gives estimated factor coverage.5rho<.5. Another residual/timing/capital path can change returns, so this oracle is not an upper bound for all hedges. No local momentum dollars are added to these paths. No new native/full/short/training/simulator process, product/source/sharedstate/Project/commit change; budgets remain0 and momentumSTOP unchanged.
