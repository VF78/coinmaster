# ObserverV2 closure3604532

**Source closed: P0=0/P1=0. Root native GO=false. Reviewer tests/native0.**

`V2-C963-01` — CLOSED_SOURCE: legacy_sessions now explicitly reads DailySignalBar.instrument_id, native Bar.bar_type.instrument_id, or null; unknown public types raise explicitly. Actual stock daily_signal(...).data objects are used in the normal checkpoint snapshot regression, with exact instrument/ts_event/ts_init assertions. Separate Bar and empty/null tests cover the alternate public inputs. The actual DailySignalBar AttributeError path is removed.

- Correction changes only observer public-type import/branch, focused unit setup/assertions, interface and checkpoint. Runtimea4 and common/worker/preflight334 remain unchanged by transitive exact diff.
- Six actual admission facts, immutable pending/queued Intent copies, original checkpoint once/true/false/error semantics, bounded observer-only error latch and read-only state/native getters are unchanged from scoped C963 review.
- Owner receipt reports eight focused pure groups PASS, constructor attempts[], engines0/matching0. This reviewer inspected source only and did not rerun tests or native code.
- VM financial dirty-file preservation hashes remain in checkpoint unchanged; no financial source, native ledger, raw artifact or original P0 state modified by review.

Active ce7 source permits SOL_ADD only via domain.decide/_intent→pending→strategy queue. H/fraction/consumption mutations run in wrapped fill callbacks; touch/activation in wrapped quote callbacks. Already queued intents can be observed before a subsequent writer; callback-created intents are exposed after creation or at same-call admission. Stock1.231 queued native commands do not reenter a later fill before the current callback returns. No concrete writer-before-first-observation counterexample was found for the exact registered paths. This is a per-intent causal argument, never a global queued-lifetime H/fraction/session immutability claim.

- Actual V2 stream must prove each relevant intent/CID and writer interval, all required clocks/origin/admission facts, capture attempts==recorded/error_count0 and genuine native ACK/fill joins; missing/stale/conflicting fields remain UNKNOWN.
- A separate source-reviewed stdlib rights verifier must consume the actual V2 schema faithfully to ce7 oldSOL, without current-budget clamp, P3/A0 rules or final-H/session reconstruction.
- Before any reserve constructor: exact observer/reader/source/input/profile freeze, unchanged normalized P0 fill/cash/funding/fee/terminal reference, fresh UUID/repeat_of/deadline/canonical claim and explicit root one-shot GO within prefix6/total17.

The narrow observer source blocker is closed. No native replay, complete rights qualification, financial receipt or P1 GO is granted.
