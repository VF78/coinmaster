# Selective zero-TP entry research — #113

One isolated native Nautilus run: canonical Bybit inputs, [2024-09-01,2026-09-01), initial10,000USDT, reserve0. Technical control and originalV0 reused after exact input/hash verification.

| Variant | Terminal TOTAL USDT | ROI | Native fees USDT | BTC/SOL fills |
|---|---:|---:|---:|---:|
| Original V0 | 3,386,491.65211338 | +33,764.916521% | 621,073.73049442 | 389 / 229 |
| Three technical fixes, original BTC logic | 3,553,011.15835738 | +35,430.111584% | 621,166.20749442 | 389 / 229 |
| Selective next-quote entry | **3,747,041.97080334** | **+37,370.419708%** | **597,517.54289494** | **311 / 221** |

Measured gain versus technical control **194,030.81244596 (+5.46102457%)**; versus originalV0 **360,550.31868996**. Fee savings versus technical control **23,648.66459948**. The remaining169,382.14784648 is changed pre-fee native cash result, including unisolated funding/other cash; do not label it all trade PnL.

105 actual native entries:45 reduced/passive and60 full/fallback.76 zero allocations omitted; all76 rights causally activated after actual entry fill and reference-price touch. Zero-level maker reductions76->0. Actual positive-gross zero fallback reductions75->73, with73 matching entry/level identities. The two remaining FULL entry plans retained volume but their next-quote short entry VWAP was lower, so the original daily close did not reach zero threshold; positiveTP2 executed, remaining native quantity closed byREGIME next day. Gross-positive is distinct from net-positive after fees; one of these two old fallback lots was negative after allocated fees.

74/76 previous maker identities omitted directly. The other two belonged to old Sep10 2025 entry, replaced on the new path by Sep5 entry with two omitted zero allocations. This is a causal policy, not hindsight selection of historical fills.

PositiveBTC reductions82->82; BTCentry count105->105, all fully filled. BTCfills389->311; SOLfills229->221, SOLadds114->110. Gross-reference/beta SOL sizing formula and multipliers preserved; realized sizes and times change with actual balance/fills/rights.

Implementation: freeze q0 plan, classify strictly next fresh q1 quote with original post-only predicate, submit one native IOC under normal current margin/admission. Passive branch omits zero allocations; full branch suppresses zero resting targets and retains daily native market fallback. Omitted rights derive proportionally from confirmed net entry fills, activated once at causal reference touch in an accepted executable paired session. No fake fills/PnL/fees. One-minute delay changes VWAP, exposure and later entry path; result is not fee-only.

89 relevant tests and one narrow independent review passed. Implementation ee8cdc3 + single correction a9c4d62. Full native run exit0; all1,051,200rows/source processed,532fills,586terminal orders,0liquidations,0terminalpositions; fees reconciled. One fresh run, no optimizer/independent repeat/pilot action/deployment.

Actual cash maximum relativeDD:58.14621682% control versus62.46697029% new variant. Full marked-equityDD unknown; runtime reporting-helper defect is outside this economic pass. Corrected summary in comparison.json.

Raw result SHA256:0ccad5771c23e380ba6115cc7bc8530b47ee39ec6fe99c08595640e17b9faee1. JSON/CSV include source/input/config/policy hashes, reproduction command, branch audit, actual fallback fills and limitations.

**Diagnostic limitation:** realBybit1m close data create synthetic zero-spread quotes; historicalBBO/L2/slippage/liquidity unproven. NOT_FAITHFUL_DIAGNOSTIC, ranking_eligible=false. Best among these evaluated variants, no global optimum/liveROI prediction. Funding model unchanged, separate native journal, signed funding unknown. Pilot remains installed81e6318,PID2009732/NRestarts0; no deploy/restart/reseal/config/orders.
