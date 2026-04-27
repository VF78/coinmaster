# ACTIVE_TASK

Updated: 2026-04-27 10:55 Europe/Madrid
Status: ACTIVE / #65 native Freqtrade Stage 1 is deployed in dry-run; reset handoff prepared
GitHub Project item: #65 `Этап 1: Полный переход CoinMaster на native Freqtrade core` — In Progress
Canonical root: /root/.openclaw/workspace/coinmaster (app: /root/.openclaw/workspace/coinmaster/coinmaster)
Branch / HEAD / origin/main / deploy commit / divergence: freqtrade-stage1-migration / committed + pushed reset handoff package / origin/main f6f2279cd10eb97223d20cbf958a6c4e2f93737a / deploy marker refreshed during final reset prep; verify with `/opt/coinmaster/.deploy-source-commit` / origin/main...HEAD about 15 commits ahead
Goal: finish Freqtrade Stage 1 dry-run validation and prepare explicit owner-approved live cutover.
Done:
- Freqtrade strategy now runs base 5m with informative 15m/1h/4h; entry TFs, HTF FVG sweep/first-touch/confirmation, and regime TF are implemented natively.
- Opposite Engulfing exit removed from UI/Freqtrade path; Signal Quality / Portfolio Guards toggles cleaned up.
- Dry-run deployed and running via Freqtrade; current whitelist BTC/ETH/HYPE, allocations 33.3333/33.3333/33.3334.
- Coin Distribution now mirrors active Freqtrade whitelist only; allocation % sets target margin stake in `custom_stake_amount()` (not just a display or proposed-stake cap).
- Overnight candidate evidence moved out of repo to `/var/log/coinmaster/reports/freqtrade-nightly-20260427/`; final ETH/HYPE candidate had 42 trades, +39.36%, DD 15.28%.
- Deploy protocol/runbooks/systemd units updated for actual prod layout `/opt/coinmaster/freqtrade`; cron watchdog installed at `/etc/cron.d/coinmaster-freqtrade-night-watch`.
Next exact step: after reset, run live preflight (`git status`, HEAD, divergence, deploy marker, Freqtrade API `/show_config`/`/status`/`/locks`, watchdog status), then observe dry-run until fresh signals/trades appear; update #65 and only prepare live cutover after owner approval.
Checks / commit / deploy / push: latest checks before handoff passed (`py_compile`, `npm run check`, `npm run build`); handoff package committed and pushed to `origin/freqtrade-stage1-migration`; production deploy rerun after commit; Freqtrade service restarted and dry-run API/watchdog verified healthy.
Blockers / risks: live is not approved; need fresh dry-run trades/signals; one earlier Hyperliquid WS close event self-recovered and recent logs were clean; private Freqtrade config must stay ignored and never be printed/committed.
Key files: coinmaster/freqtrade/user_data/strategies/CoinMasterStrategy.py; coinmaster/src/web/pages/TradingRulesPage.tsx; coinmaster/scripts/deploy-prod-safe.sh; coinmaster/scripts/freqtrade-night-watch.sh; coinmaster/RUNBOOK_COMMANDS.md; coinmaster/freqtrade/RUNBOOK_VPS.md.
