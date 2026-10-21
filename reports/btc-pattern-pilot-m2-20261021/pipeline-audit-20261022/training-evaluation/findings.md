# Training/evaluation audit — confirmed guards, not a new model run

Read-only audit completed1.626s CPU4:0fits,0optimizer steps,0saved-model inference,0new forecasts/CHECK.18baseline neural checkpoints and18CatBoost models checked;72historical forecast groups independently match all expected outer IDs and prepared D/Q/bound labels. No core/protocol/model fixes were made.

## Confirmed implementation defects

1. **Evaluator can promote incomplete or mismatched-truth artifacts.** `btc_pattern_evaluate.py:24–26,46–50` iterates available groups, checks only paired IDs, and tests `fold_wins>=2`; it never requires three candidate folds or validates NPZ truth against prepared labels. `btc_pattern_run.py:17–19` invokes it without completion/protocol/source validation. Tiny synthetic files (not model predictions) demonstrate:
   - Candidate present inF1/F2 only, controls inall3: `SHORTLIST_READY`, D`PREDICTIVE_PASS`,2wins, paired loss delta−1.07840958.
   - Three candidate files with cyclically shifted saved Dtruth relative to controls, same IDs: still `SHORTLIST_READY`,3wins, same claimed improvement. With canonical control truth those deliberately wrong predictions have NLL4.60517 instead of the reported.020203, versus prior1.098612.
   - Both accepted a prepared directory containing metadata only: no canonical labels, manifest or completion receipt.
   Impact: future corrupted/partial artifacts can create false passes. **Not evidence of historical score corruption:** independent checks confirm all72actual groups are complete and truth-aligned. Wrappers' fixed loops and hash guards mitigated the executed runs but do not repair the standalone evaluator.
   Minimal fix: before any outputs, require exact expected fold/method/ordered unique ID sets, completion+source/data/protocol receipt, canonical labels/maturity/masks, valid probability/Q schema. Regression tests: missingF3, shifted truth, reordered/duplicated/out-of-fold IDs, corrupted probabilities must fail closed.

2. **Single-class AUROC diagnostics crash evaluation.** `btc_pattern_evaluate.py:30–33,54` catches only `ValueError`. Installed scikit-learn returnsNaN with a warning when binary labels contain one class; strict `write_json(...allow_nan=False)` then raises `ValueError: Out of range float values are not JSON compliant: nan`. The controlled one-class fixture reproduces this. Installed source/version is captured in `installed-AUROC-source.txt`.
   Impact: an otherwise scoreable one-class evaluation slice cannot finish/write gates. Existing actual outer folds have class variation; this did not explain prior results. Minimal fix: explicitly mark AUROC undefined (`None`) when either class is absent or result nonfinite, retaining strict JSON elsewhere. Test all-UP/all-NONE and empty-valid-D slices.

3. **Masked-D ES aggregation uses the wrong denominator when masks occur.** `btc_pattern_train.py:72–73` weights batch means by ALL batch rows, while `btc_pattern_models.py:55–59` Dmean uses only valid Drows. Two2-row batches with valid Dcounts1/2 and valid loss sums10/0 aggregate to5 rather than10/3. Q uses all rows and needs its own denominator.
   Impact is dormant here: every actual inner-ES set has0ambiguous D. Minimal fix: accumulate Dsum/n_valid and Qsum/n_rows separately, reconstructing L_predict; add mask-varying and all-masked batch tests. Current numerical ES selection was unaffected by this denominator issue.

## Reporting limitation, not proof of broken learning

`btc_pattern_train.py:77` reports an unweighted mean of minibatch means. It is not the row-weighted epoch loss, and parameters also change between batches. Example64+1rows with batch losses0/10: recorded5 versus row-weighted.153846. Actual F1CNN refit has79full64-row batches plus8rows: last batch receives1.25% of logged weight rather than.158%,7.91×. Standard shuffled minibatch optimization itself is not thereby a fixed-sample weighting bug. Use weighted sums/counts and retain separate saved-model full-dataset inference for fit/ES/outer comparisons; never equate online train curves with final-model generalization loss.

## Checked and not found broken

- `train.py:49–50,65–67`: seed7, new model+AdamW per fit, shuffled fullfit IDs, zero_grad→backward→clip→step. Saved parameters differ from fresh seed7 initial weights: L2deltaCNN5.50–7.22,TCN5.95–11.32,Kronos projection3.80–5.54. This refutes an optimizer-never-updated explanation, without a new training step. Optimizer step counters/state were not persisted, so exact runtime histories cannot be reconstructed independently from checkpoints alone.
- `train.py:80–85,177–178`: best ESstate is deep-copied, reloaded, then saved; all9baseline ES checkpoints' epoch fields match the actual strict1e−8 best-curve rule. All9fresh refits use exact complete purged prefixes and selected epochs, have distinct ES/refit weights, and start new model/optimizer/RNG state. No ESweight warm start was found.
- All18states' context normalization, Q MAD, signature IQR and sampled-pairtau reproduce from ONLY their own fit IDs; maturity/cutoffs pass. Folds/indices use the frozen full-history protocol; no rolling crop or future-learned scales found. Other agents own the separate input-footprint/data/retrieval audit.
- `models.py:55–59`: per-side .2/.5/.8 pinball shape/order and division by fit-only MAD match independent NumPy arithmetic; Dmask affects only D. Probe D=.63422918,Q=.19888890. Qtargets remain valid on D-ambiguous rows by contract; no sign/side-order reversal found.
- `train.py:94–102,168–178`: inference loads saved weights/scalers, sets eval plus inference_mode, retains batch order, and slices `index+query` at exact index length. Serialization pairs query IDs/labels correctly; all72actual groups' projections equal fixed max(0,sort(rawQ)). No new saved-model inference was required; existing parity/inference receipts were reused.
- CatBoost ES/refit: all18saved models' tree counts match selected receipts, classifier classes are[0,1,2], quantile heads retain alpha=.2,.5,.8 order. `tree_count_` is count, so fresh refit avoids a best-iteration off-by-one error.
- Raw Q is trained/ES-scored; fixed nonnegative sorting is evaluated and raw diagnostics retained. This is predefined projection, not learned calibration. Exit heads can pass without D; complicated/retrieval controls, same-ID pairing, bootstrap arithmetic and no-weak-only shortlist agree with the frozen protocol. No historical gate-arithmetic reversal was found.

## Methodological limits, distinct from implementation bugs

Hourly72h targets overlap heavily; shuffled training is not IID evidence. The14d calendar-block bootstrap is paired correctly (independent reconstruction matched exactly), but only29pooled blocks and temporal/model/fold dependence do not establish nominal coverage under documented regime drift. It conditions on saved models and omits model-refit/selection uncertainty. Multiple families/heads and development-driven recipe iterations reuse DEVELOPMENT; no multiplicity-adjusted or fresh CHECK result exists. Fixed maximum absolute-loss ranking also compares different task units, an explicit frozen choice rather than an implementation accident.

The28d ES distribution differs from subsequent four months; fit/ES/outer losses use different populations, and online scaled/dropout train loss is not raw projected-Q loss. Low fit loss or easier ES cannot alone diagnose classic overfit. Synthetic prior initialization passing after its known failure is algorithm debugging, not independent market validation. Bootstrap/coverage, terminal classification versus path skill, and actual ROI/DD remain separate claims.

## Minimal safer next process

Before any new model experiment: add the evaluator contract/negative-fixture tests and finite diagnostic handling; fix masked and reported aggregation; jointly resolve the data/retrieval agent's true input-footprint finding. Re-evaluate immutable existing forecasts/caches where valid before fitting anything. Persist actual optimizer-step counts, per-head valid counts/loss sums and immutable source/data/epoch receipt; keep fresh-refit and predictor-order assertions. Then require one reviewed/frozen hypothesis and original controls, with CHECK still isolated. This audit supplies no GO for a joint TP/SL model, extra epochs, pilot or trading.
