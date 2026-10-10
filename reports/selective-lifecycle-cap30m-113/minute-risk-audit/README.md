# CM113 minute risk audit

Result SHA-256 `8e4a387260688729563258b84befe34b0bef2479f2fbe369c621fab9cc3281e2`; native source `d7d18cd`; source paths unchanged at canonical `9f892974`.

The winner does not evaluate 1-minute highs/lows. It feeds each execution close as a synthetic zero-spread quote with size 1000 and each mark close as nonmatching custom data. Liquidation is checked on every mark callback against native account cash plus native unrealized PnL and tier maintenance margin; with the research repair enabled a first leg callback may use the other leg's prior-minute fresh mark. Zero observed liquidations applies only to that minute-close diagnostic feed.

Archived native cash minimum is 7193.87239049 USDT at 2024-09-19 00:00:00+00:00. Loss below initial 10000 is 2806.12760951 USDT (28.061276095100%). Full minute marked-equity minimum and initial-capital loss remain UNKNOWN.

Top 3 distinct native CASH drawdowns (peak-relative percent, not marked-equity extrema):

|Rank|Peak UTC / cash|Trough UTC / cash|Loss USDT / %|Recovery UTC|
|---|---|---|---|---|
|1|2025-04-10 00:00:00+00:00 / 1095942.11640240|2025-06-08 00:00:00+00:00 / 413114.18091703|682827.93548537 / 62.30510948213748904270403494%|2025-09-25 17:37:00+00:00|
|2|2024-09-11 14:00:00+00:00 / 13759.84864610|2024-09-19 00:00:00+00:00 / 7193.87239049|6565.97625561 / 47.71837557581722853802517597%|2024-10-12 00:00:00+00:00|
|3|2026-05-03 20:37:00+00:00 / 8506264.26289257|2026-08-19 00:00:00+00:00 / 4866419.16808691|3639845.09480566 / 42.79017183470296191528068674%|Unrecovered at interval end|

Excursions are nonoverlapping peak-to-first-recovery periods; only each excursion's deepest trough is ranked. Ranking individual adjacent lows would repeat the same risk episode. CSV exports every distinct cash episode.

There are 2170 interval native cash checkpoints and only 24 monthly marked-equity checkpoints. Cash excludes open-position unrealized loss. All four normalized sources contain real OHLC; full bounded scans found no gaps, null OHLC or invalid OHLC (see audit.json). Data presence does not mean extrema were used.

A faithful observer replay is the cheapest available route to complete minute-close native marked equity: same native engine, strategy, fee policy, funding and feeds; record native account/positions and native unrealized PnL plus margin at paired closes and monetary events, then require exact cash/fills/orders/fees/funding parity. Stream compressed output rather than filling the existing checkpoint dict. Prior native run took 9m02s, systemd memory477.8M/Python RSS615MB; observer run budget about10–20m, unbenchmarked. No replay launched.

Full native minute account/cash/open-position/mark/maintenance trace including fill/funding event sequencing; exchange tick/path timing within each minute and synchronized BTC/SOL mark extrema. Existing fills/orders, cash, funding journal and 24 monthly marked snapshots do not supply native per-minute mark valuations..

OHLC does not identify intrabar chronology or cross-asset extreme synchrony. Changing execution/risk feed to high/low would be a new modeled scenario, not validation of the existing close-feed result. Any fixed-exposure OHLC risk envelope must label its conservative synchrony and intrabar exposure assumptions. Do not claim an exact actual historical maximum from OHLC.

Proof references:
- close_only_marks_and_quotes: `runtime/coinmaster/research/native_baseline.py:766-786`
- cash_report_and_export: `runtime/coinmaster/research/native_baseline.py:798-812,836`
- mark_callback_and_liquidation_equation: `runtime/coinmaster/strategy/wave_overlay.py:292-300,354-402`
- marked_equity_snapshot_gate: `runtime/coinmaster/strategy/wave_overlay.py:338-352`
- monthly_checkpoint_schedule: `runtime/coinmaster/research/native_baseline.py:306-313`
- native_unrealized_pnl: `runtime/coinmaster/strategy/wave_overlay.py:833-847`
- synthetic_size_1000: `runtime/coinmaster/research/native_fixture.py:472-477`

Opt-in observability implementation prepared in `runtime/coinmaster/research/minute_risk.py` and research runner CLI `--observe-minute-risk`. It emits three rows per minute (paired mark before quotes, after BTC quote, after SOL quote), native cash/free/initial and maintenance margins, native position side/quantity/entry average, actual mark OHLC, native PnL and conditional bounds. All sampled close points are combined in a constant-memory distinct-excursion tracker. Observer completeness is fail-closed. The actual captured profile is checked for monotonic maintenance requirements across every tier boundary before calling high-mark maintenance an upper bound. No high/low execution or liquidation event is published.

Focused native verification includes long and short market round trips with actual funding debit/credit, exact native account/fee/fill/order CSV parity (only engine `init_id` removed), streamed batch boundaries, and exclusion of pre-entry extrema. 24 tests passed; compile and diff checks passed. Economic 24-month replay remains pending root review and launch authorization. Its parity gate must compare 5146884.95718200 terminal total, 1144089.96955003 native fees,502 fills,556 terminal orders,1321 funding postings,0 liquidations,flat native positions and normalized fill/order digests.

CLI: existing isolated native recipe, with `--observe-minute-risk` added; retain original V0 control `runtime/var/data/runs/tp-fee-floor-113/v0/v0.json`, same `--research-v0-execution-repairs --research-v0-deferred-selective-zero-tp --research-v0-selective-lifecycle-repairs`, data root `runtime/var/data`, and a fresh isolated artifact directory. No source strategy, pilot, fee/funding model or execution configuration changed.
