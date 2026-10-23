# Independent saved-fill attribution validation

PASS for all24cited numerical claims at the document’s stated cents precision. The asset values are identifiable **confirmed-fill net cashflows excluding allocated funding**, not exported native asset PnL including funding. No new engine, replay, backtest, training, data fetch, product change or pilot action occurred.

Source S0 scientific75ffc9c69e9d79c4da4cd0614634a3eeba48d716; B executed25a085f596292df58e51188dd91e996adbe5724c. Inputs are the immutable S0 verifier-reference-fills.csv, B native-fills.csv, comparison.csv and owner-sizing-calendar.csv. Input hashes and the owner document hash are in attribution-summary.json. These files support the document’s sections1–4 attribution assertions; this pass does not validate proposed new execution contracts or full-native economics.

## Confirmed-fill bridge

Both assets start with zero inventory and their native signed quantities finish exactly zero, including actual terminal closing orders. Therefore `gross=sum(SELL filled_qty×avg_px)−sum(BUY filled_qty×avg_px)` and `net_ex_funding=gross−sum(native commissions)` are descriptive closed-inventory cashflows. This is a finite ledger sum, without mark sampling, cost-basis discretion, inferred funding or alternative matching-engine economics. Commissions use ast.literal_eval and Decimal; serialized native average-price precision is preserved.

|Recipe/asset|native filled-order rows|terminal signed qty|gross fill cashflow|native fees|fill net ex funding|
|---|---|---|---|---|---|
|S0/BTC|416|0.000|6273361.445100010293496|927666.95630420|5345694.488795810293496|
|S0/SOL|205|0.0|696921.989|18260.78131405|678661.20768595|
|B/BTC|322|0.000|4523649.149600007170138|577343.13666423|3946306.012935777170138|
|B/SOL|162|0.0|646698.175|14747.18003495|631950.99496505|

|Recipe|TOTAL−seed|fill net ex funding|unallocated bridge|
|---|---|---|---|
|S0|6067107.23887483|6024355.696481760293496|42751.542393069706504|
|B|4612034.27336437|4578257.007900827170138|33777.265463542829862|

BTC delta−1399388.475860033123358; SOL delta−46710.21272090; combined fill-net delta−1446098.688580933123358. Unallocated bridge delta−8974.276929526876642. These reconcile to native TOTAL delta−1455072.96551046. Gross fill cashflow delta−1799936.109500003123358 plus fee saving353837.42091907 equals the fill-net delta; the additional bridge explains why the older TOTAL-plus-fees residual−1808910.38642953 is a different number.

**Do not label the residual signed funding.** The native asset net export remains absent. The positive residual42751.542393069706504 for S0 and33777.265463542829862 for B can contain funding and any other native account/ledger boundary effects until those native mutations are independently reconciled. No allocation to BTC or SOL is made. The two actual native fee sums exactly match the comparison; quantities end flat. Native aggregated-order report average prices have minute serialization differences from the fill-audit price strings, already documented in the prior ROI analysis; no decimal normalization conceals them.

## Why this is stronger than the prior UNKNOWN

The prior report explicitly kept native asset net and signed funding UNKNOWN because neither field is natively exported, and turnover/fees alone cannot establish trade PnL. That remains correct for **native exported asset net including funding**. This pass adds the missing proof and calculation: asset-level terminal inventory is exactly flat; signed BUY/SELL consideration can then be summed, actual commissions deducted, and every BTC parent and SOL zero-to-zero cycle reconciled to that sum. Thus confirmed-fill net **excluding funding** becomes measured without pretending it is a newly exported native account field. Old historical episode-label values were not reused; those can differ materially because their original attribution basis differs from the native split-entry ledger. Neither fees nor unsigned turnover is relabeled profit.

## Matched quantities and unit outcomes

attribution-matched_entry_attribution.csv is the reusable51same-UTC-entry-day attribution table. Each row uses two actual completed BTC parents, their true total entry quantities and their full closed-parent fill cashflows after all native entry/exit fees. Each parent’s net signed inventory is0; its summed non-reduce entryQ equals the saved parent’s actual filledQ. All BTC native filled-order rows partition exactly once across105S0and77Bparents. Dates are a descriptive correspondence; exits and lifetimes can differ.

Let `qS,qB` be actual entryQ and `uS=netS/qS,uB=netB/qB`. The symmetric identity is:

`netB−netS = (qB−qS)*(uB+uS)/2 + (uB−uS)*(qB+qS)/2`.

Across51matched days, delta=−705981.086361189416376; Q-component=−709196.209124880006798472439842633080984522191; unit-component=+3215.12276369059042247243984263308098452218288. The tiny algebraic residual below1e−32 is the declared finite45-digit Decimal division context, not an economic tolerance. This validates the document’s−705981.09/−709196.21/+3215.12. It does not identify q as capital alone: cap, selector branch, zero-level netting, changed execution/admission and the actual inherited capital can all affect actualQ. Unit outcome can include changed exit paths, prices and fees. This is accounting for two histories; it is not a policy counterfactual or a promise that restoring size recovers705981.

## Cited delayed pairs

These are the document’s temporal pairings, independently linked to actual BTC parent ledgers. They are distinct episodes and can have different sizes, directions, exit timestamps and rights; pairwise differences are not isolated delay effects or sums of recoverable profit.

|S0→B entry|S0Q→BQ|S0 net ex funding|B net ex funding|S0→B final exit|
|---|---|---|---|---|
|2025-01-03 → 2025-01-04|11.755 → 8.268|46092.34400612|-5426.91204235|2025-01-06T15:46:00+00:00 → 2025-01-08T00:00:00+00:00|
|2026-03-13 → 2026-03-16|201.321 → 287.155|658351.95132688|-262204.15386452|2026-03-16T04:55:00+00:00 → 2026-03-20T00:00:00+00:00|
|2026-03-20 → 2026-03-22|429.296 → 404.011|772145.15518148214648|-504557.96696470914148|2026-03-22T21:20:00+00:00 → 2026-03-24T00:00:00+00:00|
|2026-07-18 → 2026-07-21|469.354 → 252.801|707107.22398714269880|-329339.675908088988796|2026-07-21T07:40:00+00:00 → 2026-07-25T00:00:00+00:00|
|2026-08-18 → 2026-08-19|464.975 → 321.238|252667.684456898000604|778571.68332722815288|2026-08-19T14:09:00+00:00 → 2026-08-20T00:00:00+00:00|

All10paired values round exactly to the document. These full-parent trade cashflows should not be confused with the prior ROI report’s native **portfolio return during the fixed S0 episode window**. For example, the B entryJul21can contribute positive marked portfolio return before the original S0Jul21morning endpoint, then later finish as a−329339.68trade. The two statements use different clocks and scopes and are compatible. This ledger validation does not independently prove the August “morning risk grew” or threshold-crossing assertions; those require marked inventory/equity evidence, owned by the risk/source passes.

## Early SOL is measured and material

|Recipe/cycle|native interval|gross|fees|net ex funding|
|---|---|---|---|---|
|S0/4|2024-12-23T03:15:00+00:00 → 2024-12-25T00:00:00+00:00|21490.000|421.62450000|21068.37550000|
|S0/5|2024-12-27T17:21:00+00:00 → 2025-01-03T00:00:00+00:00|157328.464|1674.06232400|155654.40167600|
|B/4|2024-12-31T00:00:00+00:00 → 2025-01-03T00:00:00+00:00|50030.000|659.64250000|49370.35750000|

The two S0 SOL cycles startDec23 03:15 andDec27 17:21, realizing21068.37550000 and155654.40167600; total176722.77717600. B’s Dec31–Jan3cycle realizes49370.35750000. Difference−127352.41967600 validates176722.78/49370.36/−127352.42. The first S0 cycle closesDec25; the other S0 and B cycles closeJan3at00:00, before the cited January BTC parent entries. Their final net realization predates those January sizing decisions. Some cashflow is posted earlier during the cycles; no artificial single realization timestamp is assigned to every cash mutation.

The two-year SOL fill-net delta−46710.21 does not negate this early−127352.42gap: later SOL path gains partially offset it, while the earlier gap changes the actual capital available to subsequent parent sizing. The ledger establishes timing and magnitude, not a one-to-one causal forecast of later BTC quantity or a right to add127352.42to a candidate TOTAL. attribution-SOL-cycles.csv preserves every actual zero-to-zero SOL cycle, including favorable and adverse outcomes.

## Provenance and checks

attribution-derive.py uses only saved CSVs and standard-library Decimal/ast processing. It does not import strategy/native engine code. It checks exact fee parity, flat asset inventory, every parent’s flatness/actualQ/direction, complete unique fill partition, BTC parent-net and SOL cycle-net reconciliation,51matched-day identities, and all24cited cents assertions. **636selfchecks pass.** attribution-document-claims.csv keeps every exact measured value and document-rounded comparator; attribution-summary.json keeps detailed booleans and input SHA256. attribution-file-manifest.json hashes this pass’s own attribution-* files only.

No old report, source file, ops document, Project state or external service was edited. Signed asset funding and native exported asset net stay UNKNOWN; the explicitly named confirmed-fill cashflow attribution is now available for descriptive research.
