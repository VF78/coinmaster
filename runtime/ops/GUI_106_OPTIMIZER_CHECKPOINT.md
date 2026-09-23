# GUI #106 — bounded native optimizer job checkpoint

Status: implemented locally; no 24-month economic optimizer run was launched.

- The only GUI optimizer search is the sealed Stage-G BTC notional one-axis set `7.375, 7.625, 7.875, 8.125, 8.375` (five variants, TOP20 cap). It calls the existing `run_native_diagnostic` engine with funding and private per-job artifacts; it does not route orders or promote a candidate.
- `READY` requires the selected saved config to map exactly to the sealed Stage-G candidate, the exact 2024-09-01 to 2026-09-01 four-stream manifest to claim complete minute coverage, each normalized parquet to match its manifest SHA-256, and the shared native research lease to be free. Start and child recheck; immutable request includes the source manifest hash.
- Baseline and optimizer share one atomic lease and owned-process cancel/restart path. The optimizer result is diagnostic, ranks only reconciled terminal ACTIVE+RESERVE TOTAL, retains ROI/DD/liquidations/fees/funding/fills/limitations, and is accepted only after result and per-candidate private evidence hashes are checked.
- Verification: 70 focused Python tests passed (API, new optimizer fixture tests, prior native optimizer and baseline); `npm run check`, `npm run build`, and `npm run invariants:nautilus-research-ui` passed (26 UI checks). The existing process-signal tests require execution outside the macOS sandbox. Pandas deprecation warnings remain unrelated.
- Next: deploy under #105, confirm the live data root and saved sealed Stage-G research config show `READY`, then let the user explicitly start any full 24-month run from the GUI. No result or economic ranking is claimed by this checkpoint.
