# Architecture (MVP -> Production-ready -> SaaS)

## 1) Current MVP boundaries
- `src/core/*`: domain logic (strategy adapter, simulation, stats, risk handling).
- `src/server/*`: API + orchestration + market ingest.
- `src/web/*`: React UI only.
- `data/db.json`: temporary local persistence (to be replaced by Postgres).

## 2) Confirmed target topology
- **Web (UI): Vercel**
- **API + workers + DB: Hetzner VPS**
- Initial mode: single-operator, no public user registration yet.

## 3) Near-term production-ready scope (7-10 days)
- Paper/live-capable backend with manual confirmation control.
- Realtime ingest (WS + fallback) with health checks and restart policies.
- Persistent DB (PostgreSQL) instead of local JSON.
- Append-only trade event log for exact audit/P&L reconstruction.
- Clear runbook for start/stop/recovery.

## 4) Strategy execution semantics (locked)
- Signal trigger on 5m/15m engulfing+sweep logic.
- **Replay and analysis execution:** entry only on close of engulfing candle.
- **Live initial execution policy:** limit order at engulfing candle close level.

## 5) Security architecture baseline (exchange-API system)

### Key management
- Single-operator phase: API keys in VPS `.env` allowed.
- Strict file permissions (`chmod 600`, owner-only), no keys in logs or repos.
- Planned migration path: secret manager/KMS when scaling.

### Access control
- Principle of least privilege for exchange API key (trade-only scope required, no unnecessary permissions).
- Service account separation (app runtime vs admin shell).
- 2FA on exchange + operator accounts.

### Network and host hardening
- Public exposure minimized (only required ports/services).
- Reverse-proxy/TLS in front of API if externally exposed.
- Fail2ban/firewall baseline and regular security updates on VPS.

### Trading safety controls
- Hard daily drawdown stop.
- Position/risk caps and leverage guards.
- Kill-switch and manual emergency stop path.
- Idempotent order handling + retry with dedupe keys.

### Audit and observability
- Append-only trade-event journal (signal/open/partial/close/cancel/override).
- Structured logs + correlation ids for each order lifecycle.
- Metrics/alerts for stale feeds, order failures, and risk-limit breaches.

### Resilience and availability
- Single VPS now (cost-efficient MVP), but architecture ready for HA evolution.
- Future 99.99 path: multi-node API, managed HA DB, redundant market-feed workers.

## 6) SaaS evolution path
1. Introduce auth boundary (`userId`, sessions/JWT).
2. Add tenant boundary (`tenantId` across entities + scoped repositories).
3. Add plan/entitlement middleware.
4. Horizontal scale of API/workers + managed HA data layer.
5. Reuse shared contracts for native iOS/Android clients.
