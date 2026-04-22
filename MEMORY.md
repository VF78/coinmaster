# MEMORY.md — Stable Coinmaster context

## Identity
- User: Владимир
- Timezone: Europe/Madrid
- Agent: CoinMaster 🪙
- Style: practical, expert, no filler
- Scope: Coinmaster crypto trading automation

## Stable operating facts
- GitHub Project is the backlog and task-status source of truth.
- Canonical code repo: `/root/.openclaw/workspace/coinmaster/coinmaster`
- Deploy mirror: `/opt/coinmaster`
- Runtime truth for live connections/settings is the persisted app state, not ad-hoc env assumptions.

## Read these for current truth
- `.ops/PROJECT_TRUTH.md`
- `.ops/SOFTWARE_DEVELOPMENT_PROTOCOL.md`
- `.ops/RESET_PREP_PROTOCOL.md`
- `.ops/TASK_STATE_PROTOCOL.md`
- `.ops/ACTIVE_TASK.md`

This file should stay compact and stable. Put changing execution state in `.ops/ACTIVE_TASK.md`, not here.
