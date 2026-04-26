# CoinMaster Freqtrade Stage 1 — VPS Runbook

This runbook is for the autonomous native Freqtrade core. The old CoinMaster/Radar runtime is reference-only and must not run live trading in parallel with Freqtrade on the same Hyperliquid account.

## 1. Host layout

Recommended production path:

```bash
/opt/coinmaster                 # git checkout of VF78/coinmaster
/opt/coinmaster/coinmaster/freqtrade
/opt/coinmaster/coinmaster/freqtrade/user_data/config.private.json  # private secrets, never committed
```

Required host tools:

```bash
docker --version
docker compose version
git --version
```

## 2. Checkout/update

```bash
sudo mkdir -p /opt/coinmaster
sudo chown -R "$USER":"$USER" /opt/coinmaster
cd /opt/coinmaster

git clone https://github.com/VF78/coinmaster.git .  # first install only
git fetch origin
git checkout freqtrade-stage1-migration
git pull --ff-only origin freqtrade-stage1-migration
```

## 3. Secrets

Create `user_data/config.private.json` from the committed example and keep it mode `600`:

```bash
cd /opt/coinmaster/coinmaster/freqtrade
cp user_data/config.private.example.json user_data/config.private.json
chmod 600 user_data/config.private.json
editor user_data/config.private.json
```

`docker-compose.prod.yml` overlays this private config on top of `config.example.json` for the systemd service. Local validation commands can keep using `config.example.json` only.

Rules:

- do not commit live secrets;
- keep FreqUI/API bound to `127.0.0.1:8080` unless a reverse proxy with auth/TLS is explicitly configured;
- use a dedicated Hyperliquid account/subaccount for dry-run/live cutover where possible.

## 4. Preflight validation

From `/opt/coinmaster/coinmaster`:

```bash
docker compose -f freqtrade/docker-compose.yml pull

docker compose -f freqtrade/docker-compose.yml run --rm freqtrade \
  list-strategies --userdir /freqtrade/user_data

docker compose -f freqtrade/docker-compose.yml run --rm freqtrade \
  show-config --config /freqtrade/user_data/config.example.json
```

Expected current baseline:

- `CoinMasterStrategy` is discoverable and hyperoptable;
- exchange is `hyperliquid`, trading mode is futures/cross;
- pairs resolve as `BTC/USDC:USDC`, `ETH/USDC:USDC`, `SOL/USDC:USDC`;
- example config remains dry-run safe.

## 5. Backtest data

Freqtrade 2026.3 / CCXT 4.5.44 currently refuses native `download-data` for Hyperliquid with:

```text
Historic data not available for Hyperliquid. Hyperliquid does not support downloading trades or ohlcv data.
```

Use the repo bridge script, which pulls public candles from Hyperliquid `candleSnapshot` and stores Freqtrade-compatible futures OHLCV files:

```bash
docker compose -f freqtrade/docker-compose.yml run --rm --entrypoint python freqtrade \
  /freqtrade/user_data/scripts/download_hyperliquid_ohlcv.py \
  --pairs BTC/USDC:USDC ETH/USDC:USDC SOL/USDC:USDC \
  --timeframes 15m 1h 4h \
  --timerange 20260101-
```

Known data limitation observed on 2026-04-27:

- `15m` candles are available only for roughly the latest 5k candles from Hyperliquid, starting around `2026-03-05` for the current baseline;
- `1h`/`4h` candles are available back to `2026-01-01` for the same request;
- Stage 1 backtests on the current 15m strategy should use `20260306-` until a deeper data source is added.

Generated OHLCV data is local runtime state and ignored by git.

## 6. Baseline backtest

```bash
docker compose -f freqtrade/docker-compose.yml run --rm freqtrade backtesting \
  --config /freqtrade/user_data/config.example.json \
  --strategy CoinMasterStrategy \
  --timerange 20260306- \
  --export trades
```

Baseline result from 2026-04-27 data pull:

- period tested by Freqtrade: `2026-03-08 06:15:00` → `2026-04-26 22:30:00`;
- trades: `1`;
- result: `-0.430 USDC`, `-0.04%` total;
- conclusion: current Stage 1 strategy is too restrictive for meaningful optimization and needs signal/refinement work before dry-run acceptance.

## 7. Hyperopt smoke test

Use this only as a pipeline validation until the strategy produces enough trades:

```bash
docker compose -f freqtrade/docker-compose.yml run --rm freqtrade hyperopt \
  --config /freqtrade/user_data/config.example.json \
  --strategy CoinMasterStrategy \
  --timerange 20260306- \
  --spaces buy sell \
  --hyperopt-loss SharpeHyperOptLossDaily \
  --epochs 20 \
  --random-state 65
```

Observed smoke result: hyperopt runs and writes result files, but only sees one losing trade. Do not promote generated params from this run.

Next refinement target:

1. increase trade sample size without weakening the architecture;
2. separate entry diagnostics by tag/pair/timeframe;
3. decide whether Stage 1 needs broader data import beyond Hyperliquid's public 15m retention;
4. only then run longer hyperopt and champion/candidate comparison.

## 8. Dry-run service

Install the systemd unit:

```bash
sudo cp /opt/coinmaster/coinmaster/freqtrade/systemd/coinmaster-freqtrade.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable coinmaster-freqtrade
sudo systemctl start coinmaster-freqtrade
sudo systemctl status coinmaster-freqtrade --no-pager
```

Operational checks:

```bash
cd /opt/coinmaster/coinmaster/freqtrade
docker compose ps
docker compose logs --tail=200 freqtrade
curl -s http://127.0.0.1:8080/api/v1/ping || true
```

The example config starts with `initial_state: stopped`; explicitly start trading through FreqUI/Telegram/API only after backtest and dry-run acceptance are met.

## 9. Live cutover checklist

Do not start Freqtrade live until all are true:

- latest accepted backtest/hyperopt candidate is documented;
- dry-run has been stable and operator workflow is covered by native Telegram/FreqUI;
- old CoinMaster trading execution is stopped/disabled;
- no other bot can open/reduce positions on the same Hyperliquid account;
- current positions/orders/account state are understood;
- secrets are present only in ignored `user_data/config.private.json` or another private secret store;
- rollback path is known: stop Freqtrade, inspect open orders/positions manually, do not automatically restart old execution without owner approval.

## 10. Rollback / stop

```bash
sudo systemctl stop coinmaster-freqtrade
cd /opt/coinmaster/coinmaster/freqtrade
docker compose down
```

Then inspect Hyperliquid account state manually before making any further live-trading decision.
