# P0 saved-output parity gate

**Exact observed economic parity: PASS. Strict original↔Mac repeat contract: FAIL, unresolved. Root decides P0 admission under §9. 45/46 comparisons match exactly.** The sole failure is two floating-point diagnostic fields in BTC3 parent audit. No economic output mismatch was found, but no new tolerance was authorized or applied.

| BTC3 parent field | Original immutable S0 | Mac P0 |
|---|---:|---:|
| `planref_v1_beta` |1.1957320011177692|1.195732001117769|
| `planref_v1_h_actual` |61610.393324870296|61610.39332487031|

All other parent fields match. The existing `verify_split_cover_repeat.py` compares the entire canonical parent audit exactly; these fields are neither identity nor excluded path/performance fields. Calling this strict repeat PASS would require an explicit qualification; this verifier does not invent one.

**Exact economic and risk matches:**

- TOTAL/ACTIVE `6077107.23887483`; RESERVE0; ROI fraction `606.710723887483` (60671.0723887483%). Native fees `945927.73761825`, including exact fill-audit fee sum and fee attribution.
- **621canonical native fills and710canonical orders exactly equal** under existing identity exclusions; ordered fill audit, entry sizing, native cash series and terminal flat lifecycle exactly equal.0liquidations,0terminal native positions.
- **1320funding rows exactly equal** across `(instrument_id,ts_event,rate,settlement_mark,account_total_after)`. Signed funding remains `UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA`, not0.
- Config hash `22e1eefe8f9c71669e52a8e44b7acbdfd5f177d6ef4ae2118e9df566a05c6edc`; data hash `7ab5ae2cdaa14885da28d188c7ad14dfc8168ee600b78535f7317409ea94e9cc`; policy hash `c9540fbef259039c95829a774ef54e0eea2dcf2b6748d6455e171bf28e889834`; full config/policy and source-hash metadata match.
- Full canonical saved risk object matches. Settled DD **66.25691486468686414439256686%**, callback DD **66.31878024969152066570091116%**, conditional OHLC bound **67.54771031869252420136632742%**.1051199settled receipts,1051200samples includingseed,0unavailable, no pending source quote. Conditional bound remains non-tick diagnostic.
- Raw P0 native TOTAL equals wrapper TOTAL. Streaming schedule matches after the existing peakRSS exclusion. No alternative cash/PnL reconstruction or new DD tolerance.

Original reference wrapper SHA256 `e7854784dce9bcf27e77d45ebe12873d78a42a0ecb43b3686f2a0da810fb2bfa` independently verified. Only thin original fills/orders/funding artifacts were copied read-only from VPS; byte sizes and original manifest SHA256 all match. No remote giant trace was read, no local million-row stream was required, and no engine/backtest was imported or run. SQLite finalized journals were opened `mode=ro&immutable=1` to avoid WAL/shm writes while using the existing verifier's exact SELECT/order contract.

`P0-validation.json` records each comparison and artifact hashes; `verifier-p0.py` reproduces the saved-output gate. P0 does not replace or modify immutable S0 and does not demonstrate 50/90. No product/source edits or services were touched by this parity review.


## Localized float difference and gate scope

A math-only270return probe on the same fixed input ratios reproduced both saved results exactly. Actual Mac3.12.13 and VPS3.12.3 give one different `math.log` output (BTCreturn index260): Mac `0x1.14f09ec787132p-7`, VPS `0x1.14f09ec787133p-7`. Mean/variance match; covariance differs by two ULP. Replaying the VPS log outputs through Mac arithmetic reproduces original beta exactly. This localizes the difference to platform `math.log`/libm rounding, **not JSON serialization**.

- beta original hex `0x1.321b7e0f94da3p+0`; Mac `0x1.321b7e0f94da2p+0` (**−1ULP**).
- H original hex `0x1.e154c961e09d4p+15`; Mac `0x1.e154c961e09d6p+15` (**+2ULP**, not1).

Source: daily log returns/270d covariance in domain `FeatureState.append` lines149/154; beta frozen into Episode at379, used for relative move at429 and H-derived SOL budget at438; H recomputed at560. Parent audit logs actual ep.h/beta_entry at strategy2469/2471. These are operational mathematical quantities, not intrinsically display-only fields. The saved P0 history nevertheless has **exactly identical native lot/sizing plans, quantities, actions and all205SOLfills/102SOLadds**. BTC3's start→nextBTCstart interval has **0SOLfills**. No new native/action/money/data mismatch was found.

§9 requires attested economic parity for P0 and explicitly invokes the previous strict repeat contract for R. The evidence supports root attesting exact **observed economic parity** for this P0 while preserving the strict parent-audit failure. This reviewer does not declare root GO. Future R on one Mac retains the unchanged strict repeat contract. No tolerance, exclusion, source change or engine rerun was added. Detailed hex/probe evidence: `verifier-float-localization.json`, `verifier-float-mac-native-runtime.json`, `verifier-float-vps.json`.
