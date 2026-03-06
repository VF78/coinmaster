# Multi-Exchange Read-Only Ingestion Architecture (Bybit first)

Date: 2026-03-06  
Author: Coinmaster

## Goal

Add Bybit account connection in **Settings** with explicit **read-only mode** and ingest its trading/account data for a complete daily AI analysis picture.

Critical constraint: do this through a universal architecture so future exchanges (Binance, OKX, etc.) are plug-ins, not refactors.

---

## Non-goals (this phase)

- No order placement/cancel/modify on Bybit.
- No replacing existing Hyperliquid execution engine.
- No cross-exchange position netting engine.

---

## Target architecture

### 1) Separate execution exchange from read-only external exchanges

Keep current `exchange` adapter (Hyperliquid) as **execution source**.
Add a new integration layer for **external read-only sources**.

- Execution exchange (existing): trading-critical, order flow.
- External read-only exchanges (new): telemetry/analytics only.

This avoids coupling risk-sensitive execution with optional telemetry connectors.

### 2) Connector contract (universal)

Create `src/integrations/readOnlyExchanges/types.ts`:

- `ReadOnlyExchangeId` (`bybit` now, extensible)
- `ReadOnlyMode` (`off | read_only`)
- `ReadOnlyExchangeConfig` (api key/secret + flags)
- `ReadOnlyExchangeStatus` (configured/connected/error/lastSync)
- `ReadOnlyTradeFill` (normalized trade/fill record)
- `ReadOnlyAccountSnapshot` (equity/available/etc. optional)
- `ReadOnlyExchangeConnector` interface:
  - `id`
  - `validateConfig(config)`
  - `getStatus(config)`
  - `getRecentFills(config, sinceMs)`
  - `getAccountSnapshot(config)` (optional)

Future exchanges only implement this interface + register in registry.

### 3) Connector registry + service

Create:

- `src/integrations/readOnlyExchanges/bybitReadOnlyConnector.ts`
- `src/integrations/readOnlyExchanges/registry.ts`
- `src/integrations/readOnlyExchanges/service.ts`

`service.ts` responsibilities:
- Load enabled connectors from app settings.
- Query status/fills with timeout and per-connector error isolation.
- Return merged normalized data tagged by source exchange.

This ensures one connector failure never breaks the app.

### 4) Settings model extension

Extend app settings with universal structure:

```ts
settings.readOnlyExchanges = {
  bybit: {
    mode: 'off' | 'read_only',
    apiKey: string,
    apiSecret: string,
    accountType?: 'UNIFIED' | 'CONTRACT' | 'SPOT',
    enabledCategories?: Array<'linear' | 'inverse' | 'spot' | 'option'>
  }
}
```

Notes:
- Secrets masked in API responses.
- API secret write-only in UI.
- `mode` gate guarantees no trading path exposure.

### 5) API surface

Add universal settings endpoints:

- `GET /api/settings/read-only-exchanges`
- `PUT /api/settings/read-only-exchanges/:exchangeId`
- `POST /api/settings/read-only-exchanges/:exchangeId/test`

`/api/settings/exchange` may embed summary, but dedicated endpoints avoid bloat.

### 6) Daily analytics integration

In `buildDailyAnalyticsText()` merge:
- execution fills (existing Hyperliquid flow)
- read-only external fills (Bybit)

Output with source breakdown, e.g.:
- total fills/net
- per-source (hyperliquid/bybit)
- per-symbol contributions across sources

No execution logic changes; analytics only.

### 7) UI/UX in Settings

Add section card: **Bybit (Read-only telemetry)**

Fields:
- Mode (`Off` / `Read-only`)
- API key
- API secret (password, write-only)
- optional category toggles (default `linear`)

Actions:
- Save
- Test connection

State:
- Configured/connected status
- last error (safe message)
- masked key fingerprint

---

## Security and safety

- Hard guard: read-only connectors expose no trading methods.
- Do not store plaintext secrets in responses.
- Strict timeout + retry budget for external calls.
- Errors downgraded to connector-level warnings; no server crash.

---

## Rollout plan

1. Introduce generic model + registry + no-op service.
2. Add Bybit connector implementation.
3. Add API + settings UI card.
4. Wire daily analytics merge.
5. Add tests/smokes + deployment.

---

## Why this prevents refactor later

- New exchange = new connector file + registry entry + optional UI card config.
- Core execution engine remains untouched.
- Analytics consumes normalized connector output.
- Settings schema already exchange-agnostic.
