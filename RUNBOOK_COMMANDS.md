# CoinMaster VPS Bot — Commands Cheat Sheet

Target VPS: `coinmaster24.com` → `46.225.133.161`
User: `coinmaster`

> Note: Telegram bot will only respond in **DM** (groupPolicy is disabled) and only from allowlisted IDs.

## 0) SSH connect
```bash
ssh coinmaster@46.225.133.161
```

## 1) OpenClaw status / health
```bash
openclaw status --all
openclaw gateway status
openclaw health
```

## 2) Start/stop/restart the bot (OpenClaw gateway service)
```bash
systemctl --user start openclaw-gateway.service
systemctl --user stop openclaw-gateway.service
systemctl --user restart openclaw-gateway.service
systemctl --user is-active openclaw-gateway.service
systemctl --user status openclaw-gateway.service --no-pager
```

Logs:
```bash
journalctl --user -u openclaw-gateway.service -n 200 --no-pager
journalctl --user -u openclaw-gateway.service -f
```

## 3) Telegram enable/disable (then restart gateway)
Enable:
```bash
openclaw config set channels.telegram.enabled true
openclaw config set plugins.entries.telegram.enabled true
systemctl --user restart openclaw-gateway.service
```

Disable:
```bash
openclaw config set channels.telegram.enabled false
openclaw config set plugins.entries.telegram.enabled false
systemctl --user restart openclaw-gateway.service
```

Check allowlist:
```bash
openclaw config get channels.telegram.allowFrom --json
```

Outbound test:
```bash
openclaw message send --channel telegram --target 96211907 --message "ping from VPS"
```

**If inbound DMs do not arrive (polling stuck): IPv6 egress to `api.telegram.org` may be broken on the VPS.**

Quick check:
```bash
dig +short api.telegram.org A
curl -4 -I https://api.telegram.org | head -n 1
curl -6 -I https://api.telegram.org | head -n 1 || true
```

Fix (force IPv4 via `/etc/hosts`, then restart gateway):
```bash
printf "%s\n" \
  "# OpenClaw: force Telegram Bot API to IPv4 (IPv6 egress broken)" \
  "149.154.166.110 api.telegram.org" \
| sudo tee -a /etc/hosts >/dev/null

systemctl --user restart openclaw-gateway.service
```

## 4) Models / failover
Current config:
```bash
openclaw models status --json | head
```

Live probe (calls providers):
```bash
openclaw models status --probe --json | head
```

## 5) Startup self-check (sends “готов/не готов”)
```bash
/home/coinmaster/openclaw-workspace/scripts/openclaw_startup_selfcheck.sh
```
Force re-run (remove cooldown marker):
```bash
rm -f ~/.openclaw/startup-selfcheck.last
/home/coinmaster/openclaw-workspace/scripts/openclaw_startup_selfcheck.sh
```

## 6) CoinMaster API health (trading app)
```bash
curl -sS http://127.0.0.1:8787/api/health
sudo systemctl status coinmaster --no-pager
sudo systemctl restart coinmaster
```

## 7) Secrets locations (permissions should be 600)
```bash
ls -la ~/.secrets
# telegram token file:
ls -la ~/.secrets/telegram_bot_token.txt
# github pat:
ls -la ~/.secrets/github_pat.txt
```

## 8) Cron jobs (VPS)
```bash
# View current cron
crontab -l

# Daily truth save: 23:55 Madrid time
# Weekly report trigger: Sundays 20:00 Madrid time
# Log: /tmp/openclaw-cron.log
```

## 9) Mac (reserve) — how to stop
Recommended (cold reserve):
```bash
openclaw gateway stop
openclaw gateway status
```

And ensure Telegram disabled on Mac:
```bash
openclaw config set channels.telegram.enabled false
openclaw config set plugins.entries.telegram.enabled false
openclaw gateway restart
```
