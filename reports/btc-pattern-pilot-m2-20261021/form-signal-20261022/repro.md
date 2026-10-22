# Reproduce the completed form study

Use the existing isolated environment, from the research worktree. No installation or new fitting is needed. Original immutable jobs are under runtime/var/research-jobs/btc-pattern-pilot-m2-20261021: form00-corrected, form00-precision-diagnostic, form01-context, form02-flat and form03-spatial.

The offline paired comparison and canonical validation can be recomputed from saved forecasts:

```sh
PYTHONPATH=runtime PYTHONPYCACHEPREFIX=/tmp/pattern-form-repro-cache runtime/var/research-envs/btc-pattern-pilot-m2-20261021/bin/python reports/btc-pattern-pilot-m2-20261021/form-signal-20261022/form03_completed_analysis.py
```

This runs no model inference or training; it rewrites only derived comparison/QA/manifest reports in this report directory. The first stdout-only NumPy-integer formatting failure is retained in form03-analysis-attempt01.json; the reproducible helper now casts that counter to a Python integer.

The original execution CLI is coinmaster.research.pattern_form_experiment, with mode context/flat/spatial, prepared and FORM00 baseline paths, protocol experiment-protocol-draft.json, the respective exact coordinator-form-*-go.json receipt and a new output directory. Exact source/data/protocol/resource/image/Context-comparator pins are in form01-source-freeze.json and form03-source-freeze.json. Training receipts authorize only the already-completed once-only runs; do not execute another run without a new coordinator GO. Context/Flat used source checkpoint21795a1; the spatial device-compatibility checkpoint is d5eecb3. No model/environment/old-result migration is needed.

The original local test bundle contained25distinct tests. Only the affected deterministic pooling/initialization test was rerun after the exact CPU-device route was added, followed by one zero-fit CPU/MPS output-gradient parity/resource probe. There is no applicable research CI workflow. No native economic run or CHECK scoring is part of this reproduction.
