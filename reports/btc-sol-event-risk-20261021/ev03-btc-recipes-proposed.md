# Proposed fixed EV-03 BTC recipes — NO FIT AUTHORIZATION

2026-10-21. BTC only; SOL failed EV-02 support. Freeze this proposal and exact input/code hashes before any fit. No additional feature/threshold/split search is proposed. Existing BTC50%-once-parent action and mandatory exit priority remain the eventual policy action; method comparison predicts S0 risk, not intervention value.

## Common events, features and weighting

Use exactly the 50 TRAIN / 80 CHECK eligible BTC event rows saved by EV-02 and its global cross-asset dependence blocks. No new labels or U inspection. Parent/overlap components are unchanged. Every event remains in predictions; weight each event as 1/(number of BTC events in its component), then normalize weights to mean1 for fitting; score each component equally. Do not use disjoint allocation as model row selection.

Use exactly six available causal native-state features: (1) native aggregate UPnL/W, (2) causal running native W drawdown, (3) log1p(parent age in completed seconds /86400), (4) native parent side ±1, (5) prior confirmed native BTC TP level count /3, (6) prior native SOL-present flag. Reject nonfinite/missing required features without substituting future domain state. No absolute quantity/cash/equity feature, calendar, price-level or parent-ID proxy. Native exposure/W would be useful, but avg-open was not retained in this event export; do not fabricate it from fills or add another native stream pass just for this proposal. Original exported quantities/cash remain audit facts, not model inputs. No unavailable z/beta/domain cache.

A class-probability clip `[1e-6,1−1e-6]` applies only for numerical scoring. All transforms and probability estimates use TRAIN only. No CHECK calibration or class weighting. Store every event ID, split, block ID, label and every prediction for reproducibility.

## Constant baseline and one simple causal rule

Constant: TRAIN block-weighted Laplace prevalence `(weighted_positive+1)/(total_weight+2)`, where one unit of effective weight per component is used for this prevalence. This is the forecast at every CHECK event.

Rule: risk-state flag = `native drawdown>=0.10 AND native UPnL/W<=0`. No threshold optimization. For probability comparison, estimate each of the two flag bins by the same block-weighted Laplace rule on TRAIN; an empty bin falls back to TRAIN constant. No extra rule family. Event eligibility and actual action threshold are distinct.

## One small numeric model

Six features above, TRAIN-only weighted StandardScaler then LogisticRegression L2 `C=0.1`, `solver=lbfgs`, `fit_intercept=True`, `max_iter=500`, `tol=1e-8`, `class_weight=None`, seed7, one process. Use component-normalized sample weights. One fit, no hyperparameter candidates, feature selection, refit retries or learned calibration. Failure to converge is STOP/report, not automatic increased iterations. Prediction is on actual CHECK event features.

## One STUMPY analogue variant

Only BTC1h last20 completed close values from existing pinned `runtime/var/research-datasets/fast-rnd-20261020-v1/panels.npz` (`p0_available_ns`, `p0_values` close column). Latest panel availability must be strictly before event decision; 20 contiguous1h bars required. Slice only pre-U feature history. Do not consume old direction labels, old fitted motif catalogs or old recognizer forecasts.

For each query, candidate catalogue contains only eligible TRAIN BTC events with mature72h labels before the query. Filter candidates by same parent side and same prior TP stage bucket (zero vs≥1); no further filter. Distance is STUMPY `mass(query20, candidate20, normalize=True)`, exactly one z-normalized close-only channel, window20; no other timeframes/threshold catalog. Constant/invalid windows are unavailable, never silently zero-distance. Select nearest5 distinct dependence components, at most one event per component (lowest distance, earliest timestamp tie break), no outcome selection. If fewer than3 independent candidates remain, return TRAIN prior. Otherwise probability `(sum(selected binary risks)+1)/(k+2)`. No motif search, distance threshold, neural expansion, new library or parameter grid. Record match IDs/distances and fallback counts. This is one analogue recipe, not 50 independent trials.

## Proposed predeclared information gate

Primary score: component-equal CHECK binary log loss. Secondary: component-equal Brier. Compute paired method-minus-control loss by the21 CHECK components, not80 IID events. Fixed bootstrap10000 component resamples, seed7, report95% percentile interval of paired mean differences. No bootstrap selection or refit.

Simple rule can qualify only if mean log loss improves at least5% versus constant and paired95% upper confidence bound is below0; Brier must not worsen. Numeric/STUMPY must meet those criteria against BOTH constant and simple rule. As a fixed chronology diagnostic, report CHECK quarters `[Apr8,Jul8)`, `[Jul8,Oct8)`, `[Oct8,Jan8)`, `[Jan8,Apr8)`; assign each entire CHECK dependence component to the quarter of its earliest CHECK event, and require improvement versus applicable controls in at least3of4 without selecting a quarter. Never split a component into independent quarter observations. Missing quarter support is reported as not-established, not replaced by another cut. These are conservative exploratory selection rules, not a claim of economic success or strong power from21 blocks.

If nobody qualifies, STOP BTC with no economic run. If multiple qualify, choose lowest primary log loss; ties within1e-6 prefer rule, then numeric, then STUMPY. Rule only competes against constant; a complex method cannot displace a qualifying rule without beating it. This chooses at most one BTC method. No automatic follow-up features/calibration/parameters. Economic threshold proposal: if the fixed rule is selected, act on its Boolean flag directly; if a learned numeric/analogue is selected and causally ready, act at probability>=0.5. No threshold sweep. Use a single50% BTC remainder action and unchanged safeguards; root must freeze policy before any engine.

## Economic temporal causality is a separate gate

TRAIN→CHECK comparison cannot authorize application of TRAIN-fitted weights backwards into2024/early2025. CHECK is development data after this comparison. No model is deployed or economic slot earned at EV-03 alone.

If information gate passes, propose exactly one prospective schedule for separate freeze: bootstrap with the deterministic Boolean risk flag through2025-04-08 (never TRAIN-fitted bin probabilities, prevalence or future calibrated weights), then expanding past-only artifacts at fixed quarterly cutoffs2025-04-08/Jul8/Oct8/2026-Jan8/Apr8/Jul8. Each artifact uses only fully matured72h labels from earlier historical S0 event windows and whole-parent/overlap blocks; if support fails at a cutoff, retain the causal rule fallback. The exact cutoff artifacts must be frozen before economic dispatch. They are prescribed temporal refits of the one selected recipe, not parameter search. Root must explicitly authorize these additional temporal fits and any U-derived training labels only after the appropriate freeze; current scope does NOT permit them. Without that authorization/evidence, learned24m economic evaluation stays blocked. A fixed rule needs no future learned weights, but remains subject to the economic policy freeze and native source review.

During an admitted economic run, compute features/inference from the variant’s actual current native cash/equity/positions, prior fills/TP state and causal market history. Never replay archived S0 predictions or frozen S0 quantities by timestamp on a changed compounding trajectory. Integrate only through the existing native BTC partial-reduction/helper path, preserving its order ownership and reconciliation; no additional executor or risk service. Native funding, order ownership, fees, fresh cache leaves and lifecycle locks remain authoritative. No alternative PnL ledger. New runtime-owned policy snapshots/money semantics need narrow independent review before any engine.

## Scope/resources

For EV-03 only, one small numeric fit and one bounded STUMPY comparison in existing isolated research environment `runtime/var/research-envs/fast-rnd-20261020`; no installations or runtime trading-venv changes. Pin this proposal, EV-02 output hashes, panel file hash, existing dependency lock and implementation before dispatch. Suggested cap400MB/one CPU/NUMBA_NUM_THREADS1; resource preflight must respect current pilot and disk/swap constraints. No economic engine, U, source behavior, deploy, pilot or service changes. Root approval required before fitting.
