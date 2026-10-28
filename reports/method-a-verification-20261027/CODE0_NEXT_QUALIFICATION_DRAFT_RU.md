# Единый следующий протокол: рыночная область SOL recovery и native-проверка

**Статус: PROPOSED_FOR_OWNER, 28.10.2026 20:06 Europe/Moscow. Нового разрешения на торговый код/native пока нет.** Пилот/production/deployment исключены. Этот документ заменяет промежуточный проект следующего шага, не старые утверждённые протоколы и не ledger.

## 1. Что уже конкретно готово

Published source **3f555d94cad009a0170b4c15230e18b84811c387**, parent b1807f1. Read-only codec теперь экспортирует persisted Features/OrderSide без изменения owner; два целевых engine-free теста PASS. BTC/SOL trading/risk bytes и денежный reader не менялись. Подготовлен исполняемый M3 harness, закрытый по умолчанию до нового owner receipt/root GO/canonical claim; exact DATA, universe, dynamic SECOND/SOL target и fresh boundary checks заморожены в [пакете](code0-native-preparation-20261028/PREPARATION_REPORT.json). Peer closure0P0/P1; первоначальные4P1 и их исправление сохранены. Это source-only readiness, не native PASS.

Две повторные SOL котировки заменены различными asks132.90/132.91, чтобы не повторить consumed-depth ошибку. Условный cash первого parent **6010.94888295**, не observed деньги; actual SECOND/target проверяются по native и исходным правам. Старые ROOT M3/M3R никогда не перезапускаются, FAILED не переименовываются.

## 2. Почему одного ещё одного малого fixture недостаточно

[Наблюдения старого квалифицированного P1](code0-native-preparation-20261028/OBSERVED_P1_DOMAIN_SCREEN.json): coherent marks дают максимальные held notionals BTC1108990.1088/SOL1140300; frozen first-tier caps300000/50000. Это старый legacy SOL/capital path, не контрфактический P3 и не доказательство будущей неудачи. Но текущий CODE0 допускает только первую tier и BTC-long/SOL-short, один уже исполнявшийся BTC TP и нулевые funding coefficients. Реальный producer вычисляет causal funding reserve из истории, а fixture использует нули. Применимость к реальному росту капитала не доказана.

Поэтому перед новым native предлагается **одно согласованное engine-free расширение доказанной области**, вместо последовательных разрешений на отдельные произвольные ограничения. Без него нельзя выдавать маленький synthetic PASS за готовность оптимизировать ROI.

## 3. Новый конкретный контракт: SOL-only pointwise recovery

[Условное доказательство](code0-native-preparation-20261028/POINTWISE_SOL_THEOREM.md), [машинный вердикт](code0-native-preparation-20261028/POINTWISE_SOL_THEOREM.json), [анализ существующего partitioner](code0-native-preparation-20261028/DOMAIN_GENERALIZATION_ANALYSIS.json).

Для любого одного и того же фактически реализованного старого BTC fill-vector x, включая его actual costs, обозначим F(x,z)=max_s(stress_loss_s−cushion) после нового SOL close объёма z. При фиксированном frame и доказанном affine upper bound всех дополнительных cash costs Gx(z) выпукла по z. Если полный SOL close SAFE для **всех** допустимых старых BTC partials/cost bounds, то

**F_actual(x,z) ≤ max(F_actual_old(x,0), 0).**

Каждый partial либо SAFE, либо не хуже того же old-path. Zero fill не получает relief. Не требуется доказывать достижимость общего максимума старого независимого envelope или считать его реальным неизбежным убытком. Старый scalar comparator можно оставить дополнительным gate, но он не заменяет этот proof. Полный native endpoint и actual деньги ещё НЕ проверены.

Full endpoint, положительный cushion и allpartial margin проверяются существующими `evaluate`, `tier_partition_envelope`, `prove_flat_route`; не пишем новый PnL движок. Первая tier не нужна математически: имеющийся partitioner уже включает cap/MM-zero/frontier cuts и соседние native lots. Это не утверждение, что текущий native adapter уже поддерживает эти области.

## 4. Что предлагается разрешить в одной реализации, native0

- Расширить **только SOL-recovery** на обе противоположные пары знаков, frozen Bybit tiers, несколько обычных native BTC LIMIT TP и известные finite nonnegative causal funding coefficients. BTC core, entry logic, normal admission, DD50, начальные TP prices/weights, reserve/fee параметры и source данных не менять.
- Все BTC TP: actual CID/parent/close side/ACK/generation, native leaves, aggregate leaves≤abs(actualBTC), без pending modifications/unknown ownership. Actual fills не relabel в maker. Допускается max(maker,taker) cost bound только после доказательства всех price/fee/PnL/equity rounding debit bounds. Не требовать искусственного первого maker fill каждого ещё не исполненного target, если валидный cash bound уже доказан.
- Вывести cost cap из точных установленных native Money/PnL/fee routines и минимального lot; покрыть **каждый** partial и разрешённые better prices. Одного fee ceil при LIMIT price недостаточно без monotonic tick proof. Не подбирать произвольный epsilon. Если полный bound не вмещается в прежний phi/price cap — DENY, а не расширение риска.
- Зеркально изменить close-side, dormant-price inequalities и partial/drain знаки с запретом crossing/reopen. Known old SOL TP/STOP должны быть dormant в текущем book и всём declared shock universe; иначе UNKNOWN/DENY. Старые BTC STOP и неизвестные/slippage-unbounded пути не добавляются.
- Новый BTC-close и shared-leg clipping не обобщать по SOL-теореме. Сохранить старую допустимую область BTC fallback либо fail closed вне неё. Ordinary BTC trim comparator не менять.
- Peak/marks/features/funding cash/source/owners/ACK/cost frame меняются — только fresh proof/reconciliation; никакого pending-fill credit. Неизвестное funding/неполные causal интервалы не заменять нулём. Feature funding reserve не является гарантией будущего платежа; actual signed funding и event DD проверяются отдельно.
- Одна узкая independent review и один релевантный connected acceptance pass, без повторения209/старых economic runs. Нужны captured regression, mirrored native Cache/account, несколько ещё не заполненных BTC TP, реальные profile tiers/границы/lot rounding и известный ненулевой funding, owner partial/terminal/ACK/deadline и отрицательные UNKNOWN случаи. Количество assertions не считается экономическим результатом. При NO_PROOF расширение не включать и native не запускать.

## 5. Native карта после успешного code/pure/review/freeze gate

**M3-CODE0 — ровно одна свежая попытка**, <=48h matching data, Nautilus1.231.0, public native API, cancel2s, новый UUID/source/config/data freeze. Подготовленный harness перепривязывается к принятому source; если код меняет достижимость событий — исправить до freeze, не расходуя engine. Нельзя вызвать старый launcher или helper-constructor.

M3 обязан проверить zero/partial/residual capped LIMIT IOC, actual native terminal/owned resize ACK и прежний deadline, весь исходный cap/healthy defer/retiringTP/multiple late fills/CancelRejected и объявленный в конце partialSTOP negative. Раннее failure не переименовывается в ожидаемый negative. Initial empty SOL handoff требует source-bound raw capture до первого native init и fresh BEFORE_NATIVE_MATCHING_INPUT того же quote/episode. Строки paired разрешаются только в namespace boundary, с physical row/hash; private exchange queues не объявляются публично видимыми. Sealed one-producer/complete-command closure требует independent root postrun проверки; UNKNOWN не превращается автоматически в PASS.

M3 проверяет **partial recovery**, полного CODE0 endpoint в нём нет: он уничтожил бы остаток для latefill gates. Полный held SOL recovery с actual SAFE endpoint становится обязательным gate уже выделенного M8, пока SOL ещё held, после safe/on/useful-partial фактов, до adverse-basis parent и flat. Точная M8 recipe пока feasibilityUNKNOWN; готовить её после M3 PASS, не строить весь pipeline заранее. Если совместимость исходных M8 gates не доказана, STOP до экономики, не helper-engine и не waiver. Это распределение покрытия, не замена полного endpoint математикой.

После M3 PASS → исходные M4 trim comparator, M5 band/release, M6 terminalQUOTE, M7 terminalCACHE, M8 reachability+fullSOL endpoint. Ни одна обязательная проверка не исключена. Старые M1/M2/P0R/P1 повторно не запускаются только при доказанной noninterference новых веток; иначе HOLD/отдельное решение без скрытого расхода.

## 6. Единый числовой бюджет, предложение

Canonical сейчас **9/18**, engineering6/11, prefix3/6, full0/1, active0/root_goFalse. Dedicated corrected M3 уже потрачен. Оставшиеся9 целиком распределены M4–M8×5 + P2/P4/P3 prefix×3 + fullP3×1. Новая попытка не помещается без изменения утверждённого распределения.

Предлагается **ровно +1: общий max19; engineering max12, prefix max6, full max1**. Все уже потраченные9, включая4FAILED, сохраняются; нового резерва нет. Остаток10: M3-CODE0×1, M4–M8×5, три prefix, один условный full. Это не бесконечный поиск и не разрешение на повтор ошибки. Ничего из cap19 сейчас не записано в ledger и не разрешено историческим code-only receipt.

Экономические prefix/full — только уже существующие условные gates, без их автоматической активации. Новый полный source-aware P2/P4/P3 financial adapter делать после успешной инженерии, сохраняя числовой reader/его точность. Freeze, source/universe/frame binding и actual OSexit/native accounting обязательны.

## 7. Результат и остановки

Сначала проверить механизм, затем сравнить P2/P4/P3 при actual expenses. Для P3 обязательны settled и coherent-event DD≤50%. P4 — диагностический comparator: DD>50 сам по себе не делает его невалидным. Для обоих обязательны zero liquidation, signed funding/native fees/cash/ownership/terminal quiescence. P3 должен пройти заранее объявленный prefix profit screen≥70% matched P0 net и Pareto gate относительно квалифицированного P4. Диагностические P0/P1/P2/P4 с DD>50 сами по себе не останавливают выполнение контролей. UNKNOWN/равный/неразрешённый tradeoff не даёт full GO.

FullP3 только после engineering+financial+comparison gates: original S0 seed10000/TOTAL6077107.23887483, intermediate70% TOTALfloor4256975.067212381, final90%5470396.514987347; обаDD≤50%, желательно30–50%. Никакого нового достигнутого ROI/DD пока нет. Если70%PASS, а90%FAIL, сохраняем промежуточный результат и отдельно планируем настройку; этот бюджет не разрешает скрытый второй full/подбор до победы.

При failure сохранить raw, receipts, exact source и ledger, без автореплея и без переписывания failed истории. Pilot/production/services/deploy/keys/externalorders/transfers/training/downloads — 0. Публикация research source/reports в ранее разрешённом VF78/coinmaster остаётся публикацией, не развёртыванием.
