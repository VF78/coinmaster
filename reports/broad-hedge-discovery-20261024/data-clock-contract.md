# Data/clock and local attribution proposal — no outcomes

Status: DATA_AVAILABLE; OBSERVED_FILL_RAW_MARK_ATTRIBUTION can replace missing receipt endpoints for a separately named local descriptive statistic. It cannot repair the old frozen native-equity protection gate or establish native/event-level DD. Root must freeze the interpretation before new labels. No engine, performance screen, source or strategy change was run here.

## Inputs and availability

`data-inspection.json` pins all eight Parquet inputs, three frozen source files, old extraction/feature code and native fills. `data-inspect.py` reads market/feature/clock fields only and emits no new performance labels.

Both assets have execution and mark streams with 1,051,200 rows, exactly 60,000ms apart: open timestamps `[2024-09-01T00:00Z,2026-08-31T23:59Z]`. A row open `u` supplies its completed close at `u+60s`. Thus completed marks exist on `[2024-09-01T00:01Z,2026-09-01T00:00Z]`, inclusive. Execution schema: `open_time_ms:int64; open/high/low/close/volume/turnover:string`. Mark schema: `open_time_ms:int64; open/high/low/close:string`.

Daily files have 1,460 gap-free daily rows, opens `[2022-09-02,2026-08-31]`, 730 days of prebenchmark warmup. Schema is execution schema plus `mark_close:string`. Exact Decimal OHLC aggregation of every overlapping minute day equals daily OHLC for both assets: 730/730 days, all four fields, zero difference. No prebenchmark minute equivalence can be checked because that minute history is absent; same-venue daily source is available, not fabricated H1 history.

Funding schemas: `funding_time_ms:int64; funding_rate:string`. BTC 4,380 rows; SOL 4,740 rows, first `2022-09-02T00:00Z`, last `2026-08-31T16:00Z`; their individual cadence histograms are retained, never assume identical times/8h. Actual BTC signed cash deltas come from persisted `funding_cash` / matching raw-native signed delta audit, not rate×exposure reconstruction. Hypothetical SOL/avoided BTC funding retains prior completed minute mark convention and boundary alternatives; exact historical venue settlement mark remains unproven.

## Native clock evidence

Frozen `native_baseline.py:914–944` sets `available_ns=(open_time_ms+60000)*1e6`; marks use mark close, synthetic quotes use execution close. `native_quote` at lines 902–905 applies frozen spread/price precision. This is completed-minute close execution, not raw minute open execution. `minute_risk.py:124–130` uses the same completed-minute mapping. Its lines 171–199 defer a settled receipt until a later custom event; it rejects intervening fills/account mutations and retains the old source bundle. That observer intentionally does not prove a terminal same-window receipt.

354 saved R3 fills are all exactly minute aligned, all have completed raw mark rows, including one fill at the final `2026-09-01T00:00Z` boundary. First fill is `2024-09-02T00:01Z`. Fills CSV is matched to native audit in the existing screen; fill `ts_last` / native `fill_ns` is execution-event time, not raw row open. A new action based on a feature available at `t` can use the next completed execution close `t+60s`. Using row open `t` close at timestamp `t` is lookahead.

## Settlement-equivalent observed-fill attribution

For actual signed fill increments `dq_j`, prices `p_j`, native commissions `fee_j`, and actual persisted signed funding `F_j`, form:

`q(t)=sum(dq_j, fill_ns_j<=t)`

`C*(t)=seed + sum(-dq_j*p_j-fee_j, fill_ns_j<=t) + sum(F_j, funding_ns_j<=t)`

`W_raw(t)=C*(t)+q(t)*raw_completed_BTC_mark(t)`.

`C*` is an algebraic pricecash book; it is NOT the native futures wallet balance while held. This avoids a new average-cost/matching engine. At actual flat `q=0`, marks vanish and `C*` equals seed plus observed realized fill net plus actual funding, subject to preserved native rounding tolerance. Existing R3 actual-cash reconciliation, not a new screen, already checks this full terminal identity and cycle additivity. Actual reserve is zero; transfers or nonzero reserve would require a separate observed ledger and otherwise block reconciliation. Raw vs native rounded mark differences stay explicit; do not force them to zero or assign them to funding.

Local baseline change uses `W_raw(t)-W_raw(e_pre_action)`, where `e=t_decision+60s`, anchor includes all actual baseline flows timestamped `e`, and the hypothetical action enters afterward. Snapshot both sides of the hypothetical action fee. Normalize by observed entry BTC notional (or the single predeclared denominator), not candidate equity. It is a local loss/change diagnostic; it is not percentage global native DD, executable portfolio return or compounded candidate TOTAL.

Use every completed-minute boundary plus pre/post observed timestamp-group flows. Native BTC adds remain actual baseline flows but never grow the diagnostic action. Reductions shrink the action pro rata only, no re-add. Distinct same-time fills are retained in native audit order when available; without proven intra-timestamp order, do not call grouped boundaries coherent native event DD. Include pre-fill/pre-action peaks for this sampled attribution, with the stated grid and unknown intraminute path.

## Terminal rule and action execution choices

Recommended descriptive window: `end=min(e+24h, first actual BTC flat after e)`; reject if no observed BTC inventory at entry or if flat occurs before action entry. Use the actual fill group that reaches flat, including native exit fees and actual funding through that terminal timestamp. If ending flat, baseline terminal needs no price; hypothetical SOL close still needs raw completed execution close at that exact timestamp, which exists. If ending 24h while BTC held, use the same raw completed mark for the baseline terminal and close SOL / restore only the remaining diagnostic trim at that endpoint. Do not use next-cycle entry or a delayed receipt as terminal. Full terminal reconciliation includes native boundary fills; interval-exclusive attribution must identify their inclusion separately.

There are two distinct execution interpretations. Freeze one; do not switch after outcomes:

1. **Synchronous descriptive paired attribution (recommended for cheap triage):** observed BTC reductions at native timestamp `r` reduce the diagnostic SOL/trim at raw execution close `r`, under an explicit ideal synchronous pairing assumption. Trim comparator credits exactly its removed share of actual native exit pricecash/commission; a surviving 24h restoration pays its frozen hypothetical execution cost. This does not claim the BTC fill was knowable before `r` or that a reactive hedge could fill at `r`. Strict flat endpoint is algebraically available, but implementable paired 3TP/partial/late-fill behavior remains UNKNOWN.
2. **Retimed reactive hypothesis:** reductions observed at `r` may execute only at `r+60s` raw execution close, clearly labeled hypothetical retiming. If `r` is actual flat, this leaves exposure after BTC flat, violates strict no-SOL-while-BTC-flat, and cannot pass that contract. Final raw-data boundary has no `r+60s` row. Do not silently keep synchronous close on flat and claim full causal execution; reject/UNKNOWN unless root separately freezes a pre-submitted paired execution mechanism. A conservative availability clock alone does not solve this conflict.

Thus the data endpoint blocker is resolved for option 1's specifically named descriptive attribution. `UNKNOWN_DATA_CLOCK_TERMINAL_ENDPOINT` remains the correct status for the old native-equity gate. Causal hedge execution and full event DD stay UNKNOWN under both options until independently demonstrated.

Funding ties: baseline uses observed persisted signed deltas; at a timestamp shared by entry/reduction/flat, hypothetical funding exposure has two fixed alternatives, FUNDING_BEFORE_ACTION and FUNDING_AFTER_ACTION. Both branches must satisfy any cheap gate. Enumerate BTC/SOL calendars separately; no rate replacement with zero, no sorting by favorable money effect. Include terminal boundary funding explicitly and retain tie counts.

## Early-September separate D1 family

H1 lag720 cannot be repaired using daily values; the saved H1 market begins September 1 and its first four actual cycles lack that history. Preserve that cohort limitation. A separate `D1cov30_lag1D` family can use existing daily closes causally, including those four cycles:

At decision `t`, choose latest paired daily close `c<=t-1D`; estimate simple-return covariance/beta from exactly 30 daily returns ending at `c` (31 paired closes). Use sample covariance/variance with `ddof=1`; positive finite BTC variance required, no clipping/calibration here. Its earliest possible decision is `2022-10-04T00:00Z`, before the benchmark. Every state in the benchmark therefore has source history. For a daily 1D residual use its separately declared latest completed daily return at or before decision; do not label it rolling H1 24h. H4 adverse filters may still be separately completed-minute aggregates, with explicit mixed feature roles, not renamed D1 beta as H1 beta.

30 D1 returns and 720 H1 returns have different sampling/horizon; they are distinct frozen hypotheses, not interchangeable estimates or a postresult favorable fallback. No thresholds, family outcomes or hyperparameter search were produced in this data pass.
