# Native case map V2: targeted P1 closure

**0 P0 / 0 P1 — готово только для представления OWNER.** Единственная P1 предыдущей карты закрыта на уровне source/input design. Matching PASS, новый бюджет и native GO не выданы.

Проверены V2 md/json, точный V1→V2 diff и receipt source/real QuoteTick+OrderBook preflight. Их SHA совпадают с заявленными; receipt фиксирует PID47778, constructor tripwire, constructors0/matching0. Reviewer ничего не запускал. Остальное покрытие и условия допуска переиспользованы из `NATIVE_CASE_MAP_DESIGN_REVIEW`.

В VT2 второй SOL99 в140.50 теперь имеет displayed depth0.2; первый в140.25 остаётся0.1. VT4 явно наследует V2. Установленный stock `engine.pyx:6525–6540` сбрасывает consumption при изменении размера: доступно0.2, но оставшийся TP0 ограничивает его fill величиной0.1. TP1 BUY98/TP2 BUY96 при ask99 не marketable. Известное противоречие V1 устранено.

Расчёт согласован: TP0 filled0.3→0.4→0.5; исходная liability0.2→0.1→0; heldSOL0.7→0.6→0.5; положительные права в лотах `{0:0,1:2,2:5}`→`{0:0,1:1,2:5}`→`{0:0,1:0,2:5}`. Затем TP1 retiring с latestACK leaves0.1. Общий parent deadline200 и исходный cancel142 не перезапускаются. Реальные два fill, статусы, queued CancelRejected, история fills и callback cascade всё ещё MUST_NATIVE/UNKNOWN.

Уточнение identity корректно: до constructor фиксируются статические inputs и causal recipe/code/config/source/API/variant/transport; realized stream/bindings SHA остаются NULL/NOT_REALIZED. Depth140 проверяет заранее заданное1.022, mismatch→STOP. Для A0 заранее фиксируется формула/precision/разрешённые native поля, после run — фактические tuples, stream SHA и causal prior OID/eventUUID/asof bindings. Будущий хеш и подбор благоприятного trace не заявлены.

Прямое сравнение шести case payloads подтвердило только указанную market-поправку и поясняющие metadata; common, reused gates, budget и admission равны V1. V1 и старые ledger/prefix SHA сохранены. Product a50 и harness этим review не менялись.

Числовое предложение прежнее: 6 плановых + максимум1 строго harness-only reserve = additional7/cumulative11; альтернатива без reserve —6/10. Старые remaining3 остаются HOLD, prefix/full0. Это предложение для отдельного решения владельца. Нужны linked OWNER approval/protocol/new ledger, frozen admission pins, durable attempt claim до Popen/matching и индивидуальный root GO. Все прежние запреты на product-fault retry/trace changes и требования actual OS остаются.

Следующий шаг — представить исправленную карту и числовые альтернативы OWNER. Native qualification и экономика не допущены. Tests/engine/Popen/source/harness/gate/ledger writes в этом review:0.
