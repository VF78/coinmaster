# Failure follow-up: one proposed joint TP/SL experiment, not started

Zero-fit calculation:0.821s, all8,496 original outer origins/all scored months, three fixed folds. Full DEVELOPMENT history fromJune1,2024 remains retained; CHECK/pilot/VPS untouched. Three targeted tests passed. No new predictions, conditional calibration, models, trainings or backtests were fitted.

## What failed and what the extra calculation supports

The original market result remains negative: CNN Q-long has weak evidence, no learned retrieval/path pass. Synthetic Q initialization repaired a known toy but failed to improve market forecasts. Existing gradients do not support blindly removing D; metric-off already failed. This follow-up examines a narrower structural hypothesis, not a new forecast-skill result.

Causal24h/168h volatility ratio is already derivable from context[4]/context[5]; it adds no raw information. Each fold's ratio terciles were frozen using ONLY its purged full-fit feature rows before loading outer outcomes. Cutoffs: F1 .7914/1.0857; F2 .7756/1.0814; F3 .7756/1.0884. Low/mid/high counts:1064/836/908;915/913/1052;880/1073/855.128uniform origins independently match completed-minute close calculations.

The proposed universal ratio mechanism is NOT supported. Equal-regime high-minus-low median CDF residuals are:

| Fold | long | short | 14d uncertainty/support |
|---|---:|---:|---|
| F1 |−.3868|+.2065|CI withheld:663/1000 support-preserving draws; UP_LOW has only5low/9high origins|
| F2 |+.0293|−.0632|CIs[−.1366,.2030]/[−.2024,.0279]; only two low-vol regimes exist|
| F3 |+.2185|−.0796|CIs[.0678,.3555]/[−.2396,.1359];962/1000 valid draws|

Signs reverse across folds/sides. Adjusted fixed-SL touch contrasts also reverse (F1long−.2867; F3short−.1937). All raw/adjusted/half-period results and cell counts remain in CSV; no favorable month was selected. Equal-regime contrasts are common-support descriptive estimands, not population-weighted causal effects.14d blocks address dependence; rare support still prevents reliable attribution. CDF-minus-nominal is descriptive: atoms/ties do not imply exact equality is the correct calibration criterion.

A narrower structural finding survives: with the same1sigma72 TP/SL barriers, true first-passage D cause equals TP-before-SL at TP=1 on all8,496 unambiguous labels (zero identity mismatches). Separate model heads sometimes violate compatibility bounds implied by their own q.2/.5/.8, without any interpolation or calibration fit:

| Fold | long incompatible | short incompatible | short excess>5pp |
|---|---:|---:|---:|
| F1 |.43%|24.11%|5.63%|
| F2 |0%|8.23%|.69%|
| F3 |1.28%|1.75%|0%|

This is episodic internal incoherence, strongest in F1short. It neither explains all negative skill nor proves a joint head will improve out-of-sample loss. F3 violations are tiny despite market weakness.

## Why SL needs a joint outcome, not a larger-stop shortcut

Same original CNN TP levels are held fixed below. Stop settings are DIFFERENT physical contracts, all72h and in ORIGINALsigma72 units. Each cell lists SL.75/1/1.5.

| Fold/side | SL touched within72h | median TP reached BEFORE SL |
|---|---|---|
| F1 long |41.60/31.48/16.42%|40.42/42.49/46.44%|
| F1 short |40.17/28.70/10.90%|46.97/48.11/49.61%|
| F2 long |39.65/30.00/16.53%|51.49/53.02/53.40%|
| F2 short |45.69/32.19/16.22%|38.58/39.83/41.15%|
| F3 long |45.19/33.01/18.30%|47.69/50.32/51.39%|
| F3 short |43.27/33.26/13.89%|51.39/53.92/54.45%|

Widening1→1.5 increases median TP-before-stop only.38–3.95pp across these cases while increasing stop distance about50%. Lower stop frequency is not free improvement or evidence of an optimal SL. SL-touch-anytime differs from SL-first versus a particular TP; both lower/upper competing-event bounds are retained. Zero-profit targets remain descriptive rather than tradable actions.

Current fixed-SL MFE targets support attainable-profit quantiles BEFORE that one stop. Existing real paths/signatures also support fixed-stop touch/time risk, but the model did not learn an independently optimal SL. Three stored stop-conditioned MFE variants alone do not define utility, executable sizing, costs, stop severity or portfolio drawdown. No best-stop/EV/ROI claim follows; actual ROI/DD remain NOT_EVALUATED/native replay0.

## ONE concrete next hypothesis and experiment — proposal only

Hypothesis: a shared, physically consistent competing-barrier output can improve joint3TP/fixed-SL calibration versus separate D/Q heads. Support is the exact label identity plus episodic prediction inconsistency and material stop-conditioned distribution differences; forecast advantage remains unproven. Volatility ratio alone is not the proposed fix.

Keep the original CNN encoder/context12/full-history folds, seed7, optimizer, normalization and72h horizon. Replace ONLY the output/target contract with one small shared head conditioned on origin-known lower/upper barrier distances. Predeclare TP grid[.25,.5,.75,1,1.5,2,3,4] and candidate SL[.75,1,1.5], all converted using the SAME stored originalsigma72; preserve physical stop prices. Label upper-first/lower-first/neither from genuine minute paths; mask/retain interval bounds for same-minute ambiguity. Train one proper competing-event likelihood; derive D from the single1/1query and3TP targets from80/50/20% TP-first probabilities at a fixed stop. Freeze monotonicity/out-of-grid handling before fitting; never shift targets closer to inflate hit rates.

Evaluate every original outer fold/common ID versus original CNN, empirical/numeric/random/CatBoost controls using original D/Q losses plus joint-event logloss/Brier/coverage and14d paired CIs. No rolling crop, ratio-driven reweighting, new backbone, calibration sweep or CHECK tuning. This would be ONE independently frozen/reviewed experiment; none has started. Choosing SL economically additionally requires an explicit finite-action risk/cost objective and actual S0 horizon/state parity. A72h result cannot be transferred silently to native S0.
