# CHOP_PAIR_50_NET_v1 comparison

**REJECTED: DD goal fails.** Same real Bybit1m period [2024-09-01,2026-09-01), seed10000USDT/reserve0; no pilot changes.

| Metric | Reused control | Candidate |
|---|---:|---:|
| TOTAL | 6,077,107.24 | 205.42 |
| ACTIVE | 6,077,107.24 | 205.42 |
| RESERVE | 0.00 | 0.00 |
| ROI_percent | 60,671.07 | -97.95 |
| DD_minute | 66.32 | 99.85 |
| DD_OHLC | 67.55 | 99.85 |
| fees | 945,927.74 | 11,256.90 |
| fills | 621.00 | 186.00 |
| funding_records | 1,320.00 | 489.00 |
| liquidations | 0.00 | UNKNOWN_AUDIT_LOST |
| MAKER_fees | 153,876.77 | 1,065.72 |
| MAKER_notional | 769,383,840.63 | 5,328,603.11 |
| TAKER_fees | 792,050.97 | 10,191.18 |
| TAKER_notional | 1,440,092,671.80 | 18,529,422.75 |

TOTAL delta: **-6076901.81641607 USDT**. 98 focused native tests, independent3 targeted tests/GO, one full event-processing engine. Full contiguous1051200minutes/3153600native samples verified; both positions flat and all217orders terminal. Fees are native, maker0.020%/taker0.055%; exported avg_px limits turnover precision.

At 2025-04-06 20:37 UTC the remaining exposure was only LONG7000SOL, basis121.88428571428571/mark105.62: native cash114392.09795879, native unrealized−113850, equity542.09795879. Seven real reduce-only taker SELL fills at105.63 closed1000SOL each; fees406.6755. At20:38UTC cash/equity205.42245876 became permanently flat. This proves unpaired SOL exposure, not that carry was ACTIVE then.

**Audit limitation:** the outer runner rejected an extra disabled-default report field, research_conditional_sol=false, after native exports. Durable numeric evidence is retained; the original full in-memory report and carry/liquidation/domain counters are lost and remain UNKNOWN. A separate tier-policy liquidation/lockout is consistent with the last close; exact event count/gate state is not proven. Signed funding is UNKNOWN for both cases; it is not zero.

Historical source drift is enumerated in engine-review-ready.json; no fresh full control was run. Exact causal attribution to carry alone is not asserted. No second economic run was used to recreate missing metadata. The candidate cannot qualify for DD≤50% regardless of those missing counters.

For any future separately authorized reproduction: account for the disabled metadata default and persist raw result before a guard can reject export. This run is not repeated.

[Native report](engine-final-report.md) · [JSON](comparison.json) · [CSV](comparison.csv) · [Manifest](engine-final-manifest.json)
