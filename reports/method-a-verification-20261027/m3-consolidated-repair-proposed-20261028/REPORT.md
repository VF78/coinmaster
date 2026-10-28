M3 consolidated DATA proposal — no native qualification

Readiness: PROPOSAL READY FOR REVIEW; NATIVE COMMAND/EVENT WITNESSES UNKNOWN. The failed attempt is immutable. Native constructors/runs, product/source changes and runtime claims: zero. M3 retry remains unauthorized; budget stays8/18. M4–M8,3prefix and2full slots are not repair spares.

Selected candidate: M3_DATA_CANDIDATE.json, SHA256 96cf5d004856e06742a88a0e61534d567deb373c41f9c8c705dd3eb275a802ba. Source DATA SHA ae29a508bd34821b7d909ea07d40e22260290eb889422fcd72f4377de647d0fc. PATCH.json contains four depth replacements and one quote insertion:

-66s BTC bid116.875→116.874;67s BTC bid116.250→116.251.
-68s prepend BTC107/107, bid116.251/ask1000 before existing SOL quote.
-72.5s and73s SOL ask.1→.2 together.

All original prices, marks, timestamps, phases, selections and witnesses are preserved; no fee/logic/parameter/M2/product changes. Input count changes139→140, quote count56→57 and BTC quote universe24→25 (SOL32 unchanged); future prepared input bindings, quote epochs/hashes, root gates and focused static count expectations must be regenerated for this candidate. Original source/attempt references remain immutable. Original139 inputs were audited in full:78 marks,4 daily signals,1H4,56 quotes/112 sides. INPUT_COVERAGE.json lists every quote and prior same-price depth, including revisited prices.

Installed stock semantics

engine.pyx SHA eb404e3558cf00ab9a13e3a1c67b05aab1d1d02647ac67409faa8350d33a1fbb: QuoteTick updates the L1 book without clearing consumption(4550–4579); consumption is per side/book-price and resets only when remembered original size differs(6416–6547). A different price does not erase another price's remembered consumption. Maker prices differ from consumption book prices(6931–7008). IOC remainder is canceled before exhausted-market slip(7432–7440); a terminal partial IOC cannot be assumed to resume on the next quote.

matching_core.pyx239–281 sorts BUYs descending/SELLs ascending, stably at equal price, and snapshots orders before matching. engine.pyx5855–5924 and6938+ temporarily alter core prices for maker fills; do not assume several crossed maker levels fill in one first iteration. Pending commands cause additional book-restored iterations(1890–1925). The inserted BTC quote explicitly restores iteration before CAP sizing, without advertising fresh size or depending on an incidental command.

Analytical phase coverage (all later fills are expectations, not native observations)

|Phases/time|Consumption, quantity and chronology review|
|---|---|
|0–3 first entry/passive/full|Repeated100/depth1000 is retained capacity, not replenishment. First BTC buy275 and later99.7 buy275 use distinct ask prices; total550. Audit native observed first/full gates remains controlling.|
|61–64 stress/SOL entry/protected/preload|BTC native pre-stress total550; SOL short210.9 at100 uses bid side. Repeated SOL100/depth1000 retains789.1, no extra entry intended.64SOL132.9 ask10 is preloaded and unconsumed.|
|65/66/67 BTC TP phases|TP0=116.875; candidate66TP1=116.874;67 older TP1 must consume.001 before TP2. Exact67TP2 timing remains unknown; desired remainder116.250 is retained. Total cumulative TP1 remains116.875, never116.876.|
|68CAP_PARTIAL/69CAP_DONE|Added BTC quote retains any67unused116.250 and enables TP2 before SOL quote. Then550−350=200BTC. Expected CAP78: IOC10@132.9 then separate residual68 at69 depth1000, leaving132.9SOL. Native sizing, partial-terminal and residual command payloads still required, including source-book freshness and the exact CAP pending/inflight lifetime/chronology.|
|70HEALTHY_DEFER|BTC107 bid199 resets116.251, removes199 from200→1. TP2 cumulative filled315.250, leaves1; native cumulative total must include prior116.250. SOL reduction waits for SOL quote.|
|71TINY_PROTECTED/72RETIRE_ZERO|SOL128ask132.3 then.1 are different sizes:132.9→.6→.5. Proportional integer rights6lots=1/1/4 then5lots=0/0/5. Retired TP0/TP1 each retain actual native.1.|
|72.5LATE_TP0/73LATE_TP1|Original same60/.1 fails second replenishment. Candidate advertises.2 once, then repeats.2: totalavailable.2, TP0.1@80 before TP1.1@60, TP2@20 unmarketable. Both fill by73; exact split between72.5/73 or settle iterations UNKNOWN. No residual fresh.1 remains for an unintended CLOSE@60. A73-only.2 patch would create that hazard.|
|73.5CLOSE_RESIDUAL/74.1reject/75.6drain|SOL128 depth.3 differs remembered.1, enabling residual.3@128. Both retiring fills are strictly72<fill≤73<cancel arrival74. Native cancel rejects must refer to original cancel commands. Other protection cancellation at73.5 should drain75.5 before75.6.|
|76FIRST_PARENT_FLAT/76.5ACK|BTC107bid1 resets199; final1 drains native parent. Accepted flat/allACK and cash6011.93042250 remain UNKNOWN; same aggregate maker quantities/prices and SOL close prices are arithmetic compatibility only.|
|86400/86401 nextD1;100800–100805 short/passive/full/settle|Repeated100/depth1000 has sufficient retained capacity: BTC first SELL236.719 uses bid100, second SELL236.720 uses fresh bid100.3; total473.439. Prior BUY ask consumption is a separate side. Full second parent depends on unchanged cash/selection.|
|100861–100863 MEDIUM/SOL entry/protected|SOL long196.4 uses ask100; earlier first entry used bid100. Repeated quotes do not need new capacity. BTC99.9 is away from second-parent TP limits; no premature TP intended.|
|100864 fault;100865wait;100866.1drain;100867.1commands;100868.1capture|Fresh SOL98bid.1 supports only.1 of196.4 STOP; IOC cancels196.3 residual.100865 bid1000 resets.1; protective cancels due100866, then conservative closure can use available196.3; repeated1000 does not need replenishment. Exact native fail-closed reason, timing, commands and no healthy resume remain UNKNOWN.|

The quantities above reconcile intended inventory and explain both original replenishment defects. They do not prove cash, margin, order admission, native phase witnesses or economic qualification. build_and_guard.py ran only stdlib Decimal arithmetic, lot-grid/positive-price checks, exhaustive input counts and an exact reversible-diff guard; no miniature matcher/economic simulator or whole-suite pass claim.

Separate producer evidence requirement: EMPTY_HANDOFF_ANALYSIS.json remains UNKNOWN for complete receipt-barrier SOL orders/inflight/pending/initialized-command emptiness. Require a fresh complete native snapshot plus independently complete command/initialization high-watermark at the synchronous pre-strategy barrier, bound to parent/episodes/input epoch and ordered before first initialization; include foreign/unresolved IDs and all producers. Held-zero, old FLAT signature or complete emitted rows do not waive this gap. No implementation, replay, M2 reacceptance or budget authority follows.
