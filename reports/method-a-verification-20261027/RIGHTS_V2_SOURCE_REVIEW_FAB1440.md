# RightsV2 source review fab1440

**HOLD: P0=0/P1=2. Root native GO=false. Reviewer tests/native0.**

Inventory `583bdf46c5495cb4673372f12d1e7672af9ddea77d48f5c365cfedab70d2e357`; patch `fab14403c5a269e46d5c8b1a3270cacc49aafa7ecbc31d82382b16aca1d05bef`.

## RIGHTSV2-01 [P1] Mandatory Accepted ACK is unavailable for the registered SOL market IOC path

`method_a_financial_reader.py:378`

rights_v2_evidence requires a native_acks row for every SOL_ADD. That table is populated only by typed OrderAccepted/OrderUpdated frames. Exact ce7 SOL_ADD uses MARKET IOC (strategy wave_overlay.py2068), and registered stock add_venue preserves Nautilus1.231 default use_market_order_acks=False (engine.pyx526). Native market processing emits Accepted only conditionally (5350–5354), then fills. Thus genuine Submitted→Filled market IOC orders can never satisfy this mandatory ACK lookup. The unit positive fixture invents a separate native_acks row and does not exercise the registered no-market-ACK event path. This knowingly leaves the replay rights UNKNOWN despite complete real fill/history evidence.

Correction: For the source-pinned MARKET IOC path, bind actual native fill/terminal history, CID/OID/strategy/instrument/side/quantity and genuine event IDs without requiring the optional OrderAccepted. Unfilled terminal orders also need their real terminal ownership disposition. Never count INITIALIZED/submission as accepted exposure, and do not weaken actual resting BTC TP ACK requirements. Add a stdlib fact-chain regression for actual no-Accepted market execution.

## RIGHTSV2-02 [P1] Touch proof changes legacy latch semantics and includes future same-timestamp entry fills

`method_a_financial_reader.py:282`

rights_guarded_touch requires a BTC crossing quote at exactly the activation row timestamp (282,291). Original _activate_selective_sol_rights latches an earned crossing first (source1623–1627); activation can occur at a later paired-ready quote without crossing again (1628–1637). Requiring simultaneous cross+activation adds a new oldSOL eligibility rule. In addition, earned entry sums every fill with ns<=activation_ns (289), including fills later in the same native timestamp than the activation snapshot, then compares against activation.confirmed_native_entry_qty. Existing source queue/fill ordering permits several partial entry/fill callbacks at one timestamp; future same-ns fills are not evidence of the earlier source state. Both paths can label faithful original-policy execution missing/invalid and waste the sole reserve.

Correction: Prove an actual earned latch-cross event and the subsequent guarded activation as separate causally ordered events. Bind the activation session/right-decision and confirmed entry to real before/after callback or quote frame sequence; exclude later same-ns fills. Preserve original late-entry/latch behavior, without inventing a new cross-at-activation rule. Add prior-touch/later-ready and same-timestamp later-entry negatives.

## Verified scope

- Inventory583b/patchfab144/reader7e625 and all draft-file pins independently match supplied hashes; no reader/test execution performed.
- No native imports/constructors introduced. Existing binder, strict cash NET-fees/funding residual policy, TP geometry and inherited numerical accounting blocks are not changed by this rights-only patch.
- Actual V2 observer pin, admission error/counters, immutable queued intent, raw parent/fraction writer snapshots and separate consumption/transfer/retired maps are explicit. Origin-to-admission writer evidence is per-interval, not blanket lifetime immutability.
- Creation remaining uses original float operation order and recorded hex; later budget changes are inspected without adding a current-budget clamp. Original ce7 late-entry flag remains true; no P3/A0/BTC-flat restriction or final-H backfill found.
- Native partial SOL fills are joined to admission/OID/parent/level/instrument and actual source before/after irreversible consumed-notional update. Initialized orders are explicitly not accepted exposure. These joins remain subject to the market-ACK correction above.
- Missing/stale/origin conflict paths fail closed; unit synthetic facts are clearly not actual native replay evidence. The proposed eight groups have not been executed.

One scoped stdlib reader/test correction for optional market ACK and faithful causal touch/activation proof, then exact source closure and focused pure execution. Do not spend the sole prefix harness reserve with these known evidence gaps. No new budget, product/observer change or replay GO is granted.
