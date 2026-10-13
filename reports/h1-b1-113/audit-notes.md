# H1/B1 calibration and causal contract recommendation

2026-10-13; report-only audit, no engine/run/source/config/pilot action. Canonical research V3 source a9cbb737, TOTAL 5437208.56951095 USDT, native minute DD 67.2863064484%; retained job cm113-sizing-v3-20261011. Exactly one observer scan, 90.34 seconds; no custom economic engine or PnL simulation. Helper/results: calibration-mae.py, calibration-mae.json, calibration-mae-episodes.csv.

## MAE measured against actual BTC entry VWAP

MAE is each completed BTC episode's maximum adverse price excursion as a percentage of contemporaneous actual native entry VWAP, floored at zero. LONG uses (entry-price)/entry; SHORT uses (price-entry)/entry. The reported mean is the unweighted arithmetic mean of 105 episode maxima. This is not mean minute loss, capital DD, leveraged return or portfolio combined OHLC.

| Held-price metric / subset | n | Mean % | Median % | p75 % | p90 % | Max % |
|---|---:|---:|---:|---:|---:|---:|
| Minute close / ALL | 105 | 2.207088 | 1.864226 | 2.966293 | 5.027702 | 7.912802 |
| Minute close / LONG | 53 | 2.219141 | 1.864226 | 2.966293 | 5.045367 | 6.790726 |
| Minute close / SHORT | 52 | 2.194803 | 1.841460 | 2.767695 | 4.311859 | 7.912802 |
| Held BTC low/high / ALL | 105 | 2.255100 | 1.912681 | 2.977011 | 5.073007 | 7.934671 |
| Held BTC low/high / LONG | 53 | 2.269872 | 1.912681 | 2.977011 | 5.092762 | 6.827603 |
| Held BTC low/high / SHORT | 52 | 2.240043 | 1.887099 | 2.798257 | 4.412672 | 7.934671 |
| Minute close / fill-net wins | 57 | 1.520839 | 0.977945 | 2.027387 | 3.405879 | 7.749535 |
| Minute close / fill-net losses | 48 | 3.022008 | 2.572883 | 3.637299 | 5.382057 | 7.912802 |
| Held BTC low/high / fill-net wins | 57 | 1.573677 | 1.000817 | 2.084827 | 3.473681 | 7.768704 |
| Held BTC low/high / fill-net losses | 48 | 3.064289 | 2.627033 | 3.693584 | 5.416956 | 7.934671 |

Side-specific winner/loser subsets and exact values are in calibration-mae.json. Win/loss uses already cached confirmed-native-fill weighted-entry fee-net attribution excluding unknown signed funding. This is not an independently authoritative native settled per-trade PnL label; no new per-trade PnL calculation was performed.

Coverage: all 105 episodes completed, all 105 have both metrics; 105 actual BTC entry fills, no multiple-VWAP episodes. 3,153,600 observer rows, 1,051,200 input minutes per asset; 1,331,249 native held BTC close phase samples (same-minute duplication does not change maxima), 443,779 fully-held BTC OHLC minute samples. Exact saved closes are used; native executable price rounding remains separate. OHLC accepts only prequote held position with last actual BTC entry fill <= bar-open, including pre-closing-fill minute and excluding entry-minute prefill extremes/post-flat bars. Zero prequote violations of that guard were encountered. Entry-minute postquote close is valid and retained; its prior high/low is not. Single-asset highs/lows during held position do not require hypothetical cross-asset extrema synchronisation. Historical execution remains minute-close diagnostic, not faithful venue tick simulation.

## One fixed threshold

Recommend strict current entry-relative adversity **a > 0.025 (2.5%)**, same LONG/SHORT. Basis: ALL held-OHLC mean 2.2550998333674857% plus 0.2449001666325143 percentage-point rounded buffer. It also exceeds ALL close mean 2.2070877192965948%. Direction means differ only 0.029829pp, insufficient reason to introduce two parameters. Do not choose a percentile or outlier maximum: the median is 1.9127%, p90 5.0730%, maximum 7.9347%, so the mean contains a right tail and is descriptive rather than a safe-loss ceiling. Some eventual winners also exceeded 7.7% adverse movement; a hedge may remove profitable exposure or add costs. This does not promise ROI/DD improvement.

This is **in-sample calibration**, not out-of-sample proof. Frozen 2.5% is proposed before the two independent comparisons. No optimized grid, per-trade future maxima lookup, dynamic future-selected threshold or H1+B1 combination. Online a uses only current available BTC mark and actual native entry VWAP; full-trade maxima never enter decisions.

## Shared confirmation: catch the move causally

Recommend one shared price-action definition on a completed, received bar t: LONG iff Close[t] > High[t-1]; SHORT iff Close[t] < Low[t-1]. The prior bar must be completed; both comparisons strict. Missing/unwarmed bars fail closed. This confirms a local break/reversal; it does not prove a universal optimal trading pattern.

Former draft required the break AND Close[t] above/below EMA20[t]. EMA20 weights recent data more than SMA, but still delays entry/exit; requiring it can postpone a valid local reversal during a correction. Removing that conjunct is a design inference to match the owner's speed priority, not measured superiority. No EMA slope/crossover, four-hour conjunct, right-hand pivot/future bars or extra two-bar wait. [Fidelity EMA documentation](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/ema) describes EMA sensitivity and entry/exit delay. [TradingView repainting documentation](https://www.tradingview.com/pine-script-docs/concepts/repainting/) explains confirmed-bar gating; the actual implementation must obtain native bars and enforce timestamps independently of Pine.

Fresh means decisive bar close_ns strictly later than that stage's arming event, used upon receipt; never latch an old qualifying break. SOL uses 15m OR 1h, with earliest qualifying event and duplicate-boundary order suppression. BTC B1 uses 15m OR 1h. A short BTC daily candidate may wait above daily EMA until a fresh 15m or 1h downward break; **do not** require that hourly close also fall below daily EMA34. Daily EMA34 selects direction only. Immediate existing REGIME/mandatory exits are never delayed by confirmation.

## Accepted H1 two-stage ownership contract — owner override

H1 alone replaces the legacy SOL z/TP-right overlay with one protective cycle per BTC episode. One actual SOL native position/owner, no parallel alpha hedge, no synthetic TP rights. Existing valid positive bounded SOL-on-BTC beta, native margin and fresh quote admission checks apply; actual filled quantities, pending leaves and native ACK/cancel states are authoritative.

Stage 1: actual BTC held, no mandatory close, current adversity a>2.5%; arm the crossing and await fresh opposite-BTC SOL 15m OR 1h price-action confirmation. Recheck a>2.5% at submit. If it falls to <=2.5% before any hedge fill, disarm; a later crossing may rearm. Initial target is 50% actual remaining BTC marked notional / valid beta, rounded down with current executable SOL quote and native margin limits. Freeze the target; loss/equity change cannot enlarge it. Actual partial fills belong to one opening parent; unknown ACK blocks another. Frozen implementation uses one parent per stage: a terminal zero-fill stage1 attempt closes this protective cycle; it does not retry in the same episode. Any actual stage-1 fill establishes the protective cycle; stage1 actual cumulative SOL filled quantity is authoritative.

Stage 2: only after ANY actual BTC TP reduction fill strictly later than first actual stage-1 SOL fill, BTC still held, first opening parent terminal, and another fresh opposite-BTC SOL 15m OR 1h confirmation whose bar close timestamp is strictly later than that TP fill. A pre-first-hedge TP, ACK or TP price touch cannot qualify. The first qualifying TP may arrive while first SOL parent settles; eligibility remains owned, but no second parent submits before terminal proof. Stage2 adds exactly the completed stage1 ACTUAL SOL filled quantity, subject only to native execution/lot/margin admission constraints. Owner explicitly rejected a remaining-BTC coverage cap and BTC-partial-induced SOL trim. Do not recalculate stage2 from remaining BTC, frozen intended stage1 quantity, changed beta or price; actual stage1 quantity is the reference. No second adversity threshold recheck. One additional stage only; actual partials remain owned by that stage parent, cannot trigger another stage or repeat the full amount. A 15m/1h same-boundary signal cannot create duplicate parents.

Stage2 remains valid only while the protective cycle is open and actual BTC held. Full BTC flat, group/mandatory close, timeout or recovery cancels stage2 eligibility and owned leaves. A closed first cycle cannot be reopened. Late native fills remain owned and are closed; unknown ACK or pending leaves never imply flat. BTC PARTIAL reductions do not trim SOL; BTC FULL flat closes all protective SOL with priority.

Keep last agreed exits: immediate REGIME/TRAIL/portfolio/liquidation/terminal priority; BTC-flat closes SOL and settles all owned opening/TP leaves; normal recovery a<=1% AND fresh opposite-SOL 1h confirmation; existing 14-day maximum holding from first actual SOL fill. No early profit close solely because SOL is profitable; no same-episode protective reentry after unwind. Recovery/mandatory exits take priority over any same-event stage2 increase.

Rejected prior recommendation: proportional SOL trimming after BTC partial TP, second-stage aggregate cap at 100% remaining BTC/beta, and BTC-only 1h confirmation. These were audit proposals; the owner's accepted contract above overrides them. Equal second-stage SOL size can exceed coverage of the reduced BTC remainder; preserve that owner choice and report native economic results without silently substituting a cap.

## Accepted B1 standalone contract

Completed daily EMA34 selects candidate direction only after previous episode/owned orders fully resolved. Candidate does not issue immediate BTC entry. First fresh completed BTC 15m OR 1h price-action break in candidate direction, strictly after candidate arming, allows native entry with existing size/fees/margin/TP formulas anchored to actual fill VWAP. No current/hourly price same-side daily EMA gate, EMA20 conjunct, four-hour gate or separate sequential 15m-then-1h confirmation. At coincident 15m/1h closes only one entry intent may be submitted. A new daily event expires and rearms an unfilled candidate even if direction unchanged; unknown in-flight ACK blocks overlapping candidate orders. After genuine flat/reentry, arm anew and require a new qualifying bar. Mandatory closes keep immediate priority.

This accepted section incorporates the coordinator-transmitted owner override. This report supplies calibration and independently reviewable contract documentation; source, tests, Project state, commits/push and native comparison runs are outside this auditor's ownership.

## Native aggregation primary-source cross-check

[Nautilus data documentation](https://nautilustrader.io/docs/latest/concepts/data/) documents external, internal and composite bar sources. [Maintainer discussion #1557](https://github.com/nautechsystems/nautilus_trader/discussions/1557) describes higher-timeframe internal bars driven by finer input and explains completed-bar availability. [Native bar execution documentation](https://github.com/nautechsystems/nautilus_trader/blob/develop/docs/concepts/backtesting/bar-execution.md) requires initialization timestamp to represent completed-bar availability, and documents interval-boundary timer/data ordering. [Maintainer issue #4681](https://github.com/nautechsystems/nautilus_trader/issues/4681) identifies differences between interval membership, ts_event placement, ts_init and equal-timestamp processing across aggregation paths. These current upstream sources explain why configuration names alone are insufficient causal proof for the pinned local 1.231 path. Independent review must inspect actual pinned aggregation and callback order: closed interval, true available close timestamp, same-boundary daily arming exclusion, and first native BTC/SOL execution quote after decision. No API/version migration is implied; minute-close execution remains diagnostic rather than venue-faithful execution.

## Frozen implementation economic scope

Independent source review at 7360fd0652182c5503e2da3ed80f443e2aef504d confirms H1 protective SOL closure after full BTC flat retains the ordinary legacy BTC episode. Native fixture proves same episode identity, BTC/SOL quantities zero, and no new BTC entry intent on a subsequent same-direction daily decision. H1 changes SOL lifecycle only; existing REGIME/TRAIL continue to retire the BTC episode. No hidden same-quote BTC reentry is added. B1 changes BTC admission confirmation while legacy SOL candidate/rules remain intact. Native bar feeds do not execute OHLC: bar_execution=False, actual historical quote close remains execution source.

## Corrected native confirmation execution — 2026-10-14

Original7360fd0 samequote equality invalid under real pinned timer/data ordering; initial H1/B1 runs preserved invalid diagnostics. Accepted causal consumption is firstCURRENT traded-asset executablequote afteractual closedbarreceipt, recordednextquotesequence, close<=receipt<=quote and closeage<=60s. Never cached pre-receipt book or arbitrary stalequote. Strictbarclose>arm/realTP and all economic/nativeguards retained. New exact94e0e6c independentGO/proofs in review-routing-correction.{md,json};170 relevant tests pass73.79s. Supersedes oldroutingGO only, not measuredMAE/ownertradingcontract.
