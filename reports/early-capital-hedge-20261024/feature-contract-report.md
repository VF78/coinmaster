# CM-EARLY-HEDGE-20261024 — feature and availability contract

Scope: saved-source/data feasibility only; no outcome files read, no grid, no engine/training/product change. `feature-contract-check.py` and `feature-contract-availability.json` are the reproducible check and exact schema/hash receipt. `feature-contract-features.csv` contains only causal feature columns; the old future flat timestamp and episode audit fields were deliberately not copied.

## Accepted primary feature

At a completed UTC H4 close t, read synchronized completed execution-price H1 closes P_B(t), P_S(t). Root froze SIMPLE returns before any outcomes; primary definition uses SIMPLE returns, consistent with the existing lag720 sizing calculation:

- r_X24(t)=P_X(t)/P_X(t−24h)−1.
- beta(t)=sample_cov(r_B1h,r_S1h)/sample_var(r_B1h), using exactly 720 return end timestamps t−720h,...,t−1h; no return ending at t enters beta.
- residual24=r_S24−beta*r_B24; signed_residual24=actual_held_BTC_side*residual24. A positive sign describes SOL strength relative to held BTC side; opposite-side SOL then opposes that recent relative move. This is a causal descriptive feature, not proof of prediction or profitable insurance.
- adverse_H4 iff side*(P_B(t)/P_B(t−4h)−1)<0. Require held nonzero BTC, strictly positive finite lag variances, rho>0 and beta>0. No additional magnitude threshold or bin chosen.
- Same 24h window is available for LOG returns, but its consistent beta must be computed from LOG H1 returns too. It disagrees in sign on 2/1529 rows; freeze SIMPLE vs LOG before outcomes, never pick the favorable result afterward.

The saved state schema used is `decision_ns, decision_utc, cycle, period, side, observed_BTCqty, NB_USDT, BTCclose, SOLclose, lag720_last_return_end_ns, lag720_cov, lag720_rho, lag720_sigmaBTC, lag720_sigmaSOL, lag720_betaSOLgivenBTC, closed_H4_return, side_closed_H4_return`. NS_OWNER_VOL, NS_HALF_MV and NS_HALF_FACTOR are existing mutually different size conventions, not three interchangeable meanings of 50%.

Feature-only counts: 1529 decisions /77 observed R3 cycles. Root predeclared trigger is `signed_residual_simple24<0 AND adverse_H4` (183 first-year,208 second-year;391 total; no exact-zero residual rows). The earlier reported367 was the opposite `>0` sign (147/220), not this trigger. Both are feature sign counts, with no outcome evidence. Old cohorts are already viewed history, not fresh OOS.

## Sources and clocks

All paths below are relative to authoritative manager checkout except DATA:

- `reports/market-redesign-20261024/native-analysis-sol-R3-features.csv`, SHA256 `598591a2543088181ec003baf0a2d1e696e04c792c3a76c568e44d93441edbe7`: actual accepted R3 BTC inventory states; old extractor verifies fills against native audit, terminal flat and all 1529 decision quantities against settled native trace. It excludes fills exactly at t and uses inventory strictly before t. That prior verification was read in source, not freshly rerun here.
- `reports/b-50-90-next-20261023/owner-closed-bars.csv`, SHA256 `550b0825a713169713a6077fa52e5206ef349665ebc369e246daafe551d013fc`: schema `symbol,step_ns,open_ns,close_ns,available_ns,open,high,low,close,source_rows`. 17520 synchronized H1 closes per asset; available_ns=close_ns; H4 contains 240 completed execution minutes. Saved builder `owner-precheck.py` confirms aggregation from execution-1m, not marks.
- DATA=`/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data/normalized`. Its parquet files are symlinks to `/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/data/normalized`; hashes and resolved paths retained in availability JSON.
- `bybit-{BTC,SOL}USDT-execution-1m.parquet`: open_time_ms int64; OHLC,volume,turnover strings. `bybit-{BTC,SOL}USDT-mark-1m.parquet`: open_time_ms int64; OHLC strings. Each has 1051200 rows, continuous 60s opens, from 2024-09-01T00:00Z through 2026-08-31T23:59Z. Close availability is (open_time_ms+60000)*1e6. All decision prior-minute and next-minute rows exist for both assets; this check does not compute action returns.
- `bybit-{BTC,SOL}USDT-funding.parquet`: funding_time_ms int64, funding_rate string. BTC4380 rows at8h; SOL4740 rows at8h/2h, max gap8h. Strictly prior funding observation exists for every decision; use last funding_time<t, never infer next future rate was known. 743/1529 H4 decisions exactly coincide with a funding timestamp. Saved prior-minute close mark is a fixture convention, not independently verified exchange settlement mark.
- Old outcome schema can be inspected from extractor source without reading outcomes: its `crosses_observed_native_flat` is t+h>=flat and its old price actions execute at t close; they hold hypothetical original BTC quantity across the horizon. Those labels cannot silently become next-minute/strict-held-only labels.

## Recommended decision/execution and flat contract to freeze

Root froze the SIMPLE negative-residual/adverse-H4 trigger above; this contract does not select based on outcomes. Use feature availability t; decide strictly after all completed-bar input processing, and set earliest conservative hypothetical fill at e=t+60s using execution row open=t. Never claim simultaneous execution at t close merely because available_ns=t. Recheck actual BTC held state and side at e; exclude ambiguous same-timestamp BTC fills at t or e. If held quantity changes between t and e, size from the known pre-e actual quantity, not stale feature NB. This additional fill-state reconstruction was not run in this feature-only pass.

Freeze one size rule and cap before outcomes. HALF_MV: NS=.5*NB*cov/varSOL, factor relief=.5*rho²*NB. HALF_FACTOR: NS=.5*NB/beta, exactly .5NB factor relief but may require much larger SOL notional. OWNER_VOL: NS=.5*NB*sigmaBTC/sigmaSOL, relief=.5*rho*NB. Neither saved R3 scalar NB nor an ex-post equity ratio proves early capital admission/margin capacity. Equal-factor BTC trim uses the same NS*beta relief and both legs' transaction costs; long/short signed funding must match actual held/action side.

For strict hedge local arithmetic, define scheduled endpoint e+h (one prespecified horizon), and stop SOL at the first observed BTC-flat event if earlier; do not drop whole rows because a future flat occurs. That would select on future lifecycle. Treat any nonzero-side BTC fill/quantity reduction during the interval as a separately stated limitation or adjust hedge size under a predeclared causal rule; frozen original NB across reductions is not an implemented strict hedge. Reusing old fixed-horizon labels is valid only when explicitly labeled hypothetical fixed quantity, including cross-flat exposure, and cannot satisfy strict hedge scope.

Observed BTC-flat timestamp can define an ex-post exit boundary for arithmetic, but is never an entry feature. Same-timestamp BTC-flat/SOL-exit/funding/mark order lacks an event-level executable sequence in these scalar rows. Preserve ambiguity (boundary alternatives / UNKNOWN), rather than granting favorable settlement. e=t+60s avoids scheduled H4 entry and fixed 4h/24h endpoint funding ties, but an early BTC-flat event can still tie. No H1 close tail score establishes coherent event DD or intraminute bound.

## Early capital limitation

These 1529 rows are R3 U3TP/CLEAN_Q with SOL off, not E4's BTC/SOL-capital trajectory. First included row is 2024-10-02T04:00Z, R3 cycle5. H1 starts 2024-09-01; strict lag720 cannot exist before 2024-10-01T02:00Z. Therefore initial September cycles and the original early-capital mechanism are not supported by this sample. Existing R3 frozen actions can establish local conditional hedge/trim arithmetic only. They cannot establish E4 early equity restoration, own-capital BTC quantities/admission, later compounding, candidate TOTAL/retention, three actual TP legs, margin feasibility or event DD. Any claim about that mechanism needs distinct saved-native E4 decision/capital evidence and adequate past data, and eventually separately authorized native lifecycle validation; budget remains zero.

Check result: availability PASS; causal feature extraction PASS; 0 outcome files read /0 engine launches. One initial JSON serialization failure (NumPy integer) was corrected by explicit int conversion; availability rerun passed. Only `feature-contract-*` files written. Parent coordinator owns shared documentation/Project/ledger/reset preparation; no shared files or commits modified here.
