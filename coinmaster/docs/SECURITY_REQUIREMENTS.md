# Security Requirements — Exchange API Trading System

## Goal
Define minimum security requirements for CoinMaster while it has direct/indirect access to exchange API credentials and order execution.

## A. Credentials and secrets
1. No secrets in git, logs, screenshots, or memory files.
2. Single-operator phase: secrets in VPS `.env` is acceptable.
3. `.env` permissions must be owner-only (`600`) and outside public web root.
4. API key scope must be minimal (only required trading permissions).
5. Rotation policy must be documented (manual now, scheduled later).
6. Secret-manager migration path must be prepared for multi-user scale.

## B. Authentication and operator security
1. Exchange account must have 2FA enabled.
2. Admin/server access must use strong auth (SSH keys, no password-only SSH).
3. Distinct operator/admin actions should be auditable.
4. Manual confirmation mode must remain available for production start.

## C. Host and network hardening (Hetzner VPS)
1. Minimal exposed ports only.
2. Firewall deny-by-default for inbound, allowlist required ports.
3. OS security updates enabled with controlled reboot strategy.
4. Reverse-proxy + TLS for public API endpoints.
5. Brute-force protection for SSH/API admin interfaces.

## D. Trading safety controls
1. Hard-stop daily drawdown enforcement.
2. Position sizing, leverage caps, and max-risk-per-trade checks pre-order.
3. Kill-switch to block new orders immediately.
4. Idempotent order submission and duplicate-order protection.
5. Deterministic fallback behavior on market-feed outages.

## E. Audit, logging, and forensics
1. Append-only trade-event log is mandatory.
2. Every order lifecycle step must be recorded:
   - signal_detected
   - order_submitted
   - order_acknowledged/rejected
   - partial_fills
   - exits (tp/sl/manual/reverse)
3. Timestamps in UTC + stable IDs + correlation IDs.
4. Logs must support exact P&L reconstruction and postmortem analysis.
5. Log retention and archive policy must be defined before scale.

## F. Reliability and recovery
1. Health checks for market feed, API, DB, worker loop.
2. Auto-restart policy with alerting on repeated failures.
3. Backup/restore procedure for DB and trade logs.
4. Recovery drill: restart after crash without duplicated orders.

## G. Scaling and 99.99 readiness (future)
1. Single VPS MVP is acceptable now; 99.99 not realistic on single node.
2. For 99.99 target later:
   - multi-node API/worker deployment,
   - HA DB (managed or self-managed with failover),
   - redundant feed ingestion,
   - regional redundancy if needed.

## Current decisions confirmed by user
- Web on Vercel, API+DB+workers on Hetzner.
- EN default UI, RU/ES later.
- No user registration required in first 7-10 day phase.
- Replay execution: entry only at engulfing-candle close.
- Live initial execution: limit order at engulfing-candle close level.
- `.env` key storage acceptable for now (single operator), with later secret-manager migration.
