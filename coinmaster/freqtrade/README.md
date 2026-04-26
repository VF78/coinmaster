# CoinMaster Freqtrade Stage 1

Stage 1 migrates CoinMaster trading to native Freqtrade:

- Freqtrade owns execution, dry/live trading, backtesting, hyperopt, Telegram and FreqUI.
- The old CoinMaster trading engine must be stopped before any Freqtrade live cutover.
- No manual-confirmation layer is used in the Freqtrade path.
- CoinMaster-specific Radar/FreqAI work is Stage 2.

## Local commands

From repo root:

```bash
# Validate strategy is discoverable
docker compose -f freqtrade/docker-compose.yml run --rm freqtrade list-strategies --userdir /freqtrade/user_data

# Show resolved config
docker compose -f freqtrade/docker-compose.yml run --rm freqtrade show-config --config /freqtrade/user_data/config.example.json

# Download dry/backtest data (example)
docker compose -f freqtrade/docker-compose.yml run --rm freqtrade download-data \
  --config /freqtrade/user_data/config.example.json \
  --timerange 20260101- \
  --timeframes 15m 1h 4h

# Backtest
docker compose -f freqtrade/docker-compose.yml run --rm freqtrade backtesting \
  --config /freqtrade/user_data/config.example.json \
  --strategy CoinMasterStrategy \
  --timerange 20260101-
```

## Secrets

Do not commit live secrets. Use a private config overlay or environment variables:

- `FREQTRADE__EXCHANGE__KEY`
- `FREQTRADE__EXCHANGE__SECRET`
- `FREQTRADE__TELEGRAM__TOKEN`
- `FREQTRADE__TELEGRAM__CHAT_ID`

`config.example.json` is intentionally dry-run safe.
