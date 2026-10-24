# Предварительная проверка E4, без физических прогонов

Task CM-MARKET-REDESIGN-PRECHECK-20261024. Исполнительский бюджет 0; выполнены только чтение сохранённых CSV/JSON/Parquet, SHA256 и статический анализ точного git-source. Продукт, VPS, Project и общие handoff-файлы не изменялись.

## №81: причина отсутствующего положительного TP3

Подтверждён дефект планирования жизненного цикла split-parent: постановка подтверждённых TP блокируется до завершения добора, а остановка незавершённого родителя по смене UTC-дня не запускает постановку TP на оставшийся фактический inventory.

Native evidence: первый SELL 135.648 BTC по63599 в2026-08-11 20:02UTC; второй SELL LIMIT135.648 по63758 создан20:03, исполнено0, отменён23:59. Parent.quantity271.296, filled135.648, cancelled135.648, fallback=True, completion_reason=DEADLINE, stop_reason=UTC_DAY_COMPLETION_FAILED. Во всём интервале до закрытия2026-08-18 00:00 нет reduce-only BTC LIMIT; только первый MARKET и второй отменённый entry LIMIT. Остаток135.648 закрыт REGIME по64498.1.

Точный source bd04c9b3858bcda40060a08eff488849c69af5d8:
- strategy/split_cover.py:89–100 ограничивает deadline последней минутой UTC-дня; :146–184 отменяет resting entry при deadline, на следующем минутном quote после23:59 попадает в UTC_DAY_COMPLETION_FAILED раньше нового fallback submit.
- strategy/wave_overlay.py:2523–2545: after-entry-fill вызывает _queue_confirmed_btc_targets, но она немедленно возвращается при _split_unfinished().
- там же:2565–2600: cancellation callback снова пытается queue, пока parent ещё unfinished. Это также return.
- strategy/split_cover.py:132–145: _split_stop закрывает parent/отменяет entry, но не вызывает queue. После stop нового entry fill/cancel, который мог бы создать TP, нет. Остальные queue callers относятся к отсутствующему здесь V3 protection или reject/expire.

Это вывод статического causal-chain + native конечных orders/parent, не новый native reproduction. Внутренний snapshot queue в точке23:59 не экспортирован. Цену61603.6 из attachment независимо не реконструировали; отсутствие TP установлено независимо от этой цены. Не установлено, была ли бы она исполнена или улучшила портфельный DD/ROI.

## Четыре окна UTC и M1

| № | первый native fill | последний BTC fill этого цикла | M1 баров на поток |
|---|---|---|---:|
|31|2025-04-11 00:01|2025-04-13 00:00 REGIME|2880|
|48|2025-10-11 00:02|2025-10-16 15:47 TP3|8146|
|65|2026-04-02 00:01|2026-04-03 00:00 BTC_REDUCE|1440|
|81|2026-08-11 20:02|2026-08-18 00:00 REGIME|8879|

Границы цикла: от first fill до последнего BTC fill перед следующим split-parent. Проверены BTC/SOL execution-1m и BTC/SOL mark-1m, по каждому из4окон: missing=0, duplicates=0, gaps=0. Бар сопоставлен времени исполнения по open_time_ms=quote_time−60000: close становится известен в конце минуты. Каждый полный поток1051200строк, 2024-09-01 00:00–2026-08-31 23:59 open UTC; глобальных gaps нет. Все4SHA256 совпали с data manifest. Пути/полные hashes/точные nanoseconds сохранены в evidence JSON.

M1 replay по этим4окнам технически возможен на сохранённых OHLC/mark. Сырые реальные BBO/L2/trade tape этим пакетом не подтверждены: execution config явно UNKNOWN_NO_L2_OR_TRADE_TAPE; архив использует синтетические quotes из minute close. M1 уменьшает временную неопределённость, но сохраняет неизвестный порядок внутри минуты, очередь и реальную исполнимую глубину. Новый экономический replay не запускался.

## Совпадение источника/config/data

Manager HEAD81378471c87ec96519422732cb5bd3e06c90f6b7 отличается от E4 и не использован как algo source. SHA256 всех6 указанных в raw-result исходников совпали с точным E4git-pin; artifact/raw hashes, config canonical SHA, data-manifest canonical SHA, policy canonical SHA и все10export hashes совпали с receipt. EMA34 подтверждена в resolved config, splitdiscount0.0025, PLANREF first-leg-completed, TP fractions .2125/.2125/.575. owner-closed-bars.csv blob=f2aafb8c784177e2606ed13cb11c409164f9aa9b. Полные pins в evidence JSON/исходном receipt. Статусы receipt VALID_NATIVE_COMPLETED и NOT_FAITHFUL_DIAGNOSTIC сохраняются одновременно; это не гарантия биржевой реалистичности. verifier cache:1051199 receipts, missing_source_minutes0; его compressed trace hash здесь заново не проверен.

## Ограничения / следующий допустимый шаг

ZIP из задания отсутствует в найденных локальных Downloads; использованы первичные E4 artifacts. Lifecycle81 достаточно определён для отдельного короткого acceptance-теста исправления, но продуктовые изменения и новые native runs требуют нового согласованного scope/budget. Не нужен повтор полного E4 ради повторной проверки уже совпавших hashes. Нет новых утверждений об economic PASS или реальной ликвидности.
