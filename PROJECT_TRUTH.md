# PROJECT_TRUTH.md

Updated: 2026-03-26 Europe/Madrid

Canonical project truth: `.ops/PROJECT_TRUTH.md`

Quick rules:
- GitHub Project is the only task backlog and source of status.
- Main work default: `openai-codex/gpt-5.4-mini`; reserve only: `anthropic/claude-sonnet-4-6`.
- Coding work goes through a subagent / coding agent.
- Coding policy: Sonnet 4.6 default; Opus 4.6 for hard/architectural/stuck reruns; Codex 5.4 fallback only when Claude limit is reached.
- After each completed GitHub Project task, reset temporary model override to default.
- Deployment invariant:
  - canonical workspace = `/root/.openclaw/workspace/coinmaster/coinmaster`
  - deploy mirror = `/opt/coinmaster`
  - no manual edits in `/opt/coinmaster`
  - Hyperliquid / Bybit / Telegram connection settings live in the DB snapshot; env vars are not runtime source of truth
  - commit on `main` triggers post-commit deploy sync + restart
  - if workspace HEAD != `/opt/coinmaster/.deploy-source-commit`, redeploy first
- No secrets in repo or truth files.
