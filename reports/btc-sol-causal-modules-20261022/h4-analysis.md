# H4 preliminary direction census

**Independent SOL EMA34 agrees with BTC direction on597/730 decision days (81.78%) and69/105 actual S0 BTC entry decisions (65.71%).** Therefore copying the BTC-style direction to SOL does not usually create an opposite hedge. H4 remains design analysis only, without native approval, optimization or PnL.

|Causal completed-daily EMA34 directions|All730 decision days|At105 actual S0 BTC entry decisions|
|---|---:|---:|
|BTC long / SOL long|276|26|
|BTC short / SOL short|321|43|
|BTC long / SOL short|89|27|
|BTC short / SOL long|44|9|
|Same direction|597|69|
|Opposite direction|133|36|

Window: decision availability `[2024-09-01T00:00Z,2026-09-01T00:00Z)`. Each decision uses the previous completed daily close, with730 feature-only warmup days. Frozen exact-S0 pure `batch_features_for` runs with explicit `Candidate(ema_period=34)` for BTC and with SOL substituted as the signal series. Rule: close>EMA long, otherwise short; ties short. All105 parent sides match reconstructed BTC EMA34 exactly. This is a direction census, **not trade count or actual held-position overlap**. SOL beta/wave/admission eligibility was not reconstructed and remains UNKNOWN.

Pins: local mainroot `runtime/var/data/normalized/bybit-BTCUSDT-daily.parquet` SHA `71270c5b9aadad1a2d46003060e04882eaa6a0544802f4c1f025bd7253ea7545`; SOL sibling `897b89d1e93d5b961e769321edf4bb44981384fad280d8e62e8b9fca64431ab4`. Frozen helper SHA `a60a7fe8d242fcc87a028bec69bffd08a67e33ad6738abf92e2ef914159ab5b9`. Dataset is contiguous and paired;730/730 output rows,105/105 actual parent joins. Original S0 TOTAL6,077,107.23887483 is unchanged.

## Sizing definitions are different

For USD BTC notional NB and daily returns rB,rS, an opposite SOL hedge has USD notional NS=k*NB (native quantity NS/SOLmark).

- Volatility matching: `kvol=sigmaB/sigmaS`; equal individual return-vol contributions, ignoring correlation.
- Minimum variance of `rB-k*rS`: `kmin=cov(B,S)/var(S)=rho*sigmaB/sigmaS`.
- Inverse regression beta SOL-on-BTC: `1/beta=var(B)/cov(B,S)=sigmaB/(rho*sigmaS)`.

`kmin/(1/beta)=rho^2`; these agree only at absolute correlation1. The beta regression direction and units must be explicit. A negative/nonfinite coefficient cannot silently become an opposite hedge.

One fixed causal90day daily-log-return summary, including only returns available at each decision (no window grid):

|Coefficient|Minimum|Median|Maximum|
|---|---:|---:|---:|
|Correlation|0.627625|0.829369|0.934896|
|Volatility match k|0.386433|0.593639|0.808967|
|Minimum-variance k|0.276770|0.471227|0.742483|
|Inverse SOL-on-BTC beta k|0.478156|0.781525|0.982951|

These unconditional summaries are not fixed-position PnL, optimal hedge sizing, or H4 profitability estimates. CSV also preserves the105-entry coefficient subset without selecting a second window. Return convention is explicitly daily log returns; coefficients are not asserted equal to the original S0 beta270/H.

## Ownership decisions required before any future implementation

1. BTC open + same-side independent SOL signal cannot simultaneously be opposite hedge. Choose an explicit override/filter/exclusive role; do not describe them as the same policy.
2. BTC flat: standalone SOL needs its own cycle, size, TP/SL, native admission and terminal ownership. If BTC then opens while same-side SOL is held, preselect wait/reduce/close/override semantics; no silent flip.
3. NETTING has one physical SOL inventory. Standalone, original S0 SOL-alpha overlay and proposed hedge cannot each claim the whole native position. Require exclusive economic mode or explicit fill-based ownership through one native executor; no parallel PnL/cache authority.
4. BTC becoming flat requires an explicit hedge disposition. Do not reclassify an existing hedge as a fresh standalone trade or fabricate new rights. Unknown ACK, partial fills and mandatory-exit priority remain native constraints.
5. Original SOL overlay is a rights/alpha lifecycle, not a continuous beta-balanced hedge. Replacing/adding it is a new economic version; this census gives no exact-S0 alternative TOTAL/DD.

Root gates retained: H1 NO_ECONOMIC_GO, H2 NO_NATIVE_GO, H3 PRECHECK_ONLY, H4 ANALYSIS_ONLY. No half-only/combined/native run admitted. Final read-only source check: canonical HEAD0bd7351/statusSHA852caf1e unchanged; isolated HEAD75ffc9c CLEAN. No product-code edits, engines, models, service actions or orders.
