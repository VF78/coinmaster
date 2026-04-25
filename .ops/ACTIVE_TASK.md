# ACTIVE_TASK

Updated: 2026-04-26 00:23 Europe/Madrid
Status: ACTIVE / #64 implemented and locally verified; pending commit, GitHub sync, deploy, production verification
GitHub Project: https://github.com/users/VF78/projects/2
Active item: #64 [ARCH-04] Backtest and optimizer target upgrade: Optuna, QuantStats, rolling windows, Experiment/ChampionConfig
Active issue: https://github.com/VF78/coinmaster/issues/64
Canonical root: /root/.openclaw/workspace/coinmaster/coinmaster
Branch / starting HEAD / origin divergence / deploy commit: main / b28e82468665433f9e122c1cfe2349ebbcd6e6f7 / 0 ahead, 0 behind / b28e82468665433f9e122c1cfe2349ebbcd6e6f7

Project state at start:
- #61 Closed / Done
- #62 Closed / Done
- #63 Closed / Done
- #64 Open / In Progress

Owner execution preference:
- Use Claude Opus first when available.
- Fallback to Codex after Opus limit/block.
- Claude Opus was still known-blocked from earlier usage limit, so Codex fallback was used for #64.

Implemented for #64:
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

Verification passed locally:
- `git diff --check`
- `npm run check`
- `npm run invariants:experiment-governance` → 9/9
- `npm run invariants:backtest-run-persistence` → 3/3
- `npm run invariants:compute-jobs` → 10/10
- `npm run build`

Do not commit runtime noise:
- `coinmaster/data/db.json`
- `prod-backups/`

Next steps:
- Commit/push #64 implementation.
- Comment and close issue #64; mark Project item Done.
- Deploy only through `coinmaster/scripts/deploy-prod-safe.sh`.
- Verify `/opt/coinmaster/.deploy-source-commit`, service, `/api/health`, root HTML, and production source anchors.
