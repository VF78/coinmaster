# BTC-PATTERN-M2-20261021 — baseline and diagnosis (iteration in progress)

Owner requested continued quality improvement; the fixed first recipe below remains an immutable CONTROL BASE.
Status: baseline NO_SKILL / several direct heads WEAK_EVIDENCE; no confident PASS, no winner, no CHECK opening.
The economic goal is NOT_MET; no ROI/MaxDD claim follows from these forecast scores.

## Coverage and protocol

Bybit BTCUSDT linear perpetual; real contiguous minutes 2024-05-15 through 2026-10-21 00:00 UTC.
156 retained public REST pages supply 155,520 missing genuine minutes; old source checksum verified before reuse.
DEVELOPMENT 2024-06-01–2026-05-01; actual CHECK ends 2026-10-21 00:00. This historical CHECK was exposed by previous research.
20,928 valid hourly origins, 20,856 mature 72h labels, 72 censored. Entry is origin+60s minute open; maturity includes that minute.
All targets were recomputed: first-passage D, conservative/upper stop-conditioned MFE, 12D outcome signature, fixed H/SL summaries.
Separate entry-gap and current-close/entry minute pointers preserve fill versus existing-position semantics; entry is never X.
Three fixed purged expanding folds score 8,496 common mature origins, with 29 blocks for the 14-day paired bootstrap.
Zero D ambiguities occurred on these scored IDs; synthetic ties/gaps/censoring are tested. Bounds remain stored rather than invented tick order.
Nine focused causal/path/purge/metric/window/control tests passed; CPU/MPS shapes, gradients, parity and save/load passed on 128 true windows.

## What ran

18 joint neural fits (ES+fresh refit for TCN, frozen-Kronos projection, CNN across three folds), plus 18 CatBoost head fits.
Empirical prior, numerical kNN and context-matched random analogues use identical mature IDs and temporal exclusions.
Frozen Kronos uses separate genuine 64x4h and 64x1h token streams/context, no generated trajectories or backbone fine-tuning.
Every family, including CNN, completed every fold. No recipe changed after partial quality; no calibration or threshold tuning.
Mandatory auxiliary 4h-only CatBoost control completed another 18 head fits; it cannot independently promote a CHECK candidate.
DINO was excluded by the pre-quality resource/priority decision. Optional 15m, seeds, ablation, final/CHECK, native and SOL remain unadmitted.

## Forecast results (mean raw loss, projected Q)

| Method | D logloss | Q-long mean pinball | Q-short mean pinball |
|---|---:|---:|---:|
| prior | 1.093512 | .205775 | .256859 |
| CatBoost | 1.084878 | .210042 | .260594 |
| numeric kNN | 1.106193 | .208350 | .262235 |
| TCN direct / kNN | 1.100722 / 1.144479 | .205079 / .211843 | .259864 / .264977 |
| Kronos direct / kNN | 1.172799 / 1.258501 | .224744 / .229051 | .282782 / .283502 |
| CNN direct / kNN | 1.089753 / 1.105186 | .203798 / .207080 | .256738 / .262347 |

CNN direct Q-long improves all three folds, but paired delta versus prior −.001978 has CI [−.004953,+.001021]: WEAK_EVIDENCE.
CNN D delta −.003760 CI [−.044147,+.037689], Q-short −.000122 [−.006360,+.006186]: WEAK_EVIDENCE, no confident PASS.
TCN direct Q-long delta −.000696 CI [−.002567,+.001386] is weak; other learned retrieval heads show NO_SKILL.
CatBoost D improves the mean, but only one fold, so it fails the >=2/3 fold rule. No direct head or retrieval task passes its frozen gates.
4h-only versus 4h+1h CatBoost: D delta −.002067, Q-long +.000227, Q-short +.000940; all paired CIs cross zero.

## Localized failure mechanisms

Kronos overfits: refit D loss .814252 versus outer 1.172799; Q-long .180302 versus .224744. Frozen pretraining does not establish transfer skill.
TCN representation contracts: final-fold effective rank 1.92, mean variance 1.5e−5. CNN rank 4.57/variance 7.6e−5; useful geometry is limited.
Metric target entropy is near its uniform ceiling: TCN 4.744 versus log127=4.844; CNN 4.044 versus log63=4.143.
Low metric loss alone therefore does not prove learned analogues; direct CNN is better than its retrieval output.
Temporal label drift is material: F3 inner-stop NONE share 56.67% versus outer 34.58%; short q80 MFE 1.048 versus 1.411 sigma units.
F2 inner-stop DOWN share 43.17% versus outer 29.41%. A single 28-day ES segment can differ from the following four months.
No epoch cap was reached: TCN selected 5/7/2, Kronos 6/5/2, CNN 6/5/7; increasing the cap has no observed justification.
CNN has zero projected-zero TPs or raw quantile crossings on scored IDs, so those artifacts do not explain its weak evidence.
CNN long q20/q50/q80 empirical pre-stop hit rates are about 76.4/48.6/20.1%; short 79.7/47.3/20.8%, with negligible tie/ambiguity bounds.
Quantiles .2/.5/.8 target roughly 80/50/20% separate hit rates before the same stop, never an 80% probability of all three TPs.
These are forecast diagnostics; cost-valid executable TP/SL selection and portfolio performance have not been established.

## Resources, artifacts and next gate

Main run completed 20:20:54 UTC, about 34m44s after launch; sum of fit receipts 1,636.66s; process RSS peak 4,198,465,536 bytes.
TCN/CNN used measured-fast MPS; other stages CPU <=4 threads. One heavy job, default MPS watermark enabled, no CPU fallback or OOM.
Exact MPS peak is UNKNOWN; sampled allocation/driver data are labeled as samples. Existing environments and all old experiments were preserved.
Saved-model diagnostics took 33.37s with zero fits/CHECK use; exact 36-checkpoint/helper hashes were snapshotted before inference.
Models/index/caches remain in the new local job directory; manifests, forecasts, neighbors, per-q/month/regime metrics and fixed-ten-time examples are preserved.
P1 requires original S0 stop/horizon/native-state parity; P2 lacks demonstrated path skill; SOL and hedge claims remain blocked.
METRIC_OFF completed as the authorized full-history diagnostic below. RECENT180 was cancelled before launch; zero fits. Any next adaptation requires a new exact GO.
CHECK remains unopened and cannot select the adaptation. The original full-period S0 TOTAL/90%-net-profit goal is a separate reference.

## Full-history METRIC_OFF result

V1 completed all12 ES/refit neural fits across all3 fixed expanding folds in886.42s. All8,496 outer origins are paired to the original baseline and unchanged controls. Every task remains NO_SKILL; shortlist is empty. V2 RECENT180 never started.

| V1 head | D delta vs prior [14d CI] | Q-long delta [CI] | Q-short delta [CI] |
|---|---:|---:|---:|
| TCN direct | +.030603 [.002613,.057355] | +.003573 [-.000948,.007783] | +.011405 [.002432,.021475] |
| CNN direct | +.000100 [-.043600,.041670] | -.001891 [-.006347,.002241] | +.005260 [-.001351,.013177] |

Removing metric loss did not create transferable path skill. TCN direct Q-long and Q-short worsen versus its original baseline with paired CI above zero. CNN Q-long average is nearly unchanged but only1/3fold wins versus prior, down from3/3. All retrieval tasks fail the unchanged strong controls.

Training-curve embedding rank/variance are LOCAL128h probes on the first128 consecutive fit origins, not global collapse evidence. A separate no-fit probe uniformly sampled512 origins across each complete refit and outer period, with exact dates/N/checkpoint hashes in metric-off-fullhistory-geometry.csv. Baseline TCN outer ranks1.38/7.50/1.57 become3.88/8.15/4.50 with metric-off; CNN2.52/3.30/3.50 become2.10/2.94/2.82. Variance generally rises, yet forecasts do not improve. Geometry alone is not useful-path evidence, nor proof all representations collapsed.

CNN raw refit/ES/outer losses: D1.030649/1.040452/1.093108; Q-long.201736/.157661/.203699; Q-short.247536/.229049/.262196. TCN: D1.005901/1.053461/1.123935; Q-long.201236/.153900/.209183; Q-short.251600/.244894/.268386. These use raw comparable loss units; ES being easier than refit on Q also reflects target distribution, so outer-minus-ES is not a pure overfit estimate.

V1 epoch choices TCN4/3/1, CNN3/2/1; no30epoch cap reached. CNN F1 D optimum epoch1 versus Q7, selected3; F2 D2 versus Q6, selected2; F3 both1. F1/F2 Q minima improve only.00049/.00632 normalized Q loss from the joint-selected epoch. This local D/Q conflict exists but cannot explain the whole outer gap by itself. The single28dES has documented distribution shift and remains a plausible selection weakness; no alternate epoch was selected using outer outcomes.

CNN regime deltas versus prior (D,Q-long,Q-short), all CIs include zero: DOWN_HIGH N2342(-.032089,-.007248,+.012173); DOWN_LOW N2011(+.032347,+.002724,+.004776); UP_HIGH N1487(-.017122,-.004493,-.000419); UP_LOW N2656(+.013711,+.000797,+.002711). All rise/fall regimes remain included. This is heterogeneity, not permission to retain only a good regime.

Equal-fold V1 CNN q.2/.5/.8 pre-stop target hit rates: long77.2/51.7/23.5%, short81.4/50.4/25.5% (desired80/50/20). Tie bounds coincide on these IDs; projected zero inflation is absent; short raw crossing rate~.036%. Q predicts attainable MFE BEFORE a fixed SL. It does not learn an independently optimal SL or establish executable EV/ROI; actual first-touch/path summaries are required for stop-policy evaluation.

The existing toy positive/shuffle test exercises numeric kNN with an individual random label permutation, not a trained TCN/CNN or genuine block shuffle. A future recipe must include a small actual-trainable positive + genuine temporally block-shuffled synthetic diagnostic; synthetic fit success is not market OOS skill.

One full-history proposal, not authorization: retain original CNN architecture/metric.1 and all June1-origin history; test a single fixed three-anchor temporal ES aggregate (anchors full cutoff−90d,−45d,full cutoff; each preceding28d, purged earlier expanding subfit), then fresh full-prefix refit at the aggregate-selected epoch. Retain exact outer folds/targets/controls/gates. This addresses one short ES segment's temporal composition without cropping history or raising epoch cap. Exact aggregate criterion, source, trainable synthetic QA and worst-case cost must be frozen and reviewed before any fit. No new fit has been launched.
