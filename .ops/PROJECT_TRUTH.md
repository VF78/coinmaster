# Coinmaster Project Truth

Updated: 2026-05-04 Europe/Madrid

## Sources of truth

- Backlog/status: GitHub Project #2 `https://github.com/users/VF78/projects/2`
- Canonical repo: `/root/.openclaw/workspace/coinmaster/coinmaster`
- Deploy mirror: `/opt/coinmaster` — never edit manually.
- Current restart snapshot: `.ops/ACTIVE_TASK.md`
- Stable rules only live here; backlog/current work does not.

## Objective

Coinmaster must autonomously trade within Trading Rules/Radar and move toward **≥50% monthly ROI**. Every task must directly improve profitability, execution quality, risk/loss control, or hypothesis-testing speed/quality. No refactor-for-refactor.

## Core invariants

- One active implementation task at a time.
- Default model for all Coinmaster tasks: `openai-codex/gpt-5.5`.
- Non-trivial development uses subagent/coding-agent unless the change is trivial or Vladimir requests otherwise.
- GitHub Project status and `.ops/ACTIVE_TASK.md` must stay current.
- No secrets in repo, truth files, issue bodies, or chat.

## Deployment invariant

- All edits happen in canonical repo only.
- `/opt/coinmaster` is produced by deploy, not manual patches.
- Hyperliquid/Bybit/Telegram runtime connection settings live in persisted DB snapshot unless code explicitly says otherwise.
- Commit/deploy flow: post-commit hook or `scripts/deploy-prod-safe.sh` → typecheck/build → sync `src/`/`dist/` → restart `coinmaster.service` → write `/opt/coinmaster/.deploy-source-commit`.
- Before debugging/restarting, compare workspace `HEAD` with deployed commit; redeploy first if they differ.

## Protocol map

- Development: `.ops/SOFTWARE_DEVELOPMENT_PROTOCOL.md`
- Reset/handoff: `.ops/RESET_PREP_PROTOCOL.md`
- Task state/watchdog: `.ops/TASK_STATE_PROTOCOL.md`
- Current compact state: `.ops/ACTIVE_TASK.md`
