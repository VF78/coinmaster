# Target Architecture Audit — 2026-04-26

Scope: post-#61/#62/#63/#64 audit of CoinMaster live Trading Rules, Radar, backtest/optimizer governance, production logs, timeout posture, and runtime performance.

## Verified healthy

- Production source and workspace are aligned at deployed HEAD `eff327d6a3c769e64651a6f2044441c372dad6a1` at audit start.
- `coinmaster.service` was active with zero systemd restarts and `/api/health` returned `{"ok":true}`.
- Hyperliquid websocket was connected; health/perf showed no reconnects, queue length 0, failures 0, and event-loop lag below 1 ms during sampling.
- Recent production logs after the final deploy showed clean startup, Hyperliquid wallet verification, WS connection, risk watchdog startup, Engulfing/FVG monitor startup, and no warn/error/timeout/fatal lines after the final restart.
- Manual non-reduce-only order routes run `staleMarketDataGate`, `riskGateMiddleware`, `symbolAllocationGate`, `engulfingGate`, and `radarContextPolicyGate`; reduce-only/protection-only paths remain allowed.
- Explicit manual order sizes do not bypass gross-cap enforcement: `symbolAllocationGate` checks explicit `price` + `size` before route handlers; route-level gross-cap checks cover runtime auto-sized branches.

## Fixed during audit

### Backtest/live sizing parity gap

Finding: canonical backtest entries used a separate `computeSizeFromRules` path that ignored `riskPerTradePct` and `portfolioGrossCap`, while live runtime allocation sizing enforces those controls.

Fix:
- `src/core/backtestEngine.ts::computeSizeFromRules` now mirrors live risk sizing more closely:
  - validates price/equity/leverage/allocation;
  - blocks disabled symbols;
  - caps notional by `riskPerTradePct / slPct` when configured;
  - blocks oversized entries when `portfolioGrossCap` would be exceeded.
- `scripts/invariants-trading-rules.ts` now includes an explicit backtest sizing parity invariant.

## Remaining architecture follow-ups

These are not immediate production health blockers, but should become explicit backlog items if the target architecture is to be made fully strict.

1. SignalCandidate lifecycle is durable but not fully operational.
   - Current candidates are used for RadarContextPolicy and UI/read-models.
   - `routed` / `executed` candidate states are not yet reconciled from pending confirmations/order outcomes; execution reconciliation primarily updates `RadarSignalRecord` and `ExecutionIntent`.

2. RadarContextPolicy is an allow/block context controller, but `riskMultiplier` is not yet a live sizing multiplier.
   - The policy blocks entries when multiplier is zero and stores snapshots on `ExecutionIntent`.
   - Non-zero multipliers currently do not scale live order size; this is a deliberate next decision because applying >1.0 would increase risk and should be owner-approved.

3. ChampionConfig promotion is auditable governance, not automatic live activation.
   - Promotion creates a durable accepted champion.
   - Runtime Trading Rules still load from `settings.tradingRules`; applying a champion into live settings should remain an explicit future workflow.

4. Legacy deterministic replay is separate from the canonical backtest engine.
   - `/api/replay/run` still uses `runSimulationStep` and paper adapter flow.
   - Canonical promotion decisions use `src/core/backtestEngine.ts`; replay should either be deprecated or moved onto the canonical engine in a later cleanup.

## Verification commands run

- `git diff --check`
- `npm run check`
- `npm run invariants:signal-quality`
- `npm run invariants:fvg`
- `npm run invariants:engulfing`
- `npm run invariants:trading-rules`
- `npm run invariants:radar-evidence`
- `npm run invariants:radar-context-policy`
- `npm run invariants:radar-handoff`
- `npm run invariants:experiment-governance`
- `npm run invariants:backtest-run-persistence`
- `npm run invariants:compute-jobs`
- `npm run build`

Runtime noise intentionally excluded from commits: `coinmaster/data/db.json`, `prod-backups/`.
