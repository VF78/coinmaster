# Hedge sizing and sequential closing: native observation audit

The exact winning control remains TOTAL5,146,884.95718200 USDT, global minute native DD69.3409714%, conditional upper-to-lower OHLC bound70.4658144%. This extends the asset-risk audit without changing trading source or running a historical engine. Original selective/lifecycle fixes ON; only experimental SOLcap6/PORT45 OFF. SOLcap6 and portfolio45 already failed global50 with32.46%/34.08% TOTAL sacrifice. None of the hedge hypotheses below has a native comparative TOTAL or DD result.

## What the saved exposure actually looks like

| Paired-prequote state | Minutes |
| --- | ---: |
| BTC_ONLY | 374,672 |
| SOL_ONLY | 132,863 |
| BOTH | 69,107 |
| FLAT | 474,558 |

BTC/SOL overlap is 6.5741% of the24-month interval, 11.9844% of minutes with ANY position and 15.5724% of BTC-held minutes. All69,107 overlap minutes have opposite native directions: BTC short/SOL long23,905, BTC long/SOL short45,202. SOL-only132,863 minutes demonstrate that the strategy is often an independent residual overlay.

Time-weighted BTC/SOL gross dollar ratio: minimum0.3847, p101.7607, median16.9170, p9047.6789, maximum228.9486. These are observed exposure ratios, NOT optimal hedge weights. Current/entry beta was not archived in the minute trace and is UNKNOWN numerically. Beta-neutral dollar sizing needs SOLnotional≈BTCnotional/beta; quantity also divides by SOLprice. Neither opposite directions nor gross-dollar equality proves a hedge.

## Where the global TOP3 decline occurs

These are exact account-equity differences between consecutive native observer samples classified by unchanged native holding state. State changes are separate transition buckets. Funding/cash/fees remain in the native account change. BOTH is NOT SOL causal loss; BTC losses can dominate while a small SOL hedge is present. Shares can be negative when a state gains. All buckets reconcile to the original peak-to-trough decline.

| DD rank | BTC-only account decline | BOTH account decline | SOL-only account change | Transition account decline | Total decline |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 4,243.68 | 5,176.01 | 0.00 | 154.83 | 9,574.52 |
| 2 | 191,789.35 | 513,118.77 | 9,602.43 | 46,570.02 | 741,875.71 |
| 3 | 1,130,213.45 | 0.00 | 0.00 | 39,141.83 | 1,169,355.29 |

DD1 has54.06% of its decline during overlap and44.32% during BTC-only; DD2 has69.17% overlap and25.85% BTC-only, while SOL-only gains9,602.43. DD3 has ZERO overlap:96.65% of decline during BTC-only, the remainder transitions. Thus an admission-only SOL hedge cap cannot protect the recovered Nov2025 BTC-short drawdown when SOL is absent. Guaranteeing a50% global ceiling would need a separate global high-water risk budget or earlier hedge admission, not resetting episode peaks. Four successive20% losses produce59.04% cumulative loss; an asset20% loss rule is not a global50 cap.

Worst overlap equity is2024-10-03 15:44 UTC:4,233.36. BTC short gross41,303.99 with cumulative episode PnL+389.55; SOL long gross102,021.54 with cumulative−5,360.44. BTC/SOLratio0.4049. The original SOL trade later finished+2,201.95, so harmful adversity did not imply a losing final trade.

Worst combined active-episode overlap contribution is2025-04-12 20:44 UTC:−373,554.53, consisting BTC−394,742.66 and SOL+21,188.13, native equity723,491.15. BTC/SOLratio40.0464; small profitable SOL only partly offsets the much larger BTC loss. Worst-overlap samples in JSON may be adjacent observations of the same case, not three distinct independent episodes.

## Predetermined observable sequential-close screen

For each overlapping BTC/SOL completed asset-episode pair, select its FIRST paired-prequote minute where one cumulative asset episode contribution is positive after a prospective taker-exit-fee reserve and the other negative after that reserve. Contribution includes earlier confirmed partial TP gross minus ALL incurred native entry/exit fees plus current held native PnL. This is a causal profit split at that snapshot, NOT an EMA reversal. No future extrema select the trigger. Prospective reserve=remaining native quantity×rounded MARK close×control taker0.00055; it is not an executed book-price close. Remaining entry fees use the existing proportional native-fill allocation. Signed perasset funding remains UNKNOWN.

Thirteen pairs qualify:12 BTC cumulative winners/SOL losers,1 SOL winner/BTC loser. All13 initial winners also have positive CURRENT HELD PnL after remaining allocated entry fees and exit reserve; no cumulative-versus-held sign disagreements at these selected snapshots. The general possibility of a cumulative winner with a losing held remainder still exists. Exact first profit-crossing timestamp before the selected winning snapshot was not retained; only the first split and subsequent losing-leg fee-reserved break-even are observed.

All13 original losing cumulative legs subsequently reach held mark/taker-reserve break-even at least once. Times are minimum1minute, median12minutes, maximum595minutes. Only8 finish nonnegative at their original actual closes;5 finish negative. Eight cases have subsequent actual loser adds, so this is not evidence that static waiting always recovers. Complete actual future add/exit counts and reasons accompany each case. Maximum additional adversity BEFORE the first break-even was not separately captured and remains UNKNOWN; the following table measures through the original actual close instead.

| Original losing asset | Cases / unique episodes | Later original held fee-reserve break-even | Final nonnegative | New-add cases | Worst further mark adversity through actual close |
| --- | ---: | ---: | ---: | ---: | ---: |
| BTC | 1 / 1 | 1 | 0 | 0 | -394,177.33 |
| SOL | 12 / 12 | 12 | 8 | 8 | -188,591.07 |

The BTC-loser case begins2025-04-11 00:05 UTC: prospective-fee-reserved BTC contribution−3,511.02, SOL+56.16. BTC reaches proxy break-even at00:06, later reaches−397,688.35, and closes REGIME for−360,247.81; no further BTC adds. SOL Aug8 case reaches proxy break-even one minute later but adds six more SOL fills, reaches−188,693.82 and finally TRAIL−65,916.33. SOL May20 2026 case reaches proxy break-even73minutes later, adds11 more fills, later reaches−137,816.32 and closes at14-day timeout−120,525.84. Conditional adverse perasset endpoints are separately recorded; they are not synchronized joint intrabar paths.

At selected split times winning-leg cumulative mark/fee-reserved contribution sums687,894.25; those original winning episodes eventually net1,540,168.84, difference+852,274.59. This observed later evolution is NOT profit lost from an early close or a counterfactual ROI estimate. Closing the winner changes exposure, cash, fees, rights, funding and later sizing. At genuine EMA REGIME reversal both original legs close; there is NO native continuation of a retained loser after that event. Retaining it would override the original rule and require a new versioned experiment.

## Causal sizing alternatives and bounded native contracts

Current H uses original gross BTC reference×BTC entryVWAP/beta_entry; actual SOL multipliers1.75/2.625/3.5 and rights fractions apply even after BTC reductions. BTC multiplier7.875, TPfractions.2125/.2125/.575. Original H is intentionally not shrunk after TP. A fresh-equity budget caps capital use; a remaining-BTC/beta target caps estimated factor offset. They are different controls, and historical beta values were not manufactured for a numeric weight search.

1. **Lowest implementation scope: remaining-BTC admission target.** For each unused earned SOL right, clip its remaining original allowed budget to max(0,actual remaining BTC marked dollar notional / beta_entry − current aggregate held SOL marked dollar notional), using stored valid episode beta0.2<beta<4. Existing native lot normalization, mark/execution gap/fee reserve, margin/pending-opening ownership stay. BTC flat implies no additional SOL hedge target. Do not rebalance held positions, force exits, create earlier rights or change BTC exits. Record denied rights, actual fills/exposure, paired/unhedged DD and TOTAL. This may suppress profitable independent SOL adds; archived numeric coverage is UNKNOWN because beta was not saved. It cannot fix BTC-only DD by itself.
2. **Bounded partial winner harvest, a new explicit state transition.** At the specified current-fee-net profit split, use valid stored beta and signed factor E=sB*NB+beta*sS*NS. Close ONLY the profitable overweight factor leg if native-lot-rounded reduction lowers |E|; skip otherwise. Suggested candidate fraction≤min(50%,|E|/absolute winning-leg factor notional), preventing crossing past neutrality. Cancel/reconcile conflicting native TP/exit children; a new actual-fill reduction reason must update domain quantity without granting fake TP rights. Block adds/reopen in that waiting phase. Close both remaining native legs when the losing leg’s net contribution covers allocated entry/known exit fees, or after immutable24h TTL; original REGIME/TRAIL/SOL14-day timeout always has priority. A current global high-water loss limit is a separately specified safeguard, not an episode reset. Existing beta uncertainty/execution remains; this rule is untested and requires native partial/cancel/pending proof before any historical comparison.
3. **Full winner close / retained loser after actual REGIME: higher-risk separate override, not recommended first.** Fully dropping the winner can increase factor imbalance. The actual control supplies no losing-leg post-reversal path. Any research override must state explicit maximum TTL, native equity/global high-water loss budget, no adds or same-cycle reopen, actual pending settlement and final flatness. Never assume the loser eventually profits, or that realized winning cash increases already-marked equity. A blanket indefinite wait is not a viable risk contract.

Do not fit retrospective weights or launch these three together. Smallest follow-up is one remaining-BTC admission comparison; for the GLOBAL50 objective retain the earlier BTC20% asset-triggered GROUP-close comparison as more directly addressing unhedged short adversity. A partial harvest experiment is second-stage only after lifecycle correctness and exact beta/fee/TTL contracts are reviewed. Compare against reused control, same24months/seed10,000/inputs/fee/funding/quote policy; fresh native engine/journal only if separately authorized. Measure global native DD without resets, conditional upper-to-lower bound, seed minimum/TOP3, total/ROI/costs, asset rights/adds and native flatness. Maximize TOTAL among verified DD≤50; no Sharpe penalty or theoretical hedge efficiency replaces that acceptance criterion.

## Evidence, corrections and limits

hedge-risk.json/profit-split-cases.csv preserve native snapshots and all13 cases; global-DD-exposure-states.csv reconciles all native equity changes. analyze.py is one streaming existing trace observation; complete.py uses small saved native artifacts only. No historical engine, new money model, strategy/pilot/deploy change or huge trace commit. The original two asset-path diagnostic passes are reused, not rerun.

Current exact first-leg profit crossing before initial split and adversity strictly before first break-even are unknown. Fee-reserved break-even is cumulative original episode path, not guaranteed executable retained-leg settlement after a hypothetical harvest. Min-notional/lot/margin can prevent an actual partial exit; a reserve cannot guarantee fill size or price. The cached native dataset is synthetic zero-spread size1000 Bybit1m-close quotes with previous-book cancellation execution. Native close observations and conditional OHLC endpoints are separate; no actual joint intrabar drawdown or venue liquidation proof. General [cross-margin liquidation principles](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/liquidations) and [matching-model principles](https://nautilustrader.io/docs/latest/concepts/backtesting/fill-prices-and-matching/) do not certify the pinned replay or latest API equivalence.

[source-contract.md](source-contract.md) records exact beta/notional units, source lines and domain requirements. The earlier half-exit ambiguity is now resolved against original spec161 (half execution before a later daily decision), with root’s613ffa7 correction reused. Winner archived occurrence/economic impact remains unmeasured. The ordinary-close pending-ACK edge remains conditional native-fixture evidence with seeded ordering, not an attributed historical loss. No correction was implemented here.
