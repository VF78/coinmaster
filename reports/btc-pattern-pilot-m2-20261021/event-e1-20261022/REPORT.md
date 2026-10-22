# E1: no demonstrated incremental forecast value

**E1_NO_DEFINED_IMPROVEMENT.** Phase-aligned analogues fail the frozen gate: neither co-primary metric improves reliably against each of prior, state and matched-clock controls. All six primary 14-day paired confidence intervals include zero. E2/E3: **SKIPPED_GATE_FAILED**.

The full 699-day catalogue covers 2024-06-01 through 2026-05-01 (exclusive), with 372 confirmed event queries. The original three evaluation folds contribute **198 common mature IDs**: F1=64, F2=67, F3=67. The catalogue retains horizon-censored and unfinished events. Every arm scores those same 198 IDs, including fallback and NO_TRADE; supported coverage is 100% for all arms and fallback count is zero.

| Arm | TP pinball ↓ | Full72h SL-touch Brier ↓ | NO_TRADE |
|---|---:|---:|---:|
| prior | 0.251328600 | 0.205720813 | 198 |
| state | 0.254249477 | 0.206759087 | 90 |
| clock | 0.255151223 | 0.206613041 | 123 |
| phase | 0.254298512 | 0.207298580 | 122 |

Relative to the empirical event prior, phase TP pinball is **+1.18% worse** and SL-touch Brier is **+0.77% worse**. These are relative changes in forecast errors, not percentage-point changes in reach rates.

## Fixed SL=1σ72 accuracy on all 198 IDs

TP1/TP2/TP3 are predicted q20/q50/q80 levels of MFE before SL. Percentages below are positive-level reaches before SL; each cell shows conservative lower–upper intraminute bounds and its denominator. Levels differ by forecast arm, so reach rates alone do not measure forecast superiority. Proper losses above compare forecast accuracy on the same target population. All SL=1 TP levels are positive: zero-level count=0 in every cell.

| Arm | Side | TP1 lower–upper (N) | TP2 lower–upper (N) | TP3 lower–upper (N) | SL-touch predicted | SL-touch observed |
|---|---|---:|---:|---:|---:|---:|
| prior | long | 80.30%–80.30% (198) | 46.97%–46.97% (198) | 21.21%–21.21% (198) | 30.06% | 33.84% |
| prior | short | 81.82%–81.82% (198) | 55.56%–55.56% (198) | 22.22%–22.22% (198) | 32.28% | 31.82% |
| state | long | 79.80%–79.80% (198) | 43.94%–43.94% (198) | 19.70%–19.70% (198) | 30.75% | 33.84% |
| state | short | 83.84%–83.84% (198) | 55.05%–55.05% (198) | 22.73%–22.73% (198) | 34.21% | 31.82% |
| clock | long | 76.77%–76.77% (198) | 44.44%–44.44% (198) | 21.21%–21.21% (198) | 29.75% | 33.84% |
| clock | short | 81.31%–81.31% (198) | 56.06%–56.06% (198) | 23.23%–23.23% (198) | 33.32% | 31.82% |
| phase | long | 77.78%–77.78% (198) | 44.95%–44.95% (198) | 20.20%–20.20% (198) | 30.11% | 33.84% |
| phase | short | 80.30%–80.30% (198) | 56.57%–56.57% (198) | 22.73%–22.73% (198) | 33.36% | 31.82% |

SL-touch means the adverse barrier was touched anywhere in the full 72 hours, irrespective of TP exits. It is not an actual traded stopout. TP reach bounds are separate marginal path targets, not the success rate of a joint partial-exit trade. Full .75/1/1.5 SL results, positive denominators, zero-level mass, calibration bins and row losses remain in RESULTS.json and accuracy.csv.

## Frozen paired comparisons

Negative deltas favor phase. The gate requires both co-primary metrics against every control: upper95% CI<0, improvements in at least two of three folds, at least two occupied blocks per fold, plus ≥90% supported coverage for every learned arm.

| Comparator | Metric | Phase−control | 14d 95% CI | 28d 95% CI | Primary pass |
|---|---|---:|---|---|---|
| prior | TP | +0.002969912 | [-0.001778294, +0.007600101] | [-0.002326472, +0.006659175] | False |
| prior | SL | +0.001577768 | [-0.001421752, +0.004202916] | [-0.001883599, +0.003825761] | False |
| state | TP | +0.000049036 | [-0.004912251, +0.005211546] | [-0.005639881, +0.006247492] | False |
| state | SL | +0.000539493 | [-0.003074195, +0.004258406] | [-0.003244295, +0.004892850] | False |
| clock | TP | -0.000852710 | [-0.002815203, +0.001250700] | [-0.002815507, +0.000988518] | False |
| clock | SL | +0.000685539 | [-0.000753815, +0.002295918] | [-0.000322025, +0.001902457] | False |

Intervals use within-fold occupied UTC blocks, 1,000 draws and seed7. All three folds have 9/10/9 occupied 14-day blocks respectively. This remains exploratory evidence on previously studied DEVELOPMENT. Event-selected query IDs compare conditional information; they do not identify an advantage of event timing or sampling over a common calendar population.

No economic return, ROI, drawdown, cost-adjusted trading benefit or native execution performance was evaluated. No neural/API/LLM forecasts, new training, parameter search, CHECK/VPS/pilot changes, or market rerun were performed. E2 and E3 were skipped because the preregistered improvement gate failed.

## Reproducibility

`export_saved_results.py` reads only the immutable saved RESULTS.json and regenerates this report, case_arm_forecasts.csv (792 case×arm rows with all18Q/6SL and truth/IDs), accuracy.csv (all side/SL/TP reach bounds), and comparisons.csv. It does not load prices, targets, models or the evaluator. Protocol, catalogue, source/test pins and single-run completion evidence are saved alongside these files.
