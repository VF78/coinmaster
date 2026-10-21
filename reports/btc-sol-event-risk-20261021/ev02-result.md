# EV-02 result: BTC support PASS, SOL support FAIL

Frozen contract SHA256 `349b7eee60dac275a481187e747a932b1b50bf62bb23018ac3dad891c949ff49`. No model fits, engines or U payload inspection. This is event-risk feasibility, not economic action value.

| Branch/partition | Events | Valid labels | Parents | Connected blocks | Pure positive / negative / mixed | Gate |
|---|---:|---:|---:|---:|---:|---|
| BTC TRAIN | 79 | 50 | 18 | 15 | 2 / 8 / 5 | PASS disjoint 5+/5−, total≥10 |
| BTC CHECK | 143 | 80 | 25 | 21 | 3 / 10 / 8 | PASS disjoint 3+/3−, total≥6 |
| SOL TRAIN | 13 | 5 | 5 | 4 | 2 / 1 / 1 | FAIL |
| SOL CHECK | 13 | 6 | 6 | 6 | 0 / 6 / 0 | FAIL |

All 248 candidate events remain saved; 141 have complete eligible labels. Global cross-asset parent/overlap union yields 37 components. BTC has 14/50 TRAIN and 27/80 CHECK positive event labels. SOL has 3/5 TRAIN and 0/6 CHECK positive event labels. Event counts are not IID sample counts.

BTC excludes 29 TRAIN / 63 CHECK events for other same-boundary/unsettled fills. SOL excludes 8 / 7 for that reason. Conservative full-parent split purge additionally flags 3 BTC+1 SOL TRAIN events; full72h partition purge flags 2 BTC TRAIN events. These reasons overlap, so do not add them as distinct exclusions. No stale-over2min receipt was found. Unknown ordinary BTC reachability remains explicitly missing; support PASS concerns the risk opportunity task, not proven implementable intervention count.

Own-fill correction: first implementation conservatively rejected an event’s own native fill at submission time. Final predicate uses native client_order_id from observed submission and admits its consequent fill, without selecting for eventual fills/status. Other simultaneous or unsettled fills remain excluded. Fixtures cover own fill, no fill, other fill, and strict clock. Initial artifacts are preserved in `ev02-initial/`; `ev02-own-fill-diagnostic.json` records the diagnosis, and `ev02-correction-verification.json` proves all 222 BTC event feature/label values unchanged. Including corrected SOL windows merges one BTC TRAIN dependence component, changing its block count16→15 without changing its labels or PASS.

Execution: final corrected one-pass verification read 840,958 native T/V receipts in 12.24 seconds at peak RSS27,406,336 bytes. Three immutable native input hashes rechecked; native order-ID fill linkage verified against the audit timestamp/instrument multiset. Compilation and causal/purge/component/disjoint fixtures PASS. One duplicate unmodified diagnostic pass occurred during correction setup after a patch syntax preflight failure; it repeated the frozen calculation, introduced no alternative configuration or outcome search, and consumed no native economic slot. Final dataset reflects the single approved correction.

Artifacts: `ev02-events.py`, `.log`, `.csv`, `.json`; `ev02-connected-blocks.json`; `ev02-sufficiency.json`; correction receipts. Exact input/output SHA values are in sufficiency JSON. SOL stops before methods/economic runs under frozen support minima. BTC is eligible only for separately authorized fixed method comparison. Four economic slots remain unused. No future model trained on TRAIN may be applied retrospectively to early TRAIN in an economic claim.
