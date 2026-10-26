# BTC_TRIM — независимый review дизайна до кода

Статус **CONDITIONAL_DESIGN_ACCEPTANCE / TWO PREFREEZE CONDITIONS**. P0=0; P1=2 открытых уточнения до реализации TRIM: точный собственный risk/deadlineclock и сохранение полной C0-nativecoverage при назначении E3 в TRIMmode. Это не sourceacceptance/nativePASS/rootGO. Новые 6fixtures/условные4prefix подтверждены `owner-approval.json` (protocolfaa39247); этот review не добавляет constructors/варианты и не меняет C0money/G2.

Проверены только предложение исполнителя, frozen7f `coinmaster/research/paired_signal_feed.py`, `_pair_start/_pair_quote` в `coinmaster/strategy/paired_prefix.py`, P1contract и approvedprotocol. Productbranch ещё не frozen, implementation не рассматривалась. Source/engine/ledger не менялись, tests/imports/constructors0.

## Формула допустима с точным названием сравнения

Пусть B=|qref| PB — известный BTCnotional в quoteUSDT, H=intendedSOL PS — противоположный SOLnotional. σB/σS — стандартные отклонения одинаковых доходностей, горизонта/окна/единиц; ρ — signedcorrelation BTCreturns/SOLreturns, не correlation с ужеинвертированнойshort-ногой. Для longBTC/shortSOL и shortBTC/longSOL ковариационный знак одинаков:

`Var(B*rB − H*rS)/(B*σB)^2 = 1 + c² − 2ρc`, где `c=HσS/(BσB)`.

`a=.5σB/σS`, `intendedSOL=floor_SOLlot(a*qref*PB/PS)` в точности повторяет намерение C0при activation; c dimensionless, доfloor≈.5. `r=sqrt(1+c²−2ρc)`, `target=floor_BTClot(qref*r)` задаёт unhedgedBTC с той же **модельной one-step totalvariance на замороженном snapshot**, с консервативнымBTCrounddown. Не надо умножать ещё наρ, считатьinversebeta или использоватьsignedpositionqty как отрицательныйqref. Формула одинаково применяется к обоимBTCнаправлениям.

Название «точно factor-risk matched» было бы неверным. Отдельно отчёт должен показывать hedgeBTC-factorresidual `1−ρc`, orthogonalSOLcomponent `c*sqrt(1−ρ²)` и TRIMfactorresidual `target/qref`. Их squares дают totalvariance hedge; факторные экспозиции TRIMиSOL обычно различаются. Напримерρ=.5,c=.5: hedgefactor=.75, orthogonal≈.433, totalratio≈.866; TRIMfactor≈.866. Допустимое название: **ex-ante one-step total-variance matched BTC_TRIM**, factorresidual отдельно. Никакого equalitypathDD/profit/stress/liquidationmodelclaim.

Границы: qref/PB/PS/σB/σS строгоpositivefinite, qref настоящий nativeBTCлот; intendedSOL>0 и тотжеadmission/minlotcontract C0; ρ∈[−1,1] строго; radicandfinite≥0, r≤1. Приr>1/no admissibleintended/unknowncoeff — INCOMPARABLE_STOP, не clamp к1, не trimincrease, не rho=0 fallback. Дляc≈.5 r≤1 требуетρ≈≥.25; это объективное ограничение controladmission, а не выбор удачногоwindow. Если r=1, допустимнулевойtrim сявнымNOT_EXERCISEDfillcoverage; не заявлять nativeBTC_DEBTproof. Если r=0/fullflat или roundingbelowminqty — отдельные nativeflat/dustgates, не нулевойордер. Для только положительных frozenρ старыйC0validflag сохраняется; новыйcontrol не расширяет C0marketadmission.

СчитатьDecimal/точныеFraction, без float. Перед отправкой подтвердить `target_lots² ≤ qref_lots² * radicand < (target_lots+1)²` (с корректными единицами) либо эквивалентную exactrational bracket, чтобы sqrtprecision не сдвинула BTCлот. BTCrounding даёт≤1lot дополнительногосокращения, фиксируется как riskmatchresidual. Уже quantizedintendedSOL используется вc, не idealunroundedhedge.

## Неизменяемые данные и цены

Frozenfeedparser `paired_signal_feed.py:14–39,43–75` уже проверяет SHA/H4order, available=t/notbefore=t+60s, D1lastend≤t−1D; извлекает `sigma_btc_d1_30`, `sigma_sol_d1_30`, `rho_d1_30`, но текущий PairedSignal их невыносит. Разрешённый payloadaugmentation: immutableρ/σB/σS + их window/end/provenance/units из тех же frozenCSVстрок; не пересчитыватьизбудущихoutcomes, не скачивать/перезаписыватьCSV. Существующие a, valid, signalflags, PB/PS, rows/order/hash/clock сохраняются побайтно/семантически; auditdiff старыхownerrows равен0. Новыйrho∞/outside[-1,1] блокирует TRIM, ане переписывает sharedC0valid. Старыйparser допускаетρ до1+1e−12; TRIM должен явно INCOMPARABLE при>1, не незаметно clamp/C0change.

PB/PS — frozenmarketclose строки причинногоt, не futureactualC0SOLfill и не currentnativeexecutionprice. qref — положительная quantity настоящего BTCposition при selection того же parent/side, как C0 `_pair_start:202–250`. Snapshot qref/PB/PS/coefficients/parent/decision/eligible immutable. Перед executioneligible повторно проверяются parent/side/heldqref и cancelbarrier; еслиnativeBTCуспелизмениться, нельзя молча reanchor target или использовать C0qref: INCOMPARABLEпоявившийся mismatch. Nativefillprice/fees/funding/actualresidual позже отдельно; они меняют realizedwealth/risk, но не переписывают initialformula.

**Ограничение intendedrisk.** Controlmatches plannedSOL, не actualC0SOLfilledcoverage. У C0 partialentry/dust/cancel/latefill и allTP могут изменить фактическоеH и будущийBTCcap; TRIM остаётся permanentinitialcap. Динамической riskpathmatchedness нет. До financialqualification сохранить ownC0intended/actualSOL/timing/coverage, ownTRIMrequested/actualBTCreduction/timing; различие показывать, не исправлятьTRIM будущимC0trace. Pareto DD/TOTAL/ES сравнение интерпретируется как сравнение двух declaredstrategies с initialmodelriskmatching, ане causalSOL-onlyeffect/доказательство одинаковогоheldrisk на всёмпути.

## P1-1: зафиксировать собственный TRIMclock до реализации

C0eligible=signal_ns+MINUTE, но actualmaxholddeadline начинается с **первогоactualSOLfill** (`_pair_fill:346–349`); riskOFF такжеотследующегоBTCquote, пересёкшегобoundary (`_pair_quote:451–459`). В SOL-disabledTRIM событияfirstSOLfill нет. КопированиеC0futurefirstfill/подстановкаfakeSOLfill запрещены; «тотжеriskOFFclock» безформальногоопределения неоднозначен.

Минимальное решение для rootdisposition: TRIMselection/eligible/cancelbarrier — тотжеsignal schedule; ownreferenceclock=immutableeligible_ns, nominaldeadline=eligible_ns+(B2:4h/F0:8h). BoundaryriskOFF проверять причиннымиBTCquotes тойжепоследовательности, не backdate. Это **declarednominalclockproxy**, не exactactualSOLfillanchoredC0clock. Permanenttarget не восстанавливаетсяниприriskOFF, ниприdeadline; childrights остаютсяpermanentcancelled в C0/TRIM. Еслиrisk ужеinactive на eligible, применятьтотжеpreentryadmissioncancel и INCOMPARABLE/NOT_ADMITTEDreason доtrim, не создаватьчужуюпозицию. Послеstart no rearm/restore; clock влияет наmeasurement/ownership, неразрешаетновыйBTC. Rootдолжен freeze этот выбор до кода; если exactactualC0holdclock обязателен, предложенныйTRIM INCOMPARABLE иегоэкономическийslot STOP.

## Nativecontrol — отдельный абсолютный BTCcap

TRIMmode immutableприконструированииstrategy/config; noSOLorders/virtualpositions/entryfill/PairedCapscoveragecredit/solmax/reconcile. Создаёт собственный absoluteBTCtarget от настоящегоqref один раз; actualdebt=max(0,nativeBTCheld−target), неrequested trim. Reuse существующего nativeBTC_DEBTsubmit/fill/standingTP route можно narrowsharedhelper либоявнымTRIMdispatch, без fakeSOL ибезподмены C0caps. Pendingtrim даёт0fulfilledreduction; lateBTCincrease/cancelrace остаётсяdebt иобслуживаетсяnativefill. OrdinaryBTCTP не восстанавливаетtarget/child; приBTCflat cancelincreases/pendingdebt, no newdebt, complete remainingTP/flataccountгейты. SOLpositions/open/inflight>0 вTRIM→UNKNOWN/incomparable.

Lockedoriginalsecondcancelbarrier обязателен до reduction; no childrearm/retry/refund, A0tradingflag выключенвTRIM. Merelycancelrequested≠ACK: actualpendingcancel oldchildfill увеличиваетactualheld иresidualdebt, потом serviceдоcap; no afterACKfill безactualnativeproof. BTCTPstanding/marketableDEFER не отключать радиtrimroute. C0measurement остаётся side-effect-free, C0moneyнеразделяет TRIMtarget иливходящиеρvalidfilters. Любая необходимаясменаG2risk/C0signal/caps — scopeSTOP.

## P1-2: E3можетбытьTRIMmode, но покрытие C0нельзяпотерять

**Да, E3можно зафиксировать TRIMmode на весь один constructor**, еслиroot доfreeze обновит карту и независимыйsource-review подтвердит reuseactualBTCroute. Нетдополнительногоengine, нет midengineconfig/variant swaps; stages меняюттолько causalinput/events, нережим. E3 должныдатьnonzeroactualtrim, originalsecondcancelrace/partialfill→residualdebt, standingTPcurrentqty/ACK, healthyDEFER наmarketableTP, firstcleanquoteexecutionresidual, no fakeSOLcredit, terminalflat. Formula-validr=1 не даёт E3proof: выбрать объявленныйcausalcohortfixture сr<1, не подкручиватьэкономическиепараметры.

E3TRIM **не доказывает** causalSOLrelief→C0BTCdebt изависимостиSOLSTOP/ACK. Этиmandatorygates надо явноназначитьE1/E2иregisteredE5: C0mode actualSOLpartial/multipleTP→capcut→actualBTC_DEBT; стоящиеBTCremainingTP/actuallatestACK; healthyDEFER доUNKNOWN; ordinaryTPflat→no newdebt; SOLpendingSTOPdrain; completecash/account/zeroLiq/flat. E4 остаётсяseparateoriginalA0rightsfixture, notTRIM. E5immutableC0/registeredintegration; нельзя включатьA0внутриE5радиcoverage, еслиmode/configиначеfrozen. A0nativeproof E4, экономическийA0условен. Если E1/E2/E5необеспечиваютэтиreachabilityгейты в исходных≤48h/6physical, STOP доlaunch/ownerbudgetamendment, не subsetPASSдляэкономики.

## Decision и обязательные engine-free gates

Математику принимать сlabeltotalvariance ивышеописаннымилимитами. Передреализацией root закрываетP1-1(clockproxyversusexactclock) иP1-2(immutableE3TRIM+explicitC0coverage). Затем sourceowner может реализовать толькоdeclaredTRIMscope; nativeGO остаётсяотдельным.

Meaningfulpureacceptance доconstructor: symmetriclong/shortmath;ρ1/.5/.25/0/negative boundaries; quantizedSOL иBTCbracketing; zerointended/missing/NaN/±inf/illegalrho/ratio>1; a-consistencyвтомже frozenDecimalcontext; futureD1/availability/notbefore rejection; oldownerrows/CSV unchanged; fixedqrefchangedparent mismatch; riskinactivebeforeeligible; noSOLrouting/fakecaps; oneperparenttarget/no restore; commandquantityfromactualdebt; causalclockproxyanddeadlineexplicit; sourceASTimmutablemode/noBacktestEngine inpreflight. Тесты здесь не запускались, sourceещёнеfrozen. Actualmatching/ACK/fill/flatдоказательств нет; их нельзя вывестиизpureformulaPASS.
