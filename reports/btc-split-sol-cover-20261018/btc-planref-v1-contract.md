# BTC025 PLANREF_V1 — prepared research version

Status: PREPARED ONLY, NOT APPLIED, NOT NATIVE-TESTED, NOT RUN. Root selected this version instead of the archived GUARD05 alternative. Apply only after all five initial frozen runs finish, then focused native tests, independent narrow review, root checkpoint and launch authorization.

The default-OFF `research_btc_split_planref_v1` flag requires split50 with .25% discount and the existing four-hour deadline. P0 is the exact quantity-weighted actual native VWAP of the completed first leg. Partial first-leg fills accumulate without freezing P0. Until first_quantity is confirmed, management uses actual current native entry VWAP. A mandatory close before completion retains that truthful basis and cancels remaining entry leaves. Once frozen, P0 never changes with second-leg fills.

Only V3 management uses P0: resting TP limit prices, conditional accepted-reduction checks, daily TP fallback, daily TRAIL return and best_f, and early-positive-TP split acceleration. The TP fractions, strict 3% TRAIL rule, accepted Q budgets, close priority and cancel-ACK executor remain unchanged. Early TP accelerates completion of remaining admitted Q on actual subsequent quotes; it does not fabricate a threshold fill. Freezing cannot rewrite an already-confirmed reduction or SOL right.

Native blended VWAP, exact cash, fees, funding and PnL remain actual. H remains `(original gross reference Q or original fallback Q) * actual aggregate entry VWAP / beta`; P0 never replaces its price. DP and other money-risk guards remain actual. No T3/H1/B1 change, shadow positions, future dates, target list or forced 105-parent schedule is introduced. Exact BTC permissions and total admitted volume are measured, not guaranteed.

Parent audits export P0, freeze timestamp, exact actual blended VWAP, actual H, gross reference Q and beta. The proposed focused native fixtures cover both sides, first-leg partials, immutable P0 versus changing actual VWAP/H, real confirmed reduction/right preservation, mandatory close before completion, early TP/ACK completion, default-OFF behavior and explicit candidate validation. Existing race/unknown-ACK/Q-conservation fixtures remain applicable.

Prepared patch: `btc-planref-v1-prepared.patch`; base and candidate SHA256 manifest: `btc-planref-v1-patch-base-hashes.json`. AST parsing and read-only git apply --check passed. Native test execution is intentionally deferred until applying the separate version after the five initial runs. No ROI improvement or 105-parent guarantee is claimed.
