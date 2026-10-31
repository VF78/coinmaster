# CM2 causal hedge diagnostics — report only

This helper never constructs an engine, strategy, order, fill, portfolio PnL or ROI model. It reads public historical markets to cache causal hourly features, then reads actual native observer trace/report files on their original host. Mac financial inputs must remain on Mac. Output is partial structural evidence with an explicit UNKNOWN boundary; it never emits a strong implementation/structure/benefit PASS.

`build-tape` reuses existing `CM2RunConfig.seed` (exact169 paired prestart hours), current public HL NativeInstrument factory and its actual `make_price` OHLC rounding, canonical streaming minute bundles, existing `PairedHourBuilder` and `features(Config())`. Thus hourly extrema are aggregates of rounded execution minutes, rather than rounding already aggregated raw hours. It emits the initial seeded feature and each complete paired60-minute hour; gaps/partial hours fail. End is canonical end or a whole-hour prefix; no future seed/data is admitted. Tape scope is beta, beta_guard, rho, six-hour residual, common/residual stress and ATR. These are independent of trend24..168 because the feature function always uses168-return history. Channel values are default T72 ONLY and never used by this audit to infer trading decisions.

Every required public input and code/binary file must appear in `--pins` as an **absolute resolved path → expected SHA256** JSON object from root-frozen receipts. Required set: canonical Bybit manifest; eight normalized BTC/SOL execution/mark/daily/funding parquet files; both pinned warmup CSVs; three public current-HL profile JSONs; actual `cm2_policy.py`, `cm2_runner.py`, `native_baseline.py`, `current_hl_profile.py`, this helper, Native Instrument base extension and pinned Native1.231 engine extension. Daily/funding files are provenance pins, not reinterpreted funding/PnL. All actual hashes, code hashes, pinfile hash and math-host fingerprints are recorded. Existing profile validation enforces current USDC public model and fees. No dependency install or network/account read is needed. Native Instrument creation is not an engine or economic attempt.

```sh
PYTHONPATH=/ABS/frozen-source/runtime /ABS/pinned-python -B -s /ABS/diagnostics/causal_hedge.py build-tape \
  --data-root /ABS/public-data --warmup-root /ABS/pinned-warmup \
  --profile-root /ABS/three-public-profile-files --pins /ABS/root-expected-pins.json \
  --output /ABS/NEW-feature-tape.json
```

Tape availability is exact reconstructed `Bar.ts_event=Bar.ts_init=M1open+60s`, then maximum availability of both symbols'60 minutes. `asof<=risk_event_ns` and `asof<decision_event_ns` are exported separately, with a one-hour freshness limit. Equality does **not** prove that a strategy callback actually saw the new feature before the same-clock quote. Strict prior is a conservative diagnostic, not a claim that the strategy used an older feature. Source-specific native feature receipts remain missing. Mac and Linux math fingerprints are retained; an independently regenerated tape need not be bit-identical across math hosts.

`audit` consumes exact pinned observer trace (`coherent-native-events.jsonl.gz`), native report and tape. All outputs use exclusive creation; raw inputs remain untouched.

```sh
PYTHONPATH=/ABS/frozen-source/runtime /ABS/pinned-python -B -s /ABS/diagnostics/causal_hedge.py audit \
  --tape /ABS/feature-tape.json --tape-sha256 EXACT_SHA \
  --trace /ABS/native/coherent-native-events.jsonl.gz --trace-sha256 EXACT_SHA \
  --report /ABS/native/native-report.json --report-sha256 EXACT_SHA \
  --output /ABS/NEW-diagnostic-directory
```

The committed observer supplies native positionID/side/quantity/native-rounded common mark, post-fill native tradeID, sequence, epoch and actual event/receipt clocks. Those support observed contiguous signed BTC inventory episodes, co-exposure/opposite-sign facts and orphan start/end event sequence/time. `SETTLED_PRE_NEXT_SOURCE_WATERMARK` is retrospective and excluded from current inventory transitions. Sequence/clock/epoch/position gaps are UNKNOWN; multiple same-symbol native positions are unsupported rather than netted into fabricated exposure. No adapter cancellation time or +60s is substituted for actual orphan endpoints. Endpoints are observed native event-clock bounds, including same-timestamp sequence changes; censored intervals stay flagged.

`SUMMARY.json` contains observed inventory episodes, actual orphan intervals, exposure/model-guard intervals, native snapshot counts and unknown reasons. `diagnostic-events.jsonl` contains compact post-fill, hourly feature-change and orphan-transition rows with both availability joins. Snapshot counts are not time-weighted exposure, independent trades or returns. Position IDs can be reused by NETTING; observed episodes are not business parent GUIDs. A first nonflat observation is left censored. A final open episode/orphan is right censored. Report observer PASS, trace sequence/fill count and exact report/tape policy-source equality are checked; missing proof remains UNKNOWN.

Model-only amounts use native signed notionals B and S, reconstructed causal beta and stress coefficients b/u: BTC-only downside `abs(B)*b`, joint downside `abs(B+beta*S)*b+abs(S)*u`, and hypothetical roundtrip SOL fee `2*.000432*abs(S)`. Net model reduction and beta/guard-factor ratios are diagnostics; no fills are matched, repriced or given counterfactual PnL. Guard nonflip is explicitly model-implied. The hedge hurdle is the policy-style common/residual/roundtrip hedge cost condition, **not** BTC positive-harvest permission. Actual BTC VWAP, allocated entry fees, parent funding and business lineage are not exported by this observer and remain UNKNOWN. Meaningful hedge threshold is not specified, so only raw notional/factor ratios are reported. Standalone SOL profit never proves hedge benefit.

Focused proof uses public Native Instrument metadata and synthetic prices/native snapshots only: exact rounded-minute hourly math versus existing features; prefix equality; common feature invariance at T24/72/168; strict/equal/stale joins; actual native event-clock episode/orphan extraction; retrospective watermark exclusion; missing fields and model factor flip. No actual financial audit or full-period tape has been executed here.

```sh
PYTHONPATH=runtime PYTHONDONTWRITEBYTECODE=1 /ABS/pinned-python -B -m unittest discover \
  -s reports/cm2-clean-hedge-20261031/diagnostics -p test_causal_hedge.py -v
```
