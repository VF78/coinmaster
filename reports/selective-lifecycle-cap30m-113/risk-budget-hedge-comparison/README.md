# CM-113 BTC episode budget / remaining BTC SOL hedge comparison

Exactly two isolated sequential native 24-month engines on frozen source 6c5e9d3. Archived minute-observer control is reused. Seed 10,000 USDT; reserve zero; Bybit interval [2024-09-01,2026-09-01).

| Variant | TOTAL USDT | ROI % | Native minute DD % | Seed minimum | Fees | BTC/SOL fills |
|---|---:|---:|---:|---:|---:|---:|
| control | 5146884.95718200 | 51368.8495718200 | 69.34097140401511909513176933 | 4233.3625743 | 1144089.96955003 | 311/191 |
| A_btc20 | 3806180.15651045 | 37961.801565104500 | 66.43688055060038334692368011 | 4847.90076204 | 1088165.31324150 | 333/191 |
| B_solhedge | 470568.99555379 | 4605.689955537900 | 72.30991447961151577544744328 | 6146.56744474 | 215435.80708486 | 311/55 |

Full TOP3 peak/trough/recovery timestamps, conditional envelope, fee/notional attribution, parameter differences, native guard/admission counts and immutable-source receipts are in comparison.json. All candidates processed 1,051,200 rows per source and 3,153,600 risk rows, reconciled fees, zero liquidations and terminal flat. Raw logs and traces remain private job artifacts.

All artifacts remain NOT_FAITHFUL_DIAGNOSTIC and ranking_eligible=false; these comparisons do not establish live readiness or faithful exchange execution.
A and B include two shared native lifecycle correctness fixes: ordinary-close pending ACK cleanup and cross-day SOL half completion. No fixes-only control was replayed, so pure candidate effects are not isolated.
A BTC20 measures native BTC episode realized PnL including fees plus held unrealized loss against portfolio equity at first confirmed BTC fill. It closes the group; it is not a global 20% drawdown limit.
B limits future earned SOL admissions to remaining native BTC notional/beta; held SOL is not rebalanced. Pending own SOL openings are conservatively serialized, which can delay/suppress same-cycle rights.
Native minute drawdown uses global marked-equity peaks without resets. Cached conditional OHLC adverse series is a fixed-exposure lower-envelope drawdown, not actual observed portfolio/tick drawdown or an upper-to-later-lower exact bound. That distinct bound is not exported by these cached summaries and was not recomputed by a new trace scan.
Signed funding remains UNKNOWN. Counts are not zero funding. Fixed fees, close proxy, absent L2/tick execution and liquidation applicability limitations remain.
Original control same-timestamp native callback ordering proof is incomplete; original control cross-day SOL half completion receipt is absent. New source includes focused proofs but this comparison does not retroactively attest old control.
Final prequote left-limit sample is retained; final postquote settlement samples are separately exported and excluded from interval DD/TOP3/seed minimum.
Initial A packing failure happened before engine.run, produced no funding journal/fill CSV, and is preserved; only two actual economic engines ran. No promotion/deploy/pilot change.

A: TOTAL delta -1,340,704.80067155 USDT (-26.04885891%); loss below seed 51.52099238%; 20 BTC episode-budget breaches, 20 rearms, 22 actual guard exit fills.
B: TOTAL delta -4,676,315.96162821 USDT (-90.85720782%); loss below seed 38.53432555%; 101 nonpending sizing clips plus 6 pending-opening ownership blocks; zero positive-admission native inequality violations. Control loss below seed 57.66637426%.
Upper-to-later-lower conditional bounds are unavailable for A/B in the cached summaries. The lower-envelope DD shown here is a distinct measure.
