# Held-portfolio cushion controller: узкий допуск архитектуры

2026-10-24; CM-EARLY-HEDGE-20261024. **ARCHITECTURE_ONLY / NO_SCREEN / NO_NATIVE_ADMISSION.** Можно сформулировать отличие от старых правил, но пока нет нового доказанного механизма прибыли или исполнимого контракта. На этом checkpoint исследование не расширяется. Oracle-alpha не используется ни как live parameter, ни как калибровка.

## Что уже было и не является новизной

| Прочитанная запись | Уже проверенный механизм | Отличие возможного нового контроллера |
|---|---|---|
| `residual-recovery-20261023/owner-contract.md`, `REPORT.md` (контракт observations/trigger/state/restore; итог и postmortem) | C1 уже имел whole-account native E/H, F=.50H и cushion; DD>=40%, выбранная наиболее убыточная нога с loss>C, один half-cut/один causal restore на genuine group. Actual cutfills/token, ограничения увеличений. TOTAL4.3886m/DD51.80%, rejected. | Не открытие cushion/floor. Отличие — совместный forward stress всех текущих обеих ног и actual pending, переменный допустимый остаток, отсутствие restoration token/one-cut-per-group лимита и отдельный strictly BTC-owned hedge. |
| `e4-budget-tp3-20261023/REPORT.md` (SOL recipe), `protocol-freeze.json` (SOL budget) | DD35%, F=.55H, D1ATR14, conservative BTC reserve **без hedge credit**; разовый trim доминирующего SOL до qcap; **уже без automatic restore**, unused original alpha adds возможны. TOTAL1.3601m/DD66.859%, rejected. | No-restore само по себе старое. Новое возможно только при совместном выборе BTC+SOL остатка с явным basis stress, а не cap наиболее опасного originalSOL. |
| `system-contract-repair-20261023/owner-final-SC03-SC04-CONTRACT.md` (H_SOL), `REPORT.md` (H_SOL section) | Каждый ADD: E−BTCreserve−held/pendingSOL stress−newADDcost>=.55H; reservations один раз, no trim/stop/restore. Held excess16случаев не исправлялся по определению. TOTAL3.9644m/DD65.6948%, rejected. | Контроль **уже удерживаемой** пары и реальное уменьшение BTC при недостатке cushion, а не только разрешение нового SOLADD. |

Значит переименование C1/H_SOL в CPPI или снятие restore — **STOP/REUSE**, не новая гипотеза. Только нижеследующий joint held-risk контракт имеет структурное отличие в этих прочитанных материалах; его стоимость/польза не установлены. Ранее упомянутый broader selected-leg controller в C1contract был rejected proposal, не отдельный доказанный тест joint-risk правила.

## Предлагаемая формула, пока без новых outcomes

На причинном согласованном native checkpoint после известных fills и обеих marks: E=current whole-portfolio cash+markedpositions, H=max прежнегоH,E), Hinitial=10000 без сброса по эпизоду. F=.5H, C=E−F; отрицательный C сохраняется как breach, не стирается max(0,..). Для допустимого бюджета использовать Cplus=max(C,0). Это risk floor, не виртуальная RESERVE и не гарантированная нижняя граница equity.

При фактически heldBTC: сторона s=+1long/−1short, x=abs(QB)*PB; oppositeSOL notional y=abs(QS)*PS. Causal positive beta=Cov(S,B)/Var(B), paired closed-bar sigmaB/sigmaS и rho; окно/TF еще не выбраны. Proposed owner target y_owner=.5*x*sigmaB/sigmaS, signSOL=−s. Factor coverage beta*y_owner/x=.5rho, не50%. Неположительные/неизвестные covariance/коэффициенты блокируют увеличение; существующий риск не объявляется нулевым. BTCflat⇒SOLtarget0, отмена всех SOL increases с учетом late actualfills; другая сторона/standaloneSOL не маскируется под hedge.

Пусть Ω_t — **еще не выбранный причинный набор совместных closed-bar shock scenarios**, каждый ω=(b,ε), где стресс BTCreturn=b, SOLreturn=beta*b+ε. Он обязан включать обе стороны marketmove, adverse residual/basis для обеих направлений, recovery после hedge и неблагоприятную задержку исполнения; нельзя просто поставить ε=0 или считать две marginal quantiles одним joint confidence bound. Signed paired PnL сценария:

`Gω(x,y)=s*((x−beta*y)*b−y*ε)`.

Предлагаемый monetary risk test:

`L_t(x,y)=max(0,max_{ω∈Ω_t}(−Gω(x,y)+Kω(x,y))) + R_t <= Cplus`.

Kω — еще не замороженный неотрицательный reserve будущих entry/exitfees, adverse execution/basis и signed funding downside на горизонте. Уже списанные native fees/funding входят вE и второй раз не вычитаются. R_t — conservative risk/cost известных opening leaves/unfinished parent и иных heldpositions, dedup по ownership/clientID; UNKNOWN_ACK/ownership не равен cancel или нулю. Имеющийся риск других ног нельзя исключить из whole-portfolio budget. Отдельный native margin admission обязателен; stress-budget не заменяет free margin/IM/MM.

OwnerSOL сначала **предлагается** лишь до y_owner, только при разрешенном pairedstress/admission. Новому target/submit/ACK защитного кредита нет: пересчет текущего L использует только realfilledSOL; unfilledincrease резервирует adverse risk/cost. При yactual после fills сначала проверить L(x,yactual). Если превышает Cplus, нужен совместный reduction target, например математически определить максимальный λ∈[0,1], удовлетворяющий `L(λ*x,λ*yactual)<=Cplus`; затем BTCtarget=λ*x и SOLtarget<=λ*yactual с ownercap для уменьшенного BTC. Это формула задания, **не разрешение solver/grid/экрану**; без специфицированных K/R/Ω корректное λ UNKNOWN. Если feasibleλ нет — explicitly INFEASIBLE, уменьшение/закрытие обеих фактических рисковых ног; никакого увеличенияSOL как «спасения».

Нельзя буквально ждать исполнения SOL, если текущий heldrisk уже не помещается в cushion: неполный/rejected/denied hedge не оправдывает сохранение опасного BTC. Очередность failclosed riskreduction и отмены increases должна получить контракт до любого действия. При partial BTCtrim SOLcap уменьшается по фактическому остаточному BTC; paired reductions не атомарны, gap/latefills сохраняются. Auto restore/readd с улучшениемC не разрешается: проданные/погашенные права не возрождаются, C/H не reset. Новые обычные BTCentries — отдельное нерешенное решение, а не скрытая restoration.

## Критические решения до любого следующего допуска

1. **Ω/горизонт/наблюдение:** один causal closedbar TF/lookback, horizon через реальные funding/latency, совместная tail/basis конструкция, coherent prefill/preopen equity/mark sequencing. FixedATRstress не является hard bound. Нет данных — UNKNOWN, не подстановка оптимистичного shock.
2. **Что заменяет:** strictly BTC-ownedSOL вместо standalone alpha; чей actual3TP контракт остается для обеих ног. Каждое SOLTP/SL должно пересчитать pairedrisk/hedgedeficit и при необходимости уменьшить BTC, без automatic SOLreadd. BTCTP соответственно сокращаетSOL. Risktrim не зарабатывает новые TP/SOLrights; latefills/cancel/partial/infeasible states должны сохранять lot conservation и обычные/mandatory priorities. Их thresholds/allocations здесь не придуманы.
3. **Капитал и экономика:** native cost/margin/queue/size; допустимая минимальная BTCparticipation и потерянный BTCupside; правила запрета/возобновления обычных increases. Для будущего отдельного допуска нужен заранее выбранный equal-factorBTCtrim comparator со всеми costs, hedge failures и lostupside. Даже надежное сокращение риска не создает раннюю positivecashflow автоматически и может повторить утрату winners/compounding.

## Один первичный источник и предел чтения

Black & Perold, *Theory of constant proportion portfolio insurance*, JEDC16(3–4),1992,403–426, DOI10.1016/0165-1889(92)90043-E: [издатель](https://www.sciencedirect.com/science/article/pii/016518899290043E). Прочитана только индексированная первичная аннотация; открытие fulltext403, полный paper/формальные допущения не прочитаны. Аннотация определяет risk exposure как constant multiple wealthabovefloor и рассматривает costs/borrowing constraints; не подтверждает наши shocks, SOLpair, multiplier или DD50.

Здесь CPPI/TIPP-like — лишь сходство riskbudget с cushion. SOLperpetual не cash/riskfreeasset: встречная нога сохраняет basis/funding/margin/liquidation risk. Из наших discrete closedbar решений, jumps, latency и partialfills следует gaprisk: F может быть пробит до следующего решения/исполнения. Утверждений о доказанной гарантии исходной статьи не делается. Самоназвание CPPI не превращает conditional stressed budget в hard drawdown floor.

## Решение checkpoint

**Новая архитектурная разница сформулирована условно, новый trading admission отсутствует.** Whole-accountfloor/no-restore были раньше; единственный возможный новый узел — joint actual-heldportfolio stress с basis обоих плеч, executedhedgecredit и paired BTC+SOL riskreduction без нового alpha/readd. Пока Ω/cost/actual3TP/ownership/infeasibleконтракт не определены, следующий screen/native/result не допускается. Если при детализации останется selectedloserhalfcut либо originalSOLADD/cap — STOP/REUSE старой семьи. Source/product/runtime/Project/sharedstate/commit не менялись; все budgets0, новых outcomes/движков нет.
