# Coinmaster Project Truth

Updated: 2026-03-26 Europe/Madrid

## Source of truth
- Tasks and statuses: GitHub Project `https://github.com/users/VF78/projects/2`
- Canonical code workspace: `/root/.openclaw/workspace/coinmaster/coinmaster`
- Deploy mirror: `/opt/coinmaster`
- This file stores only stable operating rules, not a backlog.

## Model policy
- **Primary model for my main work:** `openai-codex/gpt-5.4-mini`
- **Reserve model only:** `anthropic/claude-sonnet-4-6`
- After each completed GitHub Project task: reset any temporary model override to default.

## Coding policy
- Software development goes through a **subagent / coding agent**, not the main chat.
- Coding model policy:
  - **Default:** Sonnet 4.6
  - **Hard / architectural / stuck reruns:** Opus 4.6
  - **Fallback only:** Codex 5.4 (when Claude limit is reached)

## Deployment invariant
- All code edits happen in the canonical workspace repo only.
- `/opt/coinmaster` is a deploy mirror, never a manual edit target.
- Connection settings for Hyperliquid, Bybit, and Telegram live in the persisted DB snapshot and must be treated as runtime source of truth; env vars are not authoritative at runtime.
- On every commit to `main`, the active post-commit hook runs `scripts/deploy-prod-safe.sh`:
  - typecheck + build
  - sync `src/` and `dist/` to `/opt/coinmaster`
  - restart `coinmaster.service`
  - write `/opt/coinmaster/.deploy-source-commit`
- Before debugging or restarting, compare workspace HEAD with `/opt/coinmaster/.deploy-source-commit`; if they differ, redeploy first.

## Execution rules
- One active implementation task at a time.
- For task status and priorities, check GitHub Project first.
- No secrets in repo, truth files, or issue bodies.

## Watchdog
- progress: 8m (+4m if inference-only)
- silent stall: 90s => restart
- hard timeout: 25m

## Restart recovery
1. `SOUL.md`
2. `USER.md`
3. `memory/YYYY-MM-DD.md` (today + yesterday)
4. `.ops/PROJECT_TRUTH.md`
5. `.ops/issue-25C-checklist.md`
