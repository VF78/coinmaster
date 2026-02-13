# Architecture (MVP → SaaS)

## Current MVP boundaries
- `src/core/*`: pure domain logic (types, strategy adapter seam, simulation, stats, bias command handling).
- `src/server/*`: API and orchestration, persistence wiring.
- `src/web/*`: React UI only, no trading rules embedded.
- `data/db.json`: local JSON persistence (can swap to SQLite/Postgres via repository adapter).

## SaaS evolution plan
1. **Auth boundary**
   - Add `identity` module (JWT/session provider).
   - Inject `userId` into all API requests.
2. **Multi-tenant boundary**
   - Introduce `tenantId` on all entities (`Position`, `TradeLog`, `BiasCommand`).
   - Repository interface enforces tenant-scoped reads/writes.
3. **Billing-ready boundary**
   - Add `subscription` module with plan entitlements (max symbols, backtest frequency, API rate).
   - Enforce in API middleware before core operations.
4. **Data layer migration**
   - Replace JSON DB with SQLite/Postgres via repository implementation while keeping `core` unchanged.
5. **Native apps**
   - Reuse `core` package as shared TypeScript domain layer.
   - Keep UI and API as adapters; React Native can call same API + potentially embed shared validation logic.

## Strategy hook path to `backtest_v1`
- MVP uses `BacktestV1SignalAdapter` stub seam (`src/core/strategyAdapter.ts`).
- Next: add Python bridge (`signals.py` runner) and normalize outputs to `StrategySignal`.
- Keep adapter as anti-corruption layer so UI/API do not depend on Python internals.
