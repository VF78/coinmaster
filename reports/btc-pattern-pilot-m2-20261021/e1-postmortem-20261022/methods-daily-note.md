# Daily waves and hourly event forecasts: methodological boundary

2026-10-22. Read-only interpretation of the existing source and saved descriptive daily-context audit. No new forecast, training, target calculation or backtest. The full `[2024-06-01,2026-05-01)` 699-day catalogue and all 198 original scored IDs remain; pilot and CHECK are untouched.

The owner's proposed hierarchy is meaningful: a daily growth/fall plus correction cycle may provide context for an hourly event whose next 72-hour TP/SL outcome is being forecast. Daily context and hourly query timing are different roles. The current E1 did not test complete 100–200-day waves, so its failed shape gate cannot reject that idea.

## Completed daily cycle versus observable prefix

A full growth/fall plus correction wave can be annotated retrospectively for descriptive purposes or as a training outcome once its endpoint is confirmed and mature. Its final duration, ultimate extreme, total amplitude and position within that final cycle are not available at an intermediate hourly query. Query features must use only the daily prefix observable then. Daily bars must be completed UTC days; an hourly query cannot use that day's eventual daily close.

The same maturity rule applies to library cycles: historical completed-wave outcomes may be used only if the endpoint/confirmation and any target horizon precede the applicable training cutoff and query support boundary. A hindsight label such as “this is day 120 of a 170-day rising wave” cannot be substituted for a causal prefix state. Completed and ongoing/censored waves must be kept distinct; selecting only successful completed cycles changes the target population.

## What the saved daily audit establishes

All 198 original evaluated origins have genuine causal 90/180-day return context and the reference EMA34 state. Across the full 699-day catalogue, 73 daily dates lack a genuine 90-day return and 163 lack a 180-day return, because only 17 genuine warmup days precede June 1. These are unavailable states, not permission to truncate the period, fabricate warmup, or fetch more history.

The EMA34-sign reference has 63 runs, 61 complete; complete-run median 4 days, p90 31 days, maximum 72 days, and no 100–200-day run. It therefore does not identify the owner's full growth-plus-correction waves. It is useful only as a causal descriptive daily state.

Among E1 queries, daily EMA-down state has 115 IDs with E1−prior TP/SL losses −0.00057672/−0.00039955; EMA-up has 83 with +0.00788393/+0.00431742. TP underperformance in EMA-up recurs by fold, but SL has a fold exception. Some four-cell calibration residuals reverse strongly after conditioning on this daily reference. Consequently the earlier direction×volatility four-cell mechanism may be confounded by daily state. It should not automatically be expanded to eight cells. Correlation of 90/180-day return with E1 TP excess loss is only about .082/.070; neither establishes an effective long-wave predictor.

## Sample size and dependence

Only 3.5–7 nominal 100–200-day durations fit inside 699 days; this arithmetic is not a count of actual completed cycles. Boundaries, unfinished corrections and the causal confirmation rule can reduce the number further. The saved 198 hourly events are not 198 independent long-wave examples. The daily reference places them in 35 runs, with a median of 3 and maximum of 29 events per run; even those reference runs are not independent complete cycles.

Four-month folds can contain only part of one long wave. A 14/28-day block bootstrap may quantify short-range event variation but cannot establish robustness across 100–200-day cycles. Any future full-cycle claim must disclose actual completed/censored cycle counts and dependence, rather than reporting only hourly-query counts. The unchanged 699-day sample limits what can be established without an expanded study, which is not authorized here.

## Strict support materially constrains the next hypothesis

An ordinary recursive EMA34 retains numerical dependence on its seed and all subsequent prices. If query support is correctly recorded from the genuine May15 seed, the original strict label/query-feature disjointness would leave no eligible historical label at all. Calling it a 34-day feature would be incorrect. A finite-window EMA would be a different, separately frozen feature; alternatively relaxing purge is a different research contract. Neither should be introduced silently because the saved EMA grouping looks favorable.

A fixed 90- or 180-day log-return sign has finite, transparent support. At query origin use the most recent completed daily close and the close exactly 90/180 days earlier; include the raw start of that earliest daily bar in support. Every arm must use the common stricter boundary, along with the corrected frozen-threshold dependency. Historical events without the requisite causal daily prefix cannot enter a state-specific cell, but may remain in the global prior if otherwise eligible. Every query remains, with an explicit global-prior fallback for an undefined or empty state.

There is a real cost: genuine 180-day state first exists around November 2024, while the F1 query's earliest 180-day input lies in July–October2024. Under strict purge no F1 historical event with a defined 180-day cell can qualify, so F1 must fall back. A 90-day state begins around August 2024 and leaves some scope for F1 cell support. These are logical support consequences, not measured performance of either candidate.

## One simple next hypothesis, not a cascade

The single fixed candidate is **a two-state prior conditional on the sign of the trailing 90-day completed-D1 log return**, at the unchanged hourly event origins. State is up for return>0 and down for return<0; an exact zero, unavailable prefix or empty eligible cell falls back to the global prior. This fixed horizon uses a substantial daily prefix while preserving more eligible early-history support than 180 days; it is not a retrospectively selected best-performing horizon. The 180-day context remains descriptive only, with no competing candidate or grid.

Build two empirical historical outcome distributions and shrink with the fixed 32 global-prior pseudo-observations. This replaces the four-cell proposal rather than adding another split. Use one historical label-weight vector for all outcomes, producing ordered 18 TP quantiles and six adverse-touch probabilities. Undefined historical state is excluded from the conditional cell but remains eligible for the global pool; all 198 original queries stay in the denominator. Report actual cell support and effective weights before interpreting results, and apply the common stricter 90-day feature support to both global-prior and original E1 controls.

The hypothesis is that this one finite daily state carries conditional information relevant to next 72h TP/SL at existing H1 events. No completed macro-wave label, phase within a future full cycle, new lower-timeframe model or change in event timing is introduced. Acceptance must require both proper losses to beat the same-causality global prior with paired criteria, not merely replicate a selected subgroup contrast.

The fixed 90-day diagnostic has pooled negative-state N=108 with E1−prior TP/SL−0.00039465/−0.00068876, and positive-state N=90 with +0.00700738/+0.00429761. This is preliminary support for a bounded daily-context diagnostic, not an estimated result of the proposed conditional prior. Its fold breakdown weakens any claim of a stable mechanism. Negative/positive query counts are F1 = 31/33, F2 = 10/57, F3 = 67/0; F3 contains no positive-state query. E1 TP excess loss for negative/positive states is F1−0.000770/+0.001795, F2−0.005871/+0.010025, and F3+0.000596/unobserved. SL favors negative state in F2, but both F1 states have negative E1 excess loss. Thus the grouping is strongly associated with time/fold, and does not independently identify daily trend as the cause of E1 failure. No positive new-model result follows.

Saved-ID support bookkeeping using the exact completed-D1 endpoint minus 91 days for earliest raw-bar support gives same-state eligible classified-library counts: F1 minimum 2 / median 24 / maximum 29; F2 57/78/102; F3 57/86/101. No query has an empty same-state cell under this check. These are available label counts, not independent cycles. Total eligible historical events with a valid 90-day state have min/median/max 25/53/68, 124/147/159, 209/245/260 by fold; the global prior can additionally retain otherwise eligible events whose early daily state is unavailable. With 32 global pseudo-observations, a two-event F1 cell receives only 2/34 weight. Report this weak early conditioning openly rather than claiming uniform learned support.

The daily reference's saved grouping supports investigating daily context, but does not establish the fixed 90-day sign's information value. The owner’s complete 100–200-day wave idea therefore remains a separate descriptive/maturity question; a two-state context experiment must not be advertised as validating it. If the fixed 90-day diagnostic is weak or its eligible support is inadequate, the honest next step is a frozen descriptive causal-prefix catalogue, with no forecast run justified yet.

The earlier tiny global-shrinkage diagnostic remains insufficient to justify a new run. No independent or economic benefit has been established for any proposed replacement.
