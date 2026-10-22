# H4 baseline holding-time occupancy

Saved native intervals only; half-open `[opening fill, flat fill)`, clipped to `[2024-09-01,2026-09-01)` UTC. 730 days; BTC105/SOL26 intervals. No quantity or PnL calculation.

|State|Days|Share of730days|
|---|---:|---:|
|BTC_OPEN|307.934722|42.182839%|
|BTC_FLAT|422.065278|57.817161%|
|SOL_OPEN|139.866667|19.159817%|
|BTC_OPEN_SOL_OPEN|47.355556|6.487062%|
|BTC_OPEN_SOL_FLAT|260.579167|35.695776%|
|BTC_FLAT_SOL_OPEN|92.511111|12.672755%|
|BOTH_FLAT|329.554167|45.144406%|

BTC_FLAT is an upper bound on baseline clock-time availability for standalone SOL, not signal/admission/executable/profitable opportunity. Some BTC-flat time already has original SOL inventory. BOTH_FLAT is vacant baseline time. This is holding occupancy, unlike the730-day EMA34 direction census; alternative policy changes occupancy.

Root proposed role priority: **BTC open => hedge override; BTC flat => standalone SOL**. This needs explicit transition and NETTING ownership semantics; it is not native approval.

Own SOL TP/SL can reduce or close SOL while BTC remains open, so it conflicts with continuous full-BTC hedge coverage. Replenishing hedge after its own TP overrides the exit and changes turnover/rights. One explicit role must own the physical SOL quantity; no implicit simultaneous full claims.

Source: `reports/winner-6077107-stats/trades-ledger.csv`, SHA `791ec027990e6ad3028ff708afd7a7439b1dbdca8cfd16a666fd17d0bfa29317`. Only asset/start_ns/end_ns used; simultaneous transitions have zero duration. No market/engine/model/source/service actions. Final thin metadata task complete.
