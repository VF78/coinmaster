# Coinmaster — архитектура, Trading Rules engine, Radar и единый путь открытия сделок

> **2026-04-27 update:** The target implementation path is now autonomous native Freqtrade. This older document remains useful as AS-IS/reference material, but custom CoinMaster execution/backtest/optimizer/Radar runtime should not be treated as the future runtime. See `docs/FREQTRADE_MIGRATION_2026-04-27.md`.


_Статус: read-only аудит логики + сводная документация. Код торговой логики не менялся._

Этот документ описывает текущую реализацию Coinmaster по коду репозитория:

- общую архитектуру приложения;
- логику торгового движка, управляемого страницей **Trading Rules**;
- логику Radar / Alpha Radar;
- единый путь открытия сделки по сигналам Trading Rules engine и Radar;
- текущие инварианты, ограничения и найденные нюансы.

Если этот документ расходится с кодом, код считается источником истины.

---

## 1. Ключевая идея архитектуры

Coinmaster сейчас устроен как single-operator trading system с несколькими независимыми источниками сигналов, но с **единым исполнительным контуром**.

Упрощённая схема:

```text
React UI / Telegram / owner API
        |
        v
Express API + runtime monitors
        |
        +--> Trading Rules engine
        |       +--> Engulfing monitor
        |       +--> FVG monitor
        |
        +--> Alpha Radar source plane
        |       +--> market snapshots
        |       +--> RSS/JSON/GDELT feeds
        |       +--> Telegram / Reddit / Bluesky connectors
        |       +--> observations / ideas / health
        |
        +--> Radar execution ingest
                +--> POST /api/radar/signals
                +--> POST /api/radar/signals/batch

All executable signals
        |
        v
handoffStrategyEntrySignal()
        |
        +--> manual pending confirmation
        |       +--> Dashboard / Telegram confirm
        |
        +--> auto-confirm path
                +--> sizing
                +--> risk gates
                +--> exchange order
                +--> TP/SL placement
                +--> TP fill monitor / break-even SL
```

Главный архитектурный принцип: **Radar не является вторым торговым движком**. Radar может находить и принимать сигналы, но исполнение идёт через тот же `handoffStrategyEntrySignal()`, что и engulfing/FVG.

---

## 2. Основные слои репозитория

### 2.1. Frontend

Путь: `src/web/*`

- React + Vite UI.
- Основные страницы:
  - `DashboardPage.tsx` — live state, позиции, pending confirmations, bias controls.
  - `TradingRulesPage.tsx` — настройка активов, engulfing/FVG, risk, TP/SL, auto-confirm.
  - `AlphaRadarPage.tsx` — Radar health, observations, ideas, signals.
  - `BacktestPage.tsx` — backtest интерфейс.
  - `SettingsPage.tsx` — настройки exchange/Telegram/etc.

Frontend не торгует напрямую. Он вызывает API backend.

### 2.2. Backend / orchestration

Путь: `src/server/index.ts`

Это главный runtime-файл:

- Express API;
- live market ingest;
- Trading Rules runtime cache;
- engulfing/FVG monitors;
- risk gates;
- order endpoints;
- pending confirmation flow;
- Radar ingest;
- Alpha Radar collectors;
- Telegram outbox/update loop;
- drawdown watchdog;
- TP fill monitor.

### 2.3. Core domain logic

Путь: `src/core/*`

Важные файлы:

- `engulfingEvaluator.ts` — body engulfing + sweep evaluator.
- `fvgEvaluator.ts` — FVG zones, retrace, sweep/first-touch/confirmation.
- `backtestEngine.ts` — backtest с теми же Trading Rules настройками.
- `db.ts` — legacy-compatible DB facade.
- `tradeEvents.ts` — append-only trade event helpers.

### 2.4. Exchange abstraction

Путь: `src/exchange/*`

Основной контракт: `ExchangeAdapter`.

Поддерживает:

- market data:
  - `getMids()`;
  - `getCandles()`;
  - `getInstrumentMeta()`;
  - optional `getTradableSymbols()`;
- account:
  - `getAccountState()`;
  - `getOpenOrders()`;
  - `getOpenPositions()`;
  - `getFills()`;
- trading:
  - `placeLimitOrder()`;
  - `placeTriggerOrder()`;
  - `cancelOrder()`;
  - `cancelAll()`;
  - `placeReduceOnlyExit()`;
  - `setLeverage()`;
- realtime mids:
  - optional `subscribeMids()`.

Hyperliquid — текущий первый adapter, но архитектура явно строится exchange-agnostic.

### 2.5. Persistence

DB facade: `src/core/db.ts`.

Он возвращает объект в стиле lowdb:

```ts
{
  data,
  reload(),
  write()
}
```

Backend store выбирается через `PERSISTENCE_BACKEND`, default — lowdb.

Ключевые коллекции в `DBShape`:

- `settings`;
- `positions`;
- `tradeLogs`;
- `tradeEvents`;
- `biasCommands`;
- `marketTicks`;
- `dailyDDBaselines`;
- `riskGateAudit`;
- `pendingConfirmations`;
- `telegramOutbox`;
- `radarSignals`;
- `alphaRadarObservations`;
- `backtestRuns`;
- `optimizationResults`.

---

## 3. Runtime startup sequence

На старте сервера запускается:

1. `rulesCache.start()` — периодически читает Trading Rules из DB.
2. Initial REST ingest и live mid stream.
3. Drawdown watchdog.
4. Daily drawdown midnight reset.
5. Engulfing monitor, если `ENABLE_MULTI_TF_ENGULFING=true`.
6. FVG monitor, если `ENABLE_FVG_MONITOR=true`.
7. TP fill monitor.
8. Telegram outbox loop.
9. Telegram update loop.
10. Daily analytics loop.
11. Alpha Radar monitoring plane.
12. Initial live snapshot warmup.

Мониторы стартуют со stagger delay, чтобы не ударить одновременно по exchange/info endpoints.

---

## 4. Settings planes

В системе есть несколько независимых групп настроек.

### 4.1. Trading Rules

Источник:

- UI: `TradingRulesPage.tsx`
- типы/defaults: `src/shared/tradingRules.ts`, `src/shared/dto.ts`
- API:
  - `GET /api/settings/trading-rules`
  - `PUT /api/settings/trading-rules`
  - `GET /api/settings/trading-rules/symbols`
  - `GET /api/settings/trading-rules/effective`

Trading Rules управляют:

- tradable universe;
- allocation;
- engulfing entry/exit TF;
- FVG параметры;
- max leverage;
- daily drawdown;
- TP/SL defaults;
- emergency exit close percentage;
- auto/manual confirmation;
- bias policy.

### 4.2. Radar Runtime

Источник:

- `src/shared/radarRuntime.ts`
- API:
  - `GET /api/settings/radar`
  - `PUT /api/settings/radar`

Поля:

```ts
enabled: boolean
/* whether Radar execution ingest is active */

autoConfirm: boolean
/* whether Radar signals auto-submit or create pending confirmations */
```

Если `autoConfirm` явно не задан, fallback берётся из Trading Rules `autoConfirm`.

### 4.3. Alpha Radar settings

Источник:

- `src/server/alphaRadar.ts`
- API:
  - `GET /api/settings/alpha-radar`
  - `PUT /api/settings/alpha-radar`

Поля:

- `enabled`;
- `manualQueueOnly`;
- `autoConfirmOrders`;
- `allowHypothesisEntries`;
- `maxIdeasPerCycle`;
- `minIdeaScore`;
- `collectorLookbackHours`;
- `refreshIntervalMinutes`;
- `marketSnapshot`;
- `feeds`;
- `connectors`.

Важно: эти поля управляют **source plane / idea plane**, а не прямым exchange execution.

---

# Part A — Trading Rules Engine

---

## 5. Trading Rules: настройки и нормализация

Тип: `TradingRulesSettings`.

Основные поля:

```ts
coins: TradingCoinAllocation[]
entryTimeframes: TradingRulesTimeframe[]
emergencyExitTimeframes: TradingRulesTimeframe[]
engulfingLookbackCandles: number
fvgRetrace: number
fvgMinWidthPct: number
fvgRequireSweep: boolean
fvgSweepLookbackCandles: number
fvgRequireFirstTouch: boolean
maxZoneAgeCandles: number
fvgRequireConfirmation: boolean
fvgConfirmationTimeframes: TradingRulesTimeframe[]
maxLeverage: number
dailyDrawdown: number
tpLevels: number[]
slPct: number
exitClosePct: number
autoConfirm: boolean
biasPolicy?: BiasPolicySettings
```

Default значения:

```text
coins:
  BTC 50%, ETH 30%, SOL 20%, all enabled
entryTimeframes: [15m]
emergencyExitTimeframes: [1h]
engulfingLookbackCandles: 30
fvgRetrace: 50
fvgMinWidthPct: 0.3
fvgRequireSweep: false
fvgSweepLookbackCandles: 20
fvgRequireFirstTouch: false
maxZoneAgeCandles: 12
fvgRequireConfirmation: false
fvgConfirmationTimeframes: [15m]
maxLeverage: 5
dailyDrawdown: 3
tpLevels: [6]
slPct: 2
exitClosePct: 50
autoConfirm: false
biasPolicy.defaultBias: both
biasPolicy.symbolOverrides: {}
```

Нормализация делает:

- symbols uppercase или `namespace:SYMBOL`;
- timeframes только `5m | 15m | 1h | 4h`;
- allocation `%` clamp `0–100`;
- FVG retrace clamp `10–90`;
- FVG min width clamp `0–10`;
- trading bias clamp `long | short | both | off` (default `both`);
- sweep lookback clamp `3–100`;
- zone age clamp `1–500`;
- max leverage clamp `1–50`;
- daily drawdown clamp `0–100`;
- TP/SL clamp `0–1000`;
- `tpPct` legacy синхронизируется с первым `tpLevels`;
- legacy scalar `entryTf`/`exitTf` синхронизируются с первым элементом arrays.

Save API дополнительно требует:

- хотя бы один enabled coin;
- сумма enabled allocation = 100%;
- symbols должны существовать на exchange или быть resolvable через candle probe.

---

## 6. RuntimeRulesCache

Файл: `src/server/runtimeRules.ts`.

`RuntimeRulesCache` обновляет Trading Rules из DB примерно каждые 5 секунд и даёт hot path синхронный доступ через `getEffectiveRules()`.

Runtime view:

```ts
manualConfirmation = !rules.autoConfirm
maxLeverage = rules.maxLeverage
portfolioLeverageCap = rules.maxLeverage
dailyDDLimitPct = rules.dailyDrawdown
source = 'runtime'
raw = normalized TradingRulesSettings
```

Если DB недоступна, fallback берётся из env:

- `LIVE_MAX_LEVERAGE`, default `10`;
- `LIVE_MANUAL_CONFIRMATION`, default `true`;
- `LIVE_DAILY_DD_LIMIT_PCT`, default `20`;
- `LIVE_PORTFOLIO_LEVERAGE_CAP`, default `10`.

Но в env fallback `raw=null`, поэтому configured symbol allowlist/allocation helpers fail-closed для символов.

---

## 7. Monitored symbols

Функция: `getMonitoredSymbols(rules, fallbackSymbol)`.

Правило:

- берутся только `rules.coins`, где `enabled=true`;
- symbols нормализуются;
- дубликаты убираются;
- если enabled list пуст внутри runtime — fallback symbol, но save API не даёт сохранить пустой enabled list.

Важно:

- `assetClass` не добавляет символы в monitoring universe;
- `assetClass` используется для bias/diagnostics/verdict thresholds;
- tradable universe для Trading Rules engine и Radar handoff — это enabled coins.

---

## 8. Bias policy

Bias может быть:

```ts
'long' | 'short' | 'off'
```

Источники bias:

- class-level bias по `assetClass`;
- symbol-specific bias, если для symbol включён custom mode.

Логика:

- `off` блокирует вход;
- `long` разрешает только buy/long;
- `short` разрешает только sell/short.

Bias проверяется до queue/order для engulfing/FVG и повторно в pending queue path.

---

## 9. Engulfing evaluator

Файл: `src/core/engulfingEvaluator.ts`.

Есть два evaluator-а.

### 9.1. Body-only engulfing

Функция: `evaluateBodyEngulfingTimeframe()`.

Используется для FVG lower-timeframe confirmation.

Требует только 2 свечи:

- bullish:
  - current candle green: `close > open`;
  - body current полностью покрывает body previous;
- bearish:
  - current candle red: `close < open`;
  - body current полностью покрывает body previous.

Sweep здесь не требуется.

### 9.2. Engulfing + sweep

Функция: `evaluateTimeframe()`.

Используется для:

- entry engulfing monitor;
- emergency exit engulfing monitor;
- multi-TF engulfing gate на manual order endpoints.

Требует минимум `lookback + 2` свечи:

- `lookback` history candles;
- previous candle;
- current closed candle.

Bullish signal:

```text
current body fully engulfs previous body
AND current is green
AND low(previous + current) < lowestLow(history)
```

Bearish signal:

```text
current body fully engulfs previous body
AND current is red
AND high(previous + current) > highestHigh(history)
```

То есть это не просто engulfing, а engulfing после sweep/breakout экстремума.

Confidence by timeframe:

```text
5m  -> 0.95
15m -> 0.90
1h  -> 0.85
4h  -> 0.80
```

---

## 10. Engulfing background monitor

Функция: `runEngulfingMonitorTick()`.

Запуск:

- `startEngulfingMonitor()`;
- включается только если `ENABLE_MULTI_TF_ENGULFING=true`;
- требует `exchange.capabilities.privateAccount` и `privateTrading`.

Интервал:

```text
min(entryTimeframes) / 10
clamped to 30s..120s
```

На каждом тике:

1. берёт `effectiveRules`;
2. если `raw=null` — выходит;
3. берёт monitored symbols;
4. получает open positions;
5. получает mids;
6. для каждого symbol получает operator bias.

### 10.1. Entry path

Если по symbol нет открытой позиции:

1. для каждого `entryTimeframe` грузятся candles;
2. берутся только закрытые candles;
3. вызывается `evaluateTimeframe()`;
4. если сигнала нет — skip;
5. direction конвертируется в side:
   - bullish -> buy;
   - bearish -> sell;
6. проверяется bias;
7. signal debounce: один раз за TF-period по ключу `symbol:tf:direction`;
8. price берётся из mids или последней свечи;
9. вызывается `handoffStrategyEntrySignal()`.

Если handoff вернул `flow='break'`, текущий TF loop останавливается.

### 10.2. Emergency exit path

Если по symbol есть открытая позиция:

1. pending confirmation по symbol очищается;
2. entry signals не ищутся;
3. проверяются `emergencyExitTimeframes`;
4. reverse signal считается emergency exit:
   - long + bearish engulfing;
   - short + bullish engulfing.

Debounce emergency exit делается по закрытой engulfing candle, чтобы не закрывать позицию повторно на каждом tick.

Дальше применяется `exitClosePct`:

- `0%`: действие отключено, только audit/log;
- `>= 100%`: полный close symbol через `emergencyCloseSymbol()`;
- `1–99%`:
  - reduce-only partial close;
  - старые SL orders отменяются;
  - новый SL ставится в break-even на entry price для остатка;
  - если partial close/BE SL не удался — fallback к full emergency close symbol.

---

## 11. FVG evaluator

Файл: `src/core/fvgEvaluator.ts`.

FVG timeframes:

```text
1h, 4h
```

### 11.1. Зона FVG

Bullish FVG:

```text
candle[i-2].high < candle[i].low
zone bottom = candle[i-2].high
zone top    = candle[i].low
```

Bearish FVG:

```text
candle[i-2].low > candle[i].high
zone bottom = candle[i].high
zone top    = candle[i-2].low
```

Ширина:

```text
widthPct = gapWidth / midpoint * 100
```

Зона проходит только если `widthPct >= fvgMinWidthPct`.

### 11.2. Structure break filter

`detectStructureBreak()` смотрит последние 20 свечей:

- close выше swing high -> bullish BOS;
- close ниже swing low -> bearish BOS;
- если BOS есть, FVG зоны фильтруются по направлению BOS.

### 11.3. Retrace trigger

Bullish trigger:

```text
zone.top - (zone.range * fvgRetracePct / 100)
```

Bullish qualifies:

```text
currentPrice <= trigger
AND currentPrice >= zone.bottom
```

Bearish mirror:

```text
trigger = zone.bottom + zone.range * fvgRetracePct / 100
currentPrice >= trigger
AND currentPrice <= zone.top
```

### 11.4. Optional qualifiers

FVG может дополнительно требовать:

- HTF sweep внутри 3-свечного impulse;
- first touch only;
- max zone age;
- lower-TF confirmation через body-only engulfing того же направления.

---

## 12. FVG background monitor

Функция: `runFvgMonitorTick()`.

Запуск:

- `startFvgMonitor()`;
- только если `ENABLE_FVG_MONITOR=true`;
- требует private account/trading capabilities;
- default interval `FVG_MONITOR_INTERVAL_MS = 300000` ms, минимум 60 секунд.

На каждом тике:

1. берёт `effectiveRules.raw`;
2. если `raw=null` — выходит;
3. читает FVG settings;
4. берёт monitored symbols;
5. получает open positions и mids;
6. если position по symbol есть:
   - pending confirmation очищается;
   - entry не ищется;
7. для flat symbol проверяет только `1h` и `4h`;
8. грузит candles;
9. если включена confirmation — грузит lower-TF candles;
10. вызывает `evaluateFvg()`;
11. проверяет bias;
12. debounce: один раз за TF-period по `symbol:tf:direction`;
13. вызывает `handoffStrategyEntrySignal()`.

FVG emergency exit сейчас нет. Выходы делает reverse engulfing на emergency exit TF.

---

## 13. Manual order engulfing gate

На live order endpoints подключён `engulfingGate`:

- `POST /api/live/order/limit`
- `POST /api/live/order`

Для non-reduce-only order gate:

1. берёт Trading Rules;
2. грузит candles по entry/exit TF;
3. вызывает `evaluateMultiTf()`;
4. если нет entry engulfing signal — возвращает `403 no_engulfing_entry_signal`;
5. если candles fetch failed или rules unavailable — fail-open с audit reason.

Важно: background engulfing monitor feature-flagged, но route-level `engulfingGate` подключён к endpoints напрямую.

---

# Part B — Radar / Alpha Radar

---

## 14. Radar: две разные плоскости

В коде есть две принципиально разные сущности:

### 14.1. Alpha Radar / Source Radar

Назначение:

- наблюдать широкий рынок;
- собирать observations;
- следить за health источников;
- строить ideas/watchlists;
- показывать контекст оператору.

Alpha Radar **не открывает сделки напрямую**.

### 14.2. Execution Radar ingest

Назначение:

- принять конкретный trade candidate;
- проверить payload;
- dedupe;
- проверить, что symbol включён в Trading Rules;
- передать в единый execution handoff.

Execution Radar не считает sizing, не ставит orders сам и не обходит risk gates.

---

## 15. Alpha Radar settings and defaults

Default Alpha Radar settings:

```text
enabled: true
manualQueueOnly: true
autoConfirmOrders: false
allowHypothesisEntries: true
maxIdeasPerCycle: 2
minIdeaScore: 0.58
collectorLookbackHours: 24
refreshIntervalMinutes: 30
```

Default feeds включают:

- CoinDesk RSS;
- Cointelegraph RSS;
- The Block RSS;
- Decrypt RSS;
- The Defiant RSS;
- Coinbase Exchange Status;
- Kraken Status;
- Binance Announcements API;
- Coinbase Blog via RSSHub;
- Kraken Blog;
- и другие configured feed rows.

Connectors:

- Telegram;
- Reddit;
- Bluesky.

Market snapshot watchlists:

- macro;
- proxy;
- equity.

Некоторые assets могут быть `monitoringOnly`: они используются как контекст, но не становятся tradable universe.

---

## 16. Alpha Radar collector loops

Запуск: `startAlphaRadarMonitoringPlane()` при server boot.

Есть два collector loop:

### 16.1. Market snapshot collector

Функция: `collectAlphaRadarMarketSnapshotRun()`.

Делает:

1. берёт Alpha Radar settings;
2. берёт latest observation timestamps;
3. берёт Trading Rules и monitored/tradable symbols;
4. получает monitoring ticks по macro/proxy/equity watchlist;
5. объединяет DB market ticks + latest live ticks + monitoring ticks;
6. строит market observation candidates;
7. нормализует в `AlphaRadarObservation`;
8. сохраняет с dedupe;
9. пишет activity event.

Market observations включают:

- source `coinmaster_market_ticks` или source из monitoring profile;
- kind `market`;
- price/change context;
- asset tags;
- topic tags;
- sentiment/novelty/urgency/market alignment;
- rank;
- metadata confirmation fields.

### 16.2. External feeds / connectors collector

Функция: `collectAlphaRadarExternalFeedsRun()`.

Делает:

1. берёт enabled feeds;
2. по cadence определяет due feeds;
3. fetches RSS/JSON/GDELT;
4. парсит items;
5. строит observations;
6. обновляет source runtime state;
7. собирает connector-backed social candidates:
   - Telegram;
   - Reddit;
   - Bluesky;
8. сохраняет observations;
9. пишет activity event;
10. обновляет connector state в settings.

Fetch logic имеет retry/failure summary через `alphaRadarHttp.ts`.

---

## 17. AlphaRadarObservation

Тип: `AlphaRadarObservation`.

Ключевые поля:

```ts
id
kind: 'external' | 'market'
source
sourceType: 'rss' | 'news' | 'market' | 'manual' | 'direct' | 'social'
sourceLayer: 'primary' | 'duplicate' | 'narrative'
sourceClass: 'market' | 'official' | 'newswire' | 'macro' | 'flow' | 'social'
sourceWeight
title
excerpt
assetTags
topicTags
sentimentScore
noveltyScore
urgencyScore
marketAlignmentScore
rank
observedAt
provenance
metadata
createdAt
```

Observation build process:

1. требует title и excerpt;
2. normalizes source/kind/type/layer/class;
3. extracts asset/topic tags from title/excerpt/source + seed tags;
4. detects macro-shock patterns;
5. clamps scores;
6. computes rank.

Rank formula:

```text
abs(sentiment) * 0.20
+ novelty * 0.35
+ urgency * 0.30
+ marketAlignment * 0.15
```

Результат clamp `0..1`.

### Filtering

`shouldFilterAlphaRadarObservation()` отбрасывает low-signal content:

- promo/noise patterns без high-signal topic;
- social noise без asset tags;
- narrative/social без asset tags и high-signal topic.

### Dedupe / retention

Сохранение observations:

- market dedupe через `buildAlphaRadarMarketObservationDedupeKey()`;
- external dedupe через `source|title.lowercase|observedAt`;
- observations сортируются по `observedAt desc`;
- cap — до 2000 в DB после save path.

---

## 18. Alpha Radar source health

Health строится из expected sources + observations + runtime state.

Поля:

```ts
source
kind
sourceType
sourceLayer
sourceClass
sourceWeight
lastObservedAt
ageMs
stale
itemCount
status: fresh | stale | inactive
details
```

Health показывает:

- fresh/stale/inactive;
- source weight/class/layer;
- last observed;
- connector state;
- expected monitoring source status.

Radar UI должен позволять видеть stalled source plane без чтения логов.

---

## 19. Alpha Radar ideas

Функция: `buildIdeaCandidates()`.

Вход:

```ts
observations
ticks
positions
perpContexts?
settings
tradableSymbols
nowIso
```

Ключевой момент: `tradableSymbols` берутся из Trading Rules enabled coins.

Idea pipeline:

1. нормализует tradable symbols;
2. строит alias map для asset tags;
3. группирует observations по symbol;
4. берёт latest ticks и tick series;
5. учитывает open positions;
6. считает weighted sentiment/freshness/novelty;
7. считает source confirmation:
   - number of confirmed sources;
   - source types;
   - layers;
   - source classes;
   - primary source count;
8. проверяет macro-shock fast-track;
9. строит market structure snapshot;
10. строит execution levels:
    - trigger;
    - invalidation;
    - targets;
    - expected RR;
11. считает actionability inputs:
    - liquidity;
    - crowding;
    - funding/open interest/volume context if available;
12. считает scores;
13. выдаёт `AlphaRadarIdea`.

### Scores

Основные score components:

- `observationQualityScore`;
- `tradeActionabilityScore`;
- final `score`;
- watch breakout score;
- confirmation score;
- market structure alignment;
- RR component;
- liquidity/crowding bias.

### Verdicts

`AlphaRadarIdea.verdict`:

- `idea` — actionable idea для оператора;
- `watch_breakout` — смотреть, структура ранняя или macro candidate не подтверждён;
- `cash` — защитный/rotation state.

Даже `verdict='idea'` в текущей реализации не означает автоматический exchange order. Это UI/source-plane idea. Для реального execution нужен Radar execution ingest или другой явный handoff path.

### Actionability blockers

Idea может быть заблокирована/понижена из-за:

- structure early;
- no clean breakout/follow-through;
- недостаточно source types;
- недостаточно source classes;
- нет primary source;
- execution map warming up;
- macro shock недостаточно подтверждён.

---

## 20. Alpha Radar API surface

Основные endpoints:

```text
GET  /api/settings/alpha-radar
PUT  /api/settings/alpha-radar
GET  /api/alpha-radar/live
GET  /api/alpha-radar/observations
GET  /api/alpha-radar/ideas
POST /api/alpha-radar/collect/market-snapshot
POST /api/alpha-radar/collect/external-feeds
```

`/api/alpha-radar/live` возвращает:

- open positions;
- pending confirmations;
- monitoring state;
- collector runtimes;
- activity events;
- source health;
- monitoring-only assets;
- `llmMode: on_demand`.

`/api/alpha-radar/observations` возвращает:

- current observations;
- settings;
- connector runtimes;
- summary.

`/api/alpha-radar/ideas` возвращает:

- ideas;
- tracked assets count;
- monitoring-only assets;
- open positions count;
- strongest observation;
- source health;
- connector runtimes.

---

## 21. Execution Radar ingest

Функция: `ingestRadarSignal()`.

Endpoints:

```text
GET  /api/radar/signals
POST /api/radar/signals
POST /api/radar/signals/batch
GET  /api/settings/radar
PUT  /api/settings/radar
```

Payload:

```ts
{
  symbol: string,
  side: 'buy' | 'sell',
  timeframe?: '5m' | '15m' | '1h' | '4h',
  source?: string,
  sourceMeta?: {
    connector?: string,
    kind?: string,
    channel?: string,
    externalId?: string,
    messageTs?: string
  },
  reason: string,
  price: number
}
```

Required:

- symbol;
- side;
- source/source label;
- reason;
- price > 0.

Default timeframe: `15m`.

### 21.1. Dedupe

A RadarSignalRecord is created first with status `ignored`.

Duplicate detection:

- if sourceMeta has connector/kind/channel/externalId, uses structured dedupe key;
- otherwise uses:
  - symbol;
  - side;
  - timeframe;
  - source;
  - reason;
- duplicate window: `RADAR_SIGNAL_DEDUP_MS`, documented as 5 minutes.

Duplicate result:

- new record is still persisted;
- status remains `ignored`;
- `duplicateOf` is set;
- `error='duplicate_signal'`.

### 21.2. Runtime enabled gate

If Radar runtime `enabled=false`:

- record status remains `ignored`;
- `error='radar_disabled'`;
- API returns conflict/rejection style result.

### 21.3. Trading Rules scope gate

Before handoff:

```text
symbol must be enabled in Trading Rules
```

If not:

- status `rejected`;
- `error='symbol_not_monitored'`;
- no order/pending is created.

This is the hard boundary between observe-broadly and trade-narrowly.

### 21.4. Handoff

If not duplicate, Radar enabled, symbol monitored:

```ts
handoffStrategyEntrySignal({
  component: 'radar-ingest',
  strategy: 'radar',
  symbol,
  timeframe,
  side,
  price,
  reason,
  effectiveRules,
  autoConfirm: radarRuntime.autoConfirm,
  sourceLabel: source,
  auditDetails: { radarSource: source, ingest: ingestSource }
})
```

Then record is updated with:

- `status`;
- `pendingId`;
- `orderId`;
- `error`.

Possible statuses:

```text
pending_confirmation
auto_order_placed
rejected
ignored
```

---

## 22. Radar read model / scoring

Файл: `src/server/radarReadModel.ts`.

Это deterministic read-model для history/diagnostics. Он не исполняет сделки.

Score:

```text
candidateScore = statusWeight + freshnessScore + sourceMetaRichness - duplicatePenalty
```

Status weights:

```text
auto_order_placed     -> 40
pending_confirmation  -> 30
ignored               -> 10
rejected              -> 5
```

Freshness:

```text
<= 15 min -> 30
<= 60 min -> 20
<= 4h     -> 10
else      -> 0
```

Source metadata richness:

- connector;
- kind;
- channel;
- externalId;
- messageTs;
- max +10.

Duplicate penalty: `-20`.

Verdict thresholds:

```text
crypto:
  actionable >= 70
  bias       >= 45
  watch      >= 20

commodity:
  actionable >= 80
  bias       >= 55
  watch      >= 30
```

Rejected/duplicate always `ignore`.

`auto_order_placed` always actionable.

Важно: asset class здесь влияет только на verdict thresholds/read-model diagnostics, не на tradable universe.

---

# Part C — Единый путь открытия сделки

---

## 23. Все executable сигналы сходятся в handoffStrategyEntrySignal()

Источники:

1. Engulfing monitor.
2. FVG monitor.
3. Radar execution ingest.

Все они вызывают:

```ts
handoffStrategyEntrySignal()
```

Параметры включают:

- component;
- strategy: `engulfing | fvg | radar`;
- symbol;
- timeframe;
- side;
- price;
- reason;
- effectiveRules;
- autoConfirm;
- sourceLabel;
- auditDetails.

---

## 24. Manual mode: pending confirmation

Если `autoConfirm=false`:

1. считается estimated size через `estimateSignalSize()`;
2. если size invalid — signal ignored/rejected;
3. создаётся pending confirmation через `queuePendingConfirmation()`;
4. проверяется operator bias;
5. pending сохраняется в DB;
6. пишется trade event `signal_detected`;
7. отправляется Telegram notification, если включено;
8. Dashboard показывает блок `Positions to confirm`.

PendingConfirmation:

```ts
id
symbol
side: 'long' | 'short'
strategy: 'engulfing' | 'fvg' | 'radar'
timeframe
reason
price
size
leverage
createdAt
```

TTL pending confirmation:

```text
default 6h, minimum 5m via PENDING_CONFIRMATION_TTL_MS
```

Ограничение:

- один pending на symbol;
- duplicate pending within 60 sec returns existing id;
- новый pending по symbol заменяет старый.

---

## 25. Confirm pending

Подтверждение возможно:

- Dashboard:
  - `POST /api/live/pending-confirmations/:id/confirm`
  - `POST /api/live/pending-confirmations/:id/reject`
- Telegram:
  - `/confirm <ID>`;
  - `/reject <ID>`;
  - inline buttons.

`executePendingConfirmation()`:

1. находит pending;
2. получает current `rulesCache.getEffectiveRules()`;
3. заново проверяет risk gates;
4. если risk blocked:
   - Radar outcome reconcile as rejected, если pending связан с Radar;
   - trade event `signal_rejected`;
   - Telegram rejection notification;
5. выставляет leverage `min(pending.leverage, rules.maxLeverage)`;
6. перед отправкой ордера заново считает allocation size по текущему account state;
7. ставит limit order;
8. если exchange reject:
   - trade event `order_rejected`;
   - Radar outcome reconcile rejected;
   - Telegram order rejected notification;
9. если ok:
   - trade event `order_acknowledged`;
   - Radar outcome reconcile `auto_order_placed`;
   - pending удаляется;
   - ставятся TP/SL;
   - Telegram trade-open notification.

Важно: pending size — это estimate. При confirm размер пересчитывается заново.

---

## 26. Auto mode

Если `autoConfirm=true`:

1. берётся account state;
2. equity должен быть > 0;
3. берётся instrument meta / sizeDecimals;
4. считается allocation size;
5. проверяются risk gates;
6. ставится limit order;
7. пишется audit;
8. если order ok:
   - Telegram trade open;
   - ставятся TP/SL;
   - возвращается `auto_order_placed`;
9. если order rejected:
   - Telegram order rejected;
   - возвращается `rejected`.

---

## 27. Allocation sizing

Функция: `computeAllocationSize()`.

Формула:

```text
targetMarginUsd = equityUsd * allocationPct / 100
requires availableUsd >= targetMarginUsd
marginUsd = targetMarginUsd
notionalUsd = marginUsd * maxLeverage
size = floor(notionalUsd / price, sizeDecimals)
```

Ошибки:

- invalid price;
- zero equity;
- zero available;
- symbol not enabled;
- zero allocation;
- zero leverage;
- insufficient available margin;
- computed size zero.

Важный нюанс:

- auto sizing трактует allocation `%` как **margin allocation**;
- `maxNotionalForSymbol()` для explicit-size API allocation cap возвращает `equity * allocationPct / 100`, то есть фактически notional cap без leverage;
- это семантическое расхождение между auto sizing и explicit-size cap.

---

## 28. Risk gates

### 28.1. Daily drawdown

`evaluateRiskGates()`:

- берёт account state;
- проверяет, что equity usable for risk;
- создаёт/читает daily DD baseline;
- считает DD%:

```text
(startEquityUsd - currentEquityUsd) / startEquityUsd * 100
```

Если DD >= `dailyDrawdown`:

- risk block `daily_loss_limit_exceeded`;
- `ddLock.active=true`;
- новые entries запрещены;
- reduce-only exits разрешены;
- emergency close all запускается через middleware/watchdog.

Drawdown watchdog каждые несколько секунд:

- проверяет DD;
- активирует hard stop;
- вызывает `emergencyCloseAll('daily_loss_limit_exceeded_watchdog')`;
- продолжает до flat/verified/orders cleared;
- сохраняет settled state.

### 28.2. Portfolio leverage cap

Считает:

```text
portfolioLeverage = totalPositionNotional / equityUsd
```

Если выше `portfolioLeverageCap`:

- non-reduce-only blocked;
- reduce-only allowed.

Сейчас `portfolioLeverageCap = maxLeverage` из Trading Rules runtime.

### 28.3. Symbol allowlist

`symbolAllocationGate()`:

- non-reduce-only order должен иметь symbol enabled in Trading Rules;
- reduce-only/protection-only endpoints skip this gate.

### 28.4. Allocation cap

Для explicit `price + size` order:

- считает current exposure по symbol;
- считает new notional;
- сравнивает с `maxNotionalForSymbol()`;
- если превышает cap — blocked.

См. нюанс allocation semantics выше.

### 28.5. Stale market data

`staleMarketDataGate()`:

- non-reduce-only требует fresh tick;
- reduce-only allowed;
- если validation unavailable — блокирует trade.

### 28.6. Engulfing gate

На manual order endpoints может блокировать вход, если по configured entry TF нет engulfing entry signal.

---

## 29. Order placement and TP/SL

Entry order path использует `exchange.placeLimitOrder()`.

После successful non-reduce-only order:

1. pending по symbol очищается;
2. отправляется trade-open notification;
3. вычисляются TP/SL defaults;
4. ставятся trigger orders.

### 29.1. TP/SL defaults

Функция: `resolveTpSlDefaults()`.

Priority:

1. explicit request SL/TP;
2. runtime Trading Rules defaults.

Для long:

```text
TP = entry * (1 + tpPct / 100)
SL = entry * (1 - slPct / 100)
```

Для short:

```text
TP = entry * (1 - tpPct / 100)
SL = entry * (1 + slPct / 100)
```

Supports up to 3 TP levels.

### 29.2. Trigger order placement

Функция: `placeTpSlTriggerOrders()`.

Делает:

- full-size SL trigger reduce-only;
- TP trigger reduce-only по каждому TP level;
- TP sizes split deterministically;
- если несколько TP — trade регистрируется в `activeTrades` для TP monitor.

---

## 30. TP fill monitor

Функция: `runTpFillMonitorTick()`.

Каждые ~30 секунд:

1. если active trades пуст — пытается восстановить tracking из live exchange orders;
2. получает open orders;
3. смотрит, какие TP order ids исчезли;
4. если первый TP filled:
   - отменяет старый SL;
   - получает remaining position size;
   - ставит новый SL на entry price;
   - отправляет TP notification;
5. если все TP filled:
   - отправляет position closed notification;
   - удаляет trade из active tracking.

Есть защита от ложного SL alert: если SL order исчез, но позиция ещё открыта, система пытается rebound tracking на новый/существующий SL order.

---

## 31. Emergency close

Emergency close используется для:

- daily drawdown hard stop;
- full reverse engulfing exit;
- fallback после failed partial exit/BE SL.

Поведение:

- закрывает позиции reduce-only;
- старается отменить orders;
- verification/retry loops;
- пишет audit/events;
- отправляет result notification.

---

# Part D — End-to-end сценарии

---

## 32. Engulfing signal -> manual pending -> order

```text
Engulfing monitor tick
  -> no open position
  -> evaluate entry TF candles
  -> bullish/bearish engulfing+sweep detected
  -> bias allows direction
  -> debounce passes
  -> handoffStrategyEntrySignal(autoConfirm=false)
  -> estimate allocation size
  -> queuePendingConfirmation
  -> Dashboard/Telegram notification
  -> owner confirms
  -> risk gates
  -> recompute size
  -> place limit order
  -> place TP/SL
  -> TP monitor manages break-even
```

---

## 33. Engulfing signal -> auto order

```text
Engulfing monitor tick
  -> signal detected
  -> bias allows direction
  -> handoffStrategyEntrySignal(autoConfirm=true)
  -> account state
  -> allocation sizing
  -> risk gates
  -> exchange.placeLimitOrder
  -> notify trade open
  -> place TP/SL
```

---

## 34. FVG signal -> pending/order

```text
FVG monitor tick
  -> flat symbol only
  -> evaluate 1h/4h zones
  -> price retraced into configured level
  -> optional sweep/first-touch/confirmation pass
  -> bias allows direction
  -> debounce passes
  -> handoffStrategyEntrySignal()
  -> same manual/auto execution path
```

---

## 35. Radar API signal -> pending/order

```text
POST /api/radar/signals
  -> validate payload
  -> normalize symbol/source/timeframe
  -> create RadarSignalRecord
  -> dedupe check
  -> radarRuntime.enabled check
  -> Trading Rules monitored-symbol check
  -> handoffStrategyEntrySignal(strategy='radar')
  -> pending confirmation OR auto order
  -> update RadarSignalRecord outcome
```

---

## 36. Alpha Radar observation -> idea -> operator action

```text
Alpha Radar collector
  -> market/feed/social item
  -> AlphaRadarObservation
  -> dedupe + health/rank
  -> buildIdeaCandidates()
  -> AlphaRadarIdea in UI
  -> operator may decide to create/submit concrete Radar signal
  -> execution Radar ingest handles actual trade path
```

Current code does not show automatic AlphaRadarIdea -> ingestRadarSignal handoff. Ideas are decision-support/context unless explicitly handed into execution ingest.

---

# Part E — Current constraints, caveats, and risks

---

## 37. Important current invariants

1. Trading Rules enabled coins define tradable universe.
2. Asset class does not expand monitored/tradable symbols.
3. Bias can block otherwise valid Trading Rules signals.
4. Radar execution uses same handoff as engulfing/FVG.
5. Radar execution does not bypass sizing/risk/order logic.
6. Pending confirmation size is only an estimate; confirm recomputes size.
7. Daily DD lock blocks new entries but allows reduce-only exits.
8. TP1/multi-TP handling moves SL to break-even after first TP.
9. FVG entries are HTF-only: `1h` and `4h`.
10. Reverse engulfing is the implemented emergency exit signal.

---

## 38. Known nuances / mismatches

### 38.1. Allocation semantic mismatch

Auto sizing uses allocation `%` as margin allocation:

```text
notional = equity * allocationPct * leverage
```

Explicit-size allocation cap compares exposure to:

```text
equity * allocationPct
```

That means auto and explicit paths do not interpret allocation cap identically.

### 38.2. FVG conservative candle handling

FVG monitor passes closed candles, and `detectFvgZones()` internally uses `candles.slice(0, -1)`. This can effectively ignore the latest already-closed candle and delay detection by one candle.

### 38.3. FVG has no emergency exit

FVG only generates entries. Emergency exit is currently reverse engulfing.

### 38.4. Alpha Radar ideas are not execution records

`AlphaRadarIdea` is not currently a persisted `SignalCandidate` lifecycle entity. Execution history is tracked in `radarSignals`, but Alpha source ideas and execution signals remain separate.

### 38.5. Radar source plane lacks full candidate lifecycle

Current Radar has:

```text
observations -> ideas -> external/API radar signal -> handoff outcome
```

It does not yet have a durable lifecycle like:

```text
candidate -> validated -> actionable -> handed_off -> active -> executed/expired/invalidated/rejected -> postmortem
```

### 38.6. RSS parsing is regex-based

`extractRssItems()` parses RSS/XML with regex and string cleanup. It is practical but not as robust as a proper XML parser.

---

## 39. Useful verification commands

For Trading Rules / Radar adjacent changes:

```bash
npm run check
npm run build
npm run invariants:trading-rules
npm run invariants:engulfing
npm run invariants:fvg
npm run invariants:allocation-sizing
npm run invariants:daily-drawdown
npm run invariants:radar-handoff
```

For Radar specifically:

```bash
npm run check
npm run build
npm run invariants:radar-handoff
```

---

## 40. Practical mental model

Coinmaster should be read as three layers:

### Layer 1 — Observe

- market ticks;
- candles;
- feeds;
- social connectors;
- macro/proxy/equity monitors;
- source health.

Owned mostly by Alpha Radar and live ingest.

### Layer 2 — Decide / Signal

- Trading Rules engulfing;
- Trading Rules FVG;
- Alpha Radar ideas;
- Radar execution signal records;
- bias policy;
- read-model scoring/verdicts.

This layer may produce trade candidates, but does not itself guarantee execution.

### Layer 3 — Execute / Protect

- `handoffStrategyEntrySignal()`;
- pending confirmations;
- allocation sizing;
- risk gates;
- limit orders;
- TP/SL;
- drawdown watchdog;
- emergency close;
- TP fill monitor;
- audit/trade events.

This is the only layer that should touch exchange trading methods for new entries.

---

## 41. Summary

Current Coinmaster architecture is strongest where it keeps execution unified:

- Engulfing, FVG, and Radar all converge into one handoff path.
- Trading Rules define exactly what may be traded.
- Radar observes broadly but execution is constrained by Trading Rules.
- Manual confirmation is the default safety mode.
- Risk gates and DD lock are centralized.
- TP/SL and break-even handling are common post-entry protections.

The main development gap is not source coverage. The system already observes many sources. The main gap is the middle layer between Alpha Radar observations/ideas and execution Radar signals: a persistent, auditable candidate lifecycle with validation, evidence bundles, replay/backtest, and postmortems.
