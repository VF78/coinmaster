# ACTIVE_TASK

Updated: 2026-04-22 Europe/Madrid
Status: IDLE / planning
GitHub Project item: none active; Radar #41-#46 completed, #47 still Todo
Canonical root: /root/.openclaw/workspace/coinmaster/coinmaster
Branch / HEAD / origin/main / deploy commit / divergence: main / c01d382c630f45998cdb6cb3fac62850afcdd561 / 5d505b7379fda1d3c6028f048e01588364d4afd4 / 069f37919e903aefedf94eb5624e217282dc16d1 / local main ahead of origin by 3 commits
Goal: keep repo-backed operational context minimal, current, and restart-safe before the next implementation task
Done:
- restored and deployed Alpha Radar end-to-end
- updated GitHub Project Radar statuses to Done where completed
- analyzed reset-context loss and execution-controls drift
- split ops docs into dedicated development + reset protocols
- removed bootstrap residue and trimmed duplicate/stale top-level docs into compact pointers/indexes
Next exact step: sync current repo state to GitHub, then wait for Vladimir to approve the next task plan before activating a new Project item
Checks / commit / deploy / push:
- latest product checks: invariants:radar-handoff, check, build passed
- latest product deploy: scripts/deploy-prod-safe.sh successful
- protocol/doc commits: 160eb61001c57ef359792f9166d841bb92f3e067, c01d382c630f45998cdb6cb3fac62850afcdd561
- push state: local main ahead of origin/main by 3 commits
Blockers / risks:
- memory_search unavailable; rely on local docs + live repo state
- do not start a new implementation task until plan is agreed
Key files:
- .ops/PROJECT_TRUTH.md
- .ops/SOFTWARE_DEVELOPMENT_PROTOCOL.md
- .ops/RESET_PREP_PROTOCOL.md
- .ops/TASK_STATE_PROTOCOL.md
- .ops/ACTIVE_TASK.md
