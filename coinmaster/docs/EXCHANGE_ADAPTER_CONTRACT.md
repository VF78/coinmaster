# Exchange Adapter Contract (v1)

## Goal
Keep strategy, risk, replay, and execution orchestration exchange-agnostic.

## Core principle
Domain layer works with normalized models only; each exchange implements the same adapter interface.

## Interface (conceptual)
- `getMids()`
- `getCandles(symbol, timeframe, from, to)`
- `getInstrumentMeta(symbol)`
- `getAccountState()`
- `getOpenOrders(symbol?)`
- `getOpenPositions(symbol?)`
- `getFills(symbol?, from?)`
- `placeLimitOrder(intent)`
- `cancelOrder(exchangeOrderId | clientOrderId)`
- `cancelAll(symbol)`
- `placeReduceOnlyExit(intent)`
- `setLeverage(symbol, value)`

## Normalized domain DTOs
- `Candle`, `Tick`, `InstrumentMeta`
- `OrderIntent`, `OrderAck`, `OrderStatus`
- `PositionSnapshot`, `FillEvent`, `AccountSnapshot`

## Safety and reliability requirements (for every adapter)
- idempotency key (`clientOrderId` / `cloid` equivalent)
- retry + dedupe policy
- deterministic error mapping (network / auth / validation / risk)
- append-only audit event for every API call and order lifecycle event

## Capability flags
Each adapter declares features, e.g.:
- supports reduce-only
- supports cancel-replace
- supports websocket execution reports
- supports unified margin

Execution layer uses capability flags instead of exchange-specific if/else.

## Symbol and precision mapping
Each adapter owns symbol normalization and exchange precision rules.
Domain logic must never hardcode exchange symbol formats.

## Initial adapters plan
1. `HyperliquidAdapter` (first production target)
2. `BybitAdapter` (next)
3. `BinanceAdapter` (next)

All adapters must pass same integration test suite for order lifecycle and audit consistency.
