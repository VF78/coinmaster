# Финансовые gates нового SOL-standing пакета

**READ_ONLY_PREPARATION / НЕ GO.** Прямое approval6b8625d8… утверждает max6fixtures и условные4prefix/full0 по immutableprotocolfaa39247…. По dispatchroot новыхпопыток0; актуальные counts ведёт solewriterledger, этот reader их не изменяет. Для каждогоengine нужен отдельныйrootGO; до экономики обязателен полный engineeringgate.

## Замороженная денежная база

MetriccontractSHA **ca815cbe3b8e163b16ccca8e388c9299125f74f0e1dd10beaa3ee15e4fe31102** остаётся неизменным. Старыйschema b02b624a… иreader жёстко привязаны кsource763d985/labelsR2_OFF,C0,A0/layout. Новаяsource/TRIM/четырёхшаговаяadmissionmatrix требуют reviewedinterface-onlyrebind доfreeze; изменять metric/formulas/tolerances/gates нельзя.

Старый acceptedOFF source763d985, UUID77b7a5cc-0e2a-43a3-a17e-56868728a7d5, reportSHAfe124522…:

|Показатель|Exactsavedvalue|
|---|---:|
|terminal_total|20911.13611487|
|settled_DD_percent|50.13014281400943598272557789|
|event_DD_percent|50.13014281400943598272557789|
|fees|1072.65091609|
|signed_funding|-695.36036902|
|daily_ES20_percent|5.8899433101068996401033491697380331305483706876438|
|parent_ES20_percent|18.796333957720837909854362565708995361672402054073|
|daily_count|136|
|parent_count|19|
|native_fills|82|
|settled_receipts|195839|

Все82fills:56maker/fees313.14678188 и26taker/fees759.50413421. SignedfundingBTC−695.36036902; наличие/отсутствиеSOLpostings проверяется actualjournal, не подставленнымнулём. Старый OFF financiallyqualified, но DD50FAIL — baseline, не winner. Старыйreceipt не заменяет freshOFF/newphaseadmission. При неизменной OFFэкономике ожидается TOTAL20911.13611487; необъяснённаяразница STOP, не расширениеtolerance.

Сопоставимость: `[2024-09-01,2025-01-15)`UTC, seed10000/RESERVE0; exactR2LEGACY_Q realU3TP/configd9ea9c51…, qualifiedwarmupfeed5a02a0bc…, stockactual`/inputs/data`, Nautilus1.231.0, BASEBybitmaker0.020%/taker0.055%, zeroeconomictransport. Новуюsource/config/kwargs/input/accountclock нужно закрепить доисходов. G2/core/signal/TPweight/rearm изменения исключены.

## Условный порядок и разделение допуска

1. FreshOFF: no priornewreceipt; parity/strictfinancialPASS.
2. C0_FIXED: pinnewOFFfinancialreceipt; strictnativeTP/financialPASS+causalpredecisionrecords. Это observationalmatchedcontrol, не growthPASS. InvalidC0/нетadmissibleright→STOPunusedslots.
3. BTC_TRIM: validOFF+C0, отдельно frozen/reviewed exantecausalriskclock+factor-risk target и ownnativefill/costsemantics.
4. A0_FIXED: validcontrolmatrix; actualoriginalunfilledrights и runtimeguards на ownaccount. Будущиеfill/margin/profit не доказываются заранее. Нетpositiveactualreleasefill→ECONOMICALLY_NOT_TESTED; differingTOTALwithoutfills unexplained, не freebenefit.

В новомbinder зафиксировать точные priorlabelsets включаяTRIM, безextras/duplicates. Rootqualificationreceipt должен подтверждать riskVALID_ACCOUNTED_PREFIX/allfinancialgatesPASS, фактическийOSrc0 и immutableдоказательства. Acceptedcontrol может иметь плохуюperformance; accounting-failedreport не acceptedTOTAL. СтарыйC0 отвергнут за540s реальнойTPдыры; егоcash не priorfinancialPASS.

## UUID/receipt/artifact binding

Выбирать ровно один actualUUID+COMPLETED+reportSHA, не последнююстрокупоlabel. Report/supervisor/completion/source/freeze/namespace/currententry согласованы. Сохранить immutablecompletedentrysnapshot; canonicalentrySHA=SHA256 UTF8 `json.dumps(entry,sort_keys=True,separators=(',',':'),ensure_ascii=False)`. При последующихappend wholeledgerSHA меняется законно: он diagnostic, проверяется неизменность конкретной entry и snapshot, не wholemutableledger.

Четыре обязательных financialroles: actualreportJSON, siblingordersCSV, fundingSQLite, coherent-native-events.jsonl.gz; absoluteactualpaths+SHA вcompletionmanifest. Rootrisk/evidence/financialreceipt и дополнительный predecision/rights/margin/ownershipproof тоже pinned. Дополнительные proofs не заменяютfourroles; exactновыйproducerJSONpath объявить доfreeze. ActualOSrc supervisor обязателен, nativeCOMPLETEDalone недостаточен.

## Метрики и обязательные проверки

- Nativeequity=cash+PositionUPNL на каждомcoherentreceipt; полныйnativecash/fills/liquidityside/feesbridge, externalflows0. Signedfunding каждогоevent/asset: pre/postnativecash ↔ read-onlyimmutableSQLite `funding_cash(event_id,instrument_id,ts_event,before_total,after_total,signed_delta)` ↔ report amount/count. Не называтьcashbridgefunding и не исправлятьUNKNOWNнулём.
- 195840sourceminutes/195839continuoussettledreceipts; sequence/epoch/watermark/retainedsourcecomplete. Раздельные settled иeventHWM сseed/terminal, coherentpre-fill/pre-openhistoricalpeaks; actualpairedPRE_FILL/POST_FILLnativeIDs. Cash-only/daily/closedtradeDD не substitute. MissingcoverageUNKNOWN.
- DailyES20: все136UTCдней Sep1–Jan14, включаяflat; loss=1−end/start, startseed10000. Lastcompleteminute; толькоlastday может иметьvalidateddirectnativeflatcash/orders0fallback, earliermissingdayUNKNOWN. Sortlossesdescending, q=n/5, fractionaltail `(sumfirstfloor(q)+fraction(q)*next)/q`, Decimal50, безclipping/rounding. Returnfraction и percentage×100 различать. OwnparentES20 по pre-firstfill→bothlegsflat/ordersquiescent, собственныйcalendar/count, diagnostic, неforcedmatching.
- NativeTPownership: actualOID/parent/strategy/instrument/generation/exactleaves; requiredpositiveunconsumedtargets, consumedне возрождать. ActualACK отдельно отqueue; matchingboundary/gapduration/STOPdrain. Margin/reservations/nativeheld/pending/debt/caps/clock передincrease, pendingSOL0hedgecredit. TerminalBTC/SOL0/orders0/inflightcommands0/zeroLiq; STOPPED→DISPOSED дополнительно, не financialflat.
- Predecisionrecord независимоA0flag: originalsecond−actualsecondfilled-ever, riskOFF/+60/quote/cross/ordinaryTP/cap/debt/pending/ACK/margin/reservations. a0_rights=[] при flagOFF не zeroopportunity. Grants/submits/accepted/denials отдельно. Releaseactualfill включает positivequantity/TradeID/orderID; dedupTradeID/conflictUNKNOWN; distinctpositivefilledreleaseorders не bool/submitcount.

Точный A0performancegate: **TOTAL_A0>TOTAL_C0; ΔTOTAL>2×max(0,fees_A0−fees_C0); settledDD_A0≤50% и≤C0; eventDD_A0≤50% и≤C0; dailyES20_A0≤C0**, при allfinancialgatesPASS и positiveactualreleasefills. Funding уже вTOTAL, не прибавлять повторно. Prefix не original70/90/full/OOSproof; absolutefloors4256975.067212381/5470396.514987347 неизменны.

## TRIM и upstream до экономики

Sourceowner должен предложить формулу; данныйreader её не придумывает. Freeze causalriskclock/exantefactorrelief/notional+volnorm/correlationbasis/lotrounding/minimums/partiallatefill/pendingpolicy, ownnativeaccount/fills/expenses. FutureactualC0SOLfills не onlineinput TRIM и не способ подобрать размерпослеoutcome. Невозможен faircomparison→STOPдоTRIM, не новаяgrid. Если TRIM нехужеC0 поTOTAL/DD/ES и лучше хотябыодному, SOLдоминируем→STOPсемейства; tradeoff показатьfrontier.

Нужны: newcheckpoint/diff/purepreflight/narrowreview/immutablefreeze; полная E1–E5actualcoverage иrootacceptance (essentialNOT_REACHED блокируетeconomics); exactTRIMcontract+review; UUIDentrysnapshot/rootGO; fourroleartifacts+nativeTP/margin/rights/predecisionproofs; explicitrootcompletionnotice накаждыйresult. Одинreadonlyfinancialpass безwatcher/autorepeat. Этотдокумент не выдаёт GO и не изменяетsource/gates/ledger.

Файлы/sha256, точные historicalreceipts и машинный checklistF01–F12: FINANCIAL_GATE_CONTRACT.json. Здесь только извлечение сохранённых значений иframework; новых monetarycalculations, engines/tests, source/ledger edits0.
