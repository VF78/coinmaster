# Archived R3 prefix reference — not new-policy matched OFF

Interval `[2024-09-01T00:00Z,2025-01-15T00:00Z)`, original source `ec2a958e383a53133f8a8d03ef0e312810881265`, seed10000USDT. Read-only extraction from pinned full-run actual native receipts/fills and signed funding SQLite; no engine/replay/product edits. `implementation-archived-prefix-reference.json` carries exact input paths/hashes; `implementation-archived-prefix-nativefills.csv` preserves82original native filled-order rows for trace comparison.

| Archived measurement | Value |
|---|---:|
| Last receipt strictly inside interval | 2025-01-14 23:59UTC |
| Retained paired source close for that receipt | 2025-01-14 23:58UTC |
| Actual native cash | 19544.07357286USDT |
| Native account marked equity | 19544.07357286USDT |
| Native UPNL aggregate | 0 |
| Actual native open inventory at that receipt | empty |
| Fixed archived research RESERVE contract | 0 |
| Strict settled-receipt DD | 53.969901208792905709…% |
| Peak native marked equity / actual receipt | 34106.72858045 /2024-12-21 07:48UTC |
| Trough native marked equity / actual receipt | 15699.36086003 /2024-12-30 12:28UTC |
| Native fills before cutoff | 82BTC /0SOL |
| Native commissions before cutoff | 1135.02982656BTC /0SOL USDT |
| Actual signed funding cash events | 133 |
| Actual signed funding cash | BTC−633.29250058 /SOL0USDT |
| Actual parents started before cutoff | 19 |
| Actual parents flat before cutoff | 19 |

The actual receipt AT Jan15 00:00UTC (retained source23:59), separately excluded from the strict interval, reports identical cash/equity/inventory. The first later receipt at00:01UTC (source00:00) also agrees. No fills or funding cash events are timestamped exactly at this cutoff. These observations show the archived native account happens to be flat here; they are **not** a newly executed terminalflat prefix/forced boundary close or a new cash settlement. Cash was read directly from actual native receipts, never manufactured from summed fill PNL. Pending order state at cutoff is UNKNOWN: full-period final order status was not misused as a historical snapshot.

There is no receipt both sourced at cutoff and received before cutoff: that same-clock endpoint remains UNKNOWN under the old observer. At this particular flat endpoint no position mark is required for the observed cash value, but that fact does not repair the general event/mark-clock proof or #133's old unknown result.

The curve contains195,838actual receipts with receipt timestamps strictly inside the interval, plus the native from-genesis10000seed. From the first receipt (Sep1 00:02UTC, source00:01), all receipt gaps and source-to-receipt lags are60s. The initial seed-to-first-receipt gap has no native fills or signed funding cash mutations. Every retained receipt's fill_epoch was checked against count of actual native audit fills at/before source_quote_ns. DD uses actual receipt order and the original highwater from seed; peak/trough source times are one minute earlier and retained explicitly in JSON. This is the archived **settled receipt sampling**, not prefill/event/intraminute DD.

Native monetary/source proof: frozen `minute_risk.py:_snapshot` lines132–165 reads native account Money, native cached positions, native `instrument.make_price(Decimal(mark_close))` and native `Position.unrealized_pnl(Price).as_decimal()`. `finalize_receipt` lines171–199 rejects intervening native account/fill mutation and retains source prices. Native aggregate UPNL here is reported-equity minus reported-cash; no alternate PNL engine. Numeric native-rounded close Price is not exported separately, so raw serialized OHLC must not be substituted into hand PNL for held peak/trough states.

ACTIVE marked/TOTAL marked use native account marked equity under the accepted fixed research RESERVE0 contract. No independent external reserve stream exists in these receipts. Source uses disabled research deposit protection/no reserve-transfer module; no additional reserve money is invented.

Fees are native fill-audit commissions and match the original fills CSV multiset. Signed per-asset funding is read via SQLite `mode=ro&immutable=1` from `funding_cash.signed_delta`, and its prefix multiset matches raw-native signed cash deltas. SOL0 reflects no SOL native cash events/fills in the archived SOLoff model, not zero-filled unknown funding. Full native liquidation_audit is empty; that is reported actual model evidence, not inferred from finite PNL or a venue safety guarantee. All exported native cash/equity in the strict receipt sequence were observed finite.

**Execution comparability boundary:** the archived runner omits `liquidity_consumption` at its `add_venue` call, and installed1.231.0 stock default isFalse. The upcomingTrue-policy source must run its own matched OFF control inside the approved physical ledger. This archived reference cannot replace that control or excuse changed native BTC fills/fees/funding. Compare native trace identities and explain shared-depth differences; do not silently equate policies. Original S0 absolute70/90floors remain unchanged.
