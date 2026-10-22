# VPS AI cleanup — final completion

Deleted exactly **120 approved paths** in two bounded passes: one obsolete AI environment and 119 individual fitted-model/checkpoint/learned-embedding/transform-cache files. Removed allocation: **1,858,576,384 bytes**. Sum of observed per-pass free-space gains: **1,858,441,216 bytes** (1.731 GiB). Final disk free: **3,868,995,584 bytes**; 91% used. Concurrent filesystem writes explain small differences between allocation, per-pass free deltas and wall-interval free delta.

The supplemental 100 files were copied obsolete Mac AI artifacts: 57 CatBoost `.cbm`, 29 fitted `.pkl`, 7 encoder `.pt`, 7 learned embedding `.npy`. Exact supplemental paths, bytes, identities and hashes are in `vps-cleanup-addendum-inventory.json`. Native runtime, numerical D1/real-price/funding/historical data, source/config/seals/reports/forecast/label/metrics/CSV and money/trade evidence remain. No snapshot, native/shared cache, dependency surgery or new environment installation occurred.

All 120 paths are absent. Fresh process dependency and exact inode/device/hash guards preceded each deletion. Protected service identities/MainPID/NRestarts and container IDs/PID/StartedAt/restart counts remained unchanged throughout; no service/process action occurred. No git/Project/source edits or experiments were performed.

The first pass retained-hash count was **20396**. The 100 supplemental learned-model files were intentionally removed from that population, leaving **20296** retained regular files. Supplemental before/after report digests match when those exact 100 are excluded. Every other native/runtime/data/dataset/result/job digest still matches the first-pass receipt. The original whole-reports digest intentionally changes; claiming all original 20,396 files remain would be incorrect.

See `vps-cleanup-final.json` for cumulative counts and before/final disk figures, and the two result receipts for exact service/container and retained-hash snapshots. No further cleanup expansion was performed.
