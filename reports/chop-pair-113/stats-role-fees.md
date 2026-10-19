# Fixed event role-fee sensitivity

Saved stats-joint-events.csv only. Entry taker0.055% perleg; planned winning TP maker0.020%; forced oppositeclose taker0.055%. At firstBTCevent previousnet improves0.035% initialNB; firstSOLevent improves0.035% times thefixedhedgeratio; NONE unchanged at conservativeall-taker markedcostallowance. BTC-onlysameevent improves only firstBTCevent because firstSOLevent is not a plannedBTC TP. No newthresholds, priceevents or hypothesis.

| Period | Subset | Method | n | Old all-taker mean % NB | Role-fee mean % NB | Role-fee median % NB | Positive old -> role |
|---|---|---|---:|---:|---:|---:|---|
|calibration|all|BTC_only|57|-0.20227|-0.18876|-0.30671|23->23|
|calibration|all|factor_neutral|57|-0.10397|-0.07481|0.07340|32->33|
|calibration|all|minimum_variance|57|-0.12322|-0.10039|-0.05584|25->25|
|calibration|near_slope|BTC_only|45|-0.18687|-0.17210|-0.26335|20->20|
|calibration|near_slope|factor_neutral|45|-0.16944|-0.14027|0.01638|22->23|
|calibration|near_slope|minimum_variance|45|-0.15408|-0.13080|-0.05584|19->19|
|holdout|all|BTC_only|48|-0.07074|-0.05251|0.45706|27->27|
|holdout|all|factor_neutral|48|-0.10145|-0.07173|-0.00537|21->23|
|holdout|all|minimum_variance|48|-0.09344|-0.06676|-0.03991|21->23|
|holdout|near_slope|BTC_only|35|-0.07735|-0.06035|0.13816|19->19|
|holdout|near_slope|factor_neutral|35|-0.07933|-0.04975|0.00362|17->18|
|holdout|near_slope|minimum_variance|35|-0.06924|-0.04295|-0.03384|16->17|

Allpaired unconditionalmeans remain negative under this lower stipulatedwinnerclosefee. This sustains the negative price/costscreen for the frozen firstjointTP1 rule; it does not establish that native makerexecution would occur, or exclude everyotheralgorithm. The sensitivity corrects fee-role assumptions at identical observationprices. Native fillrole, restingordereligibility, funding, executablelatency/slippage/impact remain unknown. No native tradecash/PnL or portfolioTOTAL/ROI/DD calculated.

Plannedmaker fee cannot be inferred merely because a completedclose crossed TP. A production strategy would need prior restingorder and nativefillproof; these hypothetical pricepoints remain descriptive.
