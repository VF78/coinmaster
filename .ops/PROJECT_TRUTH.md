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

Stage F BTC boundary closure (2026-09-20, local-only) has a reproducibly fresh interior winner at EMA34, TP `(0.2,0.225,0.575)`, BTC `7.75`, SOL `(1.875,2.8125,3.75)`: TOTAL `1928707.70729495`, 422 fills, fees `441546.20782708`, zero liquidations, and 2291 funding events with explicit UNKNOWN signed cash amount. Sequential 0.25 expansion strictly improved through BTC `7.75`; `8.0` fell to `1596324.64144040`, and local `7.625`/`7.875` were both lower, resolving the boundary with no extension beyond 8.0. Two separate clean from-genesis engines reproduce all economic totals, fee splits/notionals, fills, liquidations, and normalized fills/orders exactly (only `init_id` UUID is excluded). The winner is +`1133059.38679512` vs clean Stage E and +`1187801.15615570` vs Stage D. Compact report SHA-256 `be063d203a78c81ea01249da09cc8fc99da08dd547be8240616a94f987342400`; it remains `NOT_FAITHFUL_DIAGNOSTIC`/non-ranking for live. Corrected isolated H1/H2 tie Stage D H0 exactly, strict TP fill-cycle H3 is `548601.24002896`, and H4 BTC-only is `89591.16982085`; their final sealed checkpoint SHA-256 remains `7d2de71d1b4a4c54fe0cf1ee036cf224f654c93d4fa474f0416b917853ad9d60`.

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
