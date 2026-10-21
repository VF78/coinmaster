# Fixed-model within-fold drift decomposition (descriptive, zero fits)

All8,496 retained original outer origins and every scored month are included. Each fold uses the same original CNN-refit/prior predictions on both calendar halves; no ES/refit model comparison. Existing causal30d regimes and original fit-only thresholds remain fixed. Source/protocol/data/forecast/ID hashes were captured before analysis. Runtime.528s; no new predictions, optimizer steps, fits or CHECK.

The table gives late-minus-early mean pinball on COMMON SUPPORT only; each row obeys Δ=mix+within. It does not silently attribute missing regimes.

| Fold/side | CNN Δ | mix | within | prior Δ | prior mix | prior within |
|---|---:|---:|---:|---:|---:|---:|
| F1 long |+.024638|−.008273|+.032911|+.027114|−.007746|+.034859|
| F1 short |−.119806|−.072574|−.047232|−.136379|−.074942|−.061436|
| F2 long |−.038705|−.039303|+.000598|−.037850|−.040362|+.002511|
| F2 short |+.142569|−.066914|+.209483|+.155837|−.070506|+.226343|
| F3 long |+.005118|−.009544|+.014662|+.006640|−.009941|+.016581|
| F3 short |−.199011|−.009315|−.189697|−.213731|−.008459|−.205272|

Support limits are material. F1 excludes35early UP_LOW origins: early coverage97.57%, late100%. F2 has only DOWN_LOW/UP_LOW in both halves, covering100% of observed rows but no high-volatility-regime evidence. F3 excludes485late UP_HIGH origins: early coverage100%, late64.55%. The full four-regime decomposition is UNIDENTIFIED; absent means were never set tozero. F3 long FULL observed Δ is−.011122, whereas common-support Δ is+.005118: full/common signs differ, so common effects cannot be projected onto the missing35.45% late population.

For Q-short, within-regime changes dominate the common-support movement in F2/F3; F1 has both mix and within contributions. Q-long F2 is mostly mixture, while F1/F3 common-support movements have opposing mix/within components. Prior shows similar broad patterns. A universal mix-only explanation is unsupported.

CDF coverage also changes within regimes: F3 originalCNN median long CDF common within contribution−.356837 and median short+.290736 (probability units). All per-quantile CDF/pinball components are retained in drift-decomposition.csv; these are descriptive, not causal effects.

14d block bootstrap uses1,000seed7 draws inside each half. Fixed common support survives640/999/909draws in F1/F2/F3. Frozen minimum800withholds all F1CIs. Remaining intervals are conditional on preserved common support. F3 common-support CNN-minus-prior Q-short deterioration+.014719 has CI[.001685,.027355]; F2 improvement−.013268 has CI[−.036315,.006957]. The result does not establish a better learning recipe.

Decision: NO-GO for a Q-only/exit-only fit, more epochs, or blind regime-mix reweighting in this pilot. Real D-vs-Q gradients lack consistent opposition; metric-off already failed; no epoch cap was reached; fixed-model decomposition shows within-regime drift as well as missing support. Full history remains preserved. A future change needs a separately justified, frozen hypothesis and exact root GO; none has been launched.
