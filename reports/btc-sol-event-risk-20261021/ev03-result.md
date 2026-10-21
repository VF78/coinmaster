# EV-03: valid negative result — no economic run

Frozen recipe `eb21d1eea69b51847c81efb9a6736a24e80958c125190ad21af5fee0b7cb43e5`; pre-fit source/input/dependency manifest `82f225adf37b17525bddc92205ce8af6aec4aaee023ee639e2e603c84c0ba323`. Exactly one fixed BTC comparison completed, TRAIN50events/15components → CHECK80events/21components. CHECK belongs to this new event protocol, not the old generic FAST-RND V dataset.

| Method | Component-equal CHECK log loss | Brier | Improved CHECK quarters vs prior | Qualifies |
|---|---:|---:|---:|---|
| TRAIN constant | 0.630220456 | 0.219086943 | — | control |
| Fixed causal rule | 0.650978627 | 0.227871766 | 0/4 | NO |
| Small L2 logistic C0.1 | 0.720974983 | 0.248939316 | 1/4 | NO |
| STUMPY20h analogue | 0.707928969 | 0.252517555 | 0/4 | NO |

All three methods are worse than the constant on both primary log loss and Brier. None meets the frozen5% improvement, paired component-bootstrap confidence and chronology conditions. Rule qualifies independently only against prior; numeric/STUMPY were required to beat both controls. No method qualifies under either route. The simple rule high-risk flag bin estimated a lower TRAIN risk probability than its complement; no direction/threshold inversion was attempted after seeing this.

STUMPY used exactly the one close-only BTC1h20-window recipe;9/80 queries fell back to TRAIN prior because fewer than3 eligible independent neighbors were available. Zero invalid TRAIN/CHECK windows. No motif/timeframe/feature expansion, calibration, manual CHECK selection or fitting retry.

Execution: isolated existing research environment, UID994, private network, readonly package/dependencies,400MiB memory cap, swap0, one CPU/thread and low priority. Nine synthetic causal/statistical/STUMPY API checks PASS before real fit. Pre-fit hashes covered comparison source, recipe/freeze, event data, sufficiency/components, dependency lock/freeze and original panel; package bytes matched canonical files. One real logistic fit completed with exit0. Wall11.82seconds, peakRSS318,984,192bytes; initial synthetic preflight312,459,264bytes. All five recorded output hashes verified after collection. Full dispatch/exit/stdout and immutable package are retained.

Decision: `NO_ADDED_INFORMATION_STOP_NO_ECONOMIC_RUN`. H-SOL had already failed event support; H-BTC now fails the information gate. The combined variant is not admitted. All four native economic slots remain unused. No new U outcomes, engine, trading-source behavior, execution service, pilot, deploy or secret changes occurred. No economic policy implementation, temporal refits or early-TRAIN retrospective prediction are authorized by this negative result.

This rejects these fixed predictors on this S0 portfolio-risk task; it does not prove that all risk signals or BTC management actions lack value. Native risk is not action value, and exact BTC ordinary-branch reachability remains unknown in saved data. The cycle stops without a new ROI/DD claim. S0 remains TOTAL6,077,107.23887483 / settled native DD66.2569148647%; the DD≤50% /90%net-profit goal is unachieved.

Artifacts: `ev03-output/result.json` (full metrics, paired bootstrap and four-quarter scores), `check-predictions.csv`, `numeric-model.json`, `stumpy-matches.json`, `synthetic-checks.json`, `real-fit-started.json`; `ev03-input-source-manifest.json`, `ev03-comparison.log`, dispatch/exit receipts. Implementation added only report-local comparison/launcher scripts; no product source was edited. Coordinator owns final README, Project and budget status. No commit requested/performed by executor.
