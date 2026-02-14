# CoinMaster Status

Updated: 2026-02-14 17:19 Europe/Madrid

## Current focus (Sprint 1-2 days)
1) Production baseline on Hetzner VPS (no replay detour)
2) Hyperliquid account connectivity for controlled live test (small size)
3) Safety wrappers + manual confirmation in live flow

## This hour
- По решению Владимира сменён приоритет: historical replay поставлен на паузу, активная задача в проекте переведена на production baseline.
- Пересобран project plan в логике "launch-critical first": всё вторичное (статистика/доработки) уходит в post-launch backlog.
- GitHub Project синхронизирован: issue #1 (append-only trade event log) закрыт как выполненный; issue #6 выставлен `In Progress`.
- На VPS установлен Docker Compose v2 (`docker compose` доступен), проверен текущий runtime (coinmaster service active).
- Усилен операционный процесс: hourly Telegram-апдейт с обязательными блоками «что сделано / что протестировано / следующий шаг», после завершения — отдельный апдейт + demo/приёмка + перевод следующей задачи в In Progress.

## Blockers / help needed
- Для подключения live-аккаунта Hyperliquid нужен только доступ к trading credentials (лимиты старта подтверждены: 30 USDC max notional, до 10x, manual confirmation ON).

## Next hour target
- Подготовить production runbook на VPS (Docker/Compose + health/restart + HTTPS baseline) и начать интеграцию private Hyperliquid command layer под controlled live launch.
