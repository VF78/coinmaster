# BTC 50/50 и SOL-cover: результаты исследования

Дата: 18 октября 2026. Это результаты native-симулятора на исторических Bybit execution/mark 1m за **[2024-09-01, 2026-09-01)**, а не доказательство исполнения или доходности на Hyperliquid. Начальный капитал — 10 000 USDT. Четыре канонических потока по 1 051 200 строк проверены по SHA-256; пропуски и дубликаты отсутствуют.

**Выбран седьмой вариант `BTC025_PLANREF_V1_POSITIVE_TP_NATIVE_IOC`: TOTAL 6 077 107.23887483 против V3 5 437 208.56951095, прирост 639 898.66936388 (+11.7689%). Global marked DD снизился с 67.2863% до 66.3188%.** Это победитель выполненного исторического сравнения, не разрешение на production/live. **Результат при DP=OFF не является прогнозом ROI для live DP50: такой перенос отдельно не рассчитан.**

**Финальный восьмой fresh-repeat: PASS.** Отдельные native engine и funding SQLite повторили TOTAL, fees, 621 fills, 710 orders, 105 plans, параметры, данные и зафиксированные risk structures точно: 26/26 checks, 1320/1320 funding rows. Все 85 source files совпали. Raw minute trace bytes/rows не сравнивались; UUID/path/RSS исключены явно.

[Final repeat verification](final-repeat-verification.json) · [Отдельный repeat receipt](btc025-planref-tp-ioc-repeat-receipt.json). SHA-256 verification: `9284fc17abd03d73de77a69055435c242976f24a5ed75ffe0631c53d68449046`. Raw result hashes различны из-за новых UUID/путей; экономические поля совпадают точно.

## Все выполненные варианты

TOTAL — native ACTIVE+RESERVE после terminal settlement; terminal callbacks на exclusive end учитываются отдельно от интервальных DD. DD — глобальная marked equity по всем native minute-close фазам. Последний столбец риска — **условный** предыдущий favorable upper → строго более поздний adverse lower из OHLC; это не установленная внутриминутная траектория.

| Вариант | TOTAL, USDT | Marked DD, % | Условный OHLC DD, % | Minimum equity | BTC parents |
|---|---:|---:|---:|---:|---:|
| V3, контроль | 5 437 208.57 | 67.2863 | 68.4920 | 4 514.70 | 105 |
| BTC 0.25%, 4h, blended management | 4 759 384.60 | 77.9382 | 78.7352 | 2 990.60 | 104 |
| BTC 0.50%, 4h, blended management | 4 379 050.17 | 77.6497 | 78.4514 | 3 030.53 | 104 |
| SOL base 50% | 21 765.87 | 56.4035 | 58.2977 | 7 556.56 | 105 |
| SOL 50% → 75% tactical | 23 826.62 | 55.3452 | 56.7568 | 7 371.61 | 105 |
| SOL 50% → 100% tactical | 26 111.23 | 54.3439 | 55.4116 | 7 178.40 | 105 |
| BTC 0.25%, PLANREF | 6 005 487.81 | 70.4734 | 70.8565 | 4 530.57 | 105 |
| **BTC 0.25%, PLANREF + TP IOC** | **6 077 107.24** | **66.3188** | **67.5477** | **4 530.57** | **105** |

Во всех строках зарегистрировано 0 ликвидаций. DP выключен одинаково в исследовании. Историческая применимость margin tiers и достоверность venue liquidation/intrabar модели не подтверждены; нулевой счётчик не доказывает отсутствие риска ликвидации. DD 66.32% также не означает соблюдения какого-либо лимита потерь 50%.

Полные значения, ROI, lots, все комиссии/обороты и пути raw: [native table CSV](comparison-analysis-native-table.csv), [JSON](comparison-analysis-native-table.json), [ликвидность/комиссии](comparison-analysis-native-liquidity.csv).

## Точный алгоритм победителя

Исходник: `759823d69a74e72b123add5ae775dd8c3aed4ac5`. Полный замороженный набор — [resolved parameters](btc025-planref-tp-ioc-resolved-parameters.json); [receipt с SHA и source/input checks](btc025-planref-tp-ioc-receipt.json).

1. Сохраняются исходные V3 permissions, направления, q0/q1, zero-level/netting, gross referenceQ и принятый netQ. Sizing: long 5.5, short 7.875, максимум parent notional 30 млн. После биржевой нормализации acceptedQ делится в лотах: первая часть `max(1, floor(lots/2))`, остаток — второй child; один лот исполняется сразу.
2. Первая часть исполняется немедленно. `P0` — фактический native VWAP **полностью исполненной первой части**. Второй child: long `P0×0.9975`, short `P0×1.0025`, с исходным биржевым округлением. Дедлайн — `min(start+4h, следующий UTC-день−1min)`; отмена/известный ACK предшествуют исполнению остатка. Mandatory close имеет приоритет.
3. `PLANREF_V1` фиксирует P0 только для TP, daily fallback, TRAIL/best_f и early-TP management. Реальные native cash/VWAP/PnL/fees не переписываются. **H = grossReferenceQ × actual blended entry VWAP / beta**, без подмены blended VWAP на P0.
4. Положительный TP до завершения parent ускоряет только оставшийся entryQ через существующий executor. После полного завершения parent уже пройденный положительный target исполняется штатным **native reduce-only MARKET/IOC** в пределах действительных позиции/target leaves. Комиссия — фактическая TAKER. Unknown ACK/partials обрабатываются исходной очередью; права не выдаются за одну отправку заявки.
5. Старый SOL-overlay включён; SOL-cover выключен. Исходные параметры SOL: opposite BTC, beta 270d, H-множители 1.75/2.625/3.5, z-entry 1.25/2.5/3.75, half/all exits 0.375/0.125, timeout 14d. BTC TP-доли исходного плана 0.2125/0.2125/0.575, EMA34, daily profit-trail 3%; новых фиксированных SL не добавлено. **15m early confirmation и runaway guard выключены и native не запускались.**

Все **105** контрольных дат/направлений, q0/q1, первых реальных котировок и P0/timestamps совпали. Все 105 accepted plans полностью исполнены: **14 864 943 planned = filled BTC lots по 0.001 BTC, cancelled 0**. H и actual blended VWAP сверены независимо по fills; максимальная относительная ошибка H — 3.04e−16. Это сохранение acceptedQ каждого собственного причинно рассчитанного плана после q0/q1-нормализации, а не одинаковых абсолютных размеров всех 105 сделок между runs; будущие абсолютные количества между compounding runs закономерно меняются вместе с equity. Цены/размеры/задержки не подменялись контрольным списком будущих сделок. TP fill paths не обязаны совпадать: у победителя 22 parent exit-time списка отличаются от V3.

## Фактическая стоимость и причина улучшения

Для победителя, по native fill-report `liquidity_side`, `filled_qty`, `avg_px`, `commissions`:

| Исполнение, все активы | Turnover, USDT | Фактические fees, USDT |
|---|---:|---:|
| MAKER | 769 383 840.63 | 153 876.76812554 |
| TAKER | 1 440 092 671.80 | 792 050.96949271 |
| Всего | 2 209 476 512.43 | 945 927.73761825 |

BTC fees — 927 666.95630420; SOL — 18 260.78131405. Тариф исследования одинаков для контроля/кандидатов: Bybit maker 0.020%, taker 0.055%; историческая применимость тарифа UNKNOWN. IOC не объявлялся maker по типу заявки. BTC entries: 66 реальных maker и 149 taker fills; 66 limit / 17 deadline / 22 early-TP parent completions. Среднее ожидание второй части 1.395h, максимум 4h1min с фактическим завершением очереди после deadline. Среднее нормированное улучшение полной entry cost +4.5178 bp: цена +3.4175, entry fees +1.1003 bp. Это сравнение исполнения, **не прибавка proxy к native TOTAL**.

В шестом PLANREF после early-TP completion пропускался уже пройденный post-only TP: 11 апреля TP2 контроля исполнился 00:04, Q2 кандидата завершился 00:05; 6 июня — TP2 00:13 против завершения Q2 00:14. На следующей котировке post-only target уже marketable, поэтому reduction отсутствовал. Это сохраняло избыточную позицию до позднего REGIME. В седьмом реальные IOC catch-ups закрыли TP2 11 апреля в 00:06 и 6 июня в 00:15; marked DD периода апрель–июнь снизился до 59.8427% против V3 62.2527% и шестого 70.4734%. Глобальный худший период снова сентябрь–октябрь 2024.

Все 13 catch-up audits сопоставлены с фактическими reduce-only MARKET/IOC/TAKER fills; target lots и доступная native позиция соблюдены. Их turnover 19 170 495.9316, fees 10 543.77276239 **уже входят** в таблицу выше. Положительный P0-target не гарантирует прибыль после fees: 7/13 аналитически распределённых закрытий убыточны, суммарно −1 817.86 после распределённых entry/exit fees.

Подтверждённая fill-attribution победителя: BTC net ex funding **5 345 694.48879580**, SOL **678 661.20768595**. Метод — weighted entry/proportional fee allocation, не отдельный authoritative native cash по активам. **Signed funding UNKNOWN.** Разница native cash и этой атрибуции **42 751.54239308** остаётся unallocated; она не названа funding и не приравнена нулю. Поминутное разложение asset-uPnL не использовано как доказательство риска.

Детали: [summary](comparison-analysis-btc025-planref-tp-ioc-summary.json), [parent validation CSV](comparison-analysis-btc025-planref-tp-ioc-validation.csv), [13 catch-ups](comparison-analysis-btc025-planref-tp-ioc-catchups.csv).

## Почему SOL-cover не выбран

Base50 обеспечивает SOL-position присутствие на 100% BTC-held fill-event интервалов. Actual beta-coverage в 45–55%: 99.9779% / 98.5245% / 98.5218% времени для 50 / 75 / 100; среднее 49.99% / 50.34% / 50.70%. 75/100 — редкие **тактические** цели поверх постоянных 50%, а не постоянный хедж всего периода. Все 105 BTC dates/sides/q0/q1/quotes совпали с V3, но 104 абсолютных Q изменились через equity.

Постоянная база доминирует по opportunity cost: CORE allocated net −62 161.95 / −66 149.79 / −70 496.11. Тактика дала 0 / +2 061.76 / +4 358.65 (по 27 циклов в двух вариантах, 25 выигрышей/2 проигрыша), но не восстановила исходный TOTAL. На убыточных BTC-эпизодах SOL помог в 39/48 либо 41/48; на прибыльных BTC он терял в 55/57. Это измеренная стоимость постоянного встречного hedge, не fee-only объяснение и не доказательство гарантированной защиты. Dollar differences между вариантами включают BTC/CORE compounding; CORE/tactical — явно указанная неединственная TACTICAL-first атрибуция fills, не две native позиции.

Реальное заполнение тоже существенно: после BTC TP3 2 апреля 2026, 13:36 покрытие SOL100 достигло **153.73% на одну минуту**, SOL75 — 87.32%. Правильный новый base target уже был выставлен, но IOC reductions исполнялись частями из-за **синтетического displayed quote size SOL=1000** и повторялись на следующих котировках. Это не instrument max quantity и не проверенная venue depth. Target cap не является непрерывным actual cap; у SOL100 время >100% — 0.29925% BTC-held. Нулевое actual coverage — 0 во всех трёх случаях.

First SOL fill имеет тот же модельный timestamp во всех 105 случаях, но завершение начального base budget задерживалось у 13/19/22 parents до 60/60/120s. Это не гарантия мгновенного хеджа на реальной площадке. Coverage вычислена из **actual native fill-event net quantities + canonical marks + frozen beta**, а не запаздывающих cache snapshots.

[Общий SOL вывод](comparison-analysis-sol-conclusion.json), [точные cap excursions](comparison-analysis-coverage-cap-findings.json), [SOL50](comparison-analysis-sol50-actual-fill-coverage.json), [SOL75](comparison-analysis-sol75-actual-fill-coverage.json), [SOL100](comparison-analysis-sol100-actual-fill-coverage.json).

## Что эти проверки доказывают — и не доказывают

P0 использовал все 105 BTC-дней и противоположный SOL на каждом из них. До входа не брались будущие extrema, подтверждения строились по закрытым барам. Фактический допуск/fill — anchor; будущий BTC close использован только для offline active-interval оценки, не как сигнал. Entry-day excursions и whole-episode MAE различаются.

Исходный дешёвый screen 0.25%/4h OFF: первые 12 месяцев — 57 parents, +3.0965 bp gross whole-BTC price; следующие — 48, +5.0161 bp. Поздняя часть ранее просматривалась: это **sensitivity, не честный OOS**. Ни ценовой screen, ни сравнение уже просмотренных native runs не заменяют нового forward.

Модель использует 1m close quotes без L2/trade-tape/spread/slippage доказательства, displayed size BTC=1000/SOL=1000 и native partial/cancel-ACK. OHLC upper/lower — условные диагностические endpoints, не полный intraminute path. Native деньги/fees/проверки не переписывались отдельным PnL engine.

## Артефакты и Hyperliquid qualification

В GitHub находятся компактные CSV/JSON, receipts, параметры и этот отчёт. [Analysis manifest](comparison-analysis-manifest.json) фиксирует 107 frozen analysis artifacts; README намеренно не добавлен в уже замороженный manifest. [P0 manifest](manifest-screening.json) связывает исходные данные и статистику. Полные VPS raw JSON, fills/orders, gzip minute trace и funding SQLite остаются в job directories, например:

`/var/lib/coinmaster-native-gui/data/runs/jobs/cm115-split-btc025-planref-tp-ioc-20261018a/result/`

Их точные пути/SHA перечислены в receipts и native table; тяжёлые raw traces не заменены выборочными GitHub цифрами. Восьмой repeat сохранён отдельным receipt; исходный результат не заменён.

**HL blocker #101 остаётся открытым.** [Аудит официальных источников и запросов](coverage-hyperliquid.json): публичный 1m snapshot на момент проверки возвращал только BTC с 2026-10-14 21:00 UTC, SOL с 21:12 до 18 октября. Daily bars 2022 с нулевыми trades/volume не являются историей исполнения. Первые возвращённые в проверенных запросах positive-volume daily records — BTC 2023-02-26, SOL 2023-03-04; первые возвращённые funding records обеих монет — 2023-05-12. Это границы результатов проверенных запросов, не доказанные даты листинга, начала funding или полного архива. Полная непрерывность funding и исторических mark/L2 архивов не подтверждена. Официальные S3 archives requester-pays, могут иметь пропуски; платных загрузок/credentials не использовали. Native HL backtest 2022-09-01…сегодня не выполнен, Bybit не подменял HL.

Минимальная последующая квалификация:

1. **Выполнено:** fresh-repeat той же source/config/data/policy с новым engine/journal, точное совпадение экономических fills/orders, permissions, totals/fees и записанных risk structures; отдельные receipts сохранены. Бюджет8/8 full runs завершён; девятый запуск не выполнялся.
2. Закрыть data gap: получить разрешённые actual HL execution/mark/funding records, установить earliest dates и gap/hash manifest; отдельно проверить HL lot/tick/min-notional, USDC accounting, реальные комиссии и liquidation/margin rules. Непокрытые диапазоны оставить UNKNOWN.
3. Квалифицировать нового победителя на существующем native runner: HL partial fills, cancel/ACK races, positive-TP IOC, mandatory close, достаточность маржи acceptedQ/H, close/DD и signed funding. Переход к новому алгоритму допустим только на flat boundary; виртуальные позиции не создаются, разрешение на live orders из исследования не следует.
4. Переиспользовать существующий контур: 82 USDC, DP50, неактивный trader `6c208fd` и GUI `be2f71d`. Существующие ручная reconciliation и отложенный open/restart сохраняются; отдельный recovery project, новые stop/services или дополнительные общие gates не требуются. Изменения и активация нового победителя требуют отдельного решения владельца после квалификации на flat boundary. В этом исследовании trader/services/GUI/live config не активировались и реальные ордера не отправлялись; пополнение средств не запрашивается.

Официальные HL ограничения: [historical data](https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data), [info endpoint](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint), [funding](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals).
