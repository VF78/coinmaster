# CoinMaster Status

Updated: 2026-02-14 16:13 Europe/Madrid

## Current focus (Sprint 1-2 days)
1) Deterministic historical replay engine (started)
2) Exchange-agnostic adapter layer (expand commands)
3) Postgres migration baseline
4) Hetzner deploy baseline + HTTPS runbook

## This hour
- Провёл self-diagnosis: OpenClaw status/security audit/update status, cron health, локальные `npm run check/build`.
- Подтверждён доступ к Hetzner: SSH работает через `coinmaster`, root SSH отключён по hardening (ожидаемо), sudo для `coinmaster` без пароля активен.
- Запустил replay-задачу в коде:
  - добавлен `src/core/replay.ts` (deterministic replay по close свечи),
  - расширен `runSimulationStep` (timestamp/mode для replay),
  - добавлен API `POST /api/replay/run`.
- Smoke-test replay через Hyperliquid candles выполнен успешно.

## Blockers / help needed
- Нужен confirm приоритета: сначала UI/отчёт replay, либо сразу Docker/Compose + HTTPS на VPS.

## Next hour target
- Сделать первый user-facing replay report (короткая сводка + метрики ROI/DD/winrate) и подготовить интеграцию в UI/операционный поток.
