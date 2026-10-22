# BTC lifecycle: что переносится на точный S0

**Измеренно помогли управление reference и завершение native TP, а не ужесточение stop/confirmation или blanket fee floor. Ни одна проверенная BTC risk-адаптация не прошла одновременно DD≤50% и сохранение 90% net profit.** Нового допущенного кандидата пока нет.

Контроль: TOTAL **6,077,107.23887483**, seed 10,000, reserve 0; agreed settled DD **66.2569148647%**; требуемый TOTAL≥**5,470,396.514987347**. Source S0 `75ffc9c69e9d79c4da4cd0614634a3eeba48d716`, scientific freeze `c1d0c69`; исходный выбранный вариант `759823d69a74e72b123add5ae775dd8c3aed4ac5`. Повторять S0 не требуется. [Weekly inventory](../s0-weekly-postmortem-20261022/weekly-inventory.json) переиспользован; source pins и SHA прочитанных файлов — в соседнем JSON.

## Матрица доказательств

DD ниже — портфельная, **не MAE после входа**. `UNKNOWN` — данных нет. Старые базы не считаются чистыми интервенциями точного S0.

|Исследование / база|Вход / исполнение|TP/SL и риск после входа|TOTAL / fees USDT; вывод|
|---|---|---|---|
|Fee floor V1, 29 сентября, вне недели; V0|Изолированное улучшение entry price UNKNOWN|82 fee-negative TP→0, но TP fills233→248, SOL adds114→116; marked DD UNKNOWN|3,386,491.65→2,661,216.57; fees621,073.73→586,047.08. Меньше fees, меньше TOTAL на725,275.08. [Данные](../tp-fee-floor-113/comparison.json)|
|Selective zero TP,9 октября, вне недели; technicalcontrol|105 entries;45 reduced/passive,60 full/fallback; delay60s|76 zero allocations omitted; rights earned only afterfill+reference touch; positive reductions82→82. Cash DD58.15→62.47, marked UNKNOWN|3,553,011.16→3,747,041.97; fees621,166.21→597,517.54. Уже входит в lineageS0. [Отчёт](../selective-zero-tp-113/README.md)|
|Split0.25/0.50,18 октября; V3|Blended management reference;104 calendars вместо105|DD77.94/77.65%; entryMAE UNKNOWN; TP/TRAIL/rights path сдвинут|4,759,384.60 /4,379,050.17; ниже V35,437,208.57. Нельзя оставить только приятную entryprice. [Таблица](../btc-split-sol-cover-20261018/comparison-analysis-native-table.csv)|
|PLANREF,18 октября; V3|105/105 P0/time/q0/q1 совпали; mean entryprice+3.41749bp, fullcost+4.51781bp; minprice−77.35625bp|P0 фиксирован, H от actualVWAP; DD70.47%; пропуск уже пройденных marketableTP после earlycompletion|6,005,487.81; fees960,263.21. Улучшенный вход сам по себе не снизил DD. [Сводка](../btc-split-sol-cover-20261018/comparison-analysis-btc025-planref-summary.json)|
|PLANREF+TPIOC=S0,18/20 октября|Mean entryprice+3.41746bp/fullcost+4.51778bp;105plans; completion66limit/17deadline/22earlyTP|13 realMARKET/IOC/TAKER catchups; Apr–JunDD70.47→59.84; globalcallback66.32, settled66.26|6,077,107.24; fees945,927.74; +71,619.43 vsPLANREF.7/13catchups negative afterallocatedfees, combined−1,817.86, но wholeportfolio лучше. [Сводка](../btc-split-sol-cover-20261018/comparison-analysis-btc025-planref-tp-ioc-summary.json)|
|H1,13 октябряUTC, вне недели; V3|Меняет SOL lifecycle, не BTCconfirmation|31stage1hedges,0stage2; DD62.60%; исходныйSOL заменён|190,593.97; fees65,995.57; −96.49%TOTAL. Не BTCentry доказательство. [Отчёт](../h1-b1-113/comparison/README.md)|
|B1,13 октябряUTC, вне недели; V3|104arms/entries; median dailyarm→fill47min (17–287); confirmation→fill120s; entryprice benefitUNKNOWN|DD64.64%; calendar/rights/exposure менялись; normalizedMAE UNKNOWN|1,387,384.72; fees511,337.13; −74.48%TOTAL. Confirmation не бесплатно. [Отчёт](../h1-b1-113/comparison/README.md)|
|R2/T3,11 октября, вне недели; V3|R2 требует2daily EMA closes; T3 сохраняет entry|R2DD92.13; T3minute evaluation daily-armed3%trail закрывает обеlegs, DD92.78|2,248,382.68 /466,727.72; fees530,522.98 /605,085.68. Не повторять как новые ideas. [Параметры](../selective-lifecycle-cap30m-113/v3-drawdown-causes/parameter-review.md)|
|M1/M2,22 октября; exactS0|BTC_ENTRY210 fillrecords сохраняются; абсолютные Q компаундятся|FreshDDcross25 + ownnegativeUPnL; half/.75IOC; DD58.77/70.64;22full+4/3partialcancel targets|2,615,745.21 /2,044,863.63; fees710,655.27 /614,360.75. ОбаFAIL, noTPcredit, STOP2/4. [Freeze](../s0-management-20261022/policy-freeze.json)|
|ADVERSE50,19 октября; savedcontexts|Не эксперимент entryprice; fixed1.9175212144% adverse,halfcut|15crosses/partition,7positive8negative endpoint effects; optimisticpricebound−2.504182%/−1.069702% beforecost|TOTAL/DD/fees NOT_EVALUATED. Goodloserclassification не goodstop. [Отчёт](../chop-pair-113/stats-adverse-payoff-bound.md)|
|AI entry/TP/SL,20–22 октября; forecastcontrols|Никаких доказанных улучшенных nativeentryfills|FASTprior лучше всех; H24CNN actionable0; pattern/FORM/E1/D90 gateFAIL; AstraTP≈numericD1, pairedCI включают0|Экономика NOT_EVALUATED. TPpinball/SLBrier не jointcostedpolicy и не DD. [Pattern](../btc-pattern-pilot-m2-20261021/findings.md), [H24](../forecast-independent-20261021/findings.md)|

## Почему fewer fees может ухудшить ROI

Комиссия зависит от размера и траектории, а не только числа заявок. Fee floor меняет время/цену TP, остаток BTC, заработанные SOL rights и будущий капитал. V1 вообще не сократил число BTC TP fills:233→248. Selective сохранил полезные positive targets/fallbacks и заработал больше, однако его cash DD выросла. В S0 реальный TAKER catchup с локальным net loss может раньше убрать риск и сохранить следующий капитал. Удалять7 отрицательных catchups постфактум запрещено; это другой путь, не экономия−1,817.86.

Слияние двух ad-valorem reductions само по себе fees не экономит.73 gross-positive zero fallbacks у selective не равны73 net-positive;6/24 plannedTP2 были negative послеallocatedfees (combined−774.71), но blanketfloor уже провалился. Правильная единица — весь причинный lifecycle BTC+SOL+capital, не локальная комиссия. [Selective audit](../selective-zero-tp-113/audit/README.md).

Активные TP fractions **0.2125/0.2125/0.575**, quantiles **.10/.30/.60**, history730d/min8; fixedpriceSL отсутствует. Есть daily3%profittrail, arm толькоbest_f>.03, REGIME/group и mandatory exits. Поэтому «3TP+SL» с новым постояннымSL — новое economicrule, а не включение выключенного защитного параметра. Intraday trail T3 уже проверен на V3; отдельный завершённый пакет с названием intradaylimits/tpmanagement в просмотренных reports не установлен. Unrun15mconfirmation/runawayguard не выдаются за результат.

## Что ещё неизвестно

All-opportunity exactS0 **MAE before TP**, MFE и ATR-normalized adverse distribution в прочитанных compactreports не экспортированы. PortfolioDD, entrycostbp и fixedprice adverse threshold не заменяют эти величины. Существующий BTC-only DD55.10% не устраняется одним SOL veto. Между entryfilter, postentrycut и jointTP/SL нельзя переносить measuredEV без проверки доступных причинных состояний и восстановления полезных winners.

## Ограниченный следующий поиск — только после отдельного решения

1. **Precheck1: один saved-data census всех возможностей.** Все105 исходных BTCparents, включая noTP/partial/forced/censored; dailyarm→q0/q1→firstfill→completion→TP1/2/3/REGIME/TRAIL, actualfee/Q/P0/VWAP и earned/consumedSOLrights. ATR фиксируется по доступным до решения completedbars. Outcomes: side-normalized MAEbefore каждого первого actualTP, MFE/ATR, время, recoveredwinners; same-minute TP/SL порядок — ambiguous. Нет нужных states — UNKNOWN/STOP, без simulatedfills.
2. **Precheck2: один заранее фиксированный joint вопрос TP+SL.** Не сетка thresholds и не новый recognizer. Условно на причинное состояние оценить вместе targetdistance/stopdistance/horizon/remainingQ и цену потерянных profitablefallbacks/SOLrights; сравнить сTRAINprior/no-action. MarginalTPpinball и marginalSLBrier не дают jointEV. Нельзя выбирать rule по удалению будущих losers, одному hitrate или fees. Нет механизма против BTC-only tail без уничтожения recoveredwinners — reject. Numericthreshold и ожидаемые TOTAL/DD сейчас UNKNOWN.
3. **Gate3: freeze и owner consent.** Только при содержательном PASS выбрать ONE BTC lifecycle adaptation, сохранить exactS0 entry/sizing/originalSOL, input13pins/fees/funding/margin и agreedsettledobserver. **≤2 fullnative всего:** один кандидат; только если DD≤50 и TOTAL≥5,470,396.514987347 — один freshidenticalrepeat. Никакого controlrerun, второй intensity/grid/autoretry. Каждый запуск требует явного разрешения owner. Сейчас запусков нет.

Нативная историческая квалификация остаётся NOT_FAITHFUL_DIAGNOSTIC: minuteclose proxy, неизвестные historicalL2/slippage/tiers и signedfunding. MAE по OHLC не устанавливает intrabar ordering или venue stopguarantee. Текущий документ не меняет source/model/pilot/services/Project/git.
