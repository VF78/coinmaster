# Exact CLI record

Commands run from `/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021`.
Use the isolated `runtime/var/research-envs/btc-pattern-pilot-m2-20261021/bin/python`; `PYTHONPATH=runtime`, `OMP_NUM_THREADS=4`, `OPENBLAS_NUM_THREADS=4`, `VECLIB_MAXIMUM_THREADS=4`. MPS needs host execution. Old output directories are immutable and commands refuse overwrite. Original absolute pipeline deadline2026-10-22T01:46:11Z remains in receipts; a future training replay requires a new exact coordinator GO, not a silent deadline change.

Focused tests (16passed):

```sh
PYTHONPATH=runtime <python> -m unittest runtime/tests/test_pattern_q_prior_init.py runtime/tests/test_pattern_full_es3.py runtime/tests/test_btc_pattern.py -q
```

Completed initial recipe and evaluator commands are recorded in the exact coordinator-development-go.json/pretrain-freeze-request.json. Baseline output is `runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/development`; baseline evaluator output is `.../development-evaluation`. METRIC_OFF uses `coinmaster.research.pattern_quality_variants --mode METRIC_OFF`; its exact source/protocol/data/controls are in quality-variants-freeze-request.json/coordinator-quality-variants-go.json. RECENT180 in that historical GO was explicitly revoked; never replay it.

Original baseline exact train/evaluate entry points (completed; original GO remains time-limited):

```sh
PYTHONPATH=runtime <python> -m coinmaster.research.btc_pattern_run train --protocol reports/btc-pattern-pilot-m2-20261021/protocol.json --prepared runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/prepared --output runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/development --authorization reports/btc-pattern-pilot-m2-20261021/coordinator-development-go.json
PYTHONPATH=runtime <python> -m coinmaster.research.btc_pattern_run evaluate --protocol reports/btc-pattern-pilot-m2-20261021/protocol.json --prepared runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/prepared --input runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/development --output runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/development-evaluation
```

Actual Q-prior-initialized synthetic invocation (completed once):

```sh
PYTHONPATH=runtime <python> -m coinmaster.research.pattern_q_prior_init --stage synthetic --protocol reports/btc-pattern-pilot-m2-20261021/protocol.json --recipe-protocol reports/btc-pattern-pilot-m2-20261021/q-prior-init-protocol.json --authorization reports/btc-pattern-pilot-m2-20261021/coordinator-q-prior-init-synthetic-go.json --prepared runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/prepared --baseline runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/development --output runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/q-prior-init-synthetic
```

Actual market invocation (completed once;6jointfits, no CHECK):

```sh
PYTHONPATH=runtime <python> -m coinmaster.research.pattern_q_prior_init --stage market --protocol reports/btc-pattern-pilot-m2-20261021/protocol.json --recipe-protocol reports/btc-pattern-pilot-m2-20261021/q-prior-init-protocol.json --authorization reports/btc-pattern-pilot-m2-20261021/coordinator-q-prior-init-market-go.json --qa-receipt runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/q-prior-init-synthetic/completion.json --prepared runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/prepared --baseline runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/development --output runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/q-prior-init-development
```

No-fit post-completion helpers: `variant_diagnostics.py` accepts mode-run/baseline/output/regimes; `q_prior_saved_model_diagnostics.py` and `q_prior_tp_sl_diagnostics.py` have fixed local paths and require completed artifacts. Corresponding pre-diagnostic-manifest and receipts retain helper/checkpoint SHA. The saved inference helper refuses a second diagnostic output creation via its caller; use a separately named audit directory for any approved replay. The TP helper corrects short percentage distance as1−exp(−qσ); forecast/loss/hit counts did not change.

Sources/data/weights/forecasts/neighbor tables and raw diagnostics are linked by absolute local paths and SHA in the artifact manifests. No large cache is committed to Git. Formal gates remain based on fixed common IDs,14d block CI,>=2/3folds, and original strong controls.
