# ALPHA-CORRIDOR-v1 R1 contract — PREPARE ONLY

Canonical branch codex/nautilus-btc-sol-mvp, inspected HEAD 5b45a7c. Owner task §§2–8 governs. No source edit, test engine, economic engine or commit performed. R1 implementation waits for root GO after R0; R2 requires separate owner permission.

## Narrow architecture

Add exclusive default-OFF `alpha-corridor-v1` to the existing `research_sol_risk_first` selector. Implement small methods in risk_first_sol.py; dispatch through existing conditional_hedge.py netting owner and native executor. Minimal validation/CLI/report/observer hooks in wave_overlay.py, native_baseline.py and minute_risk.py. No new mixin, optimizer, SDK, executor, accounting ledger, independent alpha/hedge position or BTC strategy. Keep older research variants intact.

Use native current signed B and held SOL, pending owned leaves, current legal original_target/tasks and domain remaining earned rights. Never use theoretical full H ladder as alpha target. Preserve split q0/q1/P0/PLANREF/Q2/TP-IOC policy, normal mandatory exits and lot/minimum/margin/tier/price constraints. Changed equity may change dollar Q. Never delay regime/trail/DP/terminal/liquidation exits for corridor recovery.

## Scenario and projection

Use 91 causal available paired Daily closes/90 log returns, refreshing beta/a/u together only after a new closed Daily pair, including BTC-flat/SOL-only. Risk beta is Cov(SOL,BTC)/Var(BTC), finite positive and distinct from original alpha-beta. a=expm1(q95(abs(BTC))), u=expm1(q95(abs(SOL-beta*BTC))). Reject invalid/nonfinite/nonpositive prices, missing dates, zero variance or invalid beta as DATA_UNKNOWN.

E/H policy observations use completed post-SOL-quote native account cash plus native unrealized PnL at fresh causal marks only; prequote and post-BTC phases remain reporting observations, not policy peak updates. The all-phase native DD remains the separate selection metric. E is retain checkpoint timestamp and last observed global H=max(10000,prior H,E). Never sample account cash in an in-progress fill callback, add realized PnL separately, clamp negative C, or reset H at flat/new episode. C=E-.55H. A fresh process starts seed H; any restart/resumption must restore H from its prior durable audit/checkpoint or be DATA_UNKNOWN rather than silently reseed. R2 fresh engine does not resume a trading episode.

L(s)=a*abs(B+beta*s)+u*abs(s)+K(s). K includes future held-to-target transaction costs, exit costs on remaining native inventory, unfilled owned opening leaves and existing execution assumption. Already posted fees/funding remain solely in E. Future signed funding and real L2 remain UNKNOWN; selected native proxy must be explicit. Reserve accepted BTC Q2 through unchanged `_split_cover_margin_reserve` and tier/margin gate; include its remaining execution cost conservatively, do not count it as filled B.

On the lawful SOL side, derive the convex piecewise-linear feasible interval using breakpoints s=0, s=-B/beta, s=held (cost absolute value), side bounds and affordable execution limits; solve segment boundaries analytically, select nearest legal s_alpha, round adjacent native lots and re-evaluate full L and native minima/margin. B=0 remains the same problem. Do not cap alpha at 100% factor coverage. Pending low/high endpoints must be checked; cancellation/UNKNOWN_ACK prevents duplicate changes or a claim of current satisfaction.

Distinguish DATA_UNKNOWN (state/marks/estimate/ACK unknowable), SOL_RISK_INFEASIBLE (known mathematical feasible set empty), SOL_MARGIN_INSUFFICIENT (mathematical target exists but venue/Q2 constraints prevent execution). For known infeasibility choose minimum L over actually lawful executable SOL quantities, keep explicit failure, preserve BTC and mandatory exits; never label best effort compliant. Native denial is a known execution failure, not an unknown ACK.

## Lifecycle

Keep healthy held/alpha untouched; do not trade on small boundary drift while held and fresh legal alpha fit. If held/pending or new alpha violates C, cancel conflicting known leaves, wait for true terminal/late fill ownership, then reconcile nearest lawful target on a fresh native quote without candle delay. Review on completed account checkpoint, fills/terminal resolved by that checkpoint, Daily update and new lawful alpha permission. Fill callbacks mark dirty only.

Remove additional protection only after a new opposite closed SOL15m after its increase and fresh receipt, with proposed L<=.8C. Restore trimmed alpha only on a new lawful live original permission/signal with L<=.8C. Retire only bound unfilled physical-attempt rights at terminal; consume/retired rights and old canceled IOC never become recurring target debt. Native original held exits keep fill/right history until actual reduction; ownership transfer is quantity credit only. BTC-flat removes pure protection while keeping actual lawful alpha under B=0 budget.

## Native accounting callback constraint

Observed_strategy_type captures post-BTC/SOL quote AFTER base.on_quote_tick; `_conditional_check` runs inside base before that post-accounting capture. Existing recorder calls `_risk_first_observe_equity` for dd-cov only. Corridor needs its own enabled observer branch restricted to finalized post-SOL checkpoints, storing completed E/H and dirty state. The native focused fixture must establish when cache account is final relative to post-quote capture; reconcile only after a completed checkpoint using fresh executable quotes. Do not take E directly from on_order_filled. Required exits bypass DATA_UNKNOWN. No requirement for identical mark nanoseconds; causal age is required.

## Durable audit before packaging

Existing native runner writes fills/orders CSV before result assembly, but `assert_report_boundaries` and wrapper control metadata can fail before final raw JSON; carry/risk counters then disappear. Add a small atomic raw-native snapshot (result plus native strategy events/counters, fill/order artifact identities and recorder outcome) before boundary/packaging validation and a final atomic complete snapshot before wrapper metadata injection. Keep raw identity distinct from packaged metadata. Use temporary file plus replace, flush/fsync where applicable. Preserve available snapshot on validation failure; do not mislabel an incomplete snapshot complete. No reporting redesign. Exact earliest snapshot site must cover assertions inside run_native_diagnostic as well as wrapper after return.

## Gates

R0 screen may reject this design before source implementation. Before R1 completion: focused connected native tests, narrow independent native money/order review if root requests it, exact source/config/data/policy freeze, source parity evidence. No ROI/DD claim at this stage. No R2 launch, repeat or control engine under this contract.

## Root refinements received before implementation

R0 trace lacks absent-asset marks, fresh prospective alpha/rights, and definitive margin availability; R0 is an observed-held mathematical screen only. R1 must use authoritative native cache/rights, never fill those fields by inference. Remaining-close cost uses actual pinned taker fee .00055 conservatively and explicit existing execution assumptions. Native free margin alone is not execution proof. Old ALPHA-CUSHION actually failed (reported DD at least93.23%, TOTAL lost/OOM); owner document wording that it is unrun is stale. It must not be repeated or enabled under this candidate.
