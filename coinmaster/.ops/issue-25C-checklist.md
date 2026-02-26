# Issue 25C — Phase 1: RISK Rules in Dual-Run

## Checklist

### Phase 1 Deliverables

- [x] **P1a** Engine types + snapshot builder
  - `src/engine/types.ts` — `EngineDecision`, `EngineSnapshot` types
  - `src/engine/snapshot.ts` — `buildSnapshot()` pure builder

- [x] **P1b** RISK rule definitions
  - `src/engine/rules/risk/index.ts`
  - `evalDailyDrawdownRule`, `evalEquityRule`, `riskResultToDecision`
  - `applyPreemption`, `countSuppressedEntries`

- [x] **P1c** Dual-run compare helpers
  - `src/engine/dualRunCompare.ts`
  - `summarizeDecisions`, `compareResults`, `formatCompareResult`

- [x] **P1d** Invariants — preemption + mismatch detection depth
  - `scripts/invariants-rule-engine.ts` (P1a–P1d cases)
  - P1d-1: RISK preempts ENTRY (ordering + suppression reason verified)
  - P1d-2: EXIT preempts ENTRY (multi-entry suppression verified)
  - P1d-3: Mismatch detection ≥2 fields (blocked + reason)
  - P1d-4: Negative control (legacy == engine → zero mismatches)

- [x] **P1e** Smoke verification + final Phase 1 artifact commit
  - `scripts/phase1-dualrun-smoke.ts`
  - Scenario A: healthy state, both allow → MATCH
  - Scenario B: DD exceeded, both block, ENTRY preempted → MATCH
  - Scenario C: zero equity caught by engine, missed by legacy → MISMATCH (audit-only)
  - Scenario D: EXIT active, ENTRY preempted, both agree block → MATCH
  - `npm run check` — TypeScript clean (0 errors)
  - `npm run invariants:rule-engine` — all assertions pass
  - `npm run invariants:phase1-dualrun` — overall PASS

## Hard Constraints (all upheld)

1. No live server runtime changes — no cutover.
2. Dual-run is audit/log-only — `compareResults` has no side effects.
3. Code is simple, typed, deterministic — pure functions only.
4. No imports from `server/index.ts` into engine rules/helpers.
5. No legacy gate removal.

## Event Log

### 2026-02-26 — P1d + P1e finalized

- Created `src/engine/types.ts`, `src/engine/snapshot.ts`,
  `src/engine/rules/risk/index.ts`, `src/engine/dualRunCompare.ts`
  (Phase 1 engine foundation, pure functions, zero server deps).
- Created `scripts/invariants-rule-engine.ts` covering P1a–P1d:
  snapshot builder, RISK rule evaluation, basic compare, preemption
  ordering (RISK>EXIT>ENTRY), 2-field mismatch detection, negative control.
- Created `scripts/phase1-dualrun-smoke.ts` with 4 end-to-end scenarios;
  Scenario C explicitly exercises audit-only mismatch logging path.
- Wired `invariants:rule-engine` and `invariants:phase1-dualrun` in `package.json`.
- All three checks (`check`, `invariants:rule-engine`, `invariants:phase1-dualrun`) passed.
- Committed: `issue25c: finalize phase1 dual-run invariants and smoke`
