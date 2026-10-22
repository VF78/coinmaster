# M1 independent economic validation — FAIL targets

Completed sealed native output validates: 44/44 checks and9/9 fee-bucket checks PASS. One saved-receipt pass49.53seconds/nice19/29,560KiB; zero additional native runs, replay, training or source changes.

Native final flat cash/TOTAL **2615745.21476479**; net-profit retention **42.9487251860%**, below90% (minimumTOTAL5,470,396.514987347). Independently recomputed agreed moneyDD **58.77409504467889817197266501%**, above50%. Final native-cash boundary endpoint DD **54.38352978592635052973558575%** also exceeds50%; including it leaves maximumDD unchanged. Zero liquidations. These are diagnostic native results, not OOS/live acceptance.

Worst receipt excursion: peak 5734212.23187448 at2026-05-15T02:55:00+00:00, trough2363980.88464897 at2026-08-11T12:15:00+00:00. Cash/TOTAL reconciles raw and wrapped reports, native cash-account last row, ACTIVE+RESERVE; final position count0/lifecycleFLAT and all native order statuses terminal.

621native fill-audit records independently reconcile with native fills CSV commission sums and all maker/taker/unknown counts/notionals. Maker135 fills /105,069.53920944fees /525,347,696.0472notional; taker486 /605,585.72869189fees /1,101,064,961.2573notional; unknown0. Native total fees710,655.26790133. Costs are already in cash and never deducted again.

26actual protective management fills: BTC20/SOL6, allTAKER MARKET/IOC/reduce-only. Each native cycle has one CLAIM/SUBMIT/FILL/TERMINAL.22orders fully FILLED;4SOL orders partially filled then CANCELED, so all26received fills but not all realized the full requested50% reduction. No pending order remains.

|Actual SOL action UTC|Submitted|Filled|Canceled remainder|
|---|---:|---:|---:|
|2025-01-13T13:03:00+00:00|2000.0|1000.0|1000.0|
|2025-07-28T05:55:00+00:00|2000.0|1000.0|1000.0|
|2025-08-10T01:37:00+00:00|1500.0|1000.0|500.0|
|2025-09-18T01:47:00+00:00|6500.0|1000.0|5500.0|

All26M1 cycles exactly match original S0 asset/first-entry timestamps. Original profitable counterexamples affected: BTC7/20 (tradeIDs8,28,66,67,71,72,96); SOL5/6 (IDs1,3,6,18,22). These are original trade outcome labels, not foregone-profit estimates. The actual M1 early SOL1 reduction atOct3 00:06 exists despite no such adverse fresh-crossing opportunity in the original S0 screen: the intervening native capital/mark path changed.

The failure is economically broad: initial September marked month-end capital improves (M1+7.14% versusS0−2.85%), but October/November growth is smaller (+109.38%/+113.21% versus+148.68%/+188.26%). ByNov2024 M1capital is68.68% ofS0, byJan2025 65.20%, byFeb2026 49.08%. July2026 is−43.58% versusS0−27.88%, ending at45.78% ofS0capital. The policy cuts exposure on12original winning intervals, and later native sizing/trigger paths differ; this supports a reduction/capital-path tradeoff but does not identify per-asset causal PnL.

FinalTOTAL is3,461,362.02411004 lower while native fees are235,272.46971692 lower. Lower costs do not establish a benefit sufficient to offset observed lower capital growth; costs alone are not a causal explanation. No losing trades were removed from old equity, and no alternate PnL ledger was built.

24-month same-source-quote-calendar nativeW/return/DD/exposure comparison is in economic-validation-m1.csv. Coverage1,051,199settled receipts+seed and1,051,200processed rows perBTC/SOL source, no unavailable/monotonic/coverage discrepancy. All13input pins matchS0andfreeze; source/input/launcher/command/config hashes and5economically relevant output hashes match frozen/sealed identity.

Saved native OHLC conditional bound is retained separately inJSON; actual tickDD and signed funding remainUNKNOWN. Conditional bounds were not reconstructed or presented as an intrabar path. All source/data/native outputs were preserved. M2 remains a separate frozen native evaluation; no new recipe or family was selected.

Native per-asset facts (actual saved fill rows; realized per-asset PnL remainsUNKNOWN_NATIVE_ACCOUNT_REPORT_ONLY):

|Asset|Native fills|Native fees USDT|Native notional|Management fills|Management fees USDT|
|---|---:|---:|---:|---:|---:|
|BTC|433|693612.55666138|1595425909.5955|20|35218.14440421|
|SOL|188|17042.71123995|30986747.709|6|541.6330436|

The report-only validator is reusable for sealed M2 with the same receipt/fee/source fields. No M2 interim result was read and no second S0 stream is needed.

Monthly CSV also includes actual native UTC fill-month fees byBTC/SOL and fill-action counts. This timestamp basis differs from source-quote receipt calendar; the final2026-09-01 boundary fill cost is stored separately inJSON, never folded intoAugust receiptreturn. Signed funding and per-asset realizedPnL remainUNKNOWN.

Worst-period shortlist (native settled scalars; primary independently restreamed):

|Rank|Peak receipt UTC|Trough receipt UTC|DD%|
|---|---|---|---:|
|1|2026-05-15T02:55:00+00:00|2026-08-11T12:15:00+00:00|58.77409504467889817197266501|
|2|2025-04-11T01:01:00+00:00|2025-06-06T15:18:00+00:00|55.28993927768639978317024965|
|3|2024-09-14T00:20:00+00:00|2024-10-03T15:45:00+00:00|46.59348096683015179714933556|

For the worst late drawdown, July2026 has35,009BTC-only /1,440SOL-only /8,191flat receipt samples; August29,644BTC-only /1,440SOL-only /13,556flat. Gross native notional/equity sample mean is2.874x/2.752x, max6.580x/8.419x. These are complete monthly exposure contexts, not exact excursion-only or trough exposure. Exact M1 trough positions were not retained by the first validator and remainUNKNOWN; no extra receipt scan was performed.

Exposure context for the shortlist, using whole UTC calendar months touching each peak→trough (includes samples outside precise excursion endpoints; no extra scan):

|DD rank|Whole months|BTC-only samples|SOL-only|BTC+SOL|Flat|Mean gross notional/W|Max|
|---|---|---:|---:|---:|---:|---:|---:|
|1|2026-05..2026-08|82198|23043|0|71879|1.858x|8.419x|
|2|2025-04..2025-06|42320|34913|25516|28291|2.746x|9.952x|
|3|2024-09..2024-10|35476|1440|2880|48043|2.139x|15.091x|
