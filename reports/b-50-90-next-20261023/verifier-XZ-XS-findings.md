# XZ/XS independent saved-output validation

Both pass38/38core checks: frozen result/raw/config/source/data/policy/input hashes, native CSV fees/fills, zero terminal native positions/orders, complete1051199settled receipts/0missing/0invalid timestamp rows, exact independently recomputed global DD and closed inventory/cycle cashflows. Both have0liquidations. Each trace received one corrected streaming traversal; P0/E4/EP/Z/S caches were not rescanned.

|Recipe|TOTAL|S0 net-profit retention|global settled DD|fees|BTC/SOL fill rows|50/90|
|---|---|---|---|---|---|---|
|XZ|4877453.55144460|80.22692462491052470340223871%|60.29622291086218148072256726%|684757.69258637|327/167|FAIL both|
|XS|5406345.11636863|88.94428438303662495658496376%|58.94743688415397241603930272%|691507.32515017|337/195|FAIL both|

XZ’s global peak/trough/recovery match standalone Z’s early episode: peak14171.0598339Oct3 2024 04:01UTC, trough5626.44600762at15:45, recoveryOct4 16:31. XS’s new global maximum isJan13 2025: peak151829.51287244at00:37→trough62329.90660044at14:37; recoveryJan14 14:42at151942.0804041. XS native peak/trough snapshots containSOLlong4000at187.23and noBTC, as for standaloneS, with a different actual cash base. A BTC+oppositeSOL conditional cut cannot be assumed to protect an interval with noBTCposition. No perasset or hypothetical equity is manufactured from raw mark closes.

XZ has6retained global-peak excursions reaching30%; XS8. All peak/trough/recovery native quantity/average/cash/equity snapshots and6priorA/C/Dboundary pairs are cached; both export24monthly rows. Maximum negative BTCclosed-cycle fill-net streak10for each, SOL1. Cash bridges and all actual asset cycle/fee/net ledgers are descriptive two actual paths, excluding allocated signed funding. Their differences are not sums of standalone module profits or forecasts.

The finite saved native fill-audit addition covers every currently completed recipeP0/E4/EP/Z/S/XZ/XS: verifier-liquidity-costs.csv contains explicit native MAKER/TAKER fill counts, actual notional and commissions byBTC/SOL. It reads native_liquidity_side directly and never infers liquidity from order type. verifier-liquidity-checks.json proves frozen CSVhash, actual rowcount, explicit knownliquidity/currency, totalnotional/commission parity and native perasset count/commission parity for each recipe. These checks are also attached to individual audit JSONs, while38core checks retain their original meaning. No risk trace is read for this addition.

All89source-file and13actual-input pins match sourcebd04c9b3858bcda40060a08eff488849c69af5d8. Sourceowner’s critical ledgers/arm cohorts are not duplicated. No new engine, replay, source edit or pilot action occurred. Awaiting root’s XZS completion/hash-freeze notice.
