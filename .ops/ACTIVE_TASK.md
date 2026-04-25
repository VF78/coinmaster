# ACTIVE_TASK

Updated: 2026-04-25 23:45 Europe/Madrid
Status: IMPLEMENTED / #62 local code complete after Claude-limit fallback to Codex; architect-reviewed and verification gates passing; pending commit/push/project-sync/deploy
GitHub Project: https://github.com/users/VF78/projects/2
Active item: #62 [ARCH-02] Radar evidence/ingestion upgrade: feedparser, provenance, EvidenceBundle, NLP, dedupe, factor score
Active issue: https://github.com/VF78/coinmaster/issues/62
Canonical root: /root/.openclaw/workspace/coinmaster/coinmaster
Branch / starting HEAD / origin divergence / deploy commit: main / 25e1f9054c5df8f67631792316b3abd7e0751628 / 0 ahead, 0 behind / 25e1f9054c5df8f67631792316b3abd7e0751628

Execution notes:
- Claude Opus first pass was attempted first and hit usage limit: `resets 3:10am (Europe/Madrid)`.
- Fallback to Codex was used per owner instruction.
- Architect review fixed the first pass to use the repo-owned npm `feedparser` package as primary RSS/Atom parser instead of a host Python/runtime dependency.
- GET `/api/alpha-radar/ideas` was kept read-only; durable evidence/candidate persistence happens during observation saves.

Implemented for #62:
- Added durable `EvidenceBundle` DTO/state and persistence shape.
- Added durable `SignalCandidate` DTO/state-machine scaffold with explicit states: `new`, `validated`, `actionable`, `routed`, `executed`, `expired`, `rejected`, `postmortem_ready`.
- Added `feedparser` dependency and primary RSS/Atom parser with bounded fallback parser.
- Added provenance fields for canonical URL, payload hash, external id/guid, published/observed/fetched timestamps, HTTP ETag/Last-Modified/status, parser id, and compact raw payload reference.
- Added explainable evidence dedupe by payload hash, canonical URL, external/source id, and fuzzy title/body similarity.
- Added optional/fail-safe NLP enrichment boundary with deterministic fallback labels; no fake spaCy/FinBERT claims and no collector crash if external ML assets are unavailable.
- Added explicit Radar factor scoring: relevance, novelty, sourceReliability, eventSeverity, timeDecay, marketConfirmation, executionability.
- Wired AlphaRadar ideas to durable evidence/candidate references where available.
- Added compact UI/read-model counters for evidence bundles, signal candidates, and dedupe suppression.
- Updated `docs/RADAR_RUNTIME.md` with evidence/candidate runtime, parser/enrichment boundaries, and discuss-before-implementation gates for SentenceTransformers/OpenBB/cryptofeed.
- Added `scripts/invariants-radar-evidence.ts` and package script `invariants:radar-evidence`.

Verification passed locally:
- `git diff --check`
- `npm run check`
- `npm run invariants:radar-evidence` → 15/15
- `npm run invariants:radar-handoff` → 34/34
- `npm run build`

Current Project state:
- #61 Closed / Done / deployed.
- #62 Open / In Progress.
- #63 Open / Todo.
- #64 Open / Todo.

Do not commit runtime noise:
- `coinmaster/data/db.json`
- `prod-backups/dbshape_v1-pre-legacy-cleanup-20260424-160348.json`

Next exact step:
- Commit #62 implementation excluding runtime noise, push, update GitHub issue/Project, then deploy via `coinmaster/scripts/deploy-prod-safe.sh` only.
