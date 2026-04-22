# Coinmaster Software Development Protocol

Purpose: one clear place for Coinmaster software-development rules.

## 1) Scope and source of truth

- Canonical repo: `/root/.openclaw/workspace/coinmaster/coinmaster`
- Deploy mirror: `/opt/coinmaster`
- Task backlog + status source of truth: GitHub Project `https://github.com/users/VF78/projects/2`
- One active implementation task at a time.
- Do not create new backlog items if an existing GitHub Project item already covers the work.

## 2) Execution model

- Main chat orchestrates. Non-trivial software development goes through a subagent / coding agent.
- Default coding executor: **Claude Sonnet 4.6**.
- Hard / architectural / stuck reruns: **Claude Opus 4.6**.
- Fallbacks only when Claude is unavailable, rate-limited, or clearly ineffective:
  - **Codex 5.4 mini** for smaller bounded passes, audits, and retries.
  - **Codex 5.4** for harder fallback runs when mini is not enough.
- If the user explicitly requests another model/tool, follow that.

## 3) Development principles

- Develop inside the **current architecture and its deliberate evolution**, not beside it.
- Prefer the smallest complete change that solves the problem cleanly.
- No broad refactor unless explicitly requested or clearly required for safety.
- No hacks, duplicate execution paths, sidecar logic that bypasses the engine, or “temporary” complexity that becomes permanent.
- Use best practices: clear ownership, deterministic behavior, explicit invariants, bounded scope, and readable code.
- Before calling something a rollback/regression, verify the actual state of `main`, `origin/main`, deployed commit, and whether the behavior belongs to a different surface/semantic model (for example, live execution controls vs backtest bias controls).
- Protect live trading paths first:
  - Daily Drawdown
  - live entry / confirmation / auto-open flow
  - TP/SL handling
  - persistence / replay / recovery semantics
- Runtime truth for live settings is the persisted DB snapshot; env vars are not authoritative at runtime unless the code explicitly says so.

## 4) Workspace hygiene

- Develop only in the canonical repo. Never edit `/opt/coinmaster` manually.
- Keep the workspace clean:
  - no `.tmp-*`
  - no scratch prompts in repo root
  - no ad-hoc exports/log dumps unless intentional and documented
  - no stale handoff files beyond the current useful one
- Scratch work belongs in `/tmp` or another non-repo location.
- If a temporary file inside the repo is unavoidable, delete it before commit/reset.
- Before commit/reset, `git status --short` should contain only intentional changes.

## 5) Mandatory preflight before coding

Run or verify these before starting implementation:

1. `git branch --show-current` → must be `main` unless user explicitly requested otherwise.
2. `git status --short`
3. `git rev-parse HEAD`
4. `git rev-list --left-right --count origin/main...HEAD`
5. `cat /opt/coinmaster/.deploy-source-commit` (if deploy mirror exists)
6. Set the matching GitHub Project item to the correct active state.
7. Update `.ops/ACTIVE_TASK.md`.

## 6) Git / branch / divergence rules

- Default working branch: **`main` only**.
- Do not create feature branches, detached-head work, or parallel local variants unless the user explicitly asks.
- Restart-critical operational docs live in the repo, not only in local chat/context:
  - `.ops/PROJECT_TRUTH.md`
  - `.ops/SOFTWARE_DEVELOPMENT_PROTOCOL.md`
  - `.ops/RESET_PREP_PROTOCOL.md`
  - `.ops/TASK_STATE_PROTOCOL.md`
  - `.ops/ACTIVE_TASK.md`
- Keep three states visible and distinct:
  - workspace `HEAD`
  - `origin/main`
  - deployed commit (`/opt/coinmaster/.deploy-source-commit`)
- After a completed task, the default target state is convergence:
  - local `main`
  - `origin/main`
  - deployed commit
- If push is intentionally deferred, record it explicitly in `.ops/ACTIVE_TASK.md` and tell the user plainly.

## 7) Implementation discipline

- Work in micro-steps with an artifact each time: diff, test output, log evidence, or commit.
- Follow `.ops/TASK_STATE_PROTOCOL.md` for ACTIVE/BLOCKED/FALLBACK/SPLIT handling.
- When stuck, narrow the step before expanding the solution.
- Prefer fixing root causes inside existing abstractions over adding glue code around them.

## 8) Verification standard

Use the smallest meaningful verification set for the task, typically:

- task-specific invariant / smoke script(s)
- `npm run check`
- `npm run build` when UI/server wiring changed

Do not claim completion without verification evidence or a named blocker.

## 9) Commit / deploy protocol

- Review the diff before commit.
- Commit on `main` with a concise, concrete message.
- Deploy only through `scripts/deploy-prod-safe.sh` or the active post-commit hook flow.
- Never treat `/opt/coinmaster` as a manual patch target.
- After deploy, verify at minimum:
  - deployed commit matches workspace `HEAD`
  - `coinmaster.service` is active
  - health endpoint responds
  - task-specific surface responds

## 10) Required operational records

Keep these current during real work:

- GitHub Project status
- `.ops/ACTIVE_TASK.md`
- optional dated reset handoff only when `.ops/ACTIVE_TASK.md` is too small to carry a safe restart

## 11) Minimal document map

Read/maintain the smallest authoritative set first:

- project truth → `.ops/PROJECT_TRUTH.md`
- development rules → `.ops/SOFTWARE_DEVELOPMENT_PROTOCOL.md`
- reset rules → `.ops/RESET_PREP_PROTOCOL.md`
- task-state/watchdog rules → `.ops/TASK_STATE_PROTOCOL.md`
- current task snapshot → `.ops/ACTIVE_TASK.md`

Treat older deep-dive docs as reference material, not default startup context.
