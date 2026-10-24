# CoinMaster: единый план сохранения прибыли и настоящего SOL-хеджа

Дата: 24.10.2026. Основание — текущий запрос владельца, пять отдельных файлов Downloads и проверенные native-артефакты. Инструкции внутри TXT рассмотрены как рекомендации: обязательный перенос B5/H5 и повторный H1-simulator не приняты автоматически. ZIP отсутствует по уточнению владельца; это больше не ожидаемый вход.

**Решение: сохранить BTC-ядро, исследовать совместное управление фактически удерживаемым риском BTC/SOL. B5/H5 не переносить в native по имеющимся результатам.** Работа начата: выполнена атрибуция старого SOL и проверена новая funding-гипотеза. Проходящего экономического кандидата пока нет. Этот план не объявляет достижимыми цели50/90 без дальнейшей проверки.

## 1. Цели и неизменные ограничения

Порядок выбора: достоверная бухгалтерия и исполнение → global DD<=50% без ликвидаций → исследовательский минимум прибыли70% → восстановление до90% и выше. Предпочтительна DD30–50%; ниже30% допустимо. Меньшая DD при утрате практически всей прибыли не считается решением.

Benchmark — исходный legacy S0, `[2024-09-01,2026-09-01)`, UTC, seed10000USDT, RESERVE0, TOTAL6077107.23887483, net profit6067107.23887483. Retention=`(candidate_TOTAL−10000)/6067107.23887483`.

| Квалификация | Минимальный TOTAL | Дополнительные условия |
|---|---:|---|
| Исследовательская ступень70% |4256975.067212381|DD<=50%, genuine native accounting, strict hedge/3TP, liquidations0|
| Финальная ступень90% |5470396.514987347|Те же условия; затем максимизировать прибыль|

Разрешённые70% — временный этап, не замена финальных90%. Не пересчитывать абсолютные цели от ослабленного BTC-only/B5. Explicit SOL-child S0 — другой execution/admission model и другой matched control; его нельзя подставлять вместо исходного benchmark.

BTC: опираться на существующие EMA34/направление, E4 wait/rearm, логику сигналов и участия в движении. S0 имеет105parents, E4 —83; выбранное ядро следующего опыта фиксируется явно. Не менять одновременно entries, размещение капитала, TP-якорь и SOL. Реальные TP1/2/3 обязательны на обеих ногах; zeroTP-селектор и скрытая standalone SOL alpha не могут стать финальным решением. Повышение плеча ради возврата ROI исключено.

Native Nautilus1.231.0 — единственный экономический движок. Никакого нового симулятора, большой сетки/Optuna/ML, SDK/сервиса/миграции. Пилот, production, сервисы, ключи, реальные ордера и переводы исключены. Sourcepush не deployment. Существующий dirty код сохраняется.

## 2. Что объединено и что отвергнуто

| Наблюдение | Следствие для действий |
|---|---|
| E4 с прежним SOL: TOTAL5631617.36, DD57.5854%, retention92.6573% |Сильный profit reference; недостаточная DD и не строгий hedge. Не финальный победитель|
| E4 без SOL R1: TOTAL304372.03, DD66.9204%, retention4.8519% |Старый SOL менял капитал, будущие BTCqty и admission. Повторять BTC-only full не нужно|
| Реальные BTC3TP R2/R3: TOTAL225919.51/120718.40 |Реальные ордера сами по себе не вернули экономику. Нельзя объявить CLEAN_Q удачным решением|
| Внешний B5front30/H5: TOTAL40017–40248, DD≈44.85% |Это непроверенные H1 summary claims, всего≈0.495–0.499% прибыли S0; до70% нужно140–141раз net profit. Не переносить как следующий кандидат|
| Внешние заметки: участие в прежних winners86.29→27.46%; старый TP3 шире короткого warmup |Проверить на исходных causal данных потерю участия/историю. Не настраивать лестницу по будущему winners/losers|
| H5 первая пятая half-MV |Даёт≈3.48–7.90% estimated factor relief на saved R3states, mean6.18%, не50%. Доля заполненияBTCf>=.5 не является измерением рыночного риска|
| H5 core без TP |Противоречит обязательным3TP на SOL. Не принимать молчаливое исключение|
| C1cut/restore: retention≈72.17%, DD51.8032% |Историческая близкая Pareto-точка, но DD>50 и старый SOL не квалифицирован как hedge. Не повторять семейство без нового механизма|

Сохраняем полезные идеи приложения: участие в трендах, causal TP3 history, actual-fill hedge quantities, полный funding calendar, учёт pre-fill equity peaks и shared liquidity. Не принимаем adverse-only пятиступенчатую лестницу как обязательное BTC-ядро, восстановление старого TP3 из83-cycle lookup как универсальную live feature, смену first-P0 на dynamic VWAP под видом технической правки, core без TP или повтор уже отрицательных favorable-.5ATR/recycle/full-in вариантов.

## 3. Выполненные шаги: денежная причинность и funding

### Старый SOL и капитал BTC — выполнено

Проверены25циклов/198actual SOLfills E4 и1051200парных minute marks. Сумма точно сходится:

`376562.11 factor +356176.04 residual −1616.89 execution basis −17418.93 fees =713702.32329125 SOL fill-net ex-funding`.

Factor использует frozen causal270D beta; secondary720H1 меняет разложение, но не actual money. Residual не доказанная торгуемая alpha. **56.9167% SOL-held времени BTC был flat**; наблюдаемый held PnL таких интервалов426629.8025USDT. Первые пять SOLциклов дали105055.25329125USDT fill-net до дальнейшего BTC compounding. Проверка начала циклов:9 доказанно BTCflat,3 BTCheld,13 timestamp ties UNKNOWN; прежнее краткое13/25 не использовать как новый проверенный факт.

Механизм влияния SOL на BTC: realized cash/fees/funding и текущий UPNL меняют equity/free margin; из собственного нового equity формируются размеры BTC и решения admission. Затем меняются последующие PnL, капитал и размеры следующих сделок. Эффект нелинейный. Нельзя вычесть старую SOL-прибыль из итогового TOTAL и оставить старые BTCqty. Нельзя сохранить BTCflat/excessSOL прибыль, просто переименовав её хеджем. Сохранить вклад возможно только через прибыль/снижение потерь нового совместного процесса и достаточное участие BTC; это ещё нужно доказать.

Signed asset funding старого E4 и точная counterfactual стоимость удаления SOL остаются UNKNOWN. Подробности/проверки: `sol-attribution-report.md`, protocol/result/verification и CSV рядом.

### Funding как источник оплаты защиты — проверено и отвергнуто

Изучив исследования carry, проверили одну новую ограниченную гипотезу на существующих R3fixed actions:1529H4states/77cycles,21371outcomes, неизменные3размера/4h24h, два заранее объявленных lag-funding bins и четыре settlement-boundary сценария. Полные BTC/SOL market funding calendars, будущие rates только outcomes;276 independent direct-sum checks PASS.

В lag-recipient bin HALF_MV24h funding покрывает лишь13.8%/7.2% fees по двум годам; net после funding −7.79/−12.77bp BTCnotional. Преимущество против equal-factor BTCtrim неустойчиво; вывод одинаков по трём размерам/четырём timing cases. **STOP_CARRY**: funding gate не допускается в следующий native кандидат. Это endpoint saved-data screen, не новый TOTAL/DD или hedge lifecycle. Старый price-tail metric не переименован в funding-adjusted DD. Результат: `carry-screen-findings.md` и воспроизводимые файлы рядом.

Новых native/full/short/training/simulator запусков на этих шагах0; продуктовый код не менялся.

## 4. Метод оптимизации: сначала допустимость, затем восстановление прибыли

### A. Диагностика участия BTC без engine — завершена, NO_GO

Выполнен один paired audit сохранённых E4/R1/R2/R3actual83parents и одна арифметическая проверка:332parent rows, четыре исходных trace по одному чтению, без matching/equity replay. Сопоставлены собственный equity, initial/filled/peak notional, entry/add/exit, holding time, fees/funding и earlycapital. Pending-order timeline и29H4requested gross остаются UNKNOWN; terminal snapshots не названы полным audit. Winners/losers только описательные outcome cohorts; original future equity/qty не переносились.

| Actual native diagnostic |E4 со старымSOL|R1 безSOL|R2 real3TP|R3 CLEAN_Q|
|---|---:|---:|---:|---:|
| Mean entered/requested gross,54known |83.869%|83.867%|76.738%|75.313%|
| Equal-parent mean BTCnet ex-funding,bp |80.673|80.680|94.833|94.818|
| Entered BTCnotional sum,millionUSDT |836.34|84.91|57.27|33.73|
| Own equity передparent20,15Jan2025,USDT |160437.86|25578.64|20911.14|19544.07|

E4/R1 почти совпадают по нормализованному участию и netbp, но резко расходятся по собственному капиталу. Не обнаружена ошибка делителяQ, которая возвращала бы недостающий капитал. R2/R3 имеют выше netbp, но16parents без второгоfill против1уE4/R1 и меньше time-exposure. Это не доказывает пользу восстановления всех доборов. Данные/ограничения: `btc-participation-report.md`, CSV и verification JSON.

Проверка frozen native R2/R3 уже установила730дней featurewarmup `[2022-09-02,2024-09-01)`, wavehistory730/min8/q60 и sourceguard против меньшей истории; actual source/audit фиксирует first-childP0, а не переякоривание по secondfill. **Короткий warmup и dynamicVWAP внешнего B5 не установлены как ошибка native. Их «исправление» не источник восстановления nativeROI.** Для следующего кандидата сохранить полную **доступную до решения** same-venue историю. Изменение history coverage, TP-якоря first-P0/VWAP и gross-Q policy — разные дельты. Cached83TP3 не универсальный live механизм; нехватку новой сырой истории фиксировать как blocker, не заполнять future labels. Native Q сам должен быть экономически объяснимым: размер от equity/risk и ограничений, не от признака «TPнулевой». Не повышать исходный риск/плечо и не маскировать legacy selector под новый Q.

**Выход A: NO_GO для следующего full.** Источник потери капитала подтверждён, новый поддержанный способ восстановить его strict hedge не найден. Непрерывная торговля/высокий gross, возврат zeroTP selector или повтор уже имеющихся native runs не допущены. H_PAIR_EXIT не получает admission из этого аудита.

### B. Проверить одну новую совместную гипотезу H_PAIR_EXIT

Предлагаемая гипотеза, ещё НЕ допущенная к full: реальные SOLTP/SL сокращают и защищаемый BTC-риск, поэтому защита не исчезает после прибыльного выхода SOL и не требует немедленно повторять607re-add churn. Это точечное изменение управления риском/выходами BTC, а не переписывание его сигналов. Отличие от старых ADD-only бюджетов — контроль уже удерживаемой позиции, не только новых заявок. Отличие от прежней постоянной страховки — отсутствие автоматического восстановления израсходованного hedge за счёт повторного входа.

До расчёта требуется один frozen контракт:

- Рыночный риск измеряется по actual BTCnotional, causal closed-bar volatility/ATR и доступному equity drawdown budget. Факт заполненияf, календарная дата, будущий MAE/перечень прошлых losers не являются risk signal. Точные формула/threshold/частота определяются из риск-бюджета и тестируются одним заранее объявленным вариантом; выбор «лучшего» gate задним числом запрещён. Никакого нового риск-score обучения.
- BTCflat⇒targetSOL0. При отсутствии риска SOL не открывается. Средний риск: исходный owner target `N_SOL=.5*N_BTC*sigmaBTC/sigmaSOL`, противоположный BTC знак, по completed data. Это50% по volatility-adjusted notional, не обещание50% снижения drawdown. Half-MV=`.5*N_BTC*cov(B,S)/var(S)` и half-factor=`.5*N_BTC/beta` остаются различными controls, а не взаимозаменяемыми названиями.
- Учитываются фактические fills и текущий BTC, а не Qmax/pending rights. Positive covariance/корреляция, covariance stability, lot rounding и margin проверяются до роста. При invalid inputs — NO_HEDGE и запрет увеличения риска; если защита обязательна, BTCadd отклоняется/непокрытый BTC уменьшается. Высокий риск нельзя лечить неограниченным плечом SOL.
- На всём actual inventory обеих ног всегда три экономически осмысленных reduce-only TP, подтверждённые действующие native ордера; отправленная команда не считается ACK/покрытием. Положительные цены, реальная дистанция с учётом tick/fees/волатильности и сумма qty должны быть проверены; tiny partials/округление/fill до ACK имеют явный failclosed путь. Core без TP не допускается. Объём ниже допустимых трёх минимальных ордеров нельзя оставлять скрыто незащищённым. Время/объём фактического отсутствия защиты отдельно измеряются; асинхронность не разрешает объявить «всегда» без native evidence.
- После SOLTP/SL фактическое покрытие пересчитывается. Если оно ниже обязательного floor, соответствующий BTC-риск сокращается; нет automatic re-add. Exact proportional-risk rule, частичные исполнения обеих ног, adverse movement между fills и latency limit должны быть определены до реализации. Несинхронные два инструмента не дают атомарного исполнения/гарантии DD.
- Cost/no-trade buffer допустим только над обязательным hedge floor. Funding — реальная стоимость, не standalone разрешение на SOL и не причина пропустить обязательную защиту. Для исходного входа можно применять только уже разрешённую native execution policy; timeout market chase/повторные IOC ради обхода ограничений исключены.

Сначала дешёвый **локальный action screen** H_PAIR_EXIT на исходных actual states против NO_HEDGE и equal-factor BTCtrim. Учесть потерянный последующий BTC upside, обе ноги fees/slippage/funding и состояния после SOLTP/SL; оценки по годам и cycle blocks. Это не второй portfolio simulator, не новый matching и не финальныйTOTAL/DD. Фиксировать реальные limits данных/latency. Не перебирать risk gates/TP weights по положительному результату. Если даже локально нет устойчивой полезности/источника роста раннего капитала — STOP_PAIR_EXIT; не расходовать full.

**Допуск B:** новый механизм отличается от закрытых отрицательных семейств, сохраняет BTC participation, имеет поддержанную cost/benefit гипотезу и реалистичный путь к70%. Положительная защита отдельных хвостов либо процент winrate сами по себе не допуск. Сейчас этот gate не пройден; текущий план не утверждает, что H_PAIR_EXIT прибыльна.

### C. Native реализация только после допуска A/B и точного протокола

Один GPT-6.1Sol/medium executor без истории чата, один writer engine/domain/journal. Isolated VPS worktree, existing nativeadapter/cache/account, defaultOFF; Mac — immutable commit snapshot. Узкая independent money/order review. Сначала meaningful tests: partial/reject/expire/latefill, generation ownership при замене TP, actual hedge deficit, minimum lots, margin denial, joint exit latency, funding sign, cash reconciliation, terminalflat. Crash recovery не объявлять доказанным.

До экономики проверить execution capacity. Синтетические1000SOL в L1 — fixture, не историческая глубина. Не разбивать один deficit на повторные IOC с «обновлением» той же глубины. Если нужен новый execution model, его сравнивают с matchedcontrol, сохраняя исходную абсолютную цель. Нет настоящегоL2/queue⇒capacity/live realism UNKNOWN.

Следующий source/config/data/fees/engine/TP/hedge/DD protocol и физический бюджет должны быть отдельно зафиксированы/согласованы перед реализацией торговой логики и engine-run. Старые3full/8short закрыты. Возможный будущий потолок **до4short и до2full включая неудачные** — только предложение, не открытый бюджет и не квота к расходованию. Сначала один кандидат; второй full только на одну обоснованную коррекцию/проверку. Если нужны дополнительные matchedcontrols, они также входят в новый согласуемый лимит; бюджет/план нужно пересогласовать, а не прятать «control» вне счёта. Сейчас0active/0reserved/0authorized новых engine attempts.

### D. Native совместная квалификация и возврат прибыли

Каждый полноценный кандидат живёт на **собственном капитале** от10000: BTC/SOL quantities/admission/margin пересчитываются с actual fills/funding. Fresh native namespace/journal, causal features и неизменный economic calendar. Нельзя сшивать лучшие old/new сделки или брать старый BTC PnL в новый equity.

Отчёт обязан показать TOTAL/net retention, global comparable settled marked-equity DD и отдельно coherent event-level DD с pre-fill/pre-open peaks, terminal inventory, model liquidations, cash/fees/funding, число/время провалов hedge и3TP, turnover/slippage, broken/tied data. Финальный PASS требует<=50% на обеих заранее определённых согласованных шкалах; худший eventDD нельзя скрыть хорошим settledDD. Несогласованные cash/position snapshots не считать event-DD. При недостатке event данных — UNKNOWN, неPASS. Старый settled DD не выдаётся за intraminute limit. Абсолютный DD<=50% нельзя доказать одним ATR/correlation/CVaR расчётом.

Кандидат ниже70% — диагностический FAIL, даже если DDхорошая. Ниже50%DD, но ниже70%profit — не база для бесконечной настройки. При честном проходе70%/50% заморозить механизм и затем корректировать **один параметр за шаг** по известной причине потери upside/стоимости: timing покрытия, участие/выход BTC или cost buffer над floor; не все одновременно и не повышая исходное плечо. Каждый следующий engine опыт — новый заранее ограниченный допуск, не автоматическое продолжение. Финальная квалификация>=90%/DD<=50% плюс все инварианты.

2024–2026 уже многократно просмотрены; годы/cycle blocks и повторный run — robustness/reproducibility, не fresh OOS. После исторического прохода нужен замороженный протокол проверки на действительно неиспользованном периоде. Изменений пилота/production для этого текущим заданием не разрешено.

## 5. Почему выбран такой метод и как использованы внешние источники

Читались оригинальные статьи, код, интервью автора и discussion/forum материалы. Источники дают механизмы и ограничения; ни один не доказывает CoinMaster50/90.

- [Chekhlov–Uryasev–Zabarankin, drawdown optimisation](https://www.cis.upenn.edu/~mkearns/finread/drawdown.pdf): ставить drawdown ограничением, прибыль вторым критерием. Их CDaR/constant weights не решает наш stateful compounded native portfolio напрямую.
- [Bailey et al., Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf): учитывать все попытки и selection bias. Не выдавать использованные годы за OOS и не считать PBO без требуемой матрицы экспериментов.
- [Gârleanu–Pedersen, Dynamic Trading](https://nbgarleanu.github.io/DynTrad.pdf), [Carver, исходное интервью](https://investresolve.com/podcasts/rob-carver-uncertainty-principles/): текущее inventory/издержки и неопределённость оценок важнее формального target. Отсюда buffer/turnover контроль, но не пропуск обязательного hedge.
- [Leung–Li, transaction-cost entry/exit](https://arxiv.org/html/1411.5062v3): вход и выход согласовывать вместе. Не предполагать, что BTC/SOL residual действительноOU или mean-reverting только по beta регрессии.
- [Risk-Constrained Kelly, Stanford](https://web.stanford.edu/~boyd/papers/kelly.html): полезна постановка growth under risk constraints; вероятность wealth floor в модели не гарантия фактического maxDD50%. Новую Kelly-инфраструктуру не внедрять.
- [pysystemtrade buffering, зафиксированный код](https://github.com/pst-group/pysystemtrade/blob/164328bd76d2937d3dd61491377704c488283bc2/systems/provided/dynamic_small_system_optimise/buffering.py): partial adjustment/no-trade region как идея снижения churn. Не использовать buffer ниже required protection. [Hummingbot GridExecutor](https://github.com/hummingbot/hummingbot/blob/9af100d6822da7d2d0291a906c730ef172284ee2/hummingbot/strategy_v2/executors/grid_executor/grid_executor.py) даёт lifecycle patterns, но его grid не копируется как прибыльный BTC алгоритм. Dynamic Grid Trading и Freqtrade использованы для проверки ограничений grid/lookahead, не как новый движок.
- [BIS Crypto Carry, 2023](https://www.bis.org/publications/working-paper-1087-crypto-carry): carry не бесплатный доход; изучаемый futures basis BTC/ETH не доказательство выгодного SOLperp hedge. Результат проверки CoinMaster выше STOP_CARRY.
- [BIS, март2026](https://www.bis.org/publications/qr-202603/markets-recalibrate-amid-shifting-currents): падение BTC примерно50% от пика2025 и усиление leveraged liquidations — основание stress cases по gaps/margin/funding/correlation, не торгуемый новостной фильтр или independent OOS.

Подробные source notes/ограничения: `sources-methods.md`, `sources-mechanisms.md/json`, `source-registry.json`. Forum/Reddit — anecdotal источник вопросов, не численная калибровка. GitHub/бумажные результаты чужих стратегий не переносить как expectedROI CoinMaster.

## 6. Текущий статус и следующий шаг

DONE: loose-file audit; reuse старого BTC-only и R1 вместо повторов; точные70/90floors;25SOLcycle attribution с денежной сверкой; новый bounded carry screen STOP_CARRY;332parent BTC participation/history audit A_NO_GO; научно-практический план и отмена необоснованного B5-переноса.

NEXT: новый **admission memo**, а не повторA/новый full: назвать конкретный рыночный сигнал риска при heldBTC, объяснить восстановление раннего совместного капитала без BTCflat/excessSOLalpha и показать отличия от закрытых отрицательных семейств. До любого нового screen заранее зафиксировать одну проверяемую гипотезу/контракт и stop gate против equal-factor BTCtrim с обеими costs/потерянным BTCupside. Пока такого основания нет, B/C/D не исполняются автоматически. H_PAIR_EXIT — архитектурное предложение, не экономически допущенный кандидат. Потребность в новом native бюджете задаётся конкретным кандидатом; открытого нового бюджета нет.

Экономическая цель **NOT_MET**. Капитал старого самостоятельного SOL нельзя обещать сохранить одним формальным half hedge; итоговая прибыль/просадка проверяются только совместным native процессом.
