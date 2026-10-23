# Final independent saved-native-output validation

**ALL8VALIDATED; NO50/90WINNER; NO CONDITIONAL RUN QUALIFIES.** This is a completed negative economic result, not goal achievement. E4has the highest terminal TOTAL and passes90%net-profit retention, but fails full global DD. S has the lowest tested global DD57.14703597783395322774634393%, still above50and even the55near-bound. No parameter search or automatic next run is authorized by this validation.

## Exact economic gate

Seed10000; immutable S0TOTAL6077107.23887483, netprofit6067107.23887483. Required candidateTOTAL5470396.514987347, equivalently `(TOTAL−10000)/(6077107.23887483−10000)>=.90`, full original-global-peak settled DD<=50%, zero liquidations and complete valid evidence. The rounded-cents threshold5470396.52is not substituted for the exact comparison. Scalar formula/threshold/owner-receipt readback checks are in verifier-scalar-criteria.csv and verifier-final-decision.json.

|Recipe|native TOTAL|net-profit retention%|global settled DD%|native fees|BTC/SOL native fill rows|50/90|
|---|---|---|---|---|---|---|
|P0|4622034.27336437|76.01702247510777033476616279|57.58541045962226379114466259|592090.31669918|322/162|FAIL|
|E4|5631617.35953723|92.65729347120922274896207062|57.58541045962226379114466259|706755.52937844|337/198|FAIL|
|EP|3992055.58641779|65.63351247366905933081845698|57.58541045962226379114466259|615999.76639960|341/179|FAIL|
|Z|2517706.78173418|41.33282440874152968490857052|60.29622291086218148072256726|438106.32694056|310/144|FAIL|
|S|4155625.77863239|68.32952864372335303307712839|57.14703597783395322774634393|557093.62594034|322/153|FAIL|
|XZ|4877453.55144460|80.22692462491052470340223871|60.29622291086218148072256726|684757.69258637|327/167|FAIL|
|XS|5406345.11636863|88.94428438303662495658496376|58.94743688415397241603930272|691507.32515017|337/195|FAIL|
|XZS|4696068.73175334|77.23728207287120124646626314|58.71953818315642454894385564|670582.02285807|327/164|FAIL|

E4exceeds the exact TOTAL threshold by161220.844549883; XS misses it by64051.398618717. Neither has a qualifying DD. XZS ends4696068.73175334with77.23728207287120124646626314%retention, DD58.71953818315642454894385564%,491fills and native fees670582.02285807. It has14actual zero-retrace BTC risk orders plus1actual SOL risk order; no liquidations. No sum of standalone improvements is used to evaluate a combination.

## Independent audit and fixed provenance

All8recipes pass38core checks each (**304core checks**): frozen wrapper/raw hashes, independently rehashed config payloads and prepared config identity, original data/policy identity,89frozen source-file hashes and13actual input pins, native CSV hash/count, commissions, terminal account/cash/position/order/lifecycle identity, native flat-inventory proof and full unique closed-cycle ledger reconciliation, native funding-event row counts, and independently streamed settled DD/coverage. Each has10additional explicit-liquidity cost checks (**80checks**). P0has18exact old-B parity checks;50additional scalar/budget/readback checks pass. All**452named checks**pass; no mismatch or unavailable receipt is hidden.

Sourcebd04c9b3858bcda40060a08eff488849c69af5d8, immutable archive under source-bd04c9b; source scientific/implementation correctness review belongs to the separate code reviewer. Data hash7ab5ae2cdaa14885da28d188c7ad14dfc8168ee600b78535f7317409ea94e9cc and native execution-policy hashc9540fbef259039c95829a774ef54e0eea2dcf2b6748d6455e171bf28e889834match original B for every recipe. Allactual market/input pins are rehashed; venue manifests/risk-limit JSON resolve under source_snapshot, market files under data_root. Per-result config hashes, source hashes and artifact identities are retained in verifier-{recipe}-audit.json.

P0reproduces B from source25a085f596292df58e51188dd91e996adbe5724c: TOTAL4622034.27336437,484fills, fees592090.31669918, DD57.58541045962226379114466259% and full uncompressed settled-trace SHA256864830b3534a1de899a68e452999791f4eb8a50d6c872e3754e1152d64721c22exact. Config hash remains06c9e99ce88bed050a62ac38cb9c0370cde35ce8c990582b888c06e68bcf53ea. Native CSV normalization excludes random init_idonly; funding identity compares the complete ordered funding_events SQLite rows, never job path strings. No quantity/price/fee/time/account tolerance or exclusion is introduced.

## Full native settled risk and changing failure mechanism

Every recipe has1051199native settled receipts,0missing,0invalid timestamp rows and0liquidations; no synthetic interpolation or stale-mark cash substitution. Seed and global peak never reset for the criterion. Full independent uncompressed trace hashes are recorded. Monthly native observed equity returns are diagnostics separate from cash drawdown and post-boundary terminal cash. Terminal positions and native orders are flat; actual closing fees and the preterminal-equity-to-final-cash bridge remain explicit in verifier-cash-bridges.csv.

The native mechanism at the original and new global maxima is:

|Recipe|native peak receipt UTC|native trough receipt UTC|peak equity|trough equity|actual native trough holdings|
|---|---|---|---|---|---|
|P0|2024-10-03T04:01:00+00:00|2024-10-03T15:45:00+00:00|14743.45772484|6253.37707805|BTC short 0.940@60887.24999999999; SOL long 1000.0@140.09|
|E4|2024-10-03T04:01:00+00:00|2024-10-03T15:45:00+00:00|14743.45772484|6253.37707805|BTC short 0.940@60887.24999999999; SOL long 1000.0@140.09|
|EP|2024-10-03T04:01:00+00:00|2024-10-03T15:45:00+00:00|14743.45772484|6253.37707805|BTC short 0.940@60887.24999999999; SOL long 1000.0@140.09|
|Z|2024-10-03T04:01:00+00:00|2024-10-03T15:45:00+00:00|14171.0598339|5626.44600762|BTC short 0.896@60887.24999999999; SOL long 1000.0@140.09|
|S|2025-01-13T00:37:00+00:00|2025-01-13T14:37:00+00:00|156612.85793845|67113.25166645|SOL long 4000.0@187.23|
|XZ|2024-10-03T04:01:00+00:00|2024-10-03T15:45:00+00:00|14171.0598339|5626.44600762|BTC short 0.896@60887.24999999999; SOL long 1000.0@140.09|
|XS|2025-01-13T00:37:00+00:00|2025-01-13T14:37:00+00:00|151829.51287244|62329.90660044|SOL long 4000.0@187.23|
|XZS|2025-01-13T00:37:00+00:00|2025-01-13T14:37:00+00:00|152418.7843454|62919.1780734|SOL long 4000.0@187.23|

The7test candidates expose different economic paths. E4/EP retain P0’s Oct3global maximum. Z/XZ keep1000SOLlong but have smaller0.896BTCshort and lower inherited cash, worsening the same early episode. S/XS/XZS reduce early SOL exposure but their new global maxima move toJan13, with **SOL4000long at187.23and no BTCposition** at both peak and trough. The conditional opposite-BTC/SOL hypothesis does not automatically cover these observed SOL-only states. The recorded native mark OHLC is original source data; do not multiply raw closes into purported native perasset PnL without native tick/rounding semantics. Authoritative native equity/cash and native positions are preserved directly.

XZS’s new peak152418.7843454Jan13 00:37→62919.1780734at14:37recoversJan14 14:42at152531.35187706. XS peak151829.51287244→62329.90660044and S156612.85793845→67113.25166645occur at the same peak/trough timestamps with the same4000SOLlong, but different actual inherited cash. This is observed capital/risk path dependence, not a native accounting defect.

The actual S-family cut is500SOLsell@134.72with37.048native commission onOct3 15:00, not the document’s illustrative135.84. StandaloneS still has52.58012598855353113295331574%DD in the early episode; its6991.32907805trough is380.39978437below half the unchanged14743.45772484peak. Z’s Aug19actual cycle has no actual zero-retrace risk fill and remains profitable; it must not be reported as an observed August false stop. Actual reduce-only risk-order proofs are in verifier-actual-risk-fills.csv (46orders overall: Z15, S1, XZ14, XS1, XZS15). Sourceowner’s arm/cohort source audits are separate and not duplicated here.

The single corrected saved-trace pass per candidate yields192monthly rows and70distinct global-peak excursions reaching30%, with202available peak/trough/recovery native snapshots. Small caches also preserve6priorA/C/Dboundary pairs per recipe, keeping actual prior/first-at-or-after receipt times rather than interpolating a boundary. P0’s first discarded analysis traversal hit an input-path helper error; root explicitly authorized one corrective extra P0read. The corrected risk cache was immediately persisted and reused thereafter; no other recipe trace was rescanned.

## Actual asset cashflows, fees, and unallocated bridge

Every asset terminal signed quantity is exactly0. The finite actual ledger identity `sum(SELL qty×avg_px)−sum(BUY qty×avg_px)−native commissions` therefore identifies closed-inventory **confirmed-fill net excluding allocated funding**. This is not an exported native asset-net field or a second matching/PnL engine. A positive or negative portfolio cash residual is explicitly unallocated; it is never assumed to be signed asset funding.

|Recipe|BTC confirmed-fill net ex funding|SOL confirmed-fill net ex funding|unallocated cash bridge|
|---|---|---|---|
|P0|3946306.012935777170138|631950.99496505|33777.265463542829862|
|E4|4858451.835330331913550|713702.32329125|49463.200915648086450|
|EP|3399477.062780855390834|541318.58081955|41259.942817384609166|
|Z|1973456.171314044271116|495268.43114540|38982.179274735728884|
|S|3501449.380877217076984|607450.36588245|36726.031872722923016|
|XZ|4038832.331921749476820|773949.53719190|54671.682330950523180|
|XS|4647041.001250102086962|699990.91529975|49313.199818777913038|
|XZS|3868254.522810899616040|762582.68273105|55231.526211390383960|

The native fill-audit cost table uses explicit native_liquidity_side, not order type. Actual notional/commission sums and counts reconcile to the native totals and each asset’s native commission ledger for every recipe. Here are the actual liquidity totals; verifier-liquidity-costs.csv preserves the32BTC/SOL×MAKER/TAKERrows, including genuine zeros:

|Recipe|maker actual notional|maker commissions|taker actual notional|taker commissions|
|---|---|---|---|---|
|P0|518743391.4779|103748.67829558|887893888.0061|488341.63840360|
|E4|652023664.7018|130404.73294036|1047910538.9778|576350.79643808|
|EP|530036175.3212|106007.23506424|927259147.8820|509992.53133536|
|Z|378679598.9878|75735.91979756|658855285.7142|362370.40714300|
|S|486648325.4206|97329.66508412|835934474.2837|459763.96085622|
|XZ|629862634.8638|125972.52697276|1015973028.3879|558785.16561361|
|XS|636763395.7793|127352.67915586|1025735719.9892|564154.64599431|
|XZS|615810914.3061|123162.18286122|995308799.9939|547419.83999685|

Native aggregated filled-order CSV average-price serialization can introduce tiny notional residuals versus fill-audit price strings, as already documented for B. The fill-audit native notional is the primary cost basis; neither representation is silently rounded or declared identical. Native commissions match exactly on both ledgers. Native signed asset funding remains UNKNOWN because the funding audit exports rate/mark/post-account total without a per-asset signed cash delta.

The828actual closed-asset cycles reconcile every filled-order row exactly once to the flat asset ledger. The144loss-streak rows describe consecutive negative actual closed-cycle fill net excluding funding; zero/nonnegative cycles end a streak. These sums are actual historical accounting, not removed-trade counterfactuals or future policy profit. They do not replace marked-equity DD. The allrecipe BTC maximum streaks are P0:7/E4:10/EP:9/Z:7/S:7/XZ:10/XS:10/XZS:10; SOL:1each.

## Final bounded decision and files

Authoritative owner ledger readback:8started/8completed,0reserved, current_engine=null, conditional_authorized=0, native_launches_closed=true. All8main attempts are COMPLETED_VALID_NATIVE; no candidate passes50/90or DD<=55. verifier-final-decision.json hashes this readback and records no automatic follow-up. Verifier engine runs=0. No source/product edits, replay, data fetch, SSH, services, credentials, orders or pilot action occurred. Native source correctness and deployment approval are not inferred from this saved-output audit.

Root can aggregate these exact standalone CSVs into the required generic report names: verifier-completed-summary.csv, verifier-scalar-criteria.csv, verifier-cash-bridges.csv, verifier-liquidity-costs.csv, verifier-monthly.csv, verifier-DD-ge30-episodes.csv, verifier-DD-native-snapshots.csv, verifier-asset-fill-net.csv, verifier-closed-cycle-ledger.csv, verifier-loss-streaks.csv and verifier-actual-risk-fills.csv. Perrecipe verifier-*-audit.json and verifier-*-risk-cache.json retain full pins and native evidence. verifier-file-manifest.json hashes only this pass’s own verifier-* outputs. No further automatic work follows.
