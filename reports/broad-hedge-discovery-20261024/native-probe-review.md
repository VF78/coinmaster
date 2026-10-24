# Narrow independent review — native probe proposal

Current status: **PASS revised behavioral approval packet; no implementation/launch/budget approval**. Targeted re-review confirms the four initial findings below are resolved by the revised proposal. Reviewed only `candidate-native-probe-proposed.md` changed clauses, against current cached scale evidence and the coordinator's installed1.231.0 stock-liquidity finding. No new outcomes, engine/source/Project changes or physical attempts. Sections1–4 preserve the initial review evidence; they are not outstanding findings.

## 1. [P1] UNKNOWN_RISK must preserve the paired BTC obligation

Line36 currently closes SOL on UNKNOWN_RISK without NEW BTC debt. A missing close/state does not establish the explicit INACTIVE_RISK condition; closing the hedge can therefore leave the actual paired BTC exposed while erasing the obligation that an ACTIVE_RISK stop/failclosed SOL fill would create. NO_GO accounting does not make that runtime transition safe.

Concrete fix: UNKNOWN_RISK is failclosed ACTIVE-for-debt, never INACTIVE. Block/cancel increases; every actual non-BTC-caused SOL reduction while risk is unknown creates the same permanent proportional BTC debt as ACTIVE_RISK, with existing debt retained. Credit only actual BTC reduction fills, preserve the bounded next-distinct-quote debt barrier, and mark qualification NO_GO until state/protection is reconciled. Only a known completed-bar invalidation or known deadline may take the specified INACTIVE_RISK path. Test missing bar/state immediately before SOL stop/forced close, partial close and duplicate callback; no lost debt or BTC restoration.

## 2. [P1] Partial entry requires actual coverage and an absolute paired-cap ledger

Lines25–27 allow a partial IOC hedge if three target lots/stop are valid, while line48 initializes pairedBTC to Qref. Example: intended5000SOL, actual1000SOL retains only20% of intended halfVOL coverage; installing three valid small TPs does not cover the original BTC slice at the declared target. The current contract has neither an executed-coverage gate nor a mandatory BTC capacity-deficit reduction.

Concrete fix: calculate retained hedge coverage from actual native SOL fills/cache, frozen signal-time target units and actual held BTC, never intended/pendingSOL. Before a partial position may qualify, enforce a monotonically reduced BTC ceiling sufficient for that actual hedge (or mark NO_GO and follow an explicit conservative deficit/closure policy); cancel pending increases, and give no relief until deficit BTC trim actually fills. Initialize the paired slice from the actual covered/retained BTC after this reconciliation, not automatically fullQref. Require actual retained quantity to support the remaining TP rights and stop.

Specify the BTC→SOL cap as an **absolute cap from the reconciled activation anchors and executed paired balances**, not repeated multiplication of currentSOL by each BTC-reduction fraction. Example: SOL100→75 creates BTC100→75 debt; the subsequent debt fill must leave allowedSOL75, not cut75 again to56.25. Deduplicate fill IDs and preserve BTC_CAUSED provenance so cap trims create no second BTC debt, consume no new activation and create no new parent/rights. Tests must cover entry1000/5000, partial deficit trim, ordinary BTC exit during debt, and the100/75 round trip.

## 3. [P2] Three targets are an initial contract; consumed targets must not be recreated

Line42 says accepted orders must cover “three unconsumed targets.” After TP1 is filled, only two unconsumed target rights remain; after TP2 only one. A literal perpetual-three requirement either recreates TP1 or falsely fails protection and closes the hedge/pairedBTC. Line58's consumed-rights sentence is correct but does not resolve that contradiction.

Concrete fix: require three valid, native working/accepted target allocations at initial admission; thereafter require exact leaves for **all and only unconsumed rights**, plus the mandatory stop and actual remaining inventory. A partially filled level keeps only its residual entitlement; a fully consumed level remains consumed across BTC_CAUSED resize, cancel/ACK replacement, late fills and same-parent processing. Do not create another activation/cycle to regain targets. Add TP1-filled→BTC-cap-resize→replacement and partialTP1→latefill tests; TP1 may never reopen.

## 4. [P1] ONE entry IOC does not settle aggregate quote-liquidity policy

Line27 correctly prohibits entry IOC chaining, but several resting SOL TPs/stop/forced-reduction orders can still consume the same synthetic1000-unit quote independently under the stock default policy. “Next distinct quote” for debt does not by itself bound aggregate fills across all leaves on the current quote.

Concrete fix: explicitly freeze either stock Nautilus1.231.0 `liquidity_consumption=True` with proof that the actual runner/config propagates it, or a proved structural bound that **aggregate actual SOL fills across every order/reason** cannot exceed available per-side quote liquidity for each quote event and that no callback chain resets it. Use the existing engine; no custom fill engine/depth simulator. Test simultaneous ladder leaves, stop/TP races, partial protection failure and forced exits against one quote. A different monetary liquidity policy requires matched OFF control under the identical policy **inside** the proposed physical ledger. If corrected-control plus corrected-candidate cannot fit the single reserve slot, STOP/request a new explicit packet; do not hide a control or compare unlike policies.

## Other targeted checks

- Strong exit delta is honestly explicit: complete ACTIVE SOL reduction may remove the entire actual paired BTC slice, with permanent ceiling cuts and canceled split-increase rights. This is a new BTC exit/admission hypothesis, not native reproduction of the small scalar sidecar or established70/50 benefit. The owner must approve that concrete scope; current scale results do not establish its gain.
- Positive finite completed SOL ATR, lot/tick/min-notional/fee-floor feasibility, native SOL reduce-only LIMIT/protective stop/ACK APIs, signed per-asset funding and coherent observer proof are already explicit **launch blockers**. They are not yet source-ready/proven capabilities. A stop substitution by minute-OHLC accounting remains prohibited.
- Budget wording is correct: maximum4short physical attempts (OFF/B2/combined/one correction reserve, all failures counted), then maximum2full OFF/combined **proposed only**, conditional and separately owner-approved. A source/policy monetary correction may exhaust the short reserve; no implicit rerun exemption. No short/full is currently approved, and no automatic fallback from failed combined to B2 is admitted.

After these four contract fixes, refreeze the proposal before implementation review/owner budget decision. This review creates no engine, source, financial run or trading authorization.

## Targeted re-review of the revised clauses — PASS

No remaining material behavioral finding in the changed scope.

- UNKNOWN_RISK now conservatively retains ACTIVE-for-debt semantics; SOL closure cannot erase the actual BTC obligation. Known invalidation/expiry is distinguished, and existing debt survives both.
- IOC terminal actualSOL and frozen k determine absolute Bmax, with executed capacity-deficit trim required before partial coverage qualifies, including S0=0 fullBTCclose. Absolute native-cache Bmax/SOLmax and the100→75 example prevent75→56.25 recursion. BTC_CAUSED is an audit cause, not permission to ignore a real late/oversized-fill deficit. No intended/pending relief or ceiling restoration remains.
- Initial three targets are distinguished from only remaining UNCONSUMED rights. Provisional entry VWAP while IOC is nonterminal and terminal actual entry VWAP are explicitly different from first-fill price; subsequent protection replacements remain subject to cancel/ACK, consumed-right and partial-fill tests. No reanchoring after terminal or resetting the expiry clock is permitted.
- Stock liquidity_consumption=True is now mandatory for OFF and candidates, subject to runner propagation and aggregate per-instrument/per-side tests. The changed policy has a new matched control inside the four-attempt budget; original S0 absolute goals are not reset. No custom engine is introduced.

The new completed-minute risk invalidation against frozen K/O is explicitly a new causal proposal choice; H4 entry remains unchanged. It is not represented as a validated discovery parameter. Exact completed source/timestamp/price conversion and callback priority still require implementation proof before launch.

The approval packet honestly includes capacity-driven permanent BTC cuts, active SOL exits potentially closing all paired BTC, canceled increase rights and a changed parent calendar. Those are a stronger BTC exit/admission hypothesis; the small cached sidecar results do not establish its economics.

This PASS makes the behavioral packet reviewable for a separate owner decision on implementation plus at most four 4.5-month prefix physical attempts, with failures/reserve counted. It approves no attempt itself. Native APIs/ATR/lot-stop validity/ACK/funding/observer/shared-depth proof and connected tests remain launch gates. The two full replays remain a future proposal requiring successful short gates, a new freeze and separate explicit approval. No full/short budget, native70/50 claim, pilot/live or real trading permission follows from this review.
