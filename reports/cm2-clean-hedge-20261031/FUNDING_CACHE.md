# Exact native funding audit read cache

Future source only; active Mac R1 remains immutable779. No engine or account operation was run.

NativeEventJournal owns one persistent SQLite writer connection. Existing record_funding_cash/record_funding are INSERT OR IGNORE plus commit. Original reader scans funding_cash ORDER BY ts_event,event_id,instrument_id and sums requested-asset signed_delta with Decimal0; this exact query/order/sum is retained on refresh. No incremental sum, schema change, posting or cash/fee adjustment exists.

Cache revision includes connection identity, writer total_changes, PRAGMA data_version for external commits, and complete numeric Decimal context/traps. All in_transaction reads bypass/reset committed cache, including SAVEPOINT rollback. Reopen identity invalidates. Same-asset cached values replay Decimal flags from the exact sum; context/trap changes recompute. Assets are lazy, so malformed/unrequested other assets do not change the requested original behavior. Closed connections still raise instead of returning stale data.

9 constructor-free tests passed: both assets/absent; own backdated append/duplicate/update/delete/other-tablecommit; rollback with and without reads; nested savepoint; external append/update/duplicate/rollback; connection reopen; Decimal precision/order/flags/traps; malformed unrequested asset; actual CM2 _sync_funding method on plain fakes with both-parent deltas/duplicate callbacks.

Tiny performance uses792 synthetic rows, the same persistent WAL database and original/native sorted query before versus cached reader after,3x25 interleaved. No actual Mac financial rows were copied. Results and source hashes are FUNDING_CACHE_PARITY_PERF.json. No actual full-run call count, ROI or full-run speed improvement is asserted.

Callback ABI stays iid->Decimal. Factory/complete_report source provenance includes the new cache module. Native journal money, fees, ordering, config, features and policy remain unchanged. Report comparison must explicitly record this exact-behavior proof across779 and new cached source; source hashes are honestly different. Restart/joint-state persistence remains unimplemented.

Checkpoint requested before controlled VPS security maintenance. Full relevant regression/critical API verification remains pending after VPS_MAINTENANCE_RELEASED; no new native or API probe is authorized here.
