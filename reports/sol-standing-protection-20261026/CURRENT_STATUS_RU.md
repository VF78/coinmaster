# Текущее решение: native STOP после E2

Source `8a21673ca5c678120bf0498c97ebe9b562fe3c31` сохранён на VPS, в неизменяемой Mac-копии и публичной исследовательской ветке. Это не deployment и не финансово квалифицированный алгоритм.

**Бюджет: 4/7 fixtures — три FAILED, один COMPLETED; active0.** Три неиспользованные попытки — HOLD: протокол требует STOP после новой неудачи. Prefix0/4 условно после полного инженерного PASS; full0. Пилот и production исключены.

## Что подтверждено

Снимок заполненного native margin-счёта исправлен: публичные getters, явный UNKNOWN при ошибке. E6 записал восемь состояний при выключенном A0; это не полнота будущего prefix.

E7 (физическая №3, сценарий E1) принят координатором и независимым reviewer. Сохранены исходные SOL TP; тот же STOP получил три Updated ACK и full fill1.1 SOL@102. Три исходных BTC TP получили OrderCanceled ACK@138s. До cleanup позиции, ордера, inflight, команды и debt0, paired owner освобождён. Все три OS exit0. Это **PASS только E1**, не всего инженерного этапа или экономики.

## Что не прошло

E2 (физическая №4, cancel2s) FAILED@143s до предусмотренного негативного P2. BTC TP fill0.382 уменьшил BTC до1.418; SOLcap1.5 при actualSOL1.8. Старая ветка SOL_CAP отправила отмену трёх SOL TP и STOP. Перед следующим SOL matching все четыре PENDING_CANCEL; строгая проверка принятой защиты остановила движок.

Количества правильные: SOL TP0.3/0.5/1.0, STOP1.8; pending modify отсутствовал. **Интервал полного отсутствия живой защиты не доказан:** движок остановлен до cancelACK. Но реальная отмена защиты и неподтверждённое состояние доказаны; это не ложная ошибка observer и не PASS. До cleanup BTC1.418/SOL1.8 открыты; STOPPED/DISPOSED не означает flat. Все три OS exit1.

## Следующее решение

[Аудит 13 групп вызовов отмены](SOL_PROTECTION_CANCEL_PATH_AUDIT.md) выявил SOL_CAP, TP с нулевым остаточным правом и порядок глобального закрытия. [Контракт V2](SOL_REDUCTION_CONTRACT_V2_PROPOSED_RU.md) прошёл независимое review0P0/P1: один SOL_CLOSE owner, сохранение положительной защиты, реальные ACK и ограниченная retiring liability/late fill. Удалить один cancel или ослабить observer недостаточно.

[Следующий план из четырёх задач](NEXT_ACTION_PLAN_RU.md): контракт → isolatedкод+Cache/Orderreplay с native0 → source-review/полный native case map/отдельный бюджет → условная экономика. Владелец 27 октября утвердил реализацию и engine-free/native0; actual receipt `owner-v2-zero-engine-approval.json`, SHA `fb263ef1cdfb6267c76cc60c8b4340e23468f78a2e5dbbf2eeecb7d64d0fbfc1`. Реализация идёт в изолированном VPS-worktree. Новых native-запусков и нового native-лимита нет; supervisor STOP, четыре строки ledger, три слота HOLD и raw сохраняются.

Цели прежние: сначала ≥70% прибыли оригинального победителя при DD≤50%, затем ≥90%. Новых экономических результатов нет; prefix не полный период/OOS. [Обзор четырёх недель](../four-week-review-20261026/REVIEW_RU.md) и [единый план](../four-week-review-20261026/UNIFIED_PLAN_RU.md) сохраняются.
