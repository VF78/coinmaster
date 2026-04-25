# ACTIVE_TASK

Updated: 2026-04-25 22:53 Europe/Madrid
Status: COMPLETE / GitHub issue #61 closed and Project #2 updated
GitHub Project: https://github.com/users/VF78/projects/2
Completed item: #61 [ARCH-01] Trading Rules target upgrade: SignalQualityContext, regime filters, RR gate, fail-safe entries
Completed issue: https://github.com/VF78/coinmaster/issues/61
Canonical root: /root/.openclaw/workspace/coinmaster/coinmaster
Branch / pushed commit: main / 95d5a17 Implement Trading Rules signal quality context

Owner instruction:
- Clean Project #2, keep #61-#64 only, put #61 In Progress.
- Implement #61 by protocol on Claude Opus 4.6 first; fallback Codex 5.5 only if needed.
- Review coding-agent output architecturally; remove hacks/workarounds/overengineering; continue slice-by-slice without waiting until #61 is complete.
- Find the GitHub token in secrets/credentials and connect to GitHub Project for task updates.

Completed:
- Found valid GitHub token in the repository remote credentials without printing the secret.
- Verified GitHub auth as `VF78`.
- Pushed commit `95d5a17` to `origin/main`.
- Commented verification summary on issue #61.
- Closed issue #61.
- Updated GitHub Project #2: #61 = Done.
- Verified Project #2 now has:
  - #61 Closed / Done
  - #62 Open / Todo
  - #63 Open / Todo
  - #64 Open / Todo

Implemented for #61:
- New pure `src/core/signalQualityContext.ts` with deterministic TypeScript EMA/ATR/ADX, regime assessment, displacement/FVG impulse quality, expected RR, and combined verdict.
- Live Engulfing/FVG monitors call the quality gate before unified `handoffStrategyEntrySignal`.
- Backtest parity: backtest uses the same evaluator and FVG impulse triple handling.
- FVG latest-closed-candle lag fixed; invariant added so latest supplied closed candle can complete a zone.
- `engulfingGate` changed from fail-open to fail-safe for new non-reduce-only entries, with explicit audited override `tradingRulesGateOverride: true`.
- Live regime candle fetch failures block entries when quality gate is active.
- Live RR gate no longer invents fallback TP/SL; if runtime TP/SL defaults unavailable, RR evaluates as 0.
- UI exposes exactly the eight approved Stage-1 fields: `regimeTf`, `adxMin`, `minImpulseAtr`, `minExpectedRr`, `timeStopBars`, `riskPerTradePct`, `eventLockoutMinutes`, `portfolioGrossCap`.
- `regimeTf` constrained to owner-approved HTF values (`1h` / `4h`) in normalization and UI.
- `riskPerTradePct` wired into allocation sizing as opt-in (`0` default), capping notional by risk budget / SL distance.
- `portfolioGrossCap` live guard added for auto-sized entry flows, auto-confirmed entries, and pending confirmations.
- `timeStopBars` implemented in backtest and live TP-fill monitor: no TP1 follow-through after N entry-TF bars closes remaining position via reduce-only IOC, cancels managed TP/SL, and notifies `time_stop`.
- `eventLockoutMinutes` wired to real existing AlphaRadar observations: fresh `macroShock` / `macro-shock` / high-urgency macro observations block Trading Rules auto entries. No fake state introduced.
- No external trading engines added; no TA-Lib/Python dependency in live path.

Final verification before push:
- `git diff --check` passed for clean code/doc set excluding runtime noise.
- `npm run check` passed.
- `npm run invariants:trading-rules` passed: 61/61.
- `npm run invariants:signal-quality` passed: 32/32.
- `npm run invariants:fvg` passed: 18/18.
- `npm run invariants:engulfing` passed: 38/38.
- `npm run build` passed (`vite build`).

Runtime noise still intentionally uncommitted:
- `coinmaster/data/db.json`
- `prod-backups/dbshape_v1-pre-legacy-cleanup-20260424-160348.json`

Next available task by Project order:
- #62 [ARCH-02] Radar evidence/ingestion upgrade: feedparser, provenance, EvidenceBundle, NLP, dedupe, factor score
