# Two isolated native risk comparisons

Comparison reference is the reused audited selective-lifecycle30m winner TOTAL 5,146,884.957182 USDT. The original V0 artifact is only the immutable input-loader source, not the economic comparison baseline.

Frozen source 498a8fe0d62cac5cea00e81660195f7e9c3e0131; independent narrow review GO; 116 relevant tests passed. Two mutually exclusive flags, one fresh native engine/funding journal per variant, identical Bybit inputs and all other economics. No control rerun, pilot action, or follow-up candidate.

| Variant | TOTAL USDT | Change vs winner | ROI on 10,000 | Global native DD | Conditional upper-to-lower bound | Fees | Fills |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Reused control | 5,146,884.96 | — | 51,368.85% | 69.3410% | 70.4658% | 1,144,089.97 | 502 |
| solcap6 | 3,476,258.69 | -1,670,626.27 (-32.46%) | 34,662.59% | 63.1297% | 63.4791% | 979,346.01 | 492 |
| portfolio45 | 3,392,830.71 | -1,754,054.25 (-34.08%) | 33,828.31% | 64.8435% | 65.0787% | 1,142,862.13 | 518 |

Native DD uses the global 24-month pre/post callback-close sampled curve without any reset. It is not an exact intrabar trajectory. The final completed-bar prequote at end_exclusive is retained; terminal quote/fill settlement is separately exported and excluded from interval DD. TOTAL includes native terminal settlement.

| Variant | Minimum native equity / UTC | Loss below initial 10,000 | Conditional adverse minimum | Funding postings | Liquidations | Modeled conditional MM breaches |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| solcap6 | 6,146.57 / 2024-09-18T16:05:00+00:00 | 3,853.43 (38.5343%) | 6,120.96 / 2024-09-18T16:05:00+00:00 | 1321 | 0 | 0 |
| portfolio45 | 5,962.33 / 2024-10-04T01:01:00+00:00 | 4,037.67 (40.3767%) | 5,908.17 / 2024-10-04T00:42:00+00:00 | 1351 | 0 | 0 |

Signed funding and per-trade native PnL attribution remain UNKNOWN; posting counts are not signed funding amounts. Fees and filled notional come directly from native fills and reconcile to native totals. A change in final TOTAL cannot be attributed solely to the fee difference because subsequent exposure and compounding differ.

## Global native TOP3 distinct peak-to-recovery excursions

| Variant/rank | Peak UTC / equity | Trough UTC / equity | Recovery UTC | Loss USDT | DD |
| --- | --- | --- | --- | ---: | ---: |
| solcap6/1 | 2025-04-11T01:00:00+00:00 / 642,733.10 | 2025-06-06T15:17:00+00:00 / 236,977.93 | 2025-08-24T19:38:00+00:00 | 405,755.17 | 63.1297% |
| solcap6/2 | 2026-05-15T00:34:00+00:00 / 7,026,708.49 | 2026-08-18T03:33:00+00:00 / 3,038,843.97 | UNRECOVERED | 3,987,864.52 | 56.7530% |
| solcap6/3 | 2025-10-22T21:29:00+00:00 / 1,503,946.99 | 2025-11-28T14:28:00+00:00 / 650,659.27 | 2025-12-01T04:23:00+00:00 | 853,287.72 | 56.7366% |
| portfolio45/1 | 2025-04-11T01:00:00+00:00 / 1,075,085.05 | 2025-06-07T00:17:00+00:00 / 377,962.10 | 2025-09-25T17:32:00+00:00 | 697,122.95 | 64.8435% |
| portfolio45/2 | 2026-05-15T00:34:00+00:00 / 7,328,752.33 | 2026-08-18T03:33:00+00:00 / 2,970,132.71 | UNRECOVERED | 4,358,619.62 | 59.4729% |
| portfolio45/3 | 2024-09-14T00:19:00+00:00 / 13,807.88 | 2024-10-04T01:01:00+00:00 / 5,962.33 | 2024-10-11T17:34:00+00:00 | 7,845.55 | 56.8193% |

Conditional adverse lower-series TOP3 are in drawdown-top3.csv and the JSON. These lower-to-lower excursions are not the conservative maximum intrabar-DD bound. The separate favorable running-upper to later adverse-lower maximum permits unfavorable same-bar ordering; BTC/SOL extrema are not synchronized and historical path/order is unknown.

## Measured mechanism and native economic divergence

**solcap6:** 14 preceding native monetary fill rows match the control before the first divergence.
- First control row: 2024-10-03T00:00:00+00:00 UTC, SOLUSDT-PERP.P1SIM, SOL_ADD/SOL_ADD, qty 766.1, price 140.09, notional 107322.949, commission 59.02762195.
- First variant row: 2024-10-03T00:00:00+00:00 UTC, SOLUSDT-PERP.P1SIM, SOL_ADD/SOL_ADD, qty 397.2, price 140.09, notional 55643.748, commission 30.6040614.

SOL admission attempts 113; positive admissions 91; positive clamps 74; zero admissions 22. All positive admission inequalities verify against native equity, aggregate held marked notional, gap/fee reserve and lot normalization. This is entry sizing only; held exposure can later exceed6x as prices/equity change. H/reference, BTC sizing, rights and exit rules stay unchanged.
First clamp 2024-10-03T00:00:00+00:00: desired 766.1 SOL → admitted 397.2; native equity 9305.85093314; existing held SOL marked notional 0. Counts are admission attempts, not unique native fill orders.

- BTCUSDT: native fills 311, filled turnover 1,961,735,109.01 USDT, native commissions 964,409.75.
- SOLUSDT: native fills 181, filled turnover 27,156,827.04 USDT, native commissions 14,936.25.

**portfolio45:** 8 preceding native monetary fill rows match the control before the first divergence.
- First control row: 2024-09-18T00:00:00+00:00 UTC, BTCUSDT-PERP.P1SIM, FORCED_CLOSE/REGIME, qty 1.002, price 60263.4, notional 60383.9268, commission 33.21115974.
- First variant row: 2024-09-17T14:16:00+00:00 UTC, BTCUSDT-PERP.P1SIM, FORCED_CLOSE/RESEARCH_PORTFOLIO_45, qty 1.002, price 59716.8, notional 59836.2336, commission 32.90992848.

Protection breaches 7; next-episode rearms 7; actual protection-exit fills 8, exit commissions 24,805.23. These RESEARCH_PORTFOLIO_45 exits are distinct from original TRAIL/REGIME and are not fixed price SL exits. Protective peak resets only after actual native flatness and the next fresh genuine BTC episode; global observer peaks never reset. Repeated epochs can still produce global DD above45% or50%.
First breach 2024-09-17T14:16:00+00:00: native equity 7582.71828958 versus protective peak 13807.88227209; old episode 5b4deecf-0163-4a66-879e-aaa8f86d6cd4; first/last exit fill latency 0/0ns. Last fill is not a separate atomic native-flat acknowledgement.

- BTCUSDT: native fills 327, filled turnover 2,286,514,192.42 USDT, native commissions 1,126,586.09.
- SOLUSDT: native fills 191, filled turnover 29,592,797.51 USDT, native commissions 16,276.04.

Recommendation: neither comparison meets the sampled global native ≤50% target, so this bounded comparison has no qualifying winner. Preserve the control as the ROI reference; no next candidate or deployment is authorized by this report.

## Why the portfolio guard still exceeds the global target

Seven protective epochs breached and seven rearmed. Each trigger uses its current protective peak; the global 24-month peak remains unchanged. In the deepest excursion, the first breach was 2025-04-13 19:41 UTC at 589,231.87 against 1,075,085.05 (45.1921%). The next episode rearmed 2025-04-14 00:00 UTC from 595,333.05 flat cash. A later protective peak reached 711,432.62; it breached 2025-06-06 13:41 UTC at 390,433.45 and rearmed 2025-06-07 00:00 UTC from 391,744.10. The next episode reached the global trough 377,962.10 at 00:17 UTC. The local reset permits successive losses; it does not restore the old global high-water mark. Exact trigger overshoots, exit commissions and measured fill latency appear in protection-events.csv; 0ns diagnostic fills do not prove real stop execution.

| Variant/rank | Native cash endpoint loss | Native unrealized deterioration | Cash share of DD |
| --- | ---: | ---: | ---: |
| solcap6/1 | 314,648.33 | 91,106.84 | 77.5464% |
| solcap6/2 | 3,590,090.77 | 397,773.76 | 90.0254% |
| solcap6/3 | 23,750.07 | 829,537.65 | 2.7834% |
| portfolio45/1 | 652,026.87 | 45,096.07 | 93.5311% |
| portfolio45/2 | 3,965,308.63 | 393,310.99 | 90.9762% |
| portfolio45/3 | 7,344.58 | 500.97 | 93.6146% |

These exact native endpoint components sum to each drawdown; cash includes realized trades, fees and unallocated funding and is not pure realized trade PnL. SOLcap6’s three troughs and PORT45’s two largest troughs hold BTC only. A bounded next hypothesis would reduce actual BTC exposure in these loss regimes, or test a tighter protective epoch threshold with the same next-episode resumption. Neither hypothesis guarantees 50% global DD or retained ROI; no additional run is performed here.

## Evidence and limits

comparison.json contains exact values, global TOP3, native prequote/postquote landmark snapshots, conditional bound endpoints, minimum exposed modeled MM buffer, cap admissions/protection events, sole config delta, native fill attribution and immutable trace paths/SHA-256. comparison.csv and drawdown-top3.csv are compact tables; both minute-risk-summary.json files and the independent review are retained. Large minute traces remain in immutable jobs and are not committed.

Execution is the existing synthetic zero-spread, size1000 quote policy from Bybit1m closes. Protection cancellation acknowledgement can invoke existing native market_exit against the previous cached book; pre-action marked loss and completed-bar OHLC exposure are captured first. Such fills are diagnostic and cannot be treated as venue stop execution. Funding/execution marks, historical venue fee applicability and synchronized ticks remain unvalidated.

Modeled maintenance uses existing native-equity≤tierMM only, without extra liquidation-fee reserve. Zero conditional modeled breaches is conditional model evidence, not actual venue liquidation safety. Quantity gap/fee reserve is admission evidence and does not force later SOL deleveraging.

Native fee liquidity reconciliation (fill counts, not unique orders):

| Variant | BTC entry fills | SOL add fills | Maker fills / fees | Taker fills / fees |
| --- | ---: | ---: | ---: | ---: |
| solcap6 | 105 | 91 | 78 / 65,454.03 | 414 / 913,891.98 |
| portfolio45 | 111 | 95 | 80 / 74,855.27 | 438 / 1,068,006.86 |
