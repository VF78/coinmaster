# Предложение следующего ограниченного этапа после обзора

**PROPOSED / НЕ УТВЕРЖДЕНО. Нового code/native GO нет.** Основание — REVIEW_RU, актуальный UNIFIED_PLAN_RU после P1, independent INTEGRATION_REVIEW/P1_DECISION_REVIEW. Все прежние бюджеты закрыты; это отдельный новый пакет, а не перенос последних unusedslots.

## Цель и изменения

Изолированный defaultOFF researchpatch от committedsource7f38278257624b321c9d88d9df962505b6f5bab0:

1. Минимальный SOL lifecycle: сохранять remainingTP OIDs/entitlements, менять необходимый quantity STOP через stockpublicmodify; убрать blanket cancel после ordinaryTP. Очередь/publicreturn/actualACK/reject/latefill/terminal учесть явно. Не менять BTCcore/входы/LEGACY_Q, initialBTC/SOLTPprices+weights, SOLrisk signals, lotcorridor/caps, A0originalrights или их clocks. Если нужен иной денежный scope — STOP до отдельного решения.
2. Добавить side-effect-free predecisionrecord независимо от A0tradingflag: originalsecond/rightremaining/actualfilled, riskOFF+60/quote/cross, held/pending/debt/caps/remainingTP, текущий native margin/reservation и принятие/отказ. Ничего не приписывать будущим fills; отсутствие наблюдения не превращать в zeroopportunities.
3. Для экономического сравнения отдельно объявленный native BTC_TRIMcontrol: тот же причинный riskclock и сопоставимый ex-ante факторный риск, без использования будущих C0SOLfills/без виртуального PnLдвижка. Точная формула/сопоставимость freeze и узкий review до экономическогоGO; если не обоснована — STOP передcontrol, не создавать новый sizingsearch.

G2новый residualrisk/rearm/deficit-contract, изменениеSOLsignals, новая alpha приBTCflat, модели, ETH/новыеassets, новые данные/обучение в пакет не входят. Результат correctnesspatch не называется доказанным восстановлением прибыли.

## Предлагаемые числовые пределы

**Engineering: до6физических nativeattempts, каждый≤48ч обработанных fixtureданных.** Пять обязательных сценариев E1–E5 из P1_SOL_LIFECYCLE_CONTRACT/UNIFIED_PLAN; шестой — один условный repeat после одной consolidatedcorrection. Все failures входят. Любой дополнительный BacktestEngineconstructor/matchingtest также расходует этот бюджет; не запускать скрытую nativeunit-suite. Object-level Cache/Order/event проверки без engine учитываются отдельно как engine-free.

Статический transport freeze до каждого constructor: defaultzero для обычного/economicroute; отдельные stressfixtures base/insert/update0/cancel2s. Никакого измененияlatency/venue/model внутри engine. Для naturalregisteredparent при необходимости: actualdata≤48ч; отдельный предыдущийconfigdayguard допустим и фиксируется явно (как25ч10data/49ч10config), без дополнительного streamedhistory/reset/ручныхpositions/forcedquantities.

До native: exactpublicAPI/source/state/loader/UTCpartialmonth/funding/reportserialization/ownership/env/freshnamespace checks; meaningfulpuretests; один sourceowner в canonicalVPSisolatedworktree, независимый money/order review, immutableMacfreeze/source-config-data-nativepins и rootGO. Actualcache/failurecapture доcleanup. Необходимы реальные ACK, complete remainingTP, cleanhealthyDEFER, terminalflat/orders0/inflight0/zeroLiq;5STOPPED→DISPOSED дополнительно, а не вместоflat. Непокрытыйessentialcase→STOP/noeconomics. Никакого автоматического +1.

**Экономика: только после полного engineeringPASS, до4prefixattempts**, включая failedPopen/preengine, без резерва/autonext; каждый отдельно rootGO:

1. OFF — freshsame-sourceконтроль. ExpectedTOTAL20911.13611487 при заявленномscope; unexplaineddifference→STOP.
2. C0_FIXED — строгийnativefinancial/TP/controlPASS плюс causalpredecisionrecord. Это observationalmatchedcontrol; он не получает заранее growthPASS. Он определяет actualR2coverage и пригодность дальнейшихcontrols.
3. BTC_TRIM — только после validC0 и frozencomparablecausalriskcontract. При невозможности корректного сравнения STOP, не использовать C0futurefills онлайн.
4. A0_FIXED — только при законныхoriginalrights/guards и validC0/controlmatrix; тот жеC0 плюс один originalsecond retry. Futurefill/прибыль заранее не требуются; actualadmission наownaccount. Если rightsнет/нетmeaningfulcoverage — NOT_ADMITTED/NOT_TESTED; неиспользованныйslot закрывается, не переназначается.

Окно `[2024-09-01,2025-01-15)` UTC, seed10000/RESERVE0; frozenBybitinputs `/inputs/data` и qualifiedSOLwarmupfeed5a02a0bc..., прежние BASEfees/funding, native1.231.0/zero transport, freshaccount/journal/source/config hashes. Stockreaderpreflight обязателен; фактический OSrc сохраняется без time-lwrapper в качестве authority.

Приёмка: actualnative cash/signedfunding, settled+coherenteventDD, fullremainingTP/ownership, zeroLiq, terminalflat/orders0; A0additionalBTCfills обязательны, TOTAL_A0>TOTAL_C0, ΔTOTAL>2max(0,fees_A0−fees_C0), DD≤50% и≤C0, dailyES20≤C0 по всем136UTCdays. C0/TRIM Pareto/cost сравнение не подменяет absoluteoriginal70/90цель; prefix неfull/OOS. Если TRIM доминируетSOL поTOTAL/DD/ES, SOLвариант отвергается. UnsafeC0/failedadmission→STOP оставшихсяslots.

## Границы

Full/training/downloads/pilot/production/deploy/services/credentials/реальныеордера/переводы: **0**. Сохранить dirtyusercode/старыеdrafts/всеfailedsources/results. PUBLICVF78/coinmasterpublicationresearchsource/tests/reports уже разрешена; pushнеdeployment. Параметрическая оптимизация/полныепрогоны потребуют следующего самостоятельного supportedprotocol; их бюджетздесь0.

Для начала этого пакета требуется прямое согласие владельца именно на этот scope и новые пределы **6engineering /4prefix /full0**. До согласия выполнены только обзор, план и P1read-onlyanalysis. Даже согласие наmax4prefix не отменяет условные gates и не требует потратить все4.
