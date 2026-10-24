# Next BTC experiment eligibility — fixed closed-H4 counter-swing

Decision: **NOT_ELIGIBLE_FOR_NEW_FULL** from this cheap screen. Actual cancellation opportunities exist, but the paired frozen evidence does not justify another full attempt or support the required combined profit/DD improvement. No new budget is requested.

Read only actual R3 saved report/order-cache/fill-audit,83native split parents, attribution-cycle boundaries and saved BTC closedH4bars. Rule fixed before inspection: LONG closedH4close<previous closedH4low; SHORT close>previous closedH4high. Require bar.available_ns after first actual fill and while the second LIMIT is already pending. First possible cancellation decision is strictly next M1; require that time strictly before actual second terminal/first positive TP. Same-timestamp opportunities are excluded. Contiguous H4 predecessor checked. No future pivot, first-entry filter, offset search, new fill or matching.

83parents/83second LIMIT orders;5parents have an opportunity,4would cancel a later actually filled child,1was already ultimately unfilled. Earliest eligible decisions UTC:

|cycle|side|first next-M1 cancel opportunity|later actual second fill|qty|frozen second fill-net, ex funding USDT|
|---|---|---|---|---:|---:|
|8|LONG|2024-10-13 04:01|2024-10-13 14:47|.434|+1196.52108|
|25|SHORT|2025-02-22 04:01|2025-02-22 12:10|.947|+2296.09553|
|35|LONG|2025-06-08 04:01|none, ultimately canceled|0|0|
|41|LONG|2025-08-17 00:01|2025-08-18 01:36|.788|−463.96925|
|81|SHORT|2026-08-12 04:01|2026-08-12 09:20|5.878|−1868.41728|

**FROZEN_DIAGNOSTIC_NOT_CANDIDATE_PNL**: attribute each actual second-entry cashflow plus its qty/total-entry-qty share of actual exits and native exit commissions; subtract actual second-entry native commissions. All quantities and exits are observed; each cycle exit qty exactly equals entry qty. No signed funding allocated, no endogenous capital/compounding, changed target lots, changed future admission or cancellation-ACK latency modeled. These figures describe actual filled legs; removing them is not a new native result/TOTAL.

The affected filled second legs sum to **+1160.230074135...USDT** actual frozen fill-net: the rule would discard two larger winning-leg contributions as well as two losing ones. This does not show a positive aggregate paired fill-net advantage. Global R3peak→troughJul6→Aug19 overlaps parents72–82; only81 has an opportunity with later filled qty. Ten other global-DD parents receive no direct entry-order change. The one relevant actual losing second leg contributes−1868.41728USDT exfunding; that is a narrow diagnostic benefit, not evidence that globalDD68.6% becomes<=50% or that the large90%-profit deficit is repaired. Economic effects of earlier foregone profitable legs on later native equity are uncomputed and cannot be inferred by adding frozen dollars.

Therefore stop this direction at screening. Do not launch an amended run or present a hypothetical repairedTOTAL. P+fee-floor is also not admitted here: no causal evidence in this check links global R3tail to an old positiveTP2 being moved farther; root's fixed attribution remains the authority for that gate. No SOL gate is reopened.

Artifacts: next-eligibility-parent-opportunities.csv covers all83parents; next-eligibility-frozen-second-attribution.csv contains4actual filled-leg diagnostics; next-eligibility-summary.json records pins/counts/timings. Source report SHA25698cfbdfddb33ea9aaeb1fe91274d2a441f73a6e13f96fcafbf02854c025dd59e, source family frozenec2a958 as root supplied. No engines, native short/full attempts, product edits or network actions. All3authorized full attempts remain spent; this note grants no new run permission.
