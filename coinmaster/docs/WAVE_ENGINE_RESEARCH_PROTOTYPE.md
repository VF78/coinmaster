# Wave Engine Research Prototype

Status: research-only prototype for issue #73 slices 1-5. This does not mutate the running Freqtrade config, does not restart services, and does not start dry/live trading.

## Current safe code location

The intended long-term home is `freqtrade/user_data/scripts/wave_engine/` plus `freqtrade/user_data/strategies/CoinMasterWaveEngineV1.py`.

In this workspace snapshot, `freqtrade/user_data/*` is permission-locked, so the prototype currently lives under:

- `freqtrade/wave_engine/engine.py`
- `freqtrade/wave_engine/run_wave_engine_research.py`
- `freqtrade/wave_engine/CoinMasterWaveEngineV1.py`
- `freqtrade/wave_engine/wave_engine_profile.example.json`
- `scripts/check-wave-engine-prototype.py`

This keeps the work research-only and separate from the running bot surface.

## Implemented slices

### Slice 1: 4H wave/regime prototype

- Closed-candle-only 4H regime engine with states `flat | long | short`.
- Configurable ATR ZigZag and percent ZigZag pivot detection.
- Configurable structural-break basis: `wick` or `close`.
- Sequential break counting:
  - first break => `flat`
  - second same-direction break without opposite break => confirmed `long` / `short`
  - opposite break resets count

### Slice 2: entry engine

- Strict body engulfing on `5m`, `15m`, `1h`.
- Flat entry requires one of the two engulfing candles to print the flat extreme over `flatExtremeLookbackHours`.
- Trend entry requires:
  - confirmed 4H trend
  - impulse plus correction
  - pullback ratio between configured floor and `0.8`
  - strict body engulfing confirmation
- One entry per flat 4H sequence or per trend correction context.

### Slice 3: trade simulation

- Long/short stop from impulse start with `0.33%` buffer, capped by `maxSlPct`.
- TP1 uses nearest extremum capped at `1.5%`.
- TP2 / TP3 configurable from profile.
- After TP1, stop moves to breakeven.
- `timeStopHours` supported.
- Reproducible metrics:
  - ROI
  - profit
  - profit factor
  - max drawdown
  - winrate
  - trade count
  - top-trade stress

### Slice 4: parameter matrix CLI

- `single` and `matrix` modes.
- `quick` and `deep` candidate pools.
- `random` or bounded `grid` sampling.
- `--max-candidates` and `--seed` bound search cost and keep runs reproducible.
- Immutable artifacts per run:
  - `profile.json`
  - `resolved-params.json`
  - `state.json`
  - `pivots.json`
  - `regime.json`
  - `signals.json`
  - `trades.json`
  - `trades.csv`
  - `metrics.json`
  - `SUMMARY.md`

### Slice 5: native Freqtrade research wrapper

- `freqtrade/wave_engine/CoinMasterWaveEngineV1.py`
- `freqtrade/wave_engine/freqtrade_adapter.py`
- `freqtrade/wave_engine/wave_engine_profiles.selected.json`
- `freqtrade/wave_engine/run_native_wave_engine_research.py`
- Research-only native wrapper that:
  - loads repo-local robust per-pair profile snapshots;
  - computes closed-candle regime/signal state from the existing `engine.py`;
  - projects higher-timeframe selected signals onto the native `5m` dataframe without forward merges;
  - stages temp strategy/config copies under `freqtrade/user_data/runtime/wave-engine-native-local/<run_id>/` for native backtesting / lookahead / recursive validation.

## Dataset contract

The prototype CLI expects JSON candles:

```json
{
  "candles": {
    "4h": [
      { "timestamp": "2026-01-01T00:00:00+00:00", "open": 100, "high": 101, "low": 99, "close": 100.5, "volume": 1 }
    ],
    "1h": [],
    "15m": [],
    "5m": []
  }
}
```

Timestamps may also be epoch seconds.

## Commands

Local synthetic check:

```bash
python3 scripts/check-wave-engine-prototype.py
```

Single-candidate run with writable local artifacts:

```bash
python3 freqtrade/wave_engine/run_wave_engine_research.py \
  --dataset /tmp/wave-engine-dataset.json \
  --output-root /tmp/wave-engine-runs \
  single
```

Quick matrix search:

```bash
python3 freqtrade/wave_engine/run_wave_engine_research.py \
  --dataset /tmp/wave-engine-dataset.json \
  --output-root /tmp/wave-engine-runs \
  matrix \
  --mode quick \
  --sampling random \
  --max-candidates 24 \
  --seed 73
```

Deep bounded search:

```bash
python3 freqtrade/wave_engine/run_wave_engine_research.py \
  --dataset /tmp/wave-engine-dataset.json \
  --output-root /tmp/wave-engine-runs \
  matrix \
  --mode deep \
  --sampling random \
  --max-candidates 96 \
  --seed 73
```

Production/default artifact root remains:

```text
/var/lib/coinmaster/freqtrade/research/wave-engine/runs/<run_id>/
```

In the current sandbox, writes to `/var/lib/coinmaster/...` are permission-blocked, so local verification uses `/tmp/...` instead.

## Current caveats

- The prototype is pure-stdlib Python because this local environment does not currently have `pandas` / `numpy`.
- Native wrapper validation is documented in `docs/WAVE_ENGINE_NATIVE_FREQTRADE_VALIDATION.md`.
- Do not treat the wrapper as dry-run ready until native `backtesting`, `lookahead-analysis`, and `recursive-analysis` pass.
- Same-candle TP/SL collisions are resolved conservatively by checking stop before targets.
