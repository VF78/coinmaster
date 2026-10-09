# CM-113 bounded independent review

Decision: GO for the one authorized isolated native 24-month research comparison at final exact source commit d7d18cdc22c0ebb918f202eb9168fcc3159ed9e1. No unresolved P1/P2 found in the bounded committed implementation and focused proofs. This is research review clearance, not live/deploy readiness or a ROI claim.

Reviewed initial d219ee6972bb50982e5a683969a862b2ce3f83a6 against 3b9b9c1386385d6655bcc130dadb3aed59744eef, then the sole substantive correction d7d18cdc22c0ebb918f202eb9168fcc3159ed9e1 against d219ee6. Read-only; no shared source/docs edits, test rerun, full backtest, pilot, service, credential or issue action by reviewer.

## P1 found and resolved: invented native reservation credit

Initial strategy wave_overlay.py:1282-1301 subtracted fresh current policy IM+MM from prospective total while comparing the resulting increment to native free. Canonical research native_baseline.py:738 initializes BybitTierMarginModule with no static marks. Pinned Nautilus1.231 CustomData goes through DataEngine, not exchange pre_process; the strategy policy receives its marks while that module sees no marks and clears native locks. Consequently fresh policy cost is not proof of a native cash reservation.

Exact pinned native before-proof: cash/free9994, native IM0/MM0, current BTC policy6019.8 plus SOL50 policy5025, gate admitted=True despite prospective11044.8>native free9994. Owner reproduced this exact engine/CustomData path in margin-review-before.log.

Correction wave_overlay.py:1299-1320 subtracts only bounded actual native per-instrument IM+MM credit, min(current fresh policy cost, actual native reserved cost). Opening/unsupported orders sharing the instrument receive no IM credit. Cache-confirmed reduce-only TP retains valid credit; pinned native accounting/manager.pyx:315 excludes reduce-only orders from IM reservation. Native free is unchanged, missing/account-wide reservation evidence yields no invented credit, native unrealized PnL is used only in the same fresh-mark equity/gross basis. No margin-module/funding rewrite.

After-proof: exact canonical unreserved SOL50=False and SOL10=True. Actual native MarginAccount IM6000/MM500/free3494 accepts SOL10 with a real reduce-only GTC target, denies it with a real opening GTC order, denies SOL50 in both, and leaves free unchanged. Fresh-equity/stale/future-mark proof retained.

Tests: test_wave_native_integration.py:2079 test_lifecycle_canonical_customdata_native_empty_module_marks_admission_basis; :2131 test_lifecycle_actual_native_order_reservations_and_reduce_only_target_credit[False/True]; :1949 test_lifecycle_native_locked_margin_increment_and_same_fresh_equity_marks. Four focused cases passed in2.53s after correction. Native actual locks in the latter/order tests are explicitly set on genuine MarginAccount; canonical CustomData absence-of-lock case uses the actual initialized module/engine rather than manual locks.

## Other contracts checked

- Fixed accepted SOL half/full leaves survive partial IOC/cancel and native denied terminals. Confirmed fills decrement target; unknown ACK/queued child owns exclusivity, 60s bounded cadence; actual native leaves clamp reduction. Mandatory timeout, group/forced, terminal, liquidation and protection clear/preempt conditional ownership. Native two-episode proofs: tests:1795; denial/ACK/forced proof:2019.
- Zero-suppressed BTC fallback residual only requeues conditionally at original episode TP VWAP/wave eligibility. Adverse quote retains leaves without fill; positive resting TP and positive-price fallback ownership stay unchanged. Native profitable/adverse/confirmed proportional rights proof:1862.
- Omitted-level touch cannot latch before positive confirmed BTC/fraction; once-only activation retains current paired-session/backfill guard. State and native immediate-fill/later-touch proofs:1911,2047.
- q1 final normalized BTC quantity is floor-clamped to candidate cap30m at executable side. Gross q0 reference allocations/SOL H remain fixed, admitted net denominator changes before confirmed fills, native TP targets derive actual quantity. Long/short q1 cap proof:1987; existing partial-fill right tests retained. Market-fill slippage remains outside a pre-submit price guarantee.
- Unsubmitted terminal q0 queue/selection/domain pending clears; submitted unknown ACK remains AWAITING_NATIVE_TERMINAL until native terminal evidence. Terminal lockout blocks increases. Bounded proof:1911.
- CLI candidate-only cap30m and explicit opt-in flag/label/dependencies are tested. Default behavior, fee-negative positive TP2, fee floor, EMA/z, fractions/multipliers, funding, protection/native version and installed pilot remain outside the diff.

## Verification provenance

Initial full relevant owner suite:98passed/63.55s; verification.log SHA25686b9fd33dbbf4f7d8681bf66f673cb7751dbdbf54f07640d356cef92fe7535db verified.
Before native margin proof SHA25646b4f88ce0755752179942d6eea67218111a6458ecfe07e08158df09d87c7f10 verified.
After four focused native proofs SHA256ea738e4fd47580f140cf08ff2a5540453080f2f4c892257e4d283353bdd85155 verified.
Owner compile/diff-check pass. Reviewer inspected committed source/tests and exact logs without repeating the broad suite. Corrected TOTAL and full-path economics remain unknown until the authorized comparison.
