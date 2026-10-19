# Addendum: TP-budget correction

2026-10-20. Verdict: GO_ANALYSIS_CONTRACT.

Checked only amended clause6 in final-analysis-and-proposal.md and the corresponding TP_right_retirement / TP_right_budget_includes / Q2_after_risk_fill fields in final-proposal.json. No full re-review, data/archive read or engine.

The substantial ambiguity from prior-final-review.md is resolved. Each actual native risk-fill delta retires exactly delta across current outstanding TP rights proportionally in integer lots, deterministic largest-remainder / TP-index tie-break. Already filled TP history remains actual history. Including original authorized future Q2 in the remaining exit budget is coherent: before/after the cut, aggregate outstanding exit rights represent currently held BTC plus still-authorized unfilled entry quantity, less actual reductions. Subsequent lawful Q2 fills supply the remaining budget without restoring retired rights or charging the cut twice.

Pending cancellation does not release inventory before terminal acknowledgement; late actual fills are reconciled before the next target recomputation. Joint native exit leaves are capped by actual position. Retired slots and risk fills cannot manufacture SOL rights or virtual TP fills. These are quantity/authorization transitions within the existing native-owned episode, not a second cash/PnL engine.

This GO approves consistency of the ANALYSIS CONTRACT only. Partial-fill / cancellation / late-fill / Q2 conservation remains mandatory implementation acceptance evidence. No implementation or full native run is authorized here; new TOTAL/ROI/DD remain UNKNOWN, and the prior portfolio-risk limitations remain.
