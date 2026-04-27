# ACTIVE_TASK

Updated: 2026-04-27 12:31 Europe/Madrid
Status: ACTIVE / #65 native Freqtrade Stage 1 dry-run plus #67 Freqtrade-native Radar policy bridge implementation in progress
GitHub Project item: #65 `Этап 1: Полный переход CoinMaster на native Freqtrade core` — In Progress
Canonical root: /root/.openclaw/workspace/coinmaster (app: /root/.openclaw/workspace/coinmaster/coinmaster)
Branch / HEAD / origin/main / deploy commit / divergence: freqtrade-stage1-migration / committed+pushed / origin/main f6f2279cd10eb97223d20cbf958a6c4e2f93737a / deploy marker refreshed after Telegram/Freqtrade persistence work; verify with `/opt/coinmaster/.deploy-source-commit` / origin/main...HEAD about 19+ commits ahead
Goal: finish Freqtrade Stage 1 dry-run validation, implement neutral-by-default #67 Radar policy bridge in Freqtrade architecture, and prepare explicit owner-approved live cutover.
Done:
- #67/#68 project subtasks updated: accepted local JSON snapshot + atomic write + hot-read, institutional-style hard block/off/direction/multiplier rules, and GUI Radar explainability follow-up.
- Freqtrade Strategy now has neutral-by-default Radar policy reader/cache implemented locally; stale/missing/invalid policy is ignored, global/pair/direction blocks are guarded, and risk_multiplier is clamped 0..1 and applied after existing caps. Not yet deployed at this checkpoint.
- Freqtrade Telegram enabled with full notification_settings on using the existing CoinMaster Telegram bot; legacy CoinMaster getUpdates polling disabled by default to avoid Telegram polling conflict, while send-only app notifications remain configured.
- Freqtrade dry-run DB pinned to persistent `/freqtrade/user_data/tradesv3.dryrun.sqlite`; deploy script preserves `user_data/*.sqlite*` across safe deploy swaps.
- Freqtrade strategy now runs base 5m with informative 15m/1h/4h; entry TFs, HTF FVG sweep/first-touch/confirmation, and regime TF are implemented natively.
- Opposite Engulfing exit removed from UI/Freqtrade path; Signal Quality / Portfolio Guards toggles cleaned up.
- Dry-run deployed and running via Freqtrade; current whitelist BTC/ETH/HYPE, allocations BTC 34%, ETH 33%, HYPE 33%.
- Coin Distribution now mirrors active Freqtrade whitelist only; allocation % is normalized to whole integers summing to 100 and sets target margin stake in `custom_stake_amount()` (not just a display or proposed-stake cap).
- Overnight candidate evidence moved out of repo to `/var/log/coinmaster/reports/freqtrade-nightly-20260427/`; final ETH/HYPE candidate had 42 trades, +39.36%, DD 15.28%.
- Deploy protocol/runbooks/systemd units updated for actual prod layout `/opt/coinmaster/freqtrade`; cron watchdog installed at `/etc/cron.d/coinmaster-freqtrade-night-watch`.
Next exact step: run full checks for Radar bridge, commit/push/deploy neutral bridge, restart Freqtrade dry-run, verify no behavior change without policy file; then continue observing dry-run until fresh signals/trades appear.
Checks / commit / deploy / push: before Radar bridge, latest checks passed (`npm run check`, `npm run invariants:trading-rules`, `npm run build`, deploy script `bash -n`); changes committed+pushed to `origin/freqtrade-stage1-migration`; production deploy rerun after commit; Freqtrade service restarted, dry-run started, API verified healthy (`dry_run=true`, `state=running`, Telegram RPC listening, no locks/trades). Radar bridge local checks so far: `python3 -m py_compile CoinMasterStrategy.py`, docker `invariants_radar_policy.py` 9/9 passed.
Blockers / risks: live is not approved; need fresh dry-run trades/signals; one earlier Hyperliquid WS close event self-recovered and recent logs were clean; private Freqtrade config must stay ignored and never be printed/committed.
Key files: coinmaster/freqtrade/user_data/strategies/CoinMasterStrategy.py; coinmaster/src/web/pages/TradingRulesPage.tsx; coinmaster/scripts/deploy-prod-safe.sh; coinmaster/scripts/freqtrade-night-watch.sh; coinmaster/RUNBOOK_COMMANDS.md; coinmaster/freqtrade/RUNBOOK_VPS.md.
