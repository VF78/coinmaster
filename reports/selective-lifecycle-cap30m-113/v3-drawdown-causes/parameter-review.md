# V3 drawdown parameter review — read-only

V3 has the highest measured TOTAL among C/V1/V2/V3/V4: **5,437,208.56951095 USDT**, +5.64076% against C, but native global minute DD **67.2863064484%**. No measured candidate in this package meets 50%. Peak-to-trough losses span several episodes and held inventory; admission-only changes and episode-reset stops cannot establish a global limit. This review proposes tests, not measured improvements.

Frozen economic source `a9cbb737a5239d10b9ffcb97d55f997917945263`; analysis start HEAD `868104b`. Exact active config is copied into `parameter-review.json` from `sizing-dd50-comparison/comparison.json:variants.v3`. No historical engine, optimizer, trading source, pilot, deployment, credential or reserve change was performed.

## Measured comparisons

| Variant | Changed sizing | TOTAL USDT | Minute global DD % | TOTAL vs C % |
| --- | --- | ---: | ---: | ---: |
| C | 7.875 both | 5,146,884.96 | 69.34097 | +0.00000 |
| V1 | 6.3 both | 3,981,070.44 | 58.03218 | -22.65088 |
| V2 | 5.5 both | 3,083,826.39 | 54.90264 | -40.08363 |
| V3 | long5.5/short7.875 | 5,437,208.57 | 67.28631 | +5.64076 |
| V4 | future episodes7.875→3.9375 atDD25, resume15; held unchanged | 3,112,031.23 | 52.12706 | -39.53564 |

V1/V2 sacrificed 22.65%/40.08% TOTAL and still failed50%; V4 sacrificed39.54% and reached52.13%, with conditional upper-to-later-lower61.19%. Thus repeating uniform sizing or future-only V4 is poor first use of the next budget. Earlier experiments are different-source comparisons and do **not** isolate their mechanisms against V3: BTCepisode20 TOTAL3.806m/DD66.44; remaining-BTC SOL admission0.471m/DD72.31; SOLcap6 3.476m/DD63.13; resetting protective-epoch PORT45 3.393m/DD64.84. None is proposed identically again. Blanket hedge shrink has already destroyed much of the observed compounding.

V3 top3 native excursions are67.2863% (2024-09-11→2024-10-03),62.2527% (2025-04-11→2025-06-06),55.8336% (2025-10-22→2025-11-28). Minimum4514.69512879 is54.8530% below seed, a different metric. Full BTC/SOL loss attribution is owned by the companion report; fees are BTC1,072,814.89050625 and SOL18,278.18836140 (311/205 fills), which alone do not identify asset DD causation.

## Measured causes and resulting priorities

The companion native endpoint reconciliation reports the following rounded changes (not a new PnL engine):

| Excursion | Cash change | BTC uPnL change | SOL uPnL change | Implication |
| --- | ---: | ---: | ---: | --- |
| DD1 | −2,262.3974 | −1,365.7434 | −5,657.7920 | SOL held loss is the largest component; trough SOLlong loses5,657.792 while BTCshort is+440.1516. |
| DD2 | −511,857.0929 | −155,115.0204 | +290.0000 | Account cash loss dominates; held BTC also deteriorates. Cash includes realized/fees/funding residual, not automatically allBTC. |
| DD3 | +5,646.4819 | −1,189,583.6572 | 0 | Held BTC short causes deterioration; a SOL-only admission tweak cannot protect it. |

At DD1 trough gross/equity33.879x and SOLnotional/equity24.117x amplify mark losses despite valid prior admissions. BTC-only trough exposures at DD2/DD3 are8.395x/17.204x equity. B25 therefore screens first, S10/15 second, R2 third, T3 fourth: first DD25 crossings already involve losing BTC in all three excursions; SOL later deepens DD1. This ranking identifies risk channels, not predicted ROI.

At unchanged historical peaks, moving these troughs to50% would require2,385.6188/131,217.7055/123,699.4413 USDT higher equity. These are arithmetic benchmarks, NOT executable avoided losses: a rule changes peaks, quantities, fees, compounding and later paths. Only a future separately authorized native replay can price that tradeoff.

## Active parameter map

| Parameter | Active value | Drawdown mechanism and evidence | Priority |
| --- | --- | --- | --- |
| BTC regime/entry | EMA34; daily UTC completed bar; long if close>EMA else short; beta strictly (0.2,4); >=8 prior completed same-side waves | Regime reversal closes both legs, then a genuinely fresh episode may enter; no fixed losing-price stop. EMA changes trade sequence and SOL rights, not only risk. `domain:batch_features_for, completed_wave_levels, decide` | LOW: separate regime research only |
| BTC sizing | long5.5, short7.875 x marked ACTIVE; freeze at genuine episode creation; parent cap30,000,000 | Compounding and side exposure drive realized/uPnL; long reduction also changes gross BTC reference underlying H. Cap bounds parent, not held gross/equity under losses. `comparison.v3.config.research_btc_direction_sizing; domain:decide` | HIGH: held-exposure governor; do not repeat V1/V2 |
| BTC wave/TP | history730d, min8, quantiles0.10/0.30/0.60; include_zero_waves=true; fractions0.2125/0.2125/0.575 of initial quantity | Completed-wave MFE statistics are causal; changing quantiles/fractions changes residual exposure, profits and SOL earned rights simultaneously. Fractions total1. `domain:completed_wave_levels, plan_confirmed_btc_targets` | LOW: keep during targeted risk tests |
| Zero/deferred TP | execution repairs=true; selective lifecycle=true; deferred selective zeroTP=true; blanket zeroTP netting=false; fee floor=false | Zero allocation is omitted selectively; actual entry fill and causal deferred-price touch earn rights. Positive targets stay native/resting or existing taker fallback. Changing blanket netting had poor earlier economics. `strategy:_submit_intent; domain:on_fill` | UNCHANGED correctness/economic guardrail |
| BTC trailing/stop | 3% daily signed-price profit trail, only armed best_f>0.03; fixed close stop=null | At daily close f=side*(close/VWAP-1); best_f=max(best_f,f,0); close BOTH if f<=best_f-0.03. Cannot stop a never-profitable losing episode; daily cadence misses intervening adverse marks. `domain:decide` | MEDIUM: T3 evaluation-cadence hypothesis |
| SOL H sizing/direction | opposite BTC; H=(gross initial BTC reference qty*confirmed VWAP)/beta_entry; level multipliers1.75/2.625/3.5; proportional actual-filled rights | H deliberately uses full BTC reference, not remaining BTC. It can become large vs current ACTIVE after equity erosion and survive after BTC TP. Not an automatically balanced hedge. `domain:on_fill, decide` | HIGH: tail-loss budget; never silently change H |
| SOL eligibility | persistent after actual BTC level; late entry=true; overlay=true; retries only unused earned amount | SOL need not enter at BTC TP timestamp. Later adds can increase adverse inventory; resizing rights based on hindsight profitable outcome is prohibited. `domain:decide, on_fill` | HIGH: losses/add-lock in S10/15 |
| SOL beta/relative/z | beta270d rolling; relative65d; mean/std preceding180d; episode_fixed_beta=false; sigma frozen on first SOL fill | Current beta changes relative series; H beta_entry fixed. Frozen sigma plus rolling relative/mu can shift z through holding. New-invalid beta allows reductions only. `domain:FeatureState, decide` | LOW: 90/180 beta or unfrozen-sigma are separate untested ideas, not first four tests |
| SOL z entry/exit | entry signed z1.25/2.5/3.75; half<=0.375; full<=0.125 on a later decision AFTER actual half completion | Higher entry threshold delays exposure but need not lower tail losses. Exits are daily conditional and may be preempted by group close. Half/full not a loss stop. `domain:_sol_exits; selective lifecycle half completion` | LOW: keep during loss-budget test |
| SOL holding/timeout | 14 days from first SOL fill; sol_timeout_preempts_add=false in serialized schema | Actual frozen code always checks due timeout before adds: false is retained legacy schema, not operative bypass. Timeout closes only SOL, native retry completes remainder. A 5/10day change cannot protect same-day Oct3 loss. `domain:decide, _sol_exits; strategy:_begin_mandatory_sol_exit` | LOW: prolonged-loss hypothesis separately |
| Portfolio/risk research guards | portfolio_loss_limit_fraction=null; research PORT45/BTCepisode20/SOLcap6/remainingBTChedge/drawdownSizing=false; sol_z_stop=null; deposit protection disabled | No active global peak governor or held-loss budget. Prior PORT45 resets protective epochs while observer peak persists; V4 resizes only future BTC episodes. Neither proves global50. `comparison.v3.config; strategy:_research_check_portfolio_protection, _research_sample_btc_sizing` | HIGH: B25/S10_15; R2 for realized regime losses |
| Margin/admission/gross | BTC selected40x/SOL20x; max_gross_to_active50; fresh marks<=2min; prospective IM+MM, confirmed native reservation credit; insufficient margin=reject; futureSOLmargin0 | Admission gates protect proposed increases; held losses can raise gross/ACTIVE after admission. No future SOL earmark. Leverage tiers are assumptions, not leverage targets or historical venue safety proof. `strategy:_tier_allows_increase; native_baseline:729-778` | UNCHANGED: no tier/freshness/venue relaxation |
| Reserve/capital | seed10000; ACTIVE fraction1; reserve0; transfer fraction0; trigger4 inert; restart target initial seed; liquidation restart from reserve else pause | Reserve could reduce tradable compounding and alter ACTIVE vs TOTAL DD; cannot improve metric by moving bookkeeping/resetting peak. Not a first-line test when reserve is currently zero. `comparison.v3.config` | UNCHANGED in four tests; optional future real transfer test |
| Execution/fees/funding | Bybit genuine1m execution close and mark close; nonmatching1D signals; configured1min delay; resting maker reduction later quotes; maker0.00020/taker0.00055; spread0; native funding posts | Adapter delay expression (configured_minutes-1) makes default extra delay0; event order still controls next quote. Protective forced exits can match cached previous book on cancellation ACK: no guaranteed fresh-market stop price. Signed funding per asset is unknown, not zero. `native_baseline:781; comparison config.execution_policy; forced close lifecycle` | UNCHANGED assumptions; explicit fresh-quote protective submit proof required |
| Recovery/boundary | terminal native flat; terminal settlement in TOTAL, excluded interval minute DD; no reset global peak | Native order/fill lifecycle owns exposure. No source or engine migration, live rearm or venue recovery changes are authorized. `comparison.receipt.terminal_lifecycle` | UNCHANGED |

The source does not expose a fixed 3% losing stop: **3% is a daily profit trail, armed only after signed daily BTC profit exceeds3%**. SOL14days is an age exit, not mark-loss protection. `sol_timeout_preempts_add=false` is a retained schema field: frozen code checks due timeout before adds for every candidate. V3's candidate7.875 is overridden at genuine episode creation by long5.5/short7.875. These are semantic caveats, not newly demonstrated defects.

## Four orthogonal next hypotheses — all UNTESTED

All activate from causal paired native marks and actual native holdings. A protective reduction is never labeled TP and grants no invented SOL right. Quantities are native-lot rounded, partial exits use reconciled remainder, and cancellation/ACK/late-opening races remain owned until authoritative terminal state. These are proposed new opt-in rules, not currently callable existing flag combinations (existing research guards are mutually exclusive). The pinned1.231 native implementation would require explicit bounded approval and focused lifecycle proof before any replay.


### B25 — BTC-held exposure with global hysteresis

E is causal paired-mark native equity; P=max(seed10000,all already observed native minute-equity checkpoints), never reset; D=1-E/P; first BOTH D>=0.25 AND current BTC episode contribution C_B<0 per excursion (C_B=native BTC realized since genuine episode start INCLUDING fees + held BTCuPnL; signed funding remains separate unknown) reduce only currently held BTC to50% confirmed quantity, lot-rounded down; non-TP protective reason grants no SOL rights. Reconcile/cancel conflicting BTC TP leaves before submit.

Activate sizing latch only after BOTH conditions first hold. If BTC contribution is nonnegative during SOL-driven DD, do not cut BTC or activate half-sizing merely from globalDD. After the confirmed protective cut, new genuine BTC episodes use long2.75/short3.9375. Original SOL held exposure, H/reference, rights/multipliers/entry/z/timeout unchanged; no blanket hedge shrink or suppression of original SOL adds. None added in this individual attribution test.

Rearm: D<=0.15 clears sizing latch, only future episodes return long5.5/short7.875; no buy-back current episode; one held reduction per excursion, not repeated halving each minute.

Causality: DD3 entirelyBTCuPnL deterioration−1,189,583.6572 with SOL0; DD2BTCuPnL decline155115.0204 plus large accountcash decline. Isolate held-BTC risk that future-onlyV4 cannot resize, preserving originalSOL opportunities. V4 used7.875/3.9375 only future BTC episodes; BTC20 closed whole group from episode-entry loss. Risk: Even loss-qualified BTC reduction can leave original H/SOL overweight and worsen total risk; DD1 includes profitable BTC at trough, so pureglobal trigger alone would cut a useful hedge. Record condition/trigger times and contribution. A profit-positive BTC episode can still give back large profit without C_B<0, so this candidate does not cap that channel or promiseglobal50.

### S10_15 — SOL own-loss budget preserving original H until loss

For each contiguous SOL holding cycle fix E_S to native paired portfolio equity immediately after first confirmed SOL fill. L_S=-(native SOL realized since cycle start, including entry/exit fees, plus current SOLuPnL)/E_S. Funding remains separately unknown/residual. On first L_S>=0.10 halve held SOL quantity (lot-rounded down), then if L_S>=0.15 close the remaining SOL. If both thresholds cross together, close all once.

Cancel pending SOL increases and prohibit further SOL adds for remainder of same BTC episode after first threshold; BTC sizing/TP/held quantities unchanged. Held SOL ordinary z/timeouts and group exits retain priority. 15% own-loss close is per cycle, not a portfolio stop. Native partial/ACK/terminal ownership must supersede a pending half reduction safely.

Rearm: Only after native SOL flat AND a new genuine BTC episode; original1.75/2.625/3.5 H applies there. No within-episode repeated add-stop churn or revive consumed rights.

Causality: Targets SOL adverse tail without discarding all original large-H opportunities; explicit same-day mark risk before14day timeout. Not SOLcap6 or remainingBTChedge: unchanged admission H until realized/held SOL loss; no BTC group close from BTC20. Risk: Stops may discard recovered winners or useful hedge; measure episode loss/win crossings and BTC-only residual periods.

### R2 — two completed daily EMA34 closes confirm regime re-entry

Keep immediate original REGIME groupclose on first daily EMA34 reversal. Replacement entry requires TWO consecutive completed daily closes of same EMA34 side: reversal close counts1, second same-side close counts2; flip resets count1. Current causal features and wave levels determine new entry.

No increases while waiting; ordinary reductions remain available. Non-REGIME TP/TRAIL re-entry unchanged. None: re-entry/whipsaw test, not a held-exposure or global stop.

Rearm: Only fresh daily decision with count>=2 AND native groupflat/no unresolved opening orders; original V3 directional sizing/H; no intraday reopen.

Causality: Targets accumulated BTC realized regime losses without selecting losing direction from future outcome. Not uniform sizing, BTC20 or PORT45; one-day causal confirmation. Risk: Can miss profitable reversal starts and alter subsequent SOL rights/H; no <=50% guarantee.

### T3 — minute evaluation of daily-armed BTC profit trail

Retain original DAILY best_f and arm only when a completed daily close has best_f>0.03. Between daily decisions evaluate f_m=side*(causal BTCmark/VWAP-1) at paired minute marks; if f_m<=daily_best_f-0.03 group-close BOTH. No intraminute/future high used for best_f.

Close owns all pending orders/opening intents; no increase until native group-flat and a fresh daily decision. No losing-from-start stop added; existing REGIME/TRAIL/timeout/terminal priority retained.

Rearm: New genuine episode on next fresh daily decision after native group flat; no minute same-side reopen.

Causality: Tests ONLY evaluation cadence of existing daily-armed trail while keeping arm/high-water update daily. Potentially protects profitable BTC giveback, but cannot stop unarmed early loss. Not a parameter-only daily trail2% or BTCepisode20; no hindsight profitable leg selection. Risk: Group trail can close useful SOL, including after BTC has already fully taken profit; it is not a BTC-only exposure stop. More churn/fees and exit-price ordering must be reported.

## Screening and decision contract

Phase-aware attribution and first threshold crossings rank B25 first for the common early losing-BTC channel, S10/15 second for SOL aggravation of DD1, R2 third for regime cash-loss accumulation, and T3 fourth. T3 ranks later because unarmed losses remain. Four individual tests form the bounded proposed set; only if positive standalone measured effects show useful ROI/DD tradeoffs, consider ONE separately authorized combination. No grid. A40% immutable-global-peak groupclose with permanent interval pause is an analytical global-floor reference ONLY: an early stop destroys subsequent compounding, so not a proposed paid replay. Unlike PORT45, it would not reset protective peak or rearm after another losing episode.

For every approved future run report TOTAL and % loss versus V3, immutable global minute DD/TOP3/seed minimum, conditional OHLC bound separately, fee/funding residuals, pre-action and actual-fill equity/latency/overshoot, guard/rearm counts, asset episode effects and recovered-winner exits. Identify protective partials and overhedged SOL states. Highest measured terminal TOTAL subject to native minuteDD<=50 is the decision rule; no eligible winner means report failure, not reset peaks or substitute cash DD.

Unchanged guardrails: genuine same Bybit data/interval/seed10000/reserve0, all native fees/funding and margin/mark freshness, cap30m, positive TP rules/fractions, selective repair flags, full-reference H and frozen sigma unless specifically changed above, no live/pilot/source migration. Historical crossing counts cannot price a counterfactual: changed fills, compounding, rights and future decisions require a new separately authorized native replay.

No rule guarantees50% through gaps, latency, fees or intrabar paths. Native1m-close DD and conditional fixed-exposure OHLC envelope are distinct; latest Nautilus [bar execution guidance](https://nautilustrader.io/docs/latest/concepts/backtesting/bar-execution/) cannot establish observed intrabar ordering, and [advanced-order metadata](https://nautilustrader.io/docs/latest/concepts/orders/advanced/) does not guarantee venue contingency support. They are conceptual references, not pinned1.231 API migration authority. Existing forced-close machinery may match previous cached book on cancel ACK; any future protective test must prove causal current-mark trigger, retained pre-action sample and separately record the executable quote/latency. No new proven trading-code defect or historical causal ROI impact is claimed here.
