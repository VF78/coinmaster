# Runbook: MEX-RO / Bybit read-only telemetry

Дата: 2026-03-10  
Статус: operational baseline

## Scope

Этот runbook покрывает:
- настройки Bybit read-only telemetry,
- безопасную проверку API/UX,
- smoke-проверки перед деплоем и после рестарта,
- rollback без влияния на execution path.

## Safety envelope

- MEX-RO **не должен** отправлять ордера.
- Допустимые режимы для телеметрии: `off`, `read_only`.
- При сбое коннектора основная торговая логика Coinmaster должна продолжать работу.
- Секреты в API-ответах возвращаются только в masked-виде.

## Pre-deploy checks

```bash
cd coinmaster/coinmaster
npm run check
npm run invariants:read-only-exchanges
npm run build
```

## API smoke

Если owner auth включён:

```bash
export API_BASE_URL="http://127.0.0.1:8787"
export OWNER_AUTH_TOKEN="<token>"
npm run ops:smoke
```

Ручные проверки:

```bash
curl -sS -H "Authorization: Bearer $OWNER_AUTH_TOKEN" \
  "$API_BASE_URL/api/settings/read-only-exchanges" | jq .

curl -sS -X POST -H "Authorization: Bearer $OWNER_AUTH_TOKEN" \
  "$API_BASE_URL/api/settings/read-only-exchanges/bybit/test" | jq .
```

Ожидаемо:
- `ok=true`
- в `status.exchange` → `bybit`
- при выключенном/неполном конфиге допустим `connected=false`
- секреты не возвращаются целиком

## UI smoke

В `Settings`:
- карточка **Bybit (Read-only telemetry)** отображается
- режим переключается между `Off` и `Read-only`
- placeholders для ключей masked
- `Test connection` не ломает страницу при `connected=false`

В `History`:
- фильтр `Bybit only` доступен
- записи из внешней биржи имеют `sourceExchange=bybit`

## Deploy / restart sequence

1. Снять `git status`
2. `npm run check`
3. `npm run invariants:read-only-exchanges`
4. `npm run build`
5. Перезапустить сервис
6. Выполнить `npm run ops:smoke`
7. Проверить `/api/live/status` и `/api/settings/read-only-exchanges`

## Rollback

Если MEX-RO ведёт себя нестабильно:

1. В UI/API перевести Bybit в `mode=off`
2. Перезапустить сервис только если нужна очистка runtime state
3. Если проблема в коде текущего релиза — откатить commit и повторить smoke

Rollback-критерий:
- dashboard / live status / trading endpoints снова зелёные
- Bybit connector больше не участвует в сборе внешних fills

## Evidence to attach in release note

- вывод `npm run invariants:read-only-exchanges`
- вывод `npm run ops:smoke`
- JSON ответа `/api/settings/read-only-exchanges/bybit/test` (с masked secrets)
