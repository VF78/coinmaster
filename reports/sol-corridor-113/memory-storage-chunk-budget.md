# Chunk measurement — no source or engine change

The existing 30,000-fill native audit converts losslessly to 256-record zlib JSON chunks for sequential order bundles and audit/fill rows. Accounts retain individual timestamp-indexed entries; contexts and exact trade IDs retain individual lookup entries. No schema dictionary is needed. All payload, native-event, and persisted lookup hashes/counts match. Full CSV gzip decoding matches original CSV SHA.

Measured archive 38,137,856 bytes, both CSV gzip files 2,993,934 bytes: 1,371.06 bytes per fixture fill. At the planning floor of 2,102,400 fills, archive plus CSV is 2,882,515,843 bytes. A separate 700 MiB allowance includes 150 MiB trace, 100 MiB funding/working journals, 50 MiB metadata/logs/fixed budget rows, and 400 MiB reserve. Total 3,616,519,043 bytes.

Free disk at measurement was 3,703,943,168 bytes. Four derived codec measurement SQLite copies total 308,326,400 bytes; after explicit provenance-backed removal, estimated free space is 4,012,269,568 bytes. None has been removed. Original diagnostic facts, original results, and old OOM evidence remain.

Remaining headroom beyond that total is only 395,750,525 bytes (188.24 bytes per planned fill). Real TARGET/TRIM audit rows, partial/cancel event differences, larger numerical payloads, and fills beyond the 2x planning floor are not bounded by this synthetic full-fill fixture. Pending guards do not establish a universal one-order-per-minute limit. Therefore this is a useful measured improvement, not yet a safe all-output upper bound or authorization to launch. Source remains frozen; no additional codec or engine is running.
