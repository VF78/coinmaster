# S0: full systematic audit, contract repair and H_SOL / H_BTC

All original owner requirements 0-4 remain tracked here. No single failed hypothesis closes this parent. Latest owner task is integrated below.

- [ ] #124 SC-00 S0 rules, evidence, controls and systematic optimization methods
- [ ] #125 SC-01 Explicit SOL execution policy and native equivalence
- [ ] #126 SC-02 Causal BTC parent dataset and zero-TP branch sensitivity
- [ ] #127 SC-03 H_SOL add-only portfolio risk admission
- [ ] #128 SC-04 H_BTC causal repeated-entry Q90 sizing
- [ ] #129 SC-05 Native controls, separate hypotheses and gated acceptance

# Единый план: полный аудит S0 и ограниченная проверка H_SOL / H_BTC

Основание: исходные требования владельца 0–4 и новый OWNER_TASK.txt. Существующий широкий аудит и отрицательные прогоны переиспользуются; C1, SOL budget и early TP3 не повторяются под другими именами. Parent Project #123 отражает весь пакет, а не последний эксперимент.

Цель: global settled marked-equity DD≤50%, минимум 90% чистой прибыли сопоставимого S0, нулевые model liquidations, полные деньги/позиции/заявки. DD≤30% — дополнительная цель. Старый абсолютный TOTAL floor=5470396.514987347 отдельно от относительного floor при изменении execution model. Период [2024-09-01,2026-09-01), seed10000USDT, RESERVE0; global high-water не сбрасывается. Sharpe и прочие метрики не заменяют критерий TOTAL.

## Общие ограничения

- Исследовательская работа: пилот, production, сервисы, credentials и реальные ордера не менять.
- Продуктовый код — только isolated canonical VPS checkout, не dirty основной checkout и никогда не /opt. Mac — выполнение неизменяемого снимка, данные и отчёты; один владелец engine/domain/journal, общие файлы не меняются конкурентно.
- Новые исполнители: GPT‑6.1 Sol / medium, узкий контекст. Один focused implementation pass, relevant verification, адресное независимое money/order review; максимум одно содержательное исправление конкретного дефекта.
- Максимум шесть НОВЫХ физических полных native-попыток, включая failed/invalid/corrected/control/combined/repeat. Старые закрытые ledgers не обнуляются и не переносятся. Каждый полный запуск — только после protocol/source/config/input/engine freeze, tests/review и root GO. На подготовке запусков 0.
- Nautilus — единственный economic engine; нет синтетического PnL, поддельных native terminal receipts и восстановления UNKNOWN нулём. Нет новой ML, grid/Optuna, широкого поиска EMA/TP/плеча/z или нового risk/execution сервиса.

## Пакеты и критерии готовности

| Пакет | Требования владельца | Результат и критерий готовности | Зависимости |
|---|---|---|---|
| SC-00. Контроли, методики, полный реестр правил | 0,1,4; документ §§1–3 | Exact S0/E4/source/flags/observer/settlement; существующие результаты/ledgers сверены. Каждое активное экономическое правило получает source, назначение, происхождение/обоснование, VERIFIED/CONTRADICTED/HYPOTHESIS/NOT_TESTED, доказательство пользы/вреда и KEEP/FIX/TEST/DEFER. Неоптимальность не объявляется ошибкой исполнения. Существующие 11 источников/2×2/атрибуция переиспользованы; новые источники только адресно. Ни один исходный пункт 0–4 не потерян. | Первым; реестр пополняется измерениями следующих пакетов |
| SC-01. Явное исполнение SOL и equivalence | 1,3,4; §§3.1,4 | Native fixtures requests <1000/=1000/>1000 при depth500/1000/2000; shared liquidity, partial/cancel/reject/late fill, две ступени, D1 retry, права, held/pending и margin. Explicit child cap1000 на исходную разрешённую ступень/попытку без новых внутридневных попыток. Intended→allowed→submitted→filled→unused→next attempt наблюдаемы. Эквивалентность lifecycle/экономики доказана или первое расхождение названо; FILLED не подменяется CANCELED. | SC-00; source/test/review до historical control |
| SC-02. Причинные BTC parents и zero-TP | 1,2,4; §§3.2,5 | Parent-level causal dataset: closed ATR/EMA/wave-age, first/repeat, available positions/orders/equity/E4 gate; q0/q1/zero branch/gross/net/cap/lot/VWAP/SOL-rights. q1 perturb±0.1/0.5/1/2/5bp с native tick rounding — только локальная sensitivity. MAE/MFE до конца волны с ready_at/censoring и единым minute-mark basis; future label не feature. Полнота/пропуски и независимые волны названы. | SC-00; observation hook согласован с единственным engine owner |
| SC-03. H_SOL — бюджет только новых adds | 3,4; §6 | Frozen55%H/closedWilderATR14/conservativeBTCreserve без подбора. Проверка КАЖДОЙ новой SOL_ADD, без DD35 trigger/forced trim/auto-restore. Held+pending+reserved+candidate, две ступени не тратят бюджет дважды. Наибольшая допустимая часть в rights/child/lot/fee bounds; units и монотонность доказаны до формулы/поиска. Невместившееся право сохраняется, clock/частота неизменны. | SC-00/01; не повторяет прежний budget+trim |
| SC-04. H_BTC — причинный sizing повторного входа | 2,4; §7 | Только завершённые метки с ready_at<decision; две группы first/repeat, sides вместе; frozenATR/firstactualfill PLANREF, marks до закрытого D1 EMA-switch. Минимум8 валидных наблюдений каждой группы; k=min(1,Q90first/Q90repeat), иначе1 с причиной. k один раз до zero-TP/lot corrections, не компенсируется SOL/плечом/частотой. Quantile/interpolation frozen; prefix/incomplete-wave/partial-weight tests PASS; activation и wave count показаны. | SC-00/01/02; затем отдельный native candidate |
| SC-05. Полная native-проверка и интеграция | 0,2,3,4; §§8–11 | Последовательные control→H_SOL→H_BTC→gated combination→passing repeat, всего≤6. Архивные controls используются только при сопоставимости; при неэквивалентности новые S0/E4 в одинаковой модели за счёт тех же слотов. Семь E4 эпизодов+все24месяца+новые global maxima; fees/money/rights/denial/fills/calendar/recovery. Принят или честно отклонён вариант; полезные engineering fixes отдельно от проигравшей политики. | По мере готовности SC-01/03/04, полные движки только sequential |

## Протокол запусков и рубежи

G0 — Project покрывает исходные 0–4 и все новые §§1–12, есть actual read-back; начальные ledgers/контроли сверены.

G1 — короткие контракты исполнения/данных/units/prefix tests и независимый review пройдены. protocol.json содержит точные формулы/defaults, versions/hashes, quantile method, source/data/engine/config, семантику семи окон, причинное объяснение и порядок. До G1 полных запусков нет.

G2 — отдельные H_SOL/H_BTC технически валидны, действительно активировались, локальный механизм подтверждён, money/rights/календарь корректны, control сопоставим. Только тогда комбинация. Индивидуальное прохождение глобальной DD50 не обязательно для комбинации, но отсутствие эффекта/невалидность не лечится объединением.

G3 — полный GO/NO_GO по абсолютному и сопоставимому90%-floor, global DD/нулевым liquidations и terminal accounting; fresh-engine повтор только полного проходящего кандидата. Fresh repeat не OOS. NOT_RUN всегда с конкретной причиной.

Начальный бюджет: E4 explicit-policy control; при неэквивалентности — S0 в той же новой policy; H_SOL; H_BTC; только обоснованная комбинация; passing repeat. При дополнительном необходимом контроле/ошибке сокращаются кандидаты, лимит не расширяется. Дорогой исторический stress depth не запускается без места и сопоставимых controls; short-fixture stress не выдаётся за portfolio robustness.

## Семь эпизодов и критерий полноты

Сверить recipe-specific peak/trough/recovery для 03.10.2024, 13.01.2025, 11.04–06.06.2025, 06–18.09.2025, 22.10–28.11.2025, 08.02.2026, 06.07–19.08.2026. Даты — диагностические окна, не условия торговли. Плюс все месяцы и новый global worst. Cash bridge не называется funding; missing signed funding остаётся UNKNOWN.

## Завершение и статус

Каждый пакет закрывается только по его артефакту и acceptance. Родитель не закрывается из-за результата одного C1 или другой отдельной гипотезы. После покрытия ВСЕХ пакетов исследование может завершиться GO или NO_GO; торговая цель отдельно остаётся NOT_MET при отсутствии проходящего кандидата. Нерешённые пункты/NOT_TESTED не скрываются за Done.

Обязательный report pack: protocol.json, run-ledger.json, contract-audit.md, execution-equivalence.json, btc-causal-risk.csv, comparison.json, episode-attribution.csv, REPORT.md + native receipts/manifests. На текущем старте: подготовка, 0 новых historical engines, никакого изменения пилота.


---
## Previous completed C1 and audit evidence preserved

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
