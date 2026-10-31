# E01 observed failure and bounded remediation

Original native E01 is retained FAIL, one physical attempt spent. Report SHA3b2a1216f7112ac911cfa5df2690e12086b5b1e9e2cc624b511c9366bfa30592. No native repeat was run by the author.

Two defects were observed. First, native1.231 OrderStatus.CANCELED.value=8 and str=8, so a name-substring check rejected actual5/300 canceled partial fill. Second, real long-parent progress stalled: SOL62.22 reduction left237.78 while BTC20 at1070 permits at most237.777... SOL at90. Another required.00222 reduction rounded tozero.118 staging callbacks occurred; long BTC40 ultimately stopped at950. The original fixture's one-harvest/reason-present predicates did not prove both-parent progress.

Correction: quantize the remaining guarded SOL target towardflat on exact native SOL step before calculating delta. The original case targets−237.77 and submits+62.23, then safely releases BTC20. Native min_notional10 applies even reduce-only in pinned risk/engine.pyx919–929. A pre-existing tiny guard overshoot therefore enlarges only the required reduction towardflat to legal minimum lots (example.12 at90=$10.8). Entire below-minimum residues HOLD explicitly; no native metadata, cap or tolerance is waived. Adapter records persistent minimum-blocked targets. Normal causal child capacity remains binding.

Strengthened native fixture requires both long and short actual profitable partials, confirmed SOL-before-BTC inventory safety, long harvest within3minutes, and no endless staging. A pure regression recreates E01 and rejects the old false-positive progress result. The enum-only derived validator explicitly leaves engineering NOT_ACCEPTED and reports liveness failure; it cannot erase the originalFAIL or spent attempt.

Pure verification47passed, engine0. Execution behavior changed and must receive focused review, a new immutable source pin, rootGO, and a separately counted E02. Actual native success remains UNKNOWN. No customer/account/live state was read or changed.
