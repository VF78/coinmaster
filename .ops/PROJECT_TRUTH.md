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

Stage E funding-ledger correction (2026-09-20, local-only) established a reproducible clean result at EMA34, TP `(0.2,0.225,0.575)`, BTC `4.375`, SOL `(1.875,2.8125,3.75)`: two distinct from-genesis BacktestEngines both produced TOTAL `795648.32049983`, 422 fills, fees `182721.51343851`, zero liquidations, and 2291 current-run funding postings. Their normalized fills/orders match exactly after excluding only the per-engine `init_id` UUID. The correction isolates every from-genesis funding journal in a unique attempt DB and publishes it atomically only after successful checkpoint/close; genuine process-restart durable-ID behavior remains unchanged. The clean result is +`6707.71041910` over prior clean Stage E leader `788940.61008073` and +`54741.76936058` vs Stage D `740906.55113925`, so no full grid rerun was required. Pre-fix observed `808600.57496264` (421 fills) is retained as excluded canonical-journal-reuse incident evidence, not a winner. Corrected compact report SHA-256 `35e285d45aa86c3c54fde8f143974cabcfa2b385cda8e28de5de39031932bcfa`; it remains `NOT_FAITHFUL_DIAGNOSTIC`/non-ranking for live. The BTC 4.375 boundary is unresolved and was not expanded. Corrected isolated H1/H2 tie Stage D H0 exactly, strict TP fill-cycle H3 is `548601.24002896`, and H4 BTC-only is `89591.16982085`; their final sealed checkpoint SHA-256 remains `7d2de71d1b4a4c54fe0cf1ee036cf224f654c93d4fa474f0416b917853ad9d60`.

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
