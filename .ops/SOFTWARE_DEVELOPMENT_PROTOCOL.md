# Coinmaster Software Development Protocol

Purpose: canonical rules for Coinmaster software work with minimum restart token burn.

## 1) Sources of truth

- Canonical repo: `/root/.openclaw/workspace/coinmaster/coinmaster`
- Deploy mirror: `/opt/coinmaster` — never edit manually.
- Backlog/status: GitHub Project #2 `https://github.com/users/VF78/projects/2`
- Current task snapshot: `.ops/ACTIVE_TASK.md`
- One active implementation task at a time; do not create duplicates if an existing Project item covers the work.

## 2) Default execution model

- Default model for **all Coinmaster tasks**: `openai-codex/gpt-5.5`.
- Main chat orchestrates, reviews, reports, and handles trivial doc/one-line changes directly.
- Non-trivial coding uses a subagent/coding-agent with `openai-codex/gpt-5.5` unless Vladimir explicitly asks otherwise.
- Use another executor/model only when Codex 5.5 is unavailable, rate-limited, clearly ineffective, or explicitly requested.

## 3) Development rules

- Build inside the current architecture and deliberate evolution; do not create parallel engines or bypass paths.
- Prefer the smallest complete clean change; no refactor-for-refactor.
- No hacks, duplicate execution paths, hidden sidecars, or “temporary” complexity that can become permanent.
- Protect live paths first: Daily Drawdown, entry/confirmation/auto-open, TP/SL, persistence, replay, recovery.
- Runtime settings truth is the persisted DB snapshot unless code explicitly says otherwise; env vars are not assumed authoritative.
- Before calling something a rollback/regression, verify `main`, `origin/main`, deployed commit, and semantic surface.

## 4) Preflight before implementation

From canonical repo:

```bash
git branch --show-current        # default must be main unless user requested otherwise
git status --short
git rev-parse HEAD
git rev-list --left-right --count origin/main...HEAD
cat /opt/coinmaster/.deploy-source-commit 2>/dev/null || true
```

Then set/confirm the GitHub Project item state and update `.ops/ACTIVE_TASK.md`.

## 5) Workspace hygiene

- Work only in the canonical repo.
- Scratch files go to `/tmp` or another non-repo path.
- Before commit/reset, `git status --short` must contain only intentional changes; document intentional untracked/dirty state in `.ops/ACTIVE_TASK.md`.

## 6) Verification standard

Use the smallest meaningful gate set:

- task-specific invariant/smoke script(s),
- `npm run check`,
- `npm run build` when UI/server wiring changed,
- direct runtime/API evidence when behavior changed.

Do not claim completion without evidence or a named blocker.

## 7) Commit/deploy

- Review diff before commit.
- Default branch target: `main`; avoid feature branches unless requested.
- Deploy only through `scripts/deploy-prod-safe.sh` or the active post-commit hook flow.
- After deploy verify: deployed commit = workspace `HEAD`, `coinmaster.service` active, health endpoint ok, and task-specific surface ok.
- If push/deploy is deferred or blocked, record exact reason in `.ops/ACTIVE_TASK.md`.

## 8) Restart protocol

Before reset/restart/handoff, follow `.ops/RESET_PREP_PROTOCOL.md`: update GitHub Project, compress `.ops/ACTIVE_TASK.md`, record repo/deploy state, exact next step, blockers, and key files only.

## 9) Minimal doc map

Read in this order after restart:

1. `.ops/PROJECT_TRUTH.md`
2. `.ops/ACTIVE_TASK.md`
3. Only then open this file, reset/task-state protocols, or deep docs if needed.
