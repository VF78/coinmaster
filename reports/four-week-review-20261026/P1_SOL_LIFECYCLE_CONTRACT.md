# P1a — контракт SOL protection lifecycle по frozen7f38278

Статус: **SOURCE_FEASIBLE_CANDIDATE / NATIVE_NOT_PROVEN / NO_NEW_BUDGET**. Основание — P0_ROOT_ACCEPTANCE и P1a в UNIFIED_PLAN_RU. Выполнено только чтение frozenproduct, installed1.231.0 `.pyx` и сохранённых nativecause. Никаких imports BacktestEngine, тестов, constructors, sourcepatches, data/VPS/runtimeопераций. Предлагается один минимальный дизайн: **сохранять действующие SOLTP/STOP и применять publicmodify только к изменившемуся количеству/положенной цене; прекращать blanketcancel после ordinarySOLfill**. Source поддерживает этот route, но исполнение/ACK/races пока NOT_TESTED.

## 1. Установленная причина F4 и граница исправления

Frozenroot: `/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/paired-tp-continuity-20261025/source-7f38278/runtime`; productcommit7f38278257624b321c9d88d9df962505b6f5bab0. `coinmaster/strategy/paired_prefix.py:415–442` сравнивает signature `(p0,held,tp_lots)`; каждое изменение вызывает cancel всех remainingTP+STOP. После всех terminalACK generation увеличивается и комплект создаётся заново. Из-за fills held/signature вновь меняется и цикл повторяется. Accepted-set проверяет лишь число/status, не exactnativeleaves/currentdesiredgeneration.

F4 в `tests/run_registered_standing_tp.py:202–215`: сначала SOLrelief137; после newquote150 marketSOL96 и SOLsize.9 cancel завершался на nonquote152.01. Новый комплект TP тут же matched по сохраняемой книге96; actualSOLfills.3+.5 создали вторую отмену сcancel2s до154.01. Nextquote153 пришла раньше окончания; неизменённый guard `paired_prefix.py:480–481` правильно выдал PROTECTION_OVERDUE_NEXT_QUOTE. Источники actual: `reports/tp-continuity-20261025/{F4-physical4-cause.md,F4-physical4-cause.json,RESULTS_AND_NEXT_STEP_RU.md}`. BTCheld1.006/TP3leaves1.006; отказ вызван SOLreplacement, не доказанным BTCquantitydrift. SOLflat при pendingSOLSTOP ещё не pairterminalflat.

Запрещено исправлять это сменой quoteorder, sparsequotes, clock/latency либо waiverguard. Frozen fixture transport явно base/insert/update0,cancel2s (`tests/run_registered_standing_tp.py:150,290`). Поэтому отсутствие unnecessarycancel имеет проверяемый механизм; менять update_latency внутриengine не требуется. Производственный/venue cancelreplace publicAPI может иметь иной transport: здесь заявляется лишь stocknativebacktestroute, не гарантия exchange atomicity.

Не менять BTCcore/LEGACY_Q, initialBTCprices/weights, SOLsignals/TPformula/initialweights.25/.25/.50/stopATR, lotcorridor/u/v/caps, pairedBTCcuts, A0 originalrights и их часы. Переход G2/residual/rearm/новый рискbudget не часть этого исправления. ExistingBTCstandingTP остаётся владельцемBTC; SOLowner не пересчитывает BTCtargets.

## 2. Что действительно позволяет installedpublicAPI

Nativebase: `/Users/vf/Documents/ChatGPT/Coinmaster/runtime/.venv/lib/python3.12/site-packages/nautilus_trader`.

| Route | Source evidence | Строгий вывод |
|---|---|---|
| `Strategy.modify_order(order,quantity=...,price=...,trigger_price=...)` | `trading/strategy.pyx:1011–1091,1568–1645` | Реальный ModifyOrder через RiskEngine; одно значение должно отличаться. Publicreturn неACK; создаётся PENDING_UPDATE. Closed/PENDING_CANCEL не посылается. Для STOP не передавать limitprice. |
| Risk validation/transport | `risk/engine.pyx:496–582`; `backtest/execution_client.pyx:130–134`; `backtest/engine.pyx:3369–3392,3779–3793,5238–5259` | Qty/precision/state проверки; queued latency по типуcommand;matchingprocessmodify обращается к существующемуOID. Ручной cache/event/matching вызов не нужен. |
| Limit TP | `backtest/engine.pyx:5597–5634,8159–8205` | При unchangedprice тоже может быть marketable; Updated затем immediateTAKERfill. PostOnly пересечение reject. ExistingSOLTP GTC nonpostOnly (`paired_prefix.py:275–279`); менятьpostOnly нельзя. |
| STOP_MARKET | `backtest/engine.pyx:5636–5659,8206–8210`; `model/orders/stop_market.pyx:213–220` | **STOPquantity модифицируем** пока order доступен, trigger неinthemarket. Qty-only берёт прежнийtrigger. Если trigger ужеmarketable → ModifyRejected; closed/PENDING_CANCEL → routeблокируется; после trigger/IOCterminal отсутствующийorder нельзя воскресить. Нет основания объявлять STOPunmodifiable вообще. |
| Invalid total | `backtest/engine.pyx:8189–8200` | Native cachedfilled является нижней границей total; publicorder.filled может отставать от same-stackmatching. Нужны реальныеACK/fill и mismatchNO_GO, не fabricatedquantity. |
| ReduceOnly | `backtest/engine.pyx:7360–7410,7467–7486` | Stockexecution ограничивает фактическийfill текущимresidual; это защита от reversal, **не** доказательство exactentitlement или корректногоpendingSTOPaudit. Use_reduce_only сохраняетсяTrue. |
| Position association | `backtest/engine.pyx:7978–8044`; actualF3cause | Auto-resize смотрит отдельныйcachepositionindex. Raworder.position_id≠index. Не добавлять explicitpositionlinks/parentcontingencies радиautosize и не рассчитывать на unsolicitedUpdated. |

Технически минимальный publicroute найден. Точный unresolvednativequestion: **может ли registeredstrategy на queuedstockroute последовательно reconcile SOLTP/STOP после actualpartial/multiplefill, удерживая exactremainingrights иполучая настоящиеACK до следующейmatchingboundary, включая inmarketSTOPreject/latecancel?** Source допускает вызовы, но не доказывает это расписание. Ответ требует отдельно утверждённых E1/E2/E5, не нового архитектурного слоя.

## 3. Один owner, денежные права и nativequantity

В существующий pairedowner добавить лишь SOLreconciliation state. Никакого отдельногоOMS/account/PnL. В каждой immutableownerзаписи: parent, strategy/instrument/side, kindTP/STOP, level, initialOID, currentOID, nativevenueOID еслиизвестен, allocationgeneration, ackgeneration, actualfilledtradeIDs, pendingcommandsequence/desiredtotal/senttime, terminalreason. Исключить чужие/старыеparent/order; отсутствиеcache/order→UNKNOWN/NO_GO, не отсутствие риска. Trade из oldgeneration всё равно уменьшает actualheld и entitlement один раз, безp0/capreanchor.

Authorityheld — nativecachepositions; ownership дополнительно проверяется поstrategy/instrument/side/parentреестру. Один NETTINGposition ожидается. Rawpositionfield/cacheassociation записываются отдельно. Commandsubmission/pendingSOL дают0hedgecredit.

Права берутся из нынешней `tp_lots` логики `paired_prefix.py:43–56,323–379`:

- Каждый genuineENTRYfill добавляет floorlot allocations с исходными.25/.25/.50 и remainderlast. Пока ENTRYнеterminal, p0 существующий actualVWAP; ENTRYterminal фиксируетp0 иactualentry/caps. После этого TPprices/STOPtrigger не меняются. Если preterminalVWAP меняет положеннуюформулой цену, использовать ровно existingformula; это отдельная entryreconciliation, не новыйTPуровень/retune. Не откладывать initialprotection доentryterminal без nativeproof текущегоeventclock.
- OrdinaryTPfill уменьшает **только entitlement своегоlevel**. Остальные standingTP OID/leaves неизменны; consumedlevelневыставляется заново. Multiplefills обрабатываются по tradeID ровно один раз, nativeheld reread после каждогоactualcallback.
- SOLCAP/CLOSE/STOPfill уменьшает права по существующей proportionallocation/remainderlast; всеactualreductions/caps остаются прежними. Нельзя rebalance ordinaryTPfill как entry/debtallocation.
- Для eachpositive desiredTPleaves `r_l`: `new_native_total = actual_order_filled + r_l`. При совпадении total/price и отсутствииpending ничего не посылать. SameOID/unchangedprice по умолчанию. ДляSTOPdesiredleaves=actualSOLheld, total=actualSTOPfilled+held, unchangedtrigger. В штатномordinaryTPcase меняется лишьSTOPqty; не отменятьremainingTP.
- Desired0 не разрешает нулевойnativeorder. FullyfilledTPterminal → consumed, no replacement. Если reallocation дал0 ещёlivelevel, cancel толькоэтотOID; не объявлятьего accepted/consumedfill. Requiredtargets=только реальныеpositiveunconsumedrights. Если исходный новыйentry нельзя разделить на3валидныхTP/minnotional — прежний UNEXECUTABLE_DUST/NO_GO; не размыватьthreeTPcontract.
- Если nativeheld>0, но всеremainingrights0 либо quantities offlot/minqty/minnotional, состояниеNO_GO; не изготовлятьTP0 и не переноситьdust молча. ПриallTPconsumed иheld0→drainSTOP/inflight; никакого новогоSOLentry/rearm.

## 4. Command/ACK/generation и точные границы времени

Desiredgeneration увеличивается только при изменении entitlement/actualinventory/entryVWAP, не при одномACK/ordinaryquote. PerOID максимум один in-flightmodify; latestdesired coalesces отдельно. Новуюкоманду послеACK формировать от **свежих** actualfilled+remainingrights; не отправлять oldtotal второйраз. Перед publiccall pendingrecord обязан существовать, потому что callbacks могут прийти внутриcall; послеreturn не переписывать ужеполученныйACK.

Generic+typed event dedup по immutableeventUUID; genuinefill additionallytradeID. Bothroutes должны заходить в единый SOLnativehandler; сейчас `wave_overlay.py:2669–2677` маршрутизирует Updated/ModifyRejected в BTCstandinghandler, а paired `_pair_accept` понимает только initialAccepted. Минимальная callbackдобавка должна удержатьBTCroute без изменения егоmeaning. ACK признаётся лишь для ownerOID/command/quantity/price/trigger, реально подтверждённыхnativeUpdated/cache; sameOIDoldACK не авторизует latestgeneration. Если event не имеет echoedcommandID, использовать одинinflight+eventUUID+expectedpayload+actualstate; ambiguousmatch→UNKNOWN, не угаданныйACK.

Три timestamp: cause/event native `ts_event`; commandsentstrategyclock `clock.timestamp_ns()`; observedcallback clock/sequence. Часыdeadline от первогонеустранённогопричинногоgap; не сдвигать их приACK/reject/очередномfill. Existing `protection_since` nextquote guard сохраняется: если на новомquote ns>firstunrestoredgap requirednativecoverage не восстановлена, NO_GO. Кроме callbackquote отчёт должен показать orderstate на фактическихnative matchingboundaries; guard послеmatching не даёт права назвать предыдущийboundary защищённым. Историческаяvenueintraminute safety UNKNOWN.

PENDING_UPDATE не acceptedlatestgeneration. Если старый acknowledgedorder остаётся действующим, можно записать егоphysicalcoverage отдельно, но нельзя очищатьexactprotectiongap только постарому acceptedflag. Если pendingdesired не завершился к следующейmatchingboundary/quote — fail fixture; не вводить новый graceperiod. При update0/nativequeue нужен publicflush через уже существующее nativeadvance/pump доследующегореальногоquote, без directmatching API, без измененияengineclock/latency. Сможет ли это дать требуемыйACK и избежать same-stack drift — nativegateE1/E2.

ModifyRejected: сохранить realreason/currentnativeorder/actualheld. Если старый nativeorder всё ещё точно удовлетворяет **текущему**desired, можно сверить его заново без fictionACK; иначе unresolvedgap/UNKNOWN→existingNO_GOclose. Не повторятьinvalidtotal/trigger/price в цикле. RejectприinmarketSTOP не повод cancelreplaceвсерии: stop имеет право исполниться наnativequote; покаэто не произошло, никакой новый риск/право неадмиттируется. TerminalIOCpartialSTOP сохраняет PARTIAL_NATIVE_STOPNO_GO; не заменятьIOC наGTCс syntheticremainder.

## 5. Переходы и закрытие

| Состояние / event | Действие | Следующее / запрет |
|---|---|---|
| ENTRYfill / initialprotection | ActualVWAP+rights, только отсутствующиеvalidTP/STOP; reconcile modifiedexisting приизмененииentryVWAP | WAIT_ACK→PROTECTED только exactnativecurrentgeneration; earliestgapнеобнулять |
| PROTECTED / partialTP | Decrementthatlevel; unchangedothers; publicmodifySTOPqtyеслинеобходимо | WAIT_MODIFY_ACK; consumedTPисключитьтолькоactualterminalfill |
| WAIT_MODIFY / anotherfill | Применитьactualtrade, latestdesiredcoalesce; не наложить второйcommand | ACK→freshreconcile; staleACK неPASS |
| FullTP / remainingheld>0 | Retirelevel; keepotherTP; resizeSTOPsameOID | Нетresubmitconsumed; no blanketcancel |
| ExternalSOLcut / qtydecline | Existingproportionalrights/caps; modifyonlychangedpositiveleaves+STOP | Zero-livelevelcancel индивидуально; pendingcancelfillsразрешенытолькокакactualdecrease |
| Riskinactive/BTCflat/forcedowner | Existingcloseownerwins; cancel liveSOLENTRY/TP/STOP once, запретновойprotectiongeneration | CLOSING; no duplicateclose/no resurrection atCanceledcallback |
| CANCEL_PENDING / lateTPorENTRYfill | Genuinefillreconcileactualheld/caps; do notmodifycancelpendingOID; zero pendingcredit | Latestclose/reductionпослеterminalACK; noafterACKfillclaim безactualproof |
| SOLheld0 / pendingSTOP | CancelSTOPonce; keepowner+registries andclose/reconcilelock | DRAINING, **notterminalflat**; ReduceOnlyguardsneverreopen; reject/unknownnotignored |
| PairBTC0/SOL0 + noopen/inflight/pendingcommands | Currentterminalowner recordspositions0/orders0/inflight0 andcleanscomponents | PAIRTERMINAL; onlythenreleaseparent |
| Dust/ownership/ACK/deadlineunknown | DurableNO_GO, no increases/A0release, existingconservativeclosure | Никаких zeroTP/reportPASS/sourceclockwaiver |

BTCintegration: keepremainingBTCstandingquantities afterordinaryTP, residualdebt fromnativeheld−absolutecap, actualduration от debt_since. CleanmarketableDEFER требует healthycurrentrisk/exactBTCcoverage иactualoutstandingdebt; послеUNKNOWN_RISK branch executionнеqualifyingproof. Firstcleanquote должен обслужить actualresidual в исходныйserviceclock; всеpastdurationсохраняются. OrdinaryBTC TP→flat означаетNOnewdebt, отменуA0rights иSOLdrain. SOLhandler не разрешает A0 приgap/unknownACK/pendingcancel; originalchildclock/releasecount непрерывны.

## 6. До кода и proposed≤6fixtures

**Все ниже NOT_RUN; proposed6cap не ownerapproval.** Возможнаяреализация послеP1b/newscope состоит из `coinmaster/strategy/paired_prefix.py` (SOLownership/reconciliation), только necessarycallbackrouting в `coinmaster/strategy/wave_overlay.py`, existingprobe/tests/audit. `standing_tp.py`, domainBTC/signal/price/weights/caps/A0policy менять не нужно. Если окажется нуженнетривиальныйrewrite этих частей — STOP/scope review. Contractобъясняет route, не разрешаетpatch.

Engine-freepreflight будущегоscope: staticdiff exclusionmoneyformula; AST/publicsignatures/modelstatuses; настоящиеinstrumentlots/minnotional/types; source/data/config/installedengineSHA; реальный `/inputs/data` stockreader/partialmonth/fundingpreflight; eventdedup andpayload contracts; stdoutJSONprecision; durableclaim/freshnamespace; capturebeforeend/dispose. Object-level Cache/Order/event проверки отдельно engine-free, matching всегда budgeted. Сейчас эти проверки не запускались.

| Fixture | Источник достижимости / schedule | Actualgates / приNOT_REACHED |
|---|---|---|
| E1 ordinarySOL,zero transport | Естественный registeredparent/actualpartialENTRY и IOCterminal; causalSOLsignal послеeligible; nativequotes с объявленнымfreshdepth. MultipleTP fills в одномadvance достижимы черезpricecrossнесколькихlevels/раздельныеstockfills; staleidenticaldepthнеприниматьзаreplenishment. | Initial3positiveTP+IOCSTOP; partialTP непереподнимаетothers; sameOIDSTOPUpdated,total=filled+leaves; fullconsumption; alltradeIDdedup; nativecachecash/fees; everyboundaryexact; oldTPneverrecreated. Еслиinitialentryclockнепокрыт — FAIL, неfixtureseedoverride. |
| E2 delayedcancelstress | Staticbeforeconstructor base/insert/update0,cancel2s какF4; quotes150→nonquote152.01→153 остаются. OrdinaryTP больше неcancelreplaces; затем реальныйriskOFF/closecancellation сTPfill доcancelACK, чтобы проверить repeatedreconcile не рождает SECONDcancelwindow/newTPgeneration. | FreshsameOIDACK before153; actualpendingcancel→fill→Canceled сtimestamps/IDs; noafterACKfill/reversal; existingguardunchanged; SOLflatpendingSTOP неterminal; правильныйdrain. Второй **обязательныйreplacementcycle ordinaryTP** не postulate: именноегоустраняем. Если поlegitimateENTRYpricechange replacement всёженеобходим, егоcase/расписаниеfreeze доapproval, не придуматьпослеотказа. |
| E3 BTCstanding/debt | ExistingF4 P1 цены/partialdepth дляordinaryTP, SOLrelief иmarketableTP3; только cleanbeforeNO_GO timeline. | SameOIDlatestACK; partialfilled+desiredtotal; exactallremainingBTC; healthyDEFER debt>0/duration; firstcleanquoteactualresidual; ordinaryTPflat→nonewdebt. ВозможностьсочетаниясE2 незаменяет отдельногоactualgate. |
| E4 A0rights | ExistingregisteredP2naturalshortparent на86400; actualpartialFIRSToriginalprice; riskOFF+60; stockpostOnlycross/marginfreshmarks; статическийcancel2s. Nativecachemarkmutation/forcedqty запрещены. | Realoriginalsecondonce/noFIRSTrefund; pendingcancel→actualfill→Canceled; postACKnofill; typed+genericactualACKunknown/fresh; stale→freshmargin реальнымиmarkevents. ИсходныйF4 P2 NOT_REACHED, поэтому source-supported schedule толькоproposal. Faultinjectcallbackvisibility можнотолько объявленнымfixturetransport безподменыnativecache ис generic+typeddedup. ЕслиэтоединственныйспособполучитьUNKNOWN, границуfixturevsactualstockproof показатьявно. |
| E5 registeredintegration | Один registeredstrategy/account, 729seed+naturalparents какF4;zero transport для будущегоeconomicroute; pairedSOL andA0scope послеP1b. Никаких injectedpositions/domainqty. | Reachnaturalparents/actualSOLTP+STOP/BTCdebt/A0еслиG1GO; fullcurrentgenerationcoverage,cashidentity/BASEfees, allpositions/orders/inflight0/zeroLiq;5STOPPED→DISPOSED. ЕслиG1NO_GO mapE5freezeбезA0 доapproval; E4slotнепереназначатьмолча. IntegrationrequiredдажееслиE1–E4PASS. |
| E6 conditionalreserve | Только одна заранееопределённая consolidatedcorrection и exactfailedfixture repeat послеrootdisposition | Никакой новойгипотезы/авторетрая. Всеinitialfailuresвledger; exhausted→STOP. Еслиосталосьunreachedcriticalgate — неPARTIALPASSдляeconomics. |

E2/E4/E5 sourcefeasibility достаточна для drafting, **не для заявления nativeproven**. Замороженнаякарта должна заранее указать book/quotes/events/transport/checkpoints иasserts на каждыйstage. E2 repeatedcancel idempotence иE4 реальныйlatefill требуют конкретного исполнимогорасписания; неизменённыйbook depth может бытьexhausted, rawpositionfieldнеcachelink, publicreturnнеACK. Если такиеpreconditions source/APIнеобосновать, остановитьсядоownerrequest, ане тратитьсогласованныйslot.

## 7. Решение P1a

Выбран один boundeddesign — **standingSOLprotection with selectivepublicmodify**, сохраняя existingSTOP_MARKETIOC и per-levelrights, с explicitACK/generation/deadline. Обобщённого APIblocker «STOPнельзяmodify» нет; есть конкретные inmarket/pendingcancel/terminalограничения и недоказанная queuedintegration. ИзменениеordinaryTP не требует отменыremainingorders; потому механизм прямо устраняет F4cancelstorm, но прибыльность иfinalnativePASS UNKNOWN.

P1b growth HOLD не допускает обычную A0экономику. Код/nativeшаги потребуют отдельного решения по P1b, конкретного реализационного scope и directownerчисловогоbudget. Ни old4/4, ниunusedprefix3 неauthority. P1a не закрывает C0gate и не доказываетoriginal70/90/50.
