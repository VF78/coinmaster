# C1 residual risk / bounded recovery — пакет завершён, NO_GO

Цель DD≤50% и ≥90% чистой прибыли S0 НЕ достигнута. C1 в production не переносился. Пилот/сервисы/ключи/ордера/deployment не менялись; S0/E4 переиспользованы без пересчёта.

| Вариант | TOTAL USDT | Сохранено прибыли S0 | Global settled-minute DD |
|---|---:|---:|---:|
| S0, архив | 6 077 107,24 | 100,00% | 66,26% |
| E4, архив | 5 631 617,36 | 92,66% | 57,59% |
| C1, native | 4 388 613,38 | 72,17% | 51,80% |

- [x] R0: полнокалендарный saved-data screen и exact control/data pins.
- [x] R1: зафиксированы причинные правила cut/restore, actual-fill credit, ownership и SOL/TP rights.
- [x] R2: source/review/native focused tests; финальные 18 PASS, 92 read-only source / 13 input pins.
- [x] R3: полный native путь, 1 051 199 receipts / 24 месяца / 0 gaps; 44 accounting checks и 933 assertions по механизму PASS после документированного исправления verifier.
- [x] R4: причинный postmortem; C2 не реализован/не запущен, отрицательное семейство остановлено.
- [x] R5: сохранены сравнение JSON/CSV, hashes, отрицательные результаты, инцидент экспорта и решение NO_GO. Done означает завершение этого исследовательского пакета, а не достижение экономической цели.

Причины: 9 сокращений / 3 возврата; ценовой разрыв cut→restore 385 696,02 до комиссий, 30 498,04 комиссий самих вмешательств. В январе native IOC исполнил лишь 1 000 из запрошенных 2 000 SOL; оставшаяся экспозиция сохранила DD 51,80%. Пять августовских cut относятся к затяжной общей просадке, четыре могли бы запрещаться общим rearm, но их исходы смешанные. Эти cashflow и локальная арифметика не выданы за новый портфельный TOTAL.

Бюджет закрыт: 2/4 физических попытки, 1 невалидный export и 1 полностью проверенный native-результат; 0 active/reserved. Два слота не израсходованы, новых автоматических запусков нет. Более сильный cut, завершение partial target и общий rearm потребовали бы трёх экономических изменений без обоснованного восстановления недостающих 1,08 млн до profit-floor. Независимый review рекомендует STOP.

Source 78100d4; export-only correction 78cb85a, numeric state/orders/config неизменны. Первая попытка не восстановлена и не принята. У второй сохранён wrapper exit1 из-за macOS time-l/sysctl; native child exact exit UNKNOWN, но native CLI COMPLETED/hash, все выгрузки и независимые checks подтверждены. Исходные 13 verifier FAIL сохранены; отдельное adjudication исправляет enum/точный native Price float representation, без изменения денег/DD.

[Итоговый отчёт и материалы](https://github.com/VF78/coinmaster/tree/codex/btc-pattern-pilot-m2-20261021/reports/residual-recovery-20261023).

Следующее предложенное направление исходного порядка — saved-decision анализ исполнения второй BTC-половины и прибыльных fallback; перед новым native запуском нужны конкретное действие и численное обоснование. Большая оптимизация/новая ML/новый хедж не запускаются. Нынешний diagnostic 1m CLOSE не является tick/HL-live или новым OOS доказательством.


---
## Предыдущий завершённый аудит / результаты сохранены

# Системный аудит точного S0 — завершён

Done означает завершение аудита, а не достижение DD50/90. Новый экономический вариант не выбран. S0 не пересчитан, новых native-прогонов/MLfit/source/deploy/pilot/service/key/order изменений0.

[Полный отчёт + BTC/SOL/source/JSON/CSV](https://github.com/VF78/coinmaster/tree/codex/btc-pattern-pilot-m2-20261021/reports/s0-system-audit-20261023). ExactS0source75ffc9c69e9d79c4da4cd0614634a3eeba48d716/config22e1ee;72/72sourcepins. 15 сопоставимых полных settled-DD путей,11 внешних научных/официальных/экспертных источников,2 сохранённых common-base2×2 interactions,5 native endpoint bridges;88арифметических проверок и independent scoped review PASS.

- [x] A0: identity/source/config/data, terminal settlement и ограничения исполнения.
- [x] A1: BTC signal/sizing/split/TP/fallback/reentry/group-exit, проверена utility против selection.
- [x] A2: SOL beta/z/права/аддитивный sizing/выходы; alpha против страховки, actual endpoint risk.
- [x] A3: сохранённый реестр/полный portfolio frontier, invalid/partial/repeat/AI и разные DD observers отделены.
- [x] A4: применимость DOE/interaction, Pareto, attribution/headroom, sensitivity/selection methods опробована на сохранённых фактах; no new engine.
- [x] A5: единый аудит/приоритеты/future protocol, independent review, checkpoint/read-back.

Критерий прежний: DD≤50% (30–50% желательно), TOTAL≥5470396.514987347, затемMAX_TOTAL. S0TOTAL6077107.23887483/DD66.2569148647; E4TOTAL5631617.35953723/DD57.5854104596/ret92.6573. E4запасдоprofitfloor161220.84455, gapDD7.5854п.п. Ни один сохранённый вариант50/90не проходит.

Выводы: SOL — selectivealpha, не continuousinsurance; actual presence15.37844%BTC-heldtime. HпривязанкgrossBTC/entrybeta,неостатку; worst frozenbeta exposure292.29%remainingBTC. DDмеханизмыразные: SOLoverhedge/SOLonly/BTCsqueeze/realizedlosssequence. Fixedcuts/earlyTPтеряютrecoveries; цена/капиталважнееоднойэкономиикомиссий.

Исправлены прежние трактовки, не торговые правила: beta270D1,а720hmetadataнеактивно;2BTC TRAILfillsнеравныgrouptrails(39SOL TRAILfills); diagnosticmaintenance/liquidationесть,старыйlabelустарел. NOT_FAITHFUL/1mCLOSEsyntheticexecution/notfreshOOS/signedfundingUNKNOWNсохранены.

Следующий протокол только ПРЕДЛОЖЕН: existingdomain/nativeexecutor, residualrisk+causal boundedrecovery/qualityofsecondleg; фиксировать action/state/rights/rearm, затем малый совместимый полныйportfolioexperiment. Новый числовой порог/источник/прогон не реализован и не разрешён автоматически.

---
## Предыдущий завершённый пакет — сохранённые результаты

# E4 SOL budget / BTC early TP3 — завершено, цель50/90 НЕ достигнута

Выполнено согласованное исследование:3/4 физических native-попытки, две валидные версии и одна сохранённая невалидная попытка. Done означает завершение bounded research, а не экономической цели. Пилот/production/сервисы/ключи/реальные ордера/deployment не менялись. S0/E4 не пересчитывались.

[Отчёт и JSON/CSV](https://github.com/VF78/coinmaster/tree/codex/btc-pattern-pilot-m2-20261021/reports/e4-budget-tp3-20261023). Source5dc17f0a8c6bc764746683f4d38bcf1fa9dcc77e; report-only precision fix6061446164cc32c27b3ea0e13e86c9cc56d955ac, оба exact GitHub refs PASS.

Acceptance:global settled-minute DD≤50%,TOTAL≥5470396.514987347(≥90% чистой прибыли S0),затемMAX_TOTAL. [2024-09-01,2026-09-01),10000USDT,RESERVE0/DPoff,прежние Bybit/fees/funding/margin/native execution.

|Версия|TOTAL USDT|Сохранено прибыли S0|Global DD|
|---|---:|---:|---:|
|S0 архив|6077107.23887483|100%|66.2569148647%|
|E4 архив|5631617.35953723|92.6572934712%|57.5854104596%|
|SOL budget|1360086.36695243|22.2525548634%|66.8590474891%|
|BTC early TP3 corrected|4120806.47444031|67.7556257470%|61.0796583181%|

## Выполненные задачи

- [x] T00: HEAD/контроли/действующее разрешение сверены, прежние результаты и пользовательские изменения сохранены.
- [x] T01: до реализации/прогонов frozen SOL35%DD/55%H/1×completedD1WilderATR14/conservativeBTCreserve/oncecycle-excesscut/genuine-unused-add budget; BTC20%actualinitial изTP3 на1%PLANREF,remainingTP3 по старой цели,TP1/2fallback и existing actualpartial proportional SOL rights.
- [x] T02: isolatedcanonicalVPS/defaultOFF/прежний nativeexecutor/domain/PnL;224unique focused/relevant PASS,actualpartial/cancel/denied/forcedexit/SOLsubmit/no-consumption.
- [x] T03: independent scopedreview/source/config/data/toolingfreeze/rootGO. Одна report-only коррекция localDecimal80 месячнойсверки, ПРЕЖНИЙ1e−24guard.6focusedPASS+independent correctionGO, стратегия/config/data/fees unchanged.
- [x] T04: SOL#1VALID; BTC#2 послеengine прерванreportassert+незакрытыйgzip — INVALID,rawнечинился. BTC_CORRECTED#3 newengine/journal,normalcompleteexports. Две валидные версии independently PASS,1051199/1051199receiptsкаждая,0gaps/0liq/terminalflat.
- [x] T05: COMBINED=NOT_RUN_GATE_FAILED;FRESH_REPEAT=NOT_RUN_NO_50_90_CANDIDATE. Четвёртаяпопытканепотрачена,launchauthorizationclosed,active/reserved0.
- [x] T06: comparison/fees/maker-takerturnover/cashbridge/48months/21globalexcursions/targetwindows/actualrisk+TP3lots;26independentfilehashes/934rootQA/finalcompactreviewPASS;checkpoint/Projectreadback.

T00→T01→T02→T03→T04→T05→T06 завершены. Ни скрытогоP0/controlrerun,ни сетки/новоймодели/SDK/PnLengine/миграцииNautilus/деплоя.

## Выводы

SOL:5decisions/26actualriskfills/23994.6SOL;13отказов полнойштатнойadd. ОктябрьDD50.1322%,январь44.5333% лучшеE4,ноTOTALпотерял4.272млн,globalDD66.8590%летом2026. BTCcalendar/prices337fillsсохранены,320qtyизменены вследзакапиталом.

BTC:82allocations/68actualearlyfills,66MAKER+2TAKER;early+remainingнепревышаютoriginalTP3target. НоябрьDD43.8691%вместо54.7928%,нооктябрь61.0797%/январь54.2320%,TOTALпотерял1.511млн. Локальныйэффектнепроходитпортфельнуюцель.

Новыйвариантдляdeployневыбран;S0сохранён,E4остаётсяисследовательскойбазой. Следующиеновыепрогоны/параметрытолькопосленовогозадания;незатраченныйслотнеразрешаетпродолжать.

NOT_FAITHFUL_DIAGNOSTIC/1mCLOSEsyntheticquotes/notfreshOOS;settledDDнеintraminute/liveгарантия.SignedassetfundingUNKNOWN,cashbridgeнеfunding.ОтсутствующаяasofпроекцияPLANREF/доменныхправUNKNOWN;формулапроверенаsource+nativefixtures,доступныеlots/ownership/fillsпроверены.OriginalfailedBTCневыдаётсязауспешныйrepeat.
