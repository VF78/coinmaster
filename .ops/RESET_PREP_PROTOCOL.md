# Coinmaster Reset Preparation Protocol

Purpose: make restarts resumable with minimal token burn.

## When mandatory

Before planned model/session reset, OpenClaw restart, long interruption, or stopping while work is active/partial.

## Required sequence

1. Freeze current micro-step: finish it or state exactly what remains.
2. Sync GitHub Project status: active, done, or blocked truthfully.
3. Overwrite `.ops/ACTIVE_TASK.md` with a compact facts-only snapshot (~25–35 lines; hard cap ~40).
4. Record repo/deploy state: canonical root, branch, `HEAD`, `origin/main`, divergence, `/opt/coinmaster/.deploy-source-commit`, dirty/untracked state.
5. Record execution state: current Project item, goal, done, exact next step, checks, commit/deploy/push state, blockers/risks, key files only.
6. Clean junk: `.tmp-*`, scratch prompts, throwaway logs, stale artifacts. If intentional untracked files remain, list them.
7. Commit/push restart-critical docs (`.ops/ACTIVE_TASK.md`, protocol/truth/runbook changes) unless Vladimir says not to or push is blocked. If blocked, record exact reason.
8. Create `RESET_HANDOFF_YYYY-MM-DD.md` only for overflow/incident detail that cannot safely fit in `.ops/ACTIVE_TASK.md`.

## Required `.ops/ACTIVE_TASK.md` shape

```text
Updated:
Status:
GitHub Project item:
Canonical root:
Branch / HEAD / origin/main / deploy commit / divergence:
Goal:
Done:
Next exact step:
Checks / commit / deploy / push:
Blockers / risks:
Key files:
```

## Minimal recovery path after reset

1. `SOUL.md`
2. `USER.md`
3. `.ops/PROJECT_TRUTH.md`
4. `.ops/ACTIVE_TASK.md`
5. Live preflight:

```bash
cd /root/.openclaw/workspace/coinmaster/coinmaster
git status --short
git rev-parse HEAD
git rev-parse origin/main
git rev-list --left-right --count origin/main...HEAD
cat /opt/coinmaster/.deploy-source-commit 2>/dev/null || true
```

Only open deeper handoffs/checklists/memory if `.ops/ACTIVE_TASK.md` says they matter.

## Final reset gate

Project status current; `.ops/ACTIVE_TASK.md` current; repo synced or blocker recorded; exact next step/blockers/repo-deploy state written; no unexplained junk.
