# Native known-denial type/retry — targeted review

**GO for one same-variant replacement research run.** No economic/live approval. Scope only preexisting Cache.order typed ID and known-terminal forced-close retry. No reviewer code/index edit, test rerun/fullrun or broad audit.

Exact runtime correction: import nativeClientOrderId; normalize the one forcedclose cache lookup toClientOrderId(client_order_id), preserving stringdictkeys. Capture forced_close_terminal before removing its owner mapping. At _terminal_without_fill tail, a known forcedclose terminal no longer immediately submits synchronously into the same native throttle; residual stays native and the existing nextfreshquote path remains eligible. No new timers, backoff framework, risk bypass, production risklimit or fee changes. Ordinary OrderCanceled callback/IOCpartial continuation is unchanged. Expired forcedclose terminals also use existing freshquote recovery through this same terminal helper.

ActualnativeRiskEngine fixture2submits/sec confirms originalSOL1, forcedIOCpartial0.4, genuine throttleDENIED residual0.6: exactly3orders/1denial and no recursive resubmit. After bucket refill, one freshquote submits/closes0.6: total4orders,3actualfills, nativecommissions0.20, nativeaccount9999.80, nativeflat/ordersclosed/logicalpendingclear/episode/reasonclear. A later quote creates no orders. This sequence also empirically exercises unchanged canceledpartial immediate continuation before the single denial. Type-only development fixture demonstrated recursive denial, so the small defer guard is necessary beyond the API correction.

Evidence:1focusedPASS2.54s and36conditionalmodulePASS5.00s (overlap, not37distinctcases). Exact patch, all8actualsourcepins and4development/final loghashes independently verified. No additional runtime edits beyond stated type/defer guard; nativeRiskEngine2/sec exists only in the focused fixture. Earlier failed research receipt/no-resultJSON and all historical attempts remain preserved.

PatchSHA256: b82a29982f6f8fce7414bd5152d61bf1cb67495d773c923100e5068ca499a121

Exact8pins: native-denied-type-review.json. Full historical permissions/cadence/account/economics acceptance still requires a completed valid replacement result.
