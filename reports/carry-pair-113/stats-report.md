# Fixed causal CHOP carry-pair precheck

Analysis only; source HEAD91ec919d40ac71ff699885068599687ecfe5d9ba. No trading implementation, native backtest, optimizer, services, swaps or git mutations. Original TOTAL6077107.23887483/nativeDD66.3187802497 remains reference; new TOTAL/ROI/DD UNKNOWN.

## Decision

**No qualified carry strategy established.** The fixed causal opportunity exists, but inheriting losingBTC basis changes the TP arithmetic fundamentally. Blind3TP winner/proportional-loser cuts fail the remaining-pair compensation check. A one-shot HALF-factor carry is the most conservative descriptive lead for later owner design discussion; it is not an approved strategy, and calibration does not establish positive unconditional price payoff. Do not advance it automatically to implementation or another engine. A causal range/trend-end rule and wholeepisode/account cost boundary remain unresolved.

## Fixed universe and causal admission

48 genuine BTC REGIME residualclose events =25calibration/23later, all with inherited BTC loss. Every original oppositeBTC entry occurs exactly1minute later. Opportunityscope includes42events without existingSOL (new hedge admission legitimately allowed), plus6actualpairs. No entrytimeCHOP flag is substituted for fliptimeflag.

Before minute results root froze PRIMARY: >=2EMA34 sign flips in7completedDaily transitions includingcurrent, AND abs(completedclose−EMA34)<=ATR14; immediatecurrentbar, no hysteresis. It flags19cal/15later; exclude originalSOL notional already abovefullbeta ceiling rather than force trim =>18cal/15later=33admissible. Historicalhystereticnear_slope flagsall48; hystereticflips2 flags11cal/10later, sensitivity only. No reselection from later outcomes.

Primary BTC inheritedloss min/median/max cal−3.7636/−1.4143/−.1263%; later−3.3711/−1.7205/−.3034%. OriginalSOL exists in2rawprimarycalevents and0later; abovefullbeta excludes2024-10-05. At2025-08-24 originalSOL/BTC notional.170 vsfullfactor.577; other32admissions create newoppositeSOL. Fulluniverse originalSOL ratios2.583,.031,.087,.274,.170,1.813 show that preserving originalalpha and enforcing exactnewbetaquantity cannot generally coincide with one NETTINGSOLposition. Hypotheticaltarget isMAX(existingSOL,cover); abovefullbeta rejected globally for newcoverage, existinginventory still exported diagnostically.

W90 closedDaily beta(SOL|BTC) reused from hashed priorcoefficients, frozenatflip. Coveragefactors: half=.5/beta; full=1/beta; minvar=rho²/beta. Minvar does not factor-neutralize BTC; rho² remains distinct from beta. No frozenbeta recalculation after TP or regimechanges.

Native nextoppositeBTC episode labels: primary11/18cal winners,7losers; later4/15winners,11losers. These are factualbaseline labels, not counterfactual lostcash; skipping these rights has opportunitycost. Primary originalSOLADD links within1D8cal/0later. Daily recross towardcarriedside within7D11/19rawcal,13/15later; nextdayoppositeconfirmation13/19,10/15. These are diagnostics, never automaticexit rules.

## Exact bounded price pass

One first technicalattempt failed on an overstrict assertion equating nativeexecution to completedminuteclose. Root explicitly authorized ONE technicalcorrection. Both failure and correctedreceipt/log retained. Correction verifies native_baseline.py:856 and minute_risk.py:115: closeavailable=open_time_ms+60000. First completedminute at/after nativeREGIME timestamp is observation. Actualnativebasis preserved, nativeclose and observedclose exported; no onebarfit/shift. BTC gaps−7.261..+9.692bp, no>10bpoutliers. Observed hypotheticalnewSOL increment is NOT an actualnativefill.

Correctedpass read2genuine executionparquets once,1051200alignedrows each, [2024-09-01,2026-09-01), onlytimestamp+close; matched oldsourcehashes. 558fixedinventory1/3/7Dwindows and2589TPsnapshots. FreshMemAvailable1221260kB; nice19/idleIO/singlethread; maxRSS128120KiB (~125MiB),3.64sec. No market rereads after correctedpass. Allprimaryhorizonsuncensored. Somewindows overlap; contextcounts are dependent, not independent trials.

Marks preserve actual remainingBTCqty/basis and originalSOLqty/basis; hypotheticalone-timeSOLincrement has observedflipbasis. Subtract allocatedentryfees onCURRENTREMAINING nativeinventory, hypotheticalincrement takerentry.055%, estimatedtakerexit.055% ofbothcurrentmarkednotionals. Funding/slippage/spread/impact/rounding/margin/filldelay UNKNOWN, not zero. Historicalmaker.020%/taker.055% sourcecontext unchanged. No realizedcash, matching, compounding, portfolioaccount, DD or equity generated.

**All CSV whole_* fields mean both CURRENTREMAININGLEGS, not originalepisode/account. Prior native realizedTPcash/funding notattributable here=>UNKNOWN. RemainingpairBE is not wholeepisodeBE/equity/DD.**

## Remaining inventory marks, % currentBTCnotional

| Period | Coverage | 1Dterminalmedian | 7Dterminalmedian | 7DMAEmedian | 7DBEreach | 7DBE+10bp | 7Dmeanterminal−initial |
|---|---|---:|---:|---:|---|---|---:|
|cal18|originalinventory|−1.2435|−4.5140|−6.9678|10/18|10/18|−.9887|
|cal18|half-factor|−1.8029|−3.0776|−4.5206|12/18|11/18|−.6775|
|cal18|full-factor|−1.5265|−3.2134|−5.1778|14/18|14/18|−.3592|
|cal18|minvar|−1.8567|−2.7150|−4.6524|11/18|11/18|−.7800|
|later15|originalinventory|−1.6823|−.8787|−3.9871|9/15|8/15|−.1387|
|later15|half-factor|−1.6811|−1.3246|−3.6092|9/15|9/15|+.2819|
|later15|full-factor|−2.0380|−1.5132|−3.5894|7/15|7/15|+.7025|
|later15|minvar|−1.7929|−1.5919|−3.4695|7/15|6/15|+.5278|

No horizon is a liquidation/exitrule. Terminal−initial measures change in fixedinventory price mark including retainedentrybasis; it is not strategyprofit and omits displacedoppositeentryalpha. Descriptive7Dcoverage improvement overoriginalinventory can coexist with inheritedloss and negativecalibrationincrement. Calhalf-factor1DMAEmedian−2.4145 vsoriginal−2.9102; fullfactor−3.3081. Half preserves residualBTCfactor and smaller admittedSOLnotional; full can freeze inheriteddeficit and expose relativebasisrisk. Coverage not selected by laterreturns.

Direction split is saved stats-direction-summary.csv (cal11LONG/7SHORT, later9LONG/6SHORT). 7Dmean markchange half-factor calLONG+.3604%,SHORT−2.3086%; laterLONG+.4289%,SHORT+.0614%. Fullfactor calLONG−.8540%,SHORT+.4184%; laterLONG+1.8903%,SHORT−1.0792%. Small asymmetric samples do not justify choosing a direction using lateryear.

## ThreeTP and proportional cuts

Calibration18SOL1D MFE inverse80/50/20 reachlevels:.923526%,1.869935%,3.702551%; no calibrationwindowcensored, no fitting from lateryear. Calhits14/18,9/18,4/18; later10/15,6/15,2/15. OldSOLlevels1.040878%,2.423763%,4.224761% exported separately as comparison; BTC oldlevels.531732%,1.208177%,2.104125% measured from actualoriginalBTCbasis. Pricecrossing is not fillpromise.

At each newSOLTP, FULL UNREDUCED CURRENTREMAININGPAIR mark checked with inheritedBTCbasis/allocatedfees. Half-factor positive marks:cal0/14,0/9,0/4; later0/10,0/6,0/2. Fullfactor:cal2/14,1/9,1/4; later1/10,0/6,0/2. Medianhalf remainingpairmark atSOLTP1/2/3:cal−1.5750/−1.9459/−2.0835%; later−2.7715/−2.9414/−4.2558%. A winningSOLleg therefore usually does not compensate oldlosingBTC.

Chronology SOLTP1 then oldBTCbasisrecovery by1D:cal7/14hits,later2/10; TP2thenrecovery2/9,0/6; TP3thenrecovery1/4,0/2. This confirms some reversiblepaths, not profitable pairedtrade sequence.

Mathematically equalproportionalfractionf of bothlegs realizes f times inheritedremainingpairgross minusallocatedentry/exitfees and leaves(1−f) of each originalbasis; negativepairedmark cannot become positive through equalfractioncuts. If cutwinnerfractionfW and loserfractionfL differ, compensation requires fW×winnergross >= fL×loserdeficit + relevantfees; remainingnotionalratio scales(1−fS)/(1−fB). Samebeta ratio no longer follows. Uncutremainingbasis, nonhits, priorrealizedUNKNOWN, funding and finalretirementcannot be discarded. We did NOT simulate these reductions.

## One causal lead and factual blocker

If owner later requests an implementable design, restrict discussion to one-shot half-factor admission at fixedprimaryopposedEMAevent, actualremainingBTCbasis, MAXexistingSOL, globalfullbetaceilingrejection, frozen90Dbeta, consumedadmissionrights. Timepassing, recrossingoldprice, newequityhigh oroldsignal must not replenishrights; at most a separatelyauthorizedactualnativeBTC-TPfill may spend a distinctone-timequantityright. No607-style readds. This is a riskcontract sketch only. A causal range-end/trendbreak rule must explicitly resolve retainedlosingbasis and delayedoppositeentries; neither dailyconfirmation nor7Dhorizon is silently promoted into that rule.

Factual blocker: unconditionalcalibrationfixedinventorymarkchange remains negative forhalf/full/minvar at7D; blindSOLTP compensation predominantly negative; originalentryrights displaced; wholeepisodecosts unknown. Thus no supported ROI-preserving/DD30–50 candidate or automatic economicrun recommended. Later positive meanpricechange does not repair calibration and is not true strategyOOS: originalwinner alreadyselected on fullperiod.

## Fixed saved-result risk tails and BE latency

All marks% initial remainingBTC notional at observation; MAE is fixedinventory price-path mark, NOT DD. q10 is descriptive10thpercentile of eachcontext minimum. BE latency median onlyamongcontexts reaching remainingpairBE; failuresremain in denominator.

|Period|Coverage|D|n|Initial median%|Terminal median%|PathMAE worst/q10%|BE n;median min|
|---|---|---:|---:|---:|---:|---|---|
|calibration|original_inventory|1|18|-1.649|-1.244|-6.038/-5.476|9/18;862|
|calibration|original_inventory|3|18|-1.649|-2.956|-9.855/-7.778|10/18;873|
|calibration|original_inventory|7|18|-1.649|-4.514|-20.822/-11.475|10/18;873|
|calibration|half_factor|1|18|-1.671|-1.803|-5.389/-4.921|4/18;744|
|calibration|half_factor|3|18|-1.671|-1.587|-6.919/-6.040|9/18;2316|
|calibration|half_factor|7|18|-1.671|-3.078|-11.953/-8.802|12/18;3058|
|calibration|factor_neutral|1|18|-1.703|-1.527|-5.285/-4.974|4/18;575|
|calibration|factor_neutral|3|18|-1.703|-2.014|-8.466/-5.461|10/18;1609|
|calibration|factor_neutral|7|18|-1.703|-3.213|-12.804/-8.296|14/18;2184|
|calibration|minimum_variance|1|18|-1.677|-1.857|-5.380/-4.852|3/18;993|
|calibration|minimum_variance|3|18|-1.677|-1.952|-6.972/-5.497|7/18;2357|
|calibration|minimum_variance|7|18|-1.677|-2.715|-13.007/-8.303|11/18;2986|
|later|original_inventory|1|15|-1.864|-1.682|-8.286/-6.178|5/15;307|
|later|original_inventory|3|15|-1.864|-1.777|-10.056/-8.499|6/15;566|
|later|original_inventory|7|15|-1.864|-0.879|-14.049/-9.674|9/15;1373|
|later|half_factor|1|15|-1.908|-1.681|-6.327/-4.904|3/15;846|
|later|half_factor|3|15|-1.908|-1.624|-6.518/-6.072|5/15;915|
|later|half_factor|7|15|-1.908|-1.325|-8.022/-6.451|9/15;3809|
|later|factor_neutral|1|15|-1.952|-2.038|-4.665/-4.200|2/15;442|
|later|factor_neutral|3|15|-1.952|-2.145|-5.170/-4.494|4/15;1304|
|later|factor_neutral|7|15|-1.952|-1.513|-6.447/-4.968|7/15;2311|
|later|minimum_variance|1|15|-1.925|-1.793|-5.081/-4.219|2/15;439|
|later|minimum_variance|3|15|-1.925|-1.749|-5.419/-4.833|4/15;1302|
|later|minimum_variance|7|15|-1.925|-1.592|-5.513/-5.103|7/15;3274|

Originalinventory is an exactly matched initialinventorycomparison, including one qualifyingoriginalSOLpair; it is pure BTCremaininginventory for17/18cal and15/15later, not a freshBTC-onlynativebacktest. Remaining33oppositeentryrights and priorrealizedUNKNOWN remain excluded fromthisfixedinventoryarithmetic. All1/3/7Dprimarywindowsuncensored.
