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
- P1d4: in progress
- P1e: pending

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

## Next actions
1. Finish P1d4 invariant (negative control exact match).
2. Run `npm run check` and `npm run invariants:rule-engine`.
3. Execute P1e smoke and finalize Phase 1 commit.
