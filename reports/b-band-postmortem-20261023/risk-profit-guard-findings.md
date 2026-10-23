# Fixed profit-to-breakeven partial guard: saved-state precheck

**Mechanism is not rejected by this precheck, but it is NOT_RUN and not approved for implementation or economic acceptance.** The fixed1% favorable excursion → later closed-minute gross-VWAP return → one20% remaining-quantity reduction has opportunities in the first two remaining maxima and three prior losing BTC parents inside the last excursion. It does not directly protect the final August19 long trough, misses several important losing parents, and also reduces many positions that later recover. No resulting native TOTAL/DD or profit-retention estimate is produced.

## Fixed contract and bounded method

One additional read of B's existing1,051,199 settled receipt rows only; no S0 reread, prices fetched, replay, native engine, synthetic cash/equity curve or alternate account. Native fill audit is matched to native fills by asset, exact fill timestamp, quantity and price normalized to0.0001 for matching only; each price difference is separately asserted<0.000001, addressing floating serialization ULPs. Native side establishes inventory cycles. All77BTC parents reach their actual native target quantity; completion is the final entry fill timestamp. All23SOL flat-to-flat native inventory cycles remain in the outputs, including partial/canceled native IOC attempts and daily later additions.

Arming requires a completed BTC parent, an actually held native leg and a completed source close>=1% favorable from its **actual native VWAP**, before any observed profitable ordinary native reduction. A strictly later close returning to/through gross VWAP creates the single opportunity per cycle. This uses native mark precision BTC0.1/SOL0.01 and preserves actual receipt timestamps separately from one-minute-earlier source marks. Quantity is20% of actual remaining quantity, rounded downward BTC0.001/SOL0.1. Hypothetical exit price is gross VWAP rounded to native tick; fee0.055%. Gross VWAP does not cover entry/exit fees and is not economic breakeven.

**SOL parent semantics remain UNKNOWN:** the strategy has repeated SOL_ADD attempts rather than BTC's explicit split parent. This diagnostic treats a terminal native increase attempt as a completed phase, and resets arming when actual VWAP changes; it never pools favorable movement across changed VWAP phases. A fired opportunity remains once per flat-to-flat cycle. Future SOL adds would still exist in the baseline and must be reconciled with any prospective no-readd rule. These are conditional SOL opportunity counts, not proof that a separately specified strategy-parent implementation would produce them.

Saved native output does not export B per-cycle settled asset net PnL or signed funding. Therefore exact B net-winner counts are **UNKNOWN**. The report gives direct native profitable ordinary reductions and favorable/adverse final-close **price labels**. These are not net-winner substitutes; in particular a favorable last close need not make an entire multiply reduced/added cycle profitable. Original S0 episode labels remain explicitly labeled S0 only.

## Full-history cohort, no outcome-based threshold selection

| Asset | All native cycles | Cycles arm>=1% before profitable ordinary reduction | Later return opportunities | Opportunities with later actual profitable ordinary reduction | Favorable final-close gross price among opportunities |
|---|---:|---:|---:|---:|---:|
| BTC |77|45|26|14|14|
| SOL |23|23|17|2|15|

Every cycle is retained in `risk-profit-guard-cycles.csv`; each opportunity and its baseline recovery context is in `risk-profit-guard-counterexamples.csv`. Twenty-five of the43opportunities lie inside previously saved>=20% baseline excursions that eventually recover. This count is a baseline overlap diagnostic, not the number of independent recoveries or an intervention result. No phase is excluded because its original outcome is inconvenient.

BTC67's corresponding B cycle50 is an immediate counterexample to assuming these guards remove only losers: it triggers November26 14:41UTC, then the original short endures a squeeze and recovers without another native fill before December1. Fourteen BTC opportunities later receive actual profitable ordinary native reductions. Original SOL1's corresponding B cycle1 triggers October3 07:53UTC and later recovers; its last gross close is favorable. Cutting20% suppresses part of the upside as well as downside. All six mandatory historical counterexamples are mapped in `risk-profit-guard-mandatory-counterexamples.csv`: BTC29 is matched without an opportunity; BTC40/41/96 have no same-day B parent; BTC67 and SOL1 have opportunities. Their positive historical ex-funding labels are original S0 labels, never claimed as B net PnL.

## Three remaining maxima: conditional scale at their unchanged original troughs

The following is **ORACLE/conditional fixed-state scale**, holding original trough prices and original peak fixed. It assumes the20% lot-normalized amount could exit at normalized gross VWAP, charges only its new0.055% exit fee, and compares that hypothetical quantity's mark value with the original trough. It is not a policy replay, native account, change in resulting DD or prediction of final capital. The actual first close through VWAP usually overshoots; a market order placed after receipt cannot claim the earlier VWAP fill.

| Original excursion | Guard leg and quantity | Fixed trough difference after hypothetical new exit fee | Original50% endpoint gap |
|---|---|---:|---:|
|1 Oct3 2024|SOL long200 at140.09|+1,368.59010000|1,118.351784370|
|1 same|BTC short0.188 at60,887.2|−133.628136480|same gap|
|2 Nov28 2025|BTC short28.147 at87,414.9|+154,294.023645335|80,294.075251445|
|3 Aug19 2026|Current BTC long321.238|No eligible opportunity before trough|31,658.054690925|

For excursion1, the BTC opportunity occurs October2 20:54 source/20:55 receipt, **before the original October3 peak**; SOL occurs October3 07:53 source/07:54 receipt after arming01:25. The fixed original-trough BTC+SOL scale is+1,234.96196352, greater than the fixed50% gap, but the original peak itself would change and later position adds/exits remain baseline assumptions. Thus this does **not** establish resulting DD<=50. The first SOL return close is139.97, below VWAP140.09, showing the gross-VWAP exit assumption is favorable.

For excursion2, the opportunity occurs November26 14:41 source/14:42 receipt, before the squeeze. The BTC-only conditional scale is roughly1.92times its fixed50% gap. The later native position recovers, so the withheld28.147BTC would also lose recovery gains. The C-window peak already had approximately+1.30% price excursion from entry; no threshold was selected from that observed outcome. Excursion1 SOL peak had approximately+1.96%, likewise a descriptive check, not threshold optimization.

Neither endpoint diagnostic addresses DD30 acceptance: gaps to30% remain4,067.043329338 /423,553.737641323 /1,489,722.675645295; the proposed20% partial at gross VWAP is much smaller in scale for the first two unchanged peak/trough cases, and the third cannot be derived by a fixed-current-position shortcut.

## Last excursion: every overlapping BTC parent, not just the ones that work

Dates/MFE here use actual completed parent and its own native VWAP; no averaging across different parents. Exact completion/arming/opportunity timestamps are in `risk-profit-guard-D-parents.csv`.

| Entry | Side | Maximum favorable completed-close excursion | Eligibility/opportunity before final exit |
|---|---|---:|---|
|Jul4|short|2.0541%|Already profitable ordinary reduction July4 01:26; disqualified despite later adverse final close.|
|Jul14|short|0.1497%|Never arms.|
|Jul15|long|0.9226%|Never arms.|
|Jul21|long|2.3920%|Arms Jul21 07:37; returns Jul23 07:14;20% actual252.801→50.560 eligible.|
|Jul27|long|0.5958%|Never arms.|
|Aug1|short|1.0513%|Arms Aug1 18:32; returns Aug2 01:15;20% actual274.429→54.885 eligible.|
|Aug13|short|1.5774%|Arms Aug13 16:42; returns Aug13 22:09;20% actual271.865→54.373 eligible.|
|Aug19|long|8.1857% over full cycle|No opportunity before its06:14 trough; later ordinary profitable reduction14:39 prevents a later guard.|

Thus three of the six newly entered, final-price-losing BTC parents after the July6 peak possess a qualifying return; three never arm. The July4 carried parent is separately disqualified. The final August19 winner's maximum favorable excursion happens **after** the original trough and cannot protect that earlier drawdown. The proposal targets some accumulated-loss channels but does not cover every loss. No fixed-trough value is manufactured for earlier closed parents that are absent at the final trough.

## Decision boundary and checks

This precheck supports writing a **prospective NOT_RUN protocol** for the fixed idea; it does not select implementation, certify DD50/DD30, clear the>=90% retained-profit gate, or authorize a native run. SOL parent/cycle eligibility and additions-after-guard need explicit semantics; native receipt→order timing, reduce-only rounding/partials, fees and no-readd behavior need actual native validation. The promising endpoint scale and the recovery counterexamples must travel together. No blanket permanent cut, scalar latch or timer restoration is recommended here.

Checks: exactly1,051,199B settled rows scanned once; all484native fill-audit rows mapped to native side with quantity/time/price consistency;77BTC full-parent quantities asserted; settled trace SHA preserved and checked against prior manifest; every generated opportunity precedes its first observed profitable ordinary reduction; cached extraction reused for all original peak/trough/gap/recovery comparisons. No native economic account was created.
