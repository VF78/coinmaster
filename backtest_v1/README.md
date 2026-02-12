# BTC Perp Backtest Scaffold (v1 contour)

Minimal runnable scaffold for strategy v1 from `PROJECT_TRUTH.md` + `BACKTEST_SPEC_V1.md`.

Implementation is pure Python stdlib (no external packages required).

## What is implemented now

- Data ingestion contour:
  - CSV loader for OHLCV (`timestamp, open, high, low, close, volume`)
  - Fallback synthetic generator so the project runs out-of-the-box
  - TODO marker for Hyperliquid historical candles wiring
- Signal hooks:
  - `attach_features()` (ATR + basic trend features)
  - `generate_entry_signal()` placeholder hook with clear TODO for exact engulfing/sweep/FVG rules
- Position sizing:
  - Risk per trade = 1.25% equity
  - Stop distance = structure + ATR buffer, capped at 0.70%
- Position management:
  - Partial TP logic: 1.0R/2.2R/3.8R with 40%/35%/25%
  - Stop-loss handling
  - Daily hard-stop: if equity falls >=20% from day start, force close + block new entries until next day
- Reporting:
  - trades/equity CSV exports
  - summary metrics (ROI, annualized return, max DD, PF, win rate, expectancy R, TP hit shares, stop share)

## Assumptions / simplifications

1. Current signal logic is a temporary placeholder and **not** the final v1 entry spec.
2. One open position at a time.
3. Conservative intrabar rule: stop is checked before TP within a bar.
4. Cost model is blended baseline from spec:
   - fee = 0.03%/side
   - slippage = 0.03%/side
5. If no CSV is present, synthetic candles are used for smoke testing.

## Run

From workspace root:

```bash
python3 -m backtest_v1.run_backtest
```

## Output

Generated under `backtest_v1/out/`:

- `trades.csv`
- `equity_curve.csv`
- `summary.csv`

## Next TODOs (explicit)

- Wire Hyperliquid historical candles for 1m/5m/15m/1H/4H.
- Implement exact v1 entries:
  - engulfing + local sweep
  - FVG inversion + retest fallback
  - explicit user bias regime (long/short activation)
- Add walk-forward module (3m train / 1m test / 1m step).
- Add regime splits (volatility buckets) and MAE/MFE distribution tables.
