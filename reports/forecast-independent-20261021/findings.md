# Frozen independent forecasting CHECK results

One CHECK evaluation per frozen method on BTCUSDT/SOLUSDT Bybit linear execution OHLCV, 2026-04-01 through 2026-10-20 UTC. Each method has 9,696 mature forecasts and 48 explicitly censored forecasts. Hourly origins, next-minute entry, 24-hour horizon; no PnL engine.

All calibrated methods underperformed the TRAIN-prefix prior on aggregate forecast loss and direction log loss. CNN had the lowest calibrated pinball among fitted models, but its paired 14-day confidence interval versus the calibrated raw-feature control crosses zero and its actionable coverage is zero. These results do not establish a useful trading edge.

| Method | Raw lower pinball | Cal lower pinball | Raw / cal direction log loss | Direction accuracy | Actionable / 9696 |
|---|---:|---:|---:|---:|---:|
| control | 0.212843 | 0.215153 | 1.091187 / 1.086343 | 36.25% | 5 |
| stumpy | 0.213192 | 0.214897 | 1.092397 / 1.094730 | 37.29% | 223 |
| minirocket | 0.227832 | 0.228982 | 1.178555 / 1.089352 | 37.58% | 23 |
| rdst | 0.218842 | 0.220639 | 1.121466 / 1.088624 | 38.03% | 26 |
| cnn | 0.212336 | 0.214131 | 1.084779 / 1.084759 | 35.71% | 0 |
| TRAIN-prefix prior | 0.212019 | — | 1.080523 | 39.27% | — |

Lower losses are better. March calibration improved some direction losses but increased every method’s aggregate lower pinball relative to its raw prediction. The frozen raw JSON field `vs_raw_control` actually compares calibrated predictions against calibrated raw-feature control; it is named `vs_calibrated_control` in the export summary.

| Method minus calibrated control | Lower pinball difference | Paired 14-day 95% CI |
|---|---:|---|
| stumpy | -0.000256 | [-0.001902, +0.001313] |
| minirocket | +0.013829 | [+0.011388, +0.016325] |
| rdst | +0.005485 | [+0.002609, +0.008271] |
| cnn | -0.001022 | [-0.001948, +0.000038] |

Negative differences favor the method. STUMPY and CNN intervals include zero; MiniRocket and RDST are worse than control on this comparison. Overlapping 24-hour forecasts are summarized using 15 paired 14-day blocks with 1,000 fixed-seed bootstrap draws; this is a finite CHECK sample.

| Method | Asset | Actionable N | TP1 lower–upper hit | TP2 lower–upper hit | TP3 lower–upper hit |
|---|---|---:|---:|---:|---:|
| control | BTCUSDT | 0 | — | — | — |
| control | SOLUSDT | 5 | 80.0%–80.0% | 40.0%–40.0% | 20.0%–20.0% |
| stumpy | BTCUSDT | 49 | 75.5%–75.5% | 34.7%–34.7% | 6.1%–6.1% |
| stumpy | SOLUSDT | 174 | 73.6%–73.6% | 36.2%–36.2% | 9.2%–9.2% |
| minirocket | BTCUSDT | 7 | 85.7%–85.7% | 28.6%–28.6% | 0.0%–0.0% |
| minirocket | SOLUSDT | 16 | 56.2%–56.2% | 12.5%–12.5% | 0.0%–0.0% |
| rdst | BTCUSDT | 8 | 75.0%–75.0% | 37.5%–37.5% | 12.5%–12.5% |
| rdst | SOLUSDT | 18 | 72.2%–72.2% | 38.9%–38.9% | 0.0%–0.0% |
| cnn | BTCUSDT | 0 | — | — | — |
| cnn | SOLUSDT | 0 | — | — | — |

TP levels are learned MFE quantiles (.2/.5/.8) anchored to actual entry; hit bounds account for stop/target ordering within minute bars. Small actionable samples are descriptive. Continuous calibrated targets would imply nominal exceedance 80/50/20%; actual zero masses/ties and execution paths prevent interpreting these as guaranteed hit probabilities. Each method’s quantile-tie-coverage.json retains strict and nonstrict exceedance and exact zero/tie counts.

All-origin asset/month metrics are in metrics-by-asset-month.csv; original full results, every forecast row, observed target bounds, probabilities, censor flags, receipts, hashes and deterministic examples are retained. A missing first-actionable example means no qualifying forecast for that asset/method, rather than a missing successful example. No model, calibration or selection was changed after CHECK.

The descriptive actionable-entry cohorts are retained in actionable-entry-cohorts.csv: each method/asset reports evaluated N, terminal direction correctness, prefix-prior and calibrated-control accuracy on exactly the same IDs, and unique UTC origin days. These selected subsets must be compared on matching IDs; all-origin 39.27% prior accuracy is not their cohort benchmark. Neutral terminal outcomes count as incorrect for long/short entry signals. CNN has N=0 and UNKNOWN cohort accuracy; small overlapping cohorts do not establish significance.


## Разбор причин и предложение следующего шага — 21.10.2026

Статус: анализ существующих артефактов завершён; **новые прогоны/обучения/код не разрешены и не запускались**. Пилот не затрагивается. Следующее исследование требует согласования; завершённые forecasting и EV-03 остаются завершёнными.

### Что установлено, а что остаётся объяснением

- MiniRocket/RDST проигрывали уже во внутренней TRAIN-валидации: lower pinball 0.236220/0.223347 против контроля 0.214813. Поэтому свести неудачу к переобучению или смене рынка нельзя. Причины внутри представления/оптимизации отдельно не идентифицированы; заключение относится к проверенным ограниченным рецептам, не всему семейству методов.
- STUMPY TRAIN 0.215400, CHECK calibrated 0.214897: сходство графиков найдено, устойчивого преимущества не установлено. Разница с calibrated control −0.000256, CI пересекает ноль. На выбранных SOL-ID точность направления 36.78% против prior 44.83%; это более корректное сравнение, чем общий prior на всех часах.
- CNN TRAIN 0.213831, CHECK calibrated 0.214131: лучшее качество уровней среди моделей, но CI против контроля включает ноль, входов по общему замороженному gate — 0. Ноль не доказывает отсутствие любых паттернов и не оправдывает снижение порога после CHECK. Это малая crypto-адаптация авторской stock-classification идеи, не её точная репликация.
- Мартовская коррекция улучшала мартовскую ошибку TP всех методов, но ухудшила каждую CHECK-ошибку примерно на 0.00115–0.00231. Это измеренный провал переноса калибровки. Конкретный рыночный режим как причина не установлен. Отключение калибровки недостаточно: raw-оценки тоже уступили prior по общей точечной оценке.
- Прогноз terminal direction, MFE до SL/24h и решение, как управлять портфелем, — разные цели. STUMPY SOL даёт 73.6% касаний TP1 при 36.78% правильных terminal directions. Ни одно число не является net win rate, ожидаемой доходностью после издержек или снижением DD. 9696 часовых прогнозов перекрываются; блоков неопределённости всего 15.

Источники чисел: train-sequence-progress.json, findings.md выше, actionable-entry-cohorts.csv. Общая поддержка ограничений первичными источниками: [MiniRocket](https://arxiv.org/abs/2012.08791), [RDST](https://arxiv.org/abs/2109.13514), [chart CNN](https://economics.yale.edu/research/re-imagining-price-trends), [calibration](https://proceedings.mlr.press/v70/guo17a.html). Публикации classification не доказывают перенос на нашу crypto/TP/DD-задачу.

### Что переносится в работу с S0

Переносится готовая инфраструктура реальных минутных данных, причинные окна/volatility scaling, purge, сопоставление тех же ID, раздельные raw/cal оценки, блоковая неопределённость, экспорты и визуальный разбор реального lifecycle. STUMPY допустим как описательный поиск похожих состояний, не подтверждённый торговый сигнал. CNN-картинки полезны для аудита, но оснований повторять её обучение или менять по ней S0 нет. Прогнозные вероятности и TP не переносятся в пилот.

Не повторять уже закрытый EV-03: BTC risk-prior log loss 0.630220456 против rule 0.650978627 / logistic 0.720974983 / STUMPY 0.707928969; все хуже. SOL имел всего 5 пригодных TRAIN/6 CHECK-событий и не прошёл support. См. ../btc-sol-event-risk-20261021/ev03-result.md и ev02-result.md. Неиспользованные 0/4 native-слота не являются разрешением новых гипотез.

### Экономический ориентир и реальные причины DD

S0 TOTAL 6,077,107.23887483, seed 10,000. Сохранить 90% **чистой прибыли** означает TOTAL >= **5,470,396.514987347**, а не 90% исходного TOTAL. Разрешённое снижение terminal TOTAL относительно S0 — 606,710.723887483; это конечный критерий, не бюджет суммы исключённых сделок.

По существующему полному native-phase отчёту S0 DD=66.3187802497%; по отдельно проверенной согласованной денежной проекции W=66.2569148647%. Условная OHLC-граница 67.54771032% — другая оценка. Сравнение обязано сохранять одинаковый observer и показывать обе native меры; менять observer незаметно ради улучшения DD нельзя. Tick-предел не доказан.

| Эпизод | DD native-phase | Сохранённые денежные факты | Что требуется от действия |
|---|---:|---|---|
| Sep–Oct 2024 | 66.32% | В согласованной проекции SOL long теряет около 5.2–5.6k при положительном BTC short; также снизился cash | Не сокращать прибыльный BTC вслепую; проверять усиление убыточного SOL |
| Apr–Jun 2025 | 59.84% | Cash −407,279.98, UPnL −140,386.10; на дне BTC-only | Защита только уже полученной прибыли может не покрыть цепочку потерь |
| Oct–Nov 2025 | 55.10% | BTC-only на концах: UPnL +225,132.08 → −938,216.47, cash +12,589.12; количества отличаются | Проверять своевременное сокращение BTC-остатка при развороте |

Источники: ../winner-6077107-stats/{README.md,risk-statistics.md,trades-report.md}, ../fast-rnd-20261020/s0-drawdown-attribution-result.md. Из конечных состояний не следует точная причинная ценность альтернативного выхода. Signed funding и полная native realized-атрибуция по активам неизвестны; разницу денежных итогов не называть funding.

Не повторять общий SOL cap/постоянный хедж: ранее exact-S0 cap50 дал TOTAL3,314,315.93/DD58.02%; DD/cov 4,046.59/70.54%; split/ATR 113,562.55/93.92% с liquidation. Исходный SOL имеет 22 прибыльные/4 убыточные flat-to-flat сделки; blanket-ограничение отрезает важный compounding. Trade PnL в общей траектории не равен standalone SOL ROI. Источник ../sol-risk-first-20261018/README.md.

### Один следующий пакет для согласования: проверка применимости двух механических действий

**Сначала только сохранённый lifecycle, без ML и native engine.** Проверить все подходящие состояния, обычные и прибыльные контрпримеры, а не только известные дни провала. Сформировать таблицу: доступное действие/действительные исполненные TP/текущая экспозиция/положение в DD/успевает ли действие до 50%/последующий исход исходной S0. Это mechanism screen, не контрфактический ROI.

Два ограниченных кандидата для этого screen, не готовые победители:

1. BTC: после фактического прибыльного по цене TP (нулевые TP1/TP2 сами по себе не активируют защиту) и последующего благоприятного движения остаток возвращается к текущей native средней входа; при отсутствии SOL сократить 50% остатка один раз на parent. Не сокращать сам факт входа, не переоткрывать освобождённый объём, не создавать SOL-права от risk-reduction. Исходные mandatory exits приоритетны. Сравнить с хорошими сделками, которые возвращались к входу и затем давали основную прибыль. Это не повтор DD/UPnL-классификатора EV-03; экономическая ценность ещё неизвестна.
2. SOL: вместо постоянного cap проверить запрет **очередного** добора, когда существующий SOL уже убыточен и его native открытый убыток превосходит положительный native PnL BTC, а общая equity уже ниже своего пика. Право пропускается однократно без часового retry; остальные входы/выходы SOL сохраняются. Условие — предварительный кандидат, не выбранный оптимум. Оно не ограничивает первоначальный SOL-вход и может пропускать полезное усреднение; screen должен проверить, имеется ли вообще ранний подходящий добор в худшем эпизоде. Уровень DD и величина действия до native-прогона требуют отдельной фиксации, не подбора по CHECK.

Эти действия сами по себе не доказаны способными исправить все три >50% эпизода. Если не успевают вмешаться, задевают основную прибыль либо невозможно доказать predecision-state/rights/ordinary-branch availability из сохранённых данных — результат screen отрицательный/конкретный пробел; не тратить 24m запуск и не подменять отсутствие state предположением. При необходимости нового replay сначала отдельное согласование, S0 сейчас не пересчитывать.

Только после screen, фиксации точных правил и нового согласования: не более H-BTC/H-SOL отдельных native-прогонов, условного совместного и fresh-engine повтора — максимум 4. Совмещение только если каждый отдельный снижает DD и сохраняет >=90% net profit S0. Ни один прогон не обещан заранее: предел4 не обязан быть израсходован. Финальный выбор TOTAL>=5,470,396.51 и глобальная DD<=50%, затем максимум TOTAL. Комиссии/funding/margin/native исполнение и реинвестирование одинаковы; будущие абсолютные Q закономерно меняются с equity, исходная BTC entry/sizing-формула сохраняется. Старый S0 переиспользуется, пилот неизменён. Это предложение, не запущенный этап.
