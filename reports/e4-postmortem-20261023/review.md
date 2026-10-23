# Narrow saved-evidence review of REPORT.md — 2026-10-23

Scope: numeric accuracy and proposed next experiments only. Reviewed new REPORT.md/arithmetic.json against saved B/E4 and residual compact outputs plus the parent's saved-fill extraction. No new engine/replay/training/source/VPS scan. REPORT.md was not edited.

**Disposition: economic findings PASS; experiment proposals reasonable as NOT_RUN hypotheses, with two TP3 contract clarifications required before a recipe could be frozen. No economic success claim or run authorization follows.**

## Numeric review

The five controls,50/90 floor5470396.514987347, E4 headroom161220.844549883, all three E4 >50% episode clocks/values, summer46.3347140686%, four SOL-cycle comparisons, R2C−E4 attribution and four-cut fees1631.24775 match saved evidence. Cadence/residual coverage confounding and defective R1 vs untested repaired H1 are correctly distinguished. The text correctly avoids importing B's Nov26 peak into E4 and avoids calling R2C summer61.7587% an E4 baseline failure.

The narrow October cushion is9.38571563 from7381.11457805−14743.45772484/2; reported9.3857 is correct. Oct SOLmark−9660 and BTCmark+1159.30198 refer to actual native aggregate unrealized components, not a naive quantity×unrounded OHLC-close calculation; with cash+10.61735321 these reconcile peak-to-trough−8490.08066679. Signed funding attribution remains UNKNOWN.

Sources: [B/E4 comparison](../b-50-90-next-20261023/comparison.csv), [E4 episodes/native snapshots](../b-50-90-next-20261023/verifier-E4-DD-ge30-episodes.csv), [R2C episodes](../e4-sol-residual-20261023/verifier-R2C-DD-ge30-episodes.csv), [R2C SOL cycles](../e4-sol-residual-20261023/verifier-R2C-closed-cycle-ledger.csv), [risk fills](../e4-sol-residual-20261023/verifier-risk-cut-timeline.csv), [new arithmetic](arithmetic.json).

## B-TP3 hypothesis review

The parent's saved E4 fill audit extraction establishes Nov26 entry81.738+81.739=163.477BTC; Dec1 ordinaryTP3=94.001, Dec2 TP1=34.738 andTP2=34.738; total163.477BTC. Every actual unit later participates in an ordinary TP. Thus an extra20% reduction cannot be described as economically free. This is **whole-cycle actual fill evidence**, not proof of exact working TP reservations at an earlier timestamp; as-of native ownership/working-order leaves remain UNKNOWN from the compact outputs reviewed here.

Carving an early20% from the **existing** plannedTP3 budget is therefore more coherent than claiming a new free trailing20% risk cut. It is nevertheless a new profit-taking policy: it may improve November squeeze exposure and may surrender trend profit elsewhere. Current evidence neither proves that +1% is reached before every adverse tail nor that the20% reduction will achieve the95.8k static November floor gap. The20%/+1% values are one candidate recipe, not estimated optima. PLANREF is the candidate anchor; use frozen plan reference and native tick rounding with explicit long/short definitions, not moving actualVWAP or retrospective best price.

Two recipe conditions need explicit wording before any future implementation:

1. **New entitlement gate, not an unverified claim about current policy.** REPORT's phrase “по прежнему правилу фактического завершения его совокупного планового объёма” could be read as confirmation that current code already waits for full TP3 completion. This review has not established that. Phrase it as a proposed conservative contract: the early child is part of originalTP3; its submission/partial fill does not independently grant new SOL entitlement; original level's entitlement may arise at most once only after the proposed combined originalTP3 lot budget has actually completed, subject to verified existing rights semantics. Confirm any current incremental grant behavior before freezing; an extra deferred gate would itself be an additional policy change.
2. **Quantity conservation across eligible branches.** Require enough actual plannedTP3 leaves to allocate20% of actual executed BTC-entry lots after native rounding. Nonexistent/zero/suppressed/insufficientTP3 branches must be explicit no-ops, preserving fallback. Earlychild+remainingTP3 must never reserve/fill more than originalTP3 budget, including late fills, cancels, ordinary TP precedence and partial entry fills. “Native admissible” alone does not prove this conservation.

Existing TP1/TP2 and zero-TP/fallback can remain unchanged in intent, but that is a proposed invariant requiring proof, not an already verified property of an unimplemented rule. Marketable target collisions need existing native execution policy; no guaranteed maker fill or fee is inferred from the target.

The proposed whole-calendar precheck is sensible as triage. Saved price reaches can reject infeasible cases and count potentially affected cycles, but cannot establish order-state precedence or alternative fills/equity. If complete as-of native reservations/rights are unavailable, mark those UNKNOWN instead of inferring free leaves. Avoid selecting only November or assuming target touch equals native fill. A later actual test must recalculate capital/lot/cap/admission/SOL effects.

## SOL proposals and scope

S-budget follows observed exposure/capital differences and avoids repeating fixed permanent M1/Z-style cuts, provided only one causal stress/buffer rule is frozen before a run and the all-calendar precheck rejects broad destruction of profitable participation. Past D1ATR is causal, but its multiplier/warning boundary are unselected and must not be fitted to the three hindsight floor gaps.

S-ablation correctly identifies a diagnostic question. Unused rights must be proved as-of; the difference5000→4000 or22000→15000 does not by itself prove each missing order would remain valid on the changed path. Keeping actualcut logic constant does not guarantee later triggers/quantities/fills remain constant once an add is allowed. Report this as the effect of changing only the lockout **policy**, not an identical future fill path with selected adds restored. May's identical total adds with worse cycle net demonstrates why lockout removal cannot alone solve the loss.

The suggested maximum4 conditional runs is a proposal for later owner agreement, not an active budget. Corrected H1 is untested; broad summer redesign is not justified by E4's46.33% summer baseline. Summer should remain a regression test for capital damage caused by local fixes. No thresholds, target profits or global50% guarantee have been validated here.

## Root resolution

The two requested contract clarifications are now explicitly in REPORT.md: proposed (not asserted existing) entitlement semantics; completed split, sufficient positive native TP3 leaves, quantity conservation and unchanged ineligible branches. All future recipe semantics still require owner agreement and source-level tests; no implementation or economic run was authorized. S-ablation is a policy change with subsequent path effects, not identical future fills.
