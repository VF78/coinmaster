# Issue #25C — Unified Trading Rules Engine Architecture (Draft)

## Scope
- Define one unified execution model for all Trading Rules conditions/triggers.
- Ensure deterministic behavior for entry, emergency-exit, risk gates, and safety controls.
- Separate evaluation/decision from execution side-effects.
- Keep order middleware thin; move runtime trigger handling to risk loop.
- Preserve feature-flag safety and backward compatibility.

## Current Problems (to validate)
- TODO: map duplicated/overlapping rule logic paths.
- TODO: document where request-time middleware currently owns runtime concerns.
- TODO: list non-deterministic or timing-sensitive branches.

## Unified Rule Model
- TODO: define canonical `Condition` schema.
- TODO: define canonical `Trigger` schema.
- TODO: define canonical `Action` schema.
- TODO: define priority levels and preemption rules.

## Execution Lifecycle (Evaluate → Decide → Act → Audit)
- TODO: evaluate stage contract and inputs.
- TODO: decision stage contract and conflict resolution.
- TODO: action stage contract (idempotent, side-effect boundaries).
- TODO: audit stage contract (structured events, replayability).

## Runtime Placement
- TODO: define risk-loop responsibilities (incl. emergency-exit).
- TODO: define order middleware responsibilities (validation/telemetry only).
- TODO: define handoff contract between middleware and runtime engine.

## Deterministic Conflict Resolution
- TODO: tie-break order between risk blocks, exits, and entries.
- TODO: repeated-trigger handling (debounce/lockout/windowing).
- TODO: behavior when multiple triggers fire in same tick.

## Observability & Idempotency Guarantees
- TODO: required event fields and correlation IDs.
- TODO: idempotency key strategy per action type.
- TODO: required metrics/alerts for trigger handling health.

## Migration Plan (Incremental)
1. TODO: phase 1 — contracts + adapters (no behavior change).
2. TODO: phase 2 — runtime risk-loop trigger integration under feature flag.
3. TODO: phase 3 — middleware thinning + conflict policy enforcement.
4. TODO: phase 4 — cutover, rollback hooks, and verification checklist.

## Open Questions for Claude Review
- TODO: verify contracts against existing server/risk/watchdog flow.
- TODO: validate conflict policy with real edge-cases.
- TODO: confirm migration order minimizes operational risk.
