# ACTIVE_TASK

Updated: 2026-04-23 Europe/Madrid
Status: ACTIVE / optimizer startup race fixed and deployed; backtest surface stable for continued ROI testing
GitHub Project item: #26 active — TR-03 FVG retrace trigger engine (structure break + retrace %)
Canonical root: /root/.openclaw/workspace/coinmaster/coinmaster
Branch / HEAD / origin/main / deploy commit / divergence: main / 05291c5122b019a71dbaf89981795806e8778e6c / 05291c5122b019a71dbaf89981795806e8778e6c / 05291c5122b019a71dbaf89981795806e8778e6c / synced with origin and deploy
Goal: keep FVG/live/backtest/optimization on one shared rules surface, with a stable Backtest UI and a working optimizer for reproducible ROI experiments
Done:
- restored and deployed Alpha Radar end-to-end
- updated GitHub Project Radar statuses to Done where completed
- analyzed reset-context loss and execution-controls drift
- split ops docs into dedicated development + reset protocols
- removed bootstrap residue and trimmed duplicate/stale top-level docs into compact pointers/indexes
- added explicit ROI mandate to project truth docs
- removed non-ROI / obsolete items from the GitHub Project board
- reopened GitHub issue #26 and moved it back into active work
- completed FVG repo audit + external ICT/FVG research pass
- clarified and locked the approved #26 implementation scope in GitHub + ops state
- implemented and deployed the first bounded FVG quality slice:
  - sweep + displacement gate
  - fresh / first-touch mitigation gate
  - lower-TF confirmation gate
  - configurable lower-TF mapping in Trading Rules
  - shared live/backtest FVG qualification path
  - updated invariants and settings model/UI
- verification completed:
  - npm run check ✅
  - npm run invariants:fvg ✅
  - npm run build ✅
  - deploy-prod-safe.sh ✅
  - /api/health ✅
  - /api/settings/trading-rules returns new FVG fields ✅
Next exact step: use the now-working optimizer on bounded FVG parameter batches, then compare out-of-sample stability before any live rule changes
Checks / commit / deploy / push:
- latest product commit: 05291c5122b019a71dbaf89981795806e8778e6c (`fix: keep optimization queued until worker claim`)
- latest product checks: check, build passed
- latest product deploy: scripts/deploy-prod-safe.sh successful
- latest ops commit: pending current task-state sync
- push state: product synced to origin/main; ops sync pending current update
Blockers / risks:
- memory_search unavailable; rely on local docs + live repo state
- external ICT/FVG material is mostly practitioner content, not statistically rigorous research; treat as heuristic input, not proof
- ROI value of the new shipped gates is still unproven until ST9 comparative backtests are run and reviewed
- baseline BTC ST9 backtest completed: `huh1LCpCRj8K1kpHpBHwZ` → ROI -43.5%, net PnL -435.04 USD, 40 trades, max DD 81.21%
- first completed sweep+displacement run: `nwGE_8FLRInJU1dxxw7Hm` → ROI 314.28%, net PnL 3142.84 USD, 28 trades, max DD 58.16%
- first completed first-touch-only run: `0uEcadVLFW95L6GiOTOf7` → ROI 314.28%, net PnL 3142.84 USD, 28 trades, max DD 58.16%
- stale running runs were manually reset in persistence to restore a clean queue: `uJij_c6xuRrf96MOsUZsi`, `bHTqd5aTPY_RdY1A3IOgn`, `ci8k9esg0szC_uY2mm8nP`
- suspicious equality was rechecked using the baseline run's exact rules snapshot with only target FVG flags changed:
  - rerun first-touch-only: `lCcddlzxT6WqXqSLVnmOO` → ROI 314.28%, net PnL 3142.84 USD, 28 trades, win rate 67.86%, max DD 58.16%
  - rerun sweep+displacement: `-McOPrL9N27Ly4hHMgTwG` → ROI 314.28%, net PnL 3142.84 USD, 28 trades, win rate 67.86%, max DD 58.16%
- comparison harness check passed: all other tested parameters were held constant; only the intended FVG gate booleans changed between the reruns
- runner persistence bug fixed and deployed in product commit `fc36b2aa2a79c880615cfe9c419623295e9080c3` (`fix: persist backtest run completion`)
- root cause confirmed: backtest worker held a stale `run` reference across awaits while shared store reloads could replace the underlying snapshot object
- added regression invariant: `npm run invariants:backtest-run-persistence` ✅
- lower-TF-only rerun on clean fixed runner: `svMCr1Kw7cYESMzAl5ods` → ROI 314.28%, net PnL 3142.84 USD, 28 trades, win rate 67.86%, max DD 58.16%
- combined rerun on clean fixed runner: `WY5iIPdIwvW8lO9-SllvM` → ROI 314.28%, net PnL 3142.84 USD, 28 trades, win rate 67.86%, max DD 58.16%
- clean-comparison outcome for BTC on 2026-01-01 → now:
  - baseline: ROI -43.5%, 40 trades, max DD 81.21%
  - sweep+displacement only: ROI 314.28%, 28 trades, max DD 58.16%
  - first-touch only: ROI 314.28%, 28 trades, max DD 58.16%
  - lower-TF only: ROI 314.28%, 28 trades, max DD 58.16%
  - combined: ROI 314.28%, 28 trades, max DD 58.16%
- implication from prior analysis: on the tested BTC window, all three prior gate versions converged to the same accepted trade set
- user approved and implementation completed for the next bounded revision:
  - remove displacement logic and keep sweep-only over configurable lookback X
  - keep first-touch logic and add maxZoneAgeCandles
  - replace lower-TF mapping confirmation with post-retrace engulfing-body confirmation over allowed confirmation timeframes (5m/15m/1h/4h)
- revised FVG logic shipped in product commit `7b7b7830ba34fe8771caca6ee9dced505c56ed31` (`revise FVG sweep and confirmation rules`)
- verification completed on revised logic:
  - npm run check ✅
  - npm run invariants:fvg ✅
  - npm run invariants:rule-engine ✅
  - npm run invariants:backtest-run-persistence ✅
  - npm run build ✅
  - deploy-prod-safe.sh ✅
  - /api/health ✅
  - /api/settings/trading-rules returns revised FVG fields ✅
- live rules API now exposes revised settings:
  - fvgRequireSweep
  - fvgSweepLookbackCandles
  - fvgRequireFirstTouch
  - maxZoneAgeCandles
  - fvgRequireConfirmation
  - fvgConfirmationTimeframes
- latest user-requested follow-up:
  - verify whether backtest uses the same shared trading decision logic as prod without hidden duplicate signal paths
  - add all missing engine settings from Trading Rules to Backtest page, preferably mirroring the Trading Rules controls where practical
- current conclusion:
  - backtest shares canonical FVG/engulfing evaluators and common rules semantics, but still runs through a separate isolated simulation loop rather than the literal live execution pipeline
  - Backtest page parity task is now completed for the revised FVG controls on the shared rules model
- completed in the previous pass:
  - added the missing revised FVG controls to Backtest page
  - wired them through load/reset/run snapshot handling using the existing TradingRulesSettings model
  - mirrored Trading Rules toggle/conditional-control patterns where practical
  - kept trading logic unchanged
- resolved in the latest pass:
  - Backtest form values no longer get reinitialized after ordinary edits/copy actions
  - root cause was UI-only: `cloneTradingRulesDefaults()` was being recreated on every render while the initial load effect depended on `defaults`, so server rules were replayed into form state after edits
  - fix was the smallest clean change in current architecture: make `defaults` stable for the component lifetime with `useState(() => cloneTradingRulesDefaults())`
  - no trading logic or backtest engine semantics changed
- verification for the latest pass:
  - npm run check ✅
  - npm run build ✅
  - deploy-prod-safe.sh ✅
  - /api/health ✅
  - /backtest served after deploy ✅
- product commit for latest pass: `699901df947455c2f7db8f8a9620fa17638b9178` (`fix: stabilize backtest form defaults`)
- no other trading-logic changes are approved for this pass
- latest fix completed:
  - root cause of `optimization_not_queued:running` confirmed in `src/core/optimizerProcess.ts`
  - process wrapper was pre-setting queued optimization records to `running` before `executeOptimization(...)`
  - worker correctly requires `queued` and owns the `queued -> running` transition, so the process was making the worker fail itself
  - clean fix shipped: process now only writes `workerPid` + `workerHeartbeatAt` while status is still `queued`; worker remains the single owner of `startedAt` and `running`
  - verification completed:
    - npm run check ✅
    - npm run build ✅
    - deploy-prod-safe.sh ✅
    - /api/health ✅
    - /backtest served after deploy ✅
    - end-to-end optimizer regression run completed successfully on prod persistence: `verify-1776943552903-f28170` → completed, 1/1 candidate evaluated
Key files:
- .ops/PROJECT_TRUTH.md
- .ops/SOFTWARE_DEVELOPMENT_PROTOCOL.md
- .ops/RESET_PREP_PROTOCOL.md
- .ops/TASK_STATE_PROTOCOL.md
- .ops/ACTIVE_TASK.md
