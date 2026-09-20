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

## Latest native research checkpoint

Stage D joint refinement (2026-09-20, local-only) is sealed at EMA34, BTC TP `(0.2,0.25,0.55)`, BTC multiplier `4.0`, and SOL size profile `(2,3,4)`: terminal ACTIVE+RESERVE TOTAL `740906.55113925`. Corrected isolated H1/H2 tie H0 exactly, while strict same-cycle TP-right H3 is `548601.24002896`; accepted late-right control semantics remain default. H4 BTC-only was `89591.16982085`, evidencing SOL increment `651315.38131840`. All remain `NOT_FAITHFUL_DIAGNOSTIC`, non-ranking for live; no Stage E ran. Corrected five-row checkpoint SHA-256 `439d68a0e449f49916446d3b16543efbe24a6563f795d2b1617957ce1b7c82d9` with retained supersession evidence SHA-256 `7aad4e663c6702440006bb72e4ea87ad1548dd6a3128721ab6b8c8ead018b136`.

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
