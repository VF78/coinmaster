# R0 — ALPHA-CORRIDOR observed-held feasibility screen

**ACCOUNT-FINALITY CAVEAT — NOT SETTLED-BUDGET CERTIFICATION:** The R1 native fixture proved that a subclass post-SOL recorder callback can precede actual fill settlement. The archive therefore supplies 1,051,199 observed post-SOL phase samples, NOT certified finalized account checkpoints. Completed quote-recording phase does not mean settled native account. R0 E/H/C and feasibility counts remain mathematical screens on stored observations only, not finalized native-budget proof or candidate ROI. The archived native all-phase DD66.31878025% is unchanged and NOT recertified here. R1 must use a deferred native receipt after a proven later settlement boundary.

**R0 observed-held screening is complete; implementation approval is a separate decision with the warnings below.** The observed winner path contains broad infeasibility and meaningful interference with alpha. This is one scenario screen over existing evidence, not a backtest or a hypothetical account curve. Winner TOTAL6077107.23887483 and independent BTC-only TOTAL280748.52263020 remain unchanged.

## Data, accounting and solver semantics

**E_H:** Observed post-SOL phase E values only; archival account-finality is NOT certified. H=max(10000, earlier observed post-SOL E including the current observation); prequote/postBTC observations do not update this screen H. The recorder callback may precede actual fill settlement, so E/H/C do not prove finalized account-budget admissibility. The terminal prequote left-limit remains excluded. Legacy names completed_states, completed_H_max and H_completed refer to the recorded-phase calculation, not certified account settlement. The native all-phase DD remains a separate unchanged archival metric, not recertified.

**causality:** Previous90 paired completed Daily log returns. Sample covariance/variance; linear interpolation q95(abs BTC logreturn), q95(abs residual WITHOUT intercept), then expm1. Beta/a/u refresh only after a new paired Daily close, including SOL-only. Daily timestamps<=state timestamp; age<24h. Minute marks are aligned completed source closes, no future price.

**L_K:** L=a*abs(B+beta*s)+u*abs(s)+.00055*(abs(s-held)+abs(B)+abs(s)). Only future adjustment/remaining BTC/SOL exits are charged. The screen does not charge already booked fees/funding again; a stored sample can precede later fill settlement and is not a finalized account receipt. This is a conservative future-taker fee model under the existing fixed research rates, configured spread0 and one-minute execution delay. Actual next-minute prices/L2/slippage/liquidity and signed funding components are UNKNOWN, not known-zero costs.

**solver:** Nonnegative absolute SOL notional on original held-alpha/opposite-BTC side. Breakpoints0, abs held, abs B/beta; analytic segment intersections and tail root. Project observed-held alpha target onto feasible interval; test its adjacent native0.1SOL lot neighbors and recheck L<=C. No external optimizer/grid. With B=0 formula includes (a*beta+u)*abs(s), so SOL-only is screened. Flat has no alpha permission and keeps s=0.

**rights:** Observed accepted native alpha inventory is the reference target only. Fresh prospective s_alpha, permission consumption/retirement, pending SOL leaves and remaining BTC Q2 are not fully exported: prospective policy screening is DATA_UNKNOWN for those inputs. This report does not invent full future ladders or claim a true-policy target.

**margin:** Native free cash/IM/MM are not proof of tier-based incremental SOL capacity. Mathematical HEDGE_ADD states are SOL_MARGIN_UNAVAILABLE until real tier/pending/Q2 admission checks. SOL_MARGIN_INSUFFICIENT cannot be measured from these exports and is NOT asserted zero. Reductions/hold need no incremental position margin but venue executability is not certified. The unconstrained min-L best effort may need added margin; reduce-only min-L is recorded separately and does not certify the contract optimum within actual available margin.

**turnover:** Counts are contemporaneous baseline timestamps, not independent actions. Contiguous adjustment spells and classification runs are descriptive. First-spell gap sums, gap-notional-minute area and projected-quantity total variation are unexecuted diagnostics, not candidate turnover/orders/fees/PnL. Candidate inventory, release confirmation/hysteresis and fresh rights would alter future E/H and targets.

**counterexamples:** All three >50% native excursions and eleven saved loss-flip clusters are retrospective labels used only for report slices, never runtime filters. Carry dates are evaluated on the WINNER state at the same time, not on the rejected carry candidate inventory.

**execution_precision:** Native construction proof supplied by source owner: SOL size step0.1/tick0.01/IM0.05, BTC step0.001/tick0.1/IM0.025; no explicit native min_quantity/min_notional. Fee multiplier1, maker0.00020/taker0.00055, Bybit USDT. Tier module and pending admission are still required. Raw source close precision and native lot rounding are distinguished.

| Check | Value |
|---|---|
| trace_rows | 3153600 |
| completed_states | 1051199 |
| aligned_marks_each | 1051200 |
| terminal_leftlimit_excluded | 1 |
| native_global_DD_reproduced_percent | 66.31878024969151 |
| challenge_estimate_max_difference | 0.0 |
| source_native_mark_max_difference | 0.0 |
| single_trace_pass | True |
| causal_valid_daily90 | True |
| BTC_never_changed | True |
| safe_held_never_changed | True |

## Coverage and early warning
| Classification | Baseline minutes | % observed post-SOL samples |
|---|---|---|
| FLAT_NO_ACTION | 456527 | 43.429170 |
| BTC_ONLY_SAFE | 289826 | 27.570993 |
| HEDGE_ADD | 26855 | 2.554702 |
| SOL_RISK_INFEASIBLE | 107444 | 10.221090 |
| LOT_INFEASIBLE | 1 | 0.000095 |
| ALPHA_TRIM | 43925 | 4.178562 |
| SAFE_ALPHA_HELD | 126621 | 12.045388 |

| Exposure state | Total minutes | FLAT_NO_ACTION | BTC_ONLY_SAFE | HEDGE_ADD | SOL_RISK_INFEASIBLE | LOT_INFEASIBLE | ALPHA_TRIM | SAFE_ALPHA_HELD |
|---|---|---|---|---|---|---|---|---|
| flat | 474550 | 456527 | 0 | 0 | 18023 | 0 | 0 | 0 |
| BTC_only | 375247 | 0 | 289826 | 21510 | 63910 | 1 | 0 | 0 |
| both | 68179 | 0 | 0 | 5345 | 16256 | 0 | 6889 | 39689 |
| SOL_only | 133223 | 0 | 0 | 0 | 9255 | 0 | 37036 | 86932 |

Observed held alpha: 201402 minutes; 126621 safe, 74781 not already safe (37.130217%). The latter contains trim, additional protection and infeasible cases, not executed orders. Of107444 model-infeasible states,18023 are flat after the account has already fallen below0.55H; zero exposure cannot repair a past account loss. Occupied infeasible states89421.

First occupied BTC checkpoints (105): {'BTC_ONLY_SAFE': 90, 'SOL_RISK_INFEASIBLE': 13, 'HEDGE_ADD': 2}. First60-minute occupied windows (6300): {'BTC_ONLY_SAFE': 4899, 'SOL_RISK_INFEASIBLE': 999, 'HEDGE_ADD': 246, 'SAFE_ALPHA_HELD': 156}. Independently excluding all future fees, first-checkpoint feasibility is Counter({'FEASIBLE_BEFORE_COSTS': 92, 'RISK_INFEASIBLE_EVEN_BEFORE_COSTS': 13}). This no-cost lower bound is computed only for the saved105 first checkpoints, not invented for every baseline minute.

### Earliest states by classification
| Class | UTC | Kind | E | H observed phase | C | B | Held SOL notional | L held | Min L with costs | Min L before costs | Proposed SOL qty | Margin |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FLAT_NO_ACTION | 2024-09-01T00:01:00Z | flat | 10000.000000 | 10000.000000 | 4500.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | NO_INCREMENTAL_MARGIN_FOR_REDUCE_OR_HOLD |
| BTC_ONLY_SAFE | 2024-09-02T00:01:00Z | BTC_only | 9987.232751 | 10000.000000 | 4487.232751 | -22638.943100 | 0.000000 | 1356.601118 | 1079.947543 | 1047.910442 | 0.000000 | NO_INCREMENTAL_MARGIN_FOR_REDUCE_OR_HOLD |
| HEDGE_ADD | 2024-09-02T23:01:00Z | BTC_only | 8387.598854 | 10161.005312 | 2799.045932 | -46986.586500 | 0.000000 | 2815.593268 | 2241.405371 | 2174.913130 | 7.900000 | SOL_MARGIN_UNAVAILABLE |
| SOL_RISK_INFEASIBLE | 2024-09-16T02:13:00Z | BTC_only | 10842.273253 | 13426.674321 | 3457.602376 | 71140.206120 | 0.000000 | 4262.958865 | 3496.422643 | 3393.154238 | -449.131286 | SOL_MARGIN_UNAVAILABLE |
| LOT_INFEASIBLE | 2024-10-02T07:59:00Z | BTC_only | 9085.849207 | 13426.674321 | 1701.178331 | -44695.437720 | 0.000000 | 2678.299977 | 1701.000521 | 1636.367173 | 246.317384 | SOL_MARGIN_UNAVAILABLE |
| ALPHA_TRIM | 2024-10-03T00:01:00Z | both | 10010.188070 | 13426.674321 | 2625.517194 | -43901.912000 | 113785.488000 | 10727.708519 | 1723.154406 | 1636.426336 | 314.900000 | NO_INCREMENTAL_MARGIN_FOR_REDUCE_OR_HOLD |
| SAFE_ALPHA_HELD | 2024-11-24T12:44:00Z | SOL_only | 50147.262882 | 50147.262882 | 22566.268297 | 0.000000 | -241325.175000 | 22199.523622 | 132.728846 | 0.000000 | -997.500000 | NO_INCREMENTAL_MARGIN_FOR_REDUCE_OR_HOLD |

The first model-infeasible state is 2024-09-16T02:13:00Z: C=3457.602376, min L with future fees=3496.422643, while the before-fee lower bound is 3393.154238. Therefore this first exclusion is cost-sensitive; it must not be presented as an impossibility theorem independent of execution assumptions. Later negative-C states are already budget breaches even with zero future costs.

The sole lot-infeasible snapshot has a real-valued corridor but no0.1SOL quantity inside it. Its continuous target is deliberately not labelled an executable native target.

## All24 months
| Month | States | FLAT_NO_ACTION | BTC_ONLY_SAFE | HEDGE_ADD | SOL_RISK_INFEASIBLE | LOT_INFEASIBLE | ALPHA_TRIM | SAFE_ALPHA_HELD |
|---|---|---|---|---|---|---|---|---|
| 2024-09 | 43200 | 27791 | 11071 | 956 | 3382 | 0 | 0 | 0 |
| 2024-10 | 44640 | 20253 | 18207 | 1666 | 1816 | 1 | 2697 | 0 |
| 2024-11 | 43200 | 21370 | 16070 | 0 | 0 | 0 | 5520 | 240 |
| 2024-12 | 44640 | 26123 | 8900 | 19 | 754 | 0 | 6472 | 2372 |
| 2025-01 | 44640 | 10473 | 24068 | 19 | 0 | 0 | 2880 | 7200 |
| 2025-02 | 40320 | 15751 | 5891 | 0 | 7836 | 0 | 29 | 10813 |
| 2025-03 | 44640 | 15913 | 14303 | 4 | 37 | 0 | 0 | 14383 |
| 2025-04 | 43200 | 2883 | 37 | 1197 | 26757 | 0 | 0 | 12326 |
| 2025-05 | 44640 | 4260 | 0 | 4191 | 16644 | 0 | 18098 | 1447 |
| 2025-06 | 43200 | 3123 | 0 | 2629 | 37448 | 0 | 0 | 0 |
| 2025-07 | 44640 | 17543 | 3636 | 6436 | 2625 | 0 | 0 | 14400 |
| 2025-08 | 44640 | 17288 | 10759 | 535 | 559 | 0 | 2626 | 12873 |
| 2025-09 | 43200 | 11907 | 15454 | 0 | 0 | 0 | 5603 | 10236 |
| 2025-10 | 44640 | 10618 | 21024 | 789 | 689 | 0 | 0 | 11520 |
| 2025-11 | 43200 | 33499 | 3546 | 9 | 6146 | 0 | 0 | 0 |
| 2025-12 | 44640 | 43201 | 1407 | 17 | 15 | 0 | 0 | 0 |
| 2026-01 | 44640 | 16480 | 28158 | 2 | 0 | 0 | 0 | 0 |
| 2026-02 | 40320 | 31816 | 4179 | 3590 | 735 | 0 | 0 | 0 |
| 2026-03 | 44640 | 24356 | 17401 | 2883 | 0 | 0 | 0 | 0 |
| 2026-04 | 43200 | 29079 | 14121 | 0 | 0 | 0 | 0 | 0 |
| 2026-05 | 44640 | 16045 | 11315 | 0 | 0 | 0 | 0 | 17280 |
| 2026-06 | 43200 | 38870 | 1439 | 0 | 0 | 0 | 0 | 2891 |
| 2026-07 | 44640 | 4330 | 33110 | 0 | 0 | 0 | 0 | 7200 |
| 2026-08 | 44639 | 13555 | 25730 | 1913 | 2001 | 0 | 0 | 1440 |

## Every native excursion exceeding50%

### Native excursion 37 — 66.31878024969152066570091116%

| Point | Native UTC | Native equity |
|---|---|---|
| peak | 2024-09-11T14:00:00+00:00 | 13451.3363251 |
| first_underwater | 2024-09-11T14:00:00+00:00 | 13410.3412791 |
| trough | 2024-10-03T15:44:00+00:00 | 4530.57414701 |
| recovery | 2024-10-11T02:53:00+00:00 | 13453.62745342 |

R0 observed post-SOL sample at those timestamps (different phase/H from original native extrema):
| Tags | UTC | Kind | Class | E | H | C | L held | Min L |
|---|---|---|---|---|---|---|---|---|
| DD37/peak,DD37/first_underwater | 2024-09-11T14:00:00Z | flat | FLAT_NO_ACTION | 13410.341279 | 13410.341279 | 6034.653576 | 0.000000 | 0.000000 |
| DD37/trough | 2024-10-03T15:44:00Z | both | SOL_RISK_INFEASIBLE | 4530.574147 | 13426.674321 | -2854.096730 | 10067.340397 | 1708.241330 |
| DD37/recovery | 2024-10-11T02:53:00Z | SOL_only | ALPHA_TRIM | 13453.627453 | 13453.627453 | 6054.132354 | 14353.213402 | 69.059725 |

### Native excursion 776 — 59.84272354367395947974450388%

| Point | Native UTC | Native equity |
|---|---|---|
| peak | 2025-04-11T01:00:00+00:00 | 915175.73025689 |
| first_underwater | 2025-04-11T01:01:00+00:00 | 911531.10825689 |
| trough | 2025-06-06T15:17:00+00:00 | 367509.64806046 |
| recovery | 2025-08-24T19:38:00+00:00 | 930699.83942448 |

R0 observed post-SOL sample at those timestamps (different phase/H from original native extrema):
| Tags | UTC | Kind | Class | E | H | C | L held | Min L |
|---|---|---|---|---|---|---|---|---|
| DD776/peak | 2025-04-11T01:00:00Z | both | SAFE_ALPHA_HELD | 915175.730257 | 915175.730257 | 411829.078616 | 241394.884188 | 173149.194515 |
| DD776/first_underwater | 2025-04-11T01:01:00Z | both | SAFE_ALPHA_HELD | 911531.108257 | 915175.730257 | 408184.456616 | 241621.142696 | 173311.376204 |
| DD776/trough | 2025-06-06T15:17:00Z | BTC_only | SOL_RISK_INFEASIBLE | 367509.648060 | 915175.730257 | -135837.003581 | 188542.643323 | 92225.452656 |
| DD776/recovery | 2025-08-24T19:38:00Z | BTC_only | BTC_ONLY_SAFE | 893334.182544 | 915175.730257 | 389987.530903 | 84988.542683 | 70769.913445 |

### Native excursion 943 — 55.10055575073671291811943329%

| Point | Native UTC | Native equity |
|---|---|---|
| peak | 2025-10-22T21:29:00+00:00 | 2088471.56378771 |
| first_underwater | 2025-10-22T21:30:00+00:00 | 2082398.66648771 |
| trough | 2025-11-28T14:28:00+00:00 | 937712.12544458 |
| recovery | 2025-12-01T04:10:00+00:00 | 2089614.53857348 |

R0 observed post-SOL sample at those timestamps (different phase/H from original native extrema):
| Tags | UTC | Kind | Class | E | H | C | L held | Min L |
|---|---|---|---|---|---|---|---|---|
| DD943/peak | 2025-10-22T21:29:00Z | BTC_only | BTC_ONLY_SAFE | 2088471.563788 | 2088471.563788 | 939812.203704 | 576555.322516 | 343440.300218 |
| DD943/first_underwater | 2025-10-22T21:30:00Z | BTC_only | BTC_ONLY_SAFE | 2082398.666488 | 2088471.563788 | 933739.306404 | 576796.795132 | 343584.139715 |
| DD943/trough | 2025-11-28T14:28:00Z | BTC_only | SOL_RISK_INFEASIBLE | 937712.125445 | 2088471.563788 | -210947.234639 | 635853.063821 | 494068.656606 |
| DD943/recovery | 2025-12-01T04:10:00Z | BTC_only | BTC_ONLY_SAFE | 2089614.538573 | 2089614.538573 | 940326.542358 | 589434.169482 | 456913.500162 |

## Eleven original loss-flip clusters
| ID | Entry range | Observed states | Class counts | Minimum C | First violation UTC |
|---|---|---|---|---|---|
| 1 | 3–4 | 5759 | {'BTC_ONLY_SAFE': 2909, 'HEDGE_ADD': 905, 'SOL_RISK_INFEASIBLE': 1943, 'FLAT_NO_ACTION': 2} | -384.762553 | 2024-09-15T23:10:00Z |
| 2 | 6–7 | 11520 | {'BTC_ONLY_SAFE': 6853, 'HEDGE_ADD': 1591, 'SOL_RISK_INFEASIBLE': 1816, 'LOT_INFEASIBLE': 1, 'ALPHA_TRIM': 1257, 'FLAT_NO_ACTION': 2} | -2854.096730 | 2024-10-02T00:29:00Z |
| 3 | 35–39 | 10080 | {'BTC_ONLY_SAFE': 35, 'SAFE_ALPHA_HELD': 808, 'HEDGE_ADD': 1197, 'SOL_RISK_INFEASIBLE': 8037, 'FLAT_NO_ACTION': 3} | -105991.462240 | 2025-04-11T09:54:00Z |
| 4 | 42–43 | 18720 | {'HEDGE_ADD': 4191, 'SOL_RISK_INFEASIBLE': 14529} | -135837.003581 | 2025-05-25T00:01:00Z |
| 5 | 45–47 | 8640 | {'SOL_RISK_INFEASIBLE': 8640} | -68119.035341 | 2025-06-14T00:01:00Z |
| 6 | 50–52 | 7200 | {'BTC_ONLY_SAFE': 6654, 'FLAT_NO_ACTION': 3, 'HEDGE_ADD': 283, 'SOL_RISK_INFEASIBLE': 260} | 83908.077554 | 2025-08-06T14:57:00Z |
| 7 | 58–59 | 25920 | {'BTC_ONLY_SAFE': 10079, 'FLAT_NO_ACTION': 2, 'SAFE_ALPHA_HELD': 10236, 'ALPHA_TRIM': 5603} | 138411.984033 | 2025-09-17T22:38:00Z |
| 8 | 63–64 | 10080 | {'BTC_ONLY_SAFE': 9820, 'HEDGE_ADD': 257, 'SOL_RISK_INFEASIBLE': 1, 'FLAT_NO_ACTION': 2} | 182603.090228 | 2025-10-26T12:11:00Z |
| 9 | 80–82 | 4319 | {'BTC_ONLY_SAFE': 4316, 'FLAT_NO_ACTION': 3} | 1424433.980964 | NONE |
| 10 | 91–95 | 20160 | {'BTC_ONLY_SAFE': 20155, 'FLAT_NO_ACTION': 5} | 2524489.814391 | NONE |
| 11 | 97–103 | 34559 | {'BTC_ONLY_SAFE': 33074, 'FLAT_NO_ACTION': 7, 'HEDGE_ADD': 785, 'SOL_RISK_INFEASIBLE': 693} | 448977.696327 | 2026-08-10T16:54:00Z |

The ranges are copied from saved CHOP.descriptive11clusters_coverage and span first P0 to last actual BTC exit. They are retrospective descriptions; no new cluster discovery or future-labelled selection enters the solver.

## Carry counterexamples on matching winner timestamps
| UTC | Winner state | Class | E | C | L held | Target SOL qty |
|---|---|---|---|---|---|---|
| 2024-10-11T19:07:00Z | SOL_only | ALPHA_TRIM | 18281.519047 | 8226.683571 | 14906.737904 | 490.100000 |
| 2025-01-13T14:34:00Z | SOL_only | SAFE_ALPHA_HELD | 318278.979298 | 101282.757235 | 76433.746192 | 4000.000000 |
| 2025-01-13T14:36:00Z | SOL_only | SAFE_ALPHA_HELD | 305038.979298 | 88042.757235 | 74968.972571 | 4000.000000 |
| 2025-04-06T18:04:00Z | both | SAFE_ALPHA_HELD | 816616.531472 | 367477.439162 | 174850.584728 | 4000.000000 |
| 2025-04-06T18:07:00Z | SOL_only | SAFE_ALPHA_HELD | 818323.022961 | 368173.700276 | 72017.461789 | 4000.000000 |
| 2025-04-06T20:37:00Z | SOL_only | SAFE_ALPHA_HELD | 797283.022961 | 347133.700276 | 68601.049010 | 4000.000000 |
| 2025-04-06T20:38:00Z | SOL_only | SAFE_ALPHA_HELD | 801563.022961 | 351413.700276 | 69296.022712 | 4000.000000 |

Oct11 winner SOL-only is trimmed, whereas Jan13/Apr6 winner alpha remains safe at the specified times. These differences are expected: the carry candidate changed BTC calendar, cash cushion and alpha path. Its near-ruin states cannot be substituted for winner E/H or used to claim avoided losses.

## Turnover demand and action-frequency limits
| Diagnostic | Value |
|---|---|
| contiguous_adjustment_spells | 517 |
| first_spell_gap_notional_sum | 162116723.15035877 |
| inventory_gap_notional_minute_sum | 286751233647.36395 |
| proposed_quantity_total_variation_notional | 4177653843.118609 |
| classification_runs | 2102 |

517 contiguous nonzero-adjustment baseline spells and2102 classification runs are NOT517 real rebalances. The162116723.15USDT sum is the first inventory-gap notional of each observed spell, not executed turnover. The286751233647.36USDT-minute area repeats the same baseline gap; it is not a fee base. The4177653843.12 projected-quantity variation includes changing counterfactual requests against actual baseline holdings and is not a simulated candidate inventory path. Release hysteresis, fills, fresh alpha rights and pending leaves were not replayed.

## Gate and remaining blockers

- 107444 baseline timestamps are risk-infeasible under this scenario/cost model, including18023 flat observations already below floor; this is not a proof that intervention earlier would have failed.

- Observed alpha is not already safe in74781 of201402 held-alpha minutes; keeping original alpha signals does not prove keeping original economic advantage.

- 13 of105 first occupied BTC checkpoints are scenario-infeasible with future-taker costs; before-cost exclusion count is separately reported. BTC-preservation plus a hard45% scenario floor cannot always be fulfilled by SOL.

- Prospective alpha permissions, pending Q2/leaves, actual available tier margin and actual future execution are UNKNOWN. R0 mathematical feasibility is not R1 execution acceptance.

- No ROI/DD/fees or executed action count of ALPHA-CORRIDOR was generated. R1 must explicitly accept the best-effort/failure contract and alpha interference before implementation.

No DATA_UNKNOWN estimates/marks were encountered in the observed-held mathematics; prospective-rights/pending/margin/execution unknowns are separate. No claim of SOL_MARGIN_INSUFFICIENT count0, no hard DD guarantee, no new ROI, no source/config/service/pilot/swap changes.

## Files

r0-statistics.json contains exact snapshots, roots, native lots, min-L best-effort and reduce-only alternatives, pins and resource evidence. r0-daily.csv/r0-monthly.csv contain calendar time counts; r0-first-BTC-states.csv contains105 early checkpoints; r0-landmarks.csv and r0-11-clusters.csv contain required cases; r0-classification-runs.csv contains2102 runs; r0-analysis.py is the single-pass script. Only r0-* report files were written.

Control compressed trace SHA256 reused from the previously verified winner risk proof: f9b59944ac969f5441babdf2103637f7cd179c6d18971c7bf95c0e2c46e38a0b. No additional trace read. Classification runs2102 conserve1051199 observed post-SOL samples; occupied risk-infeasible proportion89421/576649=15.5070068621%.
