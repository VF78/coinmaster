# BTC lifecycle: точный S0, сохранённые данные

Контроль native TOTAL **6077107.23887483** неизменён. Новых native runs, replay, расчётов альтернативной equity и чтения минутного рынка/trace: **0**. Точный audit SHA256 `e7854784dce9bcf27e77d45ebe12873d78a42a0ecb43b3686f2a0da810fb2bfa`; источники с локальными SHA — в JSON.

**Предпосылка «S0 мгновенно исполняет нулевые BTC TP на входе» не подтверждается:** ни один из155 фактических BTC reductions не совпадает ни с первым входным fill, ни с завершением split entry. Нулевой расчётный уровень, пропуск заявки и фактическая цена исполнения различаются.

105 BTC интервалов:53 LONG/52 SHORT;57 прибыльных/48 убыточных по диагностическому net ex funding. Это105 интервалов,210 входных fills и155 reduction fills, а не105/155 ордеров. Всего BTC416 fills, все активы621. Подписанный funding не распределён.

Все105 planned native quantities исполнены полностью, по2 входных fills. Между q0/q1:60s. Управляющий P0 заморожен на VWAP первого плеча; окончательный blended VWAP отличается. Завершение split:66 LIMIT_NATIVE (нет отдельного completion_reason),22 EARLY_TP,17 DEADLINE. Задержка от первого fill до завершения: median42min/p75 137min/p90=max241min. Native input/reference/quantity по каждому интервалу — CSV.

45 PASSIVE_NET_ZERO_LEVELS и60 MARKETABLE_FULL_ENTRY_FALLBACK. В45 PASSIVE пропущено76 **слотов**:45 TP1 и31 TP2; это не76 мгновенных fills. Полный frozen wavevector FULL-entry не экспортирован, поэтому generic reason не доказывает zero-wave fallback. Индексы0/1/2 соответствуют TP1/2/3; исходные доли .2125/.2125/.575, wave quantiles .1/.3/.6.

| Фактический reason | Fills | Maker/taker | Median задержки после полного entry | Положительная цена vs P0 / blended | Положительный diagnostic net |
|---|---:|---|---:|---:|---:|
|BTC_REDUCE|73|{'TAKER': 73}|1414.0min|73/73|73|
|BTC_TP2|28|{'MAKER': 15, 'TAKER': 13}|2.5min|28/27|16|
|BTC_TP3|54|{'MAKER': 54}|2936.0min|54/54|54|

Generic73:42 L0/31 L1, все позже завершения входа более чем на60s; ни одного равного P0/blended или в пределах1bp. Все TP3 —54 maker fills. TP2 —15 maker+13 native IOC/taker;13 IOC выполнены в пределах60s после завершения, но не одновременно с ним. Все28 TP2 положительны относительно P0,27 относительно blended. Один TP2 ближе1bp к blended. У13 IOC7 отрицательных диагностических net allocations, сумма−1817.861394 USDT ex funding. Положительный reference-TP не гарантирует положительную доходность после реальных комиссий.

Diagnostic net = signed(fill−completed native blended VWAP)×qty − пропорциональная фактическая entry commission − actual exit commission. Это распределение сохранённых fills, не authoritative native per-asset cash и не альтернативный PnL.

| MAE, % цены: median / p75 / p90 / max |57 winners|48 losers|
|---|---|---|
|15m, observed prefix|0.1251 / 0.2072 / 0.2999 / 0.5531|0.0825 / 0.2012 / 0.3174 / 0.5666|
|60m, observed prefix|0.2132 / 0.4086 / 0.6712 / 1.1290|0.2450 / 0.4035 / 0.5744 / 1.5005|
|1440m, observed prefix|0.8136 / 1.5724 / 2.1594 / 4.2907|1.6355 / 2.7440 / 4.6217 / 5.8737|
|Whole native-current-average basis|0.9900 / 1.8999 / 3.2804 / 7.7683|2.5203 / 3.6597 / 5.3507 / 7.9350|

**Привязка и цензура:**15m/1h/24h взяты из уже сохранённого close-only price study, от синхронного execution1m close в момент первого native входа, не от blended fill. Горизонт прекращается при исходном native exit.15m/1h все105 полные;24h цензурированы38 (17 winners/21 losers). Для полных24h: winners n40, MAE median1.0269%/p90 3.2856%; losers n27, median .9937%/p90 2.6349%. Цензура информативна: clipped и complete-only — разные выборки. Whole экстремумы используют сохранённые native close marks / текущий average_open, изменяющийся при split fill; их нельзя непосредственно смешивать с фиксированным close anchor. Все MFE quantiles и individual rows сохранены в JSON/CSV. Intraminute high/low здесь не использованы.

MAE строго до первого фактического TP: **UNKNOWN_NOT_EXPORTED**. Численные causal entry EMA-distance/ATR/slope: **UNKNOWN** в использованных тонких exports. Старые исследовательские лестницы/BE из chop-study не являются native S0 TP и в реальные TP counts не включены.

Final flat reasons:REGIME48, BTC_TP3 39, generic BTC_REDUCE15, TRAIL2, terminal boundary1. Fixed BTC close stop=null, portfolio loss limit=null; BTC close trail=.03. Два native TRAIL exits подтверждены, полные условия arming не выводились из audit.

У прибыльных BTC whole MAE p90=3.2804%, max=7.7683% на native-current-average mark basis. Это существенный контрпример к механическому tight fixed SL. Будущий SL остановил бы наблюдение до последующих recovery/TP/exit и изменил капитал; данные не доказывают оптимальный SL, альтернативный TOTAL или DD. Никакой порог не подбирался.

Полные pins, определения метрик,105 индивидуальных интервалов и155 execution rows — `btc-statistics.json`;105 интервалов — `btc-statistics.csv`.
