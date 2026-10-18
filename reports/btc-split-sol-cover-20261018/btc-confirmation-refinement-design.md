# Bounded BTC split confirmation refinement design (not implemented)

2026-10-18. Root-authorized shortlist after five separate initial results.
Current frozen source e4f4e67 has BTC discounts .25/.50%, fixed4h deadline,
early confirmation OFF. This note changes no code or running source.

P0 early57 train comparison: .25%/4h/ON near.10% mean whole-plan gross proxy
+2.67169bp,9 forced fallbacks, mean wait1.3304h, worst-190.899bp;
4h/OFF +3.09647bp,11 fallbacks, wait1.4497h;2h/OFF +2.35369bp,
14 fallbacks, worst-203.110bp. Late48 remain sensitivity on already observed
data. Neither price proxy nor lower fallback count is native ROI evidence.
Do not select a Mar13-specific threshold, alter3% trail reference, or inject
the known105 historical permission dates.

BTC025 actual104-vs-V3105 diagnosis is separate: Mar13 short actualVWAP
83631.2 V3 versus83554.5 split; Mar14 close81072.3 gives3.059744% versus
2.970762% favorable return. The unchanged strict best_f>.03 condition arms
V3 trail only. Both BTC positions become flat, but retained SOL keeps split
episode busy where V3 trail closes/rearms for Mar16. This is actual-VWAP
coupling through the original rule, not a denied BTC order. The candidate
fails literal105-permission acceptance; no claim that ON fixes this case.

Implementation after initial separate results and root decision:

- Add one optional defaultOFF research_btc_split_confirm flag in existing
  StrategyConfig/native runner/CLI. Keep first-half immediate, acceptedQ,
  zero-net/reference/H identity, full-plan margin and mandatory close rules.
- Reuse existing native composite15m source bars, completed-bar callbacks,
  receipt timestamp and first-future-quote sequence convention. No B1
  whole-entry gate, new executor, matching model or money ledger.
- A strictly later completed BTC15m close must break previous high for long,
  previous low for short. Receipt must precede the first real BTC quote
  consuming it; same boundary cached book is ineligible.
- At that quote, actual executable entry must be at most.10% worse than
  first-part actual native VWAP. Good confirmation cancels resting second
  child. Unknown ACK blocks all competing entry children.
- After authoritative cancel terminal, recheck current executable quality
  before submitting only remaining acceptedQ through existing IOC path.
  If quality disappeared and neither mandatory TP nor deadline is due,
  resume the original discount wait; do not promise confirmation-close fill.
- Native early positiveTP/deadline completion and mandatory close/DP retain
  priority. Original daily TRAIL continues to use actual entryVWAP.
- Audit confirmation close/receipt/trigger quote and actual submit/quality,
  cancellation and completion cause using existing parent audit.

Focused native proof before one new full run: flagOFF unchanged, no gate on
firsthalf; real native15m timer -> next actualBTCquote; wrong side/same-boundary/
stale receipt ignored; .10% quality both at trigger and after cancelACK;
unknownACK/cancel-fill race; pending close wins; exactQ/omittedzero/reference/H
conserved. Existing risk/fee/account/queue tests are retained. One narrow
independent diff recheck and pinned source before the full run.

At most one new BTC refinement, then any joint experiment only after separate
results/root decision, plus a fresh winner repeat within the owner run budget.
