# Independent BTC/SOL forecasting — #113

Owner scope: evaluate STUMPY, MiniRocket, RDST and chart CNN separately from the trading strategy. Main horizon **24h**, predict **three TP levels from patterns**, not fixed-ladder probabilities. TRAIN **[2024-09-01,2026-04-01)**; CHECK **[2026-04-01,2026-10-21)**, i.e. through 20 October inclusive.

`protocol.json` is the frozen scientific/compute contract. The entry is an actionable side/time signal with a fixed next-minute reference execution rule, not a retrospectively chosen best entry. TP forecasts are contingent offsets, deterministically reanchored to that observed entry; reference-price displays are indicative. Labels retain zero excursions and ambiguous OHLC ordering. Full-horizon boundary purge and final-day censoring apply. These are forecast/touch statistics, **not ROI or executable fill guarantees**.

PRED-00 data/source inventory complete: true minute execution history for both assets is continuous through 20 October; genuine warmup verified. `inventory.json`, `tail-verification.json`, `warmup-verification.json`, `feasibility.md`. Primary sources and maintainer discussions are summarized in `sources.md`.

PRED-01 contract frozen; narrow target/validation review GO with timestamp/entry-based direction/censor clarifications incorporated. PRED-02 causal dataset/focused checks next; then bounded TRAIN selection, mandatory separate evaluations of all four families, sealed CHECK and independent verification. Existing raw helpers may be reused; old strategy-dependent labels/models are not reused. One sequential implementation owner; coordinator owns Project/current state.

Protected pilot remains active PID2009732/NRestarts0. No pilot/service/deploy/order/secret changes; S0 is not rerun. Old event-risk study and its unused four-native-run slots are closed historical scope, not budget for this new task.

Project readback: `project-start-readback.json` verifies existing [issue #113](https://github.com/VF78/coinmaster/issues/113) OPEN and Project #2 In Progress. Progress and results will replace this current section rather than create a parallel backlog.
