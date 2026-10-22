# M2 independent economic validation — FAIL targets

Completed sealed native output: 44/44 validation checks and9/9fee-bucket checks PASS. One native-receipt saved-output stream46.13seconds/nice19/29,564KiB; zero additional native runs, S0rescan, replay or source changes.

Final native flat cash/TOTAL **2044863.63091774**; net-profit retention **33.5392725198%**, below90% (TOTALfloor5,470,396.514987347). Agreed receiptDD independently **70.64462755333227667738160314%**, above50%. Final boundary cash endpoint DD **54.28425210409471313191101312%** also above50%; overall DD remains70.6446275533322767%. Cash account tail/raw/wrapper/ACTIVE+RESERVE match; terminal positions0/lifecycleFLAT, final orders allterminal, zero liquidations.

610native fills reconcile fee counts, commissions and notionals withnative CSV: maker134 /88,299.41622348fees /441,497,081.1174notional; taker476 /526,061.33397601fees /956,475,152.6831notional; unknown0. Native fee total614,360.75019949, already included in cash.

25actual management fills, BTC19/SOL6, allTAKER MARKET/IOC/reduce-only; exactly one CLAIM/SUBMIT/FILL/TERMINAL per native cycle.22orders fullyfilled;3SOL partialfills thenCANCELED, no retries/openorders.

|Partial SOL action UTC|Submitted|Filled|Canceled remainder|
|---|---:|---:|---:|
|2025-01-13T11:51:00+00:00|3000.0|1000.0|2000.0|
|2025-08-13T03:03:00+00:00|4500.0|1000.0|3500.0|
|2025-09-18T01:48:00+00:00|9750.0|1000.0|8750.0|

Worst saved settled periods:

|Rank|Peak receipt UTC|Trough receipt UTC|DD%|
|---|---|---|---:|
|1|2024-09-14T00:20:00+00:00|2024-10-03T15:45:00+00:00|70.64462755333227667738160314|
|2|2026-07-06T13:40:00+00:00|2026-08-11T12:15:00+00:00|58.70617109061845512560555843|
|3|2025-04-11T01:01:00+00:00|2025-06-06T15:18:00+00:00|53.65302200763441432691041146|

The strongest failure is the original early SOL risk remaining unmanaged inM2. No claim targets SOL1. BTC6 short is reduced at2024-10-03 01:47UTC. At the worst receipt2024-10-03 15:45UTC, saved cash9176.88870416 andW3941.45025416; native BTCshort0.173 has native OHLC PnL bounds+113.70425..+126.64465, whileSOLlong773.5 bounds−5360.355..−4927.195. This directly shows the adverse SOL book and positive BTC remainder after actual native actions, without allocating realized losses or inventing a counterfactual.

All25M2cycles match original S0asset/first-entry timestamps.11were originally profitable intervals: BTC6/19 (IDs26,67,71,72,73,74), SOL5/6 (IDs3,6,16,22,25). These diagnostic labels are not profit-foregone estimates; capital, quantities and future triggers change under the full policy.

The full-policy native comparison measures TOTAL difference-4032243.60795709 and native-fee difference-331566.98741876 relative toS0. Lower fees do not repair either target. Because signed funding and per-asset realizedPnL areUNKNOWN, TOTAL+fee differences are not labeled pure trading PnL.

24-month same-calendar marked capital/return/DD/exposure and actual UTC fill-month fees/actions are retained inCSV/JSON, includingM1/S0capital comparators. Receipt calendar uses source_quote UTC; final boundary fill costs are separate and never folded intoAugust interval return.

Saved conditional prior-favorable-to-later-adverse OHLC bound **71.68026665310037080829601308%** is a conditional estimate; actual tick DD remainsUNKNOWN, no intrabar extrema ordering assumed. All13inputs and frozen source/input/launcher/command/config identities match;5native economic output hashes match sealed resultmanifest. Full1,051,200processed rows perBTC/SOL source,1,051,199settled receipts+seed,24months, unavailable0 and no coverage/monotonic discrepancy.

Native per-asset facts; realized asset PnL remainsUNKNOWN_NATIVE_ACCOUNT_REPORT_ONLY:

|Asset|Native fills|Native fees|Native notional|Management fills|Management fees|
|---|---:|---:|---:|---:|---:|
|BTC|429|597630.86232644|1367554255.8495|19|54079.46268490|
|SOL|181|16729.88787305|30417977.951|6|554.580125|

The two frozen evaluated intensities both fail the agreed DD and retention targets. These are complete diagnostic native runs, not proof of OOS/live performance. Root stopped at2/4runs; no further model, threshold, recipe or policy change was proposed or executed. Source/data/allnative results were retained.

Exposure context for the shortlist, using whole UTC calendar months touching each peak→trough (includes samples outside precise excursion endpoints; no extra scan):

|DD rank|Whole months|BTC-only samples|SOL-only|BTC+SOL|Flat|Mean gross notional/W|Max|
|---|---|---:|---:|---:|---:|---:|---:|
|1|2024-09..2024-10|35476|1440|2880|48043|2.413x|28.776x|
|2|2026-07..2026-08|62753|6740|1900|17887|3.022x|8.419x|
|3|2025-04..2025-06|42320|34913|25516|28291|2.611x|9.952x|
