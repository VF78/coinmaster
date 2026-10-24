# SOL: условные парные действия по сохранённому E4

Статус **INCONCLUSIVE: рабочий risk gate не выбран**. Данных хватает для причинных признаков и условной арифметики действий на наблюдавшемся BTCinventory. Это не стратегия, новый backtest или экономический результат R3. Полных native запусков **0**. Source/runtime/Project не менялись.

## Наблюдаемые состояния и признаки

В `native-fills.csv`337 BTCorders полностью исполнены, partial records отсутствуют. Все337 сопоставлены с `native-fill-audit.csv`: timestamp и quantity совпадают точно; native float avg_px нормализован к архивному BTCtick0.1, чтобы устранить представление вида60145.100000000006. Native side BUY/SELL даёт простую signed inventory сумму; terminalBTC=0.000,83 фактических цикла и их first-fill timestamps совпадают со split-parent-audit. Новый OMS не строился.

Из4380 закрытых H4 решающих timestamps исключены2692BTCflat,55 без полного lag720 и73 с BTCfill ровно на decision timestamp (порядок событий не доказан). Остаются **1560 решений/78BTCциклов**:733/38первого года,827/40второго.4h labels1560,24h1555 (последним5 нет полного будущего24h). На горизонте4h/24h **78/434** labels пересекают фактический native выход BTC: поэтому initial inventory в outcomes явно заморожен, а не выдан за реальный будущий holding. Year boundaries не пересекает ни один label. Первый год [2024-09-01,2025-09-01), второй [2025-09-01,2026-09-01).

720 синхронных простых H1return observations заканчиваются строго до решения (последний return end=t−1h). Положительные covariance/correlation/variance/beta обязательны; среди1560 связь положительная, rho **0.58960…0.88898**. H4return использует только закрытую свечу. ER24 до расчёта outcomes определён как24closedH4 increments (**96h**): abs(Ct−Ct−96h)/sum(abs(H4pricechanges),24). Страты заданы заранее, не выбирают gate: side*H4return adverse771/nonadverse789; ER<=.25:1034, .25<ER<=.5:471, ER>.5:55; rho<.3:0, .3<=rho<.7:183, rho>=.7:1377. Высокая ER страта малочисленна.

## Действия и сравнение

NB=abs(nativeBTCqty)*closedBTCprice. betaSOLgivenBTC=cov/varBTC. Три значения SOLnotional:

- OWNER_VOL=.5*NB*sigmaBTC/sigmaSOL; relief относительно BTCfactor=.5*rho.
- HALF_MV=.5*NB*cov/varSOL; relief=.5*rho².
- HALF_FACTOR=.5*NB/betaSOLgivenBTC; relief=.5.

Направление SOL противоположно native BTC. Каждому SOL действию соответствует BTCtrim NS*betaSOLgivenBTC с тем же estimated factor relief; все trims<=NB (фактически<=.5NB), незаметного clipping нет. SOL NS/NB ranges: OWNER_VOL.1947… .3943, HALF_MV.1347… .3336, HALF_FACTOR.2758… .4863. Это три разных масштаба риска.

В outcome используется наблюдённая начальная BTCпозиция, гипотетически неизменная весь4h/24h, и реальные H1close prices. Для нового действия обе ноги taker.055%: fee=.00055*Naction*(2+assetreturn). BTCtrim означает уменьшение сейчас и восстановление той же quantity на горизонте, с двумя fees. NO_HEDGE имеет incremental fees0; старые BTCentryfees повторно не начисляются. `net_action_benefit` — изменение против NO_HEDGE после этих условных fees; `combined_change`=frozenBTCchange+net_action_benefit. В CSV есть USDT, но перекрывающиеся окна **не суммируются как прибыль**.

Tail improvement в таблице — разница минимумов `min(0,min(H1 close-grid combined change))` и BTC reference на том же горизонте. Actionfees считаются как условный roundtrip на каждом будущем H1close. Это диагностическая цена защиты на close-grid, не marked-equityDD, не intrahourMAE и не actual lifecycle.

Средние по H4 rows в bp от NB. Два первых столбца — net action benefit первого/второго года; далее всё наблюдение, условная fee и tail improvement SOL/равногоBTCtrim:

|h|SOLsize|Benefit год1|Benefit год2|SOL benefit|Trim benefit|SOL fee|Trim fee|SOL tail|Trim tail|
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
|4|OWNER_VOL|-5.12|-5.69|-5.42|-6.28|3.20|4.31|8.94|11.32|
|4|HALF_MV|-3.94|-4.79|-4.39|-4.98|2.53|3.40|7.74|8.91|
|4|HALF_FACTOR|-6.67|-6.76|-6.71|-7.95|4.07|5.50|9.33|14.46|
|24|OWNER_VOL|-15.79|-11.89|-13.73|-12.54|3.20|4.31|32.26|40.54|
|24|HALF_MV|-12.91|-10.17|-11.46|-10.26|2.53|3.40|27.42|31.66|
|24|HALF_FACTOR|-19.04|-13.87|-16.31|-15.29|4.06|5.50|35.03|52.38|

Все три размера имеют отрицательную среднюю net action добавку в обоих годах; положительная tail защита существует. Сам отрицательный hedge cashflow не объявлен критерием провала. На24h ни один из трёх размеров не даёт преимущества перед равным BTCtrim по средней стоимости **и** close-grid защите; на4h SOL дешевле, но tail защита слабее. Это наблюдаемая замена доходности на защиту, ещё не найденный причинный risk gate.

H4 строки перекрываются. Для проверки устойчивости рассчитаны сначала средние внутри BTCцикла, затем равновесное среднее78циклов; отдельные H4 строки не считаются независимыми. В bp:

|h|SOLsize|Cycle mean net SOL|Cycle mean net trim|Cycle mean tail SOL|Cycle mean tail trim|Циклов с положительной mean net SOL|
|---:|---|---:|---:|---:|---:|---:|
|4|OWNER_VOL|-8.61|-8.57|9.00|12.21|30.77%|
|4|HALF_MV|-6.92|-6.81|7.81|9.67|30.77%|
|4|HALF_FACTOR|-10.77|-10.85|9.32|15.48|30.77%|
|24|OWNER_VOL|-21.12|-16.72|32.66|42.81|39.74%|
|24|HALF_MV|-17.34|-13.71|27.86|33.64|39.74%|
|24|HALF_FACTOR|-25.72|-20.44|35.33|54.87|39.74%|

Календарные/cycle views и заранее заданные ER/correlation/H4 страты сохранены полностью, без отбора лучшего gate. Даже adverse closedH4 подмножество не даёт автоматического разрешения SOL: его средний futureBTCreturn положителен (+6.53bp/4h,+13.23bp/24h), SOLnetbenefit отрицателен у всех трёх размеров. Эти наблюдения не продвигают ранее неудачные gates.

Разделение по **будущему** BTCendpoint приведено только как outcome, не как online-фильтр:

|h|SOLsize|SOL benefit при BTCdownside|Trim benefit downside|SOL benefit при BTCupside|Trim benefit upside|
|---:|---|---:|---:|---:|---:|
|4|OWNER_VOL|18.32|16.83|-27.92|-28.17|
|4|HALF_MV|14.19|13.20|-22.00|-22.21|
|4|HALF_FACTOR|23.88|21.63|-35.71|-35.98|
|24|OWNER_VOL|53.82|48.61|-77.64|-70.39|
|24|HALF_MV|41.39|37.99|-61.47|-55.91|
|24|HALF_FACTOR|70.77|62.75|-98.70|-89.14|

## Границы и следующий шаг

Есть причинная feasibility для таблиц, но **INCONCLUSIVE** для SOL правила. Нет нового gate, trained model,3TP/SL, lifecycle, собственного equity/margin/cap, order admission, slippage, funding или L2/queue proof. Ни PnL/TOTAL/ROI/DD кандидата, ни эффект на R3 здесь не получены. Наблюдался E4, история уже просмотрена; year split и cycle blocks — описательная устойчивость, не freshOOS или независимый statistical test. Expanding online rule validation отсутствует, поскольку правило не выбрано. Положительная корреляция сама по себе не нашла момент, когда выгодно платить за защиту.

Следующее действие одно: сохранить SOLoff в утверждённом BTCcheckpoint; после реального R3 attribution решать, есть ли конкретный causal risk event, для которого нужна отдельная frozen SOL hypothesis. Дополнительный SOL native run не авторизован этим screen.

Артефакты: `sol-screen-design.json` (формулы/страты до outcomes), `sol-screen-features.csv`, `sol-screen-outcomes.csv`, `sol-screen-summary.csv`, `sol-screen-cycle-blocks.csv`, `sol-screen-meta.json` (hashes/coverage/verification), `sol-screen-calculate.py`. Команда из manager checkout: `python3 reports/market-redesign-20261024/sol-screen-calculate.py`.

Одна связная финальная verification прошла:337fill/audit pairs, terminal0 и83starttime joins; lag availability, точный NO_HEDGEzero, additive identity, factor/vol/MV identities, допустимый trim. До outcomes первый диагностический запуск остановился на raw float avg_px equality; canonicaltick normalization устранила representation mismatch, timestamp/qty не менялись. ER24 уточнён root до первого расчёта outcomes. Physical native attempts0.
