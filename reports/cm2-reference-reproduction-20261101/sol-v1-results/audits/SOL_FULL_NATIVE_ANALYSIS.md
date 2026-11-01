Финансовый FULL24M PASS подтверждён:1051200 source/1051199 settled WM/24месяца, sourcec411; rawSHA9e4c88085579a700de67d1eeb4877569f5b71cf878b62e5fd614f9a9923270f5. Economic disposition: HOLD_SOL_V1 — цель собственного вклада SOL и надёжного хеджирования не выполнена. Ошибка учёта/неверная сторона исполнения этим аудитом не установлена.

| Показатель | Совместный V1 | BTC-only R3 | Оригинальный BTC-only5b |
|---|---:|---:|---:|
| Native terminal cash |554765.87924905|359473.07471552|358370.46374134|
| Максимальная native event DD |72.3004550221%|64.7416405686%|64.8279999941%|
| BTC циклы/fills |83/354|83/353|83/353|

Совместный seed10000 + native realized529821.34575831 + actual signed funding14944.53349074 =554765.87924905, residual0. Native fees114505.61528969 уже включены в realized, повторно не вычитаются. Terminal0positions/0orders,liquidations0.

BTC: native realized1057691.08532483 + funding12327.12079449 =1070018.20611932. SOL: native realized−527869.73956652 + funding2617.41269625 =−525252.32687027; fees5549.34066652 уже включены. Общая разница с R3 +195292.80453353 раскладывается на SOL−525252.32687027 и наблюдаемое изменение BTC+720545.13140380. Это точное бухгалтерское разложение общего счёта, не изолированная причинная оценка полезности SOL.

Все83 BTC entry keys, branches и q0/q1 совпали. Первый размерный разрыв — цикл6/key764 после native-прибыли SOL1. Общий капитал/HWM экономически меняют C1:14CUT/1RESTORE против13/1;3старых cut исчезли,4новых появились,ещё3cut изменили время; один TP сдвинулся на2минуты после нового C1. Итого354vs353fill. Все14quarters и15actual fill-credit bindings проверены точно; restore583108lots,creditпосле0. Изменения C1 допускаются выбранным shared-capital контрактом; новых BTC сигналов/веток/entry clock не обнаружено. Полный список цен/количеств/комиссий/часов сохранён в JSON и CSV.

SOL:16циклов/32fills,11прибыльных/5убыточных. Все16 первоначальных NB/K, official lot и frozenK/sigma/permission прошли.9циклов действительно сохранили SOL после BTCflat, суммарно50285минут; same-direction overlap с текущим BTC0минут. Выходы:9REGIME,6TRAIL,1relative convergence. Наихудший цикл15: longSOL18мая–8июня2026, native net−648143.37796431,15641минута BTCflat-carry, выход pure marketTRAIL. LongSOL против actual shortBTC при входе правильный; удержание до market-exit соответствует явному carry-контракту. Один этот убыток превышает суммарный убыток SOL. Это концентрация рыночного риска, а не разрешение удалить сделку задним числом.

До фиксированных native BTC-only drawdown crossings SOL был открыт и противоположен BTC:DD2 9/85,DD5 9/85,DD10 4/46,DD20 3/18. Перед5%crossing отсутствовал в76/85окнах; медиана опережения среди9покрытых847минут. В худшем контрольном окне829 SOL flat на всех2/5/10/20crossings и trough. Все85окон/319точек, пропуски и стороны сохранены; текущая BTCсторона классифицирована отдельно и совпала с control на этих319точках. Это описание присутствия, не предотвращённого counterfactual убытка.

Для319точек доступны реальные event-bound SOLcash+nativeUPNL endpoints, без price-PnL формул:41положительный,278нулевых вкладов на этих перекрывающихся окнах. Их нельзя складывать в ROI. Метки построены по controlDD: они не охватывают автоматически новые риски jointтраектории, включая большую потерю SOL15 и jointDD72.30%.

Prefix/full:52interiorfill поля совпали после явной биекции толькоparentUUID,107fundingposts literalexact. Все131039строк WM совпали по6полям; opaque stockPositionpickleSHA различен на50461строках. Все262078 exported PREQUOTE native states exact. Literal7WM invariant не прошёл/byteidentityNOT_PROVEN; это не отменяет строгий financialPASS. Полные отличия и sourcepickle evidence сохранены отдельно, checksum/qualifier не менялся.

Оригинальный combinedA имеет84BTC/25SOL и другой капитал/permission/sizing/exit путь; его716481.01297376SOLnet не является контрфактом данного V1 и не переносится вычитанием из5.6mterminal. Таблица выше сравнивает два квалифицированных BTC-onlyконтроля отдельно.

Новых engines, source edits, параметрического подбора или liveгарантий нет. Exact raw/derived/proof/sourceSHAs и native perasset/lifecycle/funding joins находятся в SOL_FULL_NATIVE_ANALYSIS.json; все85окна — SOL_FULL_DRAWDOWN_PRESENCE.json/CSV.
