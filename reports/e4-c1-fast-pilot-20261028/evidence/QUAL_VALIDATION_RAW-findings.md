# QUAL_VALIDATION_RAW — failed process, independent financial evidence

Process remains FAILED_NATIVE_EXIT, actual child 75889 exit1, UUID c441e4fe-8a0d-43f0-8a83-62de3e14f1cf. No process0 waiver, normal PASS report or full qualification PASS. Physical attempt8 is consumed; no rerun.

Independent financial evidence RECONCILED from existing raw/native artifacts:
- Interval [2026-09-01,2026-10-28), 57 days, clean seed10000/reserve0. Feature-only warmup [2024-09-01,2026-09-01), 730 days. TOTAL19661.98052982, net9661.98052982, return96.619805298200%. The 2-year absolute profit floor is not a 57-day threshold or matched return comparator.
- Settled and coherent event DD independently recomputed as34.95109657022590675517330698%, within current51.80315157406654834417870238% cap and strict50%. Event peak29730.702585, trough19339.49601351 at2026-10-27 21:39 UTC. Sequence timestamps joined to event_ns.
- Seven unique closed native lifecycles sum9704.63309195 Position realized PnL (fees already included). Actual funding−42.65256213; seed+PnL+funding=19661.98052982, bridge0E-8. All26 actual fill and109 funding PRE/POST native cash mutations reconcile with0E-8 bridge, no unmatched/duplicate/unexplained transitions. Funding JSON matches aborted-renamed SQLite and actual event-pair deltas. No funding invented from bridge.
- Zero modeled liquidations, terminal native FLAT/open positions0/lockouttrue. All33 unique final native orders are closed:26FILLED/7CANCELED, active0.
- Complete event gzip:246510 contiguous sequence rows,164428 eligible event-DD samples,82079 immutable SETTLED_PRE_NEXT_SOURCE_WATERMARK rows. Full settled DD independently uses those actual immutable event watermark rows and initial seed; not an economic replay or regenerated standard report.

Material artifact availability limit:
- Original minute-native-settled-receipts.csv.gz is truncated: no gzip EOF marker,81654 complete data rows plus305 trailing incomplete bytes, last complete source2026-10-27 16:54 UTC. Its partial-only DD34.31829849654392215568288764% is NOT the full result. All81654 retained rows match the corresponding complete event-watermark prefix exactly. Full event watermark coverage reaches the proper endpoint and independently verifies the full settled DD. The truncated original remains unchanged; no normal receipt export was manufactured.

Actual failure cause and metadata distinction:
- Frozen native_baseline.py lines324–327 compute expected_months=max(1,(end.year−start.year)*12+end.month−start.month). Sep1→Oct28 gives1, incorrectly excluding partial final October; actual Sep/Oct monthly rows are correctly2. This is not a hardcoded24 assertion. Packaging fails MONTHLY_ROW_COUNT:2 after native work, and process failure remains authoritative.
- Raw audit state NATIVE_COMPLETE_PACKAGING_NOT_VALIDATED. Raw config selfhash cd20ace5fd0a4e0a65f9bcbf85622216aa330677857c841911508af1cfa375ba is valid but differs from intended final9c7e16e4bee8ab6c91dae5009b083b1509ffe6053d36c5c38af929964a78d1db: the preserved raw snapshot is saved at source1208, before eight split/cover metadata additions at1213–1243. Existing raw config keys exactly match intended config; adding only these known metadata fields yields exact intended9c7e hash in analysis. Original raw/config/failed receipt untouched.
- Source299197a7140ad0ae5c18aecdf596cbdbd7124bf4 source-file hash matches raw code_hash. Exact data manifest canonical hash1714540d189ce5dbc45489ea007f2fb16a5dafb9a451c13010ceee208639171b matches raw/argv. ReceiptSHA61546762847d41b2e9eb26bef146b87827bb908c526fdfdaba35056f5a110392 verified.
- Immutable rawSHA640a0abaa07a99ccdd682e8672828b4c1c90b1a6601a09680343d9af8ab4a3a2.

No native/engine runs, tests, product/source edits, old artifact mutations, normal-PASS export, optimization, retry or live readiness claim. Evidence preserves process failure separately from actual financial reconciliation. Complete existing event/native/account/lifecycle evidence prevents needing a repeat merely to discover the economic result; this does not waive process0 or authorize another attempt.
