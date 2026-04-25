# ACTIVE_TASK

Updated: 2026-04-26 00:03 Europe/Madrid
Status: COMPLETE / #63 implemented, pushed, GitHub issue closed, Project updated; pending production deploy of final pushed HEAD
GitHub Project: https://github.com/users/VF78/projects/2
Completed item: #63 [ARCH-03] Radar role change: make RadarContextPolicy the context controller for Trading Rules entries
Completed issue: https://github.com/VF78/coinmaster/issues/63
Canonical root: /root/.openclaw/workspace/coinmaster/coinmaster
Implementation commit: d2d06a9dd681e6205deb1b4719398fb5d1743383
Production target: /opt/coinmaster
Production service: coinmaster.service

Project state:
- #61 Closed / Done
- #62 Closed / Done
- #63 Closed / Done
- #64 Open / Todo

Execution note:
- Claude Opus was known-blocked by usage limit until 03:10 Europe/Madrid from the #62 attempt.
- Codex fallback was used per owner instruction.

Completed for #63:
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

Verification passed locally before issue sync:
- `git diff --check`
- `npm run check`
- `npm run invariants:radar-context-policy` → 12/12
- `npm run invariants:radar-handoff` → 34/34
- `npm run invariants:trading-rules` → 61/61
- `npm run build`

GitHub sync:
- Commented verification summary on issue #63.
- Closed issue #63.
- Updated GitHub Project #2: #61 Done, #62 Done, #63 Done, #64 Todo.

Do not commit runtime noise:
- `coinmaster/data/db.json`
- `prod-backups/`

Next exact step:
- Commit/push this task-state update, then deploy final pushed HEAD via `coinmaster/scripts/deploy-prod-safe.sh` only and verify production.
