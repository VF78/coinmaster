# PROJECT_TRUTH.md

Updated: 2026-04-22 Europe/Madrid

Canonical project truth: `.ops/PROJECT_TRUTH.md`

Quick rules:
- GitHub Project is the only task backlog and source of status.
- Development rules live in `.ops/SOFTWARE_DEVELOPMENT_PROTOCOL.md`.
- Reset-prep rules live in `.ops/RESET_PREP_PROTOCOL.md`.
- Current compact task snapshot lives in `.ops/ACTIVE_TASK.md`.
- Deployment invariant:
  - canonical workspace = `/root/.openclaw/workspace/coinmaster/coinmaster`
  - deploy mirror = `/opt/coinmaster`
  - no manual edits in `/opt/coinmaster`
  - Hyperliquid / Bybit / Telegram connection settings live in the DB snapshot; env vars are not runtime source of truth
  - commit on `main` triggers post-commit deploy sync + restart
  - if workspace HEAD != `/opt/coinmaster/.deploy-source-commit`, redeploy first
- No secrets in repo or truth files.
