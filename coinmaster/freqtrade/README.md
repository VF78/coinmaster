# CoinMaster Freqtrade Stage 1

Stage 1 migrates CoinMaster trading to native Freqtrade:

- Freqtrade owns execution, dry/live trading, backtesting, hyperopt, Telegram and FreqUI.
- The old CoinMaster trading engine must be stopped before any Freqtrade live cutover.
- No manual-confirmation layer is used in the Freqtrade path.
- CoinMaster-specific Radar/FreqAI work is Stage 2.

VPS deployment and cutover details: [RUNBOOK_VPS.md](RUNBOOK_VPS.md).

## Local commands

From repo root:

```bash
# Validate strategy is discoverable
docker compose -f freqtrade/docker-compose.yml run --rm freqtrade list-strategies --userdir /freqtrade/user_data

# Show resolved config
docker compose -f freqtrade/docker-compose.yml run --rm freqtrade show-config --config /freqtrade/user_data/config.example.json

# Native Freqtrade download-data currently fails for Hyperliquid historical OHLCV.
# Build/update the local research dataset from public archives + fresh Hyperliquid candles.
docker compose -f freqtrade/docker-compose.yml run --rm --entrypoint python freqtrade \
  /freqtrade/user_data/scripts/sync_hyperliquid_dataset.py \
  --pairs BTC/USDC:USDC ETH/USDC:USDC SOL/USDC:USDC \
  --timeframes 5m 15m 1h 4h \
  --timerange 20250701- \
  --archives always

# Backtest current 15m baseline (Hyperliquid public 15m history is ~latest 5k candles)
docker compose -f freqtrade/docker-compose.yml run --rm freqtrade backtesting \
  --config /freqtrade/user_data/config.example.json \
  --strategy CoinMasterStrategy \
  --timerange 20260306- \
  --export trades

# Hyperopt smoke test; do not promote params until there are enough trades.
docker compose -f freqtrade/docker-compose.yml run --rm freqtrade hyperopt \
  --config /freqtrade/user_data/config.example.json \
  --strategy CoinMasterStrategy \
  --timerange 20260306- \
  --spaces buy sell \
  --hyperopt-loss SharpeHyperOptLossDaily \
  --epochs 20 \
  --random-state 65
```

## Secrets

Do not commit live secrets. Use a private config overlay or environment variables:

For VPS/prod, copy `user_data/config.private.example.json` to ignored `user_data/config.private.json`. Hyperliquid uses `exchange.wallet_address` + `exchange.private_key` in Freqtrade/CCXT. Ensure the file is readable by the container user (`uid/gid 1000`) and use the production compose overlay:

```bash
docker compose -f freqtrade/docker-compose.yml -f freqtrade/docker-compose.prod.yml up -d
```

`config.example.json` is intentionally dry-run safe.
