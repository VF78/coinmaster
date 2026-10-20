# R2 failure acceptance — incomplete native OOM

**Full24-month economic acceptance is not possible. Candidate TOTAL/ROI/DD/fees/turnover/fills/liquidations/BTC acceptance are UNKNOWN, not zero. DD<=50% is NOT_PROVEN.**

The sole economic invocation a40a9cbb20d2475e9d1583b15aa0f804 was OOM-killed at2026-10-20 11:48:54UTC. The journal records20min43.094s CPU,648.5M peak memory and0B swap under681574400-byte limit. Later transient-unit Resultsuccess/ExecMainStatus0 is not completion proof. One startup failure before an economic engine/feed is excluded. No new run was launched.

Final native raw result, fills and orders are absent. Only incomplete gzip and preserved funding DB/WAL/SHM survive. Exact heap allocation is UNKNOWN; static growth-path evidence does not prove an allocation-level cause.

## What can be said numerically

- Existing incremental reader:392240 complete CSV rows and130746 post-SOL quote observations, versus3153600 expected sample rows.
- Last stored sample:2024-11-30 19:07UTC, post-BTC phase. Engine processing beyond that flushed prefix is UNKNOWN.
- Partial gzip:11436420bytes, SHA25651da0e4405e7031960e0668395a78a4dfe902c37bfca8f843bfdd29728b1f052; gzip completeness=false.
- Stored cash/paired equity4869.94269918 is **not terminal TOTAL**, and is no basis for full ROI.
- Provisional stored-series DD77.92330403144688216329131654% is an incomplete, settlement-uncertified warning copied from the existing reader, **not validated full candidate DD**.

## Archived control versus candidate

| Metric | Archived control | Candidate |
|---|---:|---|
| settled TOTAL USDT | 6077107.23887483 | UNKNOWN_NO_COMPLETE_NATIVE_EXPORT |
| full ROI percent | 60671.072388748300 | UNKNOWN_NO_COMPLETE_NATIVE_EXPORT |
| global native allphase DD percent | 66.31878024969152066570091116 | UNKNOWN_NO_COMPLETE_NATIVE_EXPORT |
| conditional OHLC bound percent | 67.54771031869252420136632742 | UNKNOWN_NO_COMPLETE_NATIVE_EXPORT |
| actual native fees USDT | 945927.73761825 | UNKNOWN_NO_COMPLETE_NATIVE_EXPORT |
| actual native turnover USDT | 2209476512.4321 | UNKNOWN_NO_COMPLETE_NATIVE_EXPORT |
| native fill report rows | 621 | UNKNOWN_NO_COMPLETE_NATIVE_EXPORT |
| native liquidation audit count | 0 | UNKNOWN_NO_COMPLETE_NATIVE_EXPORT |
| signed funding | UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA | UNKNOWN_NO_SQLITE_ANALYSIS_OR_FINAL_COMPONENT_EXPORT |
| retained TOTAL share | 100% | UNKNOWN_NO_COMPLETE_NATIVE_EXPORT |
| DD<=50 criterion | ARCHIVED_DD_ABOVE_50_NOT_RECERTIFIED | NOT_PROVEN |

Control TOTAL6,077,107.23887483, native all-phase DD66.3187802497% and conditional OHLC67.5477103187% are reused archival metrics, not recertified settled-account proof.

## Unfulfilled acceptance and blocker

The24-month monthly/exposure statistics,105-BTC calendar/side/acceptedQ/delay acceptance,11 fixed loss-flip **portfolio** comparisons and three worst-excursion comparisons were not completed. Partial data are not substituted for those tables. No sum of fill PnL, inferred liquidation count, assumed zero funding or counterfactual ROI is used.

Funding originals and preserved copies match byte hashes; no SQLite analysis was performed. Preservation alone proves no signed funding amount, database integrity or completeness. Source f2ebdce uses the approved analyzer-off runner SHA98024a; five other R1 pins match the request. The obsolete runner SHA is not enforced.

**Concrete blocker:** OOM interrupted the sole economic run before durable final actual native/lifecycle exports. Full metrics and criterion acceptance remain UNKNOWN/NOT_PROVEN. This task authorizes no engine/control/repeat/restart or source change.

## Verification scope

Owner completion, journal, preparation/launch/coverage receipts, logs and preserved artifacts were verified against the stable failure manifest. Partial gzip compressed bytes were independently hashed once before that manifest; size/mtime and manifest identity are unchanged. No new gzip decode, trace statistics pass, SQLite analysis or monetary reconstruction occurred.

Details and all verified input identities are in r2-analysis-failure.json. Only r2-analysis-failure.md/json and r2-analysis-failure-manifest.json were written by this acceptance step.
