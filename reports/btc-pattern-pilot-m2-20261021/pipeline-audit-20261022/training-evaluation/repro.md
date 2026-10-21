Run from the current owner worktree with isolated Python, CPU4:

```sh
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 PYTHONPATH=runtime runtime/var/research-envs/btc-pattern-pilot-m2-20261021/bin/python reports/btc-pattern-pilot-m2-20261021/pipeline-audit-20261022/training-evaluation/audit.py
```

No fit/optimizer step or saved-model inference occurs. It reads18existing checkpoints,18CatBoost models and72forecast groups; computes small independent loss/bootstrap arithmetic; writes tiny deliberately malformed synthetic forecast fixtures ONLY under this audit folder. These fixtures are not research forecasts or backtests. For an exact fresh rerun, use a copied audit directory: resumed partial fixture outputs are preserved and an existing successful gate fixture is reused. The initial one-class diagnostic crash was retained and then explicitly captured; source/core were never patched. evaluator-guard-repro.json distinguishes the false-pass and one-class-crash cases.
