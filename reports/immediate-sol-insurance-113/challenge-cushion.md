# H-CUSHION: bounded numerical precheck, not native strategy result

105 selected6077 native BTC starts. Each estimate uses exactly91 paired completed daily prices/90 returns, linear q95, sample cov/var, beta(S|B) frozen at start, residual rSOL-beta*rBTC without intercept. No global fit, trace decode, engine, synthetic fills or PnL replay. Source pins in JSON. One pass 1.16s /113.5MiB peak RSS.

## Findings

- Before fees, SOL improves proposed linear scenario at100/105 starts (95.24%); worsens at5/105. Beta range1.0584..2.0183, median1.26393. a_simple median5.0234%, u_simple median4.6021%.
- Minimum scenario loss/NB: median2.9936%, p95=4.8909%, range2.0340..5.0876%. This is required C/NB lower bound, not portfolio DD.
- The expression is affine in c. Pure scenario minimization selects c=1 at100 starts and c=0 at5; intermediate grid points are not minimizers. To preserve ROI one must choose smallest c satisfying L<=C, not minimize L blindly.
- Actual entry H unavailable: sizing audit global_peak=10000/native_sample=None is stale and EXCLUDED. Eq0 inferred from recorded requested_notional/multiplier; not postfill E. Optimistic H=max(seed,Eq0) capacity admits c=0 at94 entries and c=.25 at11, none need larger cover. All105 fit the optimal grid even with illustrative taker open+close SOL/BTCexit costs, under that optimistic bound. This does NOT establish actual entry feasibility; historical H can be larger, leaving less cushion.
- NB_full=executed parent Q*first VWAP; first actual child notional separate. Neither is a continuously held mark notional or simulation of Q2/TP.

First start2024-09-02: Eq0=10000; optimistic C=4500; NB_full=45334.58; first child NB=22638.64. beta1.27148, a5.9373%, u5.8854%. Full-parent scenario no hedge2691.67, c=.25=2543.36, c=1=2098.45 before fees (c=1 known-taker illustration2162.60). This start needs no hedge under optimistic C; no claim about later H or dynamic policy.

Non-helpful example2025-02-21: NB_P0=2273204.87, beta1.28005, a4.1681%, u/beta4.5508%. Each extra c=.25 ADDS2174.8 scenario loss before fees. Opposite SOL cannot satisfy this model by simply adding more protection.

## Native selected6077 worst troughs

|E|H|.55H|C|Already below floor|
|---:|---:|---:|---:|---|
|4530.57|13451.34|7398.23|0|yes|
|367509.65|915175.73|503346.65|0|yes|
|937712.13|2088471.56|1148659.36|0|yes|

These are actual saved native E/H, not inferred entry values. Quantity/current NB were initially absent from selected compact landmarks; collaborator later independently validated them from621 native fills, folded below. Old comparison-analysis-worst-dd-native-landmarks.json is a DIFFERENT control: same first trough timestamp btc025 E2990.60 vs selected4530.57. Its quantities/E excluded. Latest preceding episode used only to provide frozen-beta contextual coefficients, not prove BTC remains open.

At C=0 any positive exposure/residual/cost leaves L>0. Hedging can slow risk growth but cannot repair an already breached capital floor while guaranteeing unchanged BTC. A complete H-CUSHION design needs an explicit infeasible-state outcome; silently increasing SOL is invalid. Daily q95 marginal shocks are NOT joint95, loss bound or DD guarantee.

## Practical gate

GO for H-CUSHION as the most evidence-backed of the new ANALYSIS hypotheses: past-only sizing and scenario-benefit checks are feasible, and capacity can avoid permanent insurance at many starts. NO-GO as a promisedDD45 solution or as ready implementation: actual H/remaining NB and costs need causal state, infeasible C must be explicit, and coefficients/gross costs do not establish ROI. Four prior native immediate-insurance variants FAILED; this arithmetic is NOT a native H-CUSHION test.

## Validated selected native inventory folded after independent crosscheck

No observer reread. Source postmortem-early-chop.json/native_621fill_inventory_crosscheck SHA43dfa946902ae484b4ca8623e84a2aad80ed948c30be2650420cc4cb5ebb986b; original selected raw and trace pins retained there.

|Trough|Actual BTC NB|Actual SOL NS|Minimum BTC scenario loss, no remaining costs|C|
|---|---:|---:|---:|---:|
|2024-10-03|43592.00|107984.31|1595.97|0|
|2025-06-06|3102472.77|0.00|88276.55|0|
|2025-11-28|15769369.58|0.00|473313.88|0|

Each remains UNHEDGEABLE at the saved trough under the specified floor. Existing opposite SOL on the first trough is shown for exposure context; it is not a hypothetical new policy. These are scenario losses, not realized PnL or joint95 estimates. Root hypotheses need smallest feasible c, churn hysteresis and an explicit UNHEDGEABLE outcome; full factor hedge cannot guarantee DD50.
