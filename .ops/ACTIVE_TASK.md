# ACTIVE_TASK

Updated: 2026-04-25 22:47 Europe/Madrid
Status: COMPLETE LOCALLY / GitHub issue #61 implementation committed locally; GitHub Project update blocked by missing `gh` authentication
GitHub Project: https://github.com/users/VF78/projects/2
Active item: #61 [ARCH-01] Trading Rules target upgrade: SignalQualityContext, regime filters, RR gate, fail-safe entries
Active issue: https://github.com/VF78/coinmaster/issues/61
Canonical root: /root/.openclaw/workspace/coinmaster/coinmaster
Branch / original preflight HEAD / deploy commit: main / 0e64964abaa3684caf211d60e4f2bf2981b7f44c / 7742add28bb8b3aac2f3d7983c416e13a0b0aba2

Owner instruction:
- Clean Project #2, keep #61-#64 only, put #61 In Progress.
- Implement #61 by protocol on Claude Opus 4.6 first; fallback Codex 5.5 only if needed.
- Review coding-agent output architecturally; remove hacks/workarounds/overengineering; continue slice-by-slice without waiting until #61 is complete.

Completed:
- Removed 27 old items from GitHub Project #2; repository issues were not deleted.
- Verified Project #2 kept only #61-#64.
- Set #61 to In Progress; #62-#64 remained Todo.
- Launched Claude Opus 4.6; first unsafe root bypass launch failed and was relaunched with `--permission-mode acceptEdits`.
- Reviewed and corrected Claude's first pass manually.
- Committed clean local implementation with message: `Implement Trading Rules signal quality context`.

Implemented for #61:
- New pure `src/core/signalQualityContext.ts` with deterministic TypeScript EMA/ATR/ADX, regime assessment, displacement / FVG impulse quality, expected RR, and combined verdict.
- Live Engulfing/FVG monitors run signal-quality gate before unified `handoffStrategyEntrySignal`.
- Backtest engine mirrors signal-quality gate and FVG impulse handling.
- `regimeTf` constrained to owner-approved HTF values (`1h` / `4h`) in normalization and UI.
- FVG latest-closed-candle lag fixed; invariant added to prove latest supplied closed candle can complete an FVG zone.
- FVG signal-quality displacement now uses the actual FVG impulse triple (`c0,c1,c2`), not the retrace candle.
- Live regime candle fetch failure blocks entries when quality gate is active.
- `engulfingGate` changed from fail-open to fail-safe for new non-reduce-only entries, with explicit audited override `tradingRulesGateOverride: true`.
- Live RR gate no longer invents fallback TP/SL; if runtime TP/SL is unavailable, RR evaluates to 0.
- Approved eight Stage-1 fields exposed in UI only: `regimeTf`, `adxMin`, `minImpulseAtr`, `minExpectedRr`, `timeStopBars`, `riskPerTradePct`, `eventLockoutMinutes`, `portfolioGrossCap`.
- `riskPerTradePct` wired into deterministic allocation sizing as opt-in (`0` default): caps notional by risk budget / SL distance.
- `portfolioGrossCap` helpers and live guard added for auto-sized entry flows, auto-confirmed entries, and pending confirmations.
- `timeStopBars` added to backtest and live system-managed TP tracking; no TP1 follow-through after N entry-timeframe bars closes remaining position with reduce-only IOC and cancels managed TP/SL orders.
- `eventLockoutMinutes` wired to real existing AlphaRadar observations: fresh `macroShock` / `macro-shock` / high-urgency macro observations block Trading Rules auto entries. Check failure blocks entries fail-safe.
- No external trading engines added; no TA-Lib/Python dependency in live path.

Manual architecture fixes applied:
- Corrected ATR invariant for perfectly flat candles.
- Corrected ADX seed indexing to first ADX at `2*period-1`.
- Removed synthetic RR fallback.
- Fixed fail-open paths in signal-quality and engulfing gates.
- Kept additions as thin layers on existing Trading Rules / handoff architecture.

Final verification:
- `git diff --check` passed for clean code/doc set excluding runtime noise.
- `npm run check` passed.
- `npm run invariants:trading-rules` passed: 61/61.
- `npm run invariants:signal-quality` passed: 32/32.
- `npm run invariants:fvg` passed: 18/18.
- `npm run invariants:engulfing` passed: 38/38.
- `npm run build` passed (`vite build`).

Clean commit-set:
- `.ops/ACTIVE_TASK.md`
- `coinmaster/package.json`
- `coinmaster/scripts/invariants-fvg.ts`
- `coinmaster/scripts/invariants-trading-rules.ts`
- `coinmaster/scripts/invariants-signal-quality.ts`
- `coinmaster/src/core/backtestEngine.ts`
- `coinmaster/src/core/fvgEvaluator.ts`
- `coinmaster/src/core/signalQualityContext.ts`
- `coinmaster/src/exchange/types.ts`
- `coinmaster/src/server/index.ts`
- `coinmaster/src/server/runtimeRules.ts`
- `coinmaster/src/shared/dto.ts`
- `coinmaster/src/shared/tradingRules.ts`
- `coinmaster/src/web/pages/TradingRulesPage.tsx`
- `coinmaster/docs/OSS_COMPONENT_ANALYSIS_2026-04-25.md`
- `coinmaster/docs/TARGET_ARCHITECTURE_OWNER_DIRECTION_2026-04-25.md`
- `docs/TARGET_ARCHITECTURE_2026.md`

Excluded runtime noise:
- `coinmaster/data/db.json`
- `prod-backups/dbshape_v1-pre-legacy-cleanup-20260424-160348.json`

Blocked external completion:
- `gh auth status` reports no logged-in GitHub host, so issue comment / Project status update to Done cannot be performed from this session until GitHub auth is restored.
