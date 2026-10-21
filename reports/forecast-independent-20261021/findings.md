# Frozen independent forecasting CHECK results

One CHECK evaluation per frozen method on BTCUSDT/SOLUSDT Bybit linear execution OHLCV, 2026-04-01 through 2026-10-20 UTC. Each method has 9,696 mature forecasts and 48 explicitly censored forecasts. Hourly origins, next-minute entry, 24-hour horizon; no PnL engine.

All calibrated methods underperformed the TRAIN-prefix prior on aggregate forecast loss and direction log loss. CNN had the lowest calibrated pinball among fitted models, but its paired 14-day confidence interval versus the calibrated raw-feature control crosses zero and its actionable coverage is zero. These results do not establish a useful trading edge.

| Method | Raw lower pinball | Cal lower pinball | Raw / cal direction log loss | Direction accuracy | Actionable / 9696 |
|---|---:|---:|---:|---:|---:|
| control | 0.212843 | 0.215153 | 1.091187 / 1.086343 | 36.25% | 5 |
| stumpy | 0.213192 | 0.214897 | 1.092397 / 1.094730 | 37.29% | 223 |
| minirocket | 0.227832 | 0.228982 | 1.178555 / 1.089352 | 37.58% | 23 |
| rdst | 0.218842 | 0.220639 | 1.121466 / 1.088624 | 38.03% | 26 |
| cnn | 0.212336 | 0.214131 | 1.084779 / 1.084759 | 35.71% | 0 |
| TRAIN-prefix prior | 0.212019 | — | 1.080523 | 39.27% | — |

Lower losses are better. March calibration improved some direction losses but increased every method’s aggregate lower pinball relative to its raw prediction. The frozen raw JSON field `vs_raw_control` actually compares calibrated predictions against calibrated raw-feature control; it is named `vs_calibrated_control` in the export summary.

| Method minus calibrated control | Lower pinball difference | Paired 14-day 95% CI |
|---|---:|---|
| stumpy | -0.000256 | [-0.001902, +0.001313] |
| minirocket | +0.013829 | [+0.011388, +0.016325] |
| rdst | +0.005485 | [+0.002609, +0.008271] |
| cnn | -0.001022 | [-0.001948, +0.000038] |

Negative differences favor the method. STUMPY and CNN intervals include zero; MiniRocket and RDST are worse than control on this comparison. Overlapping 24-hour forecasts are summarized using 15 paired 14-day blocks with 1,000 fixed-seed bootstrap draws; this is a finite CHECK sample.

| Method | Asset | Actionable N | TP1 lower–upper hit | TP2 lower–upper hit | TP3 lower–upper hit |
|---|---|---:|---:|---:|---:|
| control | BTCUSDT | 0 | — | — | — |
| control | SOLUSDT | 5 | 80.0%–80.0% | 40.0%–40.0% | 20.0%–20.0% |
| stumpy | BTCUSDT | 49 | 75.5%–75.5% | 34.7%–34.7% | 6.1%–6.1% |
| stumpy | SOLUSDT | 174 | 73.6%–73.6% | 36.2%–36.2% | 9.2%–9.2% |
| minirocket | BTCUSDT | 7 | 85.7%–85.7% | 28.6%–28.6% | 0.0%–0.0% |
| minirocket | SOLUSDT | 16 | 56.2%–56.2% | 12.5%–12.5% | 0.0%–0.0% |
| rdst | BTCUSDT | 8 | 75.0%–75.0% | 37.5%–37.5% | 12.5%–12.5% |
| rdst | SOLUSDT | 18 | 72.2%–72.2% | 38.9%–38.9% | 0.0%–0.0% |
| cnn | BTCUSDT | 0 | — | — | — |
| cnn | SOLUSDT | 0 | — | — | — |

TP levels are learned MFE quantiles (.2/.5/.8) anchored to actual entry; hit bounds account for stop/target ordering within minute bars. Small actionable samples are descriptive. Continuous calibrated targets would imply nominal exceedance 80/50/20%; actual zero masses/ties and execution paths prevent interpreting these as guaranteed hit probabilities. Each method’s quantile-tie-coverage.json retains strict and nonstrict exceedance and exact zero/tie counts.

All-origin asset/month metrics are in metrics-by-asset-month.csv; original full results, every forecast row, observed target bounds, probabilities, censor flags, receipts, hashes and deterministic examples are retained. A missing first-actionable example means no qualifying forecast for that asset/method, rather than a missing successful example. No model, calibration or selection was changed after CHECK.

The descriptive actionable-entry cohorts are retained in actionable-entry-cohorts.csv: each method/asset reports evaluated N, terminal direction correctness, prefix-prior and calibrated-control accuracy on exactly the same IDs, and unique UTC origin days. These selected subsets must be compared on matching IDs; all-origin 39.27% prior accuracy is not their cohort benchmark. Neutral terminal outcomes count as incorrect for long/short entry signals. CNN has N=0 and UNKNOWN cohort accuracy; small overlapping cohorts do not establish significance.
