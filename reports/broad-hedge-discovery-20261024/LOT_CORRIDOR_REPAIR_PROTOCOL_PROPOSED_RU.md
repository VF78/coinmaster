# Предложение: лотово-устойчивый парный выход

Статус PROPOSED_ONLY: нового разрешения этим документом не создаётся. Основание — фактический B2 и доказательство approved5-grid-recursion-review.md; base source3323f08c57ede411058f93d96acee88928c93481. Цели S0/70%/90%/DD50 и исходные экономические гейты не меняются.

## Одна денежная коррекция

Сохранить замороженное отношение k, BTC coverage floor и фактическую native-позицию. Верхний SOL cap при BTC-сокращении округлять **вверх до SOL-лота**: ceil_SOL(k×Bmax), вместо floor_SOL. Возможный излишек строго меньше одного SOL-лота; на фактическом инструменте <0.1SOL. Это явное изменение предыдущего строгого SOL cap, которое требуется утвердить.

Все cap-вычисления обязательны в точных целых native-лотах: u=intended_SOL_lots, v=Qref_BTC_lots, оба замораживаются при выборе активации. CoverageBTC=floor(v×actual_SOL_lots/u), SOLcap=ceil(u×BmaxLots/v). Использовать целочисленные деления; Decimal k остаётся только отображением отношения, не входом floor/ceil. Получать лоты из actual native Quantity/size_increment точно, без float; неподдержанный нецелый остаток — UNKNOWN/fail-close. Это сохраняет исходное математическое отношение и устраняет вычислительную погрешность на границе общей решётки.

Коридор r×b ≤ s ≤ ceil(r×b), r=u/v, b=BmaxLots, s=actual_SOL_lots — целевое устойчивое состояние **после подтверждённого исполнения** native-обязательств и выравнивания actualBTC с ceiling. Он не доказывает текущее покрытие по одному рассчитанному cap. Пока actualBTC>Bmax, остаётся BTC-debt; пока actualSOL>SOLcap, остаётся SOL-excess. Поданные/ожидающие ордера не дают исполненного покрытия или снятия риска. Сохраняются исходные cancel/ACK/recompute actual leaves, часы долга, регистрация непокрытого интервала и NO_GO при просрочке/неизвестности. Промежуточное состояние не подменяется виртуальными позициями.

SOL никогда не добирается ради коридора: действие только уменьшает уже фактически имеющийся SOL, когда он выше cap. Начальный intended SOL, HALF_VOL, signal-time Qref/k и floor-entry sizing остаются прежними. BTC credit не округляется вверх. Реальные late/oversize fills, опускающие SOL ниже покрытия, по-прежнему создают BTC-debt; запрещено игнорировать все BTC_CAUSED события. Повторные callback/fill IDs обрабатываются идемпотентно. P0/k не переякориваются, BTC ceiling только уменьшается, отменённые доборы не восстанавливаются.

Actual пример: после первого TP136.3SOL → BTC0.777; новый SOL cap136.2 даёт BTC coverage floor0.777 и не создаёт нового долга. Если реальный late/oversize fill уменьшит SOL до136.1, долг BTC0.001 настоящий: BTC→0.776, SOL cap136.0, затем устойчивый коридор. При BTC0 SOL cap0. Dust/min-notional/невозможность защитных allocations требуют native fail-close и NO_GO; запрещены виртуальные остатки и скрытая неподдержанная экспозиция.

Сохраняются реальные initial3TP и только неисполненные права после fills, IOC-stop, actual VWAP, cancel/ACK barrier, next-distinct-quote/60s debt clock, UNKNOWN fail-close, causal B2/F0/сроки/порядок событий, все BTC entry/wave/E4 правила, комиссии/funding/liquidity/benchmark/warmup. Ни новых сигналов, ни подбора параметров в этом ремонте.

## Реализация и acceptance перед native-префиксом

Один GPT6.1Sol/medium исполнитель, isolated canonical VPS worktree от3323; default OFF/publication уже разрешена отдельно, без deployment. Mac только новые committed frozen copies. Не менять running pilot/production/сервисы/ключи/ордера/переводы.

Один focused pass и один полный релевантный connected test pass; узкое независимое money/orders review конкретной дельты. Native fixtures должны воспроизвести actual1.037BTC/181.7SOL в обоих направлениях: после одного TP без новых независимых выходов выполняется одно BTC-trim обязательство и не более одного корректирующего SOL-cap обязательства, затем долг не возобновляется. Частичные native-fills внутри такого обязательства не считаются новым независимым долгом. Проверить commensurate и coprime lot grids, точные общие границы, настоящие oversize/late/duplicate/partial/stop fills, cancel/ACK, исходный partial entry, BTC-flat/terminal, dust/min-notional и consumed TP rights. Полный native cash/funding/domain/order/fill trace проверяется; observer ON/OFF parity остаётся обязательной. Сохраняются все исходные failures и прежние деньги/допуски. JSON-roundtrip, календарь и funding-watermark regression обязательны. Чистая целочисленная проверка25088 состояний уже PASS, но не заменяет native fixture.

Перед каждым физическим запуском — source/config/data/engine/fees/feed freeze, источник явного owner approval, актуальный ledger и root GO. Учитывать каждый неудачный старт/экспорт/повтор. Никакого автоматического рестарта или объявления failed output победителем.

## Конкретное изменение бюджета

Предложение: утвердить эту реализацию и **три свежих prefix-прогона**, подняв общий накопленный предел с5 до7 (+2). Уже использовано4; текущая неиспользованная попытка старого source переназначается на исправленный matched OFF только после явного разрешения. Новая последовательность physical5OFF → physical6B2 → physical7combinedB2/F0, одна версия source/параметров, новые namespaces/journals. Все прежние4 записи остаются, новые logicalIDs уникальны; лимит считается по физическим попыткам. Резерв0, full0, обучение/параметрическая сетка не разрешаются.

Новый source guard допускает только согласованный cap7 с hash-pinned owner amendment/root GO и неизменённым full0; до разрешения live ledger остаётся max5/spent4/HOLD. Старая оставшаяся попытка не даёт разрешения на денежный source change.

## Неизменные экономические и stop-гейты

Исправленный OFF должен пройти все native accounting/funding/coverage/terminal проверки и прозрачное сравнение с архивом. Затем B2 — атрибуция, combined — единственный primary. Известный общий contract/accounting/coverage дефект останавливает следующие пробы; один экономический проигрыш B2 не подменяет primary и не выбирает другой вариант постфактум.

Для qualified prefix нужны ВСЕ исходные гейты: combinedTOTAL≥2×matchedOFF; incrementalnet>2×nativeSOL+pairedtrimfees; settledDD≤50% и улучшение≥5п.п.; coherenteventDD≤50%; полный native audit без liquidation/stranded/pending debt; daily и nonoverlap-parent ES20 не хуже на общем календаре; ≥3 валидные завершённые активации с TP и nonTP путями. Определение ES20 из approved5-risk-metric-contract.json сохраняется. Missing/UNKNOWN не PASS. No parameter retune/extra window/alternate B2 winner; после отказа combined — STOP этой проверки.

Исправление может ухудшить наблюдавшуюся DD44%, поскольку непредусмотренное закрытие BTC прекратится. ROI после ремонта неизвестен. Даже successful prefix не доказывает ≥70%/≥90% прибыли на двухлетнем периоде; full требует отдельного нового разрешения. Source/math proof не обещает финансового результата.
