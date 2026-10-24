# Carry addition: STOP_CARRY, 24.10.2026

Известный до решения знак последнего settled SOL funding не даёт основания следующему native SOL-кандидату. В recipient bin будущий funding положителен в среднем, но значительно меньше roundtrip fees; price+fee+funding результат отрицателен в обоих годах при всех четырёх сценариях settlement boundary. Receiving carry не разрешает вход SOL без фактического BTC/risk need и не разрешает отказываться от обязательной защиты при дорогом funding.

Единственное новое действие — добавить funding cash к уже сохранённым R3 frozen-action outcomes. 1529 исходных H4states/77cycles, прежние три размера SOL и три equal-factor BTCtrim, NO_HEDGE,4h/24h сохранены;21371 строка,9159 SOL/trim pairs. Нового price replay, matching, состояния позиции, native engine, обучения и full/short прогонов нет. До расчёта сохранён carry-screen-design.json; скрипт carry-screen-calculate.py содержит один расчёт и одну связанную проверку.

Все числа далее — средние bp **исходного BTCnotional NB**, не equity, не TOTAL и не DD. Таблица показывает заранее определённый HALF_MV, не выбранный по результату лучший размер; остальные два размера имеют тот же отрицательный вывод в полном CSV.

| Lag SOLfunding recipient | Labels/cycles | Fees bp | Funding strict interior bp | Funding both boundaries included bp | Price/fee net bp | Net+funding interior bp | Equal-cycle net+funding interior bp |
|---|---:|---:|---:|---:|---:|---:|---:|
| First year,4h |484/34|2.1602|0|0.1321|−2.6193|−2.6193|−7.5967|
| Second year,4h |440/38|2.8814|0|0.1126|−4.4347|−4.4347|−4.8153|
| First year,24h |484/34|2.1649|0.2996|0.4164|−8.0862|−7.7866|−11.5107|
| Second year,24h |440/38|2.8796|0.2074|0.2842|−12.9725|−12.7651|−20.7532|

24h funding покрывает в среднем только13.8%/7.2% fees в двух годах при строгом interior,19.2%/9.9% при включённых обеих границах. Для OWNER_VOL/HALF_FACTOR также примерно14%/8% fees по interior; отдельные редкие события не образуют стабильного cost cover. Доля recipient labels, где interior funding>=fees:0.4132% в первом году и1.8182% во втором, одинакова для трёх размеров. На4h interior settlements нет из-за сетки H4 и наблюдаемого8h funding schedule; это не подстановка отсутствующего funding нулём.

Положительное среднее SOL-minus-trim в recipient labels не является устойчивым преимуществом. HALF_MV equal-cycle paired difference:4h +0.2873bp в первом году против−0.4631bp во втором;24h −0.8618/−1.7561bp. При включении обеих boundary settlements соответственно+0.3208/−0.4035 и−0.8550/−1.7152. Остальные размеры также теряют cycle-weighted преимущество во втором году. Это описательная проверка уже просмотренной истории, не независимое доказательство gate или causalalpha.

Исходный H1close tail improvement HALF_MV в recipient bin остаётся8.07/8.34bp для4h и28.21/26.58bp для24h. Это **прежняя price/fee conditional tail метрика**, funding-adjusted tail не вычислялась: исходные scalar outcomes не содержат времени trough. Нельзя прибавить endpoint funding к прошлому минимуму и объявить новый DD. Endpoint BTCdownside/upside views сохранены отдельно; защита хвоста сама по себе не отменяет отрицательной средней стоимости/прибыли.

## Данные, знаки, timing

Использован полный нормализованный market funding calendar, не SQLite исторически удерживаемых позиций: BTC4380/SOL4740 строк, mark1m1051200 на каждый актив. Funding unique/sorted, observed maxgap8h; BTC4379 интервалов8h, SOL4259×8h и480×2h за весь календарь. В relevant интервале2096events каждого актива; отсутствующих prior-minute marks0. Точное соответствие historical venue interval schedule независимо не доказывалось.

Feature: последний **settled** SOLrate с timestamp<decision; будущие rates только outcome. Bin recipient, если BTCside×lagSOLrate>0, иначе payer_or_zero; фактических нулевых rates нет. Отложенная settledrate не называется известным прогнозом следующего rate.

Для SOL funding delta=BTCside×Q_SOL×priorSOLmark×actualrate; для trim incremental delta=BTCside×removedQ_BTC×priorBTCmark×actualrate, то есть минус funding удалённого BTC. Mark — raw close ровно settlement−1min, тот же prior-minute convention frozen native source; точный биржевой settlement mark и native tick rounding не подтверждены. Количество постоянно только в гипотетическом outcome horizon.

Четыре сценария: EE исключает funding ровно на входе/выходе; IE включает только вход; EI только выход; II обе границы. Все результаты сохранены, выгодный порядок не выбирался. Для SOL9159 action/horizon rows:2352 без boundary ties,4587 с одной,2220 с двумя. Прежний crosses_observed_native_flat flag сохранён:5.04%4h и27.82%24h states. Такие outcomes не являются допустимым hedge lifecycle после nativeflat.

## Проверка и файлы

PASS: исходные price/fee/outcome columns неизменны в памяти; lagfeature строго раньше решения; NO_HEDGE funding0;276 независимых direct signed event-sum checks сверены с prefix arithmetic, tolerance1e−8USDT. Input SHA256/coverage в carry-screen-meta.json. Новый статус STOP_CARRY означает отказ добавлять funding gate к следующему native предложению по этому screen; не запрещает вести funding accounting в обязательном фактическом hedge.

- carry-screen-outcomes.csv — неизменные исходные поля + lagcarry и четыре funding outcomes.
- carry-screen-summary.csv — два года/overall, оба lagbins, endpointdownside/upside; fees, funding, tails и cycle means.
- carry-screen-cycle-blocks.csv — прежние cycle blocks, без независимой статистической интерпретации перекрывающихся H4labels.
- carry-screen-paired.csv — SOL-minus-equal-factor-BTCtrim по двум годам/двум bins/горизонтам/размерам.
- carry-screen-design.json, carry-screen-calculate.py, carry-screen-meta.json — преддекларация, воспроизводимый saved-data расчёт, checks/inputpins.
