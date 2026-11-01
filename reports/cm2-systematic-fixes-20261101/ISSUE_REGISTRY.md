# CM2 systematic correction registry — 2026-11-01

Base: b8dab4a0375451c4279db8ce05c7db9cddbe7fd0. Worktree/branch: cm2-systematic-fixes-20261101 / codex/cm2-systematic-fixes-20261101.
This is a source/contract inventory against the original 61-row 004e audit, not a rewrite of that audit and not financial qualification. No native engine constructed, economic attempt, deployment, venue request, or source publication performed. Full native acceptance of this complete new version: NOT_RUN. New economics: NOT_RUN. Engineering8/8 spent.

## Confirmed defect inventory

Every original FAIL row is mapped below. Shared causes are grouped; each affected ID is explicit.

| Original IDs | Cause in 004e | b8 disposition / minimal correction here | Files / focused evidence | Status and remaining limit |
|---|---|---|---|---|
| A04, A15, D05 | Native decimal precision did not implement HL significant-figure price format; no final normalized request contract | b8 added shared request helper, legal side-aware protective rounding, worst-fill positive-harvest recheck, final native factory/type/TIF/quantity/price/reduce-only guard | strategy/cm2_order_contract.py; cm2_native.py; test_cm2_order_contract.py, test_cm2_final_send_contract.py, test_cm2_harvest_execution.py | SOURCE_CORRECTED_IN_B8; constructor-free regression PASS. Native connected acceptance of exact latest source remains pending. No relaxation for fixture. |
| A06, A07, A08, A15 | Venue child caps existed in profile but were not consumed at final send; emergency child could bypass caps | b8 limits each child after quantity/price normalization; emergency also segmented. MARKET intended cap preserved; ambiguous LIMIT/IOC uses explicitly conservative min cap | cm2_execution.py, cm2_order_contract.py, cm2_native.py; order/final-send tests | SOURCE_CORRECTED_IN_B8. IOC backend category/wire price UNKNOWN; per-order caps are not position caps. |
| A11, D07, E04 | A legal partial reduction could itself leave a subminimum remainder, then full close HOLD | b8 shrinks reducing child only, or HOLD; never grows target/cap. Existing min10 remains conservative model policy. Here reason renamed to CONSERVATIVE_RESEARCH_MIN_NOTIONAL_REDUCE_EXCEPTION_UNKNOWN, opening reason VENUE_MIN_NOTIONAL; blocker reader handles both venue-prefix reasons and new policy reason | cm2_execution.py, cm2_native.py, cm2_fixture_dust.py compatibility reader; test_cm2_residual_dust.py, test_cm2_policy.py, test_cm2_fixture_e08.py negative partial-fullclose/deadline regression | AVOIDABLE_CHILD_CREATED_CRUMB_SOURCE_CORRECTED, NOT_ALL_RESIDUALS_SOLVED. Future price gaps/partially filled full closes/preexisting dust can still block. Old 004e failed reports preserved; reported 030 failure is same residual group, not a distinct new defect. Under-$10 venue reduce-only acceptance UNKNOWN. |
| D10 | Tick event timestamp was used as “now”; emergency reductions could use stale/future/crossed quote | b8 uses native clock and explicit fresh positive uncrossed BBO guard. Mandatory owned reduction may proceed with fresh BBO and risk-mark UNKNOWN; never increases under unknown risk | cm2_native.py, cm2_order_contract.py; test_cm2_order_contract.py, test_cm2_final_send_contract.py | SOURCE_CORRECTED_IN_B8. Historical stale fill not asserted. Live adapter latency qualification separate. |
| D07, D11, E04 | Drain had no durable first-start/deadline/reconciliation latch; normal SOL-only release was unbounded | b8 persists unioned required-zero scope and first 120s deadline, native timer, cancel/reconcile/no-new-risk on expiry; ordinary SOL release also scoped. Here negative residual test proves deadline retains explicit residual input and emits no order/phantom flat | cm2_native.py, cm2_order_contract.py, cm2_checkpoint.py; order/checkpoint/e08 tests | SOURCE_CORRECTED_IN_B8, CLOSURE_NOT_GUARANTEED. 120s is own research policy. Reconcile exposes blocked position; it cannot manufacture venue acceptance or flat state. |

## Newly localized compatibility / reporting defects

| Issue | Cause / correction | Files / tests | Status |
|---|---|---|---|
| E08 fixture versus b8 final guard | Old v2 overridden production factory mutated protected LIMIT/IOC to far GTC; correct b8 guard refused it, so it never became owned/submitted. New versioned v3 explicitly constructs test-only actual native owned GTC sentinel at 302min-1ns and 842min-1ns, requires actual +/-20 parent position, current admitted POSITIVE_HARVEST rights and finite10 remaining budget. Existing production factory remains IOC; production callback sees pending leaves and WAITs, then requests cancel at adverse 303/843 quote | new cm2_fixture_e08.py, runner v3 selector/API0 route; test_cm2_fixture_e08.py real native OrderFactory + actual policy/callback on explicit fakes; public probe dispatch test | IMPLEMENTED_SOURCE_AND_CONSTRUCTOR_FREE_PASS; actual native acceptance/cancel events NOT_RUN. Native engine source shows queue settlement after same-time data callback; v3 expected acceptance at sentinel timestamp, not old v2 timestamp. 18h, price/funding/profit script unchanged. |
| E08 report lookup | next() over absent submitted order raised opaque StopIteration after engine end | explicit indexed presence check raises phase=OID invariant; existing structured partial-native-evidence exporter preserves failure, actual cache observation and UNKNOWN financial qualification; zero fake order/fill/status | cm2_fixture_e08.py shaped_orders + test structured partial export | IMPLEMENTED_TESTED. Exact missing phase/OID visible; original failed E08 retained. |
| Misleading reduction-floor label | Old reason named conservative research minimum as venue law | new future-source reduction reason explicit UNKNOWN; minimum10 unchanged; native target_blockers reader explicitly accepts new reason; dust engineering reader accepts old/new labels to read old evidence | strategy/execution/native; dust fixture; policy/residual tests | IMPLEMENTED_TESTED. Historical data/reports unchanged; no size-zero/oversize order or minimum waiver. |
| Fee concern | Effective rates were already owner requested .000432 taker / .000144 maker, with referral already applied | no fee code/data change. Test asserts exact constants and both native profile instruments; re-applying effective_instrument_dict is idempotent | test_cm2_fixture_e08.py; unchanged venues/effective_fees.py and research/current_hl_profile.py | ALREADY_CORRECT; no second discount, no historical recalculation. |
| Zero-quantity safety | No zero-as-close-all contract is established; third-party serialization reports do not justify it | existing strictly positive validate_request retained; direct zero rejects REQUEST_QUANTITY_UNKNOWN. Rounded-to-zero planner input HOLDs; no order submission. | unchanged cm2_order_contract.py; new focused regression | VERIFIED_NO_WAIVER. No zero sentinel/placeholder/new SDK. |

## Original UNKNOWN / model limitations, not invented product bugs

| IDs | Why retained / required disposition |
|---|---|
| A05 | Reduce-only/full-close minimum exception not proven. Keep conservative min10 model policy and visible residue; no venue-law claim or live allowance. |
| A14, C06, E05 | M1 BBO, zero-impact/full-fill and assumed participation lack historical L2/queue/capacity proof. Existing MODEL_LIMITED/NOT_FAITHFUL_DIAGNOSTIC identity retained. Separately authorized robustness/data work required. |
| A16 | Native money/float VWAP/tier boundary matrix not fully qualified; no new accounting/precision scheme invented. |
| A17, D12 | Real backend MARKET/IOC category, wire price/band and trigger behavior not certified by native backtest. Python installed adapter maps actual quantity and reduce_only; Rust/backend behavior not inferred from it. |
| B01, B02 | Native free-equity/IM/MM vs venue collateral and all-pending fee reservation qualification incomplete. No duplicate margin or money engine. |
| B03, B13 | Bybit saved funding/mark proxy differs from HL oracle/hourly settlement. Existing source/data labels retained; no silent model/data rewrite. |
| B05 | Live cross/isolated/unified/authenticated account identity outside research scope; no account access. |
| C01 | Per-run coverage receipts required; incomplete/failed runs retain UNKNOWN. No failed totals fabricated. |
| C03 | Bybit close-availability shift source contract exists; live HL timestamp translation not qualified. No second shift. |
| C07, E02 | Reused-window optimization and differing source/control groups cannot prove fresh OOS or pure policy lift. Economic goal unmet; no parameter fix promised. |
| D03, D14 | Same-engine retained-cache replay does not implement full OS-cold/transport/venue takeover. Fail-closed cold guard retained. |
| D04, D13 | Purpose/parent/current rights and bounded handling source tests do not prove every pending-stop/live replacement/cross-asset race; v3 still awaits real connected proof. |
| D08 | Net hedge benefit/denial optimality remains an economic uncertainty, not a demonstrated source defect. |
| E01 | Per-physical-attempt executable provenance needed. This patch records exact installed source/binary/RECORD evidence; does not retroactively attest every run or assert installed/public-tag byte equivalence. |

Original PASS/N/A rows require no speculative edit. E08 original audit ID concerns attempt-ledger safety and is distinct from engineering fixture/run E08; no reset/borrow of engineering8/8 budget. Source patches do not relabel old failures.

## Exact checks and next gate

- 130 relevant constructor-free tests PASS; forbidden actual native constructor call count0. One earlier pytest collection invocation lacked parent runtime namespace; no tests executed there; import path corrected. Test receipt retains this limitation.
- Actual v3 API boundary: one intercepted boundary call, zero native engine constructions. reports/cm2-systematic-fixes-20261101/api0/api-boundary-proof.json.
- Old v2 is byte unchanged against b8: SHA256 7d70840e68750f5df57b859629a7bc94d9077a331f4847db3103d34ef9b9993d.
- PINNED_NATIVE_SOURCE.json records installed distribution1.231.0: risk/engine.pyx691–692 margin-account early return; adapter execution.py660–705 quantity/price/reduce_only mapping. Source and compiled risk binary hashes match installed dist-info RECORD. Public-tag byte parity UNKNOWN_NOT_COMPARED; differing public line layout is not proof of source equivalence or runtime mismatch.
- No reduction-floor acceptance proof arises from native margin-account early return; it is not an exchange exception.
- Narrow independent review required for this concrete diff. After report and owner approval only: any new connected native/economic attempt needs explicit budget amendment/source/config/fee freeze; engineering8/8 spent. No fresh run, publish, merge/deploy, live order or transfer authorized by this registry.
