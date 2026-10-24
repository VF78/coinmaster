# Actual native attribution helper

Prepared on actual accepted R1; no engine, native historical run, source/ledger/shared file change or new hypothesis. R2/R3 invocation belongs to root after each run has its accepted `native-analysis-R?.json` and immutable final files.

```sh
python3 reports/market-redesign-20261024/native-analysis-attribution-extract.py \
 --artifact /ABSOLUTE/ACTUAL/R2/FINAL.json --variant R2 \
 --reference-cycles reports/market-redesign-20261024/native-analysis-attribution-R1-cycles.csv \
 --output-prefix native-analysis-attribution-R2
```

Optional `--raw` selects raw JSON; default `<stem>-raw-native.json`. Optional `--acceptance` selects root's saved analysis acceptance; default `native-analysis-R?.json`. The tool requires validated full native accounting and verifies current artifact/raw/orders/journal/trace hashes against that accepted report. It never edits original outputs. All outputs are `native-analysis-attribution-*` in this report folder.

Outputs:

- `-cycles.csv`: measured parent count, native signed flat price-cash PNL, actual fees, signed persisted funding, net/bp of actual total entry notional, actual first/second filled quantities and fill/order counts, TP1/2/3 quantities and exit reasons. Each parent interval must finish flat without inventory side flip/overlap; otherwise STOP rather than invent cycle attribution. Parent identity/cohort is actual start+side, not forced83 or random archived episode IDs. Archived E4 actual timing/quantity is an observed reference only.
- `-cohorts.csv`: all/first-year/second-year entry cohorts; equal-notional mean `net/actualentrynotional` in bp, actual cash totals separately, worst ceil10% and worst individual by that bp return. Worst absolute USDT loss is separately visible in raw cycles; these rankings are not interchangeable. Years are [2024-09-01,2025-09-01) and [2025-09-01,2026-09-01). Entry cohorts differ from marked-calendar returns when a cycle spans the boundary.
- `-windows.csv`: full period, two marked years, all7 old E4 peak→trough windows plus6 existing peak→recovery windows, and six owner periods. UTC owner bounds explicitly: Oct3→Oct4,2024; Jan13→Jan14,2025; Apr11→Jun7,2025 (includes Jun6); Oct22→Nov29,2025 (includes Nov28); Feb8→Feb9,2026; Jul1→Sep1,2026. These are reporting windows, never trading rules.
- `-DDge30.csv`: every actual >=30% settled-grid high-water excursion, peak→maximum trough, recovery timestamp if any. Peak/trough are candidate observations, not old E4 dates imposed on candidate. Unrecovered final excursion retained. Intraminute extrema remain UNKNOWN.
- `-common-parent-observations.csv` with `--reference-cycles`: observed entry/second/TP quantity/notional/net changes at identical actual start+side; candidate-only/reference-only cases explicit. These are not causal isolated effects of compounding/TP/entry sizing and must not be added as frozen dollar effects to form a new TOTAL.
- `.json`: hashes, coverage, funding/rounding qualifications, reconciliation verification.

Endpoint arithmetic preserves native account scope (these variants have reserve0; tool stops if a separately observed reserve path would be required). For each asset:

`marked pricePNL = Δ(signed native inventory × exported mark close) + actual signed executed fillcash`.

Actual fee differences and signed persisted funding are separate, never allocated from a residual. Endpoint marked TOTAL change is compared with that component sum and the residual stays explicit. Exported raw mark close has more precision than actual native `instrument.make_price(close)` used by the observer. Thus interior marked-price attribution can retain a small native mark quantization residual; it is **not** an independently reconciled exact native-priced asset PNL. A conservative quantity×one-native-tick endpoint bound is recorded (BTC0.1/SOL0.01, frozen native_fixture.py66–67); this is an attribution qualification, not a widened global cash acceptance tolerance. Exact native rounded close was not exported. No inferred price or residual-based funding is manufactured. Full period has flat endpoints and avoids this mark issue.

Snapshots are as-of actual `receipt_ns<=requestedUTCboundary`; source_quote_ns and receipt_ns are both retained. Execution flow inclusion is based on actual `fill_epoch`, not an assumed same-timestamp order. Frozen source `minute_risk.py167–169` increments only in `note_fill`, called only from the `on_order_filled` wrapper299–301. Every one of1,051,199 actual receipts is checked: epoch monotonic/bounded and exactly equal to count of actual fill-audit timestamps<=causal source quote. At selected endpoints native signed inventory also exactly matches that prefix. R1 max trace epoch336; actual terminal epoch337 is the native TERMINAL_CLOSE at end-exclusive, after the final source quote=end−1minute, included only with observed terminal cash/fill facts.

Interior funding inclusion uses actual event timestamp<receipt_ns. Exact timestamp ties are explicit UNKNOWN ordering, not assumed inclusion. Actual terminal endpoint includes all actual persisted signed deltas. No tautological assignment to funding, TOTAL, SOL or residual cash bridge occurs.

R1 genuine verification:83 measured flat/nonoverlapping cycles;337actual fill events;1,051,199receipts. Cycle net sum294372.03028518 vs observed TOTAL−seed294372.03028516; native-minus-derived **−0.00000002USDT**, same as independent global cash check. Full-window residual also−2e−8. Seven actual DD>=30excursions;22fixed/year/full windows. Of29window/DD rows,12 reconcile within explicit native rounding,13 retain residuals consistent with unexported native mark rounding (not exact reconciliation),4 have funding endpoint timestamp-tie qualification. First-year marked TOTAL10000→84464.41339735 (+744.644134%); second84464.41339735→304372.03028516 (+260.355347%). These are R1 actual results, not R2/R3 or new candidate PASS. Equal-notional mean cycle return79.569984bp; worst9 mean−430.773123bp; worst bybp is cycle33 at−594.484685bp. The current global DD is July/August2026; no next experiment is inferred from old cycle31 or these rankings.
