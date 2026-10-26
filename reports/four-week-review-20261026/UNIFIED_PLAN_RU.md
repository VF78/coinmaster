# Единый план после четырёхнедельного обзора

Статус: CONSOLIDATED_RESEARCH_PLAN_AFTER_P1 / NO_NEW_NATIVE_BUDGET. Основание: [REVIEW_RU.md](REVIEW_RU.md), четыре evidence-registers и результаты P1. Цель остаётся: настоящий SOL-хедж BTC, реальные TP и исходныйBTCcore; сначала≥70% чистой прибыли originalS0 при settled+coherenteventDD≤50%, затем≥90%, предпочтительныйDD30–50%. AbsoluteTOTAL floors4 256 975,067212381 /5 470 396,514987347 не снижаются.

**Приоритет: сначала определить исполнимый и экономически осмысленный контракт; затем проверить один механизм; только после этого оптимизировать параметры.** Исправить SOL cancellation недостаточно, чтобы восстановить старый SOL-alpha. A0 не назначается заранее победителем.

## P0. Закрыть обзор и заморозить исходные факты

Завершить семейный реестр, сопоставимость контролей, статусы UNKNOWN/NOT_RUN, причины failures и этот план; узкая независимая проверка чисел/противоречий. Сохранить evidence и Project. Никаких новых моделей/прогонов. Результат: один опубликованный пакет и текущий handoff вместо возврата к старым чатам.

Exit: все существенные семейства покрыты; ни один oldcontrol/плохой export/fixturePASS не объявлен qualified70/90winner. После этого, а не параллельно разработке нового продукта, начинается P1.

## P1. Две обязательные аналитические зависимости до кода

### P1a. Контракт SOL TP/SL lifecycle — прежняя задача1

По committedsource7f38278 и installedpublicAPI зафиксировать таблицу переходов:

- Initial3TP/STOP; partialfill и multiplefills в одном native settle; consumedtarget; остаточные количества и dust.
- Actualnative owner/OID/strategy/instrument/parent/generation; NETTINGrawpositionfield отдельно от cacheassociation. Никаких ручных cachelinks.
- Publicmodify totalqty=actualfilled+desiredleaves; queue return отдельно от actualACK; deduptyped/genericUUID; rejection/unknown/deadline.
- Защита при CANCEL_PENDING, latefill, marketable replacement и втором cancel/replace цикле; SOLflat с ещё pendingSTOP; no unintended reversal/extra cut.
- Непрерывность BTC TP, marketableBTCdebtDEFER с outstandingquantity/duration; firstcleanquote→actualresidual; flat→NOnewdebt.

Техническая гипотеза для проверки: сохранять оставшуюся уже работающую защиту и менять только необходимое посредством publicnativeAPI; не отменять весь комплект после каждогоfill. Это не решение по умолчанию. Возможность exactquantities/postOnly/trigger/remainingTP/ACK проверяется по source/API; если stockroute не позволяет контракт, явно выбрать иной минимальный lifecycle до кода. Guard не выключать, котировки не разрежать под результат, latency не менять внутри engine.

Три цели относятся к реальным положительным исполнимым объёмам. Исполненный TP не выставляется заново; remainingheld покрывается оставшимися standingorders. Недостаток лотов/UNKNOWN не маскировать нулевыми ордерами или audit-only целями.

Exit: одно concrete minimaldesign, exactAPI/ownership/quantityrules, тестовая карта достижимых событий и явные ограничения. Noengine sourceproof не равен nativePASS.

### P1b. Экономическая состоятельность и ранний капитал — дополнительная задача

Составить по сохранённым данным компактную decision-table четырёх причин изменения BTC: потеря BTCflat-SOLalpha, отмена ещё действующего child, permanentBTCcuts, изменение nativeTP/sizing/execution. Не приписывать каждой причине dollar-effect из разных owncapitalpaths.

Проверить два разных механизма, без нового PnL-движка:

1. **G1/A0:** возвращает только действующий неисполненный originalsecondchild после снятия риска; не возвращает закрытыйBTC, consumedFIRST или новые попытки. Должны существовать реальные недоиспользованные права и достаточный охват, чтобы проверка имела смысл.
2. **G2/riskcontract:** fixedH≥kB иH→0 требуютB→0. Для сохраненияBTC нужен причинный переход риска вinactive либо заранее ограниченный jointstress/deficit/deadline/residual; pendingSOL не даёт hedgecredit. Новый риск-контракт и новый rearm — отдельная гипотеза, не скрытая часть A0 или lifecyclefix.

Определить единицы «50% при среднем риске»: денежный notional, затем объявленная волатильностная поправка/корреляционная пригодность; риск0→SOL0. Не подменять minvariance-h коэффициентом inversebeta. Не выбирать окно/порог по лучшему прошлому ROI. Для highrisk отдельно freezecap и допустимый остаток риска.

Нужен простой контроль: сокращение BTC с сопоставимым факторным риском, тем же причинным riskclock и actualexpenses. SOL должен дать недоминируемый результат относительно такого trim, а не только красивый standalonePnL. Предварительные saved-action screens диагностические; финальное сравнение только native.

R2 LEGACY_Q остаётся техническим reference для continuity/parity, поскольку это текущая ветка. Это не экономический выбор будущего winner. R3 уже проиграл; C1/E4 годятся как источники отдельных идей, не готовые real3TP/truehedge версии. Выбор минимального изменения BTC допускается по измеренному механизму; тотального rewrite нет.

Exit: записать структурный GO/NO_GO для G1, отдельный статус G2, необходимую controlmatrix и falsifiablegrowthhypothesis. Не требовать заранее доказанного будущего fill/положительной прибыли A0: именно это проверяет nativeexperiment. Если полного R2predecisionstate нет, его измеряют в первом отдельно утверждённом C0control, после чего решают допуск A0. При отсутствии законных прав или если механизм не касается dominantloss не начинать новый цикл A0-подгонки. Scalaroracle #133 не является upperbound всех будущих стратегий и не используется как tradefeature.

## P2. Подготовить проверяемую реализацию — прежняя задача2

Только после P1 и отдельного утверждения конкретного денежного scope/ownerbudget. Один sourceowner, isolatedcanonicalVPSworktree, defaultOFF, narrowindependentreview; Mac исполняет frozenкопии. Сохраняются BTCcore/initialTPprices+weights/SOLsignals/caps/A0rights в lifecyclepatch. G2, если нужен, получает отдельный change/control и не включается незаметно.

До любого nativeengine одним пакетом проверить реальный installedAPI/types/config, полный путь `/inputs/data`, stockreaders/partialmonth/UTC/fundingmark, реальные kwargs/seed/warmup, serialization/reportprecision, durableclaim, env и freshnamespace. Проверки Cache/Order/event без engine отдельно помечать engine-free; matchingtests не прятать под этим названием.

Исправлять causal TP-gap и ложный audit раздельно. Все failurecapture — доend/dispose, с orders/positions/cache/rawtyped+genericevents/actualOSrc. На причинных decisionpoints сохранять компактный predecision state (held/pending/TPstage/risk/cap/margin/действующие childrights), чтобы следующая оценка действий не пыталась восстановить отсутствующие поля из будущих fills. Один canonical ledger: phase,attemptUUID,source/config/data/engine, constructorcount, processstatus и qualificationstatus. Все native-конструкторы тестов объявлены отдельно; amendments не создают повторный счёт использованных слотов.

### Предлагаемый следующий инженерный пакет для отдельного согласования

Не авторизован этим планом. После завершения P1 уточнить exactfixtures/source/protocol и запросить одним пакетом **до6коротких nativeattempts**, включая failures и условный повтор; ≤48ч данных каждый, freshnamespace, один engine наattempt, без full/economics. Предлагаемая карта:

| Сценарий | Обязательное доказательство |
|---|---|
| E1 SOL ordinarylifecycle, defaultzero transport | Реальные partial/multiplefills, remainingTP+STOP, no cancelstorm/no unprotectedmatchingboundary |
| E2 SOL delayedcancel stress | Статический publiccancel2s, второй replacementcycle, latefill/nativeACK, correctquantities/no reversal, честный protective deadline |
| E3 BTC standing/debt | Actualpartial/fulltargets, sameOIDmodify/latestACK, safe ordinarydebt, cleanmarketableDEFER, residual/flatNOdebt |
| E4 A0 originalrights | Naturalregisteredparent/partialFIRST/onceoriginalsecond, рискOFF+60/cross/margin/pending, actualpendingcancel→fill→Canceled, noafterACKfill/retry/refund |
| E5 Registeredintegration | Одинaccount/strategy, естественныеparent, exactR2core/nativeactualqty, экономический zero-transportroute, terminalflat/orders0/inflight0/zeroLiq и5STOPPED→DISPOSED |
| E6 Условный reservedattempt | Только один заранее описанный correctedrepeat/diagnostic после одной consolidatedcorrection; не новая гипотеза/не автоматический шестой прогон |

Перед E2/E4/E5 source/API proof должен установить достижимость расписания без изменения nativecache/принудительных количеств и без ложных assertions. Если другое число/расписание требуется, исправить proposedprotocol **до** утверждения. Один резерва недостаточно для бесконечных +1; budgetexhaustion→STOP. Полный integratedgate обязателен независимо от числа componentPASS.

## P3. Сопоставимая экономика — прежняя задача3, дополненная trim-control

Только после полного P2PASS и отдельного economicGO. Предлагаемый лимит для будущего конкретного протокола: **до4 prefixattempts**, includingfailedPopen/preengine, безfull/reserve/autonext. Период `[2024-09-01,2025-01-15)` UTC, seed10000/reserve0, реальные frozeninputs+qualifiedwarmup, BASEfees/signedfunding, zero transport, одинаковый core/source/accounting:

1. OFF — freshконтроль. При только заявленных lifecyclechanges ожидается20911.13611487; необъяснённое различие блокирует остальные.
2. C0_FIXED — SOL-хедж с принятым lifecycle и компактным causalpredecisionstate. Это matched/observationalcontrol, не заранее profitablegrowthcandidate. Actualcash/funding/TPownership/coherentevent+settledDD/zeroLiq/flat обязательны. После него установить доступные R2originalrights/+60quote/cross/debt/cap/TP/margin/pending gates. Если guard/coverage fails, остальные candidateattempts не запускать.
3. BTC_TRIM — только при сопоставимом hedge-equivalentcontrol; минимальный отдельный declaredchange, а не новый sizingsearch. Он использует причинный сигнал/контракт риска, а не будущие actualSOLfills C0 онлайн.
4. A0_FIXED — тот же C0 плюс однократное originalsecondright. ActualadditionalBTCfills обязательны; иначеNOT_TESTED.

Если P1 отверг G1, A0slot не запускается/не переназначается другому алгоритму. Если невозможно freeze честный TRIMcontrol, не объявлять SOL-specificbenefit и переработать протокол до GO. Ранее предложенные OFF→C0→A0 сохранены; четвёртый кандидат добавлен именно из-за системного отсутствия подходящего cost/riskcontrol.

A0gate: TOTAL_A0>TOTAL_C0; ΔTOTAL>2×max(0,fees_A0−fees_C0); DD≤50% и≤C0; dailyES20 всех136UTCdays≤C0; полная cash/signedfunding/requiredTP/nativeownership/flat квалификация. Funding уже вTOTAL, не прибавляется снова. Existingmetricca815cbe... не ослабляется.

Для SOL сравнить C0 сriskmatchedTRIM. Если TRIM не хуже поTOTAL/DD/ES и лучше хотя бы по одному — SOLвариантдоминируем и отвергается. Если есть tradeoff, показать frontier и стоимость защиты; не выдавать positiveSOLPnL за hedgeedge.

Отдельный growthgate: сравнить раннюю капитализацию и влияние на будущий BTCsize/admission, а не только DD этогоprefix. Prefix70%отOFF — не70%двухлетнегоS0. Прежний gate2×prefixcapital также не заменяет originalprofitfloor. Прошедший engineering/accounting и даже A0incrementalbenefit ещё не разрешают full и не означают цельдостигнута.

## P4. Ограниченная оптимизация параметров — прежняя задача4

Только у механизма, который прошёл P3 и не доминируется trim. Один заранее frozenнабор основных параметров: riskactivation/deactivation, hedgefraction с волатильностной нормировкой, hysteresis/cooldown/rearmcost, при необходимости ограниченный deficitdeadline. Выбирать их по торговому механизму и диапазонам, не по датам известных losers.

Сначала fit-only причинные дешёвые проверки/coverage/minlot/cost, затем малый предварительно объявленный shortlist. Нативный бюджет каждого shortlist согласуется заранее. Не возвращаться к36-grid/подборуW/новымAIархитектурам после каждого отказа. Отдельно сравнить изменения signal, exits и quantity; не объединять всё в одного победителя.

Полная двухлетняя проверка и отдельная validation/forwardqualification — следующие самостоятельные протоколы, **full0 в текущем предложении**. Многократно просмотренная история2024–2026 не freshOOS. Финально требуются absolute70/90floors и globalsettled+coherenteventDD≤50%, ноль modelLiq и полное nativeaccounting. Реальнаяvenuequalification и любой rollout позже, вне этойзадачи.

## Приоритеты, остановки и ресурсный режим

| Системный вывод обзора | Задача | Приоритет / прекращение |
|---|---|---|
| LegacySOLalpha и капитал BTC связаны | P1b growth/corecontrol | До дорогостоящих новых запусков; noG1support→skipA0 |
| SOLTP replacement не выдержал реального sequence | P1a/P2 | Текущий технический блокер; guardнеослаблять |
| Fixedcoverage исчерпываетBTC | P1b/G2 отдельно | Не маскировать lifecyclepatch; no lawfulresidual→признатьtradeoff |
| Хедж может уступать простомуBTCcut | P3trim-control | DominatedSOL→STOPсемейства |
| 9из13FAILED предотвратимы по установленным причинам | P2preflight/capture/ledger | Один полный подготовительный пакет передengine; всеfailuresучтены |
| OldrealTP/coreeconomics низкие | P1b/P3 | Не оптимизировать толькоexecutionбесконечно; нетgrowthmechanism→NO_GO |
| AIgate не дал торговойдобавки | DEFERAI | Возвраттолькопосленовойдобавочнойинформации/достаточногоsupport |
| История многократноиспользована | P4freeze/validation | Не называтьповторOOS; не менятькритерийпослерезультата |

Исполнение: GPT6.1Sol/medium с минимальнымконтекстом поMODEL_ROUTING; один sourceowner, один узкийreviewer только на нужномэтапе; один последовательный nativeprocess. Переиспользовать данные/скрипты/подтверждённые компоненты; не строить OMS/PnLengine/SDK/service. Не пересчитывать exactS0 без необходимой comparabilityпричины и бюджета. Отчётность по решению и доказательствам, не по объёму тестов/коммитов.

## Результат начатого P1 и текущая очередь

P0 завершён до начала P1: independentreview0P0/0P1, две документальные P2 исправлены; P0_ROOT_ACCEPTANCE.json и P0_REVIEWED_PLAN_SNAPSHOT.md сохраняют исходную последовательность. P1 не включал нового engine/торгового кода.

P1a: выбран source-feasible design — сохранять remainingSOLTP OIDs, изменять необходимый STOPquantity через publicmodify, без blanket cancel после ordinaryTP. InstalledSTOP_MARKET допускает quantityupdate, но inmarkettrigger/pendingcancel/terminal и queuedACK требуют actualnativeproof. Это не nativePASS.

P1b: A0 структурно CONDITIONAL, economics покаHOLD. Он не возвращает BTCflatSOLalpha или уже закрытыйBTC. Старые R3четыре случая нельзя переносить в R2 по количеству. Точечный actualR2report показывает16riskselections/15OFF/19splitparents и отменённый secondchild в тех же четырёх датах, но общий +60predecisionstate отсутствует. `a0_rights=[]` при flagOFF не означает ноль возможностей. Точные количества .541/.405/.285/.418 и missingfields — P1_R2_COVERAGE_CHECK; это не новые fills A0.

Следующая реализация, если будет утверждена: закрыть SOL/BTCnativecontinuity и добавить side-effect-free predecisionrecord независимо от A0 tradingflag; затем получить freshOFF и честный C0control с нужными полями. Только его результат решает, использовать ли оставшиеся TRIM/A0slots. Не требуются заранее известные будущиеfill/прибыль либо counterfactualA0margin до опыта; во время опыта actualadmission проверяется на ownaccount. Отсутствие законных прав/unsafeC0/неподходящийcontrol останавливает его. G2сохраненияBTCпослевсехSOLTP — отдельный пока невыбранный riskcontract, не часть lifecyclepatch. При выборе G2 новый протокол/контроль меняются до запуска, не после результата.

Этот порядок дополнительно прошёл P1_DECISION_REVIEW: conditionalpass/blockers0, без code/nativeGO. Proposed6fixtures/4prefix остаются предложением. Первым конкретным будущим protocol должен быть lifecycle+recording scope и точная карта E1–E5/E6, а не запуск старого physical4 заново.

## Текущая авторизация

Запрос владельца разрешает полный анализ, согласование единого плана с известными выводами и последующее продвижение в разрешённых пределах. Закрытые бюджеты #131–136 не возобновлены. Этот документ предлагает будущий пакет6fixtures/4prefix/full0, но **не даёт GO на код/native**.

После P0 можно выполнять P1 как read-only анализ source/API/сохранённых данных, подготовить конкретный protocol и запросить явное числовое согласие одним пакетом. Пилот/production/services/keys/новые данные/обучение/реальные ордера/переводы исключены. Разрешение PUBLICVF78/coinmaster на researchsource/tests/reports сохраняется; pushнеdeployment.
