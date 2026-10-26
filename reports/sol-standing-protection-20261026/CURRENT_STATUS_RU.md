# Текущее решение: native STOP после E2

Текущий V2 source `a50af5433a0bbe00aecd6fec26e8d5c0321ced80` принят по коду/event replay: VPS209 и Mac209 PASS, review0P0/P1, BacktestEngine0. Он сохранён на VPS, в immutable Mac-копии и публичной research-ветке. Matching/экономика не квалифицированы; deployment не выполнялся. Native E1/E2 результаты ниже относятся к прежнему source8a.

**Бюджет: 4/7 fixtures — три FAILED, один COMPLETED; active0.** Три неиспользованные попытки — HOLD: протокол требует STOP после новой неудачи. Prefix0/4 условно после полного инженерного PASS; full0. Пилот и production исключены.

## Что подтверждено

Снимок заполненного native margin-счёта исправлен: публичные getters, явный UNKNOWN при ошибке. E6 записал восемь состояний при выключенном A0; это не полнота будущего prefix.

E7 (физическая №3, сценарий E1) принят координатором и независимым reviewer. Сохранены исходные SOL TP; тот же STOP получил три Updated ACK и full fill1.1 SOL@102. Три исходных BTC TP получили OrderCanceled ACK@138s. До cleanup позиции, ордера, inflight, команды и debt0, paired owner освобождён. Все три OS exit0. Это **PASS только E1**, не всего инженерного этапа или экономики.

## Что не прошло

E2 (физическая №4, cancel2s) FAILED@143s до предусмотренного негативного P2. BTC TP fill0.382 уменьшил BTC до1.418; SOLcap1.5 при actualSOL1.8. Старая ветка SOL_CAP отправила отмену трёх SOL TP и STOP. Перед следующим SOL matching все четыре PENDING_CANCEL; строгая проверка принятой защиты остановила движок.

Количества правильные: SOL TP0.3/0.5/1.0, STOP1.8; pending modify отсутствовал. **Интервал полного отсутствия живой защиты не доказан:** движок остановлен до cancelACK. Но реальная отмена защиты и неподтверждённое состояние доказаны; это не ложная ошибка observer и не PASS. До cleanup BTC1.418/SOL1.8 открыты; STOPPED/DISPOSED не означает flat. Все три OS exit1.

## Следующее решение

[Аудит 13 групп вызовов отмены](SOL_PROTECTION_CANCEL_PATH_AUDIT.md) выявил SOL_CAP, TP с нулевым остаточным правом и порядок глобального закрытия. [Контракт V2](SOL_REDUCTION_CONTRACT_V2_PROPOSED_RU.md) прошёл независимое review0P0/P1: один SOL_CLOSE owner, сохранение положительной защиты, реальные ACK и ограниченная retiring liability/late fill. Удалить один cancel или ослабить observer недостаточно.

[План из четырёх задач](NEXT_ACTION_PLAN_RU.md): V2code+enginefree этап выполнен; [результаты](V2_IMPLEMENTATION_RESULTS_RU.md). Подготовлены [полная native карта V2](NATIVE_CASE_MAP_V2_PROPOSED_RU.md) и [новый протокол](NEXT_NATIVE_QUALIFICATION_PROTOCOL_PROPOSED_RU.md), оба reviewed0P0/P1: 6planned+максимум1harness-onlyreserve, до7 НОВЫХ attempts/cumulative11. Это ещё не согласие владельца. Старые supervisor STOP/четыре строки/триHOLD/raw сохраняются, новых native запусков нет. Prefix/full0; следующий бюджет требует отдельного прямого согласия.

Цели прежние: сначала ≥70% прибыли оригинального победителя при DD≤50%, затем ≥90%. Новых экономических результатов нет; prefix не полный период/OOS. [Обзор четырёх недель](../four-week-review-20261026/REVIEW_RU.md) и [единый план](../four-week-review-20261026/UNIFIED_PLAN_RU.md) сохраняются.
