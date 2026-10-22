# D90: bounded retrospective result

**FAIL — no defined improvement.** Both primary errors exceed the common-causality global prior in every fold. D90 improves mean TP loss versus phase but worsens SL; both acceptance requirements fail. No automatic follow-up run.

| Arm | TP pinball18 | SL touch Brier6 | Supported | Fallbacks |
|---|---:|---:|---:|---:|
| prior | 0.253341553 | 0.207860587 | 100% | 0 |
| phase | 0.257481419 | 0.209425537 | 100% | 0 |
| daily90 | 0.256448815 | 0.210736115 | 100% | 0 |

Differences below are D90 minus control; negative favors D90. Paired within-fold UTC blocks,1000 draws,seed7.

| Control | Loss | Mean delta | 14d95%CI | 28d95%CI | Folds improved |
|---|---|---:|---|---|---:|
| prior | TP | +0.003107262 | [-0.000334106,+0.006265205] | [-0.000341111,+0.006145439] | 0/3 |
| prior | SL | +0.002875528 | [-0.000131753,+0.005722369] | [+0.000205983,+0.005332311] | 0/3 |
| phase | TP | -0.001032604 | [-0.005933592,+0.004599992] | [-0.005532260,+0.004650207] | 2/3 |
| phase | SL | +0.001310577 | [-0.002431942,+0.005210570] | [-0.001963416,+0.005326137] | 1/3 |

Full699-day [2024-06-01,2026-05-01) catalogue372events preserved; all198 original scored IDs retained (64/67/67 byfold), no drops or replacements. Same corrected stricter causal historical pool for all3arms. Phase comparator here is recomputed on that pool and must not be conflated with the earlier E1 result.

| Fold | Query negative/positive | Eligible global min–max | Same-state cell min/median/max |
|---|---:|---:|---:|
| F1 | 31/33 | 65–108 | 2/24/29 |
| F2 | 10/57 | 164–199 | 57/78/102 |
| F3 | 67/0 | 249–300 | 57/86/101 |

All cells nonempty; earliest two-label cell receives only2/34=5.88% conditional weight. Missing historical90d states remain in the eligible global pool. Global pseudo-weight32 and shared weights for every target were fixed before this run. Counts are historical event labels, not independent long cycles.

The preregistered prior gate requires both errors to improve, paired14d upper95%CI<0 and≥2/3fold improvements; neither loss improves in anyfold. Phase nonworse aggregate requirement also fails forSL.14d occupied blocks9/10/9;28d5/6/5.

case_arm_forecasts.csv contains594 rows (198IDs×3arms), every18Q/6SL and truth. accuracy.csv contains54 side×SL×quantile rows, coordinate pinball,SLBrier,actual touch frequency,quantile hit rates and positive-level TP reach bounds/counts. Quantile hit uses truth_lower≤forecast, reach uses truth_bound≥forecast; equality is intentional. Zero TP levels remain in proper losses but are excluded from positive reach denominators; zero counts are explicit. RESULTS.json retains calibration bins, upper-MFE sensitivity, fold/state summaries, all predictions and support pools.

For SL=1×query sigma72, the actual TP reach frequencies before that barrier are shown below. TP1/2/3 use forecast quantiles20/50/80, whose nominal exceedance targets are80%/50%/20%. Each query has its own forecast price levels; these are calibration frequencies across198 changing forecasts, not the success rate of a fixed-price or traded policy.

| Arm | Side | TP1 reach (nominal80%) | TP2 reach (nominal50%) | TP3 reach (nominal20%) | Positive N per TP |
|---|---|---:|---:|---:|---:|
| prior | long | 79.8% | 44.9% | 20.2% | 198/198/198 |
| prior | short | 82.3% | 56.6% | 22.2% | 198/198/198 |
| phase | long | 78.3% | 43.9% | 21.2% | 198/198/198 |
| phase | short | 81.8% | 56.6% | 21.2% | 198/198/198 |
| daily90 | long | 81.3% | 44.4% | 19.7% | 198/198/198 |
| daily90 | short | 84.3% | 55.1% | 21.7% | 198/198/198 |

All displayed levels are positive; lower/upper intraminute reach bounds coincide for these SL=1 rows. Both directions are evaluated on every query; this table does not select a trade side. For D90, full72h adverse SL-touch probability/observed frequency is29.8%/33.8% long and33.7%/31.8% short. Full72h adverse touch is a distinct target from TP-before-SL reach and is not an actual trade stopout.

Single run2.913s;370 mature target paths computed once,198 saved query truths exactly verified/reused and172 missing library truths computed with unchanged targets().370mature+2right-horizon-censored catalogue events; only original198 fold-mature queries scored.20focused tests pass and scoped preflight review passed. No rerun.

Retrospective selected hypothesis after E1 postmortem; not independent confirmation
Daily state is fold-confounded; F3 has no positive90 state
14/28d bootstrap cannot establish 100–200d cycle robustness
Adverse touch is not traded stopout; no ROI/DD evaluation

The negative result applies to this fixed daily90 sign conditional prior at the unchanged hourly event origins. It does not test or reject a complete growth-plus-correction macro-wave model. No economic/native execution or ROI/DD evaluation was performed; pilot,VPS,S0,CHECK and trading code were untouched.
