# Conditional price-path addendum — без native/PnL

20 сохранённых возможностей; SHA обоих original execution Parquet и621 native fill-audit rows подтверждены. Реальный collector:2.825s,peakRSS268,791,808bytes (~256.34MiB),nice19. Новых native/replay/engine/PnL0.

**17/20** имеют closed15m confirmation и следующий1m close до первого ordinary actualfill; **3/20** нет (BTC43/63/100, REGIME/FORCED_CLOSE). **11/17** после условного restore снова касаютсяcutref. Это отрицательное свидетельство против простого restore, не равенство убытку и не опровержение полной политики.

Median normalized adverse pricegap+TWO fee terms = **0.68624941%** cut reference price; max **1.48106488%**. Это per-unit условный price-cost reference, не портфельный PnL/ROI. Никаких взвешенных сумм упущенной прибыли.

| SOL | Cutref UTC /price | Confirm UTC | Next1mclose UTC /price | Cut→confirm /restore min | Signed gap/unit | Gap+fees normalized | Touchcutagain | Max adverse afterrestore |
|---|---|---|---|---:|---:|---:|---|---:|
|1|2024-10-03T08:23:00+00:00 /137.35|2024-10-03T09:30:00+00:00|2024-10-03T09:31:00+00:00 /137.31|67.0/68.0|-0.04|0.0808613%|True|3.20442794%|
|3|2024-11-22T03:20:00+00:00 /264.27|2024-11-22T04:15:00+00:00|2024-11-22T04:16:00+00:00 /261.41|55.0/56.0|2.86|1.19163129%|True|1.1437971%|
|22|2025-09-18T16:52:00+00:00 /249.89|2025-09-18T19:15:00+00:00|2025-09-18T19:16:00+00:00 /248.44|143.0/144.0|1.45|0.68993617%|False|0.22943165%|

Ранний SOL1: confirm через67min, nextclose через68min. На nextclose137.31 цена уже нижеcutref137.35, хотя закрытая15m дала подтверждение; этот negativecase не отфильтровывался задним числом. После него OHLC adverse move3.20443% и повторное касаниеcutref. Если будущая политика повторно проверяет recovery на реальном quote, решение может отличаться; здесь оноUNKNOWN.

Timestamp semantics проверены: Parquet open_time_ms — начало минуты, closeavailable=open+60s;15mavailable=UTCopen+15min. Cutref строгоПОСЛЕsnapshotreceipt, вся confirming15m открыта не раньшеcutref; restoreref строгоПОСЛЕconfirmation. Нормализатор bybit_minute.py:96, native available-time native_baseline.py:879; пути/схемы вJSON. Все timestampQAtrue.

Три no-confirm окна содержат полноценные postcut15m bars, но ни одна не выполнила совместно recovery+previousbarbreak до первого actualordinaryfill; точные времена/reasons/counts вJSON/CSV. Actualfill —лишь верхняя граница окна: более ранний ordinaryintent/eligibilityUNKNOWN. Nativeactualtrim/restoreprices,filledqty,L2 иреальныеexecutionoutcomesUNKNOWN. OHLCtouch не доказывает intraminuteorder илиfill. 20строк включают negative/absentcases. Больше чтений илирасширений не запускалось.
