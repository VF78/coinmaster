# CM113 deep drawdown causes and stop statistics

Read-only analysis of exact winner and observer trace at source64faa21. No new simulation, strategy edit, pilot/deploy action or independent PnL engine. Native cash/equity are authoritative; saved confirmed-fill average/proportional fee attribution is exfunding. Native endpoint-derived perasset close-PnL is reconciled within0.01USDT and labeled attribution, not separately settled trade PnL.

## What caused the three deepest marked drawdowns

|DD / period UTC / recovery|Peak cash → trough cash|Cash decline / unrealized decline|Trough exposure and unrealized PnL|Actual gross/equity at trough|
|---|---|---|---|---|
|69.3410%: 2024-09-14 00:19:00 → 2024-10-03 15:44:00; recovery 2024-10-11 12:36:00|13,700.24 → 9,122.28|4,577.96 / 4,996.56|BTC SHORT 0.686 / 412.49; SOL LONG 766.1 / -5,301.41|33.8562x|
|65.7386%: 2025-04-11 01:00:00 → 2025-06-06 15:17:00; recovery 2025-09-25 17:37:00|1,093,856.94 → 503,277.42|590,579.52 / 151,296.19|BTC SHORT 30.848 / -116,630.12|8.3952x|
|56.7365%: 2025-10-22 21:29:00 → 2025-11-28 14:28:00; recovery 2025-12-01 04:23:00|1,854,924.95 → 1,822,382.91|32,542.04 / 1,136,813.25|BTC SHORT 165.049 / -930,711.31|17.2041x|

DD1 combines two realized BTC regime losses (completed BTCepisodes3/4:−4326.10/−2167.10) with a later SOLlong loss. At trough BTCshort gains412.49 while SOLlong loses5301.41. BTCactual0.686 is57.65% of reference1.19 after two omitted levels; SOLlevel0 enters766.1 at140.09 (107322.949notional) using H from fullBTCreference/beta and earned rights. Exact archivedbeta/entryequity are absent. This is approved reference-based sizing plus equity erosion, not a proved size bug. SOLnotional at trough102021.537/equity4233.363=24.099x.

DD2 is predominantly accumulated realized BTC regime/whipsaw losses:6BTCregime remaining exits net−839406.00 offset profitable reductions and SOLexits. Native cash accounts for79.61% of the741875.71 equity drawdown. Biggest local completed BTC losses: episode35 Apr11–13−360247.81, episode42 May25–Jun06−174713.90, episode36 Apr13–14−120389.41. Trough is BTCshort only; no SOLloss explains it.

DD3 is97.22% unrealized deterioration. Remaining BTCshort165.049 loses930711.31 at trough; actual markednotional15.340m/equity891671.60=17.204x. Earlier realized regime losses were largely offset by TPprofits, so net cash drops only32542.04. The same BTCquantity remains through Dec01 recovery; leverage rises as equity falls. A daily profit trail is not a downside intraday stop. None of these three periods is explained by a30mcap breach; firstcapbinding is2026-03-05.

## First50% crossings and observed recovery

|DD|First50% crossing UTC / native equity|Further decline to trough|Original-path rise to recovery|Time underwater|
|---|---|---|---|---|
|1|2024-09-17 15:04:00 / 6,862.18|2,628.82|6,973.49|27.512days|
|2|2025-04-14 00:23:00 / 559,838.60|173,191.30|577,417.61|167.692days|
|3|2025-11-28 13:48:00 / 980,864.08|89,192.48|1,081,915.25|39.288days|

These are observed original-path values, not avoided losses or a stopped strategy’s foregone PnL. Stopping changes exposure, rights, fees and future compounding.50% is a portfolio peak-relative threshold; the disabled seed/start deposit protection is a different rule.

## Stops and loss counts

True fixed-price stop-loss exits: **0**, losses from that nonexistent mechanism: **0**. BTCfixedstop=null, SOLzstop=null, portfolio-loss-limit=null, depositprotection disabled, liquidation exits0. BTCprofittrail uses `f=side*(dailyclose/entryVWAP−1)`; activates only if bestf>3%, then exits if f<=bestf−3percentagepoints. This is daily entry-return profit retrace, not3%capital loss or a minute price stop.

|Actual exit label|Native orders/fill rows|Logical closing cohorts|Net losing rows|Total attributed net exfunding|
|---|---|---|---|---|
|BTC BTC_REDUCE|77/77|44|0|3,270,265.74|
|BTC BTC_TP2|24/24|24|6|58,293.38|
|BTC BTC_TP3|54/54|54|0|12,021,222.84|
|BTC REGIME|48/48|48|48|-10,972,129.72|
|BTC TERMINAL_BOUNDARY_SETTLEMENT|1/1|1|0|55,548.45|
|BTC TRAIL|2/2|2|0|114,243.78|
|SOL REGIME|42/42|13|1|552,372.05|
|SOL SOL_HARD_TIMEOUT|12/12|1|12|-120,525.84|
|SOL SOL_Z_FULL_EXIT|1/1|1|0|4,858.10|
|SOL SOL_Z_HALF_EXIT|1/1|1|0|4,128.50|
|SOL TRAIL|40/40|11|13|122,560.11|

TRAIL has **13 parent/reason closing cohorts:11positive,2negative**,42nativeclosingorders (2BTC+40SOL), totalnet **236,803.89**. The2BTCclosures bothprofit (+114243.78 combined);11SOL-onlycohorts occur after BTCnativeposition is already TP-flat while retained domain episode still applies BTC’s daily trail. This is not42SLtriggers. Negative SOLcohorts: Apr02 2025−19606.076 (6orders), Aug15 2025−65916.3295 (7orders), total−85522.4055; gross−83230, allocatedentryfees1133.6325+exitfees1158.773. Worst group is Aug15. Native IDs/dates are in trail-closing-groups.csv; cohorts are inferred from parent+reason, not archived decision callbacks.

SOLtimeout12orders is **one** full SOLepisode (May20–Jun03 2026), net−120525.836; it is a14dayholding timeout, not a priceSL. SOLzhalf/full each1positive exit.6BTC TP2 rows lose655.815655 after allocatedfees despite positivegross, so fee loss is not SL.

|Completed position episodes|Losing / winning|Sum losing net exfunding|Sum winning net exfunding|
|---|---|---|---|
|BTC 105|48 / 57|-10,796,001.94|15,343,446.42|
|SOL 26|4 / 22|-210,980.23|774,373.15|

48negative remaining BTCREGIME exits are not synonymous with whole-episode PnL; earlier TPs offset portions. Whole BTCepisode losing total−10796001.94 differs from REGIMEremaining-exit−10972129.72. Worst completed BTCepisodes: May15–18 2026−1388243.06, Jul31–Aug01−937538.17, Mar05–06−856438.97. Worst SOL: May20–Jun03 2026−120525.84, Aug08–15 2025−65916.33, Mar27–Apr02 2025−19606.08. Exact dates/fees/IDs are in JSON.

Reconciliation: actualnative fees **1,144,089.97**, closing attributed net **5,110,837.40**, native cash gain **5,136,884.96**; residual **26,047.56** remains unallocated native cash/funding/other. Do not label it actual signed funding. Peak-to-trough cash residuals are−29.2876,−1919.6864,+8737.6544 after actual window fill fees; they also remain unallocated.

## Minimal variants to compare toward50%DD

1. **Minute native marked portfolio high-water risk trigger, e.g.40-45% below running marked-equity peak, native reduction/flatten plus explicit entry lockout/reset policy** (NEW_TRADING_RULE). All3 measured excursions cross50%; protects both BTC and SOL, unlike BTC-only stop. Existing disabled seed/deposit protection is not this rule. 50% trigger cannot guarantee50% realized DD after gaps, latency, fees or partial exits; use buffer and compare native execution. No counterfactual ROI claimed.
2. **Single param-only exposure scaling0.5: BTCnotional multiplier7.875→3.9375, SOLh multipliers1.75/2.625/3.5→0.875/1.3125/1.75** (NEW_CANDIDATE_PARAMETER_VARIANT). Measured gross/equity up to33.856x,17.204x; actualnotional reduction attacks leverage. Changing exchange leverage setting alone does not resize exposure. Compounding/rounding/rights/margin and fees change; DD/ROI are not linear and <=50% is not proved.
3. **SOL allowednotional cap relative to fresh native marked equity and overall gross budget, with native SOL stop/derisk action if bound breached** (NEW_SOL_SIZING_AND_RISK_RULE). DD1 SOLlong alone−5301.412 unrealized against4233.363 total equity; approved H usesfullBTCreference notremaining0.686 and isnotreducedwhen equityfalls. SOLalso earns563392.9181 net exfunding overall; cap or stop can cut profitable paths. Beta floor alone is not demonstrated fix; archived exactbeta absent.
4. **BTC adverse-entry price SL4/5/6%, native minute mark trigger/reduce-only execution; keep profit trail separately** (NEW_BTC_STOP_RULE). Daily profit-retrace trail is not downside stop. DD3 short165.049 suffers large adverse unrealized move and crosses50% intraday. BTC-only SL misses DD1 SOLdominant loss. No hypothetical SL PnL from original path; later rebound is observed originalpath only.

Lower exchange leverage alone changes collateral requirement, not the actual position/equity exposure; reduce actual notional multipliers or native quantities. Raising beta floor alone is not proven to address DD1. No proposed variant has a measured<=50%DD or nondecreasingROI yet. A gap/fees/partialexecution buffer and explicit restart/entry policy are needed before a portfolio stop can be treated as a risk cap. Existing immutable diagnostic limitations—minuteclose execution, synthetic quotes, unknown historical slippage/liquidation/fee applicability—remain.

Evidence: drawdown-causes.json / .csv, exit-reason-stats.csv, trail-closing-groups.csv; reproducible analyze.py reuses existing native observations only.
