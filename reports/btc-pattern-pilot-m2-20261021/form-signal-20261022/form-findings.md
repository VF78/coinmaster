# Full-history form controls — bounded result

All three planned form tests are complete. Every overall development gate is **NO_SKILL**; no new predictive winner is admitted. FORM04 is **NOT_ADMITTED**: no eligible forecast/path component. CHECK, native economics, S0 and the trading pilot were untouched. Actual ROI/DD is **NOT_EVALUATED** (native runs0); TARGET_NOT_MET means the goal remains unmet/unproven, not a computed low ROI.

The full DEVELOPMENT period `[2024-06-01,2026-05-01)` and all8496 out-of-fold origins remain. Each training prefix expands from June1; no180d crop, favorable-month selection, new targets, feature search or optimizer sweep was introduced. Q remains the .2/.5/.8 MFE quantiles before the same fixed1σ72 stop over72h; it does not learn an optimal SL or guarantee80% success for all3TPs.

## Absolute losses on identical outer IDs

D is log loss; Q is mean pinball over the three quantiles in originalσ72 units. Lower is better; different task units are not interchangeable.

| Method | D | Qlong | Qshort |
|---|---:|---:|---:|
|Prior|1.093512|0.205775|0.256859|
|Context|1.112849|0.204406|0.262645|
|Original CNN|1.089753|0.203798|0.256738|
|Grouped numeric corrected|1.105514|0.208342|0.262222|
|Flat780|1.108080|0.208020|0.261592|
|CNNSpatial|1.095582|0.206677|0.258664|

## Spatial incremental comparisons

**Every delta is CNNSpatial minus comparator; negative is better.** Intervals are paired14d calendar-block bootstrap/1000draws/seed7.

| Comparator | Head | F1 | F2 | F3 | Mean [95%interval] | Spatial wins |
|---|---|---:|---:|---:|---|---:|
|CNN-direct|D|+0.021628|-0.011082|+0.007375|+0.005829 [-0.032769,+0.038427]|1/3|
|CNN-direct|Q-long|+0.003570|+0.002421|+0.002659|+0.002880 [-0.001359,+0.007315]|0/3|
|CNN-direct|Q-short|+0.003975|-0.000505|+0.002370|+0.001926 [-0.002890,+0.006956]|1/3|
|Context-direct|D|+0.027977|-0.076001|-0.002271|-0.017267 [-0.070174,+0.025851]|2/3|
|Context-direct|Q-long|+0.003985|+0.002409|+0.000415|+0.002271 [-0.001059,+0.005612]|0/3|
|Context-direct|Q-short|+0.000347|-0.008618|-0.003556|-0.003982 [-0.008782,+0.000183]|2/3|

All spatial-minus-original-CNN means are positive and their intervals include0; long-Q loses in all3folds. Against Context, spatial short-Q has2/3wins but its interval upper bound is+.000183, so it is not a pass. Spatial direct and retrieval heads all remain NO_SKILL against the frozen control requirements.

Original CNN does beat Context on short-Q: Context-minus-CNN+.005908 [+.000342,+.012215], with CNN better3/3folds. This supports incremental window evidence for that comparison, not profitable forecasting: original CNN short-Q versus prior is only about−.000122 with an interval including0. Context D/long-Q versus CNN remain unresolved. Removing the image also changes model capacity; causal information and capacity are not separately identified.

Unaveraged Flat780 versus corrected grouped204 has D+.002567, Qlong−.000322, Qshort−.000629; every paired interval includes0, with1/3,1/3,2/3wins. Its short-Q is worse than prior by+.004733 [+.001359,+.007917]. Preserving all positions did not establish an improvement under this fixed standardized/L2/cosine rule; this does not prove the discarded positions contain no information.

## Correctness, resources and evidence

FORM00 repaired B1raw/engineered support, B2complete/canonical/hash gates, B3undefinedAUROC, B4valid-D denominators and R1online-loss reporting. All710 invalid archived TCN/numeric neighbor pairs are absent after correction. Its gate remained NO_SKILL. CPU reconstruction caused near-tie ranking changes; the same-CPU old/new-support decomposition is preserved, so changes are not all attributed to the80h fix. Old artifacts remain immutable.

FORM01 used exact Heads(0)/same12context, CNN-matched batch64/procedure and common conservative raw256h retrieval support. It completed6joint ES/refit fits in36.863s/5201updates (selected epochs3/8/1). FORM02 trained0encoders, completed32.048s, and changed only grouped204 to flattened780 coordinates with the same fit-only standardization/L2/cosine/k32/72h spacing/prior8.

FORM03 changed only global pooling to2×8 plus the corresponding2048-feature Heads input. The original224×224 cache and convolution initialization were retained. MPS cannot natively pool28×28→2×8, so only this stock adaptive-pool operation uses a differentiable CPU route. Fixed output/input-gradient parity was exactly0; deterministic position patterns collide under global pooling but remain distinct under2×8. No alternate pooling, resizing, learned layer or environment upgrade was added.

Spatial completed6joint fits in775.997s/3632updates, selected refit epochs2/3/1. Final process peak RSS was3,078,094,848bytes (~3.08GB), including evaluation, below the6GiBguard. The2456swall guard/default watermark remained unchanged. Exact training MPS peak was not measured; cleanup driver allocation is not a peak. Resident-tensor resource timing excludes full image preparation, so actual pipeline step cost was higher; the fixed run still completed within its guard. New FORM01/03 market fits total12joint/8833optimizer updates; all resource/position checks trained0models.

Local verification:25distinct focused/reused tests passed; the affected pool-position/initialization test was rerun after compatibility routing, and CPU/MPS output+gradient parity passed. No applicable research CI exists; no claim of CI-green or native-backtest validation is made. FORM01/02 validated69fold-method groups; FORM03 validated36more. All90 inherited control NPZ files were checked byte-identical to FORM00.

Only29paired blocks support the intervals; overlapping72h targets, fold/model dependence, drift and repeated DEVELOPMENT reuse limit inference. These are conditional exploratory comparisons, without multiplicity correction, model-refit uncertainty or a fresh CHECK claim. No economic policy is inferred from an isolated head result.

Detailed tables: `form-summary-metrics.csv`, `form01-02-comparison.csv`, `form03-paired-comparison.csv`. QA/source/protocol/resource/image pins and local weight/forecast/representation manifests are adjacent. Completed-analysis helper performs0fits/0model inference. Its initial stdout-only NumPy integer serialization failure was corrected; calculated artifacts and results were unchanged, with the attempt retained.

No active model jobs remain. No automatic next family, retraining, calibration, policy or economic run is authorized by this result.
