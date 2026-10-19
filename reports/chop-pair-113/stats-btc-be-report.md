# Final fixed BTC TP / break-even path check

**Mixed evidence; insufficient to claim protection or profitability.** TP1 followed by an early nominal BE return frequently precedes eventual TP2/TP3, while a substantial loss group never reaches TP1 and receives no protection. A small CHOP-only TP+BE research hypothesis is more defensible than blindly paired losing-leg liquidation, but remains provisional and cannot be sold as an established improvement.

Freeze BTC favorable close levels0.5317%,1.2082%,2.1041%; BE+0.11% favorable. All105 original BTC-derived entry timestamps/sides, synchronized entryclose anchor, observation ends atmin24h/originalBTCexit. First postTP1 completed1m close <=+0.11% is nominal BE return. The stop can overshoot and is not a fill. Actual native fees/funding/slippage can differ. No position fractions, tradecash/PnL, compounding, portfolio TOTAL/ROI/DD or production timer simulated. CHOP subset is frozen at entry using exact previous baseline flips2/7 completedD transitions with2consecutive-state enter/exit, not the near_slope detector; no filter reselection.

| Period | Subset | n / truncated | TP1/TP2/TP3 hits | BE beforeTP2 | LaterTP2/TP3 despiteBE | BEfirst + terminalnegative | NeverTP1 / negative | NeverTP1 MAE median/q10/worst % NB |
|---|---|---|---|---:|---|---:|---|---|
|calibration|all|57/24|44/29/20|26|12/8|13|13/13|-1.660/-3.704/-5.222|
|calibration|CHOP_flips2|13/5|12/9/7|9|6/4|3|1/1|-0.753/-0.753/-0.753|
|holdout|all|48/14|36/21/10|25|12/7|10|12/10|-1.712/-4.408/-5.090|
|holdout|CHOP_flips2|12/6|9/6/2|5|2/1|3|3/3|-2.062/-3.949/-4.421|

Holdout all48: TP1 occurs36 times;25 paths return to nominal BE beforeTP2. Of those,12 later reachTP2 and7 later reachTP3 on the unchanged observed path;10 finish at a negative mark. Thus earlyBE may avoid some eventual adverse price movement while also cutting many favorable tails. These counts overlap and are not quantities of realized saved/lost money. Nine paths reachTP2 beforeBE;2 hitTP1 but neitherBE norTP2 by endpoint. Calibration shows the same tradeoff:26 BEfirst,12 laterTP2,8 laterTP3,13 negative endpoints. One calibration jump already reachesTP2 on the firstTP1 close; separately recorded, not a second trade event.

Holdout fixedCHOP subset is only12 contexts:9TP1,5BEfirst,2 laterTP2/1laterTP3,3BEfirst negative endpoints. All3 neverTP1 contexts end negative. This sparse evidence leaves a CHOP-restricted partial-BE hypothesis open for a later owner-approved native test, but does not validate full-position earlyBE, a chosen reduction fraction, exact BEstop, or a higher return. Calibration CHOP has13 contexts,9BEfirst,6laterTP2/4laterTP3 versus3negative endpoints: tail-cut risk is substantial and must not be hidden by the holdout3-versus2 count.

The DD-protection gap is concrete:12/48 holdout contexts never reachTP1;10 end negative, median adverse close excursion-1.712%,q10-4.408%,worst-5.090% initialBTCnotional. In CHOP3/12 neverTP1, allnegative, medianMAE-2.062%,worst-4.421%. Nominal BE only afterTP1 cannot protect these paths. These are price movement normalized to initialBTCnotional, not account/equity drawdown.

Recommendation to coordinator: retain only as a minimal **provisional** CHOP-specific partial-management hypothesis if separately approved; reject any claim that these counts already establish benefit or meetDD30–50. Preserve original profitableSOLalpha and nativeBTCentrycalendar/size. Do not force bothlegs closed onEMAflip, and never preserveoldBTC past an incompatible nextnativeNETTINGentry. No furtherparametersearch is justified from this sameholdout.

Technical receipt: finalBTC-only read used2columns(timestamp,close), sequential8192-row batches, lowpriority/idleI/O and single-thread numerical runtime. InitialJSON export failed on numpyint64 after both complete CSVs; repaired exclusively from savedCSVs, with future script serialization fixed. PeakRSS was not persisted by the failed export; no fabricated memory measurement. No SOL/observer/nativeengine read. Prior frozen artifacts verified separately in this finish.
