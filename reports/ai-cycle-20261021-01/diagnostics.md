# Diagnostics — AI-CYCLE-20261021-01

Saved old predictions reproduce raw/calibrated logloss, Brier and lower pinball to tolerance1e-10 on identical IDs. Coverage, per-asset OVR AUROC and confidence distributions are in old-metrics-reproduced.json. Historical CHECK is already studied, not pristine.

Old final weights were available and hash verified. Fixed first256 mature chronological TRAIN IDs are actual fit rows, not internal validation; first256 mature March IDs provide the comparison. Existing predictions were reused where IDs matched; UTC correction inferred only6 missing IDs/method without fitting. These small chronological samples differ in market regime and cannot measure a universal generalization gap.

|Old model|Fit logloss|March logloss|Fit lower pinball|March lower pinball|
|---|---:|---:|---:|---:|
|control|1.065794|1.051771|.217834|.208273|
|STUMPY|1.061523|1.031101|.213414|.209206|
|MiniRocket|1.005557|1.206319|.208145|.234173|
|RDST|1.001168|1.119400|.206601|.224953|
|CNN|1.057948|1.048851|.217813|.211822|

MiniRocket and RDST show substantial fit/March gaps on this fixed sample, consistent with overfit or regime shift; this sample does not separate those explanations. Old learning curves/gradient histories were not saved: UNKNOWN. Finite loss is not evidence that a model or pipeline is healthy. CNN raw confidence below0.5 explains zero old entries; thresholds were not lowered.

Known technical errors and their preserved receipts:
- RDST initially shared a process with incompatible parent modules; original failure retained. Only remaining RDST/CNN old-weight inference ran in isolated processes.
- Legacy date-only timestamp parsing used host timezone. Initial A quality was sealed and quarantined before any metrics were opened. Narrow UTC wrapper normalizes requests AND inherited in-memory TRAIN/CHECK seals, without changing old disk protocol/source. Seven focused tests include actual inherited seal behavior under UTC/Europe-Moscow.
- Invalid first A102 fits cost537.539s, retained and charged to A. Exactly the fixed recipe was repeated once after explicit technical-error authorization. Valid A cost543.412s. Neither original invalid quality nor its forecasts were used for selection.
- Negative-control TRAIN14day block IDs/permutation were unchanged by UTC correction; original3 positive fits were reused; only6 negative fits replayed because their weights were not saved.
- New B dependency preflight initially lacked requests; no weights/inference/fits opened. Isolated pinned dependency closure resolved it; b-preflight-error.txt records the original failure.

Positive synthetic independent D/Q controls passed; synchronized whole14day shuffled-label controls did not show robust temporal validation advantage. These are small pipeline checks, not financial evidence. Future OHLC AND volume changes preserve past features/predictions; model roundtrips and full horizon purge pass.

Valid A saves fit/ES/refit curves and raw/projected forecasts. All12 CatBoost D ES fits have positive last-computed ES-minus-fit loss (median.081077); Q-long8/12(median.036320), Q-short7/12(median.014958). Positive gaps are consistent with overfit; their varying signs and high errors do not identify weak signal versus weak features versus insufficient training. Metrics have different units across heads.
Only shape-BTC-fold0-D reached500 computed iterations; fit loss still fell over the last10. Its cap diagnosis is unfinished; no training extension was made. Three linear-Q ES runs reached80 epochs. Full per-fit changes/gaps are in a-fit-curve-diagnostics.json; selected-tree count is never confused with computed iterations.
Linear Q curves retain actual gradient norms, raw ranges and fit/ES crossing/clipping fractions with N. Logistic has final logits but no invented gradient history. CatBoost saved D class mapping [UP,DOWN,NEUTRAL]=[0,1,2] and restore predictions are checked.

All6 joint A gates fail the fixed prior+linear mean/fold/blocked-CI criteria; no D rank admission. Exact losses,14day paired1000draw CIs and7/28day sensitivity are in valid A gates.json;21 common14day blocks. Forecast-loss CI is not a PnL/DD interval.

Kronos original small/tokenizer provenance and corrected MIT metadata are verified against original weight hashes; authors report pretraining endsJune2024. Public releaseJune2025 postdates part of TRAIN: historical availability is not established. Independent sample_count1 calls retain16 paths; zero volume/amount ablation is explicit. Random fixture verifies sample axis, future OHLCV invariance and frozen generation-reference/sigma as-of age.
Kronos resource pilot stops at3 paired origins: fastest warmed pair11.9166s, excludes startup/firstpair. All3120 common generation origins alone project619.66min. No outcomes/head fits were read. B is INCOMPLETE_RESOURCE, not NO_SKILL.

TS2Vec uses32/32/depth6, batch16, lr.001, maxlength256,600iterations,seed7. Prefix scaler and encoder are isolated from ES validation and future data; full-prefix refit is separate. Random-weight prefix/futureOHLCV and averaged-model roundtrip fixtures pass with causal=True/sliding_length1/padding255 and no pooling. Fixed real-prefix resource pilot600 iterations and saved trained-model restore also pass. Encoder contrastive loss is not forecast quality. All required14 unique encoder fits,144714 causal inference timestamps and future heads are charged. Full C resource outcome is recorded in mac-artifacts/profile-C/resource-result.json; no head outcomes were opened.

The saved S0 state screen contains all scanned timing/price-eligible candidates and profitable counterexamples. Native ordinary-branch availability, pending intents/consumed rights and exact predecision per-asset UPnL are not reconstructible. Availability remains UNKNOWN, never zero or a proof of eligibility. No paired action-value branches exist: ACTION_VALUE_UNIDENTIFIED. Original profitable trade PnL is not a counterfactual action outcome.
First native DD>50% is2024-10-03T09:01:00Z. Real hourly June–August warmup exists; real minute/15m history startsAug31, so no fully24h-mature X_joint fit rows atSep1. An overlay retaining earlyS0 inherits its early breach. This does not automatically exclude a BTC-only strategy with early flat on its own equity.
