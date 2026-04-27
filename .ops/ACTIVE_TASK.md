# ACTIVE_TASK

Updated: 2026-04-27 13:10 Europe/Madrid
Status: ACTIVE / #65 native Freqtrade Stage 1 dry-run plus #67/#68 Freqtrade-native Radar producer + policy GUI deployed to dry-run
GitHub Project item: #65 `Этап 1: Полный переход CoinMaster на native Freqtrade core` — In Progress
Canonical root: /root/.openclaw/workspace/coinmaster (app: /root/.openclaw/workspace/coinmaster/coinmaster)
Branch / HEAD / origin/main / deploy commit / divergence: freqtrade-stage1-migration / 1e3f703330a37972ad3244bf4ba8d93029ce432a committed+pushed / origin/main f6f2279cd10eb97223d20cbf958a6c4e2f93737a / deploy marker 1e3f703330a37972ad3244bf4ba8d93029ce432a / origin/main...HEAD ahead
Goal: finish Freqtrade Stage 1 dry-run validation, keep Freqtrade as sole execution core, use Freqtrade-native Radar only as a policy/context layer, and prepare explicit owner-approved live cutover.
Done:
- #67 Freqtrade-native Radar producer implemented/deployed. It reuses old Alpha Radar primitives where safe (connectors/parsers/evidence/candidate scoring) as upstream context, but does not reuse the old runtime/execution loop.
- New producer maps Radar context policy book into `/var/lib/coinmaster/freqtrade/radar_policy.json` using atomic writes. Strategy hot-reads this snapshot from `/freqtrade/user_data/runtime/radar_policy.json`.
- Missing/expired/unmonitored/missing-evidence policies are neutral/ignored; no accidental freeze. Pair decisions export `mode`, `risk_multiplier`, reason codes, evidence IDs, candidate IDs, and source policy IDs. `risk_multiplier` remains capped 0..1 and only reduces exposure.
- #68 first GUI/API slice implemented: custom Radar page shows producer status, updated/valid times, global guard, pair decisions, risk multipliers, reasons/reason codes, candidate IDs, diagnostics, and disk read errors. Added `GET /api/freqtrade/radar-policy` and `POST /api/freqtrade/radar-policy/refresh`.
- Freqtrade Strategy Radar bridge remains native and neutral-safe: stale/missing/invalid policy is ignored, global/pair/direction blocks are guarded, and multiplier is applied after existing caps.
- Freqtrade Telegram enabled with full notification_settings using existing CoinMaster Telegram bot; legacy CoinMaster getUpdates polling disabled by default to avoid Telegram polling conflict.
- Freqtrade dry-run DB pinned to persistent `/freqtrade/user_data/tradesv3.dryrun.sqlite`; deploy script preserves `user_data/*.sqlite*` across safe deploy swaps.
- Freqtrade strategy runs base 5m with informative 15m/1h/4h; entry TFs, HTF FVG sweep/first-touch/confirmation, and regime TF are implemented natively.
- Dry-run deployed and running via Freqtrade; current whitelist BTC/ETH/HYPE, allocations BTC 34%, ETH 33%, HYPE 33%.
- Coin Distribution mirrors active Freqtrade whitelist only; allocation % is normalized to whole integers summing to 100 and sets target margin stake in `custom_stake_amount()`.
- Deploy protocol/runbooks/systemd units updated for actual prod layout `/opt/coinmaster/freqtrade`; cron watchdog installed at `/etc/cron.d/coinmaster-freqtrade-night-watch`.
Current prod Radar policy: active file exists at `/var/lib/coinmaster/freqtrade/radar_policy.json`; latest observed snapshot has 3 pair overrides (BTC long_only x1.00, ETH both x0.99, HYPE long_only x0.89), global open/neutral, valid short TTL.
Next exact step: continue dry-run observation until fresh Freqtrade dry signals/trades appear; then evaluate whether Radar policy improved filtering/ROI and tune deterministic thresholds. Radar quality bar from Vladimir: preserve/improve old Radar signal quality using accumulated experience + institutional best practices, but simplify logic and keep it transparent; avoid dozens of tunable parameters. Add a Radar work-funnel visualization on the Radar page showing collection/evidence/candidate/policy/Freqtrade-decision flow and why items were filtered. Keep live disabled until Vladimir explicitly approves.
Checks / commit / deploy / push: Producer checks passed (`npm run invariants:freqtrade-radar-policy` 16/16, `npm run invariants:radar-context-policy` 14/14, `npm run check`, `npm run build`, `git diff --check`, lightweight secret scan); commit 1e3f703 pushed; production deploy successful; app `/api/health` OK; Freqtrade API verified `dry_run=true`, `state=running`, `runmode=dry_run`, `trading_mode=futures`, `margin_mode=cross`, `timeframe=5m`, no locks/open trades, trade_count 0.
Blockers / risks: live is not approved; need fresh dry-run trades/signals; GitHub issue comment update via CLI/API was blocked by unavailable GitHub token in the environment; private Freqtrade config must stay ignored and never be printed/committed.
Key files: coinmaster/src/server/freqtradeRadarPolicy.ts; coinmaster/src/server/index.ts; coinmaster/src/web/CustomApp.tsx; coinmaster/src/web/lib/api.ts; coinmaster/scripts/invariants-freqtrade-radar-policy.ts; coinmaster/freqtrade/user_data/strategies/CoinMasterStrategy.py; coinmaster/freqtrade/RUNBOOK_VPS.md.
