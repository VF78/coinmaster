# D90 saved-output failure decomposition

Analysis only: the script reads saved RESULTS, PROTOCOL and PREFLIGHT JSON and performs arithmetic on existing predictions/errors. No model, forecast, target, pool, detector, catalogue, market data, resampling or economic evaluation is run. All 198 IDs match PREFLIGHT exactly; the full 699-day/372-event source universe is preserved. Prior files are unchanged.

## What failed, exactly

D90 minus prior mean loss is **+0.003107262 TP** and **+0.002875528 SL**. Each fold is worse for both targets. This rejects the preregistered improvement claim; the primary 14-day intervals cross zero, so it is not a blanket statistical proof that D90 is worse in every population. Existing phase comparison is TP −0.001032604, SL +0.001310577: it also fails the requirement to be nonworse on both. No scores for a newly blended or altered forecast are produced.

| Saved-output partition | TP delta within partition | TP contribution to total | SL delta within partition | SL contribution to total |
|---|---:|---:|---:|---:|
| F1, 64 IDs | +0.001465843 | +0.000473808 | +0.000297302 | +0.000096098 |
| F2, 67 IDs | +0.001500683 | +0.000507807 | +0.003307950 | +0.001119357 |
| F3, 67 IDs | +0.006281762 | +0.002125647 | +0.004905888 | +0.001660073 |

F3 contributes 68.4% of net TP damage and 57.7% of net SL damage. F2 adds 38.9% of net SL damage. This is retrospective attribution, not an explanation proved causal.

## TP damage: upper quantiles, especially short

Q20/Q50/Q80 contribute +0.000066354/+0.000589827/+0.002451081 to total TP delta. **Q80 is 78.9% of net TP damage**. Short forecasts contribute +0.001994163 (64.2%); long +0.001113099. The largest coordinate is short, SL1.5, Q80: within-coordinate delta +0.013324418 and total contribution +0.000740245. Short Q80 at SL0.75 and SL1 each add +0.000574995. Together those three short Q80 coordinates contribute 60.8% of total net TP damage.

All three SL partitions worsen TP: contributions +0.000891138 (0.75), +0.001029867 (1), +0.001186256 (1.5). F3 short alone adds +0.001476370, 47.5% of total TP damage. March–April 2026 add +0.002311596, 74.4% of net TP damage, with improvement in other months offsetting some damage. These overlapping cuts must not be added to each other.

## SL damage: stronger variation without useful timing alignment

For every saved query-coordinate, set a = p_D90 − p_prior. The exact identity is:

`Brier_D90 − Brier_prior = a² + 2a(p_prior − y)`.

Across all six coordinates and 198 queries:

* Adjustment-square cost: **+0.000861311** (30.0% of net excess loss).
* Residual-alignment term: **+0.002014217** (70.0%). Positive means the adjustments align with prior errors in the harmful direction on average.
* Sum: **+0.002875528**. Every coordinate identity is checked to floating-point tolerance.

F1 has a helpful alignment term −0.000167225, insufficient to cover adjustment-square +0.000464526. F2 and F3 alignment terms are harmful (+0.002273706/+0.003838493). Their larger changes therefore do not earn an offsetting alignment benefit.

A second exact decomposition, separately within each side×SL coordinate, is `Brier = ybar(1−ybar)+(pbar−ybar)²+Var(p)−2Cov(p,y)`. Averaged across the six coordinates:

| Component | Prior | D90 | Change in loss |
|---|---:|---:|---:|
| Mean calibration bias squared | 0.000756913 | 0.000754507 | −0.000002406 |
| Probability variance | 0.000507509 | 0.002108390 | +0.001600881 |
| −2 covariance with outcome | 0.002118731 | 0.003395783 | +0.001277052 |

Probability variance rises 4.15×. The mean bias barely improves, while covariance alignment deteriorates. Mean calibration alone would miss the failure. This decomposition is descriptive; it is not a reliability/resolution estimate from a newly fitted calibration model.

Every SL threshold has positive net damage: +0.000959851/+0.001014898/+0.000900778 at 0.75/1/1.5. Both sides worsen. F2 long contributes +0.000985977; F3 short +0.000962046; F3 long +0.000698027.

## Tiny early support is not the main culprit

The two n=2 queries have conditional component weight 2/(2+32)=5.88%; **they improve** TP by −0.027929862 and SL by −0.010932174 per query on average, contributing −0.000282120/−0.000110426 to the totals. Removing them is neither proposed nor scored.

The 114 queries with cell count ≥64 have mean conditional weight 73.05% and contribute **+0.002460886 TP (79.2% of net damage)** and **+0.002548575 SL (88.6%)**. F2/F3 each average approximately 71.75% conditional component weight; F1 36.10%. The actual recorded problem is concentrated in substantial, heavily weighted historical cells, not primarily the earliest two-label cell. Support and time/fold grow together, so this is not proof that higher weight itself causes worse performance.

The formula is a mixture of empirical distributions, with same-state labels also present in the global pool. Conditional component weight is n/(n+32); it is not the full mass on same-state labels and not an effective independent-cycle count. SL probabilities follow that distribution mixture linearly; empirical quantiles need not be linear mixtures of prior/cell quantiles. Fixed pseudo-weight32 regularizes label counts, but does not ensure that historical same-sign labels remain relevant across time.

## Prior calibration and the limits of the state explanation

At SL1, for positive-state queries, long observed touch frequency is 31.11%; prior predicts 29.07%, D90 24.61%. D90 moves away from the observed conditional rate. For negative-state queries, long observed is 36.11%; prior predicts 30.54%, D90 34.12%. That group mean moves closer, yet Brier worsens 0.238913693→0.240143850. For negative-state short, prior/D90/observed are 32.34%/32.74%/33.33%; again mean bias improves but Brier worsens 0.228988241→0.234725372. Some mean state alignment exists; useful query-level error reduction is not demonstrated.

F1 has 31 negative/33 positive queries, F2 10/57, F3 67/0. Hence the negative-state excess TP loss (+0.004886390 versus +0.000972307 positive) overlaps heavily with F3; it cannot isolate a causal sign-state effect. Repeated historical event labels and overlapping state histories are not independent 90-day cycles. The source 14/28-day block intervals do not establish robustness over 100–200-day waves.

Damage is not confined to one anomalous query: 112/198 TP and 108/198 SL query deltas are harmful; the ten worst account for 20.9%/20.0% of gross harmful contributions. Saved per-query rows and month summaries expose this concentration without dropping or replacing IDs.

## Why sign90 is not a wave/correction representation

The implemented feature retains only whether `log(close_last_completed_day / close_90_days_earlier)` is positive or negative. Magnitude is saved for reporting but is not used to form the conditional cell. It does not encode the path between endpoints, wave start/peak/trough, leg ordering, elapsed leg age, expansion amplitude, retracement depth, correction stage, or the relationship of a recent correction to its preceding rise. A strong rise followed by a deep correction and a steady smaller rise can share the same positive sign; a recovery after a large fall can remain negative. This many-to-one mapping is an arithmetic information loss, not empirical proof that adding those features would improve predictions.

The test therefore establishes failure of this fixed sign-conditioned empirical prior at unchanged event origins. It does not establish that the 90-day state causally explains the failures, nor test a complete growth-plus-correction wave model. Future wave proposals require their own explicit semantics and authorization; no such experiment is performed here.

## Algebra appendix: uniform shrinking of the saved SL correction

This is an identity derived from the saved corrections, not a new forecast evaluation or a selected weight. Let `a = p_D90 − p_prior`, and apply the same scalar λ to every saved SL query-coordinate: `p_λ = p_prior + λa`. Expanding the square and averaging over the unchanged 198×6 coordinates gives:

`ΔBrier(λ) = E[(p_prior + λa − y)² − (p_prior − y)²]`

`= λ² E[a²] + 2λ E[a(p_prior − y)] = Aλ² + Bλ`,

where the already computed saved-output coefficients are **A = +0.000861310750916515** and **B = +0.0020142168435155587**. Both are positive, so `ΔBrier(λ) > 0` for every `λ > 0`. At λ=0 the correction vanishes and equality holds. For probability-preserving convex blends, `0 < λ ≤ 1`, the same conclusion follows directly. No new λ-specific accuracy score, sweep, fit or optimal λ is calculated.

Thus uniformly shrinking this exact saved SL probability correction cannot turn its aggregate saved-sample Brier difference into an improvement. Another run that only applies that same uniform shrinkage would not resolve the failed SL gate. This statement does **not** cover pseudo-count grids (whose effective shrinkage varies with cell support), state-dependent rules, changed forecasts, TP quantiles, other models, future samples or general causal claims.

## Reproducibility

Run `python3 stats-replay.py` in this directory (or provide its absolute path). The standard-library script checks all ordered IDs, recomputes the existing TP aggregate losses, checks the saved SL delta and both Brier identities, and records SHA-256 of the three input JSON files. `stats-results.json` contains grouped machine-readable results and limitations. `stats-query-deltas.csv`, `stats-tp-coordinates.csv`, `stats-sl-decomposition.csv`, `stats-calibration.csv`, and `stats-group-summary.csv` expose the underlying arithmetic. Partitions are exploratory and correlated; no new significance tests or adjusted forecasts are introduced.
