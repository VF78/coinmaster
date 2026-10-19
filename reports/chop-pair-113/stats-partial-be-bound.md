# Partial BE slice: optimistic price-improvement bound

Only saved stats-btc-be-events.csv arithmetic; no market-data read or new path computation. Frozen candidate slice0.2125 initialBTCnotional, core0.575 unchanged in proposal only. For BEbeforeTP2 cases assume best-case BE signedexit+.11%; comparator +1.2082% if laterTP2 occurs, otherwise existing finiteendpoint signedmark. UpperDelta=.0011−comparator; elsezero. Multiply0.2125. Allcontexts includingzero remain in denominator.

| Period | Subset | n | BEfirst | LaterTP2 | Positive/negative/zero | Sum upperDelta % NB | Mean upperDelta % NB |
|---|---|---:|---:|---:|---|---:|---:|
|calibration|all|57|26|12|12/14/31|0.76030|0.01334|
|calibration|CHOP_flips2|13|9|6|2/7/4|-1.22399|-0.09415|
|holdout|all|48|25|12|10/15/23|0.40690|0.00848|
|holdout|CHOP_flips2|12|5|2|3/2/7|0.30930|0.02577|

Signed sum adds dimensionless initial-notional-normalized diagnostic deltas equally acrosscontexts; it is not money, compoundedreturn, portfolioPnL or economicTOTAL. Positive upperbounds cannot proveprofit because costs/gaps and actualtranche/nativeSOLrights are unknown. Negative aggregatebound rejects aggregatepricebenefit even under this optimisticBEassumption in this finitecomparison.

This comparator is a hypothetical frozen1.2082% TP2slice, not actualcurrentwinnerTP2(long5.5%/short7.875%) or an established alternativeexit. Futureprices after finite24h/originalexit are absent; NONE endpoint is a mark rather than an executedtrade. Core/tranchefractions have not been physicallymodeled. No threshold/fraction retuning.
