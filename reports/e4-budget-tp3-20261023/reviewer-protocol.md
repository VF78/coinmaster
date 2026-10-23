# Independent narrow protocol review — 2026-10-23

Scope: saved compact evidence and design only. No engine, historical replay, market scan, alternative equity/PnL, VPS operation, product edit, baseline rewrite or pilot inspection. Source review remains pending owner handoff. This file is review-owned.

## Proposed single numerical SOL recipe

Use pure E4 and a single causal stress rule, not a grid: global settled drawdown >=35%; warning equity floor 55% of the unchanged all-time settled-equity high H; stress distance exactly 1.0 times the latest fully closed D1 Wilder ATR14 for each asset. The term “next 1D stress” denotes this fixed scenario, not tomorrow's realized ATR or a probability/coverage guarantee. Use native actual equity E from the last fully completed paired receipt. ATR, price and position timestamps must be explicit.

For a simple conservative cap, reserve independent adverse BTC loss abs(Q_B)*ATR_B, with no hedge credit. Include worst applicable native taker commissions for contemplated SOL cut and eventual stressed exits; use actual configured fee rates, not a fitted number. Solve for the largest native SOL lot quantity q <= actual held plus a proposed original unused add for which E minus immediate cut fee minus BTC stress/exit-fee reserve minus q times SOL stress/exit-fee reserve stays >=0.55H. Price dependent commissions use adverse stress prices; valid positive price and ATR are prerequisites. Do not subtract current unrealized losses twice: E already contains them. Admission remains subject to every existing signal, entitlement, margin and native minimum gate.

At most one accepted risk-reduction target per actual SOL cycle. Freeze that target and its owned child/retry identity; ordinary exit has priority, partial native fills and cancel acknowledgements cannot create a new target. Reduce only the excess. Recompute the cap for later *unused original* adds; actual sold units and consumed rights remain consumed. A canceled never-filled add may remain unused only if existing domain semantics prove that fact; an uncertain ACK or late fill is owned exposure, never assumed canceled. Do not add timer/bounce restoration. The once-per-cycle limit necessarily means this is a stress admission/cut policy, not continuous maintenance of the 55% floor.

## Material overcut risk and preflight limit

35% activation with 55%H floor leaves only 10%H at exact activation. On the October E4 high14743.45772484 that is1474.345772484. The saved actual BTC abs quantity0.940 makes any standalone BTC ATR >=1568.452949451 (before fees) exhaust that entire buffer and force the SOL cap to zero. That arithmetic is a conditional budget bound, not a claim about the actual ATR on October3. Absolute adverse stress for opposite BTC and SOL is deliberately conservative but can charge two mutually opposing directional shocks simultaneously. This can sell the economically useful SOL leg because BTC consumes the budget.

At the saved January E4 trough E84574.29784059 <0.55*174073.90411259=95740.6472619245, a fresh cap is necessarily zero even with BTC flat. September global DD35.7041% is already eligible although its baseline tail stays below50%; its profitable SOL recovery is a required damage counterexample. E4 summer46.3347% already passes50 and must be a regression, not a baseline failure.

Before native launch, require bounded saved as-of witnesses for first eligible warning/cut and original add decisions in October, January, May, September and summer: E,H, ATR values/as-of, actual native positions, owned pending leaves, cap, proposed cut, and original unused rights. Missing components are UNKNOWN. The reviewed compact endpoint/cohort files do not provide complete causal ATR/ACK state, so this review cannot establish all-calendar participation preservation or call the rule a proven modest trim. If the owner's precheck shows widespread zero caps or renewed destruction of the major profitable SOL cycles, reject the recipe before spending a full run rather than vary thresholds to fit outcomes.

Saved sources: ../e4-postmortem-20261023/REPORT.md section7 and review.md; ../e4-postmortem-20261023/e4-excursions.csv; ../b-50-90-next-20261023/owner-sol-risk-cohort.csv; ../e4-sol-residual-20261023/verifier-risk-cut-timeline.csv. No full minute trace was read.

## BTC TP3 contract update from root / owner source inspection

Root reports exact bd04 source grants proportional SOL entitlement on the first real BTC_REDUCE partial fill, using actual credited units / original target units times entry fraction; completion separately marks btc_filled_tps. Thus preserve proportional actual-fill credit across early and remaining TP3 children. The earlier proposed full-completion gate is explicitly superseded; adding it would be a second policy change.

Freeze early quantity at lot-floor20% of actual completed initial split quantity and target at native rounded PLANREF +/-1% favorable; allocate solely from positive sufficient original TP3 target. Early child plus remaining child quantities conserve that original target. Unsupported/ineligible/suppressed/insufficient TP3 keeps original branch; TP1, TP2 and fallback preserve exact behavior. Original exits, outstanding native/UNKNOWN ownership and actual remaining position constrain submits. Late fills, fills after cancel requests, retries and duplicates must never oversell or credit a unit twice. A mere order submit/cancel or target-price touch grants no rights.

Preserving the existing entitlement *formula* also means a successful early child can advance SOL entitlement in time. Disclose that the BTC arm may therefore change SOL entry/capital paths even with SOL risk-budget disabled. Do not label the rights/calendar unchanged or interpret the arm as a static BTC-only PnL substitution. Owner tests/diff must verify this exact contract before launch.

## Bounded execution protocol

One executor; maximum four full physical native attempts including failed/aborted/recovery attempts, not four successful recipes. No S0 rerun; retain archived S0 and E4. Separate SOL and BTC arms first; combined only if separately justified, repeat only for a passing candidate. Any control replay, ablation or recovery consumes an existing slot. Preserve full native fees/funding/admission/rights/capital and receipt completeness checks. Acceptance remains global settled DD<=50%, TOTAL>=5470396.514987347, zero liquidations, coherent terminal ownership. This protocol offers no 50/90 guarantee and no pilot authorization.

Disposition: conceptually coherent one-recipe candidate with material overcut risk; source/state preflight required. Pending independent owner diff/test review.
