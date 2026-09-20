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

Stage G maximum-ROI reproducible research winner is EMA34, TP `(0.2125,0.2125,0.575)`, BTC `7.875`, SOL `(1.75,2.625,3.5)`, TOTAL `1978792.33053629` (+`50084.62324134` vs Stage F). Its completed G4 row and one clean from-genesis confirmation match exactly across TOTAL/ACTIVE/reserve, fee splits/notionals, 421 fills, zero liquidations, 2280 funding postings, and normalized fills/orders (only engine `init_id` is dropped). Prior G1 at `1945213.42678339` is runner-up. The prior G4 exclusion was procedural, not evidence of an invalid simulation; no new parameter/grid/extension or other native simulation ran. The confirmed report remains `NOT_FAITHFUL_DIAGNOSTIC` and non-live-ranking. Corrected isolated H1/H2 tie Stage D H0 exactly, strict TP fill-cycle H3 is `548601.24002896`, and H4 BTC-only is `89591.16982085`; their final sealed checkpoint SHA-256 remains `7d2de71d1b4a4c54fe0cf1ee036cf224f654c93d4fa474f0416b917853ad9d60`.

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
