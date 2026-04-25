# ACTIVE_TASK

Updated: 2026-04-25 23:48 Europe/Madrid
Status: COMPLETE / #62 implemented, verified, pushed, GitHub issue closed, Project Done, production deployed
GitHub Project: https://github.com/users/VF78/projects/2
Completed item: #62 [ARCH-02] Radar evidence/ingestion upgrade: feedparser, provenance, EvidenceBundle, NLP, dedupe, factor score
Completed issue: https://github.com/VF78/coinmaster/issues/62
Canonical root: /root/.openclaw/workspace/coinmaster/coinmaster
Implementation commit: dbacb893ad588bdc57230655923e0b30677fd848
Task sync commit: 9cad7dfb6d3b8fd95622e0fdf0f93295c6d80303
Deploy script dependency-drift fix: 62ef387a97334ca3b767e60dd73a7f72b842e568
Production target: /opt/coinmaster
Production service: coinmaster.service

Completed for #62:
- Added durable `EvidenceBundle` and `SignalCandidate` DTO/state/persistence shape.
- Added repo-owned npm `feedparser` dependency and primary RSS/Atom parser with bounded fallback.
- Added provenance capture: canonical URL, payload hash, external id/guid, published/observed/fetched timestamps, HTTP ETag/Last-Modified/status, parser id, compact raw payload reference.
- Added explainable evidence dedupe: payload hash, canonical URL, external/source id, fuzzy title/body similarity.
- Added optional/fail-safe NLP enrichment boundary with deterministic fallback; no fake spaCy/FinBERT output and no collector crash if external ML assets are unavailable.
- Added explicit Radar factor scoring: relevance, novelty, sourceReliability, eventSeverity, timeDecay, marketConfirmation, executionability.
- Wired AlphaRadar ideas/read model/UI to evidence/candidate references and compact counters.
- Kept `/api/alpha-radar/ideas` read-only; durable evidence/candidate persistence happens during observation saves.
- Updated `docs/RADAR_RUNTIME.md` with evidence/candidate runtime, parser/enrichment boundaries, and discuss-before-implementation gates for SentenceTransformers/OpenBB/cryptofeed.
- Added `scripts/invariants-radar-evidence.ts` and package script `invariants:radar-evidence`.
- Updated safe deploy script so approved dependency drift is installed through the deploy protocol rather than manual `/opt/coinmaster` patching.

Verification passed before commit/push/deploy:
- `git diff --check`
- `npm run check`
- `npm run invariants:radar-evidence` → 15/15
- `npm run invariants:radar-handoff` → 34/34
- `npm run build`

Production verification after deploy:
- `/opt/coinmaster/.deploy-source-commit` matched deployed source commit at verification time.
- `coinmaster.service`: active.
- `/api/health`: `{"ok":true}`.
- root HTML contained `<div id="root"></div>`.
- `/opt/coinmaster/node_modules/feedparser/package.json`: `2.3.1`.
- `/opt/coinmaster/src/server/alphaRadarEvidence.ts`: present.
- `/opt/coinmaster/src/server/alphaRadarFeedParser.ts`: present.
- `/opt/coinmaster/src/shared/dto.ts`: contains `EvidenceBundle`.

GitHub sync:
- Commented verification summary on issue #62.
- Closed issue #62.
- Updated GitHub Project #2:
  - #61 Closed / Done
  - #62 Closed / Done
  - #63 Open / Todo
  - #64 Open / Todo

Execution note:
- Claude Opus was attempted first but hit usage limit until 03:10 Europe/Madrid.
- Codex fallback was used per owner instruction.
- Architect review corrected the first pass to use repo-owned npm `feedparser`, removed read-side persistence mutation, and kept Radar inside CoinMaster without making it the mandatory Trading Rules context controller (#63).

Runtime noise still intentionally uncommitted:
- `coinmaster/data/db.json`
- `prod-backups/dbshape_v1-pre-legacy-cleanup-20260424-160348.json`

Next task:
- #63 [ARCH-03] Radar role change: make RadarContextPolicy the context controller for Trading Rules entries.
