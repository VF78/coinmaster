# ACTIVE_TASK

Updated: 2026-04-22 Europe/Madrid
Status: ACTIVE / clarified scope, implementation paused for user-approved logic
GitHub Project item: #26 active — TR-03 FVG retrace trigger engine (structure break + retrace %)
Canonical root: /root/.openclaw/workspace/coinmaster/coinmaster
Branch / HEAD / origin/main / deploy commit / divergence: main / e9d54fc2f6ff5410e8aebadd9eded0769ffed019 / e9d54fc2f6ff5410e8aebadd9eded0769ffed019 / 069f37919e903aefedf94eb5624e217282dc16d1 / synced with origin, deploy behind HEAD
Goal: implement the first bounded FVG quality-improvement slice inside one shared live/backtest architecture, then verify via backtest + checks before any prod promotion
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
- agreed with user on the first bounded filter set for implementation:
  - sweep + displacement
  - lower-TF confirmation after HTF FVG touch
  - fresh / first-touch / already mitigated
- user clarified two hard constraints before continuing:
  - the improvement is intended to ship into prod first, then be evaluated with backtests afterward
  - lower-TF confirmation mapping must be configurable in Trading Rules, not hardcoded
- user requested that any other logic changes be explicitly agreed before implementation continues
- updated #26 checklist to reflect the agreed first implementation slice and verification scope
- completed mandatory preflight for coding:
  - branch = main
  - workspace status clean
  - HEAD = e9d54fc2f6ff5410e8aebadd9eded0769ffed019
  - origin/main divergence = 0 / 0
  - deployed commit = 069f37919e903aefedf94eb5624e217282dc16d1
- Claude CLI route unavailable under current root runtime; switched implementation to fallback coding path per protocol
Next exact step: realign the #26 implementation spec to the clarified constraints (prod-first deployment intent, configurable lower-TF mapping, no unagreed logic changes), then continue coding only inside that approved scope
Checks / commit / deploy / push:
- latest product checks: invariants:radar-handoff, check, build passed
- latest product deploy: scripts/deploy-prod-safe.sh successful
- latest ops commit: e9d54fc2f6ff5410e8aebadd9eded0769ffed019 (`docs: mark #26 as active fvg research task`)
- push state: synced to origin/main
Blockers / risks:
- memory_search unavailable; rely on local docs + live repo state
- external ICT/FVG material is mostly practitioner content, not statistically rigorous research; treat as heuristic input, not proof
- partial product-repo edits exist from interrupted fallback pass and must be reviewed/reworked before any commit
- lower-TF mapping and any other logic beyond the explicitly agreed slice must be configurable or re-approved before coding continues
Key files:
- .ops/PROJECT_TRUTH.md
- .ops/SOFTWARE_DEVELOPMENT_PROTOCOL.md
- .ops/RESET_PREP_PROTOCOL.md
- .ops/TASK_STATE_PROTOCOL.md
- .ops/ACTIVE_TASK.md
