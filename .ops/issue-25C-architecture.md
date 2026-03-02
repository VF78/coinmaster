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
- **Evaluate:** pull deterministic inputs (`Condition` windows, account state, snapshot data, live position) into a pure `Evaluation` payload. No side effects, no telemetry emission. Conditions return `true/false` + metadata (timestamps, lookback ranges) so downstream can attribute why a trigger qualified. Evaluation runs before the legacy middleware mutates anything, meaning we can re-run the same evaluation offline for audits.
- **Decide:** run the evaluation output through trigger conflict resolution. At this stage we compute `decisionSet` (risk/exit/entry/ops actions), enforce priority ordering, apply cooldown/debounce/lockouts, and tag suppressed actions with reasons (`preempted_by_higher_tier`, `window_violation`). Decision stage emits structured telemetry (decision hash + decisionHashSlice) and caches durable idempotency keys for the action stage. Decision payloads are stored in a short-lived in-memory log (retain last 100 ticks) so we can correlate watchdog alerts / duplicate suppression rates with the exact decision set that triggered them.
- **Act:** hand the decision set to exchange-safe agents. Each `Action` has explicit `sideEffects` metadata (`none`, `exchange`, `state`, `notification`); the act stage only executes actions whose idempotency key/payload has not yet been acknowledged, and runners that mutate exchange state are decorated with retry-safe wrappers + circuit-breaker hooks so repeated ticks do not double-fire. The act stage also emits `ActionAttempt` events (status=queued|sent|acked|failed) so telemetry can spotlight stuck executions or duplicate replays.
- **Audit:** capture structured events for every evaluation → decision → action sequence, including the `decisionHash`, triggered `Condition.id`s, suppression reasons, `Action.idempotencyKey`, and `ActionAttempt` results. Auditable events feed both the append-only `tradeEvents` journal and the new “dual-run compare” log so we can replay a Phase 1 run and prove invariants. Each audit record includes `traceId`, `decisionTickMs`, and a `watchdogToken` so we can tie alerts back to the offending tick.

## Runtime Placement
- Risk loop owns evaluation and decision stages, plus emergency-exit enforcement. It consumes normalized snapshots and publishes `decisionSet` payloads to downstream actors (exit/entry/risk/ops). Emergency-exits are treated as higher-priority `exit` + `risk` actions with preemption rules baked into the loop.
- Order middleware is throttled to validation, telemetry/metrics, and backlog gating. It receives `Act` requests from the risk loop and simply ensures exchange/client state is sane before forwarding to request handlers.
- Handoff contract: middleware accepts truthy decisions, writes audit entries, and forwards to the existing `runtimeExecutor`. The executor only acts on idempotent action payloads and returns acknowledgements that feed back into the decision stage for durable status tracking.

## Deterministic Conflict Resolution
- Merge triggered actions across scopes and deduplicate by `(symbol, action.kind, action.idempotencyKey)`. When both `risk` and `entry` actions want to `place_order`, the `risk` action wins and the `entry` action is `suppressed` with reason `preempted_by_higher_tier`. The same decision tick logs the suppression and increments `entrySuppressedByRisk` so dashboards show how often legacy logic is blocked.
- Exit vs entry: an `exit` action will always preempt an `entry` action for the same symbol, even if the entry action has higher priority, because exits are deemed higher-risk safety actions. The suppressed `entry` is recorded with `suppressed_by_exit`. Exit actions also cancel outstanding `place_order` confirmations by injecting a `cancel_order` guard into the decision set when `orderId` matches a pending entry order and `exit` is triggered.
- Repeated triggers are handled by cooldown/debounce metadata on the trigger. The decision stage enforces that only transitions (edge mode) or sustained windows (level mode) that respect cooldownMs/debounceMs reach the act stage, so action biometrics are predictable even when market noise generates multiple evaluations per second.
- When two triggers of the same priority fire simultaneously, tie-break uses deterministic tuple `(scopeRank, priority desc, cachedTriggerId asc)` to ensure identical behavior across restarts. The tuple is hashed into `decisionHashSlice` so dual-run compare can deterministically verify the same tie-break was applied in both runs.
- Duplicate-action detection: the decision stage cross-checks each action's idempotency key against the per-symbol dedup cache before emitting to `Act`. If the cache already contains the key, the action is dropped, a `duplicateActionErrors` counter increments, and an audit entry marks the decision with `suppressionReason=duplicate_key`. This prevents replayed ticks from hitting exchanges twice.

## Observability & Idempotency Guarantees
- Every evaluation/decision/action emits a correlation header (e.g., `traceId`) and shares `decisionHash`. Telemetry tables track `conditionResults`, `triggerId`, `triggerWindow`, and `suppressionReason` to enable audits of mismatch reports (legacy vs engine) and to populate the dual-run compare dashboard.
- Decision hashes, `watchdogToken`, and `traceId` are surfaced to Prometheus/grafana metrics as tags so we can jump from an alert to the exact decision tick and the audit log. The risk loop publishes `decisionLagMs`, `decisionRate`, `suppressionRate`, `duplicateActionErrors`, `entrySuppressedByRisk`, and `exitPreemptsEntry` gauges plus counters for `decisionSetSize` and `auditEventCount`.
- Observability also includes a heartbeat counter (tick per 30s) and a `missingDecisionAlert`: if no `Act` payload escapes the risk loop for >8 minutes (aligns with watchdog policy) we emit a `watchdog.outage` log with `decisionHash`, `lastDecisionTickMs`, and `traceId` so the ops team can quickly correlate with telemetry.
- Idempotency keys are derived from `Action.idempotencyKeyTemplate` plus evaluation context (symbol, timestamp bucket, `decisionHashSlice`). Exchange-facing actions must reuse the same key across retries; audit logs record both the request and the acknowledgement to detect duplicates.
- `ActionAttempt` events include `idempotencyKey`, `result`, and `retryCount`. A central dedup cache keeps the last 1000 acted keys per symbol, ensuring subsequent ticks drop replays and log a high-severity `duplicateActionErrors` if duplicates surface.

## Migration Plan (Incremental)
1. **Phase 1:** contracts + adapters — document `Condition`/`Trigger`/`Action` contracts, plug dual-run compare auditing, and introduce `decisionHash` telemetry without changing runtime behavior (done via P1a–P1e). Smoke bundle (`check`, `invariants:rule-engine`, `ops:smoke`) verifies parity before any migration move.
2. **Phase 2:** feature-flagged risk loop integration — route realtime snapshots through the risk loop but keep legacy middleware decisions active (dual-run mode). Dual-run compare verifies `decisionHash` + `suppressionReason` equality before risk-loop actions touch exchanges. Watchdog policy stays in place (8m progress guard / 25m hard timeout) to bail quickly if parity breaks.
3. **Phase 3:** middleware thinning + conflict policy enforcement — once dual-run metrics show stable parity (>=1000 ticks, `suppressionRate` <1% with no duplicates), disable legacy trigger handling in middleware and rely solely on the risk loop’s deterministic conflict resolution. Expand dedup cache/metrics, harden `entrySuppressedByRisk`, `exitPreemptsEntry`, `duplicateActionErrors` alerts, and keep rollback documentation ready (scripts to flip feature flag + revert to fallback decision set).
4. **Phase 4:** feature-flag cutover + rollout/rollback checklist — after exercising rollback hooks in staging and verifying `ops:smoke` + invariants pass with risk-loop enabled, flip the flag for production, monitor `decisionLagMs`/`missingDecisionAlert`, and keep scripts (cron job + checklist) handy to revert to the previous runtime path upon watchdog/code-143 triggers. If suppression/ticket metrics spike, trigger immediate micro-restart + last-known-good commit.

## Open Questions for Claude Review
- Does the mitigation strategy (risk loop + telemetry) sufficiently capture real-world non-determinism in request-time middleware?
- Are there additional conflict scenarios (e.g., exit + cancel_order) that need explicit suppression reasoning?
- Does the migration plan align with ops windows and allow safe rollback when watchdog triggers (code 143) occur?
