# ACTIVE_TASK

Updated: 2026-04-22 Europe/Madrid
Status: ACTIVE / #26 implementation shipped, comparative backtests verified and runner issue identified
GitHub Project item: #26 active — TR-03 FVG retrace trigger engine (structure break + retrace %)
Canonical root: /root/.openclaw/workspace/coinmaster/coinmaster
Branch / HEAD / origin/main / deploy commit / divergence: main / 53e5d0d1b1e6422feef3483f1928e5a49ed5bcc0 / 53e5d0d1b1e6422feef3483f1928e5a49ed5bcc0 / 53e5d0d1b1e6422feef3483f1928e5a49ed5bcc0 / synced with origin and deploy
Goal: fix the backtest-run persistence bug cleanly inside the shared architecture, then resume post-implementation FVG comparisons and decide what to tune next for ROI
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
Next exact step: fix the backtest-run persistence bug in the shared runner/persistence flow (no duplicates, no special-case backtest path), deploy it, and only then resume lower-TF / combined comparisons on a clean runner state
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
- likely root cause to verify/fix: backtest worker keeps a run object reference across awaits while shared store reloads can replace the underlying snapshot object; completion state can then be written to a stale object and never reach persisted state
- remaining comparative runs (lower-TF only / combined) are intentionally paused until the runner persistence anomaly is fixed cleanly
Key files:
- .ops/PROJECT_TRUTH.md
- .ops/SOFTWARE_DEVELOPMENT_PROTOCOL.md
- .ops/RESET_PREP_PROTOCOL.md
- .ops/TASK_STATE_PROTOCOL.md
- .ops/ACTIVE_TASK.md
