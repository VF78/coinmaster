# Экономические исследования 21–24 октября: компактная сверка

Задача CM-FOURWEEK-REVIEW-20261026, read-only анализ сохранённых результатов; новых engine/training/download/native replay запусков нет. Дата обзора26.10.2026. Это экономическая часть общего обзора: AI/#121/#122 и ранние семейства проверяют отдельные участники.

**Ни одного квалифицированного результата70% прибыли/50%DD или90%/50% нет.** C1 — ближайший исторический диагностический компромисс: TOTAL4388613.38225343, retention72.16970476799190164204208923%, settledDD51.80315157406654834417870238%. Он превышает70%порог на131638.315041049USDT, но DD выше50 на1.803151574п.п. E4 сохраняет92.6572934712% прибыли при DD57.5854104596%. Исправление исполнения само по себе не дало прошедшего экономического кандидата.

## Сопоставимость и смысл чисел

Везде полный период `[2024-09-01,2026-09-01)` UTC, seed10000USDT, RESERVE0, TOTAL=ACTIVE+RESERVE, если явно не помечен cheap/analysis. Profit retention=(TOTAL−10000)/(S0−10000), не отношение TOTAL.

- LegacyS0 source75ffc9c69e9d79c4da4cd0614634a3eeba48d716/config22e1eefe…: TOTAL6077107.23887483/DD66.25691486468686414439256686%. Абсолютные floors:70%=4256975.067212381;90%=5470396.514987347.
- Explicit-childS0 TOTAL6482334.93387961; matched90%floor5835101.440491649. Эти контроли отличаются admission/execution. Новый child1000 до допуска пропустил ранее отвергнутый add; первое денежное расхождение23.12.2024 16:47UTC,1000SOL@183.81/fee101.0955. Старый denied-subcomponent UNKNOWN. Новый TOTAL нельзя считать улучшением стратегии относительно старогоS0.
- Bybit BASE maker0.020%/taker0.055% по actual native liquidityside. Exact fees/funding/fills/source/config и оригинальные строки сохранены в ECONOMIC_REGISTER.json. 0.1%fixturefee не используется.
- Native cash включает фактические funding postings. Signed funding в legacy/explicit семействах UNKNOWN; unallocated cashbridge не funding. В marketR1/R2/R3 signed funding проверен черезSQLite:8649.65810383/8055.75439141/4063.32156049.
- Реальные цены Bybit, но synthetic1mCLOSE/L1depth1000 и diagnostic margin assumptions: NOT_FAITHFUL_DIAGNOSTIC. Минутная settledDD не coherent eventDD/не intraminuteDD. Повторно изученная история не fresh OOS.

## Полные native-семейства

Точные значения ниже взяты из comparison.json соответствующего семейства. Архивные повторные строкиS0/E4 опущены; register сохраняет их с происхождением. B=P0 в B50/90 иXS=P0/R1 в residual не новые независимые стратегии. R2/R2C — отдельные физические попытки, но экономически один путь.

### s0-management-20261022

Fresh DD25 crossing; trim losing leg50/75%, once; no restore.

|Recipe|TOTAL USDT|SettledDD %|Net-profit retention %|Native fees USDT|
|---|---:|---:|---:|---:|
|M1|2615745.21476479|58.77409504467889817197266501|42.94872518600868131639311323|710655.26790133|
|M2|2044863.63091774|70.64462755333227667738160314|33.53927251984940738597509242|614360.75019949|

Retention control: LEGACY_S0; exactE4/XS where specified. Физических full-attempts2; execution date2026-10-22; точныеUTC из ledger в register. Permanent cuts reduce recovery/compounding; M2 fresh-cross misses dangerous SOL and leaves weaker BTC cover. Reject fixed cuts; preserve full native evidence; no threshold grid.

Evidence: [REPORT.md](../s0-management-20261022/REPORT.md), [comparison.json](../s0-management-20261022/comparison.json), [run-budget.json](../s0-management-20261022/run-budget.json).

### sol-conditional-hedge-btc-band-20261023

Independent H4 SOL EMA13/34/89 hedge with G.5/1 and4hdeadline; BTC REGIME band.5ATR; selected combination.

|Recipe|TOTAL USDT|SettledDD %|Net-profit retention %|Native fees USDT|
|---|---:|---:|---:|---:|
|C0|306.48185220|97.53441776076043948608313353|-0.1597716632679415573276054046|136.67759173|
|H4_4H_E34_G050|437.07391017|≥96.48383203633569295829914875|-0.1576192032432821146100664172|271.18878063|
|H4_4H_E13_G050|316.84518776|≥97.09949333268982022336289428|-0.1596008514600737616164719703|424.43565716|
|H4_4H_E89_G050|447.07510136|≥96.40337455021605260945614721|-0.1574543604146286563261287805|319.36161798|
|H4_4H_E34_G100|455.91575064|≥96.33225338042525607496275649|-0.1573086460085381594852816350|312.93340608|
|H4_4H_E13_G100|483.07378823|≥95.96060656929091799869884291|-0.1568610185557714506869994543|583.33084449|
|H4_4H_E89_G100|540.33349549|≥95.65313032343266042172502489|-0.1559172457657816853453680800|409.65761278|
|BTC_REGIME_REENTRY_BAND_05|4622034.27336437|57.58541045962226379114466259|76.01702247510777033476616279|592090.31669918|
|X_H4_4H_E89_G100_B05|540.33349549|≥95.65313032343266042172502489|-0.1559172457657816853453680800|409.65761278|

Retention control: LEGACY_S0; exactE4/XS where specified. Физических full-attempts10; execution date2026-10-23; точныеUTC из ledger в register. C0/H4 early liquidation; missing SOL builds attributed only to PRE_SUBMIT_INCREASE_GATE_OR_MINIMUM (exact gate UNKNOWN); B misses winners as well as losers. B is historical filter evidence; H4/X rejected; no repeat R.

Evidence: [REPORT.md](../sol-conditional-hedge-btc-band-20261023/REPORT.md), [comparison.json](../sol-conditional-hedge-btc-band-20261023/comparison.json), [selection.json](../sol-conditional-hedge-btc-band-20261023/selection.json), [run-budget.json](../sol-conditional-hedge-btc-band-20261023/run-budget.json).

### b-50-90-next-20261023

B parity; E4 closedH4 WAIT reentry; EP daily alternative; zeroTP residual Z; dominant-SOL cut S; fixed combinations.

|Recipe|TOTAL USDT|SettledDD %|Net-profit retention %|Native fees USDT|
|---|---:|---:|---:|---:|
|S0|6077107.23887483|66.25691486468686414439256686|100|945927.73761825|
|B|4622034.27336437|57.58541045962226379114466259|76.01702247510777033476616279|592090.31669918|
|P0|4622034.27336437|57.58541045962226379114466259|76.01702247510777033476616279|592090.31669918|
|E4|5631617.35953723|57.58541045962226379114466259|92.65729347120922274896207062|706755.52937844|
|EP|3992055.58641779|57.58541045962226379114466259|65.63351247366905933081845698|615999.76639960|
|Z|2517706.78173418|60.29622291086218148072256726|41.33282440874152968490857052|438106.32694056|
|S|4155625.77863239|57.14703597783395322774634393|68.32952864372335303307712839|557093.62594034|
|XZ|4877453.55144460|60.29622291086218148072256726|80.22692462491052470340223871|684757.69258637|
|XS|5406345.11636863|58.94743688415397241603930272|88.94428438303662495658496376|691507.32515017|
|XZS|4696068.73175334|58.71953818315642454894385564|77.23728207287120124646626314|670582.02285807|

Retention control: LEGACY_S0; exactE4/XS where specified. Физических full-attempts8; execution date2026-10-23; точныеUTC из ledger в register. E4 restores participation/profit but cannot alter preexisting Oct3 DD; cuts lose recoveries and move risk to SOL-only/late BTC. Keep E4 as legacy diagnostic anchor; reject Z/S/combinations for full goal.

Evidence: [REPORT.md](../b-50-90-next-20261023/REPORT.md), [comparison.json](../b-50-90-next-20261023/comparison.json), [selection.json](../b-50-90-next-20261023/selection.json), [owner-run-budget.json](../b-50-90-next-20261023/owner-run-budget.json).

### e4-sol-residual-20261023

H1 residual-SOL guard R1; minute R2; native-flat lot-based correction R2C.

|Recipe|TOTAL USDT|SettledDD %|Net-profit retention %|Native fees USDT|
|---|---:|---:|---:|---:|
|P0|5406345.11636863|58.94743688415397241603930272|88.94428438303662495658496376|691507.32515017|
|R1|5406345.11636863|58.94743688415397241603930272|88.94428438303662495658496376|691507.32515017|
|R2|2610652.32119763|61.75868639156480895429480109|42.86478248701487717743300172|521683.64232669|
|R2C|2610652.32119763|61.75868639156480895429480109|42.86478248701487717743300172|521683.64232669|

Retention control: LEGACY_S0; exactE4/XS where specified. Физических full-attempts4; execution date2026-10-23; точныеUTC из ledger в register. R1 blocked by float dust; R2/R2C trim saves Oct/Jan tails but later smaller capital yields Jul-Aug61.7587%DD. Corrected H1 NOT_RUN; R2C correction not economic lift; no reopen.

Evidence: [REPORT.md](../e4-sol-residual-20261023/REPORT.md), [comparison.json](../e4-sol-residual-20261023/comparison.json), [selection.json](../e4-sol-residual-20261023/selection.json), [owner-run-budget.json](../e4-sol-residual-20261023/owner-run-budget.json).

### e4-budget-tp3-20261023

SOL stress budget+one trim/no auto restore; separate20%initialBTC early positiveTP3 tranche at1%.

|Recipe|TOTAL USDT|SettledDD %|Net-profit retention %|Native fees USDT|
|---|---:|---:|---:|---:|
|SOL|1360086.36695243|66.85904748908962764036494870|22.25255486340816800127320123|325966.74779559|
|BTC_CORRECTED|4120806.47444031|61.07965831810633248928463321|67.75562574698574100393451199|648028.54314295|

Retention control: LEGACY_S0; exactE4/XS where specified. Физических full-attempts3; execution date2026-10-23; точныеUTC из ledger в register. Budget reduces SOL alpha/early capital; earlyTP harvest loses trend exposure. Savings in fees cannot compensate. COMBINED and fresh repeat NOT_RUN; reject.

Evidence: [REPORT.md](../e4-budget-tp3-20261023/REPORT.md), [comparison.json](../e4-budget-tp3-20261023/comparison.json), [selection.json](../e4-budget-tp3-20261023/selection.json), [owner-run-budget.json](../e4-budget-tp3-20261023/owner-run-budget.json).

### residual-recovery-20261023

C1 DD40/cushion50 losing-leg half cut; actual-fill rights; one restore closedH4/price beyond cutVWAP/DD35.

|Recipe|TOTAL USDT|SettledDD %|Net-profit retention %|Native fees USDT|
|---|---:|---:|---:|---:|
|C1|4388613.38225343|51.80315157406654834417870238|72.16970476799190164204208923|671063.37411189|

Retention control: LEGACY_S0; exactE4/XS where specified. Физических full-attempts2; execution date2026-10-23; точныеUTC из ledger в register. Restore cash cost385696.0245 before fees +30498.04072762 intervention fees; Jan2000requested/1000filled; episode rearm enables5Augcuts. Historical near-Pareto only; do not blindly rerun C1 under current true3TP/hedge objective. C2 stopped.

Evidence: [REPORT.md](../residual-recovery-20261023/REPORT.md), [comparison.json](../residual-recovery-20261023/comparison.json), [selection.json](../residual-recovery-20261023/selection.json), [root-launch-budget.json](../residual-recovery-20261023/root-launch-budget.json).

### system-contract-repair-20261023

ExplicitSOLchild1000; matchedS0/E4; H_SOL ADD-only55%H/ATR14; H_BTC repeatwaveQ90.

|Recipe|TOTAL USDT|SettledDD %|Net-profit retention %|Native fees USDT|
|---|---:|---:|---:|---:|
|S0_EXPLICIT_CONTROL|6482334.93387961|66.25691486468686414439256686|100|981911.41179846|
|E4_EXPLICIT_CONTROL|6022427.55763206|57.58541045962226379114466259|92.89425870345255834767166787|732226.13451913|
|H_SOL|3964359.61000698|65.69477083251083711659723613|61.09633772671094405061558740|608681.20137623|
|H_BTC|5352125.97225949|57.58541045962226379114466259|82.53784803836385200354321221|661862.02516131|

Retention control: EXPLICIT_CHILD_S0+E4. Физических full-attempts4; execution date2026-10-23; точныеUTC из ledger в register. Explicit child admits formerly denied add; changed control. H_SOL smaller Jan capital worsens relative DD; H_BTC first actsMay25 too late for early tails. COMBINED NOT_RUN by actual prefix futility; no inferredTOTAL; controls remain distinct.

Evidence: [REPORT.md](../system-contract-repair-20261023/REPORT.md), [comparison.json](../system-contract-repair-20261023/comparison.json), [selection.json](../system-contract-repair-20261023/selection.json), [run-ledger.json](../system-contract-repair-20261023/run-ledger.json).

### market-redesign-20261024

R1 legacyE4BTC SOLoff; R2 realU3TP/.5%limitonly LEGACY_Q; R3 same CLEAN_Q.

|Recipe|TOTAL USDT|SettledDD %|Net-profit retention %|Native fees USDT|
|---|---:|---:|---:|---:|
|R1|304372.03028516|66.9203964274313113040274377061695299005253528651376464456666|4.85193385735757168160472781242468883617522592822988883869909|71190.77151865|
|R2|225919.51131228|66.8014965825988940501356298120806585229481015518869629205355|3.55885437344475160049566408493707560680082018139901526505814|42681.92477909|
|R3|120718.40416503|68.6033754263482863768423778493842458647999693621015333671923|1.82489611285597093868117498794629805508226622060448588402363|25265.15689546|

Retention control: LEGACY_S0; exactE4/XS where specified. Физических full-attempts3; execution date2026-10-24; точныеUTC из ledger в register. Removing selectiveSOL removes early capital; actual3TP/limit execution fails profit and DD; CLEAN_Q lowers terminal capital further. No fullSOL admission; R3 is clean NONPASSING; retain realTP implementation evidence.

Evidence: [REPORT.md](../market-redesign-20261024/REPORT.md), [comparison.json](../market-redesign-20261024/comparison.json), [run-ledger.json](../market-redesign-20261024/run-ledger.json).

## C1: почему не текущий победитель и не готовая замена A0

C1 опирается на legacyE4 с selectivezeroTP, profitablepositiveTP IOCfallback и исходнымSOLalpha, который может жить при BTCflat. Историческое native/accountPASS доказывает принятую денежную траекторию, а не настоящий hedge или непрерывное наличие трёх реальных TP. **Continuous realTP1/TP2/TP3 и coherent eventDD дляC1 UNKNOWN/NOT_ATTESTED**. Уже settledDD51.803% исключает приёмку. Нельзя обещать тот же72.17%результат после замены его core/SOL/TPcontract.

9cut/3restore/6extinguishedrights. Реальные парные cashflow restore:385696.0245USDT до fees, плюс30498.04072762USDT комиссии12вмешательств; они уже включены в total671063.37411189, не добавлять повторно. Это не точная причинная атрибуция всего отставания. Январь: requested2000SOL, native IOCfilled1000, реально25%позиции. Август: пятьcuts на разных родителях при одном продолжающемся DD; без общегоrearm нельзя контролировать cumulativeportfolioDD. C2NOT_RUN/stopfamily: изменение3параметров не доказало недостающий капитал, а первыйOctcut всё ещё даёт50.6142%.

**Приоритет — контрактное причинное доказательство на сохранённых решениях**, если такой этап отдельно разрешён: actual3TPrights, исполненная hedgecoverage/deficit, действие на оставшийсяBTC/SOLrisk, стоимость ограничения/восстановления капитала и непрерывныйportfolioHWM. НазваниеC1/A0 не заменяет эти gates. C1 полезен как отрицательное свидетельство ценыrestore/partialexecution/rearm; A0 также не получает допуска из этой исторической экономики. Ни blindC1rerun, ни продолжениеA0 автоматически не следует.

C1 correctedattempt имеет wrapperexit1 от macOSsysctl, nativechild exactexitUNKNOWN, acceptedsealedCOMPLETEDexports и44accounting/933mechanism checks. ПервоначальнаяDecimalexportfailure сохранена и не считается валидной экономикой. Нельзя писать«обаexit0».

## Что установлено отдельными окнами и почему это не глобальная победа

- ЧистыйE4:Oct3DD57.5854%;Jan13DD51.4147%;Oct22→Nov28DD54.7928%. Jul6→Aug19,2026DD46.3347% уже ниже50. Нельзя заменять E4Jan51.4147% локальным rebased42.5023% из другой таблицы/явнымcontrol или global-continuousизмерением без обозначения.
- R2C:Oct49.9363%/Jan49.4068%, но глобальнаяDD61.75868639% уже Jul6→Aug19,2026. Все337BTCfills calendar/price/reason/liquidity совпадают сXS,292quantities и SOLopportunities изменены капиталом. Исправление nativeBTCflat dust дало ровно нулевую экономическую дельтуR2→R2C; correctedH1 NOT_RUN.
- SOLbudget:Oct50.1322/Jan44.5333%, но global66.8590% Jul–Aug2026. Все337BTCfills samecalendar,320quantities изменены. Это не пропавшиеBTCsignals.
- EarlyTP3:Nov43.8691%, ноOct61.0797/Jan54.2320%. 68earlyfills (66maker/2taker), не всеmaker.
- C1:Oct50.6142/Jan51.8032/Oct–Dec2025 47.2731%. Ноябрь улучшен, но restore особенно дорог; январская partialcapacity и августовский rearm остаются.
- H_SOL explicit:Oct18.7753%, Jan65.6948%. Меньший абсолютный убыток при меньшем капитале хуже в процентах. H_BTC19/33repeatparents уменьшены, firstk<1только25.05.2025; все19actual decisions черезJan13 k1. Поэтому combined provably сохраняет раннююDD65.6948%, NOT_RUN, TOTALне выдуман.
- MarketR1/R2/R3 globalDD—all Jul6→Aug19,2026. Equal-notional/netbpR2≈93.837 противR1≈79.570 не переводится в portfolioTOTAL: owncapital/admission/compounding различны. СтарыйBTCassetfillnet не BTC-aloneROI.

## Отрицательное evidence, неисполненное и counting

Восемь fullnativeсемейств дают36физических fullattempts по собственным ledgers:2+10+8+4+3+2+4+3. Это **не36уникальных стратегий** и не весь четырёхнедельный итог: включены P0/control/repeat, correction и невалидныеexportattempts. ConditionalH4 содержит P0+8core+X; единственныйB затем подтверждён новымP0. Residual содержит P0/R1/R2/R2C; R1 не тест исправленнойH1защиты. Budget3attempts→2валидных рецепта/1invalidexport. C1 2attempts→1acceptedfinancialresult/1invalidexport. Explicit4controls/candidates; market3full и отдельно8shortengineering, не8дополнительныхэкономическихfull.

Неисполненное сохраняет причину: B50/90 conditionalgatefail; residualcorrectedH1 слот занятR2C; budgetCOMBINED/repeatgatefail; C2stopfamily; conditionalR no passingcandidate; explicitCOMBINEDactualprefixfutility/freshrepeatnoPASS; marketfullSOL noadmission. Неиспользованные слоты закрыты и не разрешают запуск. FULL_GRID и laterprefixworkOct25 не относятся к этому полному Oct21–24nativeнабору.

H4/XDD имеет28/32missingreceipts около actualfundingcashmutations: это observedlowerbound, уже>95%, не точная полнаяDD и не основаниеPASS. C0/B complete1051199receipts. MacP0economicparity принят, strictfullartifactrepeatFAIL (libmULPbeta/H) сохранён. В остальных acceptedновыхfullполный1051199settledcoverage/terminalflat/zeroLiq, кроме liquidatedconditionalfamily; precise rows/report qualifiers вregister.

## Аналитические семейства: не считать повторно как новые nativeстратегии

- [btc-sol-causal-modules-20261022](../btc-sol-causal-modules-20261022/REPORT.md): H1 secondBTC on+.25%:49/105adds, equalunitprimary.245942% vsS0.376810%; H2 CUSUM no alarm earlySOL1;4/26alarms; H3 TP2giveback10signals/28activations, primary−.302990% all opportunities. H1/H2/H3 rejected, no counterfactualTOTAL/DD. H4 proposed, later native family separately registered.
- [s0-weekly-postmortem-20261022](../s0-weekly-postmortem-20261022/REPORT.md): 78inventoryrows;21 completed economics physical includes19recipes plus repeats,2wrongimplementation excluded; dates15–17 unconfirmed. M1 early46.59%DD migrates late58.77%; M2 freshcross/cover imbalance. NativefillnetBTC is not standaloneBTCROI.
- [btc-lifecycle-audit-20261022](../btc-lifecycle-audit-20261022/REPORT.md): 105BTC lifecycle; TPquantiles/zeroTP/PLANREF and profitablefallback remain distinct. More frequent intradaytrail not proven improvement. New TP/SL candidate NOT_RUN.
- [b-band-postmortem-20261023](../b-band-postmortem-20261023/REPORT.md): B includes28losers and22winners skipped insideWAIT;4additionalwinner dates lost via occupancy/calendar; no causal sum of removedfills. MixedSOL, BTCsqueeze and realizedwhipsaws need distinct mechanism.
- [e4-postmortem-20261023](../e4-postmortem-20261023/REPORT.md): E4 firstdiffOct6 cannot affectOct3 maxDD. Three>50 excursions:Oct57.5854,Jan51.4147,Nov54.7928; Jul-Aug46.3347 already passes. Tiny161220.84455 capitalheadroom above90floor not a riskbudget.
- [s0-system-audit-20261023](../s0-system-audit-20261023/REPORT.md): 72sourcepins/15comparablepaths/11sources/twoactual2x2 interactions; no newnative. SOL is selectivealpha and tied to grossBTCreference/rights, not currentcoverage. No proof50/90 attainable underfixedcore.

Market supplementalcheap: actualR3SOLscreen1529H4states/77BTCcycles, три50%sizeварианта отрицательныпоmeanNETвобоихгодах; tailprotectionположительна, но слабееequalfactorBTCtrim иcostadvantageнеустойчиво:STOP_SOL/INCONCLUSIVE, nofullSOL. Fixedcounter-swingpendingsecondgate5/83parents/4laterfilledlegs, ихfrozenobservedfillnetexfunding+1160.23; затронут1из11globalDDparents. Это неcounterfactualTOTAL/DD, следующийfull/P+feefloorNOT_ADMITTED. [MarketREPORT](../market-redesign-20261024/REPORT.md).

## Ограничения покрытия

Сверены индекс/каталог, compactreports/comparison/selection/ledgers и указанныеpostmortems; это не повтор полного rawtrace/accountaudit. Источники pinnedsha256 вregister; все exactvariantrowполезныеmoneyvalues сохранены. Reportfolderdate обозначает семейство, executiondate установлен поsavedledgerUTC; например legacyS0 исполнен до этого окна и здесь переиспользован. Историческая дата отчёта не создаёт новуюpermission/runtimeистину.

Для полногоprojectcounts нужны отдельные AI/earlyregisters и inventoryroot. CoherenteventDD, venueL2/capacity, liveROI и crashresume не доказаны. Современнуюgenuine3TPqualification имеют только marketR2/R3 (оба сильнонепроходящие); truehedge при этом не доказан. Signedfunding старыхсемейств UNKNOWN. Нет causal$attribution будущего капитала через удалениеfill; нет futureknowingwinnerfilters; нет freshOOSclaim.
