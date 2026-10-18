# Conditional SOL native money/order review

Verdict: BLOCK the isolated economic run pending these three corrections. Frozen patch and all eight source hashes independently verified against focused-development-evidence.json. Existing20passing focused cases do not cover these failures. No source/index edits or reviewer tests/runs.

1. **[P1] CLI disables required original overlay**
   Evidence: runtime/coinmaster/research/native_baseline.py:717-718, runtime/coinmaster/strategy/wave_overlay.py:172-173.
   Conditional CLI replaces candidate with sol_overlay_enabled=False, but conditional constructor requires True. The economic launch fails before running; original overlay cannot remain enabled.
   Minimum correction: Exclude conditional from overlay-disable condition; add runner-built config regression proving original overlay enabled and constructor accepted.

2. **[P1] Original half-to-full exit decision index is lost**
   Evidence: runtime/coinmaster/strategy/conditional_hedge.py:117-126, runtime/coinmaster/strategy/conditional_hedge.py:243-250, runtime/coinmaster/strategy/wave_overlay.py:2379-2380, runtime/coinmaster/domain/wave_overlay.py:464.
   Both ownership release and native physical SOL_EXIT can fulfill logical SOL_HALF_EXIT without calling on_half_exit_decision. Wrapper checks physical intent action, so sol_half_decision_index stays None. Original subsequent full z exit is then permanently blocked despite half_done.
   Minimum correction: Record original logical half completion with applied decision index after release/native/mixed fulfillment, without inventing a fill. Regress causal half then later full domain decisions for all fulfillment routes.

3. **[P2] Later first native fill overwrites assignment-time sigma**
   Evidence: runtime/coinmaster/domain/wave_overlay.py:530-533, runtime/coinmaster/domain/wave_overlay.py:597-599.
   Transferred original ownership starts first_owned_at/fixed_sigma but leaves first_fill_at None. A later native original add sets first_fill_at and fixed_sigma together, replacing the ownership cycle original decision sigma and altering its z exits.
   Minimum correction: Record first native fill time separately while preserving existing ownership-cycle fixed_sigma until original flat. Regress transfer under sigma A followed by native add under sigma B.

One consolidated correction pass, then one final relevant verification batch and targeted recheck. No additional total audit requested.

Patch SHA256: 0e12114c941943920f11a8b477566fd7b13367a1b15fe736ccc686a886a41c77

Exact eight pins are retained in review-money-orders.json.
