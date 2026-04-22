# Coinmaster Project Truth

Updated: 2026-04-22 Europe/Madrid

## Source of truth
- Tasks and statuses: GitHub Project `https://github.com/users/VF78/projects/2`
- Canonical code workspace: `/root/.openclaw/workspace/coinmaster/coinmaster`
- Deploy mirror: `/opt/coinmaster`
- This file stores only stable operating rules, not a backlog.

## Operational protocol map
- Software development protocol: `.ops/SOFTWARE_DEVELOPMENT_PROTOCOL.md`
- Reset preparation protocol: `.ops/RESET_PREP_PROTOCOL.md`
- Task-state / watchdog protocol: `.ops/TASK_STATE_PROTOCOL.md`
- Current compact handoff / restart snapshot: `.ops/ACTIVE_TASK.md`

## Core operating invariants
- Software development goes through a **subagent / coding agent** for non-trivial work.
- Canonical software-development rules live in `.ops/SOFTWARE_DEVELOPMENT_PROTOCOL.md`.
- Reset / restart preparation rules live in `.ops/RESET_PREP_PROTOCOL.md`.
- `.ops/ACTIVE_TASK.md` must stay current whenever a task is active or partially complete.
- After each completed GitHub Project task: reset any temporary model override to default.

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

## Restart recovery
1. `SOUL.md`
2. `USER.md`
3. `.ops/PROJECT_TRUTH.md`
4. `.ops/ACTIVE_TASK.md`
5. live preflight (`git status --short`, `git rev-parse HEAD`, `git rev-list --left-right --count origin/main...HEAD`, `/opt/coinmaster/.deploy-source-commit`)
6. only then open deeper handoff/checklist/memory files if `.ops/ACTIVE_TASK.md` says they matter
