# Coinmaster Project Truth

Updated: 2026-03-26 Europe/Madrid

## Source of truth
- Tasks, priorities, and statuses live only in GitHub Project:
  `https://github.com/users/VF78/projects/2`
- Repo: `https://github.com/VF78/coinmaster`
- This file is operating context only, not a backlog.

## Execution rules
- Main goal: uptime, stability, reproducibility, safe changes.
- For task status/names, check GitHub Project first.
- One active implementation task at a time.
- No secrets in repo, truth files, or issue bodies.

## Coding policy
- Software development work goes through a subagent / coding agent, not the main chat turn.
- Preferred coding path: direct Claude Code CLI.
- Model policy for coding:
  - Sonnet 4.6 = default
  - Opus 4.6 = hard/architectural/stuck reruns
  - Codex 5.3 = fallback only if Claude path is unavailable
- After each completed GitHub Project task: reset temporary model override back to default.

## Watchdog
- progress watchdog: 8m (+4m if inference-only)
- silent stall: 90s no stdout => restart
- hard timeout: 25m
- code 143 / consent-loop => immediate restart with smaller step

## Restart recovery
Read after restart:
1. `SOUL.md`
2. `USER.md`
3. `memory/YYYY-MM-DD.md` (today + yesterday)
4. `.ops/PROJECT_TRUTH.md`
5. `.ops/issue-25C-checklist.md`
