# End-to-end BTC pattern pipeline audit — 2026-10-22

Audit base: `a32c9e42be9b1888122ed33c965c102651adb13c`. Four implementation defects and one reporting discrepancy were reproduced. They do not establish a single cause of all negative market results. Original source, models, prior results, full DEVELOPMENT history and trading pilot remain unchanged. New model fits, optimizer updates, market forecasts, CHECK scoring, native backtests and deployments: **0**.

## Every stage and its acceptance evidence

| Stage | Result | Concrete evidence / limit |
|---|---|---|
| Real input data | Invariants pass | All1,280,160 minute OHLCV rows: finite positive prices, valid high/low/open/close and nonnegative volume. Source timestamp validation reuses original receipts because the compact array has implicit time. Not a fresh exchange-authenticity audit. |
| Aggregation / available information | Pass | Only closed1h/4h bars; origin/reference/next-minute entry are distinct. No terminal bar or actual future fill leaks into X. |
| Feature provenance | **Confirmed defect B1** | Engineered4h relative-volume features consume80h before recorded `input_start`; raw CNN/Kronos inputs do not consume that older warmup. |
| Labels / physical units | Pass, narrower task than independent SL prediction |283 focused assertions plus20 whole-array invariant groups;16,704 labels matured by DEVELOPMENT end. All8,496 outer D-versus-MFE first-event identities match; gaps, signed long/short prices, minute bounds and censoring checked. Q still means MFE before a fixed stop, not an optimal SL. |
| Splits / training / ES / refit | Actual saved runs pass; latent B4 |18 neural states and18 CatBoost models checked. Purged full-history fit IDs/scales, selected epochs, distinct fresh refit states and class/quantile order match. D-ES denominator is wrong only when D masks occur; actual ES ambiguity counts are0. |
| Numeric / visual / pretrained representation | APIs pass, information limits remain | TCN is causal; normalized cosine/metric arithmetic correct. CNN raster can erase nonzero price differences; global pooling lacks an explicit last-bar readout. Kronos was frozen feature extraction, not its documented autoregressive forecast benchmark. |
| Learned metric / analog retrieval | Arithmetic passes; B1 affects exact saved pairs |276 TCN+434 numeric neighbor pairs overlap actual engineered warmup. Cosine ranks neighbors; up to32 have equal weights plus fit-prior mass8. Similarity is not a calibrated win probability. |
| Saved inference / order | Pass on executed artifacts | All72 historical forecast groups have exact expected IDs, canonical D/Q/bounds and correct fixed projected Q. No saved-model inference was rerun. |
| Evaluation / admission | **Confirmed B2/B3** | An absent third candidate fold or mismatched per-file truth can falsely pass the standalone evaluator. Single-class AUROC NaN crashes strict JSON. These failures were synthetic guard counterexamples, not newly discovered corruption of the72 actual groups. |
| Prediction semantics / downstream policy | Unresolved design gap | Separate D/Q can disagree, SL is fixed, and no accepted executable policy/ROI result follows from mean calibration. Prior negative gates remain intact; S0 integration was not run. |

## Confirmed corrections needed, not applied

**B1 — P1, actual provenance / neighbor contract:** `btc_pattern_data.py:50–57,93`. Keep both `raw_window_start` and the true `feature_dependency_start`; use the relevant method's support for exclusion. Mutation80h before reported start changes the first engineered volume feature by−0.2298544496. Exactly710 baseline neighbor pairs are affected across TCN/numeric. This is known-past overlap, not future leakage. Fixing metadata does not change X or direct CNN outputs and requires no new model fit. Measure corrected cached-neighbor ranking/aggregation separately; predictive impact is presently UNKNOWN.

**B2 — P1, evaluator accepts incomplete/inconsistent evidence:** `btc_pattern_evaluate.py:24–26,46–50` and CLI dispatch. A candidate with onlyF1/F2 receives `PREDICTIVE_PASS` with2wins. Another fixture shifts candidate truth while retaining IDs and receives3wins: reported NLL.020203 instead of canonical-truth NLL4.60517. Require all expected folds/methods/unique ordered IDs, canonical mature labels, schema and existing completion/source/data/protocol receipts before any score or output. Actual72 groups independently pass these integrity checks.

**B3 — P2, undefined diagnostic handling:** `btc_pattern_evaluate.py:30–33,54`. Installed sklearn returnsNaN rather than raising for single-class AUROC; strict JSON then crashes. Emit `null` plus an undefined reason after explicit valid-class/finite checks. Preserve strict JSON; never replace an undefined metric with0.

**B4 — P2, latent early-stop denominator:** `btc_pattern_train.py:72–73`. D loss is averaged over valid D labels but reweighted using all batch rows. A two-batch fixture produces5 instead of10/3. Accumulate Dsum/validDcount and Qsum/Qcount separately. Actual ES sets have no D ambiguities, so this did not alter their selected epochs.

**R1 — reporting discrepancy:** `btc_pattern_train.py:77` averages online minibatch means equally. In actual F1 CNN, an8-row last batch receives7.91× its row-proportional logged weight. This is not proof standard minibatch optimization is wrong. Report sums/counts and distinguish online loss from final saved-model fit/ES/outer loss.

## What the numerical audit says about the failed pattern search

The pipeline did update weights, retain/reload best checkpoints, fresh-refit the whole permitted prefix and score correctly aligned actual forecasts. No reversed side/quantile order, future-learned scaler, broken KL sign, or optimizer-never-updated explanation was found. Do not repeatedly repair these already checked mechanisms.

An additional target-space diagnostic used128 uniform purged-refit anchors/fold and32 eligible, label-disjoint, spaced peers per anchor. It deliberately compares **known future signatures**, not causal forecasts:

| Fold | D disagreement, oracle-signature / random | Long absolute MFE deviation | Short absolute MFE deviation |
|---|---|---|---|
| F1 |17.31% /65.87%|.3014 /.7479|.3812 /.8791|
| F2 |6.64% /66.16%|.2298 /.7212|.2957 /.8867|
| F3 |3.20% /65.89%|.2130 /.7293|.2951 /.9423|

Thus the signature is not useless: it groups related outcomes. It is not an exact D/Q sufficient statistic, and this oracle test proves neither encoder learnability from past X nor an attainable trading upper bound. Current models failed to transfer outcome-neighborhood information into reliable past-only forecasts. Prior METRIC_OFF failed, so removing the metric blindly is not a demonstrated solution.

The original CNN long-Q improvement is only about.96% with a paired CI including0; short improvement is negligible. The known toy Q repair did not transfer to market data. Existing drift diagnostics show changes within regimes, and volatility-ratio signs reverse between folds. More epochs, a shorter180d training span, or universal volatility rescaling are not supported repairs.

The previous follow-up's exact D/Q incompatibility remains relevant: short24.11/8.23/1.75% by fold, but episodic and insufficient to explain every failed result. Correcting internal consistency cannot manufacture missing predictive information. Likewise a lower frequency of wider-stop hits is not an economic improvement.

## Minimal sequence and optimization options — proposals, not execution

1. **Repair research correctness first, no model fit:** B1/B2/B3/B4/R1 with narrow regression tests. Revalidate original complete artifacts; recompute only affected cached TCN/numeric retrieval under true support. Keep old results and raw data unchanged; do not rerun S0 or native economics for these guards.
2. **Before the next market fit, require a true end-to-end positive control:** known past pattern→genuine synthetic OHLC path→same prepare/labels/encoder/head/reload/evaluate chain, plus an outcome-block shuffled negative control. Freeze gates before running. Earlier direct image/context toys and hand-path tests cover different links and cannot substitute for this combined acceptance. This would involve small new fits and is NOT started under the current prohibition.
3. **First forecast candidate: small coherent joint-barrier output.** Keep original CNN/context, full-history prefixes, horizon, physical units and controls; derive D and3TP from one TP-first/SL-first/neither distribution for fixed candidate barriers. Freeze monotonicity/ambiguity/out-of-grid handling and evaluate original losses plus proper joint-event scores. This resolves a measured semantic gap; superiority remains unproven, and economic SL selection still needs an explicit risk/cost objective.
4. **Separate later option: more informative state/recency, without cropping history.** Current input is64×4h/64×1h plus context through168h, not699 days of context per prediction. Test one change such as numeric scale-aware/last-state readout or longer causal regime context, with genuine warmup available before the fixed training start. Do not simultaneously enlarge images, change horizons, weight samples and add15m. CNN raster collision and TCN excess receptive field motivate controlled tests, not an architecture sweep.
5. **Calibration/efficiency only after skill:** delayed-outcome, time-series-aware calibration can adjust coverage but does not guarantee sharpness or ROI. Cached empirical priors/batched exact cosine can reduce cost without changing predictions; do not replace greedy spacing with an unsafe top-k shortcut. A fair Kronos rollout experiment is a distinct later proposal, not a reinterpretation of the completed frozen-feature result.

Full DEVELOPMENT `[2024-06-01,2026-05-01)` remains retained; CHECK was not scored. The audit supplies no authorization for training, trading, or deployment. No claim is made that all market forecasts will become accurate after the code repairs.

## Evidence and reproducibility

[Data/labels](data-labels/findings.md), [models/retrieval](models-retrieval/findings.md), [training/evaluation](training-evaluation/findings.md), and their probe scripts/JSON/CSV contain exact source lines, counterexamples and commands. [Primary scientific/model-documentation review](literature.md) maps each source to a decision. Binary files under `training-evaluation/fixtures/` are explicitly tiny synthetic evaluator guard cases, not fitted models or market backtests. Source/data/model hashes and the integrated audit manifest preserve provenance; trading source and earlier reports were not patched.
