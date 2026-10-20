# FAST-RND postanalysis diagnostics

Saved T/V summaries only. Frozen result remains NO_ADDED_DIAGNOSTIC_INFORMATION.

5959 selected T rows;3432 V decisions per asset;48 greedily spaced 72 h episodes (71.5 hourly rows per spaced episode). This 48 is not an IID effective sample-size estimate.

|Model|Mean LL|Delta vs prior|Months beating prior|Mean Brier|Classwise ECE|
|---|---:|---:|---:|---:|---:|
|prior|1.100586|+0.000000|0/6|0.667948|0.054145|
|simple|1.362616|+0.262030|0/6|0.796321|0.207211|
|stumpy|1.123658|+0.023072|1/6|0.681780|0.065988|
|minirocket|7.212750|+6.112164|0/6|1.240198|0.405010|
|rdst|8.501440|+7.400854|0/6|1.351366|0.444548|
|cnn|1.269094|+0.168508|0/6|0.755552|0.144653|

## Monthly mean log-loss delta versus prior

|Model|2025-11|2025-12|2026-01|2026-02|2026-03|2026-04|
|---|---:|---:|---:|---:|---:|---:|
|prior|+0.000000|+0.000000|+0.000000|+0.000000|+0.000000|+0.000000|
|simple|+0.242599|+0.124076|+0.066682|+0.644213|+0.280938|+0.110753|
|stumpy|+0.016681|+0.052492|+0.012989|+0.017041|+0.017681|-0.014032|
|minirocket|+7.905023|+4.625575|+6.581065|+5.343351|+6.870654|+5.434775|
|rdst|+9.254391|+5.436275|+10.471193|+8.200029|+4.414406|+8.041024|
|cnn|+0.378602|+0.049178|+0.248065|+0.101520|+0.152679|+0.122916|

Only STUMPY improves in one monthly average, partial April (-0.014032); it loses the other five. CNN, simple, MiniRocket and RDST lose all six. No claim of significance follows.

## Calibration and drift

minirocket: 76.85% of pooled BTC/SOL asset predictions exceed 90%; mean confidence 98.81%, observed accuracy 32.80% (n=5275). Directly measured severe overconfidence.
rdst: 80.64% of pooled BTC/SOL asset predictions exceed 90%; mean confidence 98.99%, observed accuracy 26.99% (n=5535). Directly measured severe overconfidence.
BTC empirical T prior / V frequencies (UP,DOWN,NONE): [0.3093, 0.2875, 0.4033] / [0.2538, 0.3715, 0.3747]; V-minus-T [-5.55, 8.4, -2.85] percentage points.
SOL empirical T prior / V frequencies (UP,DOWN,NONE): [0.2928, 0.296, 0.4111] / [0.2596, 0.3744, 0.366]; V-minus-T [-3.32, 7.84, -4.52] percentage points.

BTC DOWN frequency changes 59.26% in November to 21.24% in December; SOL 50.69% to 22.04%. This proves target-frequency drift, not that drift caused all conditional failure.

## Capacity and temporal evidence

Simple uses 38 features; MiniRocket 5816 and RDST 4628 (0.976 and 0.777 features per selected T row). Input contains 720 panel values plus 20 context features, with daily windows spanning 20 days. These correlated coordinates and overlapping 72 h targets cannot be counted as independent evidence. High dimensionality with a fixed C 1 classifier is a plausible capacity/calibration mismatch; feature counts alone do not prove overfit.

STUMPY has >=3 independent analogues in at least one timeframe for 3226/3432=94.0% of V decisions. Low overall coverage alone therefore cannot explain its negative result; match relevance and mixed horizons remain untested hypotheses.

CNN selects epoch 3 for both seeds. Epoch 3 to 5 training loss changes -0.226688(seed 7), -0.192192(seed 42), while inner loss changes +0.125853,+0.025046. This is evidence of late-epoch generalization deterioration. Early stopping already avoids those later epochs, so it does not prove the selected model failed due to overtraining.

## Limits

- These summaries prove failure of the fixed recipes on this T/V selection, not absence of all usable pattern information.
- V overconfidence is directly measured. High dimensionality, dependence and drift are plausible contributors; no MiniRocket/RDST train loss or feature drift audit was inspected, so overfit or its causal share is not proved.
- CNN inner loss deteriorated after selected epoch 3 while training loss fell. Early stopping already avoided epochs 4/5; this does not establish epoch 3 overfit as the cause of V failure.
- Overlapping 72 h targets,20 day daily windows and shared BTC/SOL context limit independent evidence.48 greedily spaced episodes is not an IID effective sample size or a significance test.
- Class frequency shift is measured but does not explain conditional failure by itself. November 432 and April 96 are partial-month rows per asset. April alone provides 96 decisions.
- V was historically studied; adaptations chosen after this analysis make V development data. No U details, fits, new predictions, engines, policy, services or Project changes occurred.
- Classwise 10 bin ECE differs from top-label ECE and depends on binning. High 90 class bins uniquely identify the predicted class and allow pooled confidence/accuracy aggregation.
- Probability metrics do not determine native net profit, portfolio drawdown or risk after fees, funding and exposure interactions.

## At most three proposed next steps; none executed

1. Audit existing T/inner artifacts, if available: train versus chronological inner losses, confidence tails, feature scales and solver convergence. Any new fit or recalibration needs a separately approved locked experiment; do not tune on inspected V.
2. In a separately approved follow-up, reduce capacity and increase shrinkage toward the empirical prior; fit any temperature/prior mixture only on purged chronological T-inner predictions. Predeclare one recipe and a new untouched evaluation period. This tests overconfidence repair; it does not establish edge.
3. For trading optimization, predeclare one low-dimensional causal action task, such as SOL entry permission during BTC stress, with costs and native portfolio drawdown as objectives. Begin with a fixed cheap rule/control and one bounded native comparison only after permission. A 72 h direction label does not identify marginal PnL or portfolio drawdown.

Machine-readable details and input hashes: postanalysis-diagnostics.json. These diagnostics do not reopen the completed experiment or authorize retuning.

## Saved prediction ranking diagnostic

ROC AUC uses exact tie averaging and one-vs-rest classes on the same 3432 V labels per asset. Constant prior is exactly 0.5. No model fit, new prediction, inversion, resampling, significance claim, U inspection or economic run.

|Model|Asset|UP AUC|DOWN AUC|NONE AUC|Macro AUC|Monthly macros above 0.5 / defined|
|---|---|---:|---:|---:|---:|---:|
|prior|BTC|0.500000|0.500000|0.500000|0.500000|0/6|
|prior|SOL|0.500000|0.500000|0.500000|0.500000|0/5|
|simple|BTC|0.522180|0.523984|0.553362|0.533175|4/6|
|simple|SOL|0.573711|0.468078|0.533866|0.525219|3/5|
|stumpy|BTC|0.469417|0.472518|0.541965|0.494633|2/6|
|stumpy|SOL|0.458060|0.419218|0.510689|0.462656|0/5|
|rdst|BTC|0.401474|0.468716|0.518910|0.463033|4/6|
|rdst|SOL|0.446604|0.462528|0.497961|0.469031|2/5|
|minirocket|BTC|0.433808|0.443683|0.564200|0.480563|2/6|
|minirocket|SOL|0.489647|0.432682|0.528064|0.483464|3/5|
|cnn|BTC|0.448682|0.441820|0.550707|0.480403|2/6|
|cnn|SOL|0.491579|0.407202|0.562541|0.487107|3/5|

Per-month and per-class values: postanalysis-ranking.csv. SOL April has no UP observations; UP and the three-class macro AUC are undefined, so its macro is excluded from the monthly denominator.

AUC measures ranking on already inspected V; overlapping labels mean no significance claim.
AUC above0.5 does not establish profitable actions, calibration, or risk reduction. AUC below0.5 is not authorization to invert/tune scores.
Binary monotone calibration preserves individual score ranking, but multiclass temperature/normalization or shrinkage may change class rankings; no repair benefit was tested.
SOL April has zeroUP targets; UP AUC and3class macroAUC are undefined. Missing values are blank, not0.5.

All four recognizer families have full-V macro AUC below0.5 on both assets. Their UP and DOWN AUCs are below0.5 for both assets; only NONE is above0.5, except RDST SOL NONE0.497961.

Simple control is strongest on full-V macro: BTC0.533175 and SOL0.525219; all BTC classes and SOL UP/NONE exceed0.5, while SOL DOWN0.468078.

MiniRocket BTC NONE0.564200 and CNN SOL NONE0.562541 exceed simple on those isolated class scores, but neither recognizer demonstrates broad directional ranking. Calibration repair alone therefore has no established general ranking edge to recover.

Monthly results vary and pooled AUC is not the average of within-month AUCs: RDST BTC has4/6monthly macros above0.5 despite pooled0.463033. Do not treat individual months or score reversal as a selected strategy.
