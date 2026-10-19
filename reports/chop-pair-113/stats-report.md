# Bounded causal chop / first-passage study

Analysis only, native winner preserved. No trading engine, new portfolio PnL, TOTAL, ROI or DD was calculated. Native control remains TOTAL 6077107.23887483, ROI 60671.0723887483%, native minute DD 66.31878024969%.

One chronological pass read genuine Bybit execution minute bars separately for BTC and SOL, 1051200 aligned rows each [2024-09-01,2026-09-01), with completed daily history for EMA34, ATR and causal W90 beta. Daily source spans enough history before the interval; no substitute or fetched data. Sources and fresh exact SHA256 are in stats-summary.json; original native JSON SHA 4dbfaf0d228f27ebc5e24157b613b0ddd279bffa2d163d042684bdad13bbec1b, config/data/policy pins inherited unchanged from named preflight. Max RSS 344444 KiB (~336.4 MiB), low priority, single-thread numerical runtime, idle I/O. No observer trace read. Reproduce: runtime/.venv/bin/python reports/chop-pair-113/stats-analysis.py then stats-finish.py then stats-report.py. The finish pass only rereads daily bars, applies label embargo, adds Wilson intervals and limited coefficient comparison.

Calibration 2024-09..2025-08; holdout 2025-09..2026-08. Detector family and thresholds fixed before minute pass. Diagnostic ex-post label: forward7 completed daily ER<=.35 and at least2 forward EMA34 flips; never a feature. Labels must end before each period boundary, leaving358 scored days/period. This is one narrow descriptive definition of chop, not ground truth. Features: near EMA34 <=1 ATR(EMA14 true range); ER7<=.35; abs(EMA[t]-EMA[t-3])/ATR<=.35; >=2 flips in7 completed transitions. All detectors require2 consecutive true/false raw states to enter/exit.

| Period | Detector | Flag days | Label recall | Precision | False-positive rate | Balanced accuracy | Onset detected/missed | Median onset/end delay D |
|---|---|---:|---:|---:|---:|---:|---|---|
|calibration|flips2|76|6.1%|3.9%|23.6%|0.412|2/18|1.5/0.0|
|calibration|flips2_near|58|4.1%|3.4%|18.1%|0.430|1/19|3.0/0.0|
|calibration|near_ER|100|44.9%|22.0%|25.2%|0.598|9/11|0.0/0.0|
|calibration|near_slope|170|75.5%|21.8%|43.0%|0.662|15/5|0.0/8.0|
|calibration|ER_slope|150|53.1%|17.3%|40.1%|0.565|12/8|0.0/0.0|
|holdout|flips2|46|31.6%|26.1%|10.6%|0.605|6/4|0.0/3.0|
|holdout|flips2_near|37|28.9%|29.7%|8.1%|0.604|6/4|0.0/2.0|
|holdout|near_ER|86|44.7%|19.8%|21.6%|0.616|6/4|0.5/1.5|
|holdout|near_slope|160|73.7%|17.5%|41.2%|0.662|10/0|0.0/5.0|
|holdout|ER_slope|133|63.2%|18.0%|34.1%|0.645|8/2|0.5/1.5|

near_slope wins calibration only (balanced accuracy .66234); no holdout reselection. It catches the10 holdout label segments, but132 false flagged days and17.5% precision make full-cover activation solely from it unsupported. Zero onset delay means flag already active at label start, not accurate advance warning; delays omit missed segments. End delay is first unflagged day within14D after label end, conditional on an observed end; default8D calibration/5D holdout is slow. Baseline2 flips is late/low recall; alternatives without mandatory flips detect more but add false alarms.

Forward paths use minute closes only. Native105 BTC episode time/side are preserved from hashed existing native-derived context; entry observation is synchronized minute close, NOT claimed native average execution fill. A native BTC path stops at actual original exit or requested finite horizon.15m/1h/1D/7D horizons are exported; no7D native ladder was estimated because fewer than8 uncensored calibration paths survive original exits. Additional 15m/1h SOL EMA34 flip contexts during causal chop and daily chop onsets are diagnostics; they create no substituted BTC entries. MFE/MAE are close-based; high/low intraminute path ordering and fill ambiguity remain unknown.

TP levels are calibration-only inverse20/50/80% quantiles of future close-MFE among uncensored paths ending before split. All native1D ladder levels have33 uncensored calibration training episodes; broader calibration hit report uses57 episodes/24 censored; holdout48 episodes/14 censored. Censored paths are nonhits in the reported observed fraction. This informative exit truncation and overlapping contexts mean nominal80/50/20 labels are not promises; Wilson intervals ignore serial dependence and are descriptive.

| Native1D leg | TP | Level % | Holdout hits | Hit % [Wilson95%] | Median hit min | Conditional adverse excursion % | Conditional paired after-fee median % BTC notional | Positive paired slices |
|---|---:|---:|---|---|---:|---:|---:|---:|
|BTC|1|0.5317|36/48|75.0 [61.2,85.1]|211.0|-0.3532|-0.0756|44.4%|
|BTC|2|1.2082|21/48|43.8 [30.7,57.7]|803.0|-0.5831|-0.0792|42.9%|
|BTC|3|2.1041|10/48|20.8 [11.7,34.3]|848.5|-0.7812|-0.3684|30.0%|
|SOL|1|1.0409|30/48|62.5 [48.4,74.8]|314.0|-0.5590|0.1270|60.0%|
|SOL|2|2.4238|19/48|39.6 [27.0,53.7]|811.0|-0.7360|0.1471|68.4%|
|SOL|3|4.2248|4/48|8.3 [3.3,19.6]|1047.0|-0.7509|0.8079|100.0%|

Paired arithmetic is gross movement at the same first close trigger: signed BTC return + opposite SOL return / beta(S|B), less conservative taker roundtrip .11%*(1+1/beta) per BTC notional. It assumes hypothetical entry of both legs at the same observation and hypothetical close of both at event prices. Fees are included; funding, spread, slippage, executable delay, market impact, lot/margin effects are UNKNOWN, so this is not a true net lower bound. Conditional paired values exclude all nonhits and cannot establish unconditional edge or portfolio PnL.

15m high-probability levels (.02597% BTC/.02346% SOL) get30/48 and40/48 OOS hits but zero positive paired net slices; median paired net -.18278%/-.18348%. 1h TP1 .09241%/.20390% gets32/48 and30/48, median -.20550%/-.15189%. Fast frequent trims mainly pay costs. Native1D SOL TP1 is the strongest practical frequent-event candidate: calibration46/57 hits, median paired after-fee +.153868%,69.6% of hit slices positive; holdout30/48 hits, median +.126960%,60% positive. Even here12/30 hit slices fail after the stipulated fees, and18/48 never hit before horizon/original exit. One cannot blindly close the losing leg merely because the other leg touched TP.

Coefficient distinction matters: factor-neutral opposite SOL notional is NB/beta; minimum-variance is NB*Cov(B,S)/Var(S)=rho²*NB/beta. Holdout daily W90 rho² median .728488, min .490608/max .874030; median factor-neutral SOL/NB .788665 vs minvariance .546533. Calibration medians .592972 rho², .718997 vs .445368 notional. Minimum-variance preserves residual BTC factor exposure, so it cannot be marketed as near1 factor coverage. For30 stored OOS15m BTC-TP1 endpoints, factor-neutral paired median -.182781% vs minimum-variance -.158601%: lower cost still fails. This is a deliberately limited endpoint comparison, not a second full TP-family optimization.

Representative actual synchronized path: 2025-09-05 00:01 UTC SHORT context, BTC110737.7/SOL202.44 ->00:02 BTC110688.5/SOL202.48, beta1.763358, rho².532033. Factor-neutral gross +.055635%, fee .172381%, after-fee -.116746%; minvariance after-fee -.092798%. Exact30 example endpoints are in stats-pair-examples.csv. They were collected deterministically as the first30 OOS15m BTC-TP1 hits, not selected for positive returns.

**Strongest provisional proposal, not economic GO:** preserve original profitable SOL alpha and exact BTC entry policy. Treat near_slope as a weak context flag requiring an independent actual risk/adverse-price trigger, not sufficient evidence to force full opposite coverage. Within a current BTC episode, precheck SOL ladder1.040878/2.423763/4.224761% on a finite1D close-only monitoring horizon. TP1 proposes proportional paired reductions; TP2 proposes retirement of the paired losing slice only when actual signed slice proceeds minus known and estimated exit costs are positive with a friction buffer. TP3 may leave a residual trend fraction. Exact reduction fractions, BE/rearm transitions, eligibility when SOL alpha is same-direction, and margin remain unimplemented/untested. This is an empirically screened proposal; unconditional expected edge has not passed a test.

After TP1 a raw entry-price stop is not cost-adjusted BE: account for retained inventory cost basis, realized fees, future exit fees, funding and slippage allowance separately on each leg. At next original opposite BTC entry, one NETTING BTC position cannot retain the old opposing quantity while preserving native new-entry side/size; entry rules dominate. Do not promise hold-through-flip or cost-free whipsaw. No DD30–50 guarantee, no new TOTAL/ROI/DD inference, no economic run or implementation authorization implied.
