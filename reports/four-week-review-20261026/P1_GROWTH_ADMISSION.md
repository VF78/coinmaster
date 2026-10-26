# P1b: капитал, участие BTC и допуск A0

26.10.2026. Read-only этап после P0_ROOT_ACCEPTANCE.json. **G1/A0 структурно CONDITIONAL; новый экономический опыт сейчас NO_GO. G2 — отдельный незавершённый риск-контракт, не часть исправления lifecycle.** Нет доказательства, что исправленный lifecycle с прежним C0 и одним A0 вернёт масштаб исходной прибыли. При этом сохранённые данные подтверждают реальный узкий механизм утраты second-child; объявлять A0 бесполезным также преждевременно.

Цели неизменны: исходный S0 TOTAL 6077107.23887483 при seed10000; промежуточный TOTAL≥4256975.067212381, финальный ≥5470396.514987347; settled и coherent event DD≤50%, zero model liquidation, полное native accounting. Ни один prefix, engineering PASS или scalar oracle эти цели не подтверждает. Старые бюджеты закрыты; предложенные в едином плане 6 fixtures/4 prefixes не утверждены.

## Что именно потеряно

| Причина | Сохранённое причинное свидетельство | Что исправляет G1/A0 | Чего из этого не следует |
|---|---|---|---|
| Удалён SOL-alpha при BTC flat | E4 SOL: 713702.32329125 fill-net ex-funding; 56.9167% held-времени приходится на BTC flat, held PnL этого времени 426629.8025. Первые пять циклов до03Jan дали +105055.25329125 ex-funding. E4/R1 имеют почти одинаковое нормализованное участие и mean fill-net bp80.673/80.680, но own q0 equity parent20 160437.86/25578.64. | Ничего: A0 разрешает только ещё не исполненный original BTC second-child, не standalone SOL. | Эти суммы не независимый causal вклад в поздний TOTAL; нельзя добавить их к новому native cash или сохранить старые BTC-размеры при меньшем собственном капитале. Источник раннего капитала строгим hedge не найден. [S1, S2] |
| Навсегда отменён ещё действующий BTC second-child после краткого риска | В старом R3 combined Oct12 F0 отменил .440 из original .880 BTC. SOL закрыт через85 минут без TP/debt; свои OFF/B2 позднее реально получили .434/.438@62413.6. У combined осталось только .440 для последующих TP. | Именно эту категорию: одна переподача original-price GTC после фактического risk OFF, при всех guards и native margin. | Это не возврат закрытого BTC, не обещание fill, прибыльности или достаточного охвата. Размеры и деньги сравниваемых own paths различны. [S3, S4] |
| Реально закрыт BTC при SOL TP | Oct25 actual SOL109 прошёл TP170.09/168.16/164.31; paired cuts .220/.220/.441 довели BTC .881 до flat в22:58. Свой combined parent12772.44618285→12251.88988464 закончился раньше, чем собственные OFF/B2 parents доOct29. | Ничего: consumed/закрытые количества и ordinary TP не возрождаются. | Разность с OFF/B2 16605.95022235/15995.20491341 не causal dollar-loss конкретного решения. Сохранить BTC после полного SOL TP при активном fixed coverage требует G2. [S3, S4] |
| Изменены core quantity/реальные TP/исполнение | R1 legacy BTC без SOL TOTAL304372.03; R2 real3TP/LEGACY_Q225919.51; R3 real3TP/CLEAN_Q120718.40. Все83 first-entry times/sides совпали. R2/R3:83 PLAN/P0 freezes; d3 совпал83/83; у16 parents нет фактического второго fill против1 E4/R1. Полный native730D warmup корректен. | Не меняет real3TP, first IOC, original second .5% post-only GTC, sizing-функцию или TP-цены. | Возврат всех16 вторых fills нельзя считать допустимым/прибыльным; они не равны четырём risk-cancel случаям. Не найден ни short-warmup, ни dynamic-VWAP bug существующего native core. [S1] |

Ни одна строка не получает invented counterfactual PnL. Разные own equity, размеры, exits и дальнейший compounding не дают разложить общий TOTAL gap на четыре аддитивных эффекта.

## G1: существование права доказано; охват результата — нет

Анализ actual prefix source7d513ca1 охватил16/16 B2/F0 activations:11 F0,5 B2;15 invalidations,8 SOL TP,4 first-TP. Четыре potential original second-child: Sep14, Oct10, Oct12, Nov16. Остальные события имеют отсутствие unfilled права, ordinary exit либо отсутствие actual risk OFF. Это ограниченное старое R3 combined universe, **не полный двухлетний universe и не измеренный R2 C0 universe source763d985**. [S4]

| Случай UTC | Original second remaining | Risk OFF+60: original post-only | Ограничение |
|---|---:|---|---|
| Sep14 | .488 BTC | BUY60207.5 пересекает ask59638.9 → WAIT | .243 BTC уже закрыто debt и не возвращается. Более поздний lawful quote до ordinary TP и native margin на нём не установлены. |
| Oct10 | .575 BTC | SELL60959.8, quote60799.3: noncrossing | Только структурная/clock/quote предпосылка; собственная prospective margin и будущий fill неизвестны. |
| Oct12 | .440 BTC | BUY62413.6, quote63139.0: noncrossing | Самый прямой observed growth override; исходные OFF/B2 fills не становятся fills A0. |
| Nov16 | .375 BTC | BUY90744.4, quote91297.6: noncrossing | Восстановление участия после ранней ямы; будущие fill/ordinary exit/cost неизвестны. |

Во всех четырёх actual cancel ACK до risk OFF известен; первый child исполнен полностью, ordinary BTC exit к +60 ещё нет. На +60 native prospective margin UNKNOWN: старый account snapshot относится к risk OFF и не содержит полного reservation/open-order state. Synthetic engineering instance7 доказал работоспособность штатного stale-DENY→fresh-mark admission и once-original GTC в fixture; это не market admission этих четырёх состояний. [S4, S5]

G1 требует отдельного economic budget S0_second=original total−original first allocation и remaining=S0_second−actual second-filled-ever. Partial FIRST не расширяет second. Native cancel history сохраняется; старый order не становится OPEN. Одна новая native попытка, original price/TIF, +60s, no ordinary TP/flat/pause/UNKNOWN ACK/inflight/debt, actual closed BTC cap не возвращается. Эти условия необходимы для честного теста **этого** механизма, но даже успешные fills не докажут прибыль или цель70/90. [S5]

**Первый ранний DD и recovery — разные задачи.** Original S0 worst decline: Sep11→Oct3. Из четырёх potentials только Sep14 находится до Oct3, и на первом разрешённом +60 quote он crossing. Три noncrossing случая находятся уже после Oct3 и не могут изменить ранее состоявшуюся просадку старого пути. Позднее законное исполнение Sep14 не исключено, но здесь не доказано. Нельзя обещать, что A0 исправит первый DD: восстановленный BTC способен также увеличить held risk. Oct10/Oct12/Nov16 относятся прежде всего к последующему участию и капитализации. Это хронологическое ограничение, не новый counterfactual equity path.

У нового R2 OFF prefix собственная DD50.130142814%, а не S0 DD66.2569%; C0 diagnostic DD47.4744% с TP FAIL. Смешивать эти кривые и ранние пики нельзя. Warmup-проблема Sep2 касалась prebenchmark SOL H4 ATR: настоящий repair уже сделан, но prior combined кSep30 и без него был выше своего OFF; persistent relative gap начинается сOct13. Поэтому warmup alone не объясняет последующую утрату роста. [S6, S7]

## G2: когда нужен новый контракт

Если при активном риске требуется actual hedge H≥kB, k>0, то при полном исполнении SOL TP и H→0 допустимое B также→0. Lifecycle repair сохраняет standing orders и честный ACK; он не меняет эту алгебру. A0 не возвращает cut BTC. Если владелец принимает полное paired закрытие как цену защиты, новый G2 логически не обязателен, но его рост/стоимость должны выиграть у простого BTC trim. Если требуется продолжать исходный BTC после SOL TP, **до кода нужен отдельный G2**: причинный risk OFF либо заранее ограниченный joint-stress/deficit/deadline/residual. Нельзя просто отменить debt или считать исчезнувшую защиту неактивным риском.

Сохранённые first-TP проверки дали market-stress prerequisites3 PASS/1 FAIL (Dec26); margin/непрерывный uncut candidate state UNKNOWN. Oct25 reconstructed481 quotes не дают risk OFF к ближайшему H4+60; expiryOFF позже deadline, owner реально flat22:58. Это прямой falsifier варианта «подождать одну H4 и сохранить BTC» в этом случае. Остальные PASS не являются DD guarantee. [S4]

G2 должен заранее определить: causal risk clock и его OFF; единицы notional и volatility adjustment; basis stress обеих фактических ног; actual filled coverage; finite unhedged deficit; native margin; pending/cancel/late fills; TP remaining rights; ordinary increases и rearm net edge after costs. Pending SOL/submit/ACK не даёт hedge credit. Unknown не равен risk0. Risk0→SOL target0 при strictly BTC-owned hedge; это приказ сократить фактический остаток с учётом pending/late fills, не обещание мгновенного flat. BTCflat не допускает standalone/excess SOL. Пока Ω/горизонт/cost/pending reserve/3TP совместно не определены, статус ARCHITECTURE_ONLY. [S8]

«50%» надо freeze до outcomes. При BTC notional x и SOL y, beta=Cov(SOL,BTC)/Var(BTC), market-factor residual пропорционален x−beta·y; half-vol owner y=.5x·σB/σS даёт factor coverage .5ρ, не50% DD. Min-variance h=ρσB/σS не равен inverse beta=h/ρ². Окно/порог здесь не выбирается. [S8, S9]

## Нужный контроль капитала и риска

| Контроль | Что сохраняется / отличается | Какой вывод разрешён |
|---|---|---|
| Fresh R2 OFF | Один frozen source, warmed inputs, real3TP/LEGACY_Q, BASE costs, native accounting; SOL off | Parity20911.13611487 ожидается только при заявленном lifecycle scope. Это prefix technical reference, не новый экономический winner. |
| BTC_TRIM | Тот же причинный risk clock и заранее объявленный factor target, actual BTC reductions/costs; own equity и cash; без будущих SOL fills как online данных | Честная альтернатива SOL: стоимость потерянного BTC upside, DD/ES и капитализация. Target, rearm и partial execution необходимо заморозить до запуска; если это невозможно, SOL-specific edge не заявляется. |
| C0_FIXED | Тот же R2 core плюс B2_F0 permanent lock и принятый lifecycle; unchanged TP/cuts/rearm | Только после полного engineering/TP/accounting PASS можно сравнить с OFF/TRIM. Old C0 diagnostic cash16046.38189782 не accepted candidate. |
| A0_FIXED | Только once-original-second release относительно C0_FIXED | Additional actual BTC fill обязателен; иначе NOT_TESTED. Рост versus C0, cost gate, DD/ES/ownership обязательны; не даёт автоматически SOL edge versus trim или70/90 full PASS. |
| G2 variant | Отдельная новая change/control, если согласован residual risk | Не включать скрыто в C0/A0 и не переносить старую C0 метрику/бюджет. |

Risk-matched trim нельзя построить из будущего actual SOL fill path. В протоколе следует заранее выбрать causal beta/vol sizing и reduction target на том же clock, а затем считать **собственные actual fills** каждой ветки. Синтетические costs и delays сохраняют одинаковые правила; не обещают одинаковый реализованный риск. При полном dominance TRIM по TOTAL/DD/ES SOL отклоняется; tradeoff показывается явно. Net SOL PnL сам по себе не hedge benefit.

R2 LEGACY_Q — текущий технический reference, не original S0 и не выбранный будущий winner. R2 full225919.51/DD66.8015%, R3 full120718.40/DD68.6034% — отдельные real3TP controls. Старый explicit-child S0 6482334.93 тоже другой admission model. Original absolute floors никогда не пересчитываются от этих меньших контролей. [S1, S6]

## Минимальный shortlist и falsifiers

1. **G1, once-original-child.** Поддержка: четыре старых potentials и один прямой Oct12 observed override. Дешёвое закрытие пробела: прицельная таблица exact R2 C0 decision snapshots, если уже сохранены, с original allocation, second-filled-ever, ordinary TP, known ACK, held/debt/cap, own stock margin inputs, quote +60 и последующим фактическим terminal. Без этих полей UNKNOWN; не восстанавливать их из будущего успешного fill и не читать массивы raw ради нового PnL. Falsifiers: нет новых admissible прав; только post-ordinary-TP/crossing/UNKNOWN; actual A0 fills0→NOT_TESTED; benefit не проходит frozen cost/DD/ES gate. Даже положительный локальный результат не закрывает утраченную SOL alpha или permanent cuts.
2. **G2, явный допустимый остаток риска.** Поддержка: fixed coverage исчерпывает BTC; Oct25 не успевает risk OFF. Дешёвое закрытие: один contract table active/OFF/TP/debt/deficit/infeasible/partial и доступность каждого causal input; сравнение с уже описанным C1/H_SOL. Falsifiers: pending hedge credit, future-known OFF, отсутствие finite risk deadline, excess SOL при BTCtrim, либо возвращение старого selected-loser half-cut/ADD cap под новым названием. До этого ни screen, ни economic variant не admitted.
3. **Капитал versus BTC trim — обязательный admission comparator.** Поддержка: #133 residual-continuation уступил equal-factor trim во всех12 объявленных cohort/slip/funding cells; #134 cached half overlay имеет малый fixed-return масштаб. Дешёвый шаг: freeze causal comparator и список измеряемых own-capital/participation checkpoints без угадывания требуемого раннего капитала в долларах. Falsifier: невозможна сопоставимость или SOL dominated. Не начинать новый parameter grid для обхода этого вопроса. [S2, S10]

**C1 lessons применимы к контракту, а не переносятся как готовая доходность.** Legacy C1 TOTAL4388613.38/retention72.17%/settled DD51.8032% не проходит. Девять cuts, три restore, шесть погашенных прав; cashflow restore385696.0245 до fees плюс intervention fees30498.04072762 уже включены в totals. Январский request2000SOL дал actual1000; восстановить можно только исполненное. В августе пять parent-rearms при одной продолжающейся global DD. Один общий rearm убрал бы и полезные, и вредные cuts; dollar benefit неизвестен. Первый октябрьский cut всё ещё оставил DD50.6142%, последующий restore не отменяет историческую просадку. C1 real3TP/coherent eventDD не аттестованы; перенос72.17% на strict hedge запрещён. [S11]

#133 scalar oracle с halved losers достигает только1037982.53 equivalent, zero-losers bookend7027879.02, #134 union oracle102.97% — future-knowing fixed-return конструкции. Это показатели трудности/покрытия в конкретной модели, **не upper bound любой будущей BTC/SOL стратегии**, не точный необходимый Jan15 капитал и не способ выбрать live sizing. Новых oracle, ROI, equity или required-capital долларов здесь не вычислялось. [S2, S10]

## Решение и следующий дешёвый шаг

**Сейчас A0 economic experiment NO_GO:** mandatory C0 native TP gate не прошёл, F4 integration не завершена, exact R2 economic opportunity coverage неизвестен, честный trim-control ещё не frozen, новый budget отсутствует. G1 остаётся CONDITIONAL для узкого incremental mechanism test после этих зависимостей; достаточность роста не установлена. Нельзя сделать его основной программой восстановления прибыли только потому, что fixture возможен.

Lifecycle fix имеет самостоятельный смысл как correctness requirement. Но **fix + unchanged C0 не поддержан как следующий автономный дорогой growth experiment**: он не возвращает BTCflat alpha, уже закрытый BTC или старую core economics. Его будущий свежий результат полезен как matched control только в принятом минимальном causal comparison с TRIM и условным A0. Если exact R2 таблица не покажет meaningful lawful additional-fill opportunities, A0 исключается; слот не превращается в новый вариант. Не требовать заранее доказанного70/90 от дешёвой таблицы, но и не подменять growth admission одним фактом существования order right.

Если требование включает сохранение BTC после полного SOL TP при всё ещё active risk, G2 должен быть выбран отдельно **до monetary implementation**, а не после ещё одной подгонки A0. Если принимается paired flat, сначала честно оценить его tradeoff против trim. Сейчас ни прибыль нового G2, ни прибыль fixed C0/A0 не доказана; economics A0 NOT_RUN. Старые закрытые слоты не используются.

Сделано: чтение заранее принятых registers/summary и узких decision/contract tables; новых native/engine/training/download/source/product/VPS/runtime действий0. Следующий разрешённый шаг — объединить P1b с P1a и принять один concrete design; всё новое денежное кодирование/physical budget требует отдельного owner protocol approval.

## Источники

- S1: `reports/new-system-plan-20261024/btc-participation-report.md`, `DECISION.md`; `reports/four-week-review-20261026/ECONOMIC_EVIDENCE.md`.
- S2: `reports/early-capital-hedge-20261024/DECISION.md`; исходная SOL attribution сводка также в `reports/four-week-review-20261026/RECENT_EVIDENCE.md`.
- S3: `reports/broad-hedge-discovery-20261024/lot-corridor-next-admission-memo.json`, только две cases/mechanism/parent таблицы и admission conclusion.
- S4: `reports/hedge-risk-contract-20261025/analysis/{RESULTS_RU.md,FOUR_CHILD_NOTE_RU.md,a0-four-case-clock-cap-addendum.md}`.
- S5: `reports/hedge-risk-contract-20261025/{A0_CONTRACT_PROPOSED_RU.md,A0_RESULTS_AND_DECISION_RU.md}`. Второй файл содержит промежуточный prefix status; актуальное закрытие берётся из S6, его старые permissions не применяются.
- S6: `reports/hedge-risk-contract-20261025/FINAL_RESULTS_AND_NEXT_PLAN_RU.md`; `reports/four-week-review-20261026/RECENT_EVIDENCE.md`.
- S7: `reports/four-week-review-20261026/RECENT_EVIDENCE.md`, lot-safe/warmup diagnosis; S3.
- S8: `reports/early-capital-hedge-20261024/growth-budget-admission.md`.
- S9: `reports/four-week-review-20261026/RECENT_EVIDENCE.md`, #135 causal math/control summary.
- S10: `reports/broad-hedge-discovery-20261024/scale-admission-report.md`; S2.
- S11: `reports/residual-recovery-20261023/REPORT.md`; `reports/four-week-review-20261026/ECONOMIC_EVIDENCE.md`.

Точные абсолютные пути, выводы и ограничения сохранены в P1_GROWTH_ADMISSION.json. Этот memo не дополняет старые ledgers и не меняет ACTIVE_TASK.

## Уточнение после actualR2 closure и независимого решения

P1_R2_COVERAGE_CHECK подтвердил на source763 настоящие четыре staticcancelcase с другими R2остатками .541/.405/.285/.418. A0flagOFF обходит проверки, поэтому пустой audit не доказывает нулевое покрытие. Старый R3mechanism screen выше сохраняется как ограниченный источник, а не подмена R2количеств.

Следующий boundedпорядок — OFF→C0_FIXED с независимым от tradingflag causalpredecisionrecord→TRIM→условныйA0, принятый в P1_DECISION_REVIEW. Не требуются заранее известные будущие fills/прибыль/counterfactualA0margin: actualadmission проверяется во время опыта на ownaccount. Структурные rights/доступные причинные guards и безопасный C0 обязательны; их отсутствие останавливает неиспользованные slots. C0control не получает заранее growthPASS. Это согласование дизайна, не новый code/native/budgetGO.
