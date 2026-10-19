# One frozen adverse-tail classification screen

CSV-only direction change: one calibration-derived noise envelope, no TP retuning or market-data reads. Label is signedBTCprice at min24h/originalBTCexit, not native completedtradeprofit. Threshold is q90 of fullpath adverse magnitude among calibration endpointpositive contexts only, rawpercent because no causal entryATR is cached. Implementation would compare current adverse causally; full futureMAE is used solely to screen the outcome classes.

Calibration endpointpositive n=29; frozen q90 adverse=1.917521% from numpy linear quantile. Strict crossing > threshold. No direction-specific levels or threshold search.

| Period | n / truncated | Positive / negative | Crosses positive / negative | Negative tails caught | Positive contexts affected | Negative share of crosses | Uncaught negative n | Worst uncaught MAE / endpoint % |
|---|---|---|---|---|---|---|---:|---|
|calibration|57/24|29/28|3/12|42.9%|10.3%|80.0%|16|-1.9087/-1.2029|
|holdout|48/14|23/25|2/13|52.0%|8.7%|86.7%|12|-1.5767/-1.3125|

A higher negative-crossing rate than positive-crossing rate is evidence of price-path class separation only. Because finite negative endpoints mechanically tend to have adverse excursions, this is a modest diagnostic, not a prediction model or proof of stop profitability. It does not tell how many eventual native winners get stopped, actual fill at crossing, how a50% reduction changes subsequent equity, or whether avoiding a tail outweighs giving up recovery. Volatility confounding remains unresolved without a predeclared causal ATR envelope.

**Provisional ADVERSE-50 contract only:** once per originalBTCepisode, when observed adverse crosses the frozen envelope, request reduction of50% actual remainingBTC. No readd rights. OriginalSOLalpha and TP rules retained. InitialBTCentrycalendar/direction/size rules retained, but realized futurecompounding quantities and pendingQ2 priority require explicit native contract. No implementation or economic run authorized by this screen. A50% reduction fraction was supplied by coordinator, not fitted here.

Q2 ambiguity must be resolved before implementation: actualfilledBTC versus acceptedgroupQ, pendingsecondleg cancellation/release, nextflipNETTING obligation, in-flight reductions/UNKNOWNACK and actualremaindernotional. This screen has no orders/margin state. No portfolio TOTAL/ROI/DD or absoluteBTCquantity inference. Strongcandidate qualification requires more than correlation between adverseprice and a finite negativeendpoint; preserve the negative findings from pairedTP and CHOP-BE rather than implying this screening solves them.
