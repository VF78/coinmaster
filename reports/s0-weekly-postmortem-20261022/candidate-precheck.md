# Проверка фиксированного DD25 + own-price2% /50%-once — не допуск к native

Кандидат только для анализа на исходном S0: после полного native-входа и штатной eligibility, при уровне portfolio moneyDD≥25% и движении текущего native mark против текущего native avg≥2% один фиксированный reduce-only IOC target50% на native position cycle. Условие уровня сохраняется после busy; новая модель/параметрическая сетка/прогон не запускались.2% не optimum и не рекомендация.

Один разрешённый saved-output stream:37,417,891compressedbytes,1,051,199receiptrows,24UTC месяца,0 пропусков/неприсоединённых nativepositions;2026-10-22T18:01:44.202028+00:00→2026-10-22T18:02:27.623496+00:00;43.42s,nice19,RSS23,416KiB. SHA780efb8da2c71189ebf5feb61c555137c99154e09f709de8c5b10ff19d0f32d3 подтверждён. Предыдущий SSH255 был до remoteexecution; это единственный фактический проход. Никакой alternativeequity/PnL или engine.

|Актив|Native циклов всего/прибыльных|Попаданий|Исходно прибыльных|≤1h|≤24h|TP/half уже был|DD уже≥50%|N/W min/median/max|
|---|---:|---:|---:|---:|---:|---:|---:|---|
|BTC|105/57|23|4|0|13|6|3|2.88/5.341/10.339x|
|SOL|26/22|9|8|0|7|0|0|0.284/0.332/14.325x|

Ранний SOL1 теперь имеет наблюдаемую возможность:03.10.2024 08:22UTC, DD42.1540303930%,W7766.78994701,qty810.9,avg140.09,mark137.2,ownadverse2.06296%; за 40 мин до первого savedDD≥50%09:02. SOLN/W14.3245x против медианы всех SOL попаданий 0.3320x. BTCshort0.724 в том же book имеет положительные nativeOHLC PnL bounds, SOLlong —отрицательные. Это наличие состояния, не доказательство, что будущий nativeIOC успеет/исполнит цель и сохранит DD≤50%.

Цена в процентах не сопоставляет риск: у SOL одинаковый 2%сигнал возникает при N/W0.284..14.325x, у BTC2.880..10.339x. На первом DD50 SOLN/W16.513x, BTCshort6.539x; nativeSOL OHLC PnL bounds−3478.761..−3243.6 против BTC+395.7022..+472.953. Это nativebounds завершённого бара, не closeUPnL/tickPNL. Отдельный perasset closeUPnL не экспортирован и не вычислялся.

BTC-only окна представлены: BTC35/36/37/39/43 в апреле–июне 2025 и 63/64/67 в октябре–ноябре. Однако BTC37 впервые достигает условия уже при DD49.867%, а 39/43/45 —после 50%: правило не восстанавливает уже нарушенный денежный лимит. Наличие более ранних попыток в том же drawdown не доказывает достаточность их объёма.

Среди 32 попаданий 12 исходно прибыльных:BTC4/23 (26,67,71,72), SOL8/9 (1,3,14,15,16,18,20,22). Все 23BTC и 8/9SOL имели ранее благоприятное price наблюдение. Это описания оригинального пути; исходные доходы не суммировались как foregoneprofit. Новая политика изменила бы будущие capital/qty/triggerstates, поэтому 32 —не прогноз числа её actions.

Фильтр убирает immediate-entry haircuts:0≤1h против 33≤1min у первоначального DD25+anylosslevelscreen. Но это неэкономическая admission: подавляющее большинство SOL попаданий —восстановившиеся оригинальные победители. Старый BTCADVERSE50 при≈1.9175%/50% имел отрицательные optimistic endpoint price-proxy deltas на calibration и holdout; это другая выборка, но причина не путать precisionlosslabels с payoffedge.

Execution: используются причинные nativeavg/mark/DD и прежний once-cycle fixed-target IOC механизм. Нового executor/model не требуется. Pending/ACK/entrycomplete/ordinary priority не экспортированы в receipts —actualeligibilityUNKNOWN. У 1 из 9SOL номинальная половина qty превышает известную 1000quote-liquidity; это риск partialfill, не предсказание исполнения. M1/M2 уже показали 4/3SOL partialcancels и отсутствие retries.

Вывод: не выдавать эту ценовую гипотезу за сильнейший следующий кандидат и не допускать native только по этим данным. Она улучшает availability/устраняет haircuts, но не устанавливает ни сохранение 90%netprofit, ни DD≤50. Финальный ONEcandidate —после rootweeklyinventory; альтернативная гипотеза/новаясетка здесь не проверялась.

Месячные firsthits и прибыльные/убыточные контрпримеры сохранены в candidate-precheck-monthly.csv; все 32 попадания —в candidate-precheck.csv; running priceextrema по 131native циклам и полные причинные firstDD25/50/bookcontexts —в JSON. Полные эпизодные extrema —только hindsight описание, никогда inputpredicate.
