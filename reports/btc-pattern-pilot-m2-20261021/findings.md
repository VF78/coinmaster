# BTC-PATTERN-M2-20261021 — completed recipes, decision pending

No recipe has passed the frozen forecast gates; shortlist is empty. The economic target is NOT_MET.
Original CNN remains the best direct Q-long result, with WEAK_EVIDENCE rather than a predictive winner.
CHECK has not been opened in this pilot; final/stability/policy/native/SOL stages remain unadmitted.

## Data and causal contract

Genuine Bybit BTCUSDT linear-perpetual minutes cover2024-05-15–2026-10-21 00:00UTC without gaps.
156 retained public REST pages add155,520 real prefix minutes; immutable previous data hashes were verified.
DEVELOPMENT2024-06-01–2026-05-01; historical CHECK ends2026-10-21 00:00 and was exposed by older research.
20,928 origins;20,856 mature72h labels;72 censored. Entry is origin+60s minute OPEN, never an input feature.
All D/MFE/signature/fixed-H-SL targets were recomputed from actual minutes; old24h quality was not reused.
Three purged expanding folds score8,496 common origins. Refit history always startsJune1, never a rolling crop.
Fit-only scalers/prior/target scales/index eligibility and strict query-input-window exclusions remain unchanged.
14d paired bootstrap uses29 blocks/1000draws. Reporting regimes use causal30d trend/volatility, thresholds fit-only.
EarlyJune30d reporting is UNKNOWN until enough genuine warmup exists; all scored outer origins have full warmup.
Primary D ambiguity is zero on scored IDs; same-minute bounds/censoring/gaps remain explicitly represented and tested.

## What ran

Baseline:18 neural joint fits (TCN/Kronos projection/CNN ES+freshrefit×3),18CatBoost head fits, prior/numeric/random controls.
Mandatory4h-only CatBoost control:18additional head fits; no significant paired advantage versus2TF.
METRIC_OFF:12 neural joint fits, same full history/targets/controls, metric coefficient0 only.
RECENT180: cancelled before launch by owner;0fits. FULL_ES3: market deferred;0fits.
Original actual-CNN synthetic QA:2×8epochfits, D passed but Q failed; the FAIL is retained unchanged.
Q_PRIOR_INIT:2×8epoch synthetic fits passed unchanged gates, then6CNNmarket joint fits, original28dES/metric.1/fullhistory.
Q initialization alone changed: original random construction first, then Qweight0/bias=own purged-fit marginal quantiles.
Six core modules remained immutable; old controls, environments and experiments were preserved.
DINO excluded before quality by resource/priority;15m/other families/seeds/architecture sweeps were not admitted.
No backbone trajectory generation, production changes, orders or S0 economic replay occurred.

## Common-ID losses (all8,496 origins; lower is better)

| Direct forecast | D logloss | Q-long pinball | Q-short pinball |
|---|---:|---:|---:|
| prior |1.093512|.205775|.256859|
| CatBoost |1.084878|.210042|.260594|
| original CNN |1.089753|.203798|.256738|
| METRIC_OFF CNN |1.093612|.203885|.262120|
| Q_PRIOR_INIT CNN |1.106578|.205379|.261190|

| CNN recipe/head | D−prior [14d CI], foldwins | Qlong−prior [CI], wins | Qshort−prior [CI], wins |
|---|---|---|---|
| original/direct |−.003760[−.044147,.037689],2/3|−.001978[−.004953,.001021],3/3|−.000122[−.006360,.006186],2/3|
| METRIC_OFF/direct |+.000100[−.043600,.041670],2/3|−.001891[−.006347,.002241],1/3|+.005260[−.001351,.013177],0/3|
| Q_PRIOR_INIT/direct |+.013066[−.037026,.071933],2/3|−.000397[−.005859,.005497],2/3|+.004331[−.007154,.016262],2/3|
| Q_PRIOR_INIT/retrieval |+.011157[−.019696,.045350],2/3|+.001702[−.003345,.006770],0/3|+.005752[−.000846,.012692],0/3|

Q_PRIOR_INIT versus original CNN: D+.016826[.003425,.034134] is significantly worse; Qlong+.001581[−.001812,.005096], Qshort+.004452[−.001655,.011204].
METRIC_OFF versus original CNN: D+.003860[−.007159,.014027], Qlong+.000087[−.005111,.005227], Qshort+.005382[−.001755,.013376].
All learned retrieval tasks fail original prior/CatBoost/numeric/random controls; valid exit heads were assessed independently of D.
CatBoost D improves mean but only1/3fold; its direct Q losses worsen. No complicated encoder has established added predictive/path skill.
Full numeric tables:recipe-comparison-common-IDs.csv,recipe-comparison-gates-CI.csv and each recipe's archived comparisons.

## Diagnosis without new fits

Original synthetic CNN Q shapes/scales/gradient routing were correct: canonical loss.347138137 matches NumPy.347138118.
Its64optimizer steps left high-amplitude conditional targets underfit; baseline market refits used480/735/1512steps.
Fixed prior initialization passed the known toy: positive Q losses improve40.8%/51.0% versus prior, shuffled ratios1.0011/1.0012.
This is revised-algorithm debugging on an already known synthetic task, not independent market quality.
The market comparison rejects promotion of that repair: improved toy calibration did not produce transferable market skill.
Original low-variance training probes are LOCAL128h, not proof of global collapse. Whole-history512uniform probes are retained separately.
METRIC_OFF increases some TCN whole-period ranks but worsens forecasts; rank/variance alone is not path-skill evidence.
Q_PRIOR_INIT raw fit/ES/outer equal-fold losses: D1.026946/1.026953/1.105917; Qlong.201942/.158308/.205250; Qshort.239438/.215915/.261140.
Selected epochs6/6/7; no30epoch cap reached. ES D/Q optima align F1(6/6),F3(7/7); F2(5/6) differs by only.000986Dloss.
Thus simple D-vs-Q epoch-choice disagreement is insufficient to explain this market failure.
ES target distribution shifts remain material: F3 inner NONE56.67% versus outer34.58%; shortMFEq80 1.048 versus1.411sigma.
Q_PRIOR_INIT CNN regime D/Qlong/Qshort deltas versus prior: DOWN_HIGH N2342(−.052775,−.001523,+.000625); DOWN_LOW N2011(+.061426,+.000993,+.001713).
UP_HIGH N1487(+.023895,+.004610,+.007638); UP_LOW N2656(+.028443,−.003258,+.007728). Qlong UP_HIGH is worse with CI[.000671,.009793].
Regime heterogeneity does not authorize dropping months or selecting only a good regime. Full per-regime paired CIs are preserved.
Existing toy numeric-kNN label-permutation test is not a trained-CNN test or a genuine block shuffle; new actual-CNN QA is separately counted.

## Real fixed-SL/three-TP diagnostics

Q predicts attainable MFE BEFORE a fixed1sigma72 stop over72h; it does not independently optimize SL.
Quantiles.2/.5/.8 correspond to roughly80/50/20% separate target-hit rates, not80% probability of all three TPs.
Q_PRIOR_INIT common-ID TP-before-SL hits: long77.15/47.87/19.28%; short79.28/45.22/18.70%.
Long14d hit CIs:72.41–82.03/40.59–55.76/13.58–26.07%; short74.06–84.20/37.67–52.48/12.96–24.71%.
Mean gross target distances: long.909/2.536/5.312%; short.766/2.521/5.283%. Short distance uses1−exp(−qσ); correction receipt retained.
Actual fixed-SL touches within72h:31.49%long/31.39%short. SL-first fractions per target:17.82/28.93/31.26%long;15.81/28.40/30.92%short.
Lower/upper first-touch bounds coincide for these IDs; raw crossings/projected zeros are zero for new direct CNN.
Actual minute extrema and stored conservative/upper MFE support these summaries. No invented tick ordering, optimal-SL label, EV or money claim.
Cost-validity has not been established; no executable policy is admitted by descriptive calibration alone.

## Resources, reproducibility and remaining decision

Q_PRIOR_INIT completed6marketfits in1643.06s with RSSpeak2.918GB, CPU4/MPS/defaultwatermark; exact MPS peak is UNKNOWN.
Across completed recipes:36total market neural joint fits;36CatBoost head fits including mandatorycontrol;4syntheticfits separately counted.
Sixteen focused tests pass, including purge/anchors/whole-block shuffle, exact prior output, RNG/D/encoder identity and factory restoration.
Helper/checkpoint hashes were snapshotted before saved inference; artifacts remain in the new local job directory, not large Git caches.
README/cli-repro.md describe exact invocations; local manifests preserve baseline, METRIC_OFF, oldFAIL, zero-fit diagnosis and revisedQA/market outputs.
Final model/stability/CHECK/policy/native/SOL are BLOCKED/NOT_ADMITTED. P1 requires actual original S0 stop/horizon/state parity, never72h-label transfer.
Original S0 metadata snapshot is retained; the full-period90%-net-profit reference is not a shortened-CHECK threshold.
Next decision is pending one authorized zero-fit full-history shared-gradient diagnostic; no further fit has been authorized.
