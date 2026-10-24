# CoinMaster: рыночные BTC TP и условный SOL-хедж

2026-10-24, Europe/Moscow. **NO_GO. Экономическая цель NOT_MET.** Три разрешённых полных native-запуска завершены; новых запусков и обучения не разрешено. Пилот, production, сервисы, ключи, реальные заявки и переводы не менялись.

## Результат

Период [2024-09-01,2026-09-01) UTC, старт10000USDT, начальный RESERVE0. Во всех новых вариантах резерв остаётся0; DD счётчика и TOTAL совпадают. Приёмка: global settled marked-equity DD<=50% и не менее90% чистой прибыли исходного S0, то есть TOTAL>=5470396.514987347USDT. Предпочтение DD30% не заменяет верхнюю границу50%.

| Вариант | TOTAL, USDT | Global settled DD | Чистая прибыль относительно S0 | Решение |
|---|---:|---:|---:|---|
| Архивный S0, BTC+старый SOL |6077107.23887483|66.2569%|100%|Эталон, DD не проходит|
| R0, архивный E4, BTC+старый SOL |5631617.35953723|57.5854%|92.6573%|Эталон, DD не проходит|
| R1, E4 BTC без SOL |304372.03028516|66.9204%|4.8519%|Контроль, не проходит|
| R2, реальные U3TP +limit0.5%, LEGACY_Q_CONTROL, без SOL |225919.51131228|66.8015%|3.5589%|Контроль исполнения, не финальный CLEAN_Q|
| R3, то же исполнение +CLEAN_Q, без SOL |120718.40416503|68.6034%|1.8249%|Очищенный кандидат NONPASSING|

Точные значения, fees, funding, turnover, exposure, количества orders/partials/cancels и квалификация исполнения: [comparison.csv](comparison.csv), [comparison.json](comparison.json). Все83 фактических момента первых входов и стороны в каждом новом варианте совпали с архивным E4; количества/выходы/капитал пересчитаны самим native engine. Архивный SOL-календарь в новые результаты не импортирован. Старый explicit-SOL-child S0 с TOTAL6482334.93387961 и floor5835101.440491649 относится к другой модели исполнения и здесь не подменяет эталон.

## Что реализовано и проверено

Источник [ec2a958e383a53133f8a8d03ef0e312810881265](https://github.com/VF78/coinmaster/tree/ec2a958e383a53133f8a8d03ef0e312810881265), ветка codex/market-redesign-btc-20261024, изолированный canonical VPS-worktree от exactE4bd04c9b3858bcda40060a08eff488849c69af5d8. Mac исполнял только read-only snapshots. Research-флаги по умолчанию OFF. Публикация исходника не является deployment; GitHub check-runs фактически0, greenCI не заявлен.

- Сохранены E4 EMA34, причинные completed waves, стороны, rearm, REGIME/TRAIL и cap30m. Нет новых параметрических сеток, ML, price-SL BTC, нового движка/OMS/SDK.
- U: положительный причинный d3 сохраняется; d1=d3/3,d2=2*d3/3. Реальные native reduce-only LIMIT TP1/TP2/TP3 выставляются после первого fill на фактический inventory, с долями .2125/.2125/остаток. Цены связаны с фактическим first-child VWAP; provisional partial protection до terminal первого child, затем P0 фиксирован. После исполненного TP уровень не восстанавливается.
- Второй вход — только один LIMIT на0.5% выгоднее P0. Нет DEADLINE/EARLY_TP/day-end market chase. После первого TP-fill отменяется добор; late fills и cancel ACK обрабатываются по фактическому native состоянию. Partial первого IOC не увеличивает исходную second-half allocation.
- LEGACY_Q_CONTROL воспроизводит старый размер чистой причинной функцией без fake fills/TP/SOL rights. CLEAN_Q удаляет selector из фактического размера: phi_long=.8551535379805835/phi_short=.7977111237672364 после min(M*own_native_equity,30m), коэффициенты не подбирались по TOTAL.
- Если фактический terminal partial слишком мал для трёх допустимых TP, увеличение останавливается и остаток закрывается штатным native-механизмом; несуществующие TP не рисуются. Кэш/ACK/cancel reconciliation проверены. Восстановление открытого состояния после crash/restart остаётся UNPROVEN и не заменено новой системой recovery.
- Подтверждён и устранён дефект№81: прежний unfinished split блокировал TP, midnight stop не повторял постановку. Диагноз source+native ledger сохранён в precheck-executor.md.

Выполнены135 relevant checks с явной оговоркой о повторе одного исправленного exact-funding-schema assertion;18 новых genuine native случаев PASS. Независимый разбор выявил2P1 (terminal callback timestamp и historical-ACK/cancel race); они закрыты одним substantial correction batch, включая tiny-partial failclosed. Отдельно внесено observer-only исправление +3строки после фактического terminal FLAT; оно меняет только metric/audit. Один новый genuine terminal regression PASS. Исходный review и обе версии доказательств сохранены.

Короткие M1проверки31/48/65/81:4 первоначальных +4 разрешённых corrective, без executable prefix и без импорта архивных fills. Initial batch сохранил observer-open interval при уже flat; оригиналы не исправлялись задним числом. Corrective batch прошёл root acceptance: реальные ACK целей, terminalflat/order0, model liquidation0, закрытые protection intervals. №81 отдельно прошёл causal late-day admission fixture и pending second LIMIT через полночь. Это cold lifecycle diagnostics, а не архивная экономическая репликация.

## Учёт и исполнение

Все3fullprocess exit0;39/41/41 checks PASS. Каждый имеет1051199 непрерывных actual settled receipts, seed и фактический terminal cash добавлены в DD curve. Использован native marked cash+UPNL, не summary cash-DD и не closed-trade DD. В R2/R3 missing-three-TP duration0 на native observer, открытых исключений0, положительных TP-IOC0, model liquidations0, остаточных позиций/заявок0.

Signed funding получен непосредственно как native account balance after−before каждого начисления и сверен с отдельным persisted SQLitejournal по инструменту. Цена/комиссии сверены по действительным audit fills и native side/order exports. Независимая cash identity использует seed +actual flat fill cashflow−fees+actual signed funding+external flows0. Native-minus-derived residual: R1−0.00000002USDT, R2−0.00000004USDT, R30; малые native monetary rounding остатки явно сохранены, не названы funding и не подменяют terminalTOTAL. Неизвестный старый fundingR0 не придуман.

Freeze до первого full: [full-freeze.json](full-freeze.json), SHA2d2a8754d2b72809afcb6b2c25112208626f7711ff18d098ecfe4c31e67ce490;242 source files и13 input/provenance pins проверены. Python3.12.13/Nautilus1.231.0. Исходные source/config/data/policy/archivebar hashes подтверждены. Старый R0 переиспользован по верифицированному receipt, новый полный R0 не запускался; полный исторический dependency lock неизвестен, версия engine и текущий scrubbed environment зафиксированы.

Raw config сохраняет legacy positive-TP-IOC flag, но real-U branch явно выключает этот fallback; effective R2/R3 execution — native LIMIT с фактической maker/taker classification. Legacy zero-target netting flag также не влияет на real-U branch. Эти различия метаданных явно зафиксированы в freeze, не скрыты заменой полей отчёта. BASE Bybit fees maker0.020%/taker0.055%; market/IOC не переименованы в maker.

## Экономическая причина отрицательного результата

1. Удаление старого SOL меняет собственный капитал и последующие размеры BTC. Это полный причинный R1, а не вычитание713702USDT прежнего SOLfill-net из общего результата. Поэтому архивные4.858m BTCfill-net и frozen U-сценарии95–108% не являются результатом BTCalone. Главный выявленный источник потери TOTAL — исключение SOLalpha и последующий иной compounding.
2. R2 улучшает равновзвешенный net-return на фактический entrynotional с79.570 до93.837bp на цикл, но terminalTOTAL падает304372→225920. Средняя прибыль на единицу notional не сохраняет путь капитала. Наихудший цикл№31 ухудшается с−594.485 до−695.627bp; это известная проблема отодвинутого положительного TP2 уU.
3. R3 сохраняет почти тот же unit-return93.822bp, но terminalTOTAL падает ещё до120718; fixed-phi matching не сохраняет распределение долларового риска во времени. Его текущий капитал нельзя заменить архивными размерами. Плечо ради компенсации ROI не повышалось.
4. Global maxDD всех3новых вариантов: peak2026-07-06 13:40UTC →trough2026-08-19 06:14UTC. Это фактическая новая причина дальнейшего риска; улучшение старого апреля само по себе не доказывает решения текущего maxDD.

First-year/second-year, все83цикла, худшие9, худший отдельный цикл и сравнение83общих parent moments: native-analysis-attribution-R{1,2,3}-{cohorts,cycles,common-parent-observations}.csv. Для каждого из7новых DD>=30% и22fixed/year/fullwindows (включая старый E4каталог и все даты задания) сохранены native-analysis-attribution-R*-DDge30.csv/windows.csv. Отдельные native cash/UPNL components и executed-event counts дополняют эти окна. Сумма циклов совпадает с full native net в указанных rounding пределах.

Отдельные долларовые эффекты ранних TP, отсутствующего добора, first-size и compounding **не идентифицированы раздельно** тремя совместными вмешательствами. Сохранены наблюдаемые изменения quantities/entrynotional/TP/exit reasons на общих parent; они не сложены в выдуманный новыйTOTAL. Отдельных дополнительных full factorial controls бюджет не содержал.

Внутри окон exported raw markclose отличается от native instrument.make_price(close); небольшой bounded mark-rounding residual явно оставлен, не присвоен funding. На exact funding timestamp ties внутривременная attribution UNKNOWN; full funding/cash identity проверены. Realized/unrealized report-field исходного движка UNKNOWN не подменён независимым доказательством; наблюдаемая native cash/equity decomposition обозначена отдельно.

## SOL и следующие допускаемые действия

[Actual R3 SOLscreen](native-analysis-sol-R3-report.md):1529 допустимых H4состояний/77BTCциклов, actual native quantities сверены со settled trace. Изменённый R3BTCкалендарь не заменён E4:24новых timestamps,55старых исчезли, все1505общих quantities отличаются. Lag720H1, closedH4 ER24=96h, горизонты4h/24h, фиксированные fees/действия и year/cycle blocks сохранены; будущие outcomes не стали online-признаками.

Три разных50%размера (owner volatility-adjusted, half minimum-variance и half BTCfactor) дали отрицательную среднюю net action добавку в обоих годах. Защита close-grid tail положительна, но слабее равного по factor relief BTCtrim; преимущество по стоимости неустойчиво. Это не означает, что любой платный хедж плох; **полезный причинный risk gate не найден**. Статус STOP_SOL/INCONCLUSIVE. Новая SOLстратегия/3TP/SL не реализована и не названа работающей защитой; полного SOLrun не было.

[Допуск к следующему опыту](next-eligibility-review.md) также отрицательный. Один заранее определённый closed-H4 counter-swing мог отменить ещё pendingsecond у5/83parents, фактически позже исполнились4legs. Их суммарный frozen observed fill-net exfunding +1160.23USDT; удаление не показало общего преимущества. Из11parents глобального DD непосредственно затрагивается только№81. Это не counterfactualTOTAL/DD, и оснований расходовать ещё один full нет. P+fee-floor не допущен: связь глобального июль–август tail с более далёким положительным TP2 не установлена; сетка геометрий не запускалась.

**Выбор: R3 сохранить как понятный NONPASSING research artifact, не возвращать скрытно fake TP/market chase/SOLalpha ради ROI. Новый full пока не обоснован.** Для продолжения потребуется отдельная причинная гипотеза и новый согласованный бюджет, не остатки закрытого пакета.

## Артефакты и границы

- Источник/публикация: owner-source-receipt.json, owner-source.diff, source-publication.json; defaultOFF, production не менялась.
- Протокол/approval/полный расход: PROTOCOL_PROPOSED.md, approval.json, run-ledger.json. Потрачено3/3full и8/8short; активных/зарезервированных0, попытки закрыты.
- Воспроизводимые команды: owner-commands.json, owner-short-commands.json, root-R*-execution-receipt.json; fixed resolved configs owner-R*-expected-config.json. Все процессы directPythonPopen, fresh journal/namespace, scrubbed env; никаких time-l exit assumptions/авторестартов.
- Реальные fill/order/native funding/rawJSON/settled trace пути и hashes: native-analysis-R*.json и root-R*-execution-receipt.json; единый artifact index рядом. Уникальные сырые данные сохранены без изменений.
- Precheck: precheck-executor*, geometry-*, первоначальный sol-screen-*; actual R3таблицы native-analysis-sol-R3-*. Предварительные frozen расчёты не названы ROI/DD нового кандидата.

Это native диагностическая execution model: исторические M1реальны, BBO из minuteclose и depth1000 синтетические. L2/очередь/реальная ёмкость/внутриминутный DD неизвестны; historical current risk tiers не являются доказательством реальных liquidation outcomes. Новый out-of-sample не исследовался, уже просмотренная история не названа свежим OOS. Никакого победителя или live-ready режима этот пакет не установил.
