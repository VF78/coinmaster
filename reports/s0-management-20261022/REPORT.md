# S0 remainder management — native comparison

Status: both full native candidates completed and fail both economic criteria. Both candidates independently validated:44 result checks +9 fee-bucket checks each. No passing candidate; stop at2/4 attempts. Source `efa7c723d9f0c5c1bdc8f491abf12921ac41c275`; [Project #123](https://github.com/VF78/coinmaster/issues/123).

## Fixed experiment

Reuse the exact saved S0, TOTAL **6,077,107.23887483 USDT**, without rerunning its engine. All candidates use the same [2024-09-01, 2026-09-01) data, 10,000 USDT seed, fees, funding, margin, execution and observer. RESERVE=0. BTC initial signal and plan-sizing rules and the original SOL overlay remain fixed; subsequent actual quantities follow each native account's changed capital.

One added rule: on a fresh settled portfolio drawdown crossing from below25% to at least25%, reduce a currently losing native leg once in its cycle. Two consecutive eligible receipts are required; entry/pending-exit gaps clear the predecessor. M1 requests50% reduction, M2 requests75%. Each action uses one fixed remaining target and a native reduce-only MARKET IOC child. Partial fills are actual reductions; canceled leaves are not retried. Protective fills grant no BTC TP credit or new SOL rights. Native ordinary/forced exits retain priority. Full rules and before-run freeze: `policy-freeze.json`.

Acceptance: settled minute DD≤50% AND retention of at least90% of S0 net profit. The exact required TOTAL is **5,470,396.514987347 USDT** (rounded upward to cents **5,470,396.52**). Select maximum TOTAL among passing candidates. A fresh identical-engine confirmation is admitted only for a passing candidate. Four full attempts is a ceiling, not a requirement to expend all four.

## Economic comparison

|Variant|Terminal TOTAL / ACTIVE USDT|ROI|S0 net profit retained|Settled minute DD|Conditional OHLC bound|Native fees USDT|Fills|
|---|---:|---:|---:|---:|---:|---:|---:|
|Exact saved S0|6,077,107.23887483|+60,671.07238875%|100%|66.2569148647%|67.5477103187%|945,927.73761825|621|
|M1:50% trim|2,615,745.21476479|+26,057.45214765%|42.9487251860%|58.7740950447%|60.3199170803%|710,655.26790133|621|
|M2:75% trim|2,044,863.63091774|+20,348.63630918%|33.5392725198%|70.6446275533%|71.6802666531%|614,360.75019949|610|

RESERVE=0 and native liquidation count=0 in all three. Neither candidate reaches DD≤50% or TOTAL≥5,470,396.514987347. M1 has the larger TOTAL of the two changes, but it is not an admissible winner. Both variants are rejected; S0 remains the unchanged control. No fresh repeat is admitted for a failed candidate and no third posthoc intensity is selected. Unused budget:2/4.

## M1 validated result

TOTAL **2,615,745.21476479**, ROI **+26,057.4521476479%**, retained net profit **42.9487251860%**, agreed settled minute DD **58.7740950447%**: both criteria fail. Conditional OHLC bound **60.3199170803%** is separate and does not prove an actual tick path.

The first early drawdown improves to46.59%, while the full-path worst moves to May15–Aug11,2026: native equity5,734,212.23187448→2,363,980.88464897 (58.77%). The Apr11–Jun6,2025 drawdown remains55.29%. Final native flat-cash endpoint drawdown54.38% is included in validation and leaves the maximum unchanged.

There are26 protective fills (BTC20/SOL6):22 full orders and4 SOL partial IOC fills followed by cancellation. The total fill count stays621, but asset mix changes: BTC416→433, SOL205→188. BTC entry fill records remain210 in both variants; normal BTC reductions155→152→150 and SOL add fill records102→92→89 for S0/M1/M2. Fill records are not complete-trade counts.

The fee saving is235,272.46971692 USDT, yet final TOTAL falls3,461,362.02411004. By November2024 capital is68.68% of S0 and by February2026 it is49.08%. Twelve affected original S0 intervals were profitable. Those outcome labels show that the rule also cuts recovering positions; they cannot be summed as causal foregone profit. The full native comparison includes later compounding and changed SOL opportunities. Per-asset realized PnL and signed funding aggregate are unavailable in the existing native audit; no second PnL calculation substitutes for them.

## M2 result and interpretation

M2 completes with TOTAL **2,044,863.63091774**, retained net profit **33.5392725198%**, settled DD **70.6446275533%**. Native output seal/source checks and independent saved-output recomputation pass.M2 has429 BTC and181 SOL fill records. Native fees by asset are597,630.86232644 and16,729.88787305USDT respectively. There are25 protective fills (BTC19/SOL6),22 fully filled IOC orders and3 partially filled SOL IOC orders with canceled leaves. No percentage retry follows cancellation.

Its worst settled drawdown is again the first September14–October3,2024 episode:13,426.6743211→3,941.45025416, worse than S0. At the October3 trough the recorded book has BTC short0.173 and SOL long773.5; early SOL1 has no M2 management claim, while BTC6 was reduced that morning. This is observed position/action evidence, not isolated causal PnL. The July6–August11,2026 fall is58.71%; April11–June6,2025 is53.65%. Commission saving grows to331,566.98741876USDT but the final capital shortfall grows to4,032,243.60795709USDT. The stronger cut does not monotonically improve portfolio drawdown.

This is a single-crossing trim policy, not a continuous drawdown cap: it acts only on a currently losing eligible leg at a new25% crossing. It deliberately does not keep selling after the crossing, reset the global peak or prohibit future original entries while underwater. Changing exposure changes later capital, sizes, native TP quantities and SOL opportunities; a stronger first trim can therefore worsen subsequent drawdown. The combined native test measures the complete policy effect; isolated per-action causal PnL is not identified.

## Verification and reproducibility

100 focused native lifecycle tests passed (13.09s), independent scoped source review GO after one P1 priority correction. Both candidates complete all1,051,200 source rows per asset,1,051,199 settled receipts, zero unavailable receipts and zero terminal positions/open orders/liquidations.87 source/input checks pass; independent validation passes44 result checks and9 fee-bucket checks for each. All13 inputs match archived S0. Exact commands/config/source/input hashes, launch receipts, result manifests, native action audit and frozen attempt budget are retained in this directory.

Economic JSON/CSV: `economic-validation-s0.json`, `economic-validation-s0-monthly.csv`, `economic-validation-m1.json`, `economic-validation-m1.csv`, `economic-validation-m2.json`, `economic-validation-m2.csv`, consolidated `comparison.json` and `comparison.csv`; report-only saved-output validator `economic-validation-validator.py`. Candidate raw native artifacts, minute receipts and separate funding journals remain under the immutable VPS job paths pinned in completion receipts. GitHub source CI readback shows0 check runs and0 Actions runs; local tests and native result validation are the available verification. No new CI was triggered. These are historical `NOT_FAITHFUL_DIAGNOSTIC` results, not independent out-of-sample or Hyperliquid live ROI evidence. Signed funding and tick drawdown remain explicit unknowns.

S0 engine executions added:0. Production/pilot deployments, restarts and external orders:0. Both native jobs have finished; the final report and existing Project #123 close as a completed negative experiment. The DD50/netprofit90 economic goal remains unachieved. No new simulations are running or planned in this scope.
