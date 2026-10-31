# Saved CM2 anchor analysis

This helper reads completed research artifacts only. It never imports CoinMaster/Nautilus, constructs an engine, applies fills, recomputes PnL, changes cash, or reads accounts/credentials. Runtime77935a39 remains unchanged. Author tests use synthetic equity facts on the VPS; actual Mac financial artifacts must stay on the Mac.

Run after completion:
```
<pinned-python> saved_cm2_analyze.py --manifest <analysis-inputs.json> --out <own-analysis-output>
```

The manifest has:
- `native_dd_source`: absolute frozen779 runtime/coinmaster/research/minute_risk.py path.
- `native_dd_source_sha256`: its actual SHA256, mandatory.
- `ledger`: own CM2 trials.jsonl.
- `cases`: objects with case,run_id,stage=anchors,native_report,settled_receipts,coherent_trace,engine_count,request,go. Every path is explicit and local. Streams are the completed minute-native-settled-receipts.csv.gz and coherent-native-events.jsonl.gz; engine_count is engine-construction-count.json.

A case is read economically only when its own ledger ends COMPLETED and native_report is provided. No unfinished gzip is scanned. Other ledger attempts are automatically listed with null economic values. Missing/failed/unfinished cases receive24 null monthly rows and an explicit UNKNOWN DD placeholder; that placeholder is not a drawdown episode. Analysis errors preserve physical ledger status and show financialUNKNOWN.

Per case: SUMMARY.json, MONTHLY_24.csv, ALL_DD_GE20.csv and NATIVE_EVENT_CLOCK_ORPHANS.csv. Overall: COMPARISON.json and COMPARISON_PARETO.csv. Full native raw positions are never exported into a giant derived JSON.

Drawdown uses the exact frozen native DrawdownTracker class extracted by AST without module imports, Decimal precision28/ROUND_HALF_EVEN. Recording all excursions≥20% reuses its own retention formula; native peak ties, trough ties, recovery and ongoing excursions are preserved. One streaming pass pairs every coherent SETTLED watermark with the independent settled CSV: source/receipt/cash/equity must match exactly. Reconstructed interval summaries must equal native saved summaries. Source hashes and compressed raw stream hashes are retained. On cache miss streams are parsed once while hashed; on cache hit only compressed hashes are read/verified. Changed supposedly immutable streams are rejected.

Raw interval DD is retained unchanged. A second separately named DD basis appends the actual persisted DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED flat cash point to each continuous native-equity curve. This includes final-close costs; no favorable terminal fee exclusion, estimated adjustment or fresh engine is used. The numeric goal uses this stricter basis: TOTAL≥5.6m, both DD≤45%, known modeledliquidations0. It remains separate from structural/robustness acceptance.

All24 marked monthly endpoints are actual settled source=UTC next-month boundary−1minute, received at the boundary. Cash at that source, native account monthly cash total/return and marked settled equity/derived return are separate columns. Terminal settlement is excluded from these monthly interval endpoints and included only in the explicit final-close point/DD. September/October2024 and calendar endpoints2024-12,2025-12,2026-08 are retained for matched own-path early capital comparisons. Nonpositive prior equity produces a null ratio/reason.

Fees/turnover use actual native fill audit; funding retains native signed postings; realized BTC/SOL values come only from complete native closed-position lifecycles and already include fees. No fee is subtracted again. Raw native TOTAL and cashbridge remain authorities.

Positions/events can prove sign/co-exposure samples, actual zero-to-nonzero SOL openings with opposite BTC and native event-clock orphan transitions. A zero-clock interval can still span multiple native sequence events and is not an atomic-fill or real venue-latency claim. Adapter orphan intervals are separately labeled next-quote observation upper bounds, never actual exposure duration. Parent/order/race lineage and beta/tail causal benefit missing from exports remain null/UNKNOWN. A SOL increase while BTCflat is a conflict for investigation, not automatically independent alpha: late-fill/drain context may be missing. No complete structuralPASS, VALID_IMPLEMENTATION or winner is asserted.

FinancialPASS requires completed physical evidence, one real engine, existing financial gates/bridges/fees, curve parity and terminal flatness. Financial, structural, numeric goal, robustnessNOT_RUN, persistenceNOT_IMPLEMENTED and MODEL_LIMITED statuses remain separate. Pareto uses financial-qualified native figures only within exact common source/data/fee/interval/seed groups; duplicate raw reports are not independent controls. A00 is only the stated historical reference, never rerun or blended into the matched controls.

Tests:
```
<pinned-python> -m pytest test_saved_cm2_analyze.py -q
```
They exercise fixed saved-equity ties/recovery/ongoing/terminal charges against the native class, two-export parity/disagreement, null failures, signed funding/no fee double count, and matched/duplicate Pareto handling. No engine or actual Mac financial input is used.

Recovery exception: an original physicalFAILED run can be analyzed financially only with derived_receipt pointing to strict QUALIFICATION.json and qualifier_source pointing to its reviewed source. Supply ORIGINAL raw-native JSON/legacy CSV plus original request/GO/engine count. All raw/derived/source/metadata hashes and unchanged original ledger prefix are verified before switching to derived complete inputs. The physicalFAILED record is retained in SUMMARY/COMPARISON. A bare edited PASS flag or sparse CSV is never accepted.
