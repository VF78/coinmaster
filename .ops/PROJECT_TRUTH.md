# Coinmaster Project Truth (minimal)

Updated: 2026-03-11 Europe/Madrid

## Source of truth
- **Project plan, task list, priorities, and completion state live only in GitHub Project:**
  `https://github.com/users/VF78/projects/2`
- This file is **not** a backlog and must **not** duplicate project tasks.
- Use this file only for stable operating context, execution policy, links, and recovery notes.

## Repository links
- Repo: `https://github.com/VF78/coinmaster`
- GitHub Project: `https://github.com/users/VF78/projects/2`

## Active execution policy
- Preferred coding path: direct Claude Code CLI (no ACP wrapper)
- Claude Code model: **Sonnet 4.6** by default; **Opus 4.6** for hard/architectural or repeated stuck runs
- Fallback: Codex 5.3 in short, controlled iterations with explicit status reporting
- Watchdog:
  - progress watchdog: 8m (+4m extension if inference-only)
  - silent stall: 90s no stdout => restart
  - hard timeout: 25m
  - code 143 / consent-loop => immediate restart

## Known risk
Interactive consent prompts can cause `code 143` and stall runs.
Mitigation: ultra-small subtasks + watchdog + partial-diff salvage + immediate commit after local validation.

## Restart recovery playbook (no waiting)
Read in this order after restart:
1. `SOUL.md`
2. `USER.md`
3. `memory/YYYY-MM-DD.md` (today + yesterday)
4. `.ops/PROJECT_TRUTH.md`
5. `.ops/issue-25C-checklist.md`

## Operator note
If a task is asked for by name/status, fetch the current state from GitHub Project first instead of trusting any local backlog mirror.
