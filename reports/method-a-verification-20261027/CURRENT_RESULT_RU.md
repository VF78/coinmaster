# Текущий проверенный результат Method A

Расход — 9/18: 5 COMPLETED, 4 FAILED. Engineering 6/11, prefix 3/6, full 0/1; активных запусков нет. Единственный исправленный M3 из утверждённого перераспределения использован. Пилот и production не затронуты.

| Проверка | Доказано | Ограничение |
|---|---|---|
| BTC realTP, M1/P1 | Три реальных TP; 16/13/12 native fills. Prefix net151193.03 против150527.63 (+0.442%); 12 финансовых gates PASS | DD ухудшилась с57.5854% до62.4160%; это не full-результат победителя |
| M2 SOL | Частичный вход10, три TP+STOP; BTC550 сохранён, flat до cleanup; независимые63/63 PASS | Экономическая польза SOL, full ROI и DD50 не доказаны |
| Первый M3 | Идентифицирована ошибка DATA: неверное предположение о пополнении использованной глубины | FAILED69s; дальнейшие gates не достигнуты |
| Исправленный M3R, b03dacc | 13 VPS и13 Mac focused checks PASS, review0P1; CAP78 действительно исполнился10+68, позицииBTC200/SOL132.9 достигнуты | В70s strategy NO_GO после BTC TP fill199. Полный M3 FAILED; поздние gates не достигнуты |

Это не повтор прежней ошибки глубины: fail-closed следует действующему риск-контракту. Native cash показал падение equity на362.38696 при maker TP105.2 и mark107. После исполнения cushion360.2863425 меньше stress loss392.16122324487. BTC recovery ухудшает stress deficit. Любой SOL recovery отвергается из-за допустимого сценария: оставшийся BTC TP уже исполнен, новый SOL reduction ещё не исполнен. Этот неуправляемый corner добавляет1.6743468274 к текущему deficit; поэтому множества допустимых размеров пусты. Margin проходит. Точные расчёты и pins: m3r-risk-recovery-diagnostic-20261028/REPORT_RU.md и DIAGNOSTIC.json.

Новая baseline по уже работающим TP — только предложение изменения риск-контракта, а не разрешённый bugfix или реализованный solver. Пример full SOL-flat endpoint сC331.088567/L0 не доказывает all-partial route или native feasibility. Новых прогонов и бюджета нет; исходные M3/M3R FAILED неизменны. Нельзя подгонять время fault или объявлять ранний NO_GO ожидаемым PASS.

После NO_GO запрошена отмена трёх TP и STOP; cache показывает PENDING_CANCEL. Нулевой фактический интервал защиты до ACK не подтверждён. Перед end позиции BTC1/SOL−132.9 сохранялись; STOPPED/DISPOSED не означает terminal flat или PASS. Raw, OS exit, ledger snapshot и failure manifest сохранены.

Raw empty-SOL snapshot62s до первой инициализации появился, но fresh paired ref относится к61s. Source-bound command universe и новый consumer binder ещё UNKNOWN. Полной финансовой квалификации нет. Full S0 anchor6077107.23887483; TOTAL floors70/90%:4256975.067212381/5470396.514987347 при DD<=50% остаются NOT_MET.

Новая аналитическая гипотеза проверена отдельно, без изменения алгоритма: HYPOTHESIS_PROOF_RU.md/JSON и INDEPENDENT_CODE0_PROPOSAL_REVIEW.json (0P0/P1). Для captured70s при пяти фиксированных сценариях, постоянных знаках и без tier-переходов риск-функция — максимум affine forms; проверка четырёх углов покрывает весь прямоугольник старых BTC TP fills × новых SOL close fills. Худший deficit нового маршрута не превышает тот же unavoidable baseline35.2044175723; весь full-SOL edge safe, margin проходит. Нулевое исполнение остаётся уже unsafe; лемма не доказывает native очередь/завершение или все другие ордера. RECOVERY_CONTRACT_CODE0_PROPOSED_RU.md предлагает только будущий default-OFF patch и engine-free проверки, native/prefix/full0; нового разрешения на денежную семантику пока нет.
