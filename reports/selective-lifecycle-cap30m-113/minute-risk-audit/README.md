# CM113 native minute risk audit — completed

One isolated unchanged-feed native observer replay completed 2026-10-10 10:17:45–10:33:23 UTC (15m38s), source `c70f920`, exit0, memory439.1M/swap0. Interval `[2024-09-01 00:00,2026-09-01 00:00)` UTC; initial10000 USDT.

Native paired-close callback samples reached minimum **4,233.36 USDT** at **2024-10-03 15:44:00 UTC**: loss **5,766.64 USDT / 57.66637426%** against initial capital. This includes actual native cash and native position unrealized PnL before quotes and after BTC/SOL quote callbacks; it is not an observed historical intrabar path.

## Three distinct native marked-equity excursions

|Rank|Peak UTC / USDT|Trough UTC / USDT|Peak-relative DD USDT / %|Recovery UTC|
|---|---|---|---|---|
|1|2024-09-14 00:19:00 / 13,807.88|2024-10-03 15:44:00 / 4,233.36|9,574.52 / 69.34097140%|2024-10-11 12:36:00|
|2|2025-04-11 01:00:00 / 1,128,523.01|2025-06-06 15:17:00 / 386,647.30|741,875.71 / 65.73864286%|2025-09-25 17:37:00|
|3|2025-10-22 21:29:00 / 2,061,026.89|2025-11-28 14:28:00 / 891,671.60|1,169,355.29 / 56.73653736%|2025-12-01 04:23:00|

Nonoverlapping high-water peak-to-first-recovery excursions; rank each excursion once using its deepest trough. CSV/JSON preserve full precision. The older cash-only maximum DD62.30510948% and seed loss28.06127610% omit unrealized risk; they are not the full marked-equity answer.

## Conditional minute OHLC bounds

With positions held before close quotes, the adverse equity lower bound reaches **4,085.45 USDT** in bar **2024-10-03 15:44–15:45 UTC**: conditional initial-capital loss bound **5,914.55 USDT / 59.14549026%**. Entry at the close does not receive the preceding bar's extrema. Funding remains actual native cash; min(previouspostquote cash,currentprequote cash) is the conditional cash floor.

Favorable running upper peak **13,832.96 USDT** in bar2024-09-14 00:18–00:19 to later adverse lower **4,085.45 USDT** in bar2024-10-03 15:44–15:45 yields a conditional held-exposure worst-DD bound **9,747.51 USDT / 70.46581444%**. Joint asset extrema and within-bar paths are unknown; this is a possible worst-case envelope, not observed portfolio DD.

The following lower-to-lower envelope excursions are descriptive statistics of the conditional lower series. Their percentages are not upper bounds on intrabar peak-to-trough drawdown:

|Rank|Lower-series peak UTC / USDT|Lower-series trough UTC / USDT|Lower-series DD USDT / %|Lower-series recovery UTC|
|---|---|---|---|---|
|1|2024-09-14 00:11:00 / 13,781.73|2024-10-03 15:45:00 / 4,085.45|9,696.28 / 70.35604466%|2024-10-11 12:37:00|
|2|2025-04-11 01:00:00 / 1,125,029.71|2025-06-06 15:17:00 / 384,540.38|740,489.32 / 65.81953525%|2025-09-25 17:35:00|
|3|2025-10-22 21:30:00 / 2,048,716.03|2025-11-28 14:31:00 / 875,100.68|1,173,615.35 / 57.28540872%|2025-12-01 04:24:00|

**0 conditional maintenance breaches** across1051200 minutes (576642 exposed) under the existing diagnostic `native equity <= tier maintenance` rule. Minimum exposed adverse-equity-minus-MMupper buffer **3,403.79 USDT** =4085.4509743−681.6574871 in Oct03 2024 15:44–15:45 bar; smallest exposed lower-equity/MMupper ratio **5.2971551012** in Nov28 2025 14:30–14:31 bar. Captured tiers are checked monotonic. No extra liquidation-fee reserve is included; this does not prove actual venue liquidation safety.

## Boundary, fidelity and parity

Trace has3153600 rows (three callback phases/minute). Native interval curve has3153599 samples including initial seed; completed-last-bar prequote at end_exclusive is retained as left-limit equity **5160427.18052161** and cash **5081850.17292161**. Both terminalpostquote rows are excluded from interval minimum/DD/TOP3; settled flat cash **5146884.95718200** is reported separately.

Exact unchanged economics: TOTAL5146884.95718200, fees1144089.96955003,502fills,556terminalorders,1321fundingpostings,0observedliquidations,0nativeopenpositions. All ordered native CSV columns match the winner after removing only engine`init_id`; normalized fillsSHA`4e6c85a3f14731d47b20ca301d2950fcb1b4222b381f7631ccf9159ee546ac09`, ordersSHA`41dacebf8aa0fe8562cf001f4a69565c070af3d3302692d577c2b0f95015e41b`. Config/data/policy/funding parity is in native-observer-receipt.json. PilotPID2009732/NRestarts0 unchanged. No additional simulation, high/low quote, triggered liquidation, fee/funding/strategy/pilot/deploy change.

Original execution and liquidation consume each minute close only. All four complete minute datasets contain valid OHLC; the observer values actual held native positions at native mark endpoints without feeding them into execution or liquidation. Independent BTC/SOL highs/lows need not coincide; cash/exposure bounds assume the recorded close-only model and do not reconstruct exchange intrabar fills. Historical BBO/liquidity/slippage, tier/fee applicability, synchronized tick paths and actual venue liquidation remain unvalidated. Status stays NOT_FAITHFUL_DIAGNOSTIC/rankingfalse. Exact joint historical intrabar maximum DD remains unknown.

Immutable native trace `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-minute-extrema-risk-20261010/result/minute-native-risk.csv.gz` (75760233bytes), SHA`37fc8c1e85bbc9e434e33bef3d3e3ae31e48b6502f3cc7332552941f269c71d1`. Raw observer resultSHA`669d5c951f0dbc88216385890b143b5bfd5bc8eeeff88cf968dd68346474c703`; small resultgzip, summary, parityreceipt, precisionCSV and analysisJSON are repo-backed here. Raw trace is deliberately retained only in the frozen job.
