# H_RESIDUAL_CONTINUATION — один дешёвый admission screen

24.10.2026, CM-EARLY-HEDGE-20261024. Новое поручение владельца: продолжить поиск настоящего SOL-хеджа с сохранением BTC-ядра, сначала70%netprofitS0/DD<=50%, затем90%. Product/native/full/short/training budgets0; прошлые попытки закрыты. Разрешён этот ограниченный saved-data диагностический расчёт. Никакого pilot/production/runtime/VPS действия.

## Гипотеза и точное отличие

Когда heldBTC движется против своей стороны, а SOL относительно causal BTCbeta движется в сторону будущего SOL-хеджа, continuation такого остаточного движения может оплатить защиту и дать раннюю прибыль. Это только гипотеза. AdverseBTC/oppositeSOL/50%/BTCflat exit и EMA-фильтры уже исследованы и не объявляются новыми. Новый элемент — signed24h beta-residual continuation. Косвенная литература/пределы новизны в mechanism-novelty-admission.md; данные в feature-contract-report.md.

## Принятое определение, единое для первого и второго года

1. Universe — pinned1529H4states/77actualR3BTCepisodes, из feature-contract-features.csv. Это уже просмотренная история, неOOS. Решение после completedH4close t; executionreference e=t+60s. Нельзя использовать прежние same-close/fixed-horizon outcomes как новые labels.
2. Только SIMPLE: RB24=PB(t)/PB(t−24h)−1, RS24=PS(t)/PS(t−24h)−1; M24=RS24−beta_t*RB24. Beta_t/cov/rho/sigmas — existing720completedH1returns, ends t−720h..t−1h. Это causal, хотя estimationwindow пересекает momentumwindow. Не тестировать альтернативный beta до последних24h, sum-H1 или LOG. Root выбирает это определение до outcomes; source memo предлагает иной window, он не принят.
3. Trigger: heldBTCside s, s*RB4<0 AND s*M24<0, finite sigmas>0, beta>0/rho>0. Дополнительных cutoffs/EMA/ATR/z/side-specific настроек нет. Feature-only391states183/208years получены без outcomes. Не выбирать выгодный знак после результатов.
4. Один opportunity на actualBTCepisode: первый qualifying state с однозначными BTCfills/state. Если BTCfill ровно t/e, ownership/order UNKNOWN, такая попытка NO_ACTION_UNKNOWN; если к e flat или другая сторона — NO_ACTION. Отдельно считать эти причины. Проверка actual pre-e quantity причинна, будущий BTCflat не фильтр входа. Новый residual threshold/период после STOP не подбирать.
5. На e: NB=abs(actualQB_pre_e)*PBexecution(e), NS=.5*NB*sigmaB/sigmaS, qSOL=NS/PSexecution(e), sideSOL=−s. Equal-factor qTRIM=beta*NS/PBexecution(e), это доля .5rho отQB, не .5QB. Положительная rho<=1 и cap qTRIM<=QB проверяются. Qty без lot/queue matching: диагностическое непрерывное значение, не исполнимый order. Margin/minimumlots/capacity UNKNOWN, неPASS.
6. Один горизонт24h отe. Выход раньше при первом actualBTCflat или reversal; future boundary используется только для выхода. Внутри при каждом actualBTCreduction обе diagnostic quantities уменьшаются в пропорции abs(QBafter)/abs(QBbefore); BTCadds не увеличивают hedge/trim, re-add нет. Таким образом это ограниченный capped first-action screen, не контроль mandatory coverage всего будущего BTC. Если BTCflat/reversalevent не упорядочивается — UNKNOWN/две boundary alternatives, не перенос SOL заBTCflat. Не пропускать исходы по futureflat/endpoint.

## Marks, native reference и comparator accounting

Не создавать matching/портфельный симулятор. Actual BTCfills и native equity берутся из принятого R3; гипотетические cashflows одной SOL-операции и одного trim аналитически оцениваются на общем интервале. Никаких counterfactual TOTAL/DD/ROI, прежних BTCqty на новом equity либо новых сигналов BTC.

- Entry/плановый exit: execution1m close, availability=open_time+60s. Для funding используется полный marketcalendar и prior1m mark как ранее pinned fixture. M1execution/mark непрерывны и не являются L2/реальными возможными fills. Для вынужденных reductions/flat брать native BTCfilltimestamp и completed execution close этого времени; цены без доступного однозначного close — UNKNOWN, не favorable nextprice. При расхождении rawmark/nativeprecision сохранить basis, не подменять cash.
- SOLcash: вход oppositeBTC, все proportional closes и finalexit с BASEtaker0.055% от своего notional. Funding signed на реально удерживаемой diagnosticqty, не на initialqty послеreductions. При расчёте localmarkedvalue использовать mark1m для открытой SOLqty.
- TRIM — уменьшение исходногоBTC, не новая BTCshort. Входной trim несёт BASEtakerfee. При actual baselineBTCreduction уменьшающаяся removedqty экономит соответствующую долю **реальной native exit commission** и избегает соответствующего actualnativefillcash; это не платный восстановительный trade. Только оставшийся trim на scheduled24h при ещёheldBTC восстанавливается по referenceexecution с takerfee. На actualBTCflat восстановления/новогоBTCentry нет. Упущенный BTCupside полностью входит в signedcashflow. Нельзя искусственно ухудшить comparator двойной takerfee на ужеflatBTC.
- Формально trim incrementalcash: наentry s*qTRIM*PB(e)−entryfee; при original reductionδqTRIM — минус s*δqTRIM*PB_nativefill плюс пропорциональная avoidednativefee; наscheduledrestore remaining — минус s*qTRIMremaining*PB(exit)−restorefee. Open incrementalposition=−s*qTRIMremaining, оценка поmark. Fundingincrement=+s*qTRIMheld*PBpriorMark*rate, т.е. минус исключённый baselinefunding.
- Основной результат содержит 0bp дополнительного slip как reference assumption и отдельный фиксированный adverse2bp на каждое фактическое hypothetical takerдействие SOL/trim. Avoided baselinefees/exits не получают выдуманный slip. Native fills/комиссии не изменяются. Оба сценария проверяются, не выбирается выгодный. Это stress, не доказательство real capacity.
- На funding timestamp с одновременным BTCreduction/flat вычислить два фиксированных сценария до/послеreduction. Не известныйcallbackorder не объявлять точным. Все gate должны выдержать худший результат; непокрытая/неупорядочиваемая неоднозначность UNKNOWN блокируетPASS. Entry и scheduledexit e+24h сдвинуты на1minute от плановыхH4/fundingграниц.
- Для защитного necessarycheck использовать **сохранённую actualR3settlednativeequity** на окне e..exit как baseline, плюс отдельный incrementalSOLmarkedvalue. Сравнить минимальное изменение от стартовойnativeequity, нормированное наNB. Это локальный loss diagnostic; не globalMDD нового портфеля, не intraminuteDD, не второй equityengine. Если traceнедостаточен — UNKNOWN. Endpointprofit не подставлять в прошлый trough.

## Заранее объявленные срезы и stop gate

Главные срезы: первыйbenchmarkгод [2024-09-01,2025-09-01), второй [2025-09-01,2026-09-01), и раннийcapitalcohort [2024-09-01,2025-01-15). Ранняя граница — уже зафиксированный в audit parent20 owncapitalgap E4160438/R125579, до нового screen. Весь исход относится к entrycohort; пересечениеyear/end учитывается явно. Минимально10distinctepisodes в каждом году и3в раннемсрезе; иначе INCONCLUSIVE_SMALL_SAMPLE, не подбирать границы/порог. Сентябрьские4R3cycles вне720H1sample: NO_FEATURE_HISTORY, не доказательство полной ранней защиты. Отдельный ранее упомянутый [Sep1,Oct4) лишь описательный stresswindow, не заменяет главный earlycohort и не выбирается по результату.

Один opportunity/episode означает equal-episode mean. Все amounts нормированы на собственный NBнаe; total$публикуется только описательно, без сложения перекрывающихся counterfactualcapital. По long/short показыватьcounts/sign, без выбора стороны.

Для **каждого** главного среза и обоих slip/fundingboundary сценариев требуется:

1. Mean SOLnet/NB>0 против NO_ACTION — иначе STOP_CAPITAL.
2. Mean (SOLnet−TRIMincrementalnet)/NB>0 — иначе STOP_TRIM_DOMINATES.
3. Mean localworstloss cSOL не хуже baseline — иначе STOP_PROTECTION.
4. Полные marks/funding/actualstate; нулевой будущий SOLпослеBTCflat; базовый quantity/fee/funding/cashflow verificationPASS. Иначе UNKNOWN_DATA/ACCOUNTING, неPASS.

Если samples достаточны, но хотя быодин gate провален — STOP для этого сигнала; не переставлять окна/знак/размер, не запускать native. Если gates проходят — лишь LOCAL_SIGNAL_SUPPORTED, не достижение70/90 и не permission: следующий шаг отдельный E4/native капитал/3TP/riskdeficit контракт и протокол бюджета. Даже localPASS не доказывает profitfloor4256975.067212381, final5470396.514987347, DD<=50% или отсутствиеликвидаций.

## Бюджет и проверка

Один logical saved-data outcome pass, одна независимая арифметическая verification. Не более одной конкретной существенной correction, все initialfailures сохраняются. До чтения новых outcomes записать SHA256этогопротокола, feature/source/data hashes и UTCfreeze в screen-ledger.json. Native/full/short/training/simulator physicalattempts0. Не импортировать productrunner и не менять frozen source. Не запускать альтернативные scores/грид/другойhorizon после результата.
