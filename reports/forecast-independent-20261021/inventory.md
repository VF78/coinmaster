# Independent forecasting: data and reuse inventory

Read-only inventory at canonical HEAD `cf83b9987757eb2d6ab1d846a7a59f6be2711912`. No fetch, labels, fit, source change, install or economic engine.

- BTCUSDT/SOLUSDT Bybit linear execution and mark minute streams: each 1,051,200 rows, exact contiguous [2024-09-01,2026-09-01), all normalized SHA match. Timestamp columns checked; raw pages not rescanned.
- Missing minute tail: [2026-09-01,2026-10-21), 50 days = 72,000 rows per symbol/stream. Expected 72 public API pages per stream, 144 execution-only or 288 including mark. Availability is unverified until fetch.
- Genuine hourly warmup: [2024-06-01,2024-09-01), 2,208 bars per asset; CSV timestamps and hashes verified. Daily base starts 2022-09-02. No genuine minute/15m warmup before 2024-09-01 in inspected inputs.
- Protected pilot has public daily candles through 20 October, 1,510 contiguous daily bars per asset. Its manifest is a candidate reuse source only; no protected files copied or modified. Old runtime Sept23 alias is broken.
- Base funding BTC 4,380 rows (8h); SOL 4,740 rows includes 480 two-hour steps. No complete normalized tail established; do not infer cash funding or uniform SOL frequency.
- Available 2,764,795,904 disk bytes, 982,564,864 available memory bytes, two logical CPUs; swap almost full. Start with one CPU, zero swap, 400MiB cap and fresh preflight; CNN viability at that cap remains unproven.
- All four model libraries already installed. Parquet lives in runtime/.venv, absent isolated scientific env; use separate preparation without installing packages.
- Existing complete-group causal UTC aggregation and mmap model scaffolding can be reused. Old labels, six-panel/three-class interfaces and train splits cannot implement the new task unchanged. Freeze independent entry, three TP/SL targets, dual-hit ambiguity, horizon/censoring/purge, calibration and sampling before implementation.

Full exact counts, reusable function surfaces, API links and blockers: `inventory.json`. Pilot verified PID 2009732, restart count zero, active.

## Authorized execution tail update

Public fetch COMPLETE: 72,000 actual rows per asset, 144 raw pages total, zero response errors/gaps/duplicates, closed before every response server time. New isolated `runtime/var/research-datasets/forecast-independent-20261021-v1/execution-tail/manifest.json` SHA `010126bf0632ef03f5ea42449aa76420c8ab8629b8f0833d7e1941b6088b7a71`. Independent CSV timestamp/hash/server-time check: `tail-verification.json`. Joined base+tail has 1,123,200 minutes per asset through 20 October; old data/pilot unchanged. No mark/funding fetch, labels or model fit.
