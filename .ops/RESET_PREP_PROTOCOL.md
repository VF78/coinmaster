# Coinmaster Reset Preparation Protocol

Purpose: make reset/restart/session handoff resumable with minimal token burn and no ambiguity.

## 1) When this protocol is mandatory

Run this before any planned:

- model/session reset
- OpenClaw restart
- long interruption / handoff
- stopping work while a task is still active or partially complete

## 2) Required preparation sequence

1. **Freeze the current micro-step cleanly**
   - Do not reset in the middle of an unexplained edit.
   - Either finish the micro-step or state exactly what remains.

2. **Sync GitHub Project status**
   - Active unfinished task → correct active status.
   - Fully finished task → `Done`.
   - If blocked and no dedicated blocked status exists, keep the task status honest and capture the blocker in `.ops/ACTIVE_TASK.md`.

3. **Update `.ops/ACTIVE_TASK.md` (mandatory)**
   - Overwrite in place; do not keep a growing diary there.
   - Target size: ~25–35 lines, hard cap ~40 lines.
   - Facts only, no long narrative.

4. **Record repo + deploy state in `.ops/ACTIVE_TASK.md`**
   - canonical root
   - branch
   - workspace `HEAD`
   - `origin/main`
   - divergence vs `origin/main`
   - deployed commit from `/opt/coinmaster/.deploy-source-commit`
   - whether there are local uncommitted changes

5. **Record execution state in `.ops/ACTIVE_TASK.md`**
   - current GitHub Project item
   - one-sentence goal
   - short done list
   - exact next step
   - checks state
   - commit state
   - deploy state
   - push state
   - blockers / risks
   - key files only

6. **Clean workspace junk**
   - delete `.tmp-*`, scratch prompts, throwaway logs, and stale local artifacts
   - move temporary investigation files out of the repo
   - if any intentional untracked file remains, list it explicitly in `.ops/ACTIVE_TASK.md`

7. **Sync restart-critical state into GitHub repo**
   - `.ops/ACTIVE_TASK.md` is not local-only; it is a repo-backed restart artifact.
   - If restart-critical docs changed (`.ops/ACTIVE_TASK.md`, protocol docs, runbooks, current truth docs), commit them.
   - Push `main` to `origin` before reset unless the user explicitly says not to or push is blocked.
   - If push is blocked, write the exact reason and current divergence into `.ops/ACTIVE_TASK.md`.

8. **Use a dated reset handoff only if strictly needed**
   - Default: `.ops/ACTIVE_TASK.md` is enough.
   - Create/update `RESET_HANDOFF_YYYY-MM-DD.md` only when there is incident-grade detail or bounded context that cannot fit safely in `.ops/ACTIVE_TASK.md`.
   - Keep it short and practical.

9. **Final reset gate**
   - GitHub Project status is current.
   - `.ops/ACTIVE_TASK.md` is current.
   - GitHub repo is synced, or the push blocker is explicitly recorded.
   - next exact step is written
   - blockers are written
   - repo/deploy state is written
   - no unexplained junk remains in the workspace

## 3) Required `.ops/ACTIVE_TASK.md` structure

Use this shape:

- `Updated:`
- `Status:`
- `GitHub Project item:`
- `Canonical root:`
- `Branch / HEAD / origin/main / deploy commit / divergence:`
- `Goal:`
- `Done:`
- `Next exact step:`
- `Checks / commit / deploy / push:`
- `Blockers / risks:`
- `Key files:`

If no task is active, say so explicitly and state what decision/work is pending.

## 4) Minimal recovery path after reset

Read only this by default:

1. `SOUL.md`
2. `USER.md`
3. `.ops/PROJECT_TRUTH.md`
4. `.ops/ACTIVE_TASK.md`
5. live preflight:
   - `git status --short`
   - `git rev-parse HEAD`
   - `git rev-list --left-right --count origin/main...HEAD`
   - `git rev-parse origin/main`
   - `cat /opt/coinmaster/.deploy-source-commit`

Only then, if `.ops/ACTIVE_TASK.md` says it matters, open:

- the current dated `RESET_HANDOFF_*.md`
- the current issue/runtime checklist
- daily memory or longer docs

## 5) Token discipline

- `.ops/ACTIVE_TASK.md` is the restart source, not chat history.
- Prefer one compact authoritative file over multiple long handoffs.
- Do not reread daily memory by default.
- Do not paste large retrospectives into reset notes.
- If something is worth remembering for restart, compress it into actionable bullets.
