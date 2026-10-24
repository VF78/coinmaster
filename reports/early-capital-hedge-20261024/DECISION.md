# CM-EARLY-HEDGE-20261024: результаты и следующий допуск

Владелец поручил продолжать настоящий SOL-хедж при сохраненииBTC-ядра: сначала>=70%прибыли исходногоS0/DD<=50%, затем>=90%. Эти цели **NOT_MET**. Новый nativeкандидат в этом пакете не квалифицирован; pilot/production не затронуты.

## 1. Один новый сигнал проверен и отвергнут

H_RESIDUAL_CONTINUATION — oppositeSOL после adverseBTC H4 и24h относительного движения в сторону хеджа — **STOP**. Новым был только residual continuation, не adverse/opposite/50%/BTCflat/EMA. Протокол/знак/SIMPLEwindow/24h/одинentryнаcycle зафиксированы до outcomes, независимый reviewPASS.

| Entrycohort | Episodes | SOLnetbp/NB без добавочногоslip | SOL−equal-factorTRIMbp/NB |
|---|---:|---:|---:|
| Первыйгод |29|−30.97…−30.95|−14.44…−14.43|
| Второйгод |33|−40.83…−40.82|−16.25…−16.24|
| РаннийSep1→Jan15 |13|−29.02…−28.99|−32.24…−32.23|

Все12cohort/slip/fundingboundary cells провалили оба cashadmissiongate. Исполнения hypothetical t+60s; actualBTCreductions/flat и avoidednativeexitcash/fees comparator учтены; все62episodes сохранены. 248scenario endpoints/196nativeexitchecks/1344fundingintegrations/36means independentlyverifiedPASS. Nativequantity/fills354 — acceptedR3source, не337E4/R1.

Защита **UNKNOWN_DATA_CLOCK_TERMINAL_ENDPOINT**: исходные settledreceipts используют более поздний wallclock и retainedprior marks; необходимого coherent same-windowterminalendpoint нет. Первый coverageassert остановился доmoneyresults; failure/source сохранены, одна substantiveclockcorrection. Gateнеослаблен, числоDD/локальнойзащиты не выдумано. Metadata-onlyrepair fundingtiecount60→5 сохранила все moneycolumns. Детали: screen-report.md, screen-ledger.json и screen-verification.json.

Эти cashgates — заранее установленный **допуск данного сигнала**, не математически необходимые условия всей задачи. Отрицательный meanSOLPnL сам по себе не доказывает, что экономия больших потерь не улучшит сложный рост. Поэтому отдельно проверен масштаб такого механизма.

## 2. Масштаб compounding: половинного среза потерь недостаточно в фиксированной модели

На всех83реальныхR3closedcycles проверено seed+cashnets=120718.40416503, funding4063.32156049, maxownq0reportresidual1e−8. ExactFraction независимая проверкаPASS. Ровно три заранее заданных scalarproducts:

| Арифметический сценарий, **не nativebacktest** | TOTAL-equivalent | OriginalS0netretention |
|---|---:|---:|
| НаблюдаемыеR3returns |120718.40|1.8249%|
| Вдвое меньше всеreturns |44053.08|0.5613%|
| Oracle: вдвое меньше всеlosers, всеwinners сохранены |1037982.53|16.9435%|

Oracle знает будущие проигрыши, бесплатно снижает и ихcosts, никогда не ошибается и сохраняетвесьupside. Он не исполним. Даже ему недостаёт4.1012×до70% в этой fixed-return модели. CycleboundaryDD≈38% не является globalmarked/eventDD и не проходит экономическийgate. Раннийoraclecapital34649.79 против observed19544.07 кJan15 также не возвращает старыйE4capital160437.86. Детали: growth-envelope-report.md.

Отдельный **post-result** scalarвопрос, объявленный до своегорасчёта: полное исключение всехlosers даёт bookend7027879.02 (115.6709%S0net). Обратная арифметика fixedwinner/attenuation-only модели требует убрать86.3883% отрицательныхreturns до70% и93.1526% до90%. Это **не liveα/stoplossparameter**, не новый торговыйрезультат и не формальная граница любых настоящихBTC/SOLстратегий. Источник будущихwinners/losers нельзя использоватькакfeature. Детали: growth-requirements-report.md и собственный протокол/hash/verification.

## 3. Следствие для следующих шагов

Не продолжать momentumпорог/окна/знак/размер и не запускать native, чтобы проверить уже отрицательный сигнал. Не предполагать, что формальный среднийhalfvolhedge сам вернёт раннийкапитал. Размер .5NBσB/σS даёт estimatedfactorcoverage .5rho, а не50%DD; реальныеcosts/ошибки делают идеальнуюloss-halving картину ещё более требовательной.

Следующий вопрос — совместный held-riskконтроль BTC/SOL из реального marketstress и текущего drawdownheadroom. Сигналы BTC можно сохранить, но при доказанном высокомриске может потребоваться сильнее уменьшать фактический BTC, а не полагаться только на SOL. Это направление не отменяет целевых70/90 и не разрешает повышать плечо, возвращать fakeTP или BTCflat/excessSOLalpha. Новизна относительно C1cut/restore/старыхbudget+trim должна быть проверена до нового screen. Идеальныйoracleinverse не выбирает параметры этого контроллера.

Проверка новизны завершена в growth-budget-admission.md: C1 уже использовал E/H/floor.5H/cushion, oldbudget+trim уже имел noautorestore. Переименование вCPPI не новаягипотеза. Единственное возможное отличие — jointstress **обеих actualheld ног** с SOLbasisrisk, executedhedgecredit и согласованным сокращениемBTC/SOL вместо selectedloserhalfcut/originalSOLADDcap. Статус **ARCHITECTURE_ONLY, NO_SCREEN/NO_NATIVE_ADMISSION**. До следующего вычисления требуется один frozenконтракт: causaljointshocksetΩ/TF/lookback/horizon, nativecost/fundingdownsideK, dedupheld/pendingreserveR, coherenteventcheckpoint, actual3TP/pairedexit/partialfill/infeasible и обычныеincreases. Нельзя ждатьнеисполненного SOL приужеопасномBTC или уменьшатьBTC, оставляяexcessSOL. Детализация, вернувшаястарыйC1/H_SOL, получаетSTOP/REUSE.

Реальные3TP обеихног и сопряжённыеexit/deficit/ACK/partialfill правила обязательны для будущегоnativeконтракта; этот пакет их не реализует. Coherent observer/cash/mark clock и terminalcoverage должны быть решены до любогоPASSпоDD; текущие UNKNOWN не скрываются.

## 4. Разрешения и сохранённая работа

Новых native/full/short/training/simulatorattempts0, productchanges0. Один frozenlogicalsignalpass+однаverification, один3-productarithmeticpass+exactverification, один отдельно объявленныйpost-resultrequirementscalculation+verification. Initialfailures/одноразовыеcorrections/hashreceipts сохранены. Никаких новыхphysicalbudgets/автоматическихповторов. Исходныеbenchmarks/floors4256975.067212381/5470396.514987347 неизменны.

Закрытый#131budget3/3full+8/8short не возобновлён. Sourceec2a958 defaultOFF unchanged/notdeployed; dirtyVPSprimary/Macrootusercode сохранены. Все операции — managerresearchdocs/saveddata, без /opt/services/keys/orders/transfers. Продуктовый executor/физическийrun нуждаются в отдельном поддержанном протоколе/бюджете; такогоGO этот отчёт не выдаёт.
