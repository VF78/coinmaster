# Wave Engine Native Freqtrade Validation

Status: research-only wrapper for issue `#73`. This path must stay separate from the running dry bot until native validation passes.

## What was added

- `freqtrade/wave_engine/CoinMasterWaveEngineV1.py`
  Research-only native Freqtrade strategy wrapper.
- `freqtrade/wave_engine/freqtrade_adapter.py`
  Deterministic adapter that converts Freqtrade dataframes into the existing `engine.py` regime/signal model and maps the resulting signals back onto the `5m` native dataframe without peeking forward.
- `freqtrade/wave_engine/wave_engine_profiles.selected.json`
  Repo-local robust profile snapshot for `BTC`, `ETH`, `HYPE`.
- `freqtrade/wave_engine/run_native_wave_engine_research.py`
  Temp-workspace helper that stages strategy/profile copies into `freqtrade/user_data/runtime/wave-engine-native-local/<run_id>/` and bind-mounts that temp directory into the one-shot research container.

## Selected robust profiles

- `BTC/USDC:USDC`: `atr_zigzag`, `atr_mult=1.5`, `wick`, entry timeframe `5m`, `lookback=120h`, `pullback=0.6`, `maxSL=0.035`, `TP2=0.03`, `TP3=0.05`, `timeStop=12h`.
- `ETH/USDC:USDC`: `atr_zigzag`, `atr_mult=1.5`, `wick`, entry timeframe `1h`, `lookback=120h`, `pullback=0.5`, `maxSL=0.025`, `TP2=0.04`, `TP3=0.04`, `timeStop=16h`.
- `HYPE/USDC:USDC`: `pct_zigzag`, `wick`, entry timeframe `15m`, `pct_move=0.03`, `lookback=120h`, `pullback=0.4`, `maxSL=0.03`, `TP2=0.03`, `TP3=0.08`, `timeStop=6h`.

## Safety model

- No running config mutation.
- No writes into `freqtrade/user_data/strategies/`.
- No restarts or service control.
- Temp strategy/config copies live only under `freqtrade/user_data/runtime/wave-engine-native-local/<run_id>/` by default.
- Native commands use `--strategy-path` pointing at that temp directory.
- `lookahead-analysis` uses a separate generated `config.wave-engine-lookahead.json` with `entry_pricing.price_side = "other"` and `exit_pricing.price_side = "other"`, because Freqtrade internally forces market entry orders for that analysis and rejects the normal dry/backtest limit-order pricing setting.

## Adapter behavior

- Base native timeframe is fixed to `5m`.
- `BTC` emits entries directly on `5m`.
- `ETH` and `HYPE` use `1h` and `15m` entry candles respectively, but those signals are projected onto the `5m` base dataframe by exact closed-candle timestamp match.
- Informative `4h` candles drive the regime state.
- Regime snapshots are merged into the `5m` dataframe with backward-only `merge_asof`, so each `5m` row only sees the latest already-closed `4h` state.
- Native partial exits and stop/time-stop are handled in strategy callbacks from cached signal context, not from forward precomputed trades.

## Current limitations

- This is still a research wrapper, not a dry-run candidate.
- Native exits are intentionally conservative and simpler than the pure research simulator:
  - TP1/TP2/TP3 and capped stoploss are native.
  - Time-stop is native.
  - Exit-signal flips use current regime/opposite signal only.
  - The wrapper does not yet mirror every simulator nuance such as dataset-end behavior.
- Exact validation artifact under `/var/lib/coinmaster/.../robust-search-fast-20260430T0430Z.json` was not readable from this workspace, so the selected params are mirrored from operator-approved task context into the repo snapshot.

## Exact commands

Prepare a temp workspace only:

```bash
python3 freqtrade/wave_engine/run_native_wave_engine_research.py \
  --timerange 20260101-20260427
```

Prepare and run strategy discovery only:

```bash
python3 freqtrade/wave_engine/run_native_wave_engine_research.py \
  --timerange 20260101-20260427 \
  --tasks list_strategies \
  --execute
```

Prepare and run native backtest in temp workspace:

```bash
python3 freqtrade/wave_engine/run_native_wave_engine_research.py \
  --timerange 20260101-20260427 \
  --tasks backtesting \
  --execute
```

Prepare and run native lookahead analysis in temp workspace:

```bash
python3 freqtrade/wave_engine/run_native_wave_engine_research.py \
  --timerange 20260101-20260427 \
  --tasks lookahead_analysis \
  --execute
```

Prepare and run native recursive analysis in temp workspace:

```bash
python3 freqtrade/wave_engine/run_native_wave_engine_research.py \
  --timerange 20260101-20260427 \
  --tasks recursive_analysis \
  --execute
```

Run all three validations in sequence:

```bash
python3 freqtrade/wave_engine/run_native_wave_engine_research.py \
  --timerange 20260101-20260427 \
  --tasks list_strategies backtesting lookahead_analysis recursive_analysis \
  --execute
```

Every prepared run also writes exact docker commands into:

- `freqtrade/user_data/runtime/wave-engine-native-local/<run_id>/COMMANDS.md`
- `freqtrade/user_data/runtime/wave-engine-native-local/<run_id>/commands.json`

## Dry promotion gate

Do not propose dry-run replacement unless all of the following are true:

1. `list-strategies` resolves `CoinMasterWaveEngineV1` from the temp `--strategy-path`.
2. Native `backtesting` completes on the selected pairs/time window.
3. Native `lookahead-analysis` passes.
4. Native `recursive-analysis` passes, or any variance is shown to be harmless and documented.
5. Results are not dominated by one outlier trade.
6. No command in the temp workflow mutates the running dry bot config or service state.

If any gate fails, keep the wrapper research-only and record the blocker before any dry-run proposal.
