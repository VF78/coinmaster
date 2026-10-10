# BTC and SOL risk-path audit of the winning control

Control TOTAL is 5,146,884.95718200 USDT; flags from frozen498a8fe are OFF. This is a read-only audit, not a third comparison. Source/report HEAD568e9dc, prior audited control native globalDD69.3409714%, conditional upper-to-lower bound70.4658144%. Prior SOLcap6 and portfolio45 each failed global50 while reducing TOTAL32.46% and34.08%. Objective remains maximum TOTAL among candidates whose global24-month DD≤50; global peaks never reset.

## New observed asset evidence

The 105 BTC and26 SOL completed flat-to-flat episodes reuse the existing confirmed-native-fill extractor. Episode path equals cumulative confirmed exit gross minus all incurred native entry/exit fees plus held native-PnL endpoints at paired prequote minute marks. Earlier partial TP profits remain included. Signed funding is unallocated/UNKNOWN. This is native observation attribution, not a new execution or money engine. The denominator is the FIRST HELD native snapshot’s portfolio equity, not exact entry decision equity; values are asset loss as a fraction of that equity, not asset-price returns or global drawdown.

| Asset | Winners / losers | Sum positive episode net | Sum negative episode net | Worst3 share of losses | Longest loss streak |
| --- | ---: | ---: | ---: | ---: | ---: |
| BTC | 57 / 48 | 15,343,446.42 | -10,796,001.94 | 29.4759% | 7 |
| SOL | 22 / 4 | 774,373.15 | -210,980.23 | 97.6623% | 1 |

BTC losses are spread across repeated episodes, not confined to three giant losses. SOL’s four losing episodes are concentrated, and none follows another SOL loser. Dollar totals across years depend on compounded exposure and are not risk-adjusted causal effects.

| Entry cohort / direction | Episodes / losers | Completed net, ex funding |
| --- | ---: | ---: |
| BTC FIRST12M BUY | 31 / 16 | -78,618.88 |
| BTC FIRST12M SELL | 26 / 9 | 604,688.94 |
| BTC SECOND12M BUY | 22 / 12 | -378,456.07 |
| BTC SECOND12M SELL | 26 / 11 | 4,399,830.49 |
| SOL FIRST12M BUY | 12 / 1 | 284,592.03 |
| SOL FIRST12M SELL | 9 / 2 | 128,971.36 |
| SOL SECOND12M BUY | 1 / 1 | -120,525.84 |
| SOL SECOND12M SELL | 4 / 0 | 270,355.36 |

Cohorts are assigned by episode entry: first12m2024-09-01→2025-09-01, second12m2025-09-01→2026-09-01. BUY=long, SELL=short. BTC long net is negative in both cohorts; short net is positive in both. This supports testing a directional sizing hypothesis, but direction profitability is observed in sample and does not prove future predictability. SOL second-year long evidence consists of ONE episode and cannot justify a broad long ban.

## Profitable trades can recover from large adversity

| Asset / episode | Adverse minute-close amount / first-held equity | Trough UTC | Final episode net | Maximum held notional / contemporaneous portfolio equity |
| --- | ---: | --- | ---: | ---: |
| BTC/67 | -938,636.66 / 51.6501% | 2025-11-28T14:28:00+00:00 | 324,162.34 | 17.2041× |
| BTC/72 | -881,052.78 / 34.3780% | 2026-02-08T23:08:00+00:00 | 401,672.73 | 12.4668× |
| SOL/1 | -5,360.44 / 56.9691% | 2024-10-03T15:44:00+00:00 | 2,201.95 | 24.0994× |
| SOL/3 | -11,787.17 / 28.7804% | 2024-11-23T04:42:00+00:00 | 35,244.13 | 13.9718× |

BTC Nov26 short began near7.93× and reached17.20× at adverse equity, without a corresponding new entry of that size. SOL Oct3 long’s first held snapshot was11.42×; its loss trough reached24.10× as portfolio equity fell. Both ultimately won. Admission size and loss-inflated effective exposure must be distinguished. Their conditional OHLC adverse loss fractions were52.5619% and58.1904%, respectively; these are possible perasset bar endpoints, not observed intrabar paths.

## Small descriptive screen

| Asset / minute-close loss budget | Losing episodes touched | Winning episodes touched | Touched losers’ final net | Touched winners’ full final net at risk |
| --- | ---: | ---: | ---: | ---: |
| BTC / 20% | 14/48 | 4/57 | -3,107,218.06 | 740,734.52 |
| BTC / 30% | 6/48 | 2/57 | -731,451.82 | 725,835.07 |
| BTC / 40% | 1/48 | 1/57 | -175,385.87 | 324,162.34 |
| SOL / 20% | 1/4 | 2/22 | -65,916.33 | 37,446.08 |
| SOL / 30% | 0/4 | 1/22 | 0.00 | 2,201.95 |
| SOL / 40% | 0/4 | 1/22 | 0.00 | 2,201.95 |

Thresholds touch an episode if its observed preclose path minimum reaches the threshold. These are descriptive, in-sample coverage counts. Touched loser net is NOT avoided loss; touched winner full final net is NOT future profit lost after a stop. Exact first crossing/future PnL after crossing was not retained in this bounded pass, so it remains UNKNOWN. Native stops would change commissions, execution, TP rights, subsequent positions and compounding. Conditional-OHLC screens are separately retained in threshold-screens.csv; they are not executable triggers.

First-held SOL gross exposure≥6× touched3 winners and0 losers (42,599.72 positive final net);≥9× touched2 winners and0 losers. This does not screen later adds and therefore cannot replace the completed aggregate-cap comparison. BTC≥6× touches22 losers and37 winners; its touched winner net7,466,438.87 shows the opportunity cost of indiscriminate size suppression.

| Entry-known prior-loss screen | Losers touched | Winners touched | Winners’ full final net at risk |
| --- | ---: | ---: | ---: |
| BTC after previous_1_completed_asset_episodes_losing | 25 | 23 | 6,089,479.10 |
| BTC after previous_2_completed_asset_episodes_losing | 14 | 11 | 2,713,440.51 |
| SOL after previous_1_completed_asset_episodes_losing | 0 | 4 | 273,456.47 |
| SOL after previous_2_completed_asset_episodes_losing | 0 | 0 | 0.00 |

The prior completed outcome is known before the next asset entry. The screen does not simulate skipped entries or delayed eligibility. A blanket SOL loser cooldown touches only profitable next episodes; a BTC cooldown also suppresses many profitable episodes. It is lower priority than a small directional size experiment.

Paired BTC/SOL held exposure exists69,107 prequote minutes. Native held-PnL signs oppose in49,110; both are negative in3,816. Combined held PnL is positive in41,147 and negative in27,960. This is descriptive offset evidence, not a hedge ratio or marginal contribution claim: daily beta, fill timing, realized TP cash and quantities differ. Opposite position directions alone do not ensure protection.

## Experiment ordering and acceptance

No candidate is implemented or run here. Test ONE independent native variant at a time against the reused exact control, keeping period2024-09-01→2026-09-01, seed10,000, data/quote policy/fees/funding and minute observer frozen. Rank completed variants by TOTAL only after global native DD≤50; conditional upper-to-lower risk bound must be reported separately. Measure seed minimum, globalTOP3/recovery, first/second year and long/short attribution, entry/exposure distribution, perasset realized/held loss paths, costs, actual liquidation and terminalflat. No Sharpe penalty, protective-epoch reset, or inferred skipped-trade ROI.

BTC first hypothesis: reduce long entry notional by20% using an opt-in long-only multiplier9.0→7.2, short multiplier unchanged. This is entry-known and targets the direction with negative net in both cohorts. Reference quantity/H and SOL budgets mechanically change when the parent reference changes; report that coupled consequence rather than claiming pure BTC isolation. Existing TP/right grants remain based on actual native fills. Accept only measured comparative economics; no guaranteed DD cap.

BTC second hypothesis: an opt-in20% asset episode loss budget using actual native realized gross/fees plus current native unrealized, referenced to actual native equity at first admitted BTC fill. Monitor paired minute marks, capture pre-exit risk first, and use existing native market_exit. Define exact post-exit next-episode eligibility before implementation. The descriptive14-loser/4-winner tradeoff is preferable to pretending all deep paths are losses. BTC third hypothesis, lower priority: reduce long admission only while the unchanged global portfolio peak is already20% underwater; do not reset global peaks. Its joint screen has NOT been measured here, so expected ROI/DD is UNKNOWN.

SOL first hypothesis: retain the profitable reference/H rights chain and apply a narrow native loss budget only to the SOL leg, with an explicit20% first-admitted-equity budget and existing native exit; one loser and two recovered winners were touched in the descriptive screen. This is a modest diagnostic candidate, not a confident improvement. SOL second hypothesis: shorten the existing hard timeout for adverse SOL exposure only, preserving adds/rights until the tested threshold. Exact adverse-duration joint coverage and final PnL after timeout are UNKNOWN in this pass and must be captured before picking a day threshold. SOL third hypothesis: condition a cap on global underwater state or unusually low entry beta rather than blanket6×; beta-at-decision was not archived with every closed asset episode, so its coverage is UNKNOWN and it ranks last.

The smallest follow-up set is one BTC long-size comparison first, followed only if necessary by one exact native BTC asset-budget comparison. SOL tests are secondary because BTC is the dominant repeated cash-loss source and its largest control/variant drawdown troughs are BTC-only. Frozen-source edge cases listed below require focused native correctness proof before any future execution changes; no archived-loss benefit is assigned to them.

## Data and causal limits

Minute-close native PnL is interpolated between actual native low/high position-PnL endpoints at native instrument-rounded close marks; prior attribution audit bounds native equity residual below0.01USDT. Conditional adverse perasset marks use the unfavorable OHLC endpoint with prequote exposure. No simultaneous BTC/SOL extrema or intrabar ordering is asserted. Prequote excludes same-timestamp closequote fills; actual terminal close/net is separately in completed episode outcome, not added as an intrabar sampled trough. A final exit fee can therefore make final net below the last held snapshot. Native funding is not assigned to either asset. Profit/outcome attribution is the existing confirmed-fill average/proportional fee method, not a venue’s pertrade settled PnL field.

Execution remains the original synthetic zero-spread size1000 Bybit1m-close quote model. Existing market_exit may execute against the previous cached book on cancellation acknowledgement; no screen predicts real stop fills. Zero modeled liquidation/maintenance breaches is conditional existing equity≤tierMM evidence, without an added liquidation fee reserve. No live viability or true synchronized-tick DD claim follows.

Reproducer analyze.py performs exactly one bounded control trace read; summarize.py reuses episode-paths.csv only. The committed compact JSON/CSVs preserve all131 episodes and exact Decimal values; large immutable traces are never committed. Source-flow evidence and check receipts accompany this report. Running episode profit-peak giveback was not captured: entry loss budgets do not screen giving back earlier profits or global portfolio high-water losses.

Temporal parent mapping (latest BTC entry before SOL first fill; domain UUID unarchived):

{
  "basis": "Latest native BTC entry before SOL episode first fill; inferred chronological parent, not archived immutable domain UUID; rights may persist after physical BTC flat. No causal skipped-parent ROI.",
  "by_BTC_side": {
    "SELL": {
      "SOL_episodes": 13,
      "SOL_net": "164066.1977073500000000000001",
      "SOL_net_parent_BTC_losing": "21857.32755045",
      "SOL_net_parent_BTC_winning": "142208.8701569000000000000001"
    },
    "BUY": {
      "SOL_episodes": 13,
      "SOL_net": "399326.7203886000000000000004",
      "SOL_net_parent_BTC_losing": "247379.4055000000000000000007",
      "SOL_net_parent_BTC_winning": "151947.3148885999999999999997"
    }
  }
}

BTC long parents supply SOL short rights whose completed net totals399,326.72; reducing those parents changes these profitable rights/budgets. Isolated negative BTC long net cannot justify deleting parent entries. This mapping is chronological evidence, not a coupled counterfactual return.

Full BTC/SOL causal chain and intended-rule / source-edge / model-limit classification are in [source-flow.md](source-flow.md). Two native scratch lifecycle probes reproduced potential late-ACK ordinary-close and cross-day half-completion edges; archived occurrence and economic impact remain UNMEASURED. These are correctness candidates separate from the demonstrated sizing/stop risks.

## Four SOL losing cases and hypothesis limits

| Episode / dates | Actual exit reasons / hours | Net | First-held exposure | Close MAE / first-held equity | MAE UTC |
| --- | --- | ---: | ---: | ---: | --- |
| 11 / 2025-03-27T00:03:00+00:00 → 2025-04-02T00:00:00+00:00 | {'TRAIL': 6} / 143.95h | -19,606.08 | 0.1700× | -39,949.75 / 4.9487% | 2025-03-31T00:46:00+00:00 |
| 19 / 2025-08-08T00:00:00+00:00 → 2025-08-15T00:00:00+00:00 | {'TRAIL': 7} / 168.00h | -65,916.33 | 0.2454× | -187,885.44 / 26.3745% | 2025-08-14T04:26:00+00:00 |
| 21 / 2025-08-23T00:23:00+00:00 → 2025-08-24T00:00:00+00:00 | {'REGIME': 1} / 23.62h | -4,931.99 | 0.2302× | -8,979.70 / 1.0361% | 2025-08-23T05:18:00+00:00 |
| 24 / 2026-05-20T00:00:00+00:00 → 2026-06-03T00:11:00+00:00 | {'SOL_HARD_TIMEOUT': 12} / 336.18h | -120,525.84 | 0.0115× | -137,335.78 / 1.8790% | 2026-06-02T23:26:00+00:00 |

MFE, first onset/duration of weakness and running profit-peak giveback were not captured; no new trace pass is justified to fill them here. Earlier timeout targets the actual 14-day losing timeout case, but earlier-date profit at risk is UNKNOWN. The7-day losing case can motivate a conditional adverse holding-age guard; it does not establish an optimal7-day cutoff. Other group-close losing cases implicate parent REGIME/TRAIL dependence, not existing fixed SOL SL. SOL20% is a testable budget example touching only one loser and two winners, not a recommended optimum. Low initial exposure does not prevent later fill accumulation; all add-time cap/beta/age screens remain unmeasured.

For BTC, an entry-known progressive size contract could reduce actual long admission after consecutive completed BTC losers (e.g0.8 after one,0.6 after two, floor0.6, restore after a completed positive episode), rather than skip trades. The causal prior-loss counts are measured, but these multiplier choices and joint long/weak-regime screen are NOT tested. Preserve actual fill-based rights and report the coupled SOL budget effect. Daily EMA-wave age/current z/beta are available at decision, but their joint loss-coverage was not archived in this pass; do not present them as proven predictive indicators.
