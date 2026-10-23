# Independent focused contract review

Status: **SC01 SOURCE CHECKPOINT PASS; FULL G1 / HISTORICAL GO PENDING**. Reviewed frozen SC01 commit `6e7ab3da243d3916538f246f1cc7420bdc260a25` using canonical VPS `git show`, its five-file diff and surrounding submit path. Source-owner working tree was not read or changed. Source target is E4 `bd04c9b`; pinned native receipts are Nautilus `1.231.0`. This document approves no full historical engine; root owns that decision.

## SC01 findings

No blocking source defect found in this checkpoint. Research flag defaults OFF and is passed explicitly through native runner/config/hash. `child_quantity` validates finite quantity/step and floors min(original executable quantity,1000) to native lot. Placement precedes the original minimum/margin admission, while original notional entitlement and domain D1 scheduling remain intact. Order mapping is established before submit; native event observation does not rewrite receipts or credit money. Audit payload uses JSON-safe quantities/prices. Source scope is research policy, integration, observer and tests; no production configuration/service/key/order change is present in this diff.

Inspected persisted native matrix and lifecycle receipts and owner test source. Requests500/1000/2500 and depths500/1000/2000 cover below/equal/above child cap, full and partial IOC terminals. At depth1000 old2500 IOC is CANCELED after1000; child1000 is FILLED1000 with the same actual commission. The dedicated test compares native cash/init-margin, domain SOL quantity/consumed notional and pending removal. At depth2000 the old IOC fills2000 versus child1000; this is intentional model sensitivity, not equivalence.

Two same-quote child orders each fill1000 at displayed depth1000; depth500 each fills500. Thus this pinned default L1 behavior does **not** cumulatively deplete displayed size across separate IOC orders. It cannot be described as shared historical liquidity evidence. No custom depletion fix was added.

Tests also cover lot/input validation, original next-D1/right exhaustion, native reject, native confirmed cancel, off-lot native denial, local margin denial and actual reporting JSON roundtrip. Owner's broader log records131 relevant PASS; owner reports29 focused PASS. Reviewer inspected source, logs and actual receipts, but did not independently rerun those suites.

Two precision limits were sent to the owner: the late-fill test overrides `cancel_order` to return without transporting cancellation, so it establishes a real native fill after a local unconfirmed cancellation request, **not** an exchange cancel-ACK race. Confirmed native cancellation is tested separately. The local margin-denial fixture mocks `_tier_allows_increase`; it is not proof that child sizing preserves actual full-history native admission. These limits do not block this source checkpoint, but must remain explicit in acceptance claims.

Full historical equivalence remains NOT_TESTED: smaller submitted children may alter margin admission, later rights/positions and BTC/SOL calendars even when short-fixture fills match. First full control must locate the first such divergence and decide archive comparability. A FILLED receipt must never be relabeled CANCELED to force similarity.

## SC00/SC02 offline evidence review

Reviewed data source SHA `4bd3c42ddd4ecb589ec84b83a19925b66785cfe36556bf8934ec0b5acf80f73b`, data-tests.json, causal summary and active rule inventory. Reviewer requested one targeted correction: implementation/branch/count verification must not be labeled economic-benefit verification. The owner corrected registry mechanical statuses to economic NOT_TESTED; only measured common-base E4-versus-B benefit retains scoped VERIFIED. Source/implementation evidence remains separate. The43-rule inventory covers the active economic layers and maps original requirements0–4; it is not a new72-pin re-audit or proof of optimal numerical settings.

The archive causal builder explicitly sorts parents by actual first-fill time and validates unique native first-fill/q1 joins, q0<q1≤fill, and decision/fill within the same actual EMA wave. Labels use the first native fill distinct from unchanged management PLANREF, frozen prefill ATR fraction, direction-correct minute MARK excursions through completed EMA-switch, and strict ready_at<decision eligibility. Censored labels remain invalid rather than zero; parent-ID deduplication/conflict checking prevents duplicate partial rows changing Q90 or weight. Decimal linear(n−1) Q90, pooled sides and min8 each group are explicit. The refreshed28 checks all report PASS.

This is sufficient archive descriptive/eligibility evidence:83 actual parents,50first/33repeat,50actual waves,81completed/2censored;24 repeat decisions eligible and19 descriptive k<1. It is not a live-hook prefix test or proof of predictive benefit. Archived decision held/pending/equity/full E4 gate state remain UNKNOWN; source hooks must capture those on future runs. Production H_BTC finite/nonfinite fallback, streaming label readiness and exact once-only sizing remain pending delta review. Neither offline counts nor local q1 perturbations are synthetic portfolio outcomes.

## Remaining source gate

SC03 and SC04 implementation and their tests are not covered by the SC01 checkpoint. Required delta: inherited USD budget/unique ownership/atomic reservation transitions and monotonic max-lot proof; live causal first-fill labels, completed-wave availability and finite Q90 fallbacks; observation state; final immutable source/config/data/engine/observer/terminal pins. Matched controls and root historical GO remain separate. Six physical full attempts cap includes failures, controls and repeats; reviewer started0.

## Staged G1 clarification

The first explicit-E4 control may proceed to root GO using frozen SC01 plus the reviewed reporting-precision delta, final pins/tests and preflight, with H_SOL/H_BTC flags OFF. Completion of unused hypothesis implementations is not a prerequisite for measuring execution equivalence. No additional SC01 source blocker has been identified. Precision delta review and final source/config/data/engine/observer/settlement verification remain pending; any included unfinished hooks must have no active effect with flags OFF. Each subsequent hypothesis engine requires its own source/test delta approval. Reviewer issues no full-engine GO.

## Explicit-control precision delta reviewed

Frozen commit `1ad834a91447bd877cc0a5aa204684d4badda16c` contains SC01 plus only the report-boundary precision patch. It wraps monthly-ratio multiplication/division in Decimal localcontext precision80, retains the exact1e-24 threshold and inputs, leaves report/money unchanged and restores ambient context. Tests cover the context28 false rejection and a real corrupted return. Reviewer independently ran the two precision tests against immutable Mac source: **2 PASS**. Owner frozen-source log records **31 PASS** (29SC01 +2precision; not six precision tests). Preparation/config inspected: explicit child enabled, no H_SOL/H_BTC source or flags, period/seed/E4 options preserved.

**SC01 explicit-control SOURCE GO**, conditional only on root final pin/preflight verification and root engine authorization. No additional SC01 blocker identified. This permits measuring historical equivalence; it does not assert equivalence or approve either economic hypothesis. Full historical engine GO remains false in reviewer artifacts.

## SC03/SC04 functional delta checkpoint

Frozen `27c1904a9b132c30632c1b471d7f688ab0f6c053` reviewed against clean control1ad. No blocking money/order/causal functional defect found. H_SOL uses fixed gross units, unique native opening leaves, unfinished-parent topup without counting full parent plus full child, unbooked entry fees and stressed future closing fees; affine maximal-lot proof matches code. H_BTC uses completed streaming labels with strict readiness, first actual native-fill reference, actual-filled-parent grouping and once-only scaling of domain already-capped notional before zero-TP/lots. Missing minute paths are invalid/censored. Reviewer independently ran immutable focused risk tests:9PASS. Owner logs40focused/142relevant PASS.

Default-OFF H flags leave trading paths unchanged; explicit-child mode enables extra observation only. q0 telemetry covers held quantity, pending IDs, native equity, closed signal vector and passed-existing-gates-to-q0 witness. Pending signed leaves/status and explicit ATR/EMA-distance/wave-age are not all fully exported; owner was asked for bounded observer completion or explicit remaining limitations. Full internal admission vector must not be claimed. This reporting precision is separate from functional policy evidence.

## Control non-equivalence and schedule interpretation

Root reports first control TOTAL6022427.55763206 versus archive E45631617.35953723: economically NOT equivalent. Matched S0 in the explicit execution model is required; old S0 cannot serve as its relative-profit control. A same-time original SOL_ADD pre-submit margin denial also exists where explicit child sizing produces an additional actual fill. The denied exact level remains UNKNOWN absent an ID/level witness. Smaller submitted size changing admission is a legitimate explicit-model difference: an additional fill is not itself an additional attempt. No blind callback scheduling fix is justified.

The unchanged per-level/D1 attempt guard and multiple originally allowed levels are compatible with §4.2. Conversely, a demonstrably new level attempt generated solely by changed FILLED continuation would breach the no-new-intraday-attempt schedule requirement; §4.3 would not waive that restriction. Current denial evidence does not establish that violation. Native FILLED remains genuine; no fabricated cancellation or selective deletion of PnL is permissible. Root retains all subsequent engine decisions and six-attempt accounting.

## Final bounded observer and clock delta

Frozen `8f2f78005325776d1f600297a0c2d39e29c48bdd` changes only read-only prefix telemetry and targeted tests from functional27c. The q0 snapshot now exports signed positions, native order sides/status/quantity/filled/leaves/known owners, unresolved IDs, free margin, closed ATR/EMA/distance and wave bar age. Full internal gate vector remains expressly UNKNOWN via `PASSED_TO_Q0_NOT_FULL_INTERNAL_GATE_VECTOR`; no gate is reevaluated or invented. Copied E4-release witness contains integer timestamps and remains JSON-safe. No sizing or admission functional change appears in this delta.

The whole-advance clock fixture runs real daily advance, domain batching, queued executor and native callbacks with only unrelated tier admission fixed. It confirms both originally authorized levels are batched before fills, each attempts once per D1 under both partial-CANCELED and fully-FILLED receipts, no additional intraday retry occurs, and unused rights retry on next D1. This supports preserving the original level-attempt schedule; it does not identify the exact archived denied UUID level or prove historical equivalence.

Reviewer independently ran the final immutable SC01/risk/precision suite: **42 PASS** (matching owner frozen log). **SC03 and SC04 SOURCE GO** on this reviewed source, subject to root per-recipe immutable pins/preflight and root historical-engine authorization. No further source changes requested. Implementation source correctness is separate from activation, coupled portfolio economic benefit, matched-control acceptance, terminal accounting and repeat evidence. Reviewer has started no full historical engine.
