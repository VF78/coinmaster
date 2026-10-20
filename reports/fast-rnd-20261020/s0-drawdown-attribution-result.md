S0: five largest native-W drawdowns inside T+V only. Receipt timestamps shown; source quote timestamps retained in CSV/JSON. No U receipt-position payload parsed; outside-T+V fee amounts not interpreted.

|Rank|Peak receipt UTC|Trough receipt UTC|DD %|Native W loss|Δcash|Δtotal UPnL|BTC fees|SOL fees|
|---|---|---|---:|---:|---:|---:|---:|---:|
|1|2024-09-14T00:20:00+00:00|2024-10-03T15:45:00+00:00|66.256915|8896.10017409|-3738.47267409|-5157.62750000|182.08278253|62.47943955|
|2|2025-04-11T01:01:00+00:00|2025-06-06T15:18:00+00:00|59.842724|547666.08219643|-407279.98224643|-140386.09995000|23358.73858803|1749.31350000|
|3|2025-10-22T21:30:00+00:00|2025-11-28T14:29:00+00:00|55.100556|1150759.43834313|12589.11625687|-1163348.55460000|32537.26917082|0.00000000|
|4|2024-12-31T17:11:00+00:00|2025-01-01T09:42:00+00:00|42.172484|79265.60078393|-190.14478393|-79075.45600000|0.00000000|71.43433440|
|5|2025-01-21T18:39:00+00:00|2025-02-04T22:13:00+00:00|40.268005|216292.59902564|2552.47182436|-218845.07085000|6272.95305096|0.00000000|

Native cash + total UPnL reconcile every listed decline exactly. Commissions already affect cash/W; these cost columns are descriptive and are not deducted again. Endpoint native BTC/SOL quantities, entry prices, marks and native low/high PnL bounds are in CSV/JSON.

Exact asset-level native realized/close-UPnL allocation and signed funding remain UNKNOWN because the native component artifacts were not saved. Positive open-UPnL reduction alone does not prove economic profit giveback when a position was realized into cash. No alternate PnL ledger is used.

Coverage: 840958 strictly monotone receipts, actual receipt <2026-04-08T00:00:00+00:00, one streaming pass. Peak RSS 19791872 bytes.

Brief endpoint attribution (native monetary facts only):
1. At the trough, SOL long native open-PnL lies between -5,619.537 and -5,165.433; BTC short is positive between 475.849 and 530.0042. Aggregate open loss is -5,121.0266. Cash also fell 3,738.47267409. Seed-capital loss is 5,469.42585299; exact initial-trade loss/realized asset allocation remains UNKNOWN.
2. Cash falls 407,279.98224643 and total open PnL falls 140,386.09995. Trough exposure is BTC-only, with exact native open loss 113,305.5378; this does not allocate the preceding cash loss by asset.
3. Both endpoints are BTC-only: native open PnL changes from +225,132.0842 to -938,216.4704 while cash rises 12,589.11625687. The open-book deterioration drives this decline; quantities differ, so this is not a same-lot causal PnL claim.
4. Both endpoints are SOL-only: positive native open PnL declines from 80,370 to 1,294.544, with cash down 190.14478393. This is predominantly positive-open-PnL giveback in the actual book; quantities changed.
5. Both endpoints are BTC-only: native open PnL changes from +93,132.17585 to -125,712.895 while cash rises 2,552.47182436. Open-book deterioration exceeds the W decline; no closed-trade allocation is inferred.

Cost timing: actual saved OrderFilled fill_ns, not filled-order ts_last. Fees use (peak.source_quote_ns,trough.source_quote_ns]; cash/position source finality guards had zero unavailable receipts. Native commissions remain descriptive and already included in W.
