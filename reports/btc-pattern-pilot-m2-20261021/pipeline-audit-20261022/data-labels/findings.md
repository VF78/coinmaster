# Data, time, features, labels and split audit

Scope: actual `btc_pattern_data.py`, original protocol/schema, saved prepared metadata and 32 uniformly spaced mature DEVELOPMENT origins. No model fitting, new predictions, CHECK scoring, service actions, or old-artifact/core edits. Independent probe: 283 assertions, 0.15s; NumPy only. Original source SHA-256: `d6ad604b95195d8c61e07f01888bab5b77ae57af1b1582e834c5a2f444ebb311`.

## Confirmed issue: input provenance omits 80h of feature warmup

`runtime/coinmaster/research/btc_pattern_data.py:50` computes each of the 64 volume features from a preceding 20-bar mean: the first feature reads 4h volumes starting at `t[j-84]`. Lines 49/52 also read the preceding close at `t[j-65]`. However line 54 records `t[j-64]`, and line 57 returns that as `input_start`; line 147 persists it. Thus `input_start` is the first **raw 64-bar window** timestamp, not the earliest actual input dependency.

Reproducer in `probe.py`: create positive synthetic hourly OHLCV, aggregate 4h, query at hour1300; multiply only volume at `t4[j-84]` by100. This candle is 80h before the returned `input_start`, yet the first engineered 4h relative-volume feature changes by `-0.2298544496`. The putative prefix assertion `assert np.array_equal(before[0], after[0])` after changing only data earlier than the claimed input start fails. Reported start is3758400000ms; actual volume-dependency start3470400000ms.

Impact: provenance/claimed isolation boundary is incomplete. `neighbors` line93 faithfully filters `label_end <= input_start`, but this can leave neighbor future outcomes overlapping the query's derivative-feature warmup if exclusion is intended to cover all raw dependencies. This is **not future-data leakage**: every consumed candle is already closed at the query. It is not evidence that the issue caused negative predictive results. The number of affected saved neighbors belongs to the separate retrieval audit; none is asserted here. If the intended exclusion is specifically the displayed64-bar window, that convention needs an explicit name instead of a claim of earliest feature support.

Minimal proposed fix, not applied: retain `raw_window_start=t[j-64]`, add `feature_dependency_start=min(t[j-84], hourly-context support start)`; choose and document the retrieval exclusion contract explicitly. Under full-dependency isolation use the latter. Here the earliest 4h volume dependency is336–339h before origin and dominates the169-hour context support; keeping both timestamps also avoids silently changing the visual/raw window. A corrected neighbor experiment would require a new version; do not relabel the archived results.

Acceptance tests: perturb a volume/close between dependency start and raw start and show engineered features can change; perturb data strictly before the full dependency start and require invariance; require every chosen neighbor label end to precede the selected documented boundary. Keep all four origin phases modulo4h in that test.

## Passed contracts

- UTC half-open aggregation validates alignment, contiguous timestamps and valid positive OHLCV; no interpolation or partial terminal bins (`forecast_independent_data.py:19-31`). Main inputs include only `bar_end <= origin` (`btc_pattern_data.py:36,47`), with known 4h age.
- Independently hand-computed up-then-stop, down-then-stop, same-minute two-barrier ambiguity, adverse open gap and favorable open-before-stop paths give correct D and long/short conservative MFE lower/upper bounds (`60-88`). A later minute open establishes order before that minute's extrema; unknown intraminute order is not invented.
- Horizon endpoints: `entry=origin+60s`, label end `entry+72h`; exactly4320 minute bars are consumed. The last included close is at entry+72h. An incomplete4320-bar path raises; no-touch sentinels equal2 and unknown tail labels stay NaN, not zero. All20928 origins satisfy metadata timing, with72 censored origins (`138-152`).
- Saved raw reference is the last close before origin; saved entry uses the open at origin+60s. Reference and entry indices differ by2, preserving the intervening minute. Entry-gap arrays equal `log(entry/reference)/sigma24_or72` and are separate from X (`138-159`).
- All saved input stamps end by origin. Sigma72 independently recomputed from168 completed hourly log returns matches saved metadata at32 DEVELOPMENT origins. Features normalize log-price components by hourly volatility×sqrt(TF); sigmaH uses×sqrt(H). No terminal-price/fill value enters `features_at`.
- Primary saved labels match path recomputation at32 DEVELOPMENT origins. This is a consistency check, while the separate hand fixtures establish sign/order/bounds independently. For all24/72h×SL.75/1/1.5 cases at those origins, stored `policy_mfe` correctly converts from sigmaH×SL back into **original sigmaH units** (`155-156`); the physical stop changes with SL.
- Every subfit, ES, refit and outer ID satisfies its actual cutoff including the entry minute; outer folds contain2808/2880/2808 mature origins. F3 labels never use May outcomes. ES begins in the final28 days and subfit purges to the inner boundary (`23-31`).

## Limits, not confirmed bugs

No full-history minute-path rescan or exchange-source authenticity audit was needed here. The saved-minute manifest/code identities were inspected; market label checks were DEVELOPMENT-only. OHLC bounds cannot reconstruct tick ordering or execution slippage. The 24h helper also returns its unused signature with later horizons clipped to24h (`83-84`); current callers discard that signature and only persist the72h signature, so no saved target corruption is established. Future users should not interpret that auxiliary return as genuine48/72h outcomes.

Overall: data/labels/time/units/split checks pass, with one confirmed input-support metadata defect and a separately scoped retrieval-impact question. No trading or new-training readiness conclusion follows.

## Closing whole-array coverage check

`whole_array_probe.py` / `whole-array-results.json`:20 invariant groups passed in0.17s, zero fits/new targets/new predictions. All1,280,160 minute rows (5,120,640 OHLC values) are finite, prices positive, volume nonnegative, high>=max(open,close), low<=min(open,close), high>=low. Entire-row count matches the aligned UTC minute start/end; origin clocks are unique hourly and all entry indices match the implicit minute axis.

For16,704 DEVELOPMENT rows matured **by2026-05-01** (explicit `label_end<=2026-05-01`, not merely origin before May), MFE/signature/policy labels are finite, MFE nonnegative and lower<=upper, and D ambiguity flags match D=-1. On all8,496 original outer origins, both long and short `MFE_lower>=1` identities match the unambiguous D cause:0 mismatches,0 ambiguous D. No CHECK outcome rows were indexed in this closing check. Reading the compressed NPZ decompresses its file; all outcome operations explicitly index only the purged DEVELOPMENT set.

Chronology limitation: `minutes.npy` stores OHLCV only, no explicit timestamp column. This check proves its manifest-implied axis, count and index alignment, not source timestamp authenticity. Original source gap/duplicate/UTC checks are reused from `prepare` source receipts and its explicit `validate` contract; independently re-reading every original source page was outside this bounded closing check. No original data/code validation defect was found.

Reproduce from worktree root:

```sh
PYTHONPATH=runtime OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 runtime/var/research-envs/btc-pattern-pilot-m2-20261021/bin/python reports/btc-pattern-pilot-m2-20261021/pipeline-audit-20261022/data-labels/probe.py
```
