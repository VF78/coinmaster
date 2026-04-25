# ACTIVE_TASK

Updated: 2026-04-25 23:58 Europe/Madrid
Status: IMPLEMENTED / #63 local code complete after Codex fallback; architect-reviewed and verification gates passing; pending commit/push/GitHub sync/deploy
GitHub Project: https://github.com/users/VF78/projects/2
Active item: #63 [ARCH-03] Radar role change: make RadarContextPolicy the context controller for Trading Rules entries
Active issue: https://github.com/VF78/coinmaster/issues/63
Canonical root: /root/.openclaw/workspace/coinmaster/coinmaster
Branch / starting HEAD / origin divergence / deploy commit: main / 35e39b500a20d9f69b9895044437e1931a4bb4a9 / 0 ahead, 0 behind / 35e39b500a20d9f69b9895044437e1931a4bb4a9

Project state:
- #61 Closed / Done
- #62 Closed / Done
- #63 Open / In Progress
- #64 Open / Todo

Execution note:
- Claude Opus was known-blocked by usage limit until 03:10 Europe/Madrid from the #62 attempt.
- Codex fallback was used per owner instruction.

Implemented for #63:
- Added durable `RadarContextPolicy` DTO/persistence collection.
- Added durable `ExecutionIntent` audit object and wired pending confirmations / Radar signal records to `executionIntentId`.
- Added deterministic `src/server/radarContextPolicy.ts` policy builder using #62 `EvidenceBundle` + `SignalCandidate` scores, not opaque LLM output.
- Policy fields include symbol/scope, directionMode, riskMultiplier, lockNewEntries, eventLockoutUntil, narrativeRegime, priorityScore, validUntil, assetSpecificOverrides, reasonCodes, evidenceIds, signalCandidateId.
- Added active-policy helper with TTL expiry handling and entry evaluator with explicit rejection reason codes: `direction_blocked`, `event_lockout`, `ttl_expired`, `risk_multiplier_blocked`, `missing_required_evidence`.
- Synced policy book after Radar observation/evidence ingestion and before entry gating.
- Gated unified Trading Rules handoff path used by live Engulfing/FVG monitors before pending confirmation or auto-order placement.
- Gated owner/manual non-reduce-only order endpoints through the same policy; reduce-only/protection-only exits remain allowed.
- Added explicit audited manual override path: request body `radarContextPolicyOverride: true`, persisted on `ExecutionIntent` and risk-gate audit.
- Kept `/api/radar/signals` on unified handoff path; no second independent trader was introduced.
- Added compact Radar UI/read-model counters for policy count, active/locked/expired policies, policy pass/block counts.
- Updated `docs/RADAR_RUNTIME.md`.
- Added `scripts/invariants-radar-context-policy.ts` and package script `invariants:radar-context-policy`.

Verification passed locally:
- `git diff --check`
- `npm run check`
- `npm run invariants:radar-context-policy` → 12/12
- `npm run invariants:radar-handoff` → 34/34
- `npm run invariants:trading-rules` → 61/61
- `npm run build`

Do not commit runtime noise:
- `coinmaster/data/db.json`
- `prod-backups/`

Next exact step:
- Commit #63 implementation excluding runtime noise, push, update GitHub issue/Project, then deploy via `coinmaster/scripts/deploy-prod-safe.sh` only and verify production.
