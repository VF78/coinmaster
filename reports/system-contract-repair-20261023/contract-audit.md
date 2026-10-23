# Execution and strategy contracts — current evidence

Status: bounded package completed, valid negative economic result; goal50/90 NOT_MET. Scope: original owner audit0–4 plus OWNER_TASK, SC00–05. No pilot, deployment, real orders or production config changes.

## Confirmed dependencies

- The historical synthetic quote displays1000 asset units. In E4,96/98 SOL_ADD orders filled1000 and canceled the rest. This is a fixture governor, not exchange liquidity. Pinned1.231 L1 matching reuses depth independently for each IOC; two children can each fill1000. Native fixtures do not establish portfolio robustness at another depth.
- Explicit child policy changes the submitted quantity only, retaining original notional right and perlevel/D1 attempt guard. Native FILLED and partial/CANCELED remain distinct, truthful receipts. Focused tests31PASS; relevant131PASS; independent source review plus two precision testsPASS.
- Historical equivalence is disproved: old E4 TOTAL5631617.35953723 versus explicit6022427.55763206. First observed economic difference23Dec2024,16:47UTC: original same-time queued SOL_ADD was locally denied, explicit capped order was admitted and added1000SOL@183.81, fee101.0955. Old exact denied level/component UNKNOWN. Original all-eligible-level batch and denial witness support changed admission, not a proven new scheduling attempt. FILLED callback as an independent cause is unproven; no blind scheduling patch is justified. Matching S0 in the same explicit policy is therefore mandatory within budget.
- E4 TP1zero83/83, TP2zero58/83. ±1bp q1 perturbations change6/10 entry branches respectively. This is local native-tick branch sensitivity, not a new ROI estimate. Gross plan, zero-TP sizing and first-child PLANREF are separate from actual blended entry price; profitable fallback remains unchanged.
- SOL is selective alpha, not continuous BTC insurance:56.9167% of SOL-active time is BTC-flat,13/25 cycles start BTC-flat, H references original gross BTC and step rights add. A SOL intervention also changes later BTC equity/sizing/admission. R2C had337 matching BTC fill times/prices/reasons versus XS but292 differing quantities; corrected float-flat did not change its economic path.

## Active-rule audit and methods

The43-row rule registry covers source/purpose/provenance/implementation/economic evidence, problem and KEEP/FIX/TEST/DEFER for all original0–4 requirements. Implementation verification is not proof of economic benefit. Parameter choices without isolated evidence remain HYPOTHESIS/NOT_TESTED; no unverifiable claim about an author's intent is made.

Existing72source pins,15 saved comparable paths, two actual2×2 interactions and11 external sources are reused from the completed systematic audit. New work applies actual native lifecycle fixtures, controlled changed-model comparison, local branch perturbation, prefix-causal labels and full portfolio trajectory attribution. Missing factorial cells do not prove interaction; fresh repeat is not OOS. See rule-registry.json, evidence-audit.md, methods-and-coverage-review.md.

## H_SOL and H_BTC — implemented and tested, both economically negative

The frozen source contract is owner-risk-SC03-SC04-CONTRACT.md. Functional source27c1904 passed focused independent review/9risk tests; owner40focused/142relevantPASS. Final observer/test-only source8f2f780 is pinned and independently42testsPASS. Both individual historical candidates completed normally and passed60accountchecks each; neither passes50/90.

H_SOL: every ADD is admitted only when fixed nonnegative gross stress coefficients leave at least55% global high-water. Unique held/opening leaves/unfinished parent reservations and unpaid entry fees are counted once. Maximal lot is solved from a monotone affine inequality; native margin remains independent. No forced cut, DD35trigger, stop, automatic restore or new retry.

H_BTC: one observation per actual-filled parent, first/repeat by actual EMA wave, label anchor first actual native fill, frozen closed ATR/q0. Only complete minute-MARK potential MAE labels with ready_at<decision enter Decimal linear Q90. Minimum8 valid each group; repeat k=min(1,Q90first/Q90repeat), fallback1 explicitly. Apply once after original notional cap, before zero-TP/lot rules. No compensating SOL/leverage/frequency increase.

Offline causal dataset:83parents/50actual waves,81completed/2censored;24eligible repeated decisions,19potential k-reductions.28offline checksPASS. This is activation feasibility on the old path, not predictive or portfolio benefit. Archived decision-time held/pending/internalgate/equity are UNKNOWN; native hooks must provide available state and precisely qualify any missing gate vector.

## Completed acceptance and explicit limits

MatchedS0, H_SOL and H_BTC completed:4physicalattempts total. CombinationNOT_RUN by independently verified actual-prefix DD65.6948lowerbound; repeatNOT_RUN because no candidate passes. Two unused slots closed. Maximum6 physical attempts including controls/failures/corrections. Every candidate needs complete native money/positions/orders, full settled DD, all24months/seven fixed E4 episodes/new global worst and explicit rights/pending evidence limits. Economic50/90 goal is NOT_MET, no winner selected. Native causal datasets each2407groundtruthchecksPASS; archiveUNKNOWN fields were not backfilled with invented values.
