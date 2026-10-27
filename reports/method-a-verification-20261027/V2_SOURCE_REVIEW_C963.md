# ObserverV2 source review c963

**HOLD: P0=0/P1=1. Native/tests0.**

**[P1] Session capture assumes Bar, but registered producer supplies DailySignalBar** — `reports/method-a-verification-20261027/prefix_observer.py:60`.

legacy_sessions.native(value) dereferences value.bar_type.instrument_id. The actual stock exact-a4 path receives DailySignalBar via strategy.on_data; it stores that object in _day (wave_overlay.py672), and _try_advance_session assigns the selected objects directly to _current_btc/_current_sol at1182. DailySignalBar (venues/signals.py11–26) exposes instrument_id, ts_event and ts_init but no bar_type. After the first accepted daily session, every new evidence.state() invokes legacy_sessions and raises AttributeError. This occurs in ordinary pre_process/callback recording outside the admission-only exception latch, so it can abort the sole reserved native child. Focused V2 unit setup constructs Bar instead and misses this actual public producer type.

Correction: Read the actual public DailySignalBar.instrument_id or handle the two explicit public types without inferred fields. Add a focused engine-free regression using actual daily_signal/DailySignalBar objects through the existing stock on_data/session assignment shape. Preserve exact timestamps/nulls, original callback/checkpoint result and all immutable runtime/other-wrapper bytes.

## Verified scope

- Exact diff changes observer/interface/focused test/receipt only. Runtime diff froma4 empty; common/worker/preflight diff from334 empty. No native order/account/domain/cash/config mutation introduced.
- ActualTrue SOL_ADD override calls original _record_submission exactly once; false and original exceptions propagate unchanged. Admission-only capture exceptions latch bounded metadata and return original result. Initialized native order explicitly earns no ACK/fill credit.
- Existing six facts plus separate transfer/retired/raw denominator/original candidate/quote/instrument/immutable pendingIntent are copied, with float.hex and explicit Decimal/native strings; no current-budget clamp, final-H substitution or new P3/A0 rule.
- Full queued Intent and pre-domain episode/session state now appear in callback/pre-matching frames, supporting per-intent origin proof. Active-ce7 ordinarySOL_ADD creator is domain448→pending357–359→strategyqueue1369; subsequent H/fraction/consumed writers are inside wrapped fill callback, raw-touch inside wrapped quote. Native1.231 use_message_queue defaultsTrue and send/drain serializes later commands after callback return. No concrete writer-between-creation-and-first-observation counterexample found for these registered paths.
- Streaming/coalescing/1MiB hash/count-onlyUUID remain. New admission counters scalar; error samples capped8×80; maps/current queued native work bounded by active state.
- Eight owner focused pure groups inspected only; their actual Cache/Order/Bar test snapshots are not native matching or actual financial proof. Need actual registered DailySignalBar type coverage for the single remaining finding.

Even after this public-type fix, source closure does not prove actual per-intent/CID/writer-frame coverage or complete legacy rights. Require zero capture errors, all admitted initialized CIDs joined to real ACK/fills, actual creation-origin interval proof and unchanged normalized P0 economic trace. Root nativeGO remainsfalse; preserve sole reserve and VM dirty financial files.
