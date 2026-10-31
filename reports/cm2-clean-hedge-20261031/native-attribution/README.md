# Native six-hour attribution — descriptive report helper only

`native_attribution.py` uses stdlib JSON/gzip/CSV/Decimal. It imports no trading runtime, connects to no account, constructs no engine and never writes source/runtime/budget/ledger/data/lease files. Trace input is streamed; only cash mutation-epoch states and six-hour endpoints/window counts are retained. Raw report JSON supplies identity maps. No actual trial/E04 report has been read in authoring; all proof inputs are synthetic.

Actual money source is exclusively `POST_FILL_COMMITTED_NATIVE.native_cash_delta` and `POST_FUNDING_ACCOUNT_NATIVE.native_cash_delta`. Fill `native_id` maps to unique report `fill_audit.trade_id → instrument`; exact fill/event clocks are required. Funding native IDs do not themselves encode instrument reliably: map by actual `funding_cash_audit` tuple `(event_id,instrument,ts_event,before_total,after_total,signed_delta)` using exact ID/time/before/after/delta. Ambiguous zero postings, duplicates, unmapped money and foreign instruments are UNKNOWN. Native commissions/funding already enter these cash deltas; neither is added a second time. PRE_FILL/PRE_FUNDING copies validate identity/prior state but never contribute cash.

Cumulative asset cash is indexed by **native state_epoch**, with each committed mutation checked against actual prior/post native cash and its immutable position-state hash. Repeated quote publications are inert. Missing/noncontiguous/duplicate mutation epochs invalidate attribution rather than inventing intermediate states. Retrospective `SETTLED_PRE_NEXT_SOURCE_WATERMARK` joins its `state_epoch`, cash and native position-state hash, not the newer current epoch accumulator. When state_epoch differs from current epoch, explicit prior-source retention proof must match source, epoch, signature and first later mutation clock. Both current event clocks and emitted receipt clocks are checked; retrospective event time is not treated as current time.

Asset mark values are taken directly from each endpoint's `positions[].native_upnl`, with complete BTC/SOL native position lists and `cash+nativeUPNL=nativeequity` checked. There is no native VWAP reconstruction, fill matching, quantity×price PnL, realized-PnL simulator or counterfactual portfolio. Absent positions mean zero UPNL only within a complete validated native snapshot. At each UTC six-hour window, asset contribution is the change in actual allocated native cash plus change in native UPNL; BTC+SOL must reconcile to actual native equity change within explicit `1e-8`, Decimal precision60. Global coverage/identity/clock errors conservatively mark attribution UNKNOWN, never zero/PASS. Native joint equity differences may remain visible as directly observed facts while asset attribution is UNKNOWN.

Initial seed10000/reserve0 is the scoped known baseline, corroborated by the first contiguous epoch0 native flat cash snapshot within the initial minute. Seed/HWM/cash are never reset. Terminal `DIRECT_NATIVE_AFTER_ENGINE_END_RETURNED` must be native flat at the exact end clock. Its directly observed cash is labelled separately from asset attribution. Only AFTER all final trace/report coverage checks may terminal cumulative asset cash be called reconciled: any global error makes terminal attribution UNKNOWN and nulls asset deltas, their sum and derived cash-minus-seed; the separately labelled observed flat-cash row may remain as a fact. The final six-hour endpoint often lacks a subsequent-source SETTLED watermark: that final window remains UNKNOWN rather than substituting post-boundary settlement cash or inventing a left limit.

`WINDOWS_6H.csv` retains every canonical window, positive/negative/unknown, endpoint event/source/receipt/sequence/state-epoch basis, BTC/SOL cash+UPNL contributions, native joint cash/mark/equity changes and snapshot/coexposure counts. Counts describe current native snapshot rows, not duration-weighted exposure or independent trades. `SUMMARY.json` contains exact input/helper hashes, existing report source/config/data identity fields, global unknown reasons, terminal native flat cash and conditional diagnostics. Source/runtime/binary groups must remain separate (including old A00/R1, changed code and ARM/x86); missing exported binary identity stays UNKNOWN and requires root's external group receipt. This single-input helper never merges groups.

Conditional diagnostics split windows by attributed BTC adverse/winner and report SOL positive/negative contributions. Worst5% tails report BOTH BTC and joint means on the SAME selected window indices, once ranked by BTC attribution and once by native joint PnL. Unknown windows are excluded with explicit population counts. These are within the **same actual inventory path**; attributed BTC is not a BTC-only strategy, and SOL profit/cost is not proof of causal insurance benefit. Meaningful hedge threshold, business GUID, true decision-time feature equality and STRUCTURAL/BENCHMARK PASS remain unproven. Submission parent/feature audit metadata is not promoted into lineage or availability facts.

Exact CLI; run on the original financial-input host with a NEW output directory:

```sh
python3 -B /ABS/native-attribution/native_attribution.py \
  --report /ABS/RAW-NATIVE-REPORT.json --report-sha256 ROOT_EXACT_SHA256 \
  --trace /ABS/coherent-native-events.jsonl.gz --trace-sha256 ROOT_EXACT_SHA256 \
  --output /ABS/NEW-native-attribution
```

Defaults are canonical `[2024-09-01,2026-09-01)` UTC and six-hour windows. A separately labelled fixture smoke may supply `--fixture-scope --start-ns ... --end-ns ...`; it is never24-month evidence. Mac financial files must remain on Mac; the helper can be placed/executed there by Terra with finalized root inputs. Authoring did not run any real case or whole32 analysis.

Focused proof:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover \
  -s reports/cm2-clean-hedge-20261031/native-attribution -p test_native_attribution.py -v
```

Seven synthetic tests cover valid terminal reconciliation plus terminal sequence-gap, upstream-UNKNOWN and missing-coverage rejection, as well as fee/funding reconciliation once, retrospective WM after newer funding using the older state epoch, missing/duplicate/unmapped/foreign/gapped evidence, preserved missing windows and ambiguous zero-funding IDs. No engine/API probe/native attempt/runtime change.
