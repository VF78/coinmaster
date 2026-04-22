# ACTIVE_TASK

Updated: 2026-04-23 Europe/Madrid
Status: ACTIVE / revised FVG logic deployed, post-change backtests starting
GitHub Project item: #26 active — TR-03 FVG retrace trigger engine (structure break + retrace %)
Canonical root: /root/.openclaw/workspace/coinmaster/coinmaster
Branch / HEAD / origin/main / deploy commit / divergence: main / 7b7b7830ba34fe8771caca6ee9dced505c56ed31 / 7b7b7830ba34fe8771caca6ee9dced505c56ed31 / 7b7b7830ba34fe8771caca6ee9dced505c56ed31 / synced with origin and deploy
Goal: evaluate the newly deployed revised FVG logic with post-change backtests and find better parameter values for ROI
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
Next exact step: run post-change backtests for the revised FVG semantics (sweep-only, first-touch + maxZoneAgeCandles, engulfing-body confirmation) and identify the best parameter candidates for follow-up tuning
Checks / commit / deploy / push:
- latest product commit: 53e5d0d1b1e6422feef3483f1928e5a49ed5bcc0 (`Implement shared FVG qualification rules`)
- latest product checks: check, invariants:fvg, build passed
- latest product deploy: scripts/deploy-prod-safe.sh successful
- latest ops commit: bee6ed5 (`docs: lock approved #26 execution spec`)
- push state: product + ops synced to origin/main
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
- no other logic changes are approved for this pass
Key files:
- .ops/PROJECT_TRUTH.md
- .ops/SOFTWARE_DEVELOPMENT_PROTOCOL.md
- .ops/RESET_PREP_PROTOCOL.md
- .ops/TASK_STATE_PROTOCOL.md
- .ops/ACTIVE_TASK.md
