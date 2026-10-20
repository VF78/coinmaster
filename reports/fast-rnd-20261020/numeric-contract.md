# FAST numeric contract

Implementation only; no market fit or recognizer comparison has run. Actual fits require separate root GO after S0 and dataset completion. No trading logic or source outside the two new numeric files changes.

## Frozen dataset interface

Dataset directory contains features.npy float32[N,6,20,6], context.npy float32[N,20], panel_end_indices.npy[N,6], samples.csv, and panels.npz. Panel order BTC1h,SOL1h,BTC4h,SOL4h,BTC1d,SOL1d; field order O,H,L,C,V,causalMA20. NPZ keys p{0..5}_available_ns and p{0..5}_values (raw six-field values), alongside builder open_ns keys. Continuous native clocks retain missing bars as NaN. Numeric source never concatenates selected rows into a clock.

Public import is stdlib+NumPy only. Dataset(path) exposes rows, features/context/ends memmaps and panel(p)->(available_ns,raw_values). Sample fields: row,sample_id,decision_ns,horizon_end_ns,ready_ns,labels,selected_train,eligible. U rows are skipped before parsing label/ready fields. This is an intentional pre-finalist reader; it does not provide a U-fit option.

partition(rows,start,cutoff,predict_end) returns common selected eligible train and complete eligible prediction IDs. Full horizon_end_ns must be strictly less than the next partition start for both subsets. Early touch does not relax purge. Fixed fold cutoffs from experiment-lock.json: first20% T -> next20%; first40% -> next20%; all T -> V. V/U boundaries remain fixed. No outcome-based sample refill.

## Fixed recipes

- Prior: empirical two-asset three-class frequencies; UP=0,DOWN=1,NONE=2.
- Simple: context20 plus six panels x log(close_last/close_previous), log(close_last/close_5_bars_earlier), log(close_last/close_first_window), total38. All within the same available20 bars. Train-only StandardScaler and two fixed C1 lbfgs LogisticRegression heads, max_iter1000. Missing train classes retain zero class probability; single-class train heads are explicit constants. Report log loss clips probability at1e-12.
- STUMPY: per asset/TF five prices log(P_j/C_previous)/train return std, one common scale perasset/TF; volume log1p standardized by train only. Population std ddof0; epsilon1e-12. Both assets/all12 channels; mstump m20 normalizeFalse p2, mmotifs k11 max8 min_neighbors3 max_matches50. Train-native history only, no U computation; match normalizeFalse p2 max50 with explicit frozen linear P90 of independent train nearest-neighbor distances, recomputed as mean per-channel L2 in match units. Distances with separation below max(20TF,72h) are excluded; absent independent calibration distances is an explicit blocker. No threshold tuning.
- Analogue: only common selected train IDs, same higherTF age, full horizon ready at query, no near copies. Greedy distance-ranked episodes separated by max(20TF,72h); (counts+3*train_prior)/(n+3), prior if n<3; equal average overTFs. V labels never enter memory. Catalogue includes raw transformed prototypes, independent occurrences, train IDs/labels/horizon references; held-out match labels are separately annotated and never learned. Up to3 patterns now get actual raw-price historical-match previews: choose up to2 independent common-train occurrence IDs per pattern, showing both assets'20 native-TF raw OHLCV/MA20 input records and genuine hourly closes strictly in(decision,decision+72h]. Small SVGs use actual-price axes and explicitly separate native-window and hourly-continuation time scales. JSON retains source panel/manifest paths, decision/input-end/horizon timestamps and sample trajectory indices. Missing/insufficient independent train matches or continuation hours remain explicit. These future train annotations are diagnostics only and never enter features, scales, thresholds or analogue memory.
- MiniRocket: three independent aeon1.6.0 MiniRocket n_kernels2000 seed7 n_jobs1, expected actual1932 outputs each; reject unexpected width. Concatenate + context20; same scaler/two heads.
- RDST: three independent aeon1.6.0 RandomDilatedShapeletTransform max_shapelets512 proba_normalization.8 seed7 n_jobs1, fit(X) WITHOUT labels, default lengths. Actual widths recorded; three features/shapelet min distance,argmin,count. Save full learned shapelets in model.pkl plus top coefficient associations and real minimum-distance sample IDs. Coefficients are not causal explanations.

metrics(rows,proba[N,2,3]) returns per-asset logloss, sum-of-class multiclass Brier, class frequency,10-bin per-class calibration, monthly losses, N and greedily separated72h episode counts. Fits/inference timings and process peak RSS recorded. select_recognizer waits for all four including mandatory CNN and controls on identical validation ID hashes, applies BTC simple-control safeguard, then minimum mean logloss; relative difference denominator is lowest mean logloss, below1% chooses measured lower fit+inference cost then simpler recipe. Negative added information is explicit; no ROI inference.

## Resources, outputs, execution gate

AEON/STUMPY/sklearn imports are lazy. NUMBA_NUM_THREADS1 and n_jobs1; CLI threadpool limits1. Inputs are memmaps; six raw panel arrays are loaded from NPZ once and reused by object identity to prevent per-query whole-array copies. Transforms are128-row chunks into private float32 disk arrays, standardized in place, then removed after successful fit. No image corpus or market all-pairs matrix. Native TF STUMPY remains quadratic CPU work and must be measured in the authorized stage; implementation does not claim validated full-fit memory or runtime. Failed stage outputs remain visible for diagnosis; output directories must be new.

Per stage/fold: metrics.json (recipe and common-ID SHA256s), predictions.csv (same IDs/class order), model.pkl; STUMPY adds catalogue.json and small SVGs. Never load untrusted pickle. Models are not traded or deployed.

Ready command, only after separate ROOT GO, isolated environment and measured resource admission:
```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1 runtime/var/research-envs/fast-rnd-20261020/bin/python -m coinmaster.research.fast_numeric --dataset DATASET --lock reports/fast-rnd-20261020/experiment-lock.json --output NEW_OUTPUT --stage stumpy --fold validation --execute-fit
```
Set PYTHONPATH=runtime when invoked at repo root. Run stages prior/simple then STUMPY -> MiniRocket -> RDST, under root stage gates; OOF folds use same recipe/strict purge. Omitting --execute-fit prints only command plan, without reading market data. CNN is separate and mandatory before final selection.

## Verification

Synthetic focused tests cover strict horizon purge, future-invariant scales, common price scale, age/readiness/near-copy exclusion, spacing and prior smoothing, skipping U labels, chunk feature order/context, class-aligned metrics, selection-completeness gate, and tiny logistic missing-class behavior. No market data or aeon/STUMPY transformer fit in tests.

Current status: stdlib syntax compile PASS. Exactly one root-authorized synthetic suite PASS:8 tests in4.015s, process maxRSS148426752bytes, transient MemoryMax268435456bytes / MemorySwapMax0 / CPUWeight10 / Nice15 / BLAS-OMP-Numba threads1. No AEON/STUMPY import/JIT or market reads/fits. Test output: all8 named tests OK; unittest exit0. Full market-fit resource cost remains unverified and separately gated.

Root bounded correction verification: affected numeric suite9/9 PASS in4.049s, peakRSS148918272bytes under256MiB/swap0/thread1. One new targeted test checks continuation timestamps strictly after decision and at/before horizon, genuine raw BTC/SOL prices and single-load panel-cache identity. Original8 tests also remain passing. No market read/fit or AEON/STUMPY import/JIT. No classification/matching recipe change.
