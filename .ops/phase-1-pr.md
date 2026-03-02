# Phase 1 PR / Artifact note

## Context
- Issue #25C Phase 1 (RISK rules dual-run foundations) should deliver deterministic risk gating + auditable smoke for entry/exit/risk invariants.
- P1d4 (negative-control exact match) and P1e (smoke + PR) were the final steps tracked in the checklist.

## Commands performed
1. `npm run check` (TypeScript typecheck) — ensures no typing regression in the engine + scripts.
2. `npm run invariants:rule-engine` — all 39 invariant cases pass, including Case 11 (negative control parity) and Case 10 (both-blocked context mismatch).
3. `API_BASE_URL=http://127.0.0.1:8787 npm run ops:smoke` — `/api/health`, `/api/dashboard`, `/api/live/status` respond with HTTP 200 and valid JSON while the API server is running locally.

## Output summary for PR
- Phase 1 introduces the dual-run engine snapshot builder, risk rule definitions, dual-run compare helpers, and the newly validated invariants P1d1–P1d4.
- Smoke verification bundle: `check`, `invariants:rule-engine`, `ops:smoke` (documented above).
- No open blockers remain; operational risks (Claude consent prompts/code 143) mitigated via watchdog policy (8m progress watchdog, 90s silent stall, 25m hard timeout, immediate restart on consent-loop).

## Next steps
1. Stage PR with the above summary + QUALITY.md verifying smoke commands.
2. Switch focus to architecture track: 25C.A3 (lifecycle/idempotency/observability) and 25C.A4 (conflict-resolution policy + migration plan) per PROJECT_TRUTH next actions.
