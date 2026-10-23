# B reentry-band ROI postmortem — saved evidence only

B is a valid negative result. It lowers global settled DD from66.2569148647% to57.5854104596%, but terminal TOTAL falls from6077107.23887483 to4622034.27336437: −1455072.96551046, with76.0170224751% of S0 net profit retained. The90% target is5470396.514987347, so B needs848362.241622977 more terminal capital (18.3547% of B TOTAL) and another7.5854percentage points of DD improvement. No economic improvement is established by the proposals below.

This is one bounded analysis of saved observations, no native engine/replay/backtest/training/model run, no new market data, no product edit, no parameter optimization. Frozen implementation25a085f596292df58e51188dd91e996adbe5724c; report checkout HEAD7fa5800f9ae58a84281a561532f1248ef0eaecdb. The inputs and their SHA256 are in roi-summary.json; the12 assertions and exact Decimal accounting are reproducible in roi-analyze.py. This benchmark remains NOT_FAITHFUL_DIAGNOSTIC and seen-data, not independent OOS. Parent owns publication/ops/Project; this work writes only this folder.

## 1. Exact turnover/fee bridge

|Metric|S0|B|B−S0|
|---|---|---|---|
|TOTAL|6077107.23887483|4622034.27336437|-1455072.96551046|
|ROI_percent|60671.072388748300|46120.342733643700|-14550.729655104600|
|net_profit_retention_percent|100|76.01702247510777033476616279|-23.98297752489222966523383721|
|settled_DD_percent|66.25691486468686414439256686|57.58541045962226379114466259|-8.67150440506460035324790427|
|fills|621|484|-137|
|BTC_fills|416|322|-94|
|SOL_fills|205|162|-43|
|fees|945927.73761825|592090.31669918|-353837.42091907|
|turnover|2209476512.432100011491088|1406637279.4840|-802839232.948100011491088|
|maker_notional|769383840.627700008811020|518743391.4779|-250640449.149800008811020|
|taker_notional|1440092671.804400002680068|887893888.0061|-552198783.798300002680068|
|maker_fees|153876.76812554|103748.67829558|-50128.08982996|
|taker_fees|792050.96949271|488341.63840360|-303709.33108911|

B pays353837.42091907 less native commission and turns over802839232.948100011491088 less notional. Fills fall137 (BTC−94, SOL−43). Fewer trades do save fees, but those savings coexist with the1455072.96551046 terminal deficit. The exact accounting identity is:

`TOTAL_B − TOTAL_S0 = ((TOTAL_B + fees_B) − (TOTAL_S0 + fees_S0)) − (fees_B − fees_S0)`

`−1455072.96551046 = −1808910.38642953 +353837.42091907`.

The−1808910.38642953 is a nonfee terminal accounting residual, **not** gross trade PnL or an isolated signal effect. It includes changes in path, capital, exposure, realized/unrealized settlement, and unknown signed funding. Adding fees back does not create a new economic simulation. The S0 verifier-reference-fills.csv contains621native aggregated filled-order report rows and permits an independent asset/liquidity split. Commissions are parsed with ast.literal_eval and Decimal; notional is filled_qty×avg_px. The old episode-label fee column is never substituted for this native evidence. B’s actual fill audit permits the following exact decomposition:

|B asset/liquidity|fills|native fees|native turnover|
|---|---|---|---|
|BTC/MAKER|106|103748.67829558|518743391.4779|
|BTC/TAKER|216|473594.45836865|861080833.3971|
|SOL/MAKER|0|0|0|
|SOL/TAKER|162|14747.18003495|26813054.609|

B BTC commissions577343.13666423; SOL14747.18003495. BTC entry154fills, reduction136fills, REGIME28fills, TRAIL3fills, terminal1fill; SOL add80fills and exit82fills (all taker). Group-level reasons span both assets: the67REGIME and41TRAIL entries in roi-fill-actions.csv must not be mistaken for BTC-only counts. BTC entry fees287888.80476200 and turnover690960927.4861 are already included, not extra. Original SOL rights remain active; this is not a BTC-only strategy. Asset signed funding and asset native net PnL remain UNKNOWN throughout;1157 funding rows in B establish occurrence, not signed cash per asset.


The independent **native aggregated filled-order report** comparison is:

|Recipe / asset / liquidity|native filled-order rows|commissions USDT|filled_qty × avg_px notional|
|---|---|---|---|
|S0/BTC/MAKER|135|153876.76812554|769383840.627700008811020|
|S0/BTC/TAKER|281|773790.18817866|1406891251.233400002680068|
|S0/SOL/MAKER|0|0|0|
|S0/SOL/TAKER|205|18260.78131405|33201420.571|
|B/BTC/MAKER|106|103748.67829558|518743391.477900004436300|
|B/BTC/TAKER|216|473594.45836865|861080833.397100004147210|
|B/SOL/MAKER|0|0|0|
|B/SOL/TAKER|162|14747.18003495|26813054.609|

S0 BTC416rows, commissions927666.95630420, native report notional2176275091.861100011491088; SOL205rows, commissions18260.78131405, notional33201420.571. B BTC322rows, commissions577343.13666423, report notional1379824224.875000008583510; SOL162rows, commissions14747.18003495, notional26813054.609. BTC fee reduction350323.81963997 and SOL3513.60127910 sum exactly353837.42091907. Both total commission sums reconcile exactly to their comparisons. S0 aggregated report turnover reconciles exactly. B aggregated report turnover1406637279.484000008583510 differs from the native fill-audit/comparison1406637279.4840 by0.000000008583510 because exported native avg_px serializes small floating representation differences. roi-native-order-notional-reconciliation.csv preserves both bases and this residual; no tolerance or exact-turnover equality claim hides it. The primary B turnover above stays the actual native fill-audit sum. These rows do not reconstruct asset PnL, and neither funding nor asset native net becomes known.

## 2. Capital divergence compounds; it is not a list of removed profits

For each nonoverlapping native calendar month, let `f=(B_end/B_start)/(S0_end/S0_start)` and `q=B_end/S0_end`. Then `q_end=q_start*f`. All monthly boundaries join exactly in the saved native observations (relative boundary multiplier1); the24relative monthly factors multiply to0.7606755966131168930164783269804977957340 before terminal settlement. These are realized path comparisons; they do not identify which single entry caused a month’s whole return.

|Month|S0 return%|B return%|relative factor|end B/S0|S0 end|B end|
|---|---|---|---|---|---|---|
|2024-09|-2.8458|26.1571|1.298525|1.298525|9,715.42|12,615.71|
|2024-10|148.6761|147.0560|0.993485|1.290065|24,159.93|31,167.87|
|2024-11|188.2566|188.5478|1.001010|1.291368|69,642.58|89,934.22|
|2024-12|72.9915|7.3907|0.620786|0.801663|120,475.73|96,580.97|
|2025-01|288.9478|135.3173|0.605010|0.485014|468,587.69|227,271.70|
|2025-02|-4.6347|33.3543|1.398353|0.678221|446,870.02|303,076.69|
|2025-03|68.3637|93.1283|1.147090|0.777981|752,367.03|585,326.99|
|2025-04|-36.7812|-8.3041|1.450453|1.128424|475,637.29|536,720.71|
|2025-05|10.0004|-4.9332|0.864240|0.975229|523,203.01|510,242.99|
|2025-06|5.2070|-15.4295|0.803849|0.783937|550,446.43|431,515.23|
|2025-07|26.3534|37.5322|1.088473|0.853294|695,507.63|593,472.38|
|2025-08|21.0664|-1.4700|0.813851|0.694454|842,025.81|584,748.14|
|2025-09|42.5716|56.4235|1.097157|0.761925|1,200,489.86|914,683.65|
|2025-10|36.5716|37.4628|1.006525|0.766897|1,639,528.47|1,257,349.51|
|2025-11|-16.0976|-9.2461|1.081660|0.829522|1,375,604.40|1,141,093.73|
|2025-12|62.5733|62.5727|0.999996|0.829519|2,236,365.46|1,855,107.18|
|2026-01|19.1488|16.6212|0.978786|0.811922|2,664,602.92|2,163,448.86|
|2026-02|64.0273|64.0273|1.000000|0.811921|4,370,676.67|3,548,645.67|
|2026-03|34.9718|7.9794|0.800015|0.649549|5,899,180.91|3,831,807.45|
|2026-04|46.0753|66.9102|1.142631|0.742195|8,617,246.65|6,395,677.69|
|2026-05|-2.1576|-1.6823|1.004858|0.745801|8,431,317.76|6,288,084.12|
|2026-06|6.5823|9.9652|1.031740|0.769473|8,986,291.51|6,914,704.51|
|2026-07|-27.9054|-34.6920|0.905866|0.697039|6,478,628.85|4,515,854.58|
|2026-08|-6.0598|2.5166|1.091296|0.760676|6,086,038.96|4,629,501.32|

B leads through Nov2024 at1.291368× S0 capital. December’s0.620786× relative factor erases that advantage (year-end0.801663×). January2025’s0.605010× compounds it to0.485014×. B still earns+135.3173% in January; S0 earns+288.9478%, so positive absolute return is insufficient. February/March/April recover relative capital to1.128424× by Apr2025. The May/June/August weakness then brings B to0.694454× by Aug. Near-identical December2025 and February2026 returns preserve the existing smaller base rather than repair it. March2026 compounds another0.800015× relative drag, down to0.649549×; April recovers to0.742195×. July loses relatively again; August improves but ends0.760676×.

Largest negative relative monthly factors are January2025(.605010), December2024(.620786), March2026(.800015), June2025(.803849), August2025(.813851), May2025(.864240) and July2026(.905866). This ordering measures multiplicative divergence, not additive dollars lost by individual episodes. Full exact starts, ends, fees, fills, turnover, return differences and logarithmic relative contributions are in roi-monthly-divergence.csv. roi-windows.csv supplies all8A–D/E1–E4 comparisons; local window DD is not the global criterion.


The concentration is also visible in actual native activity, rather than winner counts alone:

|Month|S0/B BTC starts|absent S0 / new B starts|B BTC/SOL fills|B SOL add fills / notional|entry-sizing rights events / levels|
|---|---|---|---|---|---|
|2024-12|5/4|2/1|19/1|1 / 191230.00|1/1|
|2025-01|5/5|2/2|23/15|7 / 1315100.00|1/1|
|2026-03|9/5|7/3|21/0|0 / 0|1/2|
|2026-07|10/5|7/2|16/8|4 / 310060.00|5/8|

December’s4Bparents versus5S0include2missing originals and1new date; January has equal5parents yet2different dates, so counting trades alone misses its timing deterioration. B’s lone December SOL fill is an addition; there is no SOL exit fill that month, so its added exposure carries into the next month. January includes7SOLadd fills/15SOLfills overall, showing the portfolio remains coupled to carried and renewed rights. March2026 shrinks9S0starts to5Bstarts,7original dates absent and3new dates, while actual B SOL fills are0despite a saved entry-right activation with2levels. Rights are permission, not a fill or economic hedge. July similarly has10S0starts versus5B,7absent and2new, with4actual SOL additions. These `entry-sizing-audit.sol_right_activations` counts are only the entry-sizing export’s events, not an assertion that every later management/TP right activation is exported there. S0 comparable rights are unavailable in the allowed set. Exact24month activity is in roi-native-month-activity.csv; no native asset PnL is inferred.

Terminal convention is explicit: last native interval equity S06086634.57861444 and B4629999.26206236; post-boundary TOTAL S06077107.23887483 and B4622034.27336437. Boundary closing fees9527.33973961 and7964.98869799 explain their respective equity-to-cash bridges here. B/S0 post-settlement capital ratio differs slightly from the preterminal monthly ratio. Monthly returns never silently use post-settlement cash.

## 3. Reentry mechanism and all missing/changed calendars

The41terminal regime latches lead to83weak daily refusals and41allows;9latches allow without a weak refusal. Saved wait-to-first-fill duration totals83.03055556days, including ordinary1–2minute execution latency. This is the sum of these disjoint saved latch waits, not all time flat in the portfolio. S0 has105BTC parent start days; B77. There are51same-day matches,54absent S0 days and26new B days. Of the54absent days,50fall inside recorded waits (28historical losing and22winning ex-funding labels);34/41/66/69 are the4outside-wait absences and all are historical winning labels. All57S0 BTC winners are retained in roi-all-S0-BTC-winners.csv, including31same-day and26missing. No missed-winner profit is summed as a recoverable portfolio amount.

The recorded decision feature is `d=(completed_daily_close−EMA)/ATR14`. All83weak refusals have `abs(d)<0.5`; all41allows have `abs(d)>0.5`. No boundary-equality sample exists, so saved events alone do not prove strict-vs-inclusive source semantics. Weak-side can flip while latched. Exact raw close/EMA/ATR, side, timestamps, signed distance and margin to0.5 are in roi-decision-inputs.csv. The41intervals in roi-waits.csv include every weak feature sequence, the final accepted close/EMA/ATR, missing original numbers, dates, and S0/B actual portfolio returns on each fixed S0 episode window.

A new B start is not the same S0 trade executed later: it can have another side, entry mark, capital size, lifetime, SOL rights and exit. roi-missing-S0-BTC.csv deliberately calls its later entry a temporal neighbor, not a matched counterfactual. Input fields are empty for the4outside-wait cases because the allowed frozen event export has no gate evaluation on those days; absence is not invented as a weak-band refusal. A same UTC date also does not force the same exact clock or exposure.

The26new B dates are:

|B start UTC|side|actual Q|
|---|---|---|
|2024-10-07T00:01:00+00:00|1|0.742|
|2024-10-13T00:01:00+00:00|1|1.790|
|2024-12-30T00:01:00+00:00|-1|7.339|
|2025-01-04T00:01:00+00:00|1|8.268|
|2025-01-16T00:01:00+00:00|1|9.684|
|2025-03-29T00:01:00+00:00|-1|47.130|
|2025-04-22T00:01:00+00:00|1|26.485|
|2025-06-08T00:01:00+00:00|1|20.097|
|2025-06-22T00:01:00+00:00|-1|17.341|
|2025-06-26T00:01:00+00:00|1|22.184|
|2025-08-08T00:01:00+00:00|1|14.959|
|2025-08-20T00:01:00+00:00|-1|23.209|
|2025-08-25T00:01:00+00:00|-1|33.937|
|2025-09-12T00:01:00+00:00|1|24.427|
|2025-10-02T00:01:00+00:00|1|42.433|
|2025-10-30T00:01:00+00:00|-1|75.104|
|2025-11-11T00:01:00+00:00|-1|93.438|
|2026-01-05T00:01:00+00:00|1|111.52|
|2026-03-07T00:01:00+00:00|-1|236.044|
|2026-03-16T00:01:00+00:00|1|287.155|
|2026-03-22T00:01:00+00:00|-1|404.011|
|2026-05-23T00:01:00+00:00|-1|397.30|
|2026-07-14T00:01:00+00:00|-1|379.144|
|2026-07-21T00:01:00+00:00|1|252.801|
|2026-08-13T00:01:00+00:00|-1|271.865|
|2026-08-19T00:01:00+00:00|1|321.238|

## 4. Every profitable original BTC input that lacks a same-day B parent

The table gives original day, frozen ex-funding label (a historical cohort annotation), actual decision signed ATR distance when available, elapsed hours to the next B start, and **portfolio** return during the exact S0 episode interval. None of these label amounts is an incremental portfolio return; intervals can overlap, so they are not summed or multiplied together. All raw feature inputs and exact window values are in roi-missing-S0-BTC.csv.

|BTC# / original start|label ex funding|d on original day|hours to next B|S0 window%|B same window%|
|---|---|---|---|---|---|
|9 / 2024-10-12|2,700.58|0.402683|23.983|14.4828|19.7518|
|16 / 2024-12-23|8,083.46|-0.209896|48.000|13.8287|-0.2049|
|18 / 2024-12-27|14,726.42|-0.127525|72.000|16.1297|-0.1893|
|19 / 2025-01-03|44,845.99|0.332774|23.983|16.7158|12.5802|
|21 / 2025-01-15|64,937.50|0.176282|23.983|15.8832|5.2982|
|33 / 2025-03-27|88,692.71|-0.111295|48.000|8.5933|0.0000|
|34 / 2025-04-03|164,102.11|no recorded gate|192.000|4.3639|-18.1701|
|40 / 2025-04-18|57,620.55|0.223998|96.000|12.1362|0.0000|
|41 / 2025-05-06|78,125.74|no recorded gate|456.000|15.4222|-0.0307|
|44 / 2025-06-07|76,960.91|0.371763|24.000|17.4190|10.6552|
|48 / 2025-06-20|66,818.79|-0.053828|48.000|13.4845|0.0000|
|49 / 2025-06-24|96,384.64|0.273012|47.983|16.9712|9.2924|
|53 / 2025-08-07|102,582.75|0.103801|24.000|12.1790|5.2540|
|55 / 2025-08-19|134,135.38|-0.088561|24.000|21.3478|-0.2599|
|57 / 2025-08-24|124,450.87|-0.168422|24.000|15.8474|0.0000|
|61 / 2025-09-30|317,587.07|0.427118|47.983|24.4676|7.3159|
|65 / 2025-10-29|303,106.54|-0.023513|24.000|20.8115|6.0242|
|66 / 2025-11-12|236,248.48|no recorded gate|336.000|14.0507|-0.1832|
|68 / 2026-01-03|111,006.72|0.126369|47.983|3.4315|-0.5575|
|69 / 2026-01-10|399,367.90|no recorded gate|240.000|13.7064|14.1198|
|76 / 2026-03-06|984,792.25|-0.135759|24.000|27.7033|0.0000|
|78 / 2026-03-13|727,446.94|0.005872|72.000|13.3184|8.0472|
|79 / 2026-03-20|729,382.25|-0.365933|48.000|14.9310|8.0374|
|89 / 2026-05-18|599,990.01|-0.150447|120.000|6.5283|1.9091|
|96 / 2026-07-18|715,654.17|0.007099|72.000|8.8664|2.9876|
|104 / 2026-08-18|199,669.42|0.411585|24.000|4.1325|4.8662|

December2024 weak shorts16/18 at−.209896/−.127525ATR are followed48/72hours later by B entries; the later16neighbor is a long. S0 fixed-window returns+13.8287/+16.1297% compare with B−.2049/−.1893%. January19/21 begin at+.332774/+.176282ATR, delayed roughly24h; original windows+16.7158/+15.8832% versus B+12.5802/+5.2982%. These concrete missed/delayed inputs coincide with the largest early compounding damage. They cannot alone account for the whole month.

March2026 BTC76 is especially instructive: Mar6 close70847.6, EMA71339.93762283606, ATR3626.5642634366295 gives d−.13575869; B waits until Mar7 d−.84807550, with new236.044BTC parent. Original76’s window has already ended atMar7 00:00, before B’s00:01 entry: S0+27.7033%, B0%. BTC78 waits72h from+.00587215ATR and79waits48h from−.36593256ATR; their windows+13.3184/+14.9310% compare B+8.0472/+8.0374%. Those facts support a latency/opportunity mechanism, not a future-optimized threshold recommendation.

Not every absent winner is harmful. BTC9 waits about24h (+.402683→+.703985ATR), yet B’s actual same-window portfolio return19.7518% exceeds S014.4828%. BTC104 waits24h (+.411585→+.538228ATR), yet B4.8662% exceeds S04.1325%. Outside-wait69also has B14.1198% versus S013.7064%. Same-day absence by itself is not a causal loss estimate.

## 5. Useful waits, harmful waits, and mixed intervals

* Sep17–18 2024 waits one weak day d−.296339 then accepts+.544487ATR. Original BTC4 portfolio window−22.9779% compares B−.4394%. This is strong local protection, with changed direction and capital.
* Feb4–5 andFeb21–22 2025: weak positive distances+.194883 and+.048910 lead to accepted shorts−.529110/−.534857. Original25/27windows−19.48/−9.12% compare B0/0%. This supports suppressing weak reversals, without claiming avoided label dollars.
* Mar24–27 2026: weak+.057295/−.054934/+.203307 then accepted short−.622181. Original80/81/82windows−1.56/−5.58/−10.95% compare B0/0/0%. Useful local selectivity, still not additive returns.
* Apr13–22 2025 is the longest wait (9days+1minute): nine weak distances alternate around EMA, then+.962359ATR allows. Original36–39have negative labels and portfolio windows−10.34/−7.70/−6.44/−11.79%; B−.35/0/0/0%. The same wait rejects BTC40 at+.223998ATR; S0’s+12.1362% window endsApr21 14:30 before B entersApr22. B0%. The April month improves overall (−8.3041% vs−36.7812%) even though this winner is missed. This mixed wait is evidence against blanket removal of the gate.
* Mar5–7 2026 mixes loss75and winner76; both B0%. Original75−14.58% and76+27.70% show that the same wait suppresses both sides of whipsaw. No label-profit subtraction can rank this as an isolated economic module.
* Jul17–21 2026 mixes loss95and winner96. Weak−.051749,+.007099,+.455992,+.393106 finally+.637629allows. BTC96original+8.8664% versus B+2.9876%; entry delayed72h from its original date. The new B252.801BTC entry is materially different from S0469.354BTC.
* Jul11–14 2026 is a counterexample to loss-label success: original92window−1.78% versus B−.12%, but93−3.42% versus B−15.18%. Delayed B exposure hurts the latter window despite both skipped original labels being losers.
* Aug6–13 2026 is another counterexample: seven refusals include+.489656ATR just under threshold, then−.507385 allows after a side switch. Original102window−3.00% versus B−.20%, but103−1.18% versus B−6.45%. The seven-day wait cannot be called uniformly protective.
* Oct5–7 2024 rejects original losing7, but S0−5.53% versus B−13.85% on that window. Conversely Sep11–12 2025 original59has a negative asset label but S0 portfolio+47.17%, B+59.05%; asset labels and overlapping portfolio outcomes are different objects.

All figures are in roi-waits.csv; the selected examples include both favorable and adverse cases. No exact whole-latch return is claimed: the allowed smaller artifacts export fixed S0 episode windows and monthly/window endpoints, not native equity at every latch timestamp. Reconstructing arbitrary latch returns would require another authorized saved-receipt read, not interpolating these endpoints.

## 6. Capital sizing versus calendar; six required counterexamples

Of51same-day BTC matches,39quantities differ:29smaller,10larger,12equal. B/S0 quantity ratio spans.4587913163–1.2983425414. For BTC29 and67 the change is nearly exact capital scaling:29Q27.699/40.841=.67821552 versus entry equity ratio.67822113;67Q140.739/169.664=.82951598 versus equity ratio.82952011. Their quantity/equity residual ratios are.99999173 and.99999503. Both retain almost identical normalized portfolio window returns; their smaller absolute gains are predominantly a smaller inherited base in this observation, not a missed signal.

Do not generalize proportional sizing everywhere. BTC84onApr2 2026 has equal440.619BTC despite B/S0 equity.64954907 (quantity/equity ratio1.53952958). BTC94also has equal265.331BTC at capital ratio.67827210. These are compatible with a binding notional cap/other native admission differences, but the derived ratio alone does not identify the binding cause. roi-sizing-capital.csv preserves all51actual same-day pairs; it never imposes S0 quantities on B or assumes every size difference is capital only. All77B parent planned and filled quantities match with zero canceled quantity in the frozen sizing export; calendar change is the more important distinction than artificially holding size constant.

|Counterexample|original interval|S0 Q|B same-day Q|S0 portfolio window%|B portfolio window%|
|---|---|---|---|---|---|
|SOL1|2024-10-03 → 2024-10-05T00:00|n/a|no BTC same-day parent|13.9424|15.4005|
|BTC29|2025-03-04 → 2025-03-10T00:00|40.841|27.699|22.2119|22.2119|
|BTC40|2025-04-18 → 2025-04-21T14:30|27.283|no BTC same-day parent|12.1362|0.0000|
|BTC41|2025-05-06 → 2025-05-08T01:01|27.828|no BTC same-day parent|15.4222|-0.0307|
|BTC67|2025-11-26 → 2025-12-02T00:00|169.664|140.739|18.8637|18.8635|
|BTC96|2026-07-18 → 2026-07-21T07:40|469.354|no BTC same-day parent|8.8664|2.9876|

BTC29/67 survive with almost unchanged normalized returns but less capital. BTC40is the clear flat-window missed winner described above. BTC41is outside every recorded wait; originalMay6–8portfolio+15.4222%, B−.0307084%, B native equity538921.00930638→538755.5152021. The next B start isMay25,456hafter the original start; this temporal neighbor is not proof that the gate remained latched19days. Calendar/position occupancy changed, and the missing daily gate field must stay unknown.

BTC96has a genuine3day later B entry while its original episode is still running; B’s+2.9876% proves some participation, not total omission. SOL1’s `candidate_same_day_BTC_parent=False` is a BTC-parent date test and **cannot establish a missing SOL cycle**. Actual B native SOL fills areOct3qty1000at140.09, Oct4qty54.5at136.73; both closeOct5at143.12, fees77.0495+4.09848175+78.716+4.290022. Its actual same-window portfolio return+15.4005% exceeds S0+13.9424%; asset native net and signed funding remain UNKNOWN. These native SOL observations directly contradict any reading that B removed SOL1 because the calendar-match cell is false.

## 7. Drawdown tradeoff remains real

Both S0 and B have complete1051199native settled receipts and0missing. Global percentage DD improves8.6715044051points but remains above50. B’s maximum-percent DD isOct3 2024: peak14743.45772484 at04:01, trough6253.37707805at15:45, loss8490.08064679. S0’s peak13426.67432110Sep14to4530.57414701Oct3 is66.2569%. At the late large-capital peakJul6 2026, B maximum equity7290323.10477185 falls to3613503.497695 onAug19, a50.4342476216% local drawdown, versus S0’s maximum-dollar drawdown3818310.32850109/40.7855906323%. B’s maximum-dollar drawdown3676819.60707685 is only modestly lower in dollars despite much smaller capital. It is not merely an early-history global-DD issue; later drawdown also violates50%. None of this justifies restoring all blocked risk to rescue ROI.

## 8. One fixed0.25ATR gate-timing precheck; no new economics

A single prespecified comparison uses the already exported completed-daily states within each of the41actual B latches: first observed `abs(d)>.25` versus the actual`.5`allow signal. It advances a gate condition in21latches, leaves20unchanged, totals1200hours of earlier gate eligibility, and has a216hour maximum. In6latches, the earlier`.25`side differs from the eventual native`.5`side. This sum is a timing descriptor, not days of profitable exposure or an implementable branch replay; after an earlier entry all later states, exits, rights, capital and latch calendar can change.

Concrete observations: December16would first qualifyDec24short(−.265919ATR),24hbefore the actualDec25long;18would qualifyDec28short(−.447968),48hearlier. April13’s+.281000would qualify immediately,216hearlier, exposing the very whipsaw interval where B protected capital. March5’s+.345249would qualify a long48hbefore the actualMar7short; it does **not** directly recover the profitableMar6short76. March78has no earlier`.25`eligibility (weak+.005872,+.121709,+.210140 then+.695714); March79advances48h. July96’s latch would qualifyJul19+.455992,48hearlier than actualJul21, still1day after originalJul18start. A global threshold reduction therefore changes both good and bad cases and cannot simply restore missed S0 winner dates.

All41feature timestamps/sides appear in roi-fixed025-gate-timing.csv/json. No other threshold was compared, no winner used to select`.25`, and no fill, portfolio TOTAL/DD, fee, or signed-funding result was computed. The diagnostic supports evaluating a more nuanced causal rule only; it does not recommend`.25`or establish either economic target.

## 9. At most two causal ROI-recovery hypotheses — NOT TESTED PORTFOLIO ECONOMICS

These are alternatives for a separately authorized future design, not recommended parameters, not orders to run, and not two additive improvements. No alpha/K/P selection, prediction fit, grid, synthetic portfolio replay, estimated TOTAL, or win claim occurs here. A future test must freeze its rule before unseen data, use the full original causal prehistory/native capital/lifecycle, preserve every episode/counterexample and native DD/fees/funding coverage, and stop if either50/90goal fails.

**A. Replace complete weak-band exclusion with a bounded probationary entry.** Motivation: materially profitable original inputs appear close to EMA—BTC40(+.224ATR),76(−.136),96(+.007)—and their actual windows are fully or partly missed. Permit a small predeclared fraction of the normal causal size on an otherwise valid weak-band signal; allow one top-up only after a later completed daily signal confirms the band and the existing native episode can legally increase. Keep existing native risk/admission, rights and management attached to actual filled quantity. Do not force historical S0 size or restart a closed parent to catch up.

```text
on_completed_daily(signal, native_state):
    if existing_native_eligibility_fails: return
    d = (signal.close - signal.ema) / signal.atr14
    if not waiting_after_regime: use_original_entry_path(); return
    if strong_band_in_signal_direction(d, signal.side):
        submit_native_size_from_current_capital(normal_fraction)
    elif no_probation_attempt_for_this_latch:
        submit_native_size_from_current_capital(predeclared_alpha)
        mark_probation_attempt_durably()
    # Only actual fills create/scale rights; no synthetic cash or S0 quantity.
    # Later top-up is native-risk checked, bounded by original parent risk,
    # and allowed only if source lifecycle supports it without duplicate entry.
```

Tradeoff: protection in28loss-label waits can deteriorate, especially alternatingApr13–22 andMar24–27. DD already57.5854%, and increased weak-signal risk could worsen it. Smaller base examples29/67 will not be repaired merely by partial participation; source/native ownership for top-up must be proved before implementation. The saved evidence motivates the binary-to-fractional hypothesis only; it does not measure an optimal alpha or a favorable portfolio result.

**B. Keep the full band for reversals, but add an independently frozen persistent-sign release.** Motivation: prolonged weak-but-same-sign runs can mature only after the profitable S0 window (December18, March76, BTC40). In contrast, alternating weak signs inApr13–22 andMar24–27 contain many losing starts. Use completed daily sign history since latch, require predeclared consecutive-session persistence, and allow normal native entry only when persistence is met or the original strong band permits. This is a causal duration/persistence criterion; it never asks whether an original future episode becomes a winner.

```text
on_completed_daily(signal):
    if waiting_after_regime:
        d = (signal.close - signal.ema) / signal.atr14
        signed_streak = update_from_completed_daily_sign_only(d)
        release = original_strong_band_condition(d)
        release |= streak_in_current_signal_direction >= predeclared_K
        if release and original_native_eligibility:
            submit_original_native_parent_sized_from_current_capital()
```

Tradeoff: K>1still misses fast original76, a1day short episode; K=1collapses much of the gate. Slow persistent losses may pass despite never reaching.5ATR. The December16side flip can reset persistence and still lose a winning short. Existing position/calendar divergence such as41remains unresolved. Thus the current sample cannot establish a K that recovers90%profit while staying below50%DD, and no K is selected from these labels. This alternative may preserve some alternating-regime protection, but economic success is UNKNOWN.

## 10. Reproducibility and limits

`python3 reports/b-band-postmortem-20261023/roi-analyze.py` uses only the named frozen CSV/JSON/Markdown plus the original label CSV, with standard-library Decimal arithmetic. It writes derived roi-*.csv/json in this folder; imports no trading/native module and has no network path. Selfchecks prove exact B fee/turnover/fill-audit parity, independent S0/B aggregated-row asset counts and exact native commission sums,77parents,41waits/83refusals/41allows,131original episodes,54missing/26newdates, monthly multiplicative bridge, and observed feature separation. All12pass. No testing framework or large trace duplicate is added.

Input hash changes should halt reuse pending explicit review. roi-file-manifest.json pins this report/script/output set after creation. No input artifact is overwritten. Native asset net/funding are UNKNOWN; historical fill-label numbers are not relabeled native account PnL. Whole-wait equity, binding sizing constraint, signed funding attribution, and an ROI-recovery portfolio remain unproven. The decision is retain immutable S0 and the valid B negative result; hypotheses await separate authorization.
