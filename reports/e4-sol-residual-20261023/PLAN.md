# E4 + защита остаточного SOL: принятый пакет

Владелец23.10.2026 поручил реализовать и проверить E4 с защитой остаточногоSOLпослеBTCflat, сохранив прибыльныеBTCfallback иSOLправа. Pilot/production/ключи/реальныеордера/deploy исключены. Предыдущий пакет завершён в4f54c2c/071dfa5; результаты сохраняются.

Контроли неизменны: S0TOTAL6077107.23887483/DD66.2569148647%; E4TOTAL5631617.35953723/DD57.5854104596%; XS(E4+старыйS)TOTAL5406345.11636863/DD58.9474368842. S0/E4/старыеэкономические результаты не пересчитываются. MandatoryP0 нужен только для доказательстваflagsOFFновогоисходника=XS.

Acceptance: global settled native minuteDD≤50%, TOTAL≥5470396.514987347 (≥90%чистойприбылиS0),0ликвидаций, полныеreceipts, terminalflat. ЗатемMAX_TOTAL. Peakне сбрасывается. Ровно тотже24m[2024-09-01,2026-09-01),seed10000USDT,reserve0,DPoff,Bybitdata/fees/funding/margin/lot/tick/executionpolicy/settlement. Неизвестныйfundingпоактивамне становится0,bridgeне называетсяfunding.

## Почему два варианта

Одно разрешениеBTCflatне устраняетраннийконтрпример:03.10старыйSуже продал500SOLпо134.72, BTC0.940оставалсяоткрыт; localDD52.5801%. ДискретныйH1запуск прошёл уже околоDD46.59, хотяпорог40. Поэтому разделяем два изменения, не подбираяпорогивслепую.

R1=E4+исходныйS (H1/DD40/adverseSOL2%/однократное сокращениефактическогоSOLна50%) + confirmednativeBTCflateligibility. BTCflatдоказан: prioractualBTCentry/domainqty0/nativecacheflat/нетunfinishedsplit,queued,pending,open/inflightBTCwork. ПриоткрытомBTCпрежнийopposite/betadominanceсохраняется. Неизвестныйкэш/ACKнеflat. НельзяосиротевшийSOLзапускатьизискусственноemptyreport.

R2=тотжеR1, нооценкаодинразнаполнуюреальнуюминутнуюпаруBTC/SOLquotesвместоH1. Пороги40%/2%/50%не меняются. Толькопричинныйпоследнийполныйnativeaccount/marks, безбудущихOHLC,синтетическихmatchingBarsилиfakeD1. Порядокпроверки/freshness/asofфиксируетсяsourceownerвконтрактеипроверяетсяnativeтестом. Этоустранениечасовогозапаздывания, не обещаниегарантированногоDD50.

Общее:одинсуществующийnativeexecutor; frozenactualremaining/lots, cancelincrease/ACK/latefill, приоритетmandatory/ordinaryexits, nooversell, onceperrealSOLcycle, noautoadd/rearm. РанееearnedordinaryBTC-TPrighsнепересчитывать/невыдумывать/неудалять; защитноеSOLисполнениенеBTC-TPи негенерируетправа. ОстальныеSOLexits/age/sigmaсохранены. Nativecashреинвестированиеестественноменяетбудущиеобъёмы:нефиксируемстарыеQдляподгонки. НикакихZ/BTCriskcuts/fullSOLcut/новыхstops/новогоhedge/optimizer.

## Очередь и бюджет

- R00: exactsourcebd04/newisolatedcanonicalcheckout/данные/контроли/Projectreadback.
- R01: residualeligibility+minutevariant; одинвладелецproductsource; новыйdefaultOFFresearchflag, нопродакшеннеактивируется.
- R02: focusednativeполучение/partial/cancel/latefill/unknownACK/flatproof/closedbar-vsquote/asof/oncecut/rights/normalexits; одиннезависимыйадресныйreview.
- R03: freeze source/config/pins; новыйP0flagsOFFEXACTXS. Прирасхождениине маскироватьтолерансомипоследующиеengineблокируются.
- R04: R1, затемR2, отдельныйengine/account/fundingjournalкаждому; одинengineодновременноMac.
- R05: максимумодинfreshengineповторлучшегопроходящего50/90. Нетпроходящего—повторNOT_RUN_GATE_FAILED.
- R06: независимаяsaved-outputпроверка,comparisonS0/E4/XS/P0/R1/R2, globalDDepisodes/assetfill-net/maker-taker/fees/turnover/SOLriskactions/rights/sourcehashes, Project/checkpoint/publish.

Всегомаксимум4полныхфизическихпопытки:P0,R1,R2,одинусловныйrepeat;неразрешеныскрытыеretry/сетка/сменапороговпослерезультата. P0илидругойinvalidфизическийрасчёттратитслот;коррекциякодадоканоническогоfreezeврамкаходногоfocusedpassиоднойсущественнойправки. NoS0rerun/nopilot/noVPSresearchload.

SourceтольковcanonicalVPS /root/.openclaw/workspace/coinmaster/coinmaster, отдельныйcheckout/branchотbd04. Macreadonlyexecutionmirror. НакаждыйengineреальныесохранённыеJSON/CSV/журнал. NativeNautilus1.231единственныйэкономическийдвижок. СтарыйbenchmarkNOT_FAITHFUL_DIAGNOSTIC/1mCLOSEsyntheticquotes;settledDDне tick/intraminute/liveгарантия,историянеfreshOOS. ПримернаястараяценаилиfixedstateэкономиянеподменяютновыйTOTAL.
