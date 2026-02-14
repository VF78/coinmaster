# CoinMaster Status

Updated: 2026-02-14 18:22 Europe/Madrid

## Current focus (Sprint 1-2 days)
1) Production baseline on Hetzner VPS (P0 only)
2) Hyperliquid private command layer + controlled live execution path
3) Safety wrappers + manual confirmation in live flow

## This hour
- Подключены Hyperliquid credentials на VPS (`/opt/coinmaster/.env`, perms 600), connectivity подтверждена.
- Расширен adapter Hyperliquid: account state, open orders/positions/fills, place/cancel/cancel-all/reduce-only, leverage setup.
- Добавлены live endpoints в API (`/api/live/status`, `/api/live/order/*`, `/api/live/leverage`) с режимом manual confirmation.
- В дашборд выведены реальные данные аккаунта: equity/available/open positions + текущая открытая сделка; в строке сделки добавлено плечо.
- Уточнён Source: `sim` теперь явно отображается как `paper(sim)`.

## What was tested
- Local: `npm run check`, `npm run build`, API smoke.
- VPS: `npm ci`, `npm run check`, `systemctl restart coinmaster`, `GET /api/dashboard` и `GET /api/health`.
- Live data smoke: dashboard API возвращает `live.connected=true`, account summary и open position с leverage.

## Blockers / help needed
- Нужно подтвердить действие по уже открытой live-позиции (на аккаунте фактическое плечо сейчас выше стартового лимита 10x).

## Next hour target
- Финализировать P0 runbook и HTTPS baseline, затем сделать dry controlled live order-flow (manual confirm ON, лимит 30 USDC/10x) и отправить отчёт на приёмку.
