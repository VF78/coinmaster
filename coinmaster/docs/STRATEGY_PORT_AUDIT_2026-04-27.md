# CoinMasterStrategy Freqtrade Port Audit — 2026-04-27

Scope: audit Stage 1 native Freqtrade strategy port against the old CoinMaster Trading Rules / backtest / monitor logic.

Status: **baseline port exists, but it is not parity-complete**. It is good enough for Freqtrade validation, data/backtest smoke, and operator UI bootstrapping; it is not yet ready for dry-run acceptance or live cutover.

## Sources inspected

- Freqtrade port: `freqtrade/user_data/strategies/CoinMasterStrategy.py`
- Old engulfing evaluator: `src/core/engulfingEvaluator.ts`
- Old FVG evaluator: `src/core/fvgEvaluator.ts`
- Old signal-quality gate: `src/core/signalQualityContext.ts`
- Old canonical backtest engine: `src/core/backtestEngine.ts`
- Trading Rules defaults/normalization: `src/shared/tradingRules.ts`
- Current production snapshot Trading Rules from PostgreSQL `state_snapshot`.

## Current production Trading Rules snapshot

Safe, non-secret fields only:

- coins: BTC 45%, ETH 25%, HYPE 15%, `xyz:GOLD` 5%, `xyz:BRENTOIL` 5%, `xyz:EUR` 5%; SOL/ZEC are not currently enabled in old Trading Rules.
- entry timeframes: `15m`, `1h`, `4h`
- emergency exit timeframes: `4h`
- engulfing lookback: `32`
- FVG retrace: `50%`
- FVG min width: `0.65%`
- FVG require sweep: `true`, sweep lookback `32`
- FVG require first touch: `true`, max zone age `12`
- FVG require confirmation: `true`, confirmations `15m`, `1h`, `5m`, `4h`
- max leverage: `15`
- TP levels: `1.5%`, `3%`, `6%`
- SL: `2%`
- emergency exit close pct: `0%`
- autoConfirm: `false` in old runtime, but manual confirmation is intentionally removed from Freqtrade target architecture
- signal quality thresholds: ADX `0`, min impulse ATR `0`, min expected R:R `0`, time stop `0`, risk per trade `0`
- portfolio gross cap: `200%`

## What is definitely ported

| Area | Old CoinMaster behavior | Freqtrade port status |
|---|---|---|
| Native Freqtrade strategy class | n/a | Implemented as `IStrategy`, `INTERFACE_VERSION = 3` |
| Futures long/short | Hyperliquid long/short | `can_short = True`, futures config |
| Body engulfing | body-only engulfing current candle wraps previous candle body | Implemented in dataframe columns `bullish_body_engulf` / `bearish_body_engulf` |
| Liquidity sweep for engulfing | pair low/high of previous+current breaks previous N-candle extreme | Implemented as `sweep_low` / `sweep_high` and `engulf_long` / `engulf_short` |
| FVG basic zone detection | c0/c2 gap, bullish and bearish zones | Implemented in `_annotate_fvg` |
| FVG retrace trigger | retrace to configured percent inside zone | Implemented for same-timeframe FVG baseline |
| EMA/ADX regime guard | fast/slow EMA + slow slope + ADX threshold | Implemented with TA-Lib EMA/ADX on strategy timeframe |
| ATR/body impulse guard | body/ATR threshold | Implemented for entry candle body only |
| Close-quality quartile | long closes upper quartile, short lower quartile | Implemented always via `close_position` |
| Expected R:R guard | compare expected TP reward vs SL risk | Implemented in simplified percent model |
| Opposite engulf exit signal | reverse engulfing can exit | Implemented as `populate_exit_trend` opposite engulfing |
| Time stop | close if no TP1 follow-through after N bars | Implemented as `custom_exit`, but simplified |
| Leverage cap | max leverage from rules | Implemented as callback, but current default differs |
| Stake sizing | Freqtrade custom stake callback | Implemented as simplified risk cap |
| Manual confirmation removed | old runtime used pending confirmation when autoConfirm=false | Correctly omitted per Stage 1 owner decision |

## What is partially ported / materially different

### 1. Timeframe model

Old CoinMaster supports multi-timeframe entries: `15m`, `1h`, `4h`; FVG scanning is `1h/4h`, and confirmation can use lower/peer timeframes.

Current Freqtrade port uses one base timeframe: `15m`.

Impact:

- 1h/4h engulfing entries are not equivalent.
- FVG detection runs on 15m dataframe, not old `1h/4h` FVG zones.
- Confirmation timeframes are absent.

Recommended refinement:

- use Freqtrade informative pairs/timeframes for `1h` and `4h`;
- implement separate tags: `engulf_15m`, `engulf_1h`, `engulf_4h`, `fvg_1h`, `fvg_4h`;
- keep execution on base `15m`, but compute HTF signals from informative data.

### 2. FVG qualification is incomplete

Old FVG logic supports:

- structure break filter;
- min width;
- optional sweep qualification;
- optional first-touch/fresh-zone qualification;
- max zone age;
- optional confirmation across configured timeframes.

Current Freqtrade port supports:

- basic FVG gap;
- min width;
- retrace level.

Missing:

- structure break alignment;
- `fvgRequireSweep`;
- `fvgSweepLookbackCandles`;
- `fvgRequireFirstTouch`;
- `maxZoneAgeCandles`;
- `fvgRequireConfirmation`;
- confirmation timeframes.

This is the largest strategy-parity gap.

### 3. Parameter defaults are not aligned with current Trading Rules

Current Freqtrade defaults differ from current production snapshot:

| Param | Current Trading Rules | Freqtrade port default |
|---|---:|---:|
| engulfing lookback | 32 | 70 |
| FVG retrace | 50 | 60 |
| FVG min width | 0.65 | 1.0 |
| max leverage | 15 | 10 |
| TP levels | 1.5 / 3 / 6 | 1 / 2 / 7 |
| time stop bars | 0 | 10 |
| risk per trade | 0 | 3 |
| entry TFs | 15m / 1h / 4h | 15m only |
| emergency exit close pct | 0 | opposite exit signal enabled |

Recommended refinement:

- align defaults to current Trading Rules before serious hyperopt;
- keep hyperopt ranges broad enough to rediscover alternatives.

### 4. Exit/risk parity is incomplete

Old canonical backtest/live logic:

- TP1/TP2/TP3 partials;
- move SL to break-even after TP1;
- emergency reverse exit can partially close based on `exitClosePct`;
- time stop only if no TP1 follow-through;
- allocation sizing + leverage + optional risk cap + portfolio gross cap.

Current Freqtrade port after Stage 1 cleanup:

- `sl_pct` is applied through `custom_stoploss()`; static `stoploss = -0.99` is only a broad fallback;
- partial TP ladder is implemented with native Freqtrade `adjust_trade_position()`:
  - one TP closes 100%;
  - two TPs close 50/50;
  - three TPs close 34/33/33;
- after first TP fill, `custom_stoploss()` protects the remainder at break-even;
- opposite engulfing exit is controlled by `exitClosePct` / configured emergency exit timeframe;
- time stop closes losing/no-profit trades after configured bars when enabled;
- stake sizing now uses Coin Distribution allocation caps plus optional risk and portfolio gross caps.

Recommended refinement:

- implement `custom_exit`/`adjust_trade_position`/Freqtrade-native mechanisms for TP ladder and BE behavior;
- decide whether Stage 1 should initially simplify exits to Freqtrade-native ROI/stoploss for robustness, or reproduce old partial ladder exactly;
- align `exitClosePct=0` unless owner chooses reverse exits in Freqtrade.

### 5. Signal-quality gate is not exactly equivalent

Old quality gate only activates when thresholds are > 0 or event lockout is active. It uses:

- regime candles on `regimeTf` (`1h`/`4h`);
- entry-timeframe displacement for engulfing;
- FVG impulse triple displacement for FVG;
- expected R:R from actual SL/TP levels;
- optional event lockout.

Current Freqtrade port:

- computes regime on 15m, not `regimeTf` informative data;
- always enforces close quartile even when `minImpulseAtr=0`;
- expected R:R is simplified from percent defaults;
- no event lockout;
- no FVG impulse triple displacement.

Impact: this likely explains why signal count collapses after regime/close-quality guards.

## Diagnostic signal counts on current local 15m dataset

Command:

```bash
docker compose -f freqtrade/docker-compose.yml run --rm --entrypoint python freqtrade \
  /freqtrade/user_data/scripts/audit_strategy_signals.py \
  --pairs BTC/USDC:USDC ETH/USDC:USDC SOL/USDC:USDC HYPE/USDC:USDC ZEC/USDC:USDC XYZ-GOLD/USDC:USDC XYZ-BRENTOIL/USDC:USDC XYZ-EUR/USDC:USDC \
  --timeframe 15m
```

Highlights:

- BTC: raw long/short signals 139/145, final entries 1/0.
- ETH: raw 117/159, final 3/8.
- SOL: raw 132/155, final 0/2.
- HYPE: raw 206/239, final 3/6.
- ZEC: raw 187/146, final 8/8.
- XYZ-GOLD/EUR: raw signals exist, final 0 due to regime/close-quality alignment.
- XYZ-BRENTOIL: final 1/1.

Interpretation:

- Pattern detection is not the bottleneck; plenty of raw engulf/FVG signals exist.
- Most candidates are removed by current same-timeframe regime + close-quartile requirements.
- Before hyperopt, the port should restore the old gate semantics: regime on configured HTF and quartile only when the quality gate is intentionally active.

## What is intentionally not ported

- Manual confirmation / pending confirmations — removed by owner decision.
- Old CoinMaster execution/runtime dependency — Stage 1 must remain native Freqtrade.
- Old Radar runtime integration — Stage 2 only, rebuilt Freqtrade-native if needed.
- Old CoinMaster UI/control shell — FreqUI/Telegram first.

## Recommended next implementation sequence

1. **Parameter alignment patch**
   - Set Freqtrade defaults to current Trading Rules snapshot.
   - Disable or make configurable the always-on quartile guard to match old quality-gate semantics.

2. **Informative timeframe patch**
   - Add `1h/4h` informative data.
   - Move regime to configured `regimeTf`.
   - Add 1h/4h engulfing and FVG tags while keeping base execution on 15m.

3. **FVG parity patch**
   - Add sweep, first-touch, max-age, structure-break, and confirmation gates.
   - Preserve all Freqtrade-native dataframe/backtest behavior.

4. **Exit/risk parity decision**
   - Owner decision needed: exact old TP ladder/BE/partial behavior vs simpler Freqtrade-native ROI/stoploss first.
   - Recommendation: implement exact old behavior only if it can be done cleanly with Freqtrade callbacks and tested; otherwise start with simpler native exits for dry-run stability.

5. **Hyperopt only after signal counts are healthy**
   - Hyperopt before restoring signal/gate parity will optimize an incomplete strategy.

## Open owner questions

1. Should Stage 1 reproduce current old Trading Rules snapshot exactly as baseline defaults, or should we intentionally start with a simpler Freqtrade-native profile and use old rules only as reference?
2. For exits: do we require old partial TP + BE + time-stop parity before dry-run, or is a simpler Freqtrade-native exit model acceptable for first dry-run?
3. Should the Freqtrade trading pair whitelist expand to all dataset markets now, or remain conservative until strategy parity improves?

## Addendum — parity update after overnight implementation

The earlier audit described the initial baseline port. The following gaps were closed after that audit:

- base timeframe moved to `5m`; `15m`, `1h`, and `4h` are informative timeframes;
- entry timeframe selection is consumed by the strategy;
- HTF FVG now uses `1h/4h` informative data and supports sweep, sweep lookback, first-touch, max zone age, and engulfing confirmation timeframes;
- regime filter now uses selected `1h/4h` informative data;
- opposite engulfing exit UI/runtime export was removed from the Freqtrade path;
- Signal Quality / Portfolio guard enable flags are exported and respected;
- expected R:R threshold handling was fixed in `SignalQualityContext` invariants.

Remaining live-gate work is operational, not a request to reintroduce the old engine: observe dry-run on fresh candles/orders and only then approve live cutover.
