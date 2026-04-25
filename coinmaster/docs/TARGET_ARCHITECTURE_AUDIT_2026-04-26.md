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

## Follow-up fixes after owner instruction

The owner asked to close the remaining issues without hacks, overengineering, or architecture drift. The follow-up patch therefore made the smallest target-aligned changes:

1. SignalCandidate lifecycle is now reconciled through handoff outcomes.
   - `ExecutionIntentPolicySnapshot` carries `signalCandidateId`.
   - Accepted policy-controlled entries transition candidates to `routed` when they enter pending confirmation or auto-order placement.
   - Confirmed/placed orders transition candidates to `executed`; rejected outcomes transition to `rejected` where legal.

2. RadarContextPolicy `riskMultiplier` now materially affects live size without increasing risk.
   - Multipliers are conservative live caps in `[0, 1]`.
   - Handoff, pending confirmation execution, and manual order routes apply the multiplier to non-reduce-only order size unless the operator uses the explicit audited Radar override.
   - This avoids hidden risk expansion while making Radar context operational.

3. ChampionConfig has an explicit live-apply workflow.
   - `POST /api/champions/:id/apply` requires owner auth, an active accepted champion, and manual confirmation.
   - It applies the champion Trading Rules snapshot to live settings and refreshes runtime rules.

4. Legacy deterministic replay is disabled when the legacy replay API flag is enabled.
   - `/api/replay/run` returns `410 legacy_replay_disabled` and points callers to canonical backtest runs.
   - This prevents a third decision model from being mistaken for target-architecture research.

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
