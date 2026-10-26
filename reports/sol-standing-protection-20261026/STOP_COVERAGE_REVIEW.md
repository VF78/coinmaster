# STOP coverage — узкое решение до первого engineeringGO

Статус: **PRE_GO_CONDITIONS / NO_NATIVE_PASS**. Это решение по достижимости и минимальному coverage, не reviewнеfrozenproduct. Source старого7f38278/P1a и checkpoint95purePASS не дают actualSTOPproof. Tests/engine/source/ledgerизменения0. Approvedcap6/4 не увеличивается.

## A. Обычный STOP — обязательное actualnativeproof

В существующих E1/E2 необходимо показать оба события: **(1)** настоящий sameOID STOP_MARKET quantity modify→nativeOrderUpdated с unchangedtrigger/IOC/reduceOnly иtotal=actualfilled+desiredleaves; publicreturn/PENDING_UPDATE неACK; **(2)** на настоящейкотировке пересечьнеизменённыйtrigger и полностью закрыть настоящийSOL черезэтотSTOP, затем пройтиremainingTPcancel/BTCdebt/terminalcleanup. STOP_MARKET не обязан выдавать отдельныйOrderTriggered event: обязательны actualstopOID/tradeIDs, nativeprices/commissions/cachequantity ипричинныйtrigger-cross, ане assertнаevent другогоordertype.

STOPfill должен уменьшитьSOLrights/actualcaps, не вернутьconsumedTP ине создатьnewSOLprotectiongeneration. Не подменятьSTOPfill marketcloseorder, forcedpositionqty либо проверкой orderobject. Не менятьTIFIOC наGTC. FullSTOP при достаточнойпредъявленнойликвидности не доказывает partialpath/venueгарантию. Если Aне включёнвкарту/reachableasserts доfreeze — первыйGO блокируется.

## B. In-market STOP ModifyRejected — условная source-exclusion, не обязательный искусственныйreject

Installed1.231.0 `backtest/engine.pyx:5636–5659` действительноrejects quantitymodify, если unchangedtrigger уже inmarket. `trading/strategy.pyx:1568–1645` негенерируетmodify дляclosed/PENDING_CANCEL, `engine.pyx:8159–8210` маршрутизируетSTOPqty с прежнимtrigger. При fixedtrigger, staticupdate0 иотсутствииinterposedSOLinput validstandingSTOPquantityupdate обычноидётпринеtriggeredbook. ПослеобычногоSOLquotematching triggerполныйIOCSTOPужеterminalдоstrategyquote; последующийpublicmodify станетNoOp, ане genuineModifyRejected.

Однако **match-beforequote сам по себе не доказываетunreachable**. IOCpartialfill callback/PositionChanged могут доставляться внутри `fill_order` до `apply_fills` последующего IOCcancel (`engine.pyx:7380–7440`). В этомокне STOPможетбытьPARTIALLY_FILLED, ещёнеPENDING_CANCEL/terminal иtriggerужеinmarket. Еслиowner попытаетсяqtymodifyпривызванномэтимfillreconcile, genuineinmarketModifyRejected source-reachable. Нельзяисключитьэтуветвь толькоутверждением«IOCзакрываетсяраньшеcallback».

Минимальное приемлемое sourceproofдля B: frozenownerявно ставит closing/failclosed STOPfillbarrier **на любом actualSTOPfill до возможногоposition/protectionreconcile**; ниpartial/fullSTOP ниclosing/cancelpending/terminalSTOP не допускаютmodify. В полномsource/eventroute доказатьединственныйquantitymodifyroute иотсутствиеalternativecallbackпередbarrier; update0/fixedtrigger/nointerposedSOLinput остаютсяfreezeinvariants. Тогда nativeinmarketModifyRejected дляnormalintendedroute **NOT_APPLICABLE_UNDER_PROVEN_INVARIANTS**, анеPASS. PublicclosedNoOp отдельнофиксируетсябезложногоnativeRejectclaim. Generic/typedcallbacksdedup/barrier должны охватыватьсяодинаково.

Если frozenproductтакогоsourceproofне имеет, Bостаётся **UNRESOLVED_REACHABLE_CONDITIONAL**: доGO либоубратьunsafeattempt вразрешённомlifecyclepatch иreview, либообъявитьactualnegativebranch в существующемE2. Нельзя менятьtrigger/latency, вставлятьfakeSOLbook/cache/event либо объявлять sourcebranchactualproof радигалочки. РеальныйModifyRejected наодномinvalid-totalSOLTP, ужеизвестныйF4, не заменяетSTOPtrigger-rejectproof.

## C. Partial STOP IOC — негативный failclosedcase либо полный unreachablebound

По source `engine.pyx:7335–7440` IOCпослеavailablefills отменяетостаток **до** L1syntheticexhaustedbookremainder. Поэтому настоящаячастичнаяSTOPfill/IOCterminal сSOLremaining>0 — допустимыйstockscenario; нельзя обещатьгарантированныйliquidexit. Старыйowner `paired_prefix.py:298–319` считает0<filled<total приterminalSTOP `PARTIAL_NATIVE_STOP`/NO_GO; новыйpatch обязан сохранитьконсервативныйсмысл.

**Предпочтительный минимальный путь — включитьactualnegativepartialSTOP всуществующий E2**, последнимnegativecase после normalA/latecancelcoverage, на допустимомnaturalparent/actualentry и statictransport. ЗаранееобъявленнаяSOLtriggerquote меньшегоavailabledepth, genuinepartialSTOPtrade и IOCcanceledremaining; не менятьlatency/TIF/filledqty/nativecache. Нужны: capturedprecleanupactualheld>0/terminalSTOP, durableNO_GO/UNKNOWNrisk/blockedincreases+A0, нольrearm/phantomprotection/nativeZEROorder, preservedBTCstandingTP иactualdebt, толькосуществующийnativeconservativecloseowner. Partialfill/terminalhandling не должен ждатьследующуюоткрывающуюсделку дляобнаруженияриска.

Еслиconservativecleanupдостигаетnativeflat, записатьactualorders/fills/funding/positions/inflight и5STOPPED→DISPOSED. Это **expectednegativefailclosedcomponent**, неfinancialPASS небезопасногосостояния. Еслиcleanupнеflat, нельзя manuallyreset/ликвидироватьпозициюизfixture/заменитьstate иназватьflat. Сохранитьunresolvedstate+failureдоend/dispose; полный integratedgate остаётсянепройденным. Процесснаяclassification/expectednegativefixturequalification заранееfreeze; не переименовыватьошибочныйprocessпослерезультата. Expectedguardlatch неwaiver; guardоставлениriskнеразблокирован.

АльтернативабезactualnegativeC допустима только **доGO** при independentlyreviewedsourcebound всех принятныхэкономическихinputs/admission: накаждомreachableSTOPtrigger remainingnativeheld≤**действительно available opposite liquidity после всех предыдущихmatchingorders иconsumption**, достаточенmatch/precision, нетпараллельногодругогоowner, lateentry/excess/closesнеобходятbound. Просто «historicalL1depth1000 иодинSOLIOC≤1000» недостаточно: надо доказатьremainingavailabledepth ивсеnativeordering/latefill/quantitypaths, анетолькоdisplayeddepth/intendedqty. Такогополногоbound ввыбранныхматериалах **нет**. Безнего current95pure/source/objectonly Cне закрываютessentialriskcoverage.

Приполномbound actualpartialpathможнообозначить UNREACHABLE_WITHIN_PINNED_ECONOMIC_ENVELOPE, одновременносengine-freefailclosedhandlerproof иобязательнымrunaudit: любоеobservedpartialSTOP немедленноNO_GO/blockedremainingprefixslots. Это неvenue/liveguarantee и не «нетpartialSTOP вообще». РежимnegativeE2 либоbound выбираетсядоfirstconstructor; послеmoneyresults менятьтребование нельзя.

## Минимальная disposition для root

1. **A essentialactual** — source/object/PASS95недостаточно; freezeactualsameOIDSTOPUpdated иactualtriggerfullfill вE1/E2.
2. **B source-excludableусловно** — explicitno-modify-on-anySTOPfillbarrier иcompletecallbackorderingproof; иначеSTOPдоsource/mapисправления. Не требоватьискусственногоnativeReject наunreachableподмоделивызове; не называтьNOT_APPLICABLE nativePASS.
3. **C essentialnegative** приотсутствииполногоsourcebound — дополнитьсуществующийE2безновогоconstructorилизаранееfreezeполныйbound сreview. Сохранять IOC/guard/nativeclosure; unsafe/uncovered→NO_GO. Normal E5flat/accountproof по-прежнемуобязателен независимоотnegativecomponent.

ПервыйGOвозможентолькопосле source/mapfreeze, закрывающеговышеперечисленныеpreconditions иостальныеapprovedgates. Данныйreview не рассматриваетimplementationиGOневыдаёт. Никаких новыхэкономических/liquidexit/globalvenuePASSclaims.
