# CoinMaster Freqtrade Migration — Owner Direction 2026-04-27

Status: owner-approved migration direction. This document supersedes older recommendations that kept live execution, backtesting, optimization, Telegram workflow, or the trading UI inside the custom CoinMaster engine.

Related GitHub Project tasks:

- #65 — Stage 1: autonomous native Freqtrade core.
- #66 — Stage 2: Freqtrade-native Radar, FreqAI, and governance.

## 1. Owner decision

CoinMaster is moving from a custom TypeScript trading engine to **native Freqtrade**.

Freqtrade becomes the source of truth for:

- exchange integration;
- Hyperliquid futures trading;
- dry-run and live execution;
- order, trade, position, and fill lifecycle;
- backtesting;
- hyperopt/optimization;
- native Telegram operations;
- native FreqUI/API operations.

The current CoinMaster trading engine is no longer the target runtime. It remains a **reference implementation** only until the Freqtrade migration reaches parity and live cutover succeeds.

## 2. Non-negotiable architecture constraints

### Stage 1 must be autonomous

Stage 1 is not an integration layer over the old CoinMaster runtime.

It must produce an autonomous native Freqtrade solution with:

- its own repository/runtime structure under the repo;
- its own Docker/compose/systemd/VPS deployment path;
- its own Freqtrade `user_data` layout;
- its own dry-run/backtest/hyperopt/live operational workflow;
- secrets handled outside git;
- no dependency on the old CoinMaster server process for trading.

The target end state of Stage 1 is: **old CoinMaster trading execution can be deleted or archived without losing trading functionality**.

### No parallel trading engines

Do not run old CoinMaster execution and Freqtrade live execution against the same Hyperliquid account.

Before live cutover:

1. stop/disable old CoinMaster trading execution;
2. confirm no parallel engine can open/reduce positions;
3. confirm current account/position state is understood;
4. start Freqtrade live only after backtest and dry-run acceptance criteria pass.

### No manual confirmation layer

Manual pending confirmations are not part of the new target architecture.

The new workflow is:

1. strategy validation through backtests;
2. parameter selection through hyperopt/backtest review;
3. dry-run validation;
4. live execution by Freqtrade.

### FreqUI-first operations

Use native Freqtrade/FreqUI/Telegram features first.

Do not rebuild a parallel CoinMaster control UI. If operator workflow gaps remain after Stage 1, prefer adapting/extending FreqUI in a later task.

## 3. Stage 1 — native Freqtrade core

Goal: move the whole trading loop to Freqtrade.

Scope:

1. Create autonomous Freqtrade runtime/deploy structure.
2. Configure Hyperliquid futures for `BTC/USDC:USDC`, `ETH/USDC:USDC`, `SOL/USDC:USDC` initially.
3. Study existing Freqtrade/community strategies before implementing custom logic.
4. Port the CoinMaster strategy into a Freqtrade `IStrategy`:
   - engulfing body pattern;
   - liquidity sweep;
   - FVG retrace;
   - long/short futures support;
   - ADX/EMA regime guard;
   - ATR impulse quality guard;
   - expected R:R guard;
   - SL/TP/ROI/custom exits;
   - time stop;
   - stake sizing;
   - leverage callback.
5. Use Freqtrade backtesting and hyperopt as the canonical research path.
6. Use Freqtrade dry-run as the mandatory pre-live gate.
7. Use native Telegram/FreqUI as the operator surface.
8. Prepare VPS cutover runbook.
9. Verify old CoinMaster trading execution can be removed/archived after cutover.

Acceptance criteria:

- Freqtrade validates the strategy and config.
- Hyperliquid futures pairlist resolves correctly.
- Backtests are reproducible and show acceptable strategy quality.
- Hyperopt/search space is defined and usable.
- Dry-run runs stably.
- Native Telegram/FreqUI cover the operator workflow.
- Old CoinMaster execution is not running in parallel.
- Secrets are not committed.
- VPS deployment path exists.

## 4. Stage 2 — new Radar, FreqAI, governance

Stage 2 starts only after Stage 1 is usable.

Radar is rebuilt **from scratch** in a Freqtrade-native architecture. The existing CoinMaster Radar is not imported as a legacy runtime dependency.

Stage 2 scope:

1. Build a new minimal `RadarContextPolicy` layer around Freqtrade:
   - direction mode;
   - risk multiplier;
   - lock new entries;
   - valid-until / TTL;
   - reason codes.
2. Feed that policy into Freqtrade strategy decisions as guards/modifiers.
3. Ensure Radar never becomes a second execution engine.
4. Configure FreqAI as the main advanced analytics/model workflow.
5. Decide which Radar/context features become FreqAI features.
6. Add governance around Freqtrade hyperopt/backtests/FreqAI results:
   - current champion;
   - candidate configuration/model;
   - comparison evidence;
   - explicit promotion decision.
7. Keep UI/control FreqUI-first.

Out of scope for Stage 2 unless explicitly re-approved:

- manual approval layer;
- old CoinMaster Radar runtime integration;
- separate CoinMaster control shell;
- custom analytics/postmortem stack outside Freqtrade/FreqAI.

## 5. Role of old CoinMaster code during migration

Old CoinMaster code is reference material only:

- strategy semantics reference;
- parameter/reference behavior source;
- historical bug lessons;
- comparison baseline for backtest/dry-run.

It should not become a runtime dependency for the new Freqtrade core.

Allowed uses:

- read old evaluators and docs;
- port concepts into Freqtrade strategy;
- compare results;
- preserve useful lessons in docs.

Disallowed uses:

- call old CoinMaster execution path from Freqtrade;
- depend on old pending confirmation flow;
- keep old Radar as a live Stage 2 dependency;
- maintain two production trading engines.

## 6. Reset / handoff rules

Future sessions should continue #65 by reading, in order:

1. this document;
2. GitHub issue #65;
3. `freqtrade/README.md`;
4. `freqtrade/user_data/strategies/CoinMasterStrategy.py`;
5. old strategy evaluator files only as reference.

Work mode:

- primary assistant works directly; do not use subagents unless owner explicitly approves;
- keep commits small and validated;
- push the branch after meaningful milestones;
- update #65 when scope/acceptance materially changes;
- do not modify old CoinMaster execution except for clearly marked migration/removal tasks.

## 7. Stage 1 implementation update — 2026-04-27 overnight

The Stage 1 runtime has been advanced from baseline smoke to dry-run candidate:

- `CoinMasterStrategy` now executes on base `5m` with informative `15m`, `1h`, and `4h` data.
- Trading Rules entry timeframes `5m/15m/1h/4h` are exported to Freqtrade and consumed by strategy gates.
- HTF FVG logic runs on native informative `1h/4h` data with retrace, sweep lookback, first-touch/fresh-zone, max-age, and optional engulfing confirmation timeframes.
- Regime filtering uses the selected informative `1h/4h` dataframe.
- Opposite-engulfing emergency exit UI/runtime export has been removed from the Freqtrade path; exits are SL/TP/time-stop/protections.
- Signal Quality / Portfolio guards are exported as explicit enable/disable flags and inactive guards do not affect decisions.
- Dry-run runtime is Freqtrade-native; the companion app is configuration/reference only.

Current selected dry-run candidate from 2026-01-01 through 2026-04-26 backtests:

- Pairs: `ETH/USDC:USDC`, `HYPE/USDC:USDC`.
- Sides: long + short.
- Entry TFs: `15m`, `1h`, `4h`.
- FVG sweep/first-touch/confirmation enabled.
- TP levels: `1.5 / 3 / 6`; SL: `2`.
- Result: 42 trades, +39.36%, profit factor 1.73, Sharpe 1.27, Sortino 4.89, max drawdown 15.28%.

Live cutover is still a separate owner-approved step. Dry-run may run unattended for observation, but live mode must not be enabled without explicit approval after reviewing fresh dry-run orders/logs and account state.
