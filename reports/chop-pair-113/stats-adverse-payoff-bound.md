# ADVERSE-50: optimistic endpoint price-delta bound

Saved CSV arithmetic only. Frozen threshold1.9175212144% adverse and50% cut, no retuning. At crossed contexts assume immediate execution exactlyatnegative threshold. Upperdelta=.5*(-threshold-terminal_signed_return), otherwisezero. This compares retained fullcontext endpointprice with hypotheticalhalfcut atthreshold, before anyfees/gaps; it is neither nativecash nor tradeTPquantity model.

| Period | Denominator | n | Positive/negative/zero | Sum upperdelta % initialNB | Mean upperdelta % initialNB |
|---|---|---:|---|---:|---:|
|calibration|all|57|7/8/42|-2.504182|-0.043933|
|calibration|crossed_only|15|7/8/0|-2.504182|-0.166945|
|holdout|all|48|7/8/33|-1.069702|-0.022285|
|holdout|crossed_only|15|7/8/0|-1.069702|-0.071313|

Calibration does not support thisfixedcandidate under the endpointcomparison. Holdout also fails. A negative endpoint label is insufficient: price may cross the adverse threshold then recover to a lessnegative endpoint, making the hypothesizedcut worsen the priceoutcome. Positiveclassificationprecision must not be presented as payoffevidence.

These sums add dimensionless deltas normalized to eachcontextinitialBTCnotional; they are not money, compoundedreturn or portfolioPNL. Negative optimisticbounds cannotbe rescued by omittedextraexitfees/gapcosts. TP/reservedquantity, Q2priority, nativeSOLrights, margin and originalwinnerfulltradecashflows are not modeled. No absoluteBTCQ/TOTAL/ROI/DD inference. No market-data read or engine; no priorartifactedited.
