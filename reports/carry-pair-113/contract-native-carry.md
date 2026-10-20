# Bounded single-episode native carry: contract and economic challenge

Analysis only, 2026-10-20. Canonical HEAD91ec919d40ac71ff699885068599687ecfe5d9ba verified. No source/product edit, git mutation, engine, tests, minute/archive reads, service action, order/key/account change or deployment. Economic constants below are intentionally UNSELECTED, so this is not implementation-ready.

## Strongest feasible direction

One bounded carry interval inside the existing BTC episode, with existing original SOL inventory protected from new pair trims and only incremental disposable cover receiving new SOL TPs. Skip opposite BTC signals only while causal CHOP remains true. One native account/executor, one BTC net position, one SOL net position; quantity permissions are not independent PnL books.

This cannot preserve original SOL alpha's complete economic lifecycle: mandatory REGIME group close is exactly the exit being waived. A protected quantity floor preserves existing inventory permissions, not the original exit time, native PnL, margin or future equity-based sizing. If exact original alpha economics/fill calendar remains mandatory, carrying its nonempty inventory through REGIME is inadmissible. This is an unavoidable tradeoff, not an implementation defect.

The recovery thesis must be old BTC directional continuation and/or favorable SOL residual movement. Paired TP mechanics supply no independent recovery edge. Prior negative insurance outcomes are adverse economic evidence. No new ROI/DD claim.

## One explicit state extension

At the current opposing-regime branch (domain/wave_overlay.py:386-390), choose CARRY_ARMING instead of CLOSE_ALL only when closed-bar CHOP is true, actual BTC remains, all marks/beta/native risk state are known, and the inherited-loss budget test passes. Deposit/liquidation/terminal/trail exits always dominate. Otherwise close normally.

Retain the SAME episode ID, original BTC basis, first-fill equity, cumulative fees/realized losses, consumed TP/SOL rights and original SOL clock. Record first opposing decision and every skipped opposite signal. Never submit opposite BTC, create a new shadow episode or backlog old entry signals. One carry interval per episode; recrossing cannot renew it.

Arming cancels unfilled BTC Q2/increases and unadmitted SOL adds; await authoritative terminal receipts. Late partial fills remain in the original episode. Existing BTC reducing TPs can fill and change the quantities; reconcile before new SOL increases. If CHOP ends while arming, close instead. Actual orders are sequential events, not an imaginary atomic rebalance.

Freeze B0 and S0 from signed native cache inventory AFTER cancellation/fill reconciliation. btc_initial_qty is cumulative confirmed entries, not remaining BTC; btc_target_basis_qty/reference_qty can be planning/management bases. Do not reset native BTC or SOL cost basis to the flip price. Default BTC .15/.25/.35 TP fractions do not establish selected-runtime residual: omitted-level/reference-lot variants require actual cache quantity.

Regime returns to old BTC direction: retire unused carry rights, cancel/reconcile cover adds, trim cover-only excess, resume ordinary management in old episode without BTC top-up or renewed TP rights. Carry cannot rearm in that episode. CHOP ends while regime still opposes BTC: full group close. Original trail/deposit/liquidation/margin/terminal close or exhausted loss budget: full group close. Original SOL z/holding-time exits retain priority; their 14-day anchor never resets. BTC native flat: no new cover, retire adds and close cover-only remainder; original SOL may survive only under its existing lawful TP-flat lifecycle. Clear episode only after native positions, open/inflight orders and pending submissions are flat/terminal. A late opening fill prolongs the same forced close.

## Original SOL boundary and one target

Let A be original-authorized allocated SOL quantity, H actual same-side native SOL held, C=max(0,H-A) disposable cover before competing reduction reservations. These are quantity permissions only; no second average cost, funding, equity or PnL service.

One target owner requests T=max(A,Qcover), never sums the same inventory twice. Permission adoption is not a native fill or cash profit. Original additions obey existing admission/expiry; carry cannot create evergreen alpha credits. During carry original rights already earned remain governed by original conditions; new cover grants never masquerade as alpha rights.

New SOL TPs and BTC-TP-triggered SOL loser cuts may consume C only, never A. Three new SOL TPs on all H would change original alpha exits. If A=H there is no disposable SOL TP quantity until a real incremental cover fill occurs. If original A itself violates cover/margin ceiling, reject carry and use normal group close; do not force-trim alpha to admit carry.

Crucial implementation correction: an original exit lowering A MUST lower the carry SOL ceiling by the released quantity too. MAX must not absorb the exit as a logical ownership release or silently refill it. Original physical exit gets priority. Existing conditional_hedge.py permits ownership-only exit while protection holds inventory; that behavior cannot prove original physical-exit preservation. Alpha adoption of existing C likewise preserves authorization, not counterfactual original entry fills/independent performance.

Even with these rules, original mandatory REGIME exit is waived. No floor can make exact original economic lifecycle coexist with retaining that position after its exit boundary.

## Price grants and three TPs

Before implementation freeze: causal CHOP predicate; three strictly ordered adverse BTC milestones a1<a2<a3 from immutable original actual BTC first fill; earned hedge fractions 0<h1<h2<h3<1; SOL TP price distances and lot-valid shares; original-episode loss budget R. No values are selected or validated here; do not restore ADVERSE-50 or tune on the prior check year.

Each milestone grants at most one cover entitlement. A fresh qualifying carry observation is needed; do not retrospectively release all three levels at flip because BTC entered carry already adverse. If a first-stage entry-at-arming grant is desired, declare it separately before screening and count its real cost/risk. No elapsed-time renewal. Freeze beta/conversion for carry. Only a new grant or actual BTC quantity fill can relatch a target, not every price tick.

At each target event, Qcover=floor_SOLstep(h*abs(Bactual)*PB/(beta*PS)). Margin, A floor, accepted pending leaves/Q2, lot/minimum rules and native risk bound admission. No positive valid beta/fresh marks/known ACK means no increase. Unknown is neither flat nor proved unhedgeable. Actual BTC TP can reduce cover entitlement; it never renews a consumed cover grant.

Keep old three BTC TP levels, already-filled rights and remaining target lots. Do not install a fresh three-TP ladder on B0 at flip. If all TP targets already filled, no new BTC TP rights exist. New SOL cover fills receive three reduce-only allocations whose total cannot exceed actual cover-filled quantity; TP3 consumes that grant's remainder. Further grants have IDs/quantity permissions but no private money book.

Winning TP events may request losing-leg reduction only from confirmed actual fill fraction. BTC TP can cut C only. SOL C TP can cut actual BTC. Proportional matching is exposure reduction, not a profitability test. Full loser exit is either (i) an entire-original-episode profitable close including all inventory/costs, or (ii) explicitly a loss-budget exit. It cannot claim profit from the winner alone while ignoring a losing residual.

Partial fills consume exact lots only. Deduplicate native trade IDs. Replacement leaves=authorized target-confirmed fills-retired entitlement. Unknown ACK and pending reductions reserve quantity; cancel request does not free it. Late fill belongs to original episode/grant. Reconcile cancellation terminals/late fills before replacement or increase. Native reduce-only and competing reservation ceilings prevent reversal. The second leg is exposed until its own actual fill; do not assume synchronous paired execution.

## Inherited loss, BE and finite residual risk

At actual regime boundary t0, future marked change for signed linear inventory is
b0*(PBt-PB0)+s0*(PSt-PS0), plus subsequent ACTUAL fill consequences and costs.
Use existing native account/journal for money; this algebra is not authorization to build a hypothetical cashflow engine. Whole-episode result includes loss already inherited at t0.

Example: inherited BTC loss -10; SOL later gains +3 while BTC loses another -3. Combined remains -10 before added costs. Closing one third of each realizes about -10/3, leaving about -20/3. A positive SOL slice does not pay the pair's old loss.

Near-full beta hedge can freeze inherited deficit while fees/funding accumulate. h<1 leaves directional factor exposure that can recover OR worsen the loss. SOL basis residual may help or hurt; it is unproved. If A already neutralizes/exceeds BTC factor exposure, a label of alpha does not restore directional recovery.

Leg BE uses that native leg's actual average basis, entry/exit fees, signed funding and execution costs. It says nothing about the other leg or prior realized losses. A fee-adjusted stop price is an intention; gaps/slippage can realize less.

Pair BE requires conservative native executable liquidation equity for the entire ORIGINAL episode, all past real trims/adds/losses/fees and BOTH remaining legs including A, compared with original start benchmark. Never reset at flip. Unknown signed funding means exact cost-complete BE UNKNOWN; do not call an estimated threshold guaranteed profit. If unrelated same-account strategies contaminate equity and native attribution is unavailable, pair BE is UNKNOWN, not pass.

Admission: quantified inherited original-episode loss D0 + executable close-cost buffer < predeclared R, with native margin safe. Remaining new-risk allowance at most R-D0-buffer; never a fresh R at flip. If already exhausted, close normally. Continuously observe native benchmark and force group exit on exhaustion. R is a trigger, not a gap-proof maximum or global DD guarantee. CHOP/regime invalidation and terminal boundary also prevent indefinite holding. No timer-based re-add or permanent replenishing SOL floor.

## Evidence and next gate

Read reports/chop-pair-113/{prior-native-feasibility.md,prior-btc-loss-guards.md}; final-analysis-and-proposal.md:147-161. Source: domain/wave_overlay.py:218-282,365-452,475-527,628-666; strategy/conditional_hedge.py:196-241; strategy/wave_overlay.py:2555-2590. HEAD verified; no tests run.

Relevant existing tests (not evidence this unimplemented candidate passes):
- runtime/tests/test_wave_overlay.py:72,121,142,253,261,283,304,323: regime priority, proportional partial TP rights/remainders, group-flat reset, partial-entry identity, lot conservation.
- runtime/tests/test_native_conditional_hedge.py:69,89,119,136,152,200,319,347,467,494,644: transfer is not fill, original rights/exits, unknown ACK/late partial, reserved Q2, TP-flat/late-add lifecycle and IOC shortfall.
- runtime/tests/test_native_btc_sizing.py:36: native first-fill/Q2/initial quantity boundary.

Addressable technical blocks: narrow guarded REGIME branch, same-ID skip latch, actual-quantity arming reconciliation, original physical-exit priority over MAX, cover-only TP/reservation conservation, inherited-loss/unknown-BE fail-closed checks. One narrow native review after a fixed contract, not a general audit.

Unresolved economics: actual REGIME-close quantity census (including A and original BTC basis/loss), causal CHOP selection, unused factor exposure, residual payoff edge and defensible R/stages. Obtain cheap inventory/payoff evidence before implementation. No structural rule demonstrates ROI preservation or DD30-50. Exact original-alpha preservation remains incompatible with retaining that alpha beyond its mandatory regime exit.
