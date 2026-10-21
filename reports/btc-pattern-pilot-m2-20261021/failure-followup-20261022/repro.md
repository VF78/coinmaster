From the existing owner worktree, isolated Python and `PYTHONPATH=runtime`; CPU threads4.

```sh
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 PYTHONPATH=runtime runtime/var/research-envs/btc-pattern-pilot-m2-20261021/bin/python -m unittest discover -s reports/btc-pattern-pilot-m2-20261021/failure-followup-20261022 -p 'test_followup.py' -v
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 PYTHONPATH=runtime runtime/var/research-envs/btc-pattern-pilot-m2-20261021/bin/python reports/btc-pattern-pilot-m2-20261021/failure-followup-20261022/followup.py
```

This reproduces only frozen descriptive calculations, no fitting/backtest/new predictions. Source/protocol/input forecast hashes and128feature proofs, purged-fit IDs/terciles are in feature-strata-freeze.json. All artifacts live only in this follow-up subdirectory; earlier frozen reports/core remain unchanged. Completion records runtime.821s and8496origins. The future joint-barrier experiment in findings.md is not authorized or started.
