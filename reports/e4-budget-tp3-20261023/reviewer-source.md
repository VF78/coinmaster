# Independent source review — final scoped GO

Reviewed owner-source.patch and read-only execution mirror on 2026-10-23. No historical engine, replay or product edits by reviewer. Final exact handoff matches reviewed five files: source 5dc17f0a8c6bc764746683f4d38bcf1fa9dcc77e, full patch SHA256 3101a12e00c7f7b943dbd345bbfeb7fd1acbd8a79e2976d98acf7cad5e9dd627, protocol SHA256 048234b57aace91940fc258dcf2941bd0ca39082518f0bf66aee5beb09f60c39. 219 relevant passing cases plus final 12 targeted cases cover 224 unique passing tests. All five immutable snapshot hashes and patch/protocol/test receipts verified; see reviewer-source-final.json. Disposition: GO for the frozen bounded research source only, subject to root's per-run authorization and physical-attempt ledger. No pilot/deployment approval or economic-success prediction.

The frozen protocol supersedes initial reviewer suggestions: equity is current native paired-mark cash+unrealized; H includes continuous settled observations and current native equity; SOL stress must dominate standalone BTC stress. Original proportional TP3 fill rights are retained. Initial reviewer-protocol.md describes earlier recommendations and must be read with protocol-freeze.json.

## Source findings

No concrete economic-code regression identified in the reviewed draft. SOL ATR uses only accepted contiguous closed D1 bars and Wilder14; future OHLC map entries do not participate. Current E comes from native account+position valuation, not prior receipt. High water updates before ATR/ownership rejection and native-flat cut reset; minute_risk's existing settled observation hook continues to retain observed high water even through quote-path early returns.

SOL cap floors to native lot, freezes one target until actual native flat with owned work terminal, and preserves consumed add-notional after risk sales. Whole original requested quantity is admitted or rejected; no clipped synthetic entitlement or timer restoration. Pre-submit denial calls domain terminal cleanup, whose cancellation path does not modify actual filled entitlement counters. Native pending/inflight state remains part of busy/unknown gates. Existing mandatory/ordinary exits preempt risk execution. Default flags remain false; patch introduces no new clock.timestamp_ns call in terminal handling.

BTC early allocation uses actual completed split/native initial lots, positive sufficient original TP3 target leaves, and rounded favorable PLANREF1%. It replaces the same level's queued intent rather than introducing a second level/reservation. Early leaves are compared with aggregate original TP3 filled lots; completion queues original-price remainder on a later eligible quote. Existing domain fill accounting and trade-ID dedup are unchanged, retaining original target denominator and proportional actual-fill SOL entitlement. Therefore early actual fills legitimately advance SOL rights timing; this is disclosed, not claimed invariant.

## Evidence status

owner-relevant-tests.log: 219 passed, 2 deselected. owner-base-clock-proof.log shows the same two tests fail in unchanged bd04 source at abstract Clock.timestamp_ns in _terminal_without_fill->_hedge_terminal. owner-base-clock-proof.json attests exact archived source/tests and unchanged terminal method. This supports baseline fixture failure classification, not a full-green claim. Actual native-engine registration is the correct fixture repair; no product clock fallback or assertion removal is justified.

Initial new fixtures prove long/short sequential partial TP3, original target quantity conservation, real fractional rights, native partial SOL risk fills, flat high water and causal ATR. Requested extra coverage: ineligible TP3 no-op, native reject/expire or cancel before first early fill with no credit/duplicate, forced-exit precedence during early pending, and actual pre-submit whole-add rejection with no consumption.

Initial snapshot had 1 failed /9 passed: resting-cancel fixture asserted replacement before terminal ACK advancement. Final targeted snapshot supersedes that verification blocker: owner-focused-final-tests.log now 12 passed, including the two existing clock tests registered with native_engine, preserving assertions and product behavior. The corrected cancellation fixture processes a genuine next native quote, then proves exactly one early replacement/no fill rights; REGIME-close cancels queued/native work. Additional fixtures prove real native RiskEngine OrderDenied on invalid wire precision before first fill, one replacement/no credit, ineligible target identity no-op, and actual _submit_intent whole-SOL-add rejection with no order or consumed entitlement. No launch GO until exact artifact/hash/commit handoff.

Reviewed final file hashes (SHA256):

- native_baseline.py: 49eaf719a571dec720e0a799601a86ccae4056ff8db610c11197e9ce25fc7946
- next_band.py: c030d8d8bb346a053d3c9e595be59fe250e24b5a1a5f4e11e996284d1f0f3c95
- wave_overlay.py: d57f22b4340d7fc57ce7a1bf0595eee0915a7746e3c4c377fd02119314948be4
- tests/test_native_budget_tp3.py: 28d8f22146f075359a11a6b3426e3f6b59acf4d999c642889d33a10a7efc6132
- tests/test_wave_native_integration.py: d8b0ebc8ee043a39d17cff4aca6a010e8490749627a43fbc73581b419eb7b039

Exact freeze must match these or receive scoped delta review.

Economic warning remains: archived as-of precheck shows October potential full1000 SOL cut, January2654.8/4000 and September12617.4/15000. These are strong cuts, not small trims; pending ownership is UNKNOWN in archive witnesses. Exact economic effect requires the separately bounded native run and is not predicted by these snapshots.
