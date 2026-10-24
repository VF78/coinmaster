# Paired lot-grid recursion: actual-source postmortem and proposal

**Current architecture: NO_GO. P1 structural order/risk defect confirmed at source `3323f08c57ede411058f93d96acee88928c93481`.** Native accounting/observer/terminal PASS does not establish correct hedge behavior. The observed DD improvement cannot qualify a correctly implemented nonrecursive hedge; its exposure path includes unintended repeated BTC/SOL reductions. B2 also fails the approved2×capital gate. Combined remains on root HOLD. This is proof and a paper proposal only: no source patch, native run, economic simulation, budget or approval change.

Scope read: approved5-risk-B2-qualification.json, prefix-B2-physical4-outcome.json, frozen PairedCaps.reconcile/solmax and position callbacks, first actual paired activation/causal fill trace. Independently verified report SHA `2368406ca61ef8ae4971f4ecaa88dbf22ee99a453df2e88038253e0e92852bb0`; detailed trace SHA `1163151e08009cec979d332fc53e891aee312ba155da221f35266aa72d207da5`. No repeated cash/CVaR review; those belong to prefix_risk_analysis.

## Exact defect

Let b be BTC lots, s SOL lots, v frozen BTC reference lots and u frozen intended SOL lots. Native BTC step is0.001BTC, SOL step0.1SOL. The source's physical k corresponds to rational lot ratio r=u/v. Both current constraints are conservative floors:

    b <= floor(v*s/u)     and     s <= floor(u*b/v).

The first implies u*b<=v*s; the second implies v*s<=u*b. Together they force **u*b=v*s exactly**. A fixed point therefore requires b to be a multiple of v/gcd(u,v), and s a multiple of u/gcd(u,v). For any noncommensurate state, alternating current floors strictly decrease BTC lots. Absolute monotone ceilings alone do not prevent this lattice erosion. Decimal precision is not its root cause: exact integer arithmetic reproduces it.

Actual first activation: Qref1.037BTC=1037lots; intended181.7SOL=1817lots; k reported175.2169720347155255544840887, exactly rational physical quantity181.7/1.037 before Decimal representation. gcd(1817,1037)=1. After any reduction below1037BTC lots, the only joint nonnegative floor fixed point is zero. The engine may invalidate/expire the risk first; the arithmetic tendency toward zero is still structural.

At2024-09-15T21:08Z, actual TP45.4SOL leaves136.3SOL=1363lots. Conservative BTC coverage floor(1037*1363/1817)=777lots, causing the intended0.260BTC trim. At21:09Z actual BTC becomes0.777. Current SOL ceiling floor(1817*777/1037)=1361lots, so actual SOL_CAP0.2SOL leaves136.1. This immediately creates a new BTC ceiling floor(1037*1361/1817)=776lots. At21:10Z, another actual0.001BTC debt fill and0.2SOL cap fill produce775BTC lots. No independent TP/risk exit initiated these latter cuts. Actual trace0.777→0.776→0.775 matches the exact equations. Aggregate990BTC_DEBT/985SOL_CAP fills across9activations are consistent with this mechanism, not evidence of990 independent risk decisions.

The earlier focused acceptance/review missed this property: commensurate and selected rounding examples were insufficient. Its reports and all failed/complete native evidence remain preserved; this postmortem supersedes their nonrecursion conclusion for actual arbitrary lot ratios.

## Minimal lot-safe proposal — requires a new approved protocol

Freeze exact integer u/v once from intended SOL lots and BTC reference lots; keep existing k/ATR/P0 semantics for their existing purposes. Use integer cross-products/division for cap predicates so Decimal representation cannot alter an exact lot boundary. Retain the conservative BTC coverage rule and monotone actual BTC ceiling:

    bmax := min(previous_bmax, floor(v*actual_s/u))  [active/unknown SOL reduction]
    bmax := min(previous_bmax, actual_b)           [actual BTC reduction]
    SOL upper cap := ceil(u*bmax/v).

The stable post-reconciliation corridor is

    u*bmax <= v*s < u*bmax + v,

with s=ceil(u*bmax/v) when a cap trim is needed. The correct BTC-caused SOL cap fill then satisfies floor(v*s/u)>=bmax, so applying the existing conservative BTC rule cannot create new debt. A real late/oversize fill that goes below that minimal sufficient SOL lot count still creates actual debt. **Do not ignore all BTC_CAUSED fills**, invent virtual positions or count pending trims as relief.

This ceiling is an upper limit for reduction only: submit no increase/re-add if actualSOL is below it. Reconcile only actual native fills/cache; ceilings never rise, ratio never reanchors. Preserve consumed TP rights, actual IOC terminal VWAP, native minimum quantity/notional, protective stop/ACK discipline, dust fail-close, parent-flat SOL closure and unknown-state handling. If the remaining native unconsumed-target/stop allocation is invalid, the existing conservative closure/NO_GO policy remains required; the mathematical corridor does not authorize unprotected dust. Nonpositive/invalid ratio or nonintegral native lot evidence fails closed.

The deliberately allowed surplus is strictly less than one SOL lot above exact proportional k*BTC, here **<0.1SOL**. At first sample: proposed ceil(1817*777/1037)=1362lots=136.2SOL, exact proportional136.143587270973963…SOL; surplus0.0564127290260366…SOL. BTC coverage floor(1037*1362/1817)=777lots stays unchanged. A genuine extra reduction to1361lots still gives776 covered BTC lots and therefore real0.001BTC debt; subsequent ceil cap at776BTC lots is1360SOL lots, a stable corridor. Generic equivalent surplus for this activation is<0.000570720968629609…BTC (<0.570721 BTC lot). This is a quantity bound, not a dollar loss/slippage or execution bound.

Changing approved SOL floor to ceil is a monetary behavior change, even though the surplus is bounded. It cannot be patched, replayed or compared under the existing frozen-source approval. New protocol/owner approval, source freeze, native acceptance and a concrete matched-control budget would be required before implementation/economic execution.

## Alternatives and acceptance boundaries

- Keep both floors and quantize cuts to exact common bundles: mathematically consistent, but this actual coprime ratio permits only the original1.037BTC/181.7SOL bundle or zero. It converts modest TP into full closure and changes the intended exit model.
- Replace conservative BTC floor with ceil: relaxes required BTC coverage by up to one BTC lot. This weakens the specified protection direction and is inferior to retaining<oneSOL-lot surplus while preserving conservative BTC coverage.
- Quantize the initial hedge ratio to an integer number of SOL lots per BTC lot: can avoid this particular lattice conflict, but changes intended HALF_VOL sizing/admission. It is a larger economic alteration.
- Suppress all BTC_CAUSED deficit callbacks: hides real oversize/late fills and fails the native actual-quantity contract. Reject.

Before any newly approved economic run, one bounded native acceptance pass must cover the actual1817/1037case, both sides, commensurate and coprime small ratios, partial IOC entry/debt, independent TP/stop and BTC exits, correct cap-fill idempotence, true one-lot overshoot/late fill, duplicate/out-of-order callbacks, no increases/reanchors, dust/protection fail-close and actual terminal flat. ON/OFF native accounting/observer parity remains required. This is a mechanics acceptance list, not authorization for more engines or a prediction of improved economics.

## Pure integer verification receipt

Owned script approved5-grid-invariant-check.py uses only Python integers/Decimal for parsing lot counts; no trading/native imports, prices, PnL or economic engine. Choices frozen before execution: u,v1..16, b0..32, independent s0..64, plus the actual1817/1037 counterexample. It proves conservative coverage, <oneSOL-lot surplus, no inventory addition, cap-fill idempotence, true additional one-lot deficit and exact old-floor fixed-point criterion. Result:25088 checked states PASS;5359 old-floor states strictly decrease BTC. Machine receipt approved5-grid-invariant-check.json pins the script and actual report. Finite enumeration supplements the algebra; it is not proof of runtime callback/protection correctness or economic qualification.
