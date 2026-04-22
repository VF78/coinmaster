# ACTIVE_TASK

Updated: 2026-04-22 Europe/Madrid
Status: IDLE / planning
GitHub Project item: none active; ROI-focused board retained (#26, #40, #41-#54, AE1-4), non-ROI/obsolete items removed from Project
Canonical root: /root/.openclaw/workspace/coinmaster/coinmaster
Branch / HEAD / origin/main / deploy commit / divergence: main / 7486eb06ce9405bd2518a023e32318221293b04c / 7486eb06ce9405bd2518a023e32318221293b04c / 069f37919e903aefedf94eb5624e217282dc16d1 / synced with origin
Goal: align project truth and GitHub Project with the ROI mandate, then agree the next execution plan before coding
Done:
- restored and deployed Alpha Radar end-to-end
- updated GitHub Project Radar statuses to Done where completed
- analyzed reset-context loss and execution-controls drift
- split ops docs into dedicated development + reset protocols
- removed bootstrap residue and trimmed duplicate/stale top-level docs into compact pointers/indexes
- added explicit ROI mandate to project truth docs
- removed non-ROI / obsolete items from the GitHub Project board
Next exact step: agree the next active ROI task and select the top 2-3 AE4/FVG-adjacent subtasks before starting implementation
Checks / commit / deploy / push:
- latest product checks: invariants:radar-handoff, check, build passed
- latest product deploy: scripts/deploy-prod-safe.sh successful
- doc/project cleanup commits: 7486eb06ce9405bd2518a023e32318221293b04c (`docs: align project truth with roi mandate`)
- push state: synced to origin/main
Blockers / risks:
- memory_search unavailable; rely on local docs + live repo state
- do not start a new implementation task until plan is agreed
Key files:
- .ops/PROJECT_TRUTH.md
- .ops/SOFTWARE_DEVELOPMENT_PROTOCOL.md
- .ops/RESET_PREP_PROTOCOL.md
- .ops/TASK_STATE_PROTOCOL.md
- .ops/ACTIVE_TASK.md
