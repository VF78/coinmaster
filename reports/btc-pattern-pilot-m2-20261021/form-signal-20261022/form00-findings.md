# FORM00 correctness repair and zero-fit re-score

B1 now records raw and engineered starts separately for newly prepared data and resolves legacy metadata without modifying it. TCN/numeric engineered support starts80h earlier; CNN/Kronos raw support is unchanged. Random-context retains its original conservative raw256h exclusion. Full historical prefixes and the original cosine normalization, k32, greedy72h separation and prior mass8 remain unchanged.

B2 requires a hashed completion/compatibility/source/data contract before evaluation, all3folds for every declared method, canonical ordered unique outer IDs/truth, mature data and valid probability/Q/support schema. Actual metadata/labels are checked against their original manifest hashes; the rescore also checks loaded features/context/raw. B3 undefined AUROC is null with reason. B4 D/Q losses now aggregate with separate valid-D/row denominators. R1 online epoch losses use those sums/counts and explicitly retain parameter-changing online semantics; actual optimizer-step counts are saved. No change to the optimizer update or target loss.

FORM00 completed100.011s CPU4; zero encoder fits/optimizer updates/CHECK use. The original saved TCN checkpoints were inferred on CPU because baseline z was not persisted. New representations are cached. CPU versus original saved-neighbor cosine discrepancies are quantified in form00-QA.json; mathematical weights/input/recipe are unchanged, but exact device-bit identity is not claimed.

| Method | Original D / corrected D | Original long-Q / corrected | Original short-Q / corrected |
|---|---:|---:|---:|
| numeric-knn |1.106193 /1.105514|.208350 /.208342|.262235 /.262222|
| TCN-knn |1.144479 /1.144606|.211843 /.211882|.264977 /.264943|

TCN reconstruction is measurably sensitive to near-ties: CPU-old-support vs archived neighbor sets differ28/3/164queries and Q15/1/101rows; same-CPU corrected-vs-old-support Q changes141/88/14rows. Thus the additionalF3changes are not the80h correction. Support-only TCN deltas D+0.0000966,QL+0.0000340,QS−0.0000443 all have14d paired CIs including0. Detailed total/device/support comparisons are preserved in form00-comparison.json. The extra zero-fit cached-representation decomposition took32.270s, with0new inference.

These are row-weighted means over the same8496 outer origins, not significance claims. Corrected gates remain NO_SKILL with an empty shortlist. The repaired exclusion does not establish a predictive winner. Corrected numeric Q changed77/163/141rows and TCN156/89/115rows acrossF1/F2/F3. All24 unaffected NPZ files are byte-identical, including prior/CatBoost/CNN/Kronos/directTCN/random controls. No corrected saved neighbor violates its true query support; all710 invalid archived pairs are absent.

Validation:20 focused/reused tests PASS3.067s, including missingfold, shiftedtruth, reordered/duplicateIDs, invalid/NaN probabilities, projection corruption, stale canonical-byte manifest, protocolhash, undefinedAUROC, mask-varying/allmasked D and row-weighted tail loss. Older synthetic toy-kNN tests are not a trainable-model positive control. No old artifacts were overwritten.

Reproduce from this worktree with the existing isolated environment:

```sh
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 VECLIB_MAXIMUM_THREADS=4 PYTHONPATH=runtime runtime/var/research-envs/btc-pattern-pilot-m2-20261021/bin/python -m coinmaster.research.pattern_form00 --prepared runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/prepared --baseline runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/development --protocol reports/btc-pattern-pilot-m2-20261021/protocol.json --output /tmp/form00-new-output
```

The output directory must be new. `form00-freeze.json` pins sources/protocol/resource contract; `form00-local-artifact-manifest.json` preserves forecast/representation/neighbor hashes outside Git. Next FORM01/02 implementation is authorized; market fits await exact coordinator GO. No pilot/native/economic results are produced.
