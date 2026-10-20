# Storage gate: source unchanged, no engine

Existing30,000-fill facts were streamed to a diagnostic compressed SQLite; every decoded payload SHA and row count matches. Original audit190,496,768B→zlib120,004,608B. Original two CSV20,432,268B→gzip2,993,934B; decompressed CSV SHA matches exactly.

| Native fills | zlib archive + gzip CSV | Plus700MiB trace/journal/reserve allowance |
|---:|---:|---:|
|100,000|410.0MB|1,144.0MB|
|250,000|1,025.0MB|1,759.0MB|
|500,000|2,050.0MB|2,784.0MB|
|1,051,200|4,309.9MB|5,043.9MB|
|2,102,400|8,619.7MB|9,353.7MB|

Current free space is3,898,068,992B. Plain storage and simple per-row zlib+gzip do not prove a safe whole-period churn bound. These are measured fixture extrapolations, not exact candidate predictions: the fixture lacks real per-submission TARGET/TRIM audit rows, so a real candidate can cost more per order.

Actual admission guards: conditional reconcile returns on an owned SOL pending order (including UNKNOWN), and creates physical work only on a SOL executable quote. Main quote callbacks invoke conditional checking once per BTC/SOL quote; original-authority processing may also invoke it on that quote. Fills and required native exits may add lifecycle events. No unsupported unconditional <=1fill/min claim is made.

No source encoding change or economic repeat has been launched. Proposed next decision is more guaranteed storage or a separately reviewed narrower compression option; do not launch on an optimistic fill-count estimate. Compression diagnostics preserve original native facts and are not production artifacts. Existing memory-fix-completion/manifest remain unchanged.

Raw measurements and exact decode hashes: memory-storage-budget.json and memory-storage-gzip-budget.json. A future DELETE-journal audit failure must preserve DB plus any -journal sidecar; rollback/analysis runs on a working copy, not the immutable original family.
