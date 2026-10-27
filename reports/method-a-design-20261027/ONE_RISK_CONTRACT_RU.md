# Один механизм: предварительный SOL-хедж с совместным стресс-бюджетом

27.10.2026. SPECIFICATION_ONLY / NOT_IMPLEMENTED / NO_RUN_AUTHORITY. Product a50af5433a0bbe00aecd6fec26e8d5c0321ced80 остаётся неизменным. Это итоговая интеграция одного executor draft и одного независимого design-review; draft сохранён как промежуточное доказательство, не действующий протокол.

## 1. Проверяемое изменение

Убрать правило active-risk `actualSOL>=k*actualBTC` и монотонный BTC cap, производный от оставшегося SOL. SOL TP **не создаёт BTC debt автоматически**. После actual fill остаётся тот BTC, который укладывается в совместный денежный риск и margin. Проданный BTC не восстанавливается; unfilled original-second право сохраняется только до исходного expiry и при повторном полном admission.

Это механизм сохранения BTC participation/compounding, а не доказанный новый доход SOL. C1 уже имел floor/cushion и halfcut, старые бюджеты — no-restore. Новизна здесь только в совокупности: joint actual-held market+basis stress, предварительный hedge до breach, отдельный execution envelope partial fills и отсутствие ratio-driven BTC exhaustion. Вариант, сведённый к прежнему selected-loser halfcut/ADDcap/fixedcoverage, отклоняется как повтор.

## 2. Снимок, данные и параметры

E — фактическая whole-account native cash+signed marked positions. H — непрерывный peak с начальным10000, включая отдельно сохранённые pre-fill/pre-open checkpoints; reset по parent/TP/riskOFF запрещён. C=E−0.5H. C<=0 — breach/close, не деление на ноль и не искусственное обнуление просадки. Старые paid fees/funding уже вE.

Один D1 statistical model: W=30 законченных paired daily simple returns (31 closes), последнее включённое завершение <=decision_day_start−1day. Все source/end/available timestamps известны как записи; для неизвестной реальной historical publication применяется объявленная модель end+60s, без утверждения о фактической задержке. Дневной lag остаётся и при наличии более свежих баров. Funding history — те же30 completeddays, обе ноги и все фактические начисления/интервалы. Gaps/отсутствующие signedrates =>UNKNOWN, неzero. Feature-only prehistory не участвует в денежных matching inputs.

beta=Cov(S,B)/Var(B), rho=Cov/(sigmaB*sigmaS), sigmaB/sigmaS вычисляются на одинаковых W/TF/endpoints. Для нового hedge нужны finite positive sigmas/beta. Residual epsilon_i=rS_i−beta*rB_i. Stress: b*=gamma*max|rB_i|, e*=gamma*max|epsilon_i|, gamma=1. Ω — четыре угла b=±b*, epsilon=±e*, rS=beta*b+epsilon; плюс zero shock для costs. Nonpositive scenario price =>INFEASIBLE. Горизонт24h соответствует D1, без sqrt-time пересчёта. Это набор observed-extreme stress scenarios, не confidence bound/гарантия futureDD.

Six potential search scalars, первая кампания использует ровно одну фиксированную точку, подбор0:

| Скаляр | Значение |
|---|---:|
| W |30days|
| gamma |1|
| u_on |0.70|
| u_off |0.50|
| adverse execution reserve на сторону |10bp|
| gross-benefit / roundtrip-cost hurdle |2|

Owner floor50%, medium fraction0.5vol — фиксированные требования. High threshold=(1+u_on)/2=0.85; high quantity=2×medium=1vol, без нового knob. Horizon24h, source clock/freshness и once-per-risk-episode — явно фиксированные части контракта, не скрытые параметры сетки. Изменение после результатов любой из этих величин — новый protocol decision, не harness repair.

Marks обеих ног age<=120s, submitquote<=60s; более строгий stock guard сохраняется. B2/F0 selection/boundary/expiry — существующая объявленная рыночная гипотеза, не новое oracle. В warmed feed available=t моделировалось отдельно; новый selection, использующий end=t H4, получает modelready=t+60s и order лишь на следующей quote после ready. BTCcore D1/entry clock этим не меняется. Funding effective/available трактуются отдельно от settlement. Реальная revision/publication history остаётся UNKNOWN.

## 3. Риск и расходы

Для BTC side s, модулей notional x=|QB|PB и opposite SOL y=|QS|PS: Gω=s*((x−beta*y)*b−y*epsilon). Foreign/другие held позиции входят со своим знаком; неизвестный owner не получает hedge-credit.

Gross stressed loss J=max(0,maxΩ(−Gω)). Kexit — worst future actual takerexitfee+10bp по scenario notional каждой ноги. Kfund — для каждой ноги max по историческим24h windows внутри W **суммы абсолютных rates**, умноженный на scenario notional. Будущий fundingcredit0; знак actual funding в бухгалтерии не подменяется этим reserve. Kentry prospective — takerentryfee+10bp на новую quantity. Already-paid расходы не резервируются повторно. BASE Bybit maker0.020%/taker0.055% и native fill classification неизменны;10bp — screening reserve, не добавленный к benchmark выдуманный fill expense.

Lheld=maxΩ(0,−Gω+Kexitω+Kfundω) для фактически held state. Native current margin/free/IM/MM и separate stress-margin mandatory. Scenario MM использует те же frozen Bybit profile tiers и `TierMarginPolicy` semantics из `research/native_fixture.py:350–398` (notional tier, deduction, selected40xBTC/20xSOL), не HL Sandbox policy. Чистый scenario evaluation не обновляет native account/marks. До native нужен zero-shock parity со current actual getters и актуальный pre-submit stock guard. Недоступный getter/MM не трактуется как0/PASS.

## 4. ДВА разных admission test

**Полезность полностью исполненного hedge.** На одной и той же actual BTC позиции сравнить gross J(x,0) с J(x,y_target). Требуется положительная разница >=2×conservative full roundtrip incrementalSOLcost (entry+exit execution/fees+funding). Это gross improvement против cost hurdle; cost не вычитается из improvement ещё раз. Полностью исполненная точка гипотетическая, не защитный кредит до fill.

**Безопасность маршрута исполнения.** Для actual opening leaves, PendingCancel до terminalACK, old/new modify liabilities и proposed new order построить множество всех достижимых partialfill states, включая0filled. Для каждого state и Ω проверить Lstate+ещё-не-оплаченный entrycost<=C и E_s>MM_s. Никакого net-credit до actualfill; zero-fill state сохраняет весь текущий риск. При двух opening owners BTC/SOL независимые partial quantities входят всеми комбинациями, не предполагается их одновременность. У одного OID/generation liability учитывается один раз по maximum old/new доlatestACK. Reduce-only outcomes и retiring latefills включаются с реальным clipping к held и с ownership.

Envelope — max по этим states; он не обязан и математически не может быть ниже Lheld, раз содержит zero-fill. Поэтому требование benefit<current применяется только к full-fill target, а envelope проверяется **на допустимость**, не на прибыльность. Independent standaloneSOL reserve не складывается поверх joint loss, если те же leaves уже включены в envelope. Если risk reduction потребует исполнения ещё не filledSOL, это не основание ждать при существующем breach.

Последующие actual fills заменяют contingent states в snapshot; фактические fees/funding входят вE, их прежний reserve снимается. Coherent peak/order of events сохраняется отдельно от post-fill snapshots. Если finite-state reduction/convexity endpoint shortcut не доказан по источнику и tier boundaries, прямой конечный lot enumeration обязателен; оптимистичный shortcut запрещён.

## 5. Risk bands, target и once-per-episode

При C>0 определить u=Lheld(x,0)/C. Это оценка BTC-only current risk, не actual loss и не future return.

- Нет действующего adverse selection либо u<=0.50: OFF, SOLincreases0. При существующемSOL закрытие выполняется только по допустимому intermediate route. Если unhedged final state unsafe, защита сохраняется до необходимого BTCtrim.
- При новом действующем selection и u>=0.70 начинается risk episode; 0.50<u<0.70 сохраняет предыдущее ON/OFF состояние. Для нового BTC parent начальноеOFF; при u>=on может сразуON.
- ON и u<0.85: MEDIUM, y50=0.5*x*sigmaB/sigmaS.
- ON и u>=0.85: HIGH, y100=x*sigmaB/sigmaS. На выборе новой entry допускается ровно эта величина; category не меняется по желаемому backtest результату. Если HIGH не проходит benefit/envelope/margin, искать «удобный» размер между ними нельзя: hedge denied, BTC risk policy остаётся.
- Existing hard breach Lactual>C: сначала recovery без новых increases. После actual reduce/fresh snapshot новая safe state может остаться ON, но не получает автоматический permission/hedgecredit. При C<=0 bands не вычисляются.

Вход не требует L(x,0)>C: это было бы недостижимо после mandatory trim и не давало бы открыть hedge до нарушения. Условия0.70/0.85 заранее оставляют headroom для costs/latency/partialfills.

В одном risk episode — одна SOL entry allocation. Partial fills одной исходной заявки не новые entries; запрет dobory/replenish сохраняется. HIGH/MEDIUM фиксируется при первой entry; смена u после fill не увеличивает её. SOL TP/STOP/invalidatedexit не дают reentry. Новый episode возможен после genuineOFF и нового laggedD1; увеличение требует ещё одного полного admission. Это явный hysteresis/cost control, не постоянная страховка с частыми re-add.

После SOLTP: пересчитать actual L и envelope. При SOL0 и допустимом BTC-only состоянии сохранить BTC. При breach — recovery. После ordinaryBTCreduce реальныйSOL приводится кcap y100(newBTC) с допуском<одногоSOLlot только при самостоятельном stressPASS после rounding. При BTCflat SOLtarget0, один existingSOL_CLOSE owner, no standalonealpha.

## 6. Сокращения тоже не атомарны

Safe target не доказывает safe execution path. Для planned reduce route применяется тот же envelope всех достижимых intermediate partialfills/working TP/STOP/late opening fills. В normal state все состояния должны оставаться допустимыми; если нет, нельзя послать обе ноги «пропорционально» и надеяться на одновременность.

При уже существующем breach zero-fill state сам недопустим. Вводится отдельная recovery branch: cancel increases с сохранением liabilities, сохранять positive TP/STOP, выбрать последовательность реальных reduce-only шагов без изменения стороны. Каждый шаг обязан не увеличивать worst deficit L−C относительно actual initial breach (с корректной заменой reserve/paidcost) во всём partialfill envelope и строго уменьшать deficit при полном исполнении шага. Среди допустимых шагов сначала минимизировать deficit, затем максимизировать remainingBTC, затем минимизировать turnover; deterministic tie по leg/order identity. После каждого actualfill — новый snapshot, без ratio-floor рекурсии. λ=0/flat может быть нормальным feasible endpoint, не ошибка сама по себе.

Если безопасную последовательность нельзя доказать, ownership/account UNKNOWN, reduction не исполняется либо превышен existing next-valid-quote/60s hard deadline: tradingNO_GO, increasesdisabled, существующий native conservative globalclose route. Его best-effort execution не объявляется гарантирующим DD; failure snapshots доcleanup сохраняются, даже если emergencyclose затем сталflat. Ожидание unfilled hedge и24hgrace запрещены. Тест expected-negative может подтвердить failclosed response, но не financialPASS.

## 7. TP/rights/release/lifecycle

BTC realTP policy задаётся матрицей P1: три initial actual positive targets, cumulativeactual-fill entitlement и сохранённый original split. Цена/лот/расходы positive, allocations conserve held, реальный tiny-partial failclosed. Нельзя resurrect проданные лоты. OldSOL policy разрешён только в диагностическихP0/P1; P3 использует свой real3TP/STOP по existing paired allocations/prices с frozen actual-entryATR, без изменения TP после результата.

Положительные SOLTP/STOP сохраняются при CAP/reduction до realflat; standard zero-right cancellation с retiring liability. Переиспользуется V2 soleSOL_CLOSE owner, immutable firstcancel+60s episode deadline, actual latefill/proportional conservation/dedup, benignCancelRejected только после genuine terminal proof. Latest accepted remaining rights и отсутствие необъяснённой protection gap проверяются на settled event boundary до следующего matching. Deadline не разрешает положительной позиции жить без защиты.

Original-second suspension — только risk admission override, не погашение original entitlement. Release требует knownOFF+60s, old order ACK/drain, liveparent, исходный expiry ещё впереди, неисполненный остаток известен, original price/TIF/fallback/quantity применимы, envelope+native marginPASS. Для exact E4 нельзя оживлять R2 limit спустя прежний4h expiry. Никакого возврата FIRST или уже закрытогоBTC. Оба native global dispatcher paths QUOTE/CACHE используют того жеSOLexitowner; foreign/pending/UNKNOWN blockers сохраняются.

## 8. Алгебраический witness и конкретные readiness gates

Непустота безопасной hedge области — необходимое условие до futurefreeze. Математический пример, **не новый исторический результат**: x35000, C5000, beta1, sigmaB/sigmaS0.95, b*=0.10,e*=0.01. BTC-only gross J3500, medium y16625 даёт gross J2003.75. При заданном reserve funding0.03%/24h и execution10bp/taker5.5bp full roundtrip SOLcost не более60.00, gross improvement1496.25>2cost. BTC-only J+exit/funding около3571.23<C и u≈0.714>on; full andzero partialfill endpoints safe при этих reserves. После всехSOLTP safeBTC0.5@70000 не обязан стать0.

Это constructive stress/cost witness, не sample-calibrated state, native marginPASS или tradePnL. FutureM8 обязан создать genuine registered orders/positions с фактическими account/tiers и одновременно доказать active selection, u>=on, currentL<C, full-fill benefit и весь partialfill/margin envelopePASS. Без такого actual witness native economic gate закрыт. Примеры неблагоприятного basis, отвергающего hedge, и hardbreach тоже mandatory; Ω не меняется после неудачи.

Readiness перед любым launch: exact raw/execution TP seam;31 laggedD1 closes+30days signed funding; accepted ready_at model; coherent prefillpeak и postfills; exact liabilities/generations; Bybit scenario-MM zero-shock parity и real current stockguard; original-second identity/expiry; всеcoverage-derived debt/cap callsites заменены последовательно; статические case recipes/hashes реально достижимы. Сейчас этих новых implementation/harness доказательств нет. Бюджет и future порядок — [ONE_EXECUTION_AND_EXPERIMENT_PROTOCOL_RU.md](ONE_EXECUTION_AND_EXPERIMENT_PROTOCOL_RU.md).
