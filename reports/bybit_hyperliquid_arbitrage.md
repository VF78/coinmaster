# Bybit ↔ Hyperliquid arbitrage analysis

- Window: 2025-08-11T04:19:00+00:00 → 2026-02-07T04:19:00+00:00 (180 days requested)
- Resolution: 1m close prices
- Strategy tested: long cheaper exchange / short more expensive exchange
- Costs modeled: fees only (no funding, no slippage, no transfer cost)
- Notes: ZEC has no Bybit USDC perp; Bybit ZECUSDT was used as the closest liquid perpetual proxy.

## Quick take
- BTC: share above ~20 bps round-trip threshold = 0.74%, max run 1922 min
- SOL: share above ~20 bps round-trip threshold = 2.49%, max run 6448 min
- HYPE: share above ~20 bps round-trip threshold = 24.76%, max run 63362 min
- ZEC: share above ~20 bps round-trip threshold = 3.36%, max run 6202 min

## BTC
- Bybit symbol: `BTCPERP`
- Hyperliquid symbol: `BTC`
- Overlap: 259,201 aligned 1m candles
- Bybit range: 2025-08-11T04:19:00+00:00 → 2026-02-07T04:19:00+00:00 (259,201 candles)
- Hyperliquid range: 2025-08-11T04:19:00+00:00 → 2026-02-07T04:19:00+00:00 (259,201 candles)
- Coverage on common span: Bybit 100.0%, Hyperliquid 100.0%
- Directional bias: Bybit cheaper 65.6%, Hyperliquid cheaper 34.3%
- Signed spread (HL - Bybit): mean 2.99 bps, median 2.63 bps, p95 14.05 bps, min -146.98 bps, max 256.65 bps
- Absolute spread: mean 5.52 bps, median 4.48 bps, p95 14.15 bps, p99 19.16 bps, max 256.65 bps
- Conservative fee benchmark: open ~10.00 bps one-way, round-trip ~20.00 bps (taker/taker assumption)
- |spread| ≥ 5.0 bps: 45.20% of minutes, max run 117155 min, avg run 117155.0 min
- |spread| ≥ 10.0 bps: 15.36% of minutes, max run 39815 min, avg run 39815.0 min
- |spread| ≥ 15.0 bps: 3.79% of minutes, max run 9821 min, avg run 9821.0 min
- |spread| ≥ 20.0 bps: 0.74% of minutes, max run 1922 min, avg run 1922.0 min
- |spread| ≥ 25.0 bps: 0.12% of minutes, max run 320 min, avg run 320.0 min
- |spread| ≥ 30.0 bps: 0.04% of minutes, max run 113 min, avg run 113.0 min

## SOL
- Bybit symbol: `SOLPERP`
- Hyperliquid symbol: `SOL`
- Overlap: 259,201 aligned 1m candles
- Bybit range: 2025-08-11T04:19:00+00:00 → 2026-02-07T04:19:00+00:00 (259,201 candles)
- Hyperliquid range: 2025-08-11T04:19:00+00:00 → 2026-02-07T04:19:00+00:00 (259,201 candles)
- Coverage on common span: Bybit 100.0%, Hyperliquid 100.0%
- Directional bias: Bybit cheaper 64.9%, Hyperliquid cheaper 32.2%
- Signed spread (HL - Bybit): mean 3.12 bps, median 3.14 bps, p95 15.71 bps, min -511.65 bps, max 901.34 bps
- Absolute spread: mean 6.74 bps, median 5.54 bps, p95 16.77 bps, p99 24.66 bps, max 901.34 bps
- Conservative fee benchmark: open ~10.00 bps one-way, round-trip ~20.00 bps (taker/taker assumption)
- |spread| ≥ 5.0 bps: 53.96% of minutes, max run 139856 min, avg run 139856.0 min
- |spread| ≥ 10.0 bps: 22.53% of minutes, max run 58397 min, avg run 58397.0 min
- |spread| ≥ 15.0 bps: 7.47% of minutes, max run 19351 min, avg run 19351.0 min
- |spread| ≥ 20.0 bps: 2.49% of minutes, max run 6448 min, avg run 6448.0 min
- |spread| ≥ 25.0 bps: 0.94% of minutes, max run 2438 min, avg run 2438.0 min
- |spread| ≥ 30.0 bps: 0.38% of minutes, max run 974 min, avg run 974.0 min

## HYPE
- Bybit symbol: `HYPEPERP`
- Hyperliquid symbol: `HYPE`
- Overlap: 255,913 aligned 1m candles
- Bybit range: 2025-08-11T04:19:00+00:00 → 2026-02-07T04:19:00+00:00 (259,201 candles)
- Hyperliquid range: 2025-08-11T04:19:00+00:00 → 2026-02-07T04:19:00+00:00 (255,913 candles)
- Coverage on common span: Bybit 98.7%, Hyperliquid 100.0%
- Directional bias: Bybit cheaper 56.1%, Hyperliquid cheaper 43.2%
- Signed spread (HL - Bybit): mean 2.89 bps, median 2.63 bps, p95 35.90 bps, min -714.29 bps, max 4228.01 bps
- Absolute spread: mean 15.18 bps, median 10.89 bps, p95 42.87 bps, p99 70.77 bps, max 4228.01 bps
- Conservative fee benchmark: open ~10.00 bps one-way, round-trip ~20.00 bps (taker/taker assumption)
- |spread| ≥ 5.0 bps: 75.83% of minutes, max run 194057 min, avg run 194057.0 min
- |spread| ≥ 10.0 bps: 53.55% of minutes, max run 137036 min, avg run 137036.0 min
- |spread| ≥ 15.0 bps: 36.49% of minutes, max run 93372 min, avg run 93372.0 min
- |spread| ≥ 20.0 bps: 24.76% of minutes, max run 63362 min, avg run 63362.0 min
- |spread| ≥ 25.0 bps: 17.07% of minutes, max run 43682 min, avg run 43682.0 min
- |spread| ≥ 30.0 bps: 11.92% of minutes, max run 30510 min, avg run 30510.0 min

## ZEC
- Bybit symbol: `ZECUSDT`
- Hyperliquid symbol: `ZEC`
- Overlap: 184,772 aligned 1m candles
- Bybit range: 2025-08-11T04:19:00+00:00 → 2026-02-07T04:19:00+00:00 (259,201 candles)
- Hyperliquid range: 2025-10-01T20:48:00+00:00 → 2026-02-07T04:19:00+00:00 (184,772 candles)
- Coverage on common span: Bybit 71.3%, Hyperliquid 100.0%
- Directional bias: Bybit cheaper 71.3%, Hyperliquid cheaper 27.0%
- Signed spread (HL - Bybit): mean 3.75 bps, median 3.12 bps, p95 16.68 bps, min -1551.93 bps, max 896.72 bps
- Absolute spread: mean 6.46 bps, median 4.52 bps, p95 17.70 bps, p99 28.58 bps, max 1551.93 bps
- Conservative fee benchmark: open ~10.00 bps one-way, round-trip ~20.00 bps (taker/taker assumption)
- |spread| ≥ 5.0 bps: 46.06% of minutes, max run 85112 min, avg run 85112.0 min
- |spread| ≥ 10.0 bps: 19.77% of minutes, max run 36521 min, avg run 36521.0 min
- |spread| ≥ 15.0 bps: 8.02% of minutes, max run 14821 min, avg run 14821.0 min
- |spread| ≥ 20.0 bps: 3.36% of minutes, max run 6202 min, avg run 6202.0 min
- |spread| ≥ 25.0 bps: 1.59% of minutes, max run 2933 min, avg run 2933.0 min
- |spread| ≥ 30.0 bps: 0.86% of minutes, max run 1586 min, avg run 1586.0 min
