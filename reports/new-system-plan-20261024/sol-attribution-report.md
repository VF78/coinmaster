# Старый SOL E4: наблюдаемая атрибуция без нового движка

**Работа начата и завершён первый фактический шаг: старый E4 SOL не соответствует строгому хеджу фактически открытого BTC.** Более половины времени SOL удерживался при BTCflat; эти интервалы дали положительный наблюдаемый price PnL. Удаление такого SOL меняет последующий капитал BTC, поэтому ниже нет выдуманного counterfactual TOTAL или обещания сохранить его доходность чистым хеджем.

Протокол `sol-attribution-protocol.json` зафиксирован до расчёта. Выполнены один saved-data analysis pass и одна отдельная проверка файловой бухгалтерии; оба PASS. Новых native/simulator/training запусков0, product/runtime/VPS/Project/commit/push действий0. Сохранённые exports не изменялись.

## Данные и метод

Использован только E4 receipt `reports/b-50-90-next-20261023/owner-E4-receipt.json`, его локальный raw native JSON и пять проверенных экспортов fills/orders/fill-audit/order-events/split-parent-audit. SHA256 raw и всех пяти экспортов совпали с receipt. Из535 native fills198 относятся к SOL; у всех535 уникальный client_order_id, каждый соответствует одному native actual fill-audit record, actual qty/price/USDTcommission и native order/event.169 CANCELED orders с actual partial fills сохранены как реальные fills, не потеряны.

Получены25 SOL циклов flat→position→flat,1051200 синхронных минутных BTC/SOL markclose. Parquet читается последовательно пачками16384, миллион строк в контекст не загружался. Markclose доступен только в `open_time+1minute`. Actual quantities до текущих fills умножаются на изменение mark, далее actual fill basis `signedQty*(mark-fillPrice)`; это разложение наблюдаемого cashflow, а не симуляция новых сделок.

Primary beta — сохранённый `planref_v1_beta` последнего однозначно связанного BTCparent, frozen раньше первого SOLfill. В25/25 случаях SOLcycle закончился до следующего BTCparent. В pinned source `bd04c9b...` beta270D определяется как `Cov(logSOLreturn,logBTCreturn)/Var(logBTCreturn)` по завершённым D1; sourcehash domain/strategy совпал с raw report. Domain создаёт новый episode только после native both-flat reconciliation. Fill export не содержит durable episode_id: связь опирается на проверенный lifecycle и непересекающиеся parent intervals, это ограничение сохранено. Beta здесь фиксируется на parent, не выдаётся за более позднюю activation-beta самого SOLsignal.

Secondary beta720H1 рассчитан отдельно по720 завершённым простым H1returns строго до первого SOLfill. Во всех25 случаях доступна полная721close история; самый ранний SOLcycle стартует03Oct2024, после накопления720H1. При недостатке истории результат был бы UNKNOWN; подстановок или будущих bars нет.

Формула factor на минутном интервале: `qSOL*SOLmark_prev*beta*(BTCmark/BTCmark_prev−1)`. Residual = observed held price PnL−factor. Primary log-beta применяется к простым minute returns как описательная линейная экспозиция; это не гарантия ортогонального residual и не причинная/торгуемая alpha. Raw mark precision отдельно от native instrument rounding; execution basis включает эту разницу.

## Полная денежная сверка

| Наблюдаемый компонент | USDT |
|---|---:|
| SOL held price PnL |732738.14750000|
| BTC factor, frozen270D beta |376562.11175364|
| SOL residual, та же beta |356176.03574636|
| Execution/mark basis |−1616.89250000|
| Actual native SOL fees |−17418.93170875|
| **SOL fill-net ex-funding** |**713702.32329125**|

Для всех25 полных flat cycles `held+executionbasis=actual flat fillcash` с **точным residual0**; `factor+residual+exec−fees=fillnet` проверен. На secondary720H1 factor415455.14958331, residual317282.99791669; total fill-net тот же. Зависимость распределения factor/residual от разумного causal beta не меняет actual money.

Signed старый perasset funding **UNKNOWN**; не распределён между монетами/циклами и не подменён cash bridge. Это SOL fill-net, не вся прибыль portfolio. E4 TOTAL5631617.35953723 остаётся отдельным ранее принятым native результатом.

## По годам и ранний капитал

Границы: первый год `[2024-09-01,2025-09-01)`, второй `[2025-09-01,2026-09-01)`. Показаны и mark-calendar attribution, и полные циклы по entry cohort. В этом наборе25 SOLcycles не пересекают границу лет, поэтому итоговые суммы обеих разбивок совпадают; это не общее правило для будущего расчёта.

| SOL entry cohort | Cycles | Factor270 | Residual270 | Exec basis | Fees | Actual fill-net |
|---|---:|---:|---:|---:|---:|---:|
| Первый год |20|202371.37|109315.78|−205.89|10005.34|301475.92|
| Второй год |5|174190.75|246860.25|−1411.00|7413.59|412226.41|

Ранние actual SOL cash contributions существовали до последующего BTC compounding:03–05Oct2024 +3214.10;11–12Oct +6373.54;22–26Nov +26439.54;23–25Dec +19657.71;31Dec–03Jan2025 +49370.36 USDT fill-net. Первые пять вместе **105055.25329125USDT** ex-funding. Это реальный приток fillcash по сохранённой траектории. Насколько изменился бы поздний BTC при другом hedge cap, **не идентифицировано**: его qty/admission должны пересчитаться в собственном native equity, нельзя просто вычесть эти доллары из конечного TOTAL.

## Где старый прибыльный SOL несовместим со строгим хеджем

| Предынтервальное фактическое состояние | SOL-active minutes | Held price PnL | Exec/fees, только однозначное состояние | Allocated observed net |
|---|---:|---:|---:|---:|
| BTCflat |110777|426629.8025|−8480.447705|418149.354795|
| BTC/SOL противоположны |83853|306108.3450|−4753.75398175|301354.59101825|
| BTC/SOL одинакового знака |0|0|0|0|
| BTCfill в тот же timestamp: ordering UNKNOWN |не отдельный held interval|0|−5801.622522|−5801.622522|

SOL был активен194630minute intervals; **56.9167%** из них BTCflat. В этих интервалах уже нет BTCриска, который SOL мог бы компенсировать: при строгом правиле `BTCflat⇒SOLflat` такое удержание запрещено. Наблюдаемые +426629.80 held PnL и +418149.35 после однозначных costs объясняют конфликт цели доходности с purehedge ограничением, но **не равны прибыли, которую можно просто удалить без изменения остальных действий и compounding**.

Cycle activation отдельно квалифицирован по native exports:9 заведомо стартовали при BTCflat,3 при heldBTC,13 имеют BTCfill в тот же timestamp и оставлены **UNKNOWN_TIMESTAMP_TIE**. Старое краткое утверждение13/25 BTCflat-start здесь не воспроизводится без предположения о callback ordering; оно не используется как проверенный новый вывод. Все held interval BTCflat значения выше не требуют выбора intratimestamp очередности.

Дополнительная описательная cap-проверка использует frozen primary beta и actual текущий BTC notional. Full-factor cap=`NB/beta`, half-factor cap=`0.5*NB/beta`; same-side/flat cap0. Это **не half-MV cap** и не новое правило торговли. Пропорциональная часть наблюдаемого held PnL на excess inventory:

- За full-factor100% cap:128057 SOL-active минут, включая17280 oppositeBTC минут сверх cap; excess held PnL746398.80 USDT.
- За half-factor50% cap:134084 минут, включая23307 oppositeBTC минут; excess held PnL770184.25 USDT.

Эти суммы могут быть больше всего held PnL732738.15: оставшаяся, меньшая часть inventory на соответствующих интервалах имела совокупный убыток. Это аддитивное распределение наблюдаемого PnL по quantity, **не достижимая прибыль/экономия от cap**, fees/exec/funding туда не распределялись. Calendar/state детали сохранены в CSV.

## Что доказано и что остаётся неизвестным

Доказаны реальный SOL fillcash/fees, связанное causal beta разложение, минутная фактическая BTCflat экспозиция и несовместимость значительной прибыльной части старого SOL с требованием строгого хеджа. Residual не назван alpha; B5/H5 не реализован и новый risk gate не выбран. S0 заново не анализировался: этот шаг использует исходный verified E4, не смешивает controls и не расходует full бюджет.

Неизвестны: signed asset funding старого run, полная intratimestamp native mark/fill очередность, counterfactual стоимость запрета BTCflat/excessSOL и её влияние на поздний BTC капитал, прибыльность новой causal hedge strategy и достижимость70/90profit floors. Для нового native опыта по-прежнему нужна отдельная поддержанная гипотеза и явно открытый budget; данный расчёт такой GO не выдаёт.

Артефакты: `sol-attribution-calculate.py`, `sol-attribution-verify.py`, frozen protocol JSON, `sol-attribution-cycles.csv`, `sol-attribution-summary.csv`, `sol-attribution-entry-cohorts.csv`, `sol-attribution-cycle-start-states.csv`, result/verification JSON. Проверка сохраняет input/source hashes; source exports и engine не изменены.
