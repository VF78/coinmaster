# M1 harness closure fe44f8e

**M1_STATIC_GO — unclosed P0=0/P1=0.** Source-only gate; native/tests/engines0.

Exact `140a6b975f5b55f54cc20fdfd4c300f029130554` → `fe44f8e0fd917b3753c5835d710524a1281a0da7`.

TP140-M1-01 CLOSED_SOURCE. Removed unjustified episode=None assertion; native Cache positions/open orders/inflight/pending0 remain mandatory and all cached orders require closed status plus terminal native event history. Retained historical alpha episode and domain pending are captured without resets.

- Exact git diff140→fe44 has3 files, no runtime/coinmaster change. Product closure from140 carries forward.
- Source seal contains sorted full runtime coinmaster/tests Python inventory, control config JSON, pyproject and uv.lock when present; byte hashes and full inventory equality reject changed frozen source. Root gate binds exact seal bytes SHA and source commit; canonical Git checkout checks explicit git -C root HEAD, while Git-less Mac copies use the sealed bytes.
- Launch still checks root_go/case/source/recipe/config/input and STARTED claim attempt/case/source before the single constructor. Root supplies the separately validated canonical unified-ledger/namespace/unique-claim binding; this static GO does not itself issue root GO.
- Output JSON uses allow_nan=False, actual newline and json.loads roundtrip. Native order event IDs/types/timestamps plus retained domain context are captured before cleanup.
- Frozen recipe/config/input pins unchanged; owner compact engine-free receipt read without rerunning it.

M1_STATIC_GO means no source blocker remains in the scoped harness correction. No native/matching/financial PASS or extra physical slot is granted. Root must finish its exact source freeze, ledger/namespace checks and one-shot GO before launch; actual native lifecycle, cash/fees and public modify ACK behavior remain unproven until the registered witness.
