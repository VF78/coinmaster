# Последний слот: единая registered R2 проверка — предложение

**PROPOSED / НЕ СОГЛАСОВАНО. Новых слотов нет.** Engineering3FAILED/max4, active0; один оставшийся слот сейчас заблокирован прежним требованием успешной отдельной API fixture. Prefix0/3. Нужен прямой ответ владельца на изменение последовательности и покрытия ниже; до него product patch/native запрещены.

## Установленная причина FAILED3

Actual partial TP0 .050 записал реальный `Order.position_id`, но `cache.position_id(TP0)` осталсяNone, TP0 отсутствовал в `orders_for_position`. Для NETTING и обычного order без execution algorithm это разные механизмы. Source exec engine возвращается без записи reduce-order в position-index; raw order получает position ID из Fill независимо. Следовательно, assertion о естественном cache self-link был неверным. Stock auto-resize перебирает именно index, а не raw field.

FAILED3/OS1 сохраняется. Это не API PASS и не доказательство stock UNSUPPORTED. Реальный debt/modify/queuedACK/standing этапы не достигнуты. Native BTC.950/SOLshort10 оставались открыты перед cleanup; пять компонентов действительно STOPPED→DISPOSED. Cause2656ea69... и независимое dispositionf2df7fbc... сохранены вместе с raw snapshots/trace/ledger. Старые FAILED1/2 неизменны.

## Явное новое разрешение, которое предлагается

1. **Разрешить isolated research product patch до полного отдельного API PASS.** Сохранить уже утверждённые queued standing TP правила (protocol7292a446.../ownerreceipt6998c5d7...), цены/начальные веса/initial+debt quantization, BTC core/R2 LEGACY_Q, SOL signals/cuts/rearm, cap и A0 original rights. Новый флаг defaultOFF. Никакого допуска к пилоту/production. Новые поля/контроллер только для existing native order lifecycle/audit/read-only native book authority; не создавать OMS/PnL engine или новый сервис.
2. **Объединить недостающий API proof с registered R2 integration в единственном physical4.** Он допускается по новому owner receipt после pure checks/independent review/freeze/rootGO, несмотря на FAILED3. Не называть FAILED3 успешным и не считать source-only анализ actual coverage. Если API или другой essential native gate в physical4 не достигнут/небезопасен — STOP, prefix не запускать. Retry/резерв/пятый engine не разрешаются.
3. **Заменить недостижимое auto-resize-positive условие проверкой реального registered route.** Зафиксировать NETTING, отсутствие explicit position_id/exec algorithm/parent links в обычных TP. Ownership подтверждать native OID/strategy/instrument/side и current intent-parent-generation; raw filled-order position ID проверять отдельно. Отсутствие cache association допустимо только в подтверждённом таком пути. Не создавать association вручную. Если фактический route/index неожиданно иной или quantity меняется непредусмотренно — STOP. Это изменение тестового критерия, не разрешение скрыть oversize/gap.

## Один engine, один registered strategy/account, два естественных parent

Использовать принятую причинную seed/source схему:729 завершённых daily bars, реальные source features/waves, actual daily inputs0/DAY, естественные LONG/SHORT; никакого reset strategy/domain/account. Данные25ч10мин≤48ч; config49ч10мин включает отдельный обязательный день стартового допуска. Native fees/cash/fills настоящие; funding в коротком synthetic fixture NOT_TESTED, не financial PASS.

Позиции и cap в registered сценарии берутся **только из настоящего R2 sizing и фактических fills/SOL reductions**. N752→593/standing159-434 остаётся точным engine-free regression vector, если такой N естественно не получен. Нельзя вручную установить .752 или qty ради совпадения с примером. На actual quantities требовать сохранения unconsumed standing entitlements после ordinary fill и доказать отсутствие повторной нормировки.

| Обязательный блок | Actual native evidence в physical4 |
|---|---|
| Нормальный lifecycle/API | Real stock margin, entries, native3TP ACK/current owners, ordinary partial TP, genuine nonmarketable BTC debt и same-OID queued modify. TotalQty=actualfilled+desiredleaves, latest-generation ACK, ноль unresolved protective commands до следующего matching; standing allocation exact на каждой потенциально исполнимой границе. |
| Debt guard | Current matching-native BBO/tick, marketable TP→DEFER/no debt submit/increases blocked; ordinary TP уменьшает actualheld, residual пересчитывается. При actualBTCflat новый debt не отправляется. Outstanding debt duration/quantity журналируются, не объявляются соблюдением cap/DD. |
| Remaining TP/audit | Real first/second target consumption и оставшийся TP3; consumed не восстанавливать. Partial/valid modify/expected native negative ModifyRejected; работающие старые ACK не считать новой quantity. Raw typed/generic UUID и TradeID применяются один раз; no reverse/extra cut/duplicate owners. |
| A0/cancel race | Second natural parent: original first IOC remainder не даёт новых прав; paired lock/riskOFF+60/cross/margin/current native pending barriers. Одна реальная переподача исходного second GTC, partial fill, ordinary TP→cancel, настоящий fill во время native PENDING_CANCEL, затем ACK и отсутствие новых fills/retry. Late increase/cap учитываются через actualheld, без refund закрытого BTC. |
| Конец | Real BTC/SOL flat/orders0/inflight0/zeroLiq, coherent audit/native truth, actual5STOPPED→DISPOSED. Cleanup не маскирует предыдущую ошибку. |

Предлагается одна **статическая публичная Native LatencyModel** для engineering: base0/insert0/update0/cancel2s, queueTrue. Не менять её, venue или account во время engine. Insert/update остаются нулевыми: normal debt dispatch→processing не допускает промежуточного BTC input/book; actual trace/source подтверждение обязательно. Delay только cancel позволяет настоящий pending-cancel A0 fill. Параметры должны быть проверены/заморожены до GO; неизвестная граница — STOP.

**Явное изменение покрытия:** positive late DEBT после flat не форсируется при insert0. Источники доказывают queue settlement до следующего input; вместо недостижимого fault-сценария требуются этот source proof и actual ordinary TP→flat→NO debt submit. Cancel-inflight проверяется фактически через cancel2s. Это не доказательство произвольного positive-insert-latency partial/nonflat cap invariant или live ACK safety; такие режимы остаются UNKNOWN и не получают допуска. Если единая actual карта не помещается/не подтверждается — STOP, не ослаблять её после результата.

## Реализация и допуски

Один source owner в canonical isolated VPS worktree; preserve user dirtiness/drafts/allfailed evidence. Один focused product+fixture pass, meaningful engine-free money/state/API/kwargs/JSON tests, независимый money/order review и максимум один consolidated correction. Затем committed source→immutable Mac, source/config/data/native/env pins, fresh namespace и rootGO ровно на один constructor. Все native attempts/setup/failures учитываются. До actualphysical4PASS нет economic GO.

После полного принятия physical4 остаются прежние **3 prefix**: fresh same-source OFF→C0_FIXED→A0_FIXED [2024-09-01,2025-01-15)UTC, seed10000/reserve0, default zero native transport, реальные frozen inputs `/inputs/data`, native fees/funding/settlement. Каждый Popen/failure считается; отдельный rootGO и actual loaders preflight. OFF parity20911.13611487; необъяснённое различие блокирует C0. Actual C0 financial PASS необходим перед A0.

Финансовые gates неизменны: cash/signed funding/settled+coherent event coverage/required TP/ownership/zeroLiq/terminalflat; TOTAL_A0>TOTAL_C0 и ΔTOTAL=TOTAL_A0−TOTAL_C0>2*max(0,fees_A0−fees_C0), DD≤50% и≤C0, dailyES20 всех136дней≤C0, actual additionalBTCfills. Global original70% intermediate/90% final net-profit floors не снижать; prefix не доказывает full/OOS/достижение цели.

Общий engineering **max4, потрачено3, разрешается только existing physical4 по новому порядку**, без добавочных слотов. Full/training/downloads/pilot/production/services/keys/externalorders/transfers0. Ранее разрешённая PUBLIC публикация research source/tests/reports сохраняется; push не deployment. Этот proposed текст не создаёт нового согласия.
