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

Canonical contracts (engine-internal):

- `Condition`
  - `id: string` — stable identifier.
  - `kind: "signal" | "risk" | "safety" | "state"`.
  - `source: "market" | "account" | "rules" | "system"`.
  - `expr: object` — normalized predicate payload (pure, side-effect free).
  - `window?: { lookbackBars?: number; lookbackMs?: number }`.
  - `enabled: boolean`.

- `Trigger`
  - `id: string`.
  - `when: string[]` — list of `Condition.id` that must be true (AND semantics by default).
  - `mode: "edge" | "level"` (`edge` = on state transition; `level` = while true).
  - `cooldownMs?: number`.
  - `debounceMs?: number`.
  - `priority: number` (higher wins).
  - `scope: "entry" | "exit" | "risk" | "ops"`.
  - `enabled: boolean`.

- `Action`
  - `id: string`.
  - `kind: "place_order" | "cancel_order" | "close_position" | "set_levels" | "block_trading" | "notify" | "audit_only"`.
  - `params: object` — action payload.
  - `idempotencyKeyTemplate: string`.
  - `sideEffects: "none" | "exchange" | "state" | "notification"`.

Priority / preemption policy:
1. `safety` actions preempt all.
2. `risk` actions preempt `entry` and non-safety `ops`.
3. `exit` actions preempt `entry` for same symbol.
4. Equal-priority ties resolve by deterministic order: `(scope, priority desc, trigger.id asc)`.
5. One symbol cannot execute conflicting exchange actions in the same decision tick; loser actions are audited as `suppressed`.

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
