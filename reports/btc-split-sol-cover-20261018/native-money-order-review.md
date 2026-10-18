# Independent narrow native money/order review

2026-10-18. Verdict: BLOCK P2 computation until one correction pass and focused recheck. Scope: frozen split_cover.py, strategy/domain wave_overlay.py, research/native_baseline.py, test_native_split_cover.py. No full historical run, services, deployment, credentials, or orders. Combined existing test log confirms 126 passed; the gaps below are not covered by that result.

1. **Missing hourly drift rebalance.** `runtime/coinmaster/strategy/split_cover.py:260-271` keys budget only by actual BTC quantity and tactical state, retaining an obsolete target indefinitely when BTC/SOL prices diverge. Plan section4.2 requires closed1H price-drift review and practical5pp coverage tolerance. Add hourly causal rebalance eligibility, preserving immediate actual BTC-fill/TP updates and unresolved-order ownership. Verify unchanged-quantity price drift both ways and no minute churn.
2. **Mandatory daily close suppressed while BTC parent unfinished.** `runtime/coinmaster/strategy/wave_overlay.py:1143-1145` returns before daily REGIME/TRAIL/close decisions. A pending parent cannot prevent mandatory close evaluation; next-day stop in split_check is later and does not itself replay the omitted daily close. Evaluate mandatory decisions while suppressing ordinary TP/entry work; prove incomplete parent plus regime change/close cancels entry before settlement.
3. **Legacy SOL hard timeout remains a competing owner.** `runtime/coinmaster/domain/wave_overlay.py:385-388,435-436` runs the14-day SOL timeout before the overlay-enabled gate. SOL-COVER disabling the old overlay does not disable that exit. `_cover_check` unchanged-budget suppression (`split_cover.py:260-271`) can leave permanent base absent afterward. Route SOL-COVER out of the old SOL lifecycle while preserving BTC/group emergency closes; prove an open BTC/cover episode beyond14days has only the coverage owner.
4. **Pause/resume can permanently omit base.** `runtime/coinmaster/strategy/split_cover.py:270-278` commits budget before the SOL_ADD entry gate. If the first base check occurs paused, incomplete remains unset; every resumed quote returns on identical budget. Existing native fixture reproduced BTC100/SOL0 after paused quote then two resumed quotes. Keep unmet base target retryable under a controlled policy; also cover rejected/partial/canceled native children without duplicate unknown-ACK orders.
5. **Tactical profitability basis is not actual fills.** `runtime/coinmaster/strategy/split_cover.py:240-247` sets tactical entry from the submit quote, estimates entry fees, and can mark used before an actual fill. Plan section4.3 requires positive result after trading fees. Accumulate tactical actual native fill quantity/notional/commission in the existing callback, use actual VWAP/known entry fees plus explicit exit-fee estimate for the exit trigger, preserve UNKNOWN honestly and never create a second PnL engine. Verify partial fills/slippage/fees and zero-fill denied tactic.
6. **Tactical residual retries escape original entry conditions.** `runtime/coinmaster/strategy/split_cover.py:235-242,260-282` checks4h/price quality only when first activating tactical, then retries an incomplete target under latched tactical/used state. Revalidate time, price, actual BTC and cap for each risk-increasing tactical child; prove delayed partial retry after4h or lost price advantage cannot add optional risk. Base remains independently mandatory.
7. **Accepted-net child quantity normalization guard.** `runtime/coinmaster/strategy/wave_overlay.py:1761-1779` would repeat zero-TP netting for split children already sized as accepted net lots, rewriting reference/planned quantities. This branch is unreachable in the approved deferred-selective V3 launch profile; it is a defensive accepted-Q contract gap, not an observed V3 economics bug. Guard initial normalization against `_split_child_submit` and test omitted zero levels preserving original reference/H, plannedQ and total actual fills.

One-lot parent exception (immediate one lot) is accepted if documented and tested. Existing use of native cache/order maps for unresolved ACK, cancel-before-fallback, actual position reduction caps and full BTC+mandatory base margin reservation is directionally correct. No GO for corrected code is implied until focused recheck. Existing minute-close quote and native execution limitations remain; no ideal fill or synthetic monetary result is accepted.

## Corrected targeted recheck — 2026-10-18

**GO for the isolated research computation gate.** This supersedes the initial BLOCK for the frozen source hashes below. It is not a trading/deployment approval or an economic acceptance result. Recheck limited to the seven findings, implementation contract, corrected native fixtures/logs, and a quick static safety review of the prepared launch helper. No full suite rerun, full historical calculation, service action, or helper launch was performed by this reviewer.

- Hourly drift: `strategy/split_cover.py:284-304` checks a new completed paired1H, archives actual versus desired coverage, and retargets beyond5pp; immediate BTC/tactical changes remain separate. Focused native regression `tests/test_native_split_cover.py:490` proves no minute churn then causal next-hour retarget.
- Mandatory close: `strategy/wave_overlay.py:1188-1197` restores the unresolved logical parent into the existing domain pending lock without suppressing mandatory pre-lock REGIME/TRAIL decisions. Existing forced-close path cancels parent first. Regression at `tests/test_native_split_cover.py:425` covers both reasons and actual native flat settlement.
- Sole SOL owner: `strategy/wave_overlay.py:243` sets the research-only domain flag; `domain/wave_overlay.py:435-436` suppresses old SOL exits while existing BTC/group emergency ownership is retained. Native beyond-timeout regression at test line442 passes.
- Paused/denied base: `strategy/split_cover.py:309-317` retains incomplete target before admission and does not consume the budget while paused; `strategy/wave_overlay.py:1685-1687,2509-2511` provides explicit1H failed-admission cooldown. Native tests at457/472 prove resumed immediate base and controlled rejection retry.
- Tactical actual basis: `strategy/split_cover.py:191-204` accumulates actual native SOL_ADD fills and quote-currency commissions; missing evidence raises rather than inventing zero fees. `:257-264` uses that quantity/notional/fee basis plus an explicit taker exit estimate for positive anchor-return eligibility. Test at521 verifies actual native partial quantity/notional/fees and a fee-negative anchor return retaining tactic until mandatory expiry.
- Tactical residual eligibility: `strategy/split_cover.py:266-283,300-301` rechecks4h, UTCexpiry and price quality, caps optional risk to already held exposure when invalid, and cancels pending tactical adds before a competing reduction. The partial regression at521 proves no bad-price or expired-window fallback and mandatory expiry preserving the current base.
- Admitted Q/reference: `strategy/wave_overlay.py:1765,1791` guards initial normalization/cap against a split child. Native omitted-zero tests at379 cover deferred approved profile and defensive initial-net branch: acceptedQ78.75 across two children, original referenceQ100, unchanged reference targets and actual-fill rights denominator. H correctly retains the original grossReferenceQ*actualVWAP/beta formula; H money value is not frozen to the first price. One-lot exception is explicit at `strategy/split_cover.py:99` and native test508.

Evidence inspected: implementation-focused-corrected-tests.log **30passed**; implementation-corrected-tests.log **136passed**. These corrected logs, not the earlier126 result, cover the original findings.

Helper `scripts/launch_split_cover_native.py` static review: lines60-72 verify shared650MiB/Swap0 slice, empty cgroup,700MiB memory/1GiB disk floors and exact protected pilot identity;77-103 preserve source/runtime and report-warmup layout and hash frozen sources/inputs;108-121 use env-i, bounded thread settings and exclusive flock;125-130 apply User994, private network, strict filesystem, readonly source/venv/data and job-only writes. Single-job safeguards are in both preflight cgroup check and runtime lock. Helper has not been executed; systemd mount/start behavior remains an operational launch check, and each result still needs native accounting/coverage/completion validation.

Frozen reviewed SHA256:

```
017988ecb7e14aae0cbd263e15f8d9ffe7eb0de30d5496ff5e5c25252dfe6835  runtime/coinmaster/strategy/split_cover.py
4b25b6f72b8420823d2596a2a09394cf4f31a981773f0552b364562b69d26765  runtime/coinmaster/strategy/wave_overlay.py
5a52a015bdb689a6d4c063dabda379b8e621bdb08cddcd05da12c4789b2db7b5  runtime/coinmaster/domain/wave_overlay.py
44db98a90dc1f4cf3aa1d86ccb95ec25dfa98b58d2f921d54e5b216d4d139abc  runtime/coinmaster/research/native_baseline.py
f111b9d35afccc2a590bd959ed10304256c368f8c2bd2e140bb9959b43ecaceb  runtime/tests/test_native_split_cover.py
ee7de8084ce52fea13bd6b3684bd63a85253cba0eed48fbcd7541adaf0874e63  scripts/launch_split_cover_native.py
```

## Final causal anchor recheck — 2026-10-18

**GO retained for isolated research computation**, with the two updated source pins below superseding their prior hashes. Scope only: actual BTC presence before creating SOL cycle, actual native initial-base fill VWAP/clock, no premature tactical arming, and frozen initial-base anchor after completion. No broad audit or full suite rerun.

`strategy/split_cover.py:233-241` now leaves cycle absent when BTC has no actual native position; a new cycle has anchorNone. `:195-209` accumulates only initial BASE actual fill quantities/notionals up to the fixed initial base budget, computes their real VWAP, sets4h start from the first actual fill and archives receipt evidence. `:264-269,286-288` requires the initial base anchor budget complete before tactical arming/admission. Later base fills cannot rewrite the completed anchor. Existing flat-cycle handling remains outside the new-cycle guard.

Native cases `tests/test_native_split_cover.py` test_pending_btc_without_native_fill_does_not_start_sol_anchor_or_tactic_window and test_initial_base_anchor_is_actual_native_partial_fill_vwap_and_freezes verify no anchor on unfilled BTC intention, submitquote100 versus actual partial101/102 VWAP, firstfill timestamp5, and unchanged anchor after hourly resize. Inspected implementation-focused-final-tests.log: **32passed**. Previous136combined result remains evidence for otherwise unchanged reviewed source; final anchor patch has32focused validation.

```
0cb6de91e49e1b28d5383a8a487cdefa396ff32223037cdacc4f10d622cf13d4  runtime/coinmaster/strategy/split_cover.py
419e988563332e6743b9b5032155f683fa210eab5aeae40854c7080b69074a0f  runtime/tests/test_native_split_cover.py
```

Other reviewed pins and the helper static-review limitation are unchanged.

Whitespace-only finalization: removed extra blank EOF from test/helper; no executable change or test rerun. These hashes supersede the same paths above; GO unchanged.

```
df23f697e96e6dead679e2fee25f18f3aca7cf0d0635ae6e9cdcc562d0e98a98  runtime/tests/test_native_split_cover.py
2b879fb37b47683ff1a252a146673ddef8a6e63853cec7f25e460d592f64b1df  scripts/launch_split_cover_native.py
```

## PLANREF_V1 final narrow review — 2026-10-18

**GO for isolated PLANREF_V1 research computation.** Full24m economics, actual permissions/parent matching, volume, execution and DD acceptance remain pending. No105-parent guarantee, live trading or deploy approval. No test rerun/source/index edit/service action by reviewer.

Reviewed applied patch SHA2564357c4c194e8f218e87cdc1d0a21cc7357bad20997f93ca89464eec28ce48486, planref-v1-applied-evidence.json and actual planref-focused-final-tests.log: **10passed,32deselected in4.02s**. Runtime candidate matches the prepared preview; only dummy daily feature fixtures were repaired with z=None, retaining assertions. Independently recomputed all six applied source hashes below and matched evidence.

`strategy/split_cover.py:125-131` freezes P0 only when accumulated actual first-leg filled quantity equals the first budget; partial-first P0 remains unset and falls back to actual current entry VWAP. `domain/wave_overlay.py:212-214,385,565`, `strategy/wave_overlay.py:1370` and `strategy/split_cover.py:160-161` consistently apply management P0 to daily TP/TRAIL/best_f, resting TP prices, conditional reduction eligibility and early-TP acceleration. Existing acceptedQ/position caps, cancel-ACK execution and mandatory close precedence are unchanged. Native fill accounting and H formula are unchanged; PLANREF callback additions export audit fields only.

Both-side native cases at test lines602-631 assert native average entry matches actual blended domain VWAP, actual commissions are positive, realizedPnL equals negative actual fees before reductions, native account cash equals seed10000 minus actual fees, H uses actual aggregateVWAP, and TP lot total remains acceptedQ. Cases at634/652/704/724 establish partial-first freeze timing, unchanged strict3% TRAIL using P0, real mandatory close before completion retaining truthful cancellation quantities, and no rewriting of confirmed native reduction/SOL rights. DefaultOFF and invalid-candidate cases also pass. This supports decision-reference separation without a second money engine; it does not establish historical permission parity.

```
e8de2eff497e5aca19c94b06a7829b5a70de46e276a724e983be01c47408a4f2  runtime/coinmaster/domain/wave_overlay.py
5cd994506696e0b7d13d2d1d0a469576e754fbebc1b0abcc7fd52bb8f4c8e98b  runtime/coinmaster/strategy/wave_overlay.py
5d76ddc063e6603eb25dbdf8c6bd9a476ca093c41d1d13ab1be39f25a4d02ea3  runtime/coinmaster/strategy/split_cover.py
7c1f8ae601f8d095617215c09dbe57be9cf4ad2063f17e451d983ae872bbb0ec  runtime/coinmaster/research/native_baseline.py
4d4ed0daeef3778be2c9d2ca1793b7b311234ecbf46a78b5f05f54a381cc923c  scripts/launch_split_cover_native.py
df68b80846a916267f33896201a0ba5598a9d91314acac1cab33c4d8c59286d4  runtime/tests/test_native_split_cover.py
```

## PLANREF positive-TP IOC catch-up — final narrow review 2026-10-18

**GO for the isolated seventh research run.** No live/economic approval or historical permission/volume guarantee. Scope only: changed completed-parent positive-TP native execution/ownership path and actual money evidence. No reviewer test rerun/source/index edit/service action.

Independently recomputed all six source pins below and patch83f628e1ef14498e7e3650ff43622b5d287ba269c8e713e757657a03e183200b; all match tp-ioc-applied-evidence.json. Actual logs inspected: focused **8passed** then full relevant module **50passed**; these overlap and are not58distinct tests. Guard alternative has no sourceflag/reference in reviewed runtime/helper/test files.

`strategy/split_cover.py:186-194` admits only positive-level reductions after exact full acceptedQ completion, zero cancellation, correct episode and no forced/liquidating state. `strategy/wave_overlay.py:1831-1843` checks the canonical native target against cached executable bid/ask, retains id/level/leaves by replacing only limit_price, and falls through the existing market factory at1892 with IOC/reduce_only; no ideal threshold fill is inserted. Native TAKER commissions/post_onlyfalse and accountcash=seed+actualrealizedPnL are asserted for both directions at test745. P0, actualVWAP, actualH, targetQ and rights-before-fill assertions are retained.

`strategy/wave_overlay.py:1362` blocks a competing same-level pending order, including unknownACK, without dropping queued leaves; existing1370-1381 conditional path rechecks actual management target on each accepted retry. `:1940-1970` extends the existing accepted-reduction owner/requeue path rather than adding an executor; native position cap remains in submit. Tests782/810/849 prove partial total21.25, fractional SOL rights only from actualfills, adverse-quote wait, unknownACK exclusion, mandatory close preemption/owner clearing, and native remainingposition cap. Tests768/824/842 prove unchanged maker/OFF, no precompletion/zero-level activation and explicit PLANREF/nativefee-profile gating. No blocker found in this narrow review.

```
e8de2eff497e5aca19c94b06a7829b5a70de46e276a724e983be01c47408a4f2  runtime/coinmaster/domain/wave_overlay.py
2b76b98397245c66493befc8332c1f1f8c2739a1f347fed82e232c12cc2e1d39  runtime/coinmaster/strategy/wave_overlay.py
ac0cbda7fe529d95c29d0a336fe1cabce3f9c4e355900f080c77119e2cb04525  runtime/coinmaster/strategy/split_cover.py
2d2983638225214831c8cec20a52cf170175b637a344ec27a95a02ad25573b9c  runtime/coinmaster/research/native_baseline.py
0730d7fb8eeabec880e66d4734ae71d88804ce0ac517dab9c078bff9c206afe6  runtime/tests/test_native_split_cover.py
40ecccf599228c6f7c86328d5702759790333becf68ee3c78aa9005c9ad77f06  scripts/launch_split_cover_native.py
```

Pre-seventh-outcome eligibility clarification: no concrete plan3.3/native-ownership violation has been found in sixth PLANREF. Its truthful marketable-post-only skip and original daily fallback can miss or delay early reductions; that is a disclosed execution-policy outcome, not an invented maker fill or invalid native money/right. With root-reported105permissions/full acceptedQ and truthful native accounting, sixth remains an eligible comparator. Do not disqualify it retrospectively because seventh has different ROI/DD. Seventh is a separately versioned actualTAKER IOC catch-up policy. Ranking remains maximumTOTAL among genuinely eligible variants; lower-DD goal is reported separately.
