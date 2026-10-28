# Frozen candidate qualification

Candidate BTC_POSTCUT_D1 / sourcefccd60c01e8cae5e8258748b046f43f88a16bb79. No further parameter search. Two remaining conditional attempts out of8; all failures count, no auto-repeat.

## QUAL_STRESS

Only after independent benchmark financial PASS, source/input/config preflight and root GO. Same benchmark, seed10000/res0, BASE fees, native1.231 and all candidate flags. Add ONLY --qualification-stress: stock FillModel(prob_fill_on_limit=1.0,prob_slippage=1.0,random_seed=0). This applies one adverse native tick to every L1 fill, including maker/limit, and may slip past limit; diagnostic stress, not historical exchange fill guarantee. No latency/liquidity-consumption change. Frozen config SHA 5a1aab4a8e0c75711869fd886aa80c08052874f38e3d107f6d2bea925ac62883. Technical gates: actual child0, complete observer coverage/cash+lifecycle reconciliation, no modeled liquidation, terminal native flat/orders0. Capital-risk gates BOTH settled+event DD<=51.80315157406654834417870238%. Stress profit/retention reported separately as diagnostic; reference profit-floor decision remains frozen benchmark. Failure blocks clean qualification claim and requires explicit disposition; no tuning/retry.

## QUAL_VALIDATION

One clean-start seed10000/res0 run on [2026-09-01,2026-10-28) UTC (57days), warmup[2024-09-01,2026-09-01), independently accepted newdata. No benchmark positions/capital carried over. Source changes limited to optional interval+exact newdata hash pin, keeping all economic files/defaults unchanged; source review/freeze/exact hash/config preflight before rootGO. Archived control provenance remains immutable and is labelled UNMATCHED_INTERVAL_AND_DATA, never a matchedperformance comparator. No optimizer/parameter changes after outcome. Require native financial/coverage/flat/liquidation gates as above; report return, both DD and selected actions honestly. DD cap applied as qualification risk flag; profit expectation for57days is not the2year absolute floor. Seen data/access declared; not untouched OOS claim.

No services/deployment/realorders/transfers/START LIVE are authorized by these qualifier runners.
