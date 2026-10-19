# ALPHA-CUSHION: cached numerical challenge

GO as a prospective analysis hypothesis; NO-GO as implementation, validated strategy or promised DD50. Only scalar arithmetic on frozen3 points; no new data, trace, estimator, model fitting, engine or PnL pass.

Define NB>=0 and protective signed NS=-sign(BTC)*signedSOLnotional. Generalized L=abs(NB-beta*NS)*a+abs(NS)*u+remaining costs handles both overhedge and same-direction SOL. For0<=c<=1 and NS=c*NB/beta it equals pure CUSHION.

Single lexicographic target rule: keep currently authorized original SOL target if complete risk/margin/Q2 check passes; otherwise choose SMALLEST feasible protective c. This preserves alpha permission whenever affordable and makes fallback identical to pure CUSHION. Do not mix smallest feasible with closest-to-original. Original target is an intention: actual holdings/pending leaves differ, so evaluate bounded actual-to-target exposure and execution costs.

Restoring alpha requires still-valid original rights, fresh opposite SOL15m confirmation and L(candidate)<=.8C plus Q2/margin availability. Opposite means against the currently protective SOL direction; this rule must not delay needed protective increases. Unknown costs/coefficients/pending bounds are UNKNOWN; empty feasible set is UNHEDGEABLE. No silent c0 fallback or unchanged-BTC DD guarantee. One native SOL NETTING owner/account only.

|Trough ns|Actual BTC NB|Actual protective SOL NS|Factor coverage|L(actual), no remaining costs|Minimum grid L, no remaining costs|C|
|---|---:|---:|---:|---:|---:|---:|
|1727970240000000000|43592.00|107984.31|3.0409|10135.32|1595.97|0|
|1749223020000000000|3102472.77|0.00|0.0000|186836.28|88276.55|0|
|1764340080000000000|15769369.58|0.00|0.0000|627179.91|473313.88|0|

First snapshot has existing SOL above300% BTC-factor coverage. The old linear expression falsely subtracts BTC-factor risk beyond neutral; absolute value correctly penalizes reversed net factor exposure. These are ACTUAL saved positions, not unavailable original authorized targets: do not label them L(original_target). Remaining costs increase these lower bounds. All3 fail C0 before costs.

This is a stronger prospective direction than unsupported CHOP filtering because it conditionally preserves original profitable alpha permissions, rather than replacing them everywhere. Control SOL fill-net+678661 is attribution evidence, NOT standalone SOL ROI. It differs from failed cap50/DD-cov by whole-position scenario capacity, no permanent cap, identical pure-CUSHION fallback and alpha retention only when affordable. No new TOTAL, selection efficacy or pathwise DD result follows. Four immediate-insurance variants already failed; pure/ALPHA-CUSHION have NOT been native tested.

Source pins and all cached numerical fields are in companion JSON. Earlier frozen challenge-cushion artifacts unchanged.
