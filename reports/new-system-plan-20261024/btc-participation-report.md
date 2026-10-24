# A: actual BTC participation/history audit

**A = NO_GO. Новый поддержанный источник восстановления BTC participation/раннего капитала не найден; H_PAIR_EXIT пока не допущен.** Native already использует полный730-дневный feature warmup и first-child P0. Возврат «утраченного warmup», смена VWAP обратно на P0 или восстановление grossQ через старую zeroTP-семантику не являются новой подтверждённой гипотезой. Данные объясняют потерю собственного капитала при удалении SOL, но не дают способа вернуть этот капитал строгим хеджем.

Один focused saved-data pass и одна арифметическая verification PASS. Повторных engine/full/short/simulator/training запусков0; продукт/пилот/runtime/Project/sharedstate не менялись. Старые бюджеты закрыты.

## Контроли, история и TP

Проверены exact E4 receipt/raw/export hashes и принятые R1/R2/R3 raw/cycle/fill/trace receipts. У всех83parents совпадают first-entry timestamps/sides; quantities, native equity, fees и funding каждого варианта собственные.332 родительских строк имеют measured own settled equity на q0. Четыре сохранённых trace прочитаны по одному разу,1051199 receipts каждый; новый matching или equity replay не создавался.

У E4/R1/R2/R3 source/config/data подтверждают `warmup=[2022-09-02,2024-09-01)` feature-only,730дней, wave_history730, min_count8, quantiles.1/.3/.6; обе pinned daily таблицы1460строк. Native runner имеет явный guard против warmup<730дней. Причинный TP3 — исходный q60 completed-wave MFE, завершённые волны до решения; R2/R3 берут `ep.wave_levels[2]` до изменения TP1/2.83 actual PLAN d3 значений R2/R3 совпали83/83. Для E4/R1 exact runtime d3 snapshots не экспортированы отдельным полем: источник/конфигурация/история проверены, но недостающие snapshot числа не придуманы.

R2/R3 actual audit содержит83 PLAN и83 `P0_FROZEN_FIRST_TERMINAL` каждый. Все реальные TARGETS_SUBMITTED сохраняют соответствующий first-child P0. У67/83 completed blended VWAP отличается от firstP0, но не подменяет TP-якорь. До terminal первого child его provisional actual VWAP причинно уточняется при partial fills; после terminal якорь фиксирован. Поэтому внешний B5 dynamic-VWAP/короткая калибровка не доказаны как ошибка существующего native baseline.

## Участие и деньги

Денежные значения BTC **ex-funding**; mean bp ниже также ex-funding и отличается от прежнего inclusive-funding cohort mean. Mean entered/gross использует только54parents с сохранённым request; у29 H4reentry requested_notional/multiplier audit отсутствует и остаётся UNKNOWN. Это не усреднение83 с выдуманными знаменателями.

| Observed native metric | E4 +старый SOL | R1 BTC-only | R2 real3TP/LEGACY_Q | R3 real3TP/CLEAN_Q |
|---|---:|---:|---:|---:|
| BTC fill-net ex-funding, USDT |4858451.84|285722.37|207863.76|106655.08|
| BTC fees, USDT |689336.60|71190.77|42681.92|25265.16|
| BTC signed funding, USDT |UNKNOWN|8649.66|8055.75|4063.32|
| Entered notional sum, USDT |836343139.79|84911887.32|57269089.55|33726816.77|
| Mean entered/requested gross,54known |83.869%|83.867%|76.738%|75.313%|
| Mean actual filled/reference qty,83 |82.758%|82.767%|75.007%|74.431%|
| Mean entry notional/own q0 equity |5.086x|5.620x|5.100x|5.032x|
| Equal-parent mean fill-net bp |80.673|80.680|94.833|94.818|
| BTC held minutes |409735|409735|394745|394745|
| Mean first-to-last-fill hours |82.276|82.276|79.266|79.266|
| Parents без фактического второго fill |1|1|16|16|
| Observed peak BTC mark notional,USDT |30859642.82|5435719.75|4071206.45|1979358.61|
| Peak observed BTC/own equity |16.817x|16.815x|12.777x|13.094x|

E4/R1 имеют почти одинаковое нормализованное участие и ex-funding netbp; абсолютный капитал/turnover сильно различается. Это подтверждает источник потери после удаления SOL — собственный капитал/compounding, а не найденную ошибку делителя BTC qty. У E4 cap30m позднее ограничивает вход относительно большого equity, поэтому более низкий средний entry/equity чем у R1 не означает более слабое участие в сигналах.

R2/R3 сохраняют более высокий equal-notional netbp, но раньше уменьшают exposure и чаще не получают второй fill. Это известная цена нового исполнения/3TP, а не доказанная возможность просто вернуть все отменённые доборы прибыльно. Их восстановление изменило бы exits/risk и требует новой поддержанной причины; данные такого admission не дают. Увеличение grossQ/плеча или возврат fake zeroTP не рассматриваются как решение.

Peak portfolio gross/equity у E4 во время BTCheld30.346x против BTC16.817x; отличие — одновременная старая SOLпозиция. У R1/R2/R3 SOLoff, поэтому portfolio gross=BTCgross. Пики используют actual native quantity и raw minute markclose/native equity; это не intraminute bound и не постоянное configured entry leverage. Рост leverage после просадки не означает новый entry boost.

## Ранний капитал и ограничения экспортов

| Actual own q0 settled equity,USDT | E4 | R1 | R2 | R3 |
|---|---:|---:|---:|---:|
| Parent1,02Sep2024 |10000|10000|10000|10000|
| Parent10,02Nov2024 |29003.97|15831.96|14553.88|16605.95|
| Parent15,23Dec2024 |89436.22|29573.94|26505.19|28966.31|
| Parent20,15Jan2025 |160437.86|25578.64|20911.14|19544.07|

Это measured state каждого собственного run. Сопутствующий уже завершённый SOL audit показывает первые5 SOLcycles до03Jan2025 +105055.25329125fill-net ex-funding. Эти деньги реально присутствовали в старой траектории; независимый BTC с прежним размером на меньшем equity здесь не склеивался. Точный counterfactual вклад раннего SOL в поздний TOTAL не идентифицирован.

Ex-post51 E4winning/32losing cycles используются только для диагностики. У R1 средний own-equity/E4 ratio21.09% на winners и18.64% на losers; actualqty ratios21.77%/20.46%. У R2 equity18.61%/16.01%, qty16.80%/17.39%; у R3 equity18.41%/15.30%, qty17.73%/17.37%. Это не доступный online фильтр и не доказательство, что перенос капитала между этими будущими группами улучшит результат.

В parent CSV сохранены actual own q0/first-fill equity, requested gross где известен, initial-child planned/actual qty, planned second, terminal cancelled qty, actual fills, add timestamps, first exit/final flat timestamp, exposure duration и observed peak notional/leverage. **Pending qty timeline UNKNOWN**: terminal snapshots не показывают все ACK/cancel-generation моменты; первичный planned second не назван фактическим outstanding order. Requested/M у uncapped54 отдельно сохранён как implied sizing equity; q0 settled equity не притворяется exact intratimestamp callback equity.

Cash verification R1/R2/R3: сумма native BTC fill-net+signed funding соответствует TOTAL−seed с сохранёнными money-rounding residual−2e−8/−4e−8/0. E4 BTCfill-net4858451.83533031 воспроизведён, старый signed asset funding UNKNOWN не заполнен bridge. Нет counterfactual TOTAL/DD, новых probability labels или новой стратегии.

## Admission

**A завершён без новой экономически поддержанной гипотезы.** Исправление внешнего короткого warmup или dynamic VWAP не восстанавливает native ROI: этих ошибок в native не обнаружено. Возврат grossQ через legacy zeroTP либо плечо не допущен. Нормализованное участие R1 уже почти совпадает с E4, а недостающий ранний капитал связан с SOLдоходом, существенная часть которого несовместима со strict hedge. H_PAIR_EXIT остаётся предложением без admission; этот audit не разрешает новый action screen/product/full/short и не открывает бюджет.

Артефакты: `btc-participation-parents.csv`332строки, summary12, early-capital80, matched-diagnostics249; calculate/verify scripts, verification JSON с input/source hashes. Записана одна metadata correction до первого trace прохода: отсутствующий request29 H4parents оставлен UNKNOWN вместо ошибочного предположения о полном sizing audit.
