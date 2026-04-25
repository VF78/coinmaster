# ACTIVE_TASK

Updated: 2026-04-26 00:27 Europe/Madrid
Status: COMPLETE / #64 implemented, locally verified, pushed, GitHub issue closed, Project Done; pending production deploy verification
GitHub Project: https://github.com/users/VF78/projects/2
Completed item: #64 [ARCH-04] Backtest and optimizer target upgrade: Optuna, QuantStats, rolling windows, Experiment/ChampionConfig
Completed issue: https://github.com/VF78/coinmaster/issues/64
Canonical root: /root/.openclaw/workspace/coinmaster/coinmaster
Implementation commit: d93b3f81b3b484e8d3e882cecc527f9438b941a4
Production target: /opt/coinmaster
Production service: coinmaster.service

Project state:
- #61 Closed / Done
- #62 Closed / Done
- #63 Closed / Done
- #64 Closed / Done

Owner execution preference:
- Use Claude Opus first when available.
- Fallback to Codex after Opus limit/block.
- Claude Opus was still known-blocked from earlier usage limit, so Codex fallback was used for #64.

Completed for #64:
- Added durable `Experiment`, `ExperimentTrial` (`experiment_trial_v1`), and `ChampionConfig` DTOs.
- Added durable persistence collections for experiments, experiment trials, and champion configs across lowdb/postgres/replay DB shapes.
- Added `src/core/experimentGovernance.ts` for rolling-window scheduling, replay assumptions, Optuna/QuantStats sidecar boundaries, objective metrics, rejection stats, backtest/live delta reports, early-prune decisions, and ChampionConfig promotion.
- Kept `src/core/backtestEngine.ts` canonical; only added `expectancyUsd` to summary output.
- Backtest queue/worker now records coverage, replay assumptions, objective metrics, rejection stats, QuantStats boundary status, trade breakdown, and backtest/live delta report.
- Optimizer now creates/updates experiments and durable trials, evaluates candidates across rolling windows, records Optuna RDBStorage/pruner request/status, prunes poor trials deterministically, and nominates a candidate trial without owning live execution.
- Added owner APIs for experiment/trial reads and explicit acceptance-gated champion promotion.
- Added `docs/EXPERIMENT_GOVERNANCE_2026-04-26.md`.
- Added `scripts/invariants-experiment-governance.ts` and `npm run invariants:experiment-governance`.
- Deferred vectorbt, TA-Lib, cryptofeed, OpenBB, and Qlib as discuss-before-implementation items.

Verification passed locally before issue sync/deploy:
- `git diff --check`
- `npm run check`
- `npm run invariants:experiment-governance` → 9/9
- `npm run invariants:backtest-run-persistence` → 3/3
- `npm run invariants:compute-jobs` → 10/10
- `npm run build`

GitHub sync:
- Commented verification summary on issue #64.
- Closed issue #64.
- Updated GitHub Project #2: #61 Done, #62 Done, #63 Done, #64 Done.

Do not commit runtime noise:
- `coinmaster/data/db.json`
- `prod-backups/`

Next steps:
- Commit/push this task-state sync.
- Deploy only through `coinmaster/scripts/deploy-prod-safe.sh`.
- Verify `/opt/coinmaster/.deploy-source-commit`, service, `/api/health`, root HTML, and production source anchors.
