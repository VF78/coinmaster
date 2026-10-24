# Дополнительный вопрос масштаба после трёх сценариев

24.10.2026. Это **post-result** арифметический вопрос, заранее ограниченный до своего расчёта, не четвёртый nativebacktest и не изменение трёх frozen growth-envelope сценариев. MomentumSTOP и его cashgates остаются неизменны. Бюджетengine0.

Исходные83проверенныеR3r_i из growth-envelope-results.json: три сценария показали, что идеального половинного снижения losing endpointreturns недостаточно до70%. Теперь фиксируется один дополнительный заведомо недостижимый без знания будущего bookend: всеr_i<0 заменить0, всеr_i>=0 сохранить полностью. Это предел именно **модели attenuation-only с неизменными winners**, не формальная верхняя граница настоящего SOL/другихBTCвыходов/сигналов/капитализации.

1. Вычислить Decimal80 `E_zero=10000*product(1+max(r_i,0))`, S0netretention и gap к70/90; early/year endpoints. Не пересчитывать/переписывать исходные трипути.
2. Только если E_zero>=соответствующегоfloor, найти монотонным bisection математический retentionα отрицательныхreturns в `10000*product(1+r_i if r_i>=0 else1+α*r_i)` для точного достижения данногоfloor. α∈[0,1], удаляемаядоля=1−α. Это **обратная диагностика требования**, НЕ выбранный liveparameter, signal/оптимизацияторговойстратегии/новыйeconomicresult. Еслиfloorнедостижим дажеα0, отметитьNOT_REACHABLE_IN_THIS_MODEL, не менятьwinners/плечо/контроль.
3. Никакие futurewinners/losers не становятся входнымиfeatures. Нет full/nativeTOTAL/DD/50%proof. Не заявлять математическую невозможность общей задачи. Вывод только: требуется ли простоеуменьшениелоссов, почтиидеальная ликвидациялоссов или новый подтверждённый положительныйcashflow/улучшениеBTCefficiency.

Один простой scalarpass и independentexact/rationalcheck zero-lossproduct плюс проверкимонотонности/остатков корней. Own filesgrowth-requirements-*; сохранитьinput/protocolhashes, явноpost-resultстатус; безchangesстарыхprotocol/scenario/screen/sharedstate/source/Project/commit.
