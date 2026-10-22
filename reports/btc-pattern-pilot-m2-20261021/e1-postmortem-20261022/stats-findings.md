# E1 saved-artifact postmortem statistics

Retrospective exploratory calculations only. Source: frozen RESULTS.json (198 scored events), catalogue.json, inputs.npz, protocol. No market data, forecasts, model fitting, neighbor reselection, backtest, new horizon labels, parameter search, or execution run. The full source period [2024-06-01, 2026-05-01) is retained. Every event remains in all headline calculations.

| Arm | TP pinball | SL adverse-touch Brier | TP delta vs prior | SL delta vs prior |
|---|---:|---:|---:|---:|
| Prior | .25132860 | .20572081 | 0 | 0 |
| State | .25424948 | .20675909 | +.00292088 | +.00103827 |
| Clock | .25515122 | .20661304 | +.00382262 | +.00089223 |
| Phase | .25429851 | .20729858 | +.00296991 | +.00157777 |
| Fixed arithmetic: .75 prior + .25 phase | .25128703 | .20558409 | −.00004157 | −.00013672 |

The last row is a requested single fixed blend of SAVED forecast coordinates, not a fitted or newly generated forecast system. Pinball of blended quantiles is evaluated against saved labels; it is not a claim about quantiles of a mixture distribution.

| Fold | n | Phase ΔTP | Phase ΔSL | Fixed .25 blend ΔTP | Fixed .25 blend ΔSL |
|---|---:|---:|---:|---:|---:|
| F1 |64|+.00055264|−.00152723|−.00044839|−.00073698|
| F2 |67|+.00765261|+.00616687|+.00106549|+.00089709|
| F3 |67|+.00059625|−.00004537|−.00076003|−.00059716|

Phase TP is worse in all three folds; F2 loses on both targets and supplies most pooled excess. F2 supplies most of the pooled excess. F2 July/September ΔSL are +.00986279 / +.00946390, while September ΔTP is +.01189595. Monthly sample sizes are only 8–21. Exact monthly/side/SL breakdown is in stats-breakdown.csv; aggregate side/SL/quantile metrics in stats-results.json.

For d = p_phase − p_prior and r = y_touch − p_prior, exact Brier excess is E[d²] − 2E[dr] = .00283288 − .00125511 = +.00157777. Adjustment RMS is .05322 probability points (5.32 percentage points); adjustment/residual correlation is .02214. F1 credit .00342147 exceeds cost .00189425; F2 credit is NEGATIVE −.00272885 against cost .00343802; F3 credit .00316970 almost cancels cost .00312433. Thus this is not only sampling variance: F2 local corrections point the wrong way. Fixed .25 arithmetic reduces cost quadratically to .00017705 while retaining .00031378 credit, explaining its tiny pooled Brier gain. There is no claim that .25 is optimal or externally validated.

Pinball excess similarly comprises −.01710461 improving-cell credit and +.02007452 worsening-cell cost. There are 1,601 improving / 1,748 worsening / 215 unchanged cells out of 3,564. Fixed .25 produces −.00485652 / +.00481495, nearly canceling. Phase median quantile contributes +.00606124 (Q20 +.00177512; Q80 +.00107337). Fixed .25 still worsens Q20/median by +.00015762 / +.00062264 and improves Q80 −.00090498. The pooled TP gain is therefore fragile and cannot be sold as validated improvement in all three TPs.

Phase loses TP on both long/short (+.00375878 / +.00218105). SL is near flat long (−.00019924) and worse short (+.00335477). SL .75 and 1 lose (+.00263902 / +.00280293), while SL1.5 improves −.00070864. Prior pooled TP quantile hit rates (.18182/.48232/.78199) are already near .20/.50/.80; phase (.20455/.48569/.78283) adds little calibration. Phase reduces pooled SL probability underprediction from 1.61 to 1.00 percentage points but worsens Brier: correcting average bias does not establish event-level discrimination.

Phase improves 94/198 event TP losses and 88/198 SL losses. The worst10 events account for 24.48% / 27.60% of positive excess. Removing them reverses signs (TP−.00057036, SL−.00197153), but this deletion is only a concentration diagnostic, never an admissible selection rule. The worst events occur in all folds; a single-month exclusion does not explain everything.

Neighbors are available: every event has32, no fallbacks. Phase uses296 distinct events; maximum reuse90; top10 account11.24% of all6,336 neighbor slots. Direction match is98.63% (state89.88%, clock98.90%). Phase looks more similar in shape: selected phase MSE mean .80189 against eligible-pool7.57821 and state-neighbor phase MSE2.61407. Yet no corresponding outcome gain is demonstrated: using only pairs whose labels are already saved in outer evaluation, MFE MAE is .90870 phase vs .89235 state (.89857 clock). Pair subsets differ (1,460/1,330/1,429), so this is descriptive evidence against equating visual similarity with outcome similarity, not a paired significance test.

Nominal .5/.5 weighting does not equal component contributions. For selected phase pairs, shape share dh/(ds+dh) median29.20%, p90 67.66%, max94.57%; eligible pool median69.14%, p9091.58%. Clock selected median32.19%, p9064.66%, max94.00%. Phase selected state MSE mean1.12684 versus shape .80189. The chosen32 constitute median16.08% / max31.68% of the eligible pool. Shape can dominate individual distances and strongly filter the pool, but selected-neighbor average shape dominance is not supported.

Exploratory median splits show no simple rescued subset: phase TP is worse for both completed-leg directions, both correction-depth groups, both correction-delay groups, both impulse-duration groups, and both frozen-delta/current-volatility ratio groups. Longer corrections (>13h) improve SL −.00054236 but worsen TP +.00208533; shorter corrections lose both. Larger correction depths (>1.13857 sigma24) almost cancel SL cost/credit (.00277581/.00266087) but TP remains +.00074043. Group sizes98–103 and post hoc splits prohibit a causal/predictive interpretation. Exact conditional prior residuals are preserved in JSON for a future separately approved residual-model rationale; no such model was fit.

Mechanism precheck: strong regularization of event-local corrections toward the causal event prior can reduce excess estimation noise, while retaining a weak conditional signal. The single fixed .25 arithmetic check supplies preliminary mechanism support, and its F2 failure / tiny pooled TP gain argue for a future predeclared past-only calibration or uncertainty shrinkage design, not adoption now. A future approved experiment must preserve all targets/denominators and require improvement versus all controls under original fold/block criteria; no new run is authorized here.

Methods dependency cross-check: activation−168h precedes recorded input_start for E00203/F2 by33h and E00307/F3 by1h. Only E00203 has a pool label crossing that earliest dependency: E00196, 1/193 pool members; it is selected in none of state/clock/phase, but enters prior/scaler. E00307 has0/297. This violates strict shared input/label nonoverlap, not causal availability before the query; it is not proof of live future leakage. No corrected forecast was computed and these rows are retained.

All source artifact hashes are in stats-results.json; script is reproducible with NumPy only. Bootstrap significance and economic returns are not established by these exploratory arithmetic checks. SL is full-horizon adverse touch, not actual traded stopout.

Additional uncertainty: original occupied-block paired bootstrap arithmetic (1,000 draws, seed7, stratified within folds) for the fixed .25 blend gives TP14d95% CI [−.00113411,+.00109349], TP28d [−.00129209,+.00081323]; SL14d [−.00088081,+.00053088], SL28d [−.00099992,+.00041872]. Both include zero by wide margins. These are post hoc exploratory intervals and do not pass the original improvement requirement. Exact hindsight Brier optimization along this stored adjustment direction has lambda*=B/(2A)=.221525 and maximum in-sample reduction B²/(4A)=.000139019, only0.06758% relative to prior Brier. This analytical bound is not another tested blend or proposed chosen coefficient. Fixed shrinkage alone has weak grounds for additional experiment budget: it mostly repairs harm and has very limited demonstrated upside.

If an owner-approved next study is desired, the evidence favors investigating a small regularized correction to the causal prior rather than simply applying fixed shrinkage. Existing prior residuals vary with causal volatility ratio: below/above median .98919 (99/99 events), long SL residuals are [.06436,.07352,.06756] / [−.00763,.00211,−.00372], and short SL residuals [−.06353,−.04030,−.01451] / [.04777,.03106,.03598]. This suggests conditional structure to test, but could be fold/regime confounding and does not establish any trained model's skill. Mean MFE-minus-Q50 also varies, especially short; it is a descriptive mean residual, not a quantile-calibration statistic. A candidate would need predeclared small feature scope and shrinkage determined exclusively from eligible past training, with all quantiles and SL targets retained. Nothing has been fit or run here.

Raw-bar-start sensitivity uses min(activation−169h, anchor−1h): still2/198 input-support defects and only1 affected eligible pool label (E00196). Missing dependency gaps are34h/2h rather than close-endpoint33h/1h. No selected neighbor changes were computed.

## Final single next mechanism: four-cell conditional prior

This additional diagnostic is post hoc and computes calibration of existing saved PRIOR forecasts only. No conditional prior has been generated, fitted, or tested. The four cells cross completed-leg direction (−1/+1) with frozen activation delta / current confirmation sigma24 at the physical boundary1. Ratio≤1 means confirmation volatility is at least activation volatility; ratio>1 means it decreased. No scored case equals1, so < versus≤ makes no numerical difference. No threshold search was performed. All198 IDs remain represented.

| Cell | pooled n | F1 n | F2 n | F3 n | Long SL residuals .75/1/1.5 | Short SL residuals .75/1/1.5 |
|---|---:|---:|---:|---:|---|---|
| Down, ratio≤1 |57|18|23|16|+.048/+.034/+.072|−.042/−.061/−.023|
| Down, ratio>1 |41|14|10|17|−.024/−.034/−.079|+.013/−.052/−.048|
| Up, ratio≤1 |55|16|19|20|+.079/+.116/+.078|−.062/−.012/+.018|
| Up, ratio>1 |45|16|15|14|−.010/+.012/+.026|+.082/+.119/+.098|

SL residual is observed touch frequency minus predicted probability. The exact prediction/observation pairs, all18 TP quantile coverage deviations per cell, fold versions, and all IDs are saved in JSON. stats-four-cell.csv provides every cell/fold/side/SL/quantile row. Coverage deviation is P(saved MFE≤saved prior Q_tau)−tau; positive means the forecast quantile is too high relative to that subgroup. It is not a mean-MFE residual.

| Cell | Long TP coverage deviations Q20/50/80 | Short TP coverage deviations Q20/50/80 |
|---|---|---|
| Down, ratio≤1 |−.025/+.067/+.007|−.077/−.038/−.057|
| Down, ratio>1 |+.003/−.061/+.013|−.037/−.045/+.078|
| Up, ratio≤1 |−.006/+.082/+.042|−.036/−.136/−.073|
| Up, ratio>1 |.000/−.026/−.141|+.052/−.004/.000|

This table averages coverage deviations across the three SL coordinates for compact presentation; it does not pool target labels as independent events. Several mechanisms recur: down/ratio≤1 underpredicts long touch for everySL in eachfold, and overpredicts short .75 touch in eachfold. Down/ratio>1 overpredicts both long/short1.5 touch in eachfold. Up/ratio≤1 short Q50 is too low in everyfold (average deviation−.312/−.079/−.050); up/ratio>1 long Q80 too low in everyfold (−.029/−.200/−.205). These are useful diagnostic signs of missing conditional distributions in the full-history prior.

The evidence is mixed: only8/24 SL cell-coordinate residuals and17/72 TP coverage coordinates have strictly consistent signs in allthreefolds. For example, up/ratio>1 short touch underprediction pooled is a fold composition effect: F1 residuals are allnegative, F2/F3 allpositive. Cell-fold samples10–23 and serial dependence make estimates noisy. The diagnostic supplies a specific mechanism worth testing, not proof of universal or future stable correction.

ONE proposed future experiment: replace32-neighbor full-distribution replacement with a four-cell empirical outcome distribution using only direction and volatility-ratio boundary1, shrinking each cell distribution toward the same eligible historical global event prior with one fixed predeclared weight shared by all18 quantiles/6 touch targets. Quantiles must come from that weighted empirical distribution, not arithmetic quantile blending. It should use the corrected shared earliest-input support and the identical eligible pool, all IDs, folds, original paired-block criteria and controls. Choose the fixed shrink strength before opening any new evaluation; do not select it from these198 outcomes. No forecast/label/model/backtest run is authorized or performed by this proposal. This supersedes the broader residual-model suggestion above; fixed .25 blending remains a diagnostic and is not a second proposed experiment.
