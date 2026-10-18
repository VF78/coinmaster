# Conditional SOL native money/order corrected review

**GO for ONE isolated native economic run.** All three original blockers resolved. Initial BLOCK retained in review-money-orders-before-correction.{md,json}; no new audit/source/index edit/test rerun by reviewer.

- P1 runner disables original overlay: native_baseline.py:717 no conditional-disable; real production builder regression accepts original overlay,721seed and2source minutes.
- P1 logical half-to-full decision transition missing: conditional_hedge.py:96-107 records applied logical HALF completion; release/native/mixed regressions require no same-cycle full and natural full at later applied index.
- P2 ownership sigma overwritten: domain/wave_overlay.py:530-533 records first native fill time separately; ownership clock/sigma set only once; sigma .02 remains after native add sigma .07.

Tiny defaultOFF hook guard now short-circuits before evaluating an abstract native clock; enabled feature path is unchanged. Corrected half fixtures use actual applied cycle2, not stale intent cycle0; production fixture includes the existing7.875 baseline candidate. No other runtime deltas relative to initial frozen review were found in the limited correction diff.

Verified evidence: ONE full relevant batch194passed/6failed74.39s, followed by ONLY the six failed cases6passed3.67s after localized fixes. No second full200-pass batch claimed. Actual logs and their hashes checked. Broad batch already passed the ownership-sigma regression; failed-only retest covers production builder, three half routes, two existing defaultOFF terminal cases.

All eight actual source pins and patch independently rehashed and match correction-verification-evidence.json. Exact final pins retained in review-money-orders.json.

Patch SHA256: d9176243a4a290e86b7f58a9d26a3f9d471fe6d6a9de20998e3ad40ac20a7ff2

Not live/economic approval. One broad batch194pass6fail plus exact6failed-onlypass; not a second full200pass run. Full24m eligibility/fees/funding/coverage/permissions and TOTAL/DD acceptance pending.
