# BTC pattern pilot M2 — 2026-10-21

Owner task: `owner-task.txt`. New local branch/checkout explicitly authorized; production untouched.

Baseline and the authorized full-history METRIC_OFF variant have completed. Baseline: 18 joint neural fits +18 CatBoost head fits; mandatory 4h-only control:18 CatBoost head fits. METRIC_OFF:12 joint neural fits,886.42s,NO_SKILL,empty shortlist. RECENT180 was cancelled before launch to preserve the owner's full-history requirement; zero fits. No process is currently training. CHECK remains unopened; no final/native/SOL promotion is authorized. Exact GO and immutable source receipts are retained; later proposals require a new GO.

- Genuine Bybit BTCUSDT linear-perpetual minutes: 2024-05-15 00:00 through 2026-10-21 00:00 UTC, contiguous. Public prefix retains 156 raw REST pages / 155,520 real minutes. Existing immutable source array verified by SHA before reuse.
- DEVELOPMENT is June 1, 2024 through May 1, 2026. CHECK actual confirmed end is October 21 00:00 UTC; prior requested freeze-hour retained separately. This CHECK was exposed by prior research and is historical validation.
- 20,928 valid origins; 20,856 mature 72h targets; 72 censored. Entry is first minute OPEN beginning origin+60 seconds; label end includes this extra minute. Separate reference/entry path indices and entry-gap arrays retain the origin-to-fill difference.
- Fresh first-passage D, conservative/upper Q, 12-coordinate signatures and fixed 24/72h × 3SL summaries. Old 24h outputs are not quality evidence.
- CPU/MPS true-window smoke passed, both 224px panels visually verified. TCN 75,465 parameters; CNN 103,305. Kronos frozen context API and 512+512 shape passed. MPS high watermark remains enabled, CPU fallback disabled; no native framework upgrades.
- Installed environment is isolated under this worktree. Previous ML environments are read-only through explicit `.pth`; only new PyArrow 21.0.0 wheel added here.
- Exact MPS peak memory is UNKNOWN; sampled current allocation/driver metrics are not peaks. Sampled RSS peak 1,239,252,992 bytes. Full training resource guard: RSS peak 6 GiB, total 21,600 seconds, one heavy process.
- Main full-30-epoch projection is 12,174 seconds including conservative overhead/reserves. Worst conditional CNN stability could exceed budget; before seed17/27/final/CHECK require selected-epoch measured estimate +20% within remaining budget, else INCOMPLETE_RESOURCE_STABILITY.
- DINO excluded by resource/priority decision before B1 quality. No optional-family search. Fixed context-matched random control uses sign return168h and fit-median volatility168h; reporting regimes separately use causal trailing30d statistics with fit thresholds. First 30d regime warmup before sufficient May15 history is UNKNOWN.

Commands (from this worktree; Python is `runtime/var/research-envs/btc-pattern-pilot-m2-20261021/bin/python`):

```sh
PYTHONPATH=runtime <python> -m unittest runtime/tests/test_btc_pattern.py -v
PYTHONPATH=runtime <python> -m coinmaster.research.btc_pattern_run train --protocol reports/btc-pattern-pilot-m2-20261021/protocol.json --prepared runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/prepared --output runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/development --authorization <exact-coordinator-GO.json>
PYTHONPATH=runtime <python> -m coinmaster.research.btc_pattern_run evaluate --protocol reports/btc-pattern-pilot-m2-20261021/protocol.json --prepared runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/prepared --input runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/development --output runtime/var/research-jobs/btc-pattern-pilot-m2-20261021/development-evaluation
```

No economic result, final model, CHECK pass, native replay or SOL admission is claimed. Conditional downstream stages remain blocked until appropriate forecast/path/policy gates.
