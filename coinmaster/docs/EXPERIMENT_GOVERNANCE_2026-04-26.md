# Experiment Governance 2026-04-26

Issue anchor: `#64`

## Scope
- `src/core/backtestEngine.ts` stays canonical for promotion decisions.
- Research state is durable and separate from live execution ownership.
- Optuna and QuantStats are optional sidecars with explicit availability status.

## Durable records
- `Experiment`
- `ExperimentTrial` with schema version `experiment_trial_v1`
- `ChampionConfig`

Each record stores:
- Trading Rules snapshot
- RadarContextPolicy replay assumptions snapshot
- symbol/timeframe coverage
- data window / rolling windows
- engine version and commit
- objective metrics
- rejection and block statistics
- backtest/live delta report when matching live data exists

## Rolling-window defaults
- train window: 3 months
- test window: 1 month
- walk-forward step: 1 month

If the requested range is too short for a full walk-forward cycle, the scheduler falls back to one deterministic full-range test window instead of inventing train/test history.

## Sidecar boundaries
- Optuna boundary uses a Postgres `RDBStorage` request/status shape and explicit pruner config.
- If `python3` or `optuna` is unavailable, the system records `unavailable`; if the runtime is detected but the canonical TS worker executes the candidate, it records `skipped` rather than pretending an Optuna study ran.
- QuantStats requests are also recorded explicitly; no tearsheet is fabricated when the runtime is missing.

## Promotion workflow
- Optimizer runs can nominate a candidate trial on the experiment.
- Champion promotion is explicit and acceptance-gated.
- Promotion writes evidence references to experiment, trial, and source run/optimization ids.
- Failed acceptance does not create an active champion.
