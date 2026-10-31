# Strict committed-native watermark qualification (report only)

Model ID: CM2_COMMITTED_NATIVE_WM_QUALIFICATION_V1. Original execution/data/policy/config/source IDs remain parent IDs. This repairs selection of a sparse legacy measurement export; it changes no native fills, cash, funding, fees, strategy callbacks or economic trajectory. It is not an assertion of identical source IDs.

R1 remains original OS1/physicalFAILED/spent one anchor with one actual engine. Original raw JSON/legacyCSV/coherenttrace/SQLite/ledger are never rewritten. No TOTAL/DD is qualified until ALL proof checks pass. Failure produces NOT_QUALIFIED and preserves partial derived evidence; use a fresh directory for any correction, never overwrite an earlier proof.

The original qualified coverage predicate is unchanged: canonical source=start+1minute+n*1minute; receipt=source+1minute;1,051,199 rows;24calendar months; final receipt=end. It runs only against a new derived directory containing the projected committed CSV, not against the intentionally sparse legacy recorder.

One streaming pass consumes completed coherent trace and all surviving legacy receipts. It selects ONLY actual persisted SETTLED_PRE_NEXT_SOURCE_WATERMARK records. Every sequence/source/receipt/epoch/common-mark/nativecash+exportedUPNL value must be exact. Every surviving legacy row must agree. Every missing legacy source must have an already-persisted retained-native watermark, its source/state/signature and PRE-native-mutation witness; causes are classified from actual PRE_FILL/PRE_FUNDING events, never assumed to be funding1:1. No interpolation or fabricated watermark is permitted. Missing and surviving counts must match original recorder metadata.

Exact frozen native DrawdownTracker28/HALF_EVEN reconstructs the complete settled and coherent interval curves, preserving event ordering and the original first eligible left-limit at end. Entire native summary dictionaries/top3/points must match. The qualified606 boundary function is extracted unchanged (precision80 and1e-24 tolerance); original month/fill/terminal conventions remain.

Native trace PRE/POST cash transitions and all fill IDs must pair exactly. Commission values sum only actual native audit amounts. Native funding rows must exactly equal read-only persistent SQLite rows and native observed signed cash deltas. Native closed-position realized values (already fees-inclusive), funding and terminal cash reconcile at exact0. No fill-based PnL simulator is used. Terminal native flat/orders, fullfeed/currency/DP gates, actual engine1 and original coverage are required.

Offline command (completed data stays on Mac):
<pinned-python> <newimmutable>/runtime/coinmaster/research/cm2_committed_validation.py --report <ORIGINAL-raw-native.json> --expected-report-sha256 <actualSHA> --legacy <ORIGINAL-minute-native-settled-receipts.csv.gz> --trace <ORIGINAL-coherent-native-events.jsonl.gz> --dd-source <frozen779>/runtime/coinmaster/research/minute_risk.py --coverage-source <qualified58b9a047-wrapper.py> --engine-count <ORIGINAL-engine-construction-count.json> --request <ORIGINAL-request.json> --go <ORIGINAL-GO.json> --ledger <own-trials.jsonl> --out <NEW-separate-derived-directory>

Outputs on success: minute-native-settled-receipts.csv.gz, COMMITTED_QUALIFIED_NATIVE_REPORT.json and QUALIFICATION.json. Receipt binds raw/derived/source/stream/SQLite/metadata hashes, original parent model IDs and unchanged ledger prefix. Later append-only ledger rows are allowed; editing the original failure prefix is rejected. CLI prints status/counts only, no premature TOTAL.

Future worker postprocessing invokes this same helper after native completion; the sparse legacy recorder remains honestly sparse. Engine count metadata is persisted before qualification. Original raw-native file remains unchanged; canonical final output gains explicit derivedfinancialPASS/model linkage only after proof. No strategy callbacks were added.

Analyzer manifests for recovery must point native_report to ORIGINAL raw-native JSON and settled_receipts to ORIGINAL sparse CSV, plus derived_receipt=QUALIFICATION.json and qualifier_source=<same reviewed new helper.py>. Request/GO/engine_count/ledger prefix hashes must match. The analyzer reads derived report/CSV only after these checks, keeps physicalFAILED, and labels hash-bound financial recovery. All DD including actual terminal-flat cash, structuralUNKNOWN, robustnessNOT_RUN, persistenceNOT_IMPLEMENTED and MODEL_LIMITED remain separate. No VALID_IMPLEMENTATION/winner is asserted.

Semantic cache equivalence is explicit root reference metadata, not silently identical source. Inflight/finished R1 executed779; cached future controls have different source IDs with exact-cache parity evidence.
