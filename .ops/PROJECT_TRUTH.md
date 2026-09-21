# Coinmaster Project Truth

Updated: 2026-09-22 Europe/Moscow

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

## Immutable runtime configuration checkpoint

Issue #95 D1 execution-semantics parity is implemented locally on top of D0 and recorded in this local checkpoint. Planned SOL exits now use explicit native taker IOC control A (including zero-spread books); post-only GTC remains limited to explicit BTC TP targets. Regime/trail forced closes and SOL hard-timeout exits preempt queued/resting SOL work, cancel leaves, then reduce the reconciled remainder; a forced close clears timeout ownership before its quote loop and always uses actual native cache leaves. Every BTC entry/SOL add rechecks the runtime pause/stale/safe-for-increase gate immediately before submission; reductions bypass it. Confirmed partial BTC TP fills earn only the proportional cumulative SOL right and use their actual confirmed fill cycle for strict H3, while notional sizing uses buy ask/sell bid before precision/minimum validation. Funding journal isolation is unchanged. Focused unit/native tests plus broad runtime regression: 125 passed (68 existing Pandas warnings). No deploy, VPS/service, paper command/order, live action, GitHub mutation, optimizer, backtest, or push occurred.

Issue #94 D0 is implemented locally: `runtime/configs/stage-g-v1.json` pins the entire sealed Stage-G `Candidate` schema. The strict file loader canonicalizes and SHA-256 hashes Candidate content (never labels), rejects missing/extra/non-finite/economically invalid data, and returns a frozen Candidate. The non-secret `paper-stage-g-example.instance.json` documents the required instance envelope. Production paper startup now requires a strict instance config and loads it plus the strategy file once before `TradingNode` construction; it logs and reports `instance_id`, venue, mode, strategy/order identity, and exact candidate hash, while passing the latter IDs into the actual native strategy config. Missing or invalid production config fails closed; an in-process default exists only for isolated tests. Focused tests: 26 passed. No deploy/VPS/paper/live/optimizer action or push occurred. The explicitly addressed CLT Git binary is usable for the local checkpoint; D1 code parity is recorded above, while any operational activation remains separately scoped.

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
