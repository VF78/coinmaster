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
# The official container runs as uid/gid 1000 (ftuser), so the private file must be readable by that user.
sudo chown 1000:1000 user_data/config.private.json
chmod 600 user_data/config.private.json
editor user_data/config.private.json
```

`docker-compose.prod.yml` overlays this private config on top of `config.example.json` for the systemd service. Local validation commands can keep using `config.example.json` only.

For Hyperliquid/CCXT, use Freqtrade's DEX credential fields:

- `exchange.wallet_address`
- `exchange.private_key`

Do not use generic `exchange.key` / `exchange.secret` for Hyperliquid private connectivity.

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

Freqtrade 2026.3 / CCXT 4.5.44 currently refuses native `download-data` for Hyperliquid even when private Hyperliquid credentials are configured. The credentials validate private/account connectivity, but they do not enable Freqtrade's historical OHLCV downloader for this exchange.

Observed with private overlay on 2026-04-27:

```bash
docker compose -f freqtrade/docker-compose.yml run --rm freqtrade download-data \
  --config /freqtrade/user_data/config.example.json \
  --config /freqtrade/user_data/config.private.json \
  --timerange 20260420-20260421 \
  --timeframes 15m
```

Freqtrade still returned:

```text
Historic data not available for Hyperliquid. Hyperliquid does not support downloading trades or ohlcv data.
```

Because native `download-data` is unavailable for Hyperliquid, use the repo's Freqtrade-native dataset sync job. It merges public archival Freqtrade feather files, previous local files, and fresh Hyperliquid `candleSnapshot` candles, then writes them through Freqtrade's data handler into the canonical Freqtrade futures data directory (`user_data/data/hyperliquid/futures`). This is an operations/data-maintenance job for Freqtrade, not a runtime dependency on the old CoinMaster engine.

```bash
docker compose -f freqtrade/docker-compose.yml run --rm --entrypoint python freqtrade \
  /freqtrade/user_data/scripts/sync_hyperliquid_dataset.py \
  --pairs BTC/USDC:USDC ETH/USDC:USDC SOL/USDC:USDC HYPE/USDC:USDC ZEC/USDC:USDC XYZ-GOLD/USDC:USDC XYZ-BRENTOIL/USDC:USDC XYZ-EUR/USDC:USDC \
  --timeframes 5m 15m 1h 4h \
  --timerange 20250701- \
  --archives always
```

Current dataset strategy:

- collect `BTC`, `ETH`, `SOL`, `HYPE`, `ZEC`, `XYZ-GOLD`, `XYZ-BRENTOIL`, and `XYZ-EUR` using standard Freqtrade pair names and data layout, e.g. `BTC/USDC:USDC` → `user_data/data/hyperliquid/futures/BTC_USDC_USDC-15m-futures.feather`;
- write via Freqtrade `get_datahandler(...).ohlcv_store(..., CandleType.FUTURES)`, not custom CSV/runtime adapters;
- public archival `1m` feather files seed older history and are resampled to `5m/15m/1h/4h`;
- fresh Hyperliquid `candleSnapshot` pulls update each target timeframe directly;
- previous local Freqtrade files are merged back in, so the VPS accumulates history over time;
- generated OHLCV data is local Freqtrade runtime state and ignored by git.

Initial sync observed on 2026-04-27:

- `1h`/`4h`: no large gaps from 2025-07/2025-07-01 through current candles;
- `15m`: archive + fresh data with a short March gap from upstream archive/candleSnapshot coverage;
- `5m`: archive + fresh data with a larger March/April gap from upstream archive/candleSnapshot coverage.

The daily sync will accumulate fresh candles from now onward. Once enough local daily snapshots have accumulated, the rolling recent window will have at least six months of full local history for `5m/15m/1h/4h` backtests.

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

Install the daily dataset sync timer first:

```bash
sudo cp /opt/coinmaster/coinmaster/freqtrade/systemd/coinmaster-freqtrade-dataset-sync.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now coinmaster-freqtrade-dataset-sync.timer
sudo systemctl list-timers coinmaster-freqtrade-dataset-sync.timer --no-pager

# Optional immediate sync after install:
sudo systemctl start coinmaster-freqtrade-dataset-sync.service
sudo journalctl -u coinmaster-freqtrade-dataset-sync.service -n 120 --no-pager
```

Then install the trading service unit:

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
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail=200 freqtrade
curl -s http://127.0.0.1:8080/api/v1/ping || true
```

FreqUI is served by the Freqtrade API server on `127.0.0.1:8080`. Keep the Freqtrade container loopback-only by default.

Current production reverse proxy layout on `coinmaster24.com`:

- `https://coinmaster24.com/` → FreqUI (`127.0.0.1:8080`)
- `https://coinmaster24.com/api/v1/` → Freqtrade API
- `https://coinmaster24.com/custom/` → CoinMaster companion operator app (`127.0.0.1:8787/custom/`) with Trading Rules, Radar placeholder, and Backtest placeholder
- `https://coinmaster24.com/old/` → old CoinMaster UI (`127.0.0.1:8787`) for migration reference
- `https://coinmaster24.com/api/` except `/api/v1/` → old CoinMaster backend API for the companion app and old UI

`/custom` inherits the same nginx basic-auth / auth-cookie gate as the root domain. Do not expose it through a separate unauthenticated location.

Trading Rules saved from `/custom` are exported into Freqtrade runtime artifacts under `/var/lib/coinmaster/freqtrade/`:

- `trading_rules.json` — hot-reloaded by `CoinMasterStrategy` through Freqtrade strategy hooks.
- `config.trading-rules.json` — Freqtrade config overlay for the enabled pair whitelist; loaded by docker compose before the private config.

Legacy CoinMaster background execution monitors must remain disabled while Stage 1 is native Freqtrade. Current production env disables the old drawdown watchdog, engulfing monitor, FVG monitor, Radar autocollect, and TP fill monitor.

Risk locks should be handled by native Freqtrade protections in `CoinMasterStrategy.protections`, not by the old CoinMaster daily-drawdown watchdog. Current baseline enables `CooldownPeriod`, `StoplossGuard`, `MaxDrawdown`, and `LowProfitPairs`. For backtesting these locks, pass `--enable-protections`.

### Freqtrade-native Radar policy bridge

Stage 2 Radar integration is intentionally a policy/context layer, not an execution engine. Freqtrade remains the only component that opens/closes orders.

`CoinMasterStrategy` hot-reads an optional policy snapshot:

- host path: `/var/lib/coinmaster/freqtrade/radar_policy.json`
- container path: `/freqtrade/user_data/runtime/radar_policy.json`

If the file is missing, invalid JSON/schema, disabled, or past `valid_until`, Radar is ignored and strategy behavior is neutral/unmodified.

Minimal policy example:

```json
{
  "schema_version": 1,
  "updated_at": "2026-04-27T10:00:00Z",
  "valid_until": "2026-04-27T10:15:00Z",
  "global": {
    "enabled": true,
    "mode": "both",
    "risk_multiplier": 1.0,
    "lock_new_entries": false,
    "reason": "normal_market"
  },
  "pairs": {
    "BTC/USDC:USDC": { "mode": "off", "risk_multiplier": 0.0, "reason": "weak_context" },
    "ETH/USDC:USDC": { "mode": "long_only", "risk_multiplier": 1.0, "reason": "bullish_context" },
    "HYPE/USDC:USDC": { "mode": "both", "risk_multiplier": 0.75, "reason": "elevated_volatility" }
  }
}
```

Allowed modes: `both`, `long_only`, `short_only`, `off`.

Rules:

- `global.lock_new_entries=true` or global `mode=off` blocks all new entries.
- pair `mode=off` blocks new entries for that pair.
- directional modes only filter already-detected Freqtrade entries; Radar never force-enters.
- `risk_multiplier` is clamped to `0.0..1.0` and is applied after Trading Rules allocation/risk/gross caps.
- Atomic writer pattern: write to `radar_policy.json.tmp`, fsync if available, then rename to `radar_policy.json`.

Useful reason codes in logs: `radar_block_global`, `radar_block_pair`, `radar_direction_mismatch`, `radar_stale_ignored`, `radar_invalid_ignored`, `radar_risk_multiplier_applied`.

If public domain access should be avoided during maintenance, use an SSH tunnel instead:

```bash
ssh -L 8080:127.0.0.1:8080 <user>@<vps-host>
# then open http://127.0.0.1:8080 locally
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

## 11. Current Stage 1 dry-run candidate — 2026-04-27 overnight

After implementing the full Freqtrade multi-timeframe/FVG/regime path, the selected dry-run candidate is:

- pair whitelist: `ETH/USDC:USDC`, `HYPE/USDC:USDC`;
- entry timeframes: `15m`, `1h`, `4h`;
- FVG sweep, first-touch, max-age, and confirmation enabled;
- TP levels `1.5 / 3 / 6`, SL `2`;
- both long and short enabled;
- Freqtrade protections enabled.

Backtest window: `20260101-20260427` (covers 2026-01-01 through 2026-04-26 closed candles).

Result:

- 42 trades;
- +393.638 USDC / +39.36%;
- profit factor 1.73;
- Sharpe 1.27;
- Sortino 4.89;
- max drawdown 176.026 USDC / 15.28%;
- entry/exit timeouts 0/0.

Runtime artifacts are written under `/var/lib/coinmaster/freqtrade/` and mounted into the container as `/freqtrade/user_data/runtime`.

Do not switch to live automatically. Required live gate remains: observe dry-run on fresh candles/orders, confirm account isolation/current positions, then get explicit owner approval.
