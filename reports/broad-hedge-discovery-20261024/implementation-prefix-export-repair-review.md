# Prefix export boundary repair review

Task CM-NATIVE-PAIRED-PREFIX-20261024. Narrow read-only export/calendar review, separate from observer funding review. **Status: CALENDAR/EXPORT_AND_INERT_BUDGET_GUARD_REVIEW_PASS at `3323f08c57ede411058f93d96acee88928c93481`; outstanding P0/P1 in this narrow delta:0. Original physical2/4 is FAILED and consumed; no valid matched control or final ROI is created by this analysis.** No reviewer native/test engine launch, product write or budget/ledger change.

Reviewed committed output path at `6f7cd9881b928dcd8b905d63d3ab7892f9e6b733`, including monthly generation/checkpoints, every assert_report_boundaries guard, direct terminal reconciliation, fee attribution, raw-before-validation and later final packaging. Actual saved raw: root-project `runtime/var/research-jobs/b2-f0-paired-prefix-20261024/MATCHED_OFF_CONTROL_CORRECTION1/result/paired-prefix-OFF-raw-native.json`, independently verified SHA256 `44e1257c22972f50c9158d150ae0b4df100ad87520432039e1e6deefc4c2afa3`.

## Exact root cause and strict repair contract

The guard does not literally require24 rows. It calculates max(1,month-number(end)−month-number(start)), obtaining4 for Sep1→Jan15. Monthly export correctly includes five intersecting calendar months:2024-09,2024-10,2024-11,2024-12,2025-01. The formula omits the partially included end month. Full Sep1→Sep1 still correctly expects24 under the old formula.

Derive expected ordered UTC month labels whose month intervals intersect [start,end). An end exactly on a month boundary excludes that ending month; a partial ending month is included. Validate exact ordered unique labels against that expected sequence, not merely count or len(actual). Preserve the full default24-month calendar and existing authorized early-liquidation semantics; retain monthly terminal equality,80-digit compounding check and1e-24 tolerance, interval drawdown bounds, native fill boundary convention/count and all fee/funding/accounting checks unchanged. A strict explicit frozen-prefix mode is acceptable if general/default behavior remains unchanged. Negative tests should reject missing/duplicate/reordered/extra months and incorrect declared calendar, plus preserve full24 behavior. One engine-free actual-raw validator receipt should show the correction passes calendar and existing checks without modifying raw amounts or labels.

No other full-calendar assumption was found in this applicable output path. `_reporting_checkpoints` lists future month boundaries but does not itself assert the final partial-month count; interval cash/monthly output remains authoritative. The packaging path after the failing guard must still complete normally on a newly authorized run; this analysis cannot manufacture omitted final fields.

## Independently checked raw evidence

- Declared interval exactly[2024-09-01T00:00Z,2025-01-15T00:00Z), seed10000; actual ordered five month labels above.
- Last monthly total equals interval cash terminal19544.07357286.80-digit monthly compounding residual9.600103476507640992433286976813471282645031045698953e-28, below unchanged1e-24 tolerance.
- Drawdown start2024-12-21T16:00Z and trough2024-12-30T08:00Z lie inside interval. All82 native fill timestamps are within[start,end];0 at boundary, exactly matching settlement count0 and original settlement convention.
- Native raw terminal positions0; native_strategy_events.terminal_open_orders0; lifecycle FLAT with TERMINAL_BOUNDARY_SETTLEMENT. ACTIVE19544.07357286, RESERVE0; direct observer terminal cash matches. These are failed-attempt raw facts, not an accepted final control result.
- Native fees1135.02982656 equal exact native attribution;56 maker/26 taker fills, unknown0.133 funding cash-delta rows sum exactly−633.29250058, equal reported signed native funding. Fill count/fill_audit length both82; native rejections0; streaming195840 processed/195840 expected source minutes.
- OFF paired owner has no events/failures/open owner. Raw marker is NATIVE_COMPLETE_PACKAGING_NOT_VALIDATED. The raw lacks minute_risk_observations, split_cover_audit, btc_sizing_audit and physical_prefix_attempt because the guard failed before those packaging steps; none were fabricated here.
- Observer status UNKNOWN remains a separate qualification blocker. This task does not duplicate its causal-snapshot audit or promote the raw headline to a passing matched control.

Both original failed attempts and their exact raw/log/freeze evidence must remain preserved. The exact final correction and its engine-free actual-raw validation receipt are reviewed below; no new physical run is authorized by this report.

## Final correction delta and receipt

Read only the committed calendar/export and launcher budget-guard delta `6f7cd9881b928dcd8b905d63d3ab7892f9e6b733`→`3323f08c57ede411058f93d96acee88928c93481`, plus their focused tests. Observer changes are owned by the separate observer-funding reviewer and are not covered by this PASS.

`_interval_month_labels` enumerates UTC month starts before end_exclusive, beginning with start's month; therefore the approved partial prefix has exactly five labels and the original full interval remains24. Exact ordered labels are now required, including a leading contiguous subset for the pre-existing authoritative early-liquidation exception. Monthly output values, native terminal checks,80-digit compounding/1e-24 tolerance, drawdown times and native fill/settlement assertions are untouched. No change to trading, order, funding calculation or native accounting is part of this calendar fix.

The focused actual-raw test explicitly pins SHA44e1257c… and NATIVE_COMPLETE_PACKAGING_NOT_VALIDATED; it calls the repaired validator without changing the dictionary/file, still asserts the saved observer UNKNOWN, and never promotes the failed run. Negative cases reject omitted partial month, reordered/duplicate labels, cash mismatch, return mismatch and out-of-interval fill. Full24 precision, native equal-timestamp insertion order and authoritative early-liquidation tests are present and passed in the connected receipt.

The budget code is inert at the current authorized cap4: effective cap is min(freeze cap,ledger cap), both strictly integer4/5; fifth logical slot is refused while either cap remains4. Cap5 additionally requires a separately hash-pinned APPROVED_BY_OWNER amendment containing protocol hash/full0/max5 and nonempty exact owner response; fifth slot is OFF-only with explicit non-trading repair reason, an authorized ledger slot, original rootGO/review gates and no logical reuse. Synthetic tests verify missing/wrong-hash amendment refusal, both cap4 paths, preserved two failures, matched corrected OFF then B2/combined and physical ceiling5. Source support for a possible amendment is not owner authorization: current live cap4/spent2 remains unchanged, and no new run/budget change was made by reviewer.

Actual Mac XML/log independently inspected: runtime/var/research-jobs/b2-f0-paired-prefix-20261024/nontrading-repair-3323f08.xml and .log;105 tests,0 errors,0 failures,0 skipped (XML time3.054s). The actual-raw validator and negative cases were not skipped. Reviewer did not execute tests/engines. Original failed raw hash and missing final fields remain as recorded; economic qualification and observer acceptance are separate gates.
