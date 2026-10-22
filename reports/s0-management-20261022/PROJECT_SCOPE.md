# S0-MANAGE — завершённый native-эксперимент, цель не достигнута

[Принятый общий план](https://github.com/VF78/coinmaster/blob/66dacb18fe4cef4cdae263d21094a90a45c8a8bc/reports/s0-optimization-plan-20261022/PLAN.md). Пакет проверяет **одно** изменение сопровождения S0. Закрытие означает выполнение ограниченного исследования; кандидата для экономической цели DD≤50% / netprofit≥90% не найдено.

Точный сохранённый S0: TOTAL **6 077 107,23887483 USDT**, [2024-09-01,2026-09-01), seed10000. Его BacktestEngine не пересчитывался. Требуемый TOTAL **≥5 470 396,514987347 USDT** (min cents5470396,52); затем maxTOTAL среди прошедших DD≤50%. Данные/fees/funding/margin/execution/observer одинаковые, RESERVE0. Начальные BTC-сигналы/правила sizing и исходный SOL-overlay сохранены; будущие фактические объёмы зависят от изменённого капитала.

- [x] Saved decisions/D1/path states за все24 месяца, прибыльные и убыточные контрпримеры; без AI/control rerun.
- [x] До запусков зафиксировано одно правило и два уровня интенсивности; policy-freeze.json, source/input/config/command pins.
- [x] Реализация одним владельцем, **100 focused tests PASS**, независимый scoped review GO после одного P1 исправления приоритета выходов.
- [x] Последовательные полные nativeM1/M2 с отдельными engine/account/funding journals; **2/4** попытки использованы, автоматических retry/grid нет.
- [x] Проверка покрытия, terminal cash/flat, минутной DD, native fees/fills/ордеров и post-run hashes; независимая сверка saved outputs. Signed funding UNKNOWN сохранён.
- [x] JSON/CSV с TOTAL/ROI/netprofitretention/DD/fees/notional/funding/fills, месячными состояниями и фактическими сокращениями; причины эффекта описаны.
- [x] Fresh-engine повтор и optional execution-вариант **не допущены**: ни один M не прошёл оба порога, доказанного нового дефекта исполнения нет. Оставшиеся2 слота не используются.

## Фиксированное правило

Два последовательных пригодных settled money наблюдения одного native-цикла: DD ранее<25%, теперь≥25%, текущая позиция имеет отрицательный native UPnL. M1 запрашивает сокращение50% остатка, M2 —75%. Один fixed target/native reduce-only MARKET IOC child на цикл, фактические fills; частично исполненные отменённые остатки не повторяются. Native TP/forced/ordinary exits имеют приоритет. Защитное исполнение не даёт фиктивного BTC-TP/SOL-права. Eligibility gaps сбрасывают predecessor; первое наблюдение только задаёт его. Нет date-exclusions/ML/cooldown/reset peak/нового исполнительного или PnL-контура.

До кода level-predicate отвергнут за33/57 срабатываний в первую минуту; выбран fresh crossing (18 архивных интервалов,0 в первую минуту). Это диагностика возможностей, не обещание доходности.

## Фактические результаты

|Вариант|TOTAL USDT|ROI|Сохранено чистой прибыли S0|Settled minute DD|Native fees USDT|
|---|---:|---:|---:|---:|---:|
|Saved S0|6 077 107,24|+60 671,07%|100%|66,26%|945 927,74|
|M1 /50%|2 615 745,21|+26 057,45%|42,95%|58,77%|710 655,27|
|M2 /75%|2 044 863,63|+20 348,64%|33,54%|70,64%|614 360,75|

**Оба M отклонены; целевого победителя нет.** M1 уменьшает раннюю DD, но теряет рост капитала и получает худшую DD позднее. M2 увеличивает даже раннюю DD; ранний SOL1 остаётся без защитного claim. Изменения затрагивают также исходно прибыльные эпизоды. Комиссии ниже, но результат падает сильнее; точный изолированный causal PnL отдельных сокращений не выводился.

Оба native-процесса exit0,1 051 200 минут/source,1 051 199 settled receipts,87 source/input postchecks PASS, terminal flat, liquidation0. M1:26 protective fills BTC20/SOL6 (22 full+4 partial CANCELED),621 total fills. M2:25 protective fills BTC19/SOL6 (22 full+3 partial CANCELED),610 total fills. Исполнения не называются количеством полных сделок.

Источник: [efa7c723](https://github.com/VF78/coinmaster/commit/efa7c723d9f0c5c1bdc8f491abf12921ac41c275). [Отчёт и JSON/CSV](https://github.com/VF78/coinmaster/tree/codex/btc-pattern-pilot-m2-20261021/reports/s0-management-20261022). Exact manifests/launch/completion/economic-validation и run-budget.json сохранены. GitHub CI для source отсутствует (0 check/0 Actions); локальные tests и native validation указаны отдельно.

Пилот/production не изменялись, PID2009732 сохранялся; deployment/restart/внешние ордера0. Native Nautilus — единственный движок. Сохраняется исторический NOT_FAITHFUL_DIAGNOSTIC; OHLC conditional bound — отдельная оценка, не tick-path proof. Signed funding и per-asset realized PnL остаются UNKNOWN. #121/#122 сохраняют Done. Новые гипотезы/прогоны/AI/GUI/live не входят в этот завершённый пакет.
