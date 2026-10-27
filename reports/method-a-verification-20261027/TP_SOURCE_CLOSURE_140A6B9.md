# Method A TP — closure 140a6b9

**Product source: P0=0/P1=0. M1 harness: P1=1, HOLD before root GO.**

Exact correction `d97a15d818a3a5dc1416fd41f5e33ab2a8ccaedd` → `140a6b975f5b55f54cc20fdfd4c300f029130554`. Source-only closure; engines/tests/native0.

## Prior review disposition

- `TP-D97-01` — CLOSED_SOURCE: _ma_before_fill dispatches native-event history before domain application; authoritative closed order clears commands and expected cancels at method_a_tp.py116–122. Partial fill retains owner.
- `TP-D97-02` — CLOSED_SOURCE: omitted Method A reductions no longer add oldSOL right or stamp its decision cycle in domain; original deferred crossing/session route remains. Separate raw target denominator mirrors legacy retained/reference allocation.
- `TP-D97-03` — WITHDRAWN_NOT_APPLICABLE_AS_ADMITTED: exact ce7 config tp_fee_floor_v1=False; existing constructor guard wave_overlay.py232 rejects split_tp_ioc=True with fee_floor=True. It was not a valid reachable P1 in admitted E4. Defensive canonicalization does not constitute proof that an admitted bug was fixed.
- `TP-D97-04` — CLOSED_SOURCE: positive target changes use public modify_order with total=actual filled+desired remaining; only zero entitlement cancels. Latest accepted/updated Cache history determines coverage; pending command has no ACK credit; _ma_entry_ready blocks further entry submission while unresolved.

## M1 harness blocking finding

**[P1] Final episode-none assertion has no source route after legitimate TP-flat second parent** — `runtime/tests/run_method_a_m1.py:206`.

The last daily signal is recipe second86400; the SHORT second parent is admitted after the H4 input at100800. Final129600/129601 inputs contain only VenueMark/QuoteTick objects. Normal TP fill terminal calls domain.on_parent_terminal→on_parent_cancelled, which retains an episode with historical BTC entry quantity. The only normal clearing method is on_group_flat after explicit group-close reconciliation. Plain VenueMark/QuoteTick callbacks do not invoke _submit_terminal_closes; terminal_close_at_ns is checked for dispatch only in _try_advance_session at a paired DAILY signal (wave_overlay.py:1190). Consequently all real second TP fills and fully flat native Cache do not imply domain.episode=None, yet run_case asserts exactly that. This can burn the registered constructor on a harness-only unreachable final condition.

Before GO: Resolve the harness assertion against the actual native flat/ownership contract or provide a causal natural final group-close input. Do not clear domain manually, inject a close/order/fill, or count post-cleanup flatness. Product policy correction budget is not reopened.

## Other scoped checks

- one_constructor: One BacktestEngine call at runner233, only after root gate and STARTED claim checks. prepare path builds config/instruments/public inputs but no engine.
- gates: Gate binds current HEAD, case, recipe/config/input SHA, attempt ID; claim matches source/case/status/attempt. Root must separately bind claim receipt to actual unified-ledger snapshot, namespace and unique physical claim before constructor; runner itself does not read/hash canonical unified ledger.
- inputs: Frozen23rows/95 public input objects; seed729 sides LONG/SHORT; genuine QuoteTick depth inputs and public signal/mark/H4 routes; no M1 private Cache writes/domain on_fill/order injection/second matcher found. Fixture venue consumptionTrue/barFalse declared stress-only, distinct from economic P0/P1 consumptionFalse/barTrue.
- captures: Native Cache positions/orders/inflight asserted and captures before end/dispose; one further harness P1 remains at final domain-none assertion.
- proof_receipts: Owner reports10 pure groups and real Cache/Order/Position method-unit replay using synthetic test events, modify3/cancel0; these are explicitly not native matching/M1/economic PASS. Read-only review did not rerun them.

Added runtime hooks guard on method flag; _ma_entry_ready immediately returnsTrue; new domain eligibility branch reduces to prior behavior when false. No defaultOFF behavioral interference found in scoped diff.

UNKNOWN/not executed; public modify ACK/fill semantics, nonzero latency continuity, actual event order, account/fees, both natural parent execution, report output and terminal ownership require registered native witness after root one-shot GO. No PASS granted.

The former four-P1 headline is superseded: three admitted product defects closed in one correction batch; the fee-floor finding withdrawn as unreachable under admitted guards. No extra product correction, engine budget, or financial permission is requested or inferred.
