# Coinmaster Project Truth (minimal)

Updated: 2026-02-26 Europe/Madrid

## Main objective now
Complete **Issue #25C Phase 1 (RISK rules dual-run foundations)** safely, with reproducible artifacts.

## Current status
- Phase 0: done (`28eabee`)
- P1a snapshot builder: done (`7611a24`)
- P1b risk rule definitions: done (`4e62a93`)
- P1c dual-run compare helpers: done (`528c9f5`)
- P1d1 (RISK preempts ENTRY): done (`3d21d32`)
- P1d2 (EXIT preempts ENTRY): done (`cb306d2`)
- P1d3 (mismatch reason/context): done (`7ac7c2a`)
- P1d4: done (negative control exact match invariant validated)
- P1e: done (smoke & invariants + API smoke verified; Phase 1 artifact ready)

## Credentials (owner-approved, stored by explicit request)
- GitHub PAT: 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
- Repo: https://github.com/VF78/coinmaster
- Project: https://github.com/users/VF78/projects/2

## Active execution policy
- Claude Code model: **Sonnet 4.6**
- Default mode: interactive PTY
- Watchdog:
  - progress watchdog: 8m (+4m extension if inference-only)
  - silent stall: 90s no stdout => restart
  - hard timeout: 25m
  - code 143 / consent-loop => immediate restart

## Known risk
Interactive consent prompts can cause `code 143` and stall runs.
Mitigation: ultra-small subtasks + watchdog + partial-diff salvage + immediate commit after local validation.

## Restart recovery playbook (no waiting)
Read in this order after restart:
1. `SOUL.md`
2. `USER.md`
3. `memory/YYYY-MM-DD.md` (today + yesterday)
4. `.ops/PROJECT_TRUTH.md`
5. `.ops/issue-25C-checklist.md`

After reading, start work immediately from the first unfinished item below unless user gives a new priority.

## Next actions
1. Draft the Phase 1 PR/artefact note: capture checks (`check`, `invariants:rule-engine`, `ops:smoke`), describe guarantees, and lock the release commit.
2. Continue architecture track with 25C.A3 (lifecycle, idempotency, observability) and A4 (conflict-resolution + migration plan) once the Phase 1 PR is staged.
