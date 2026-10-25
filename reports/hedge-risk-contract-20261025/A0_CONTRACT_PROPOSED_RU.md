# A0: временная блокировка исходного BTC second-child

25.10.2026. PROPOSED_NOT_APPROVED. Контракт для одного узкого следующего опыта, не новая торговая реализация и не доказанный прибыльный алгоритм. Новые native/sourceбюджеты пока0. Пилот/production исключены.

## Причина и проверяемая гипотеза

В полном universe16 фактических B2/F0активаций найдены4 riskOFFточки с исходным неисполненным second-child; старые заявки действительно CANCELED до riskOFF. Для3 из4 исходный post-onlylimit не пересекает текущий quote. В действующем коде приостановка из-за хеджа навсегда закрывает split. Проверяется ровно одно изменение: при исчезновении риска разрешить одну новую GTCзаявку по ещё действующему остатку исходного second-budget. Закрытый BTC не восстанавливается, новый parent или новый сигнал входа не создаётся.

Четыре случая — структурное подтверждение существования механизма, а не четыре доказанные прибыльные сделки. Quote относится к прежней syntheticCLOSE executionмодели; будущийnativecash/margin/newquantity неизвестны до прогона.

## BTCcore и контроли

Для предлагаемого парного опыта выбрать **R2 LEGACY_Q_CONTROL как исследовательский anchor**, сохранив его причинную entry/sizingфункцию, realU3TP, EMA/side/firstIOC/second0.5%limit. Основание — сохранение исходного sizing и имеющиеся отдельные R2/R3nativeрезультаты, а не новая настройка параметров. Это не выбор победителя: R2сам по себе дал только3.56% исходнойS0netprofit иDD66.80%.

Sourcebase06f75778dbc3cdb9894ffed4f4e7621261e94d3e сейчас допускает R2толькоOFF. Новый точный registeredR2pairedfamily должен быть отдельно разрешён и проверен до экономических запусков. Не ослаблять старую R3ветку/guards произвольным q_mode. Дляобоих R2pairedC0/A0 жёстко зафиксировать `research_paired_prefix=B2_F0`; используются одинаковые новыйfamily/marketpolicy и различается только A0flag(false/true). В R2OFF `research_paired_prefix=None`, SOLнет. Не сравнивать новый R2кандидат с R3как будто coreне менялся.

## Состояния и лимиты права

1. До первой risk-cancel зафиксировать parentID, side, originalfirstallocation, исходный second-budget `S0`, immutableoriginalsecondprice/GTC/postOnly, originalintent и coreeligibility. В realU `S0=originalquantity-originalfirstquantity`; недоисполненный первыйIOC **не** добавляет прав второму child.
2. Считать `secondFilledEver` по фактическим nativefills всех поколений этого экономического child, включая latefills. `Sremaining=max(0,S0-secondFilledEver)`, в целых nativeBTCлотах. Не использовать только Q0−всеentryfills: это увеличивает second-budget после partialfirst.
3. Риск ACTIVE/UNKNOWN: существующие отмены pendingincreases и BTC/SOLprotection продолжают действовать. Новыйflag сохраняет отдельно экономический остаток права, не отменяя фактCANCELED старой exchangeзаявки. Не откатывать nativeorderhistory или номера поколений.
4. Кандидат на release только при фактическом riskOFF; sameparent ещё существует и держитBTC>0; нет ordinaryBTC TP/exit/parentend/flip/паузы/ликвидации. Любой ordinaryBTC TP окончательно гасит право, включаяTP во времяrisklock. Genericdeadline/day-stop из не-realUветки не использовать: `_split_check` при `_md_enabled()` сразу возвращается; действуют реальныеcoreguards.
5. Все старые ENTRY/cancelACK известны и terminal; нет другогоowned/inflightincrease и незавершённого BTCdebt/reduce. Late/partialfill пересчитывает Sremaining перед действием. UNKNOWN→нет увеличения. Не превращать oldorder вOPEN задним числом: новая nativeзаявка получает новыйorderID/поколение.
6. Разрешить не более **одной nativeпереподачи на parent**. Сам submit расходует право попытки, включая subsequentreject/cancel; автоматического retry нет. Ожидание подходящего quote доsubmit не создаёт сделку. Новый риск послеsubmit отменяет increase и сохраняет штатную защиту; повторного grantне будет.
7. Для причинной задержки новая заявка разрешена не раньше следующего executablequote после `riskOFFtime+60s`, пока всеguards всё ещё истинны. Цену/сторону/TIF не менять: BUYlimit<currentask, SELLlimit>currentbid. Crossing→WAIT/deny, безmarket/takerконвертации, chase или переценки. При исчезновении исходного права ожидание заканчивается безордера.
8. Release абсолютного parentceiling ограничен исходным second-остатком: `newCap=min(firstTerminalFilled+S0, lockedAbsoluteCap+Sremaining)` при известном/reconciledстаромcap. Допустимая addqty≤Sremaining и свободная часть newCap после фактического held/pending. Уже уменьшенный cap не восстанавливается за счёт закрытого BTC; excessreconciliation не должно повторно уменьшать cap и создавать рекурсию. Не выводить новый cap из суммы всехзакрытий, если туда входят correctiveoverfills.
9. Перед submit обязательны существующие **штатные** native margin/tier/availablefunds/quote-age/entries-enabled проверки на собственном текущем equity. Их UNKNOWN или отказ→нет ордера. Нулевой экспортIM/MM не является свободной маржой. Не подменять gate на True и не вводить ручной marginкалькулятор. Фактическое исполнение и комиссии решаетnativeengine; pendingне даёт coveragecredit.
10. Послеfill использовать существующие actualinventory/TPgeneration/limitsecond/latefill/corridorhandlers. Все три настоящихBTC TP и SOL TP/STOP остаются прежними; целочисленный lotrepair сохраняется. Overfill/latefill не игнорировать; запретить новыеincreases, привести превышение к абсолютномуcap штатным способом и сохранитьeventproof. Если требуется менять денежную семантику сверхэтого контракта — STOP/новыйпротокол.

## Что A0 намеренно не решает

A0 не убирает SOLTP→BTCdebt и не вводит cyclicSOLrearm, stresscontroller, новыеTPцены или защитныйresidual. Для Oct25 ожидания однойH4 доriskOFF недостаточно: market-only481quotes не пересекаютboundary, OFFпоexpiry наступает позжеdeadline. Этот путь отложен до отдельного A1контракта. Текущий stress90/headroom дал3PASS и1FAIL на4firstTP; это только предпосылка, не разрешение удерживать неизвестный uncutportfolio и не DDгарантия.

## Минимальные доказательства до prefix

- OLDflagOFF/старыйR3guard/config/fees unchanged; точные R2OFF/C0/A0 config/kwargs JSONroundtrip с actualdefaults, explicitfamilyиfalseпоумолчанию.
- Originalbudget после partialfirst; protectiveBTCcut не возвращается; ordinaryBTC TP/flat/flip/пауза убивают право; ACKUNKNOWN/oldownedincrease/нетnativecash запрещают submit; crossingpostOnly не превращается вtaker; лимит одной переподачи.
- Genuine nativecancel→knownACK→riskOFF→однаoriginalpriceGTC→partial/fullfill→реальные3TP; latefill/cancelrace/overfill actualcache и absolutecap сохраняются. Штатныйmargingate обязан реально выполниться, включаяdenyслучай. NativeProbe tierbypass не является доказательством этого условия.
- Всегда сохранять snapshotactualorders/fills/held/cash/caps/rights передdispose, в том числе приошибке. NaturalTPflat и ordinaryfailclosed отличать от forcedterminalFLAT; source/status не менять ради PASS.

Изменение торгового кода и эти physicalпроверки начинаются только после утверждения конкретного протокола и бюджета.
