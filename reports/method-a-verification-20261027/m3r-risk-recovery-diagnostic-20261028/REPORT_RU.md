# M3R: почему отсутствует доказанное post-fill recovery

M3R `acd8fedd-0842-48a7-9df2-b8414bba3fb8`, source `b03dacc`, остаётся FAILED/OS1. Причина — настоящая несовместимость HEALTHY_DEFER с действующим risk-контрактом, а не задержка ACK. Доказательств ошибки исходника нет. Диагностика использует только сохранённые raw, существующую чистую `evaluate` и формулы frozen solver; native imports/движки/тесты/изменения продукта — 0. Dedicated corrected M3 slot исчерпан, ledger9/18.

## Нативное состояние и первичная ветвь

В69s: BTC200/SOL−132.9, cash8665.0833025, equity5722.6733025, peak10000, C722.6733025. Все3SOL TP33.2/33.2/66.5 и STOP132.9 ACCEPTED, latest ACK, pending modifyFalse; paired physical68 PROTECTED/exactTrue.

В70s BTC TP CID4 исполнил199@105.2, maker fee4.18696000 (risk physical97). MarkBTC107/SOL132.9 не изменился. После fill: BTC1/SOL−132.9, cash9725.5463425, equity5360.2863425, C=equity−peak/2=360.2863425 (risk95). Cash вырос1060.46304, но BTC UPNL сократился1422.85. Наблюдаемая потеря equity/C362.38696 точно равна199×(107−105.2)+fee4.18696. Это сверка фактического fill/cash, не предположение о другом исполнении.

Frozen W30 shock max: b=0.015672393400768784539637486; SOLshock=0.020706466960239101751224802431758257274549381414800504; funding0. `evaluate` даёт L392.161223244869925624426..., L−C31.874880744869925624426...>0. Gross stress loss364.0491630093; остальное — exit fee+reserve. Все5 IM/MM сценариев проходят; минимальные slacks4092.11345/4905.73787. При69s L93.0880735215 и L−C−629.5852289785. Значит отказ вызван stress-deficit, не нехваткой текущей margin и не CUSHION_BREACH.

## Ограничение, отвергающее любую величину

`_mr_after_actual`645–666 входит в recovery при L−C>0; `_pair_cancel_btc_increases` отменяет лишь BTC_ENTRY, оставляя reduce-only BTC TP. До NO_GO незавершённый BTC CID4 имеет leaves1; остальные открытия уже terminal. SOL protections остаются текущими liabilities; pending cancel появляется только вследствие `_mr_fail` после отказа. BTC/SOL lot=.001/.1, native min quantity/notional отсутствуют. Геометрически legal BTC d=[1,999]∪{1000} lots, SOL d=[1,1329].

**BTC:** снятие остаточного long уменьшает единственный противовес shortSOL. Для любого d>0 full-step objective при неизменном SOL растёт относительно initial deficit на `d×.001×107×b×(1−.00155)`; это0.00167434682743674244 на lot. Strict improvement (`objective<initial_deficit`) невозможно; всё legal BTC множество отвергнуто.

**SOL:** source route требует nonworsening для ВСЕХ partial outcomes. Для каждого d допустим исход: новый SOL trim ещё0fill, SOL остаётся132.9, зато уже стоящий BTC TP исполнил оставшийся1BTC. Этот outcome входит в source qlines (`qSOL=h`) и other.points (`qBTC=0`). Консервативный unpaid costBTC=.16585. При нём L−C=33.549227572306668067251..., что выше initial31.874880744869925624426... на1.674346827436742442825.... Неравенство `route_deficit−initial_deficit<=0` нарушено независимо от d. Поэтому feasible SOL intervals также пусты, даже если конечный SOL trim сам по себе уменьшил бы риск. Pending trim не получает кредит до fill.

Quotes не объясняют этот запрет: SOLcache69s подтверждён paired75, BTC последнее допустимое quote68–70s; оба моложе60s. Точный pointer BTC cached quote внутри solver не экспортирован, но доступная история исключает age breach. После70 native bookBTC107/depth199 уже потреблён fill199; solver не использует оставшуюся depth для этой ветви. Конкретные внутренние interval traces не экспортированы: выше восстановлена достаточная причина пустоты по исходному ограничению, а не заявлена новая runtime-телеметрия.

## Вывод и единственное предложение

Сначала возникает risk96 NO_PROVEN_POSTFILL_RECOVERY, затем forced close переводит4SOL protections в PENDING_CANCEL/FAULT_UNPROTECTED, и только потом HEALTHY_DEFER assertion падает. Guard корректно не обещает безопасное восстановление; это не доказывает невозможность любой иной политики. Текущее физическое DD≈46.3971% не отменяет stress-нарушение.

**Единственное PROPOSAL ONLY — новая семантика baseline восстановления:** сравнивать partial outcomes нового SOL reduction с максимумом deficit по УЖЕ стоящим неизбежным BTC TP fill paths, включая известные native TP prices/fees. Сейчас initial baseline использует BTC1, а проверка candidate включает BTC0; поэтому старый BTC TP даёт всем новым управлениям одинаковый отрицательный witness. Это предложение нового risk-контракта для будущего согласования, не разрешение исправлять код и не доказанная ошибка нынешнего guard.

Для иллюстрации только risk-corner алгебры: оставшийся BTC1@105.2 при mark107 и maker.00020 имеет стоимость относительно mark1.82104. В углу BTC0/SOL−132.9 получаются E5358.4653025, C358.4653025, L393.669720072306668067..., baseline deficit35.204417572306668067.... Это не наблюдавшаяся сделка/касса. Полное SOL reduction132.9 по текущему ask132.9 с консервативной fee+reserve.00155 стоит27.3767355; для угла BTC0/SOL0: E5331.088567, C331.088567, L0, deficit−331.088567. Значит безопасный конечный угол алгебраически существует; он не доказывает допуск всех partial routes, исполнение или поведение других стоящих SOL orders.

Глобальные DD50/C/coherent peak не меняются. IncreasesOFF; новая команда не получает pending-fill credit. Каждый partial outcome обязан не ухудшать ТОТ ЖЕ unavoidable baseline; full endpoint — улучшить его либо быть безопасным; native protection сохраняется без ACK/cancel waivers. Полная допустимость новой семантики остаётся UNKNOWN до отдельного согласования/доказательства. DATA patch/fault-time изменения, replay/GO и перевод текущего NO_GO в PASS не предлагаются. Физический FAILED и отсутствие terminal-flat/financialPASS сохраняются.
