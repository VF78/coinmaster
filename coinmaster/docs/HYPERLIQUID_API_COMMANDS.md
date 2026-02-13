# Hyperliquid API Commands — v1 Scope

## Цель
Реализовать полный минимально-необходимый набор команд для production-ready запуска BTC-контура (paper + live-ready с ручным подтверждением).

## 1) Public / market data commands (info)
1. `allMids` — текущие mid цены (уже используется).
2. Исторические свечи для TF: `1m / 5m / 15m / 1h / 4h`.
3. Метаданные инструмента (precision, min size, tick size, limits).
4. (Опционально) L2/mark/funding для расширенных фильтров.

## 2) Private / account commands
1. Account state (баланс, margin/equity, risk snapshot).
2. Open orders.
3. Open positions.
4. User fills / execution history.
5. Funding/fee history (для точного P&L отчёта).

## 3) Trading commands (exchange)
1. Place order (v1: LIMIT по close свечи-поглощения).
2. Cancel order by id/cloid.
3. Cancel all orders for symbol.
4. Reduce-only exit order.
5. Leverage/margin mode setup (в рамках agreed risk rules).
6. Cancel-replace (если нет native modify для нужного кейса).

## 4) Safety wrappers (обязательные)
1. `dryRun` / `live` switch на уровне execution adapter.
2. Idempotency key (`cloid`) для каждого ордера.
3. Retry policy с backoff и дедупликацией.
4. Pre-trade risk gates: daily DD stop, leverage cap, size cap.
5. Kill-switch: мгновенная блокировка новых ордеров.

## 5) Audit & observability (обязательные)
Каждая API-команда должна записывать append-only event:
- timestamp (UTC)
- symbol
- action
- request payload hash/summary
- response status
- exchange order id / cloid
- correlation id strategy-run

## 6) Acceptance criteria v1
1. Все команды из секций 1–3 доступны через единый `HyperliquidClient` + `ExecutionService`.
2. Ошибки и ретраи детерминированно логируются.
3. По каждому ордеру можно восстановить lifecycle end-to-end.
4. Replay и live используют общие risk/MM правила (разница только в execution adapter).
5. В live mode первое исполнение: **LIMIT по close свечи-поглощения**.
