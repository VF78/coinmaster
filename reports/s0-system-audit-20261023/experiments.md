# Saved economic experiments audit — 23 October 2026

No saved valid candidate reaches DD≤50% while retaining≥90% of S0 net profit. Therefore none reaches the stricter DD30–50% band either. The most useful measured intervention is E4: it retains92.6573% with57.5854% settled-minute DD. It improves the trade-off materially but still exceeds50% by7.5854 percentage points. This is historical evidence, not a fresh validation or deployment recommendation.

Scope: saved reports and small existing comparison/episode tables only. No native engine, model training, new policy backtest, synthetic equity curve, large grid or new fit. Only the three assigned audit outputs are written. No source/pilot/service/GitHub changes. Evidence pins and full preserved source rows are in `experiments.json`; the comparable-path dominance calculation is in `experiment-frontier.csv`.

## Common yardstick and comparability

Exact saved S0: seed10000USDT; TOTAL6077107.23887483; net profit6067107.23887483; required TOTAL10000+0.9×profit=5470396.514987347. S0 settled-minute DD66.25691486468686414439256686%. ROI, terminal capital and retained net profit are different quantities. RESERVE0, TOTAL=ACTIVE in these experiments.

The modern native comparisons use [2024-09-01,2026-09-01), 1051200 source rows per asset and1051199 settled receipts; later studies pin dataSHA7ab5ae2cdaa14885da28d188c7ad14dfc8168ee600b78535f7317409ea94e9cc and policySHAc9540fbef259039c95829a774ef54e0eea2dcf2b6748d6455e171bf28e889834. Maker0.0002/taker0.00055 are fixed Bybit native fees, charged from actual liquidity side. They are supported by the actual maker/taker notional-fee buckets, not inferred from LIMIT/MARKET labels. Each new engine has separate funding accounting; signed funding aggregate and asset allocation remain UNKNOWN. The unallocated cash bridge is not a funding estimate.

The benchmark remains NOT_FAITHFUL_DIAGNOSTIC: native accounting with synthetic quotes from1m CLOSE; execution/L2/slippage/historical margin realism and live portability are not qualified. Settled-minute DD is not tick/intraminute worst-case DD. Original callback-marked DD66.3187802497%, cash-DD, conditional OHLC67.5477103187% and prefix lower bounds remain separate. The15-row frontier uses only full comparable global settled-minute DD. Earlier callback and older-base studies remain evidence about their own mechanisms and are excluded from that frontier.

Source references: `reports/b-50-90-next-20261023/REPORT.md`, `reports/s0-management-20261022/REPORT.md`, `reports/e4-sol-residual-20261023/REPORT.md`, `reports/e4-budget-tp3-20261023/REPORT.md`; exact row pins in JSON. All next tables report USDT and DD percent.

## Comparable complete settled-minute paths

|Recipe|TOTAL|S0 net profit retained|DD|Interpretation|
|---|---:|---:|---:|---|
|S0|6077107.23887483|100.0000%|66.2569|Immutable control|
|B / flags-OFF P0|4622034.27336437|76.0170%|57.5854|Reentry distance filter loses too much participation|
|E4|5631617.35953723|92.6573%|57.5854|Useful improvement, fails DD|
|EP|3992055.58641779|65.6335%|57.5854|Daily alternative worse than B|
|Z|2517706.78173418|41.3328%|60.2962|Zero-TP-leaf early reduction destructive|
|S|4155625.77863239|68.3295%|57.1470|Opposite-leg H1 SOL reduction; global peak migrates|
|E4+Z / XZ|4877453.55144460|80.2269%|60.2962|Does not preserve profit floor|
|E4+S / XS|5406345.11636863|88.9443%|58.9474|Fails floor by64051.398618717 and worse DD than E4|
|E4+Z+S / XZS|4696068.73175334|77.2373%|58.7195|Combination not additive|
|M1: DD25 crossing/50% losing-leg cut|2615745.21476479|42.9487%|58.7741|Permanent reduction sacrifices recovery|
|M2: DD25 crossing/75% cut|2044863.63091774|33.5393%|70.6446|Stronger cut worsens DD|
|Residual SOL R2C|2610652.32119763|42.8648%|61.7587|Local SOL protection, later BTC path worsens|
|E4 SOL budget|1360086.36695243|22.2526%|66.8590|Large tail/recovery cost|
|E4 BTC early20% at1% TP3|4120806.47444031|67.7556%|61.0797|Improves squeeze window, loses global trade-off|
|v2 C0 SOL-off|306.48185220|−0.1598%|97.5344|Valid model-liquidated negative|

Pure two-objective Pareto set: **S0, E4, S**. E4 dominates B,EP,Z,XZ,XS,XZS,M1,M2,R2C,SOL-budget,BTC-early,C0 on TOTAL/DD. S has slightly lower DD57.1470 than E4 but sacrifices1475991.58090484 terminal capital. No row has global settled DD≤50%. Among rows retaining≥90%, E4 has lowest DD. S0 has the greatest TOTAL. This frontier is conditional on these observed recipes; it is not the frontier of all strategies or an out-of-sample efficient frontier. Fee/turnover, other risks and economic dependence are not additional optimized objectives.

## Earlier native evidence, with its original observer/base preserved

The existing78-row `reports/s0-weekly-postmortem-20261022/weekly-inventory.csv` is retained in JSON, including invalid, partial, forecast-only and historical rows. Its SHA is pinned. Source metadata, period/control, changes, fees and status are preserved rather than silently replacing old controls with S0. Full-native economic rows use the same24m research interval, but V3/old-cap controls and policies differ. Rows below cannot be added to the settled frontier by relabelling their observer.

|Mechanism|Saved TOTAL|Saved DD / type|Validity and meaning|
|---|---:|---|---|
|BTC split50/50 at0.25% /0.50%, blended reference|4759384.60025755 /4379050.17052615|77.9382 /77.6497 callback|Valid V3 sibling paths; lose a BTC calendar entry|
|Split0.25% PLANREF|6005487.81325989|70.47 callback|Valid plan-preserving path; precedes S0|
|PLANREF+native TP IOC catchup|6077107.23887483|66.3188 callback|S0 economics; historical fresh repeat exact26/26; later reproduction exact. Repeat is not new recipe|
|Permanent SOL cover50/75/100|21765.86882504 /23826.61849406 /26111.23084821|56.4035 /55.3452 /54.3439 callback|Valid V3 siblings; original alpha replaced by cover|
|Conditional SOL2%/1%/50% final D83|3007648.74434437|67.6944 callback|Accepted with execution effects; two prior implementations excluded|
|SOL cap50|3314315.92576245|58.0163 callback|Accepted; held-trim branch unexercised, not evidence every branch works|
|DD/covariance /split-ATR|4046.59122751 /113562.54508323|70.5425 /93.9156 callback|Accepted; split-ATR has declared liquidation lockout|
|I25 /light /recovery /I33|8000.31240969 /7864.88334010 /7720.28353387 /2026.97093770|67.6021 /68.3009 /67.6178 /84.6402 callback|Accepted with native execution effects/telemetry limits; light/recovery do not rescue insurance|
|BTC-only reference|280748.52263020|64.07 callback|Accepted standalone ablation, not per-asset attribution of S0|
|Carry pair|205.42245876|99.85 callback|Economic negative with durable partial-audit qualification; not strongest full audit tier|
|H1 SOL confirmation /B1 BTC delay|190593.96574493 /1387384.71961010|62.5978 /64.6369 callback|Old V3 controls5437208.56951095; actual launch13Oct, outside18–22Oct week|
|B25|2394463.52298288|46.4850 callback; conditional OHLC59.4611|Old V3 cut plus future BTC sizing halved. Passes its own minuteDD50, retains only39.3015% of S0 profit arithmetically; not faithful S0 adaptation|
|Old V3 S10_15 /R2 /T3|1147671.51274638 /2248382.68295321 /466727.71769381|62.0303 /92.1277 /92.7807 callback|Old risk alternatives, not modern residualR2|

Execution improvements are useful measured mechanics: native TP-IOC adds71619.42561494 to PLANREF TOTAL while reducing callback DD≈70.47→66.32. These improvements already belong to S0 and cannot be credited again to a new intervention. Further stop/hedge/insurance families have no supported profit-preserving winner.

## Invalid, partial and forecast work stays out of economic claims

ALPHA A/B are OOM partials; C reached full feed but incomplete export. ALPHA terminal TOTAL/fees remain UNKNOWN; a saved prefixDD≥93.23% is already negative risk evidence, not full economics. Corrected corridor remains incomplete with prefixDD≥77.47%; terminal TOTAL/fees unknown. Do not compare their incomplete capital to S0 final capital or promote an OOM to a successful completed policy.

Conditional-SOL earlier TP3/IOC implementation outputs880.08050504/19158.84958217 are explicitly excluded implementation artifacts; a full feed does not validate the intended strategy. BTC earlyTP3 physical attempt2 is INVALID (post-run Decimal assertion plus incomplete gzip); a precision-only reporting fix with unchanged1e−24 guard led to a fresh corrected complete attempt3. Its money matching the failed attempt is not a successful fresh-repeat claim. SOL/BTC budget used3 physical attempts,2 valid economics, no combined/repeat run.

Residual P0 exactly reproduces XS; R1's strict domainquantity==0 predicate falsely rejected fractional dust despite nativeflat. Its money is a valid executed path but not a test of working H1 residual protection. No corrected historical H1 run exists. R2C corrects the predicate; full minute trace/fills/cash match R2, so correctness repair has zero observed incremental economics here. CountR2/R2C as one economic outcome, preserve both executions.

The v2 SOL-off C0 and six H4 configurations plus X are valid native negative economic results: C0 TOTAL306.48, H4 TOTAL316.85–540.33, X540.33, all model-liquidated. C0 has complete settled receipts. H4/X have28–32 missing settled receipts; reported DD95.65–97.10% is an observed lower bound, not complete settled risk. They are excluded from the complete-DD frontier, even though liquidation and observed DD already reject the goal. B4622034.27 is the surviving nonliquidated v2 recipe.

FAST-RND/H24/CatBoost/TS2Vec/CNN/context/flat/spatial/GPT/E1/D90/Astra use forecast, ranking, support or price-context objectives; none becomes an economic strategy because of a score. KronosB is resource-unassessed, not proven unskilled. No forecast score is mapped to ROI or counted as native economic run. TEMP_CAP_RESTORE, ADVERSE50 and saved DD25/adverse2% screens are diagnostic hypotheses, not alternative curves. No native TOTAL/DD can be assigned to them.

## Drawdown concentration, migration and recovery

Aggregated only already saved complete global excursion tables, using their uninterrupted high-water mark. Count episodes≥30%, count episodes≥50%, and whether recovered at period end; no curve reset or fill subtraction. Different recipes create different excursions, so counts do not identify isolated causal effects. These are descriptive serially dependent events, not independent trades/tests.

|Path|Episodes≥30%|Episodes≥50%|Unrecovered at end|Worst peak→trough; recovery|
|B|10|3|1|2024-10-03T04:01:00+00:00→2024-10-03T15:45:00+00:00; 2024-10-04T16:26:00+00:00|
|E4|7|3|1|2024-10-03T04:01:00+00:00→2024-10-03T15:45:00+00:00; 2024-10-04T16:26:00+00:00|
|EP|11|5|1|2024-10-03T04:01:00+00:00→2024-10-03T15:45:00+00:00; 2024-10-04T16:26:00+00:00|
|Z|9|3|1|2024-10-03T04:01:00+00:00→2024-10-03T15:45:00+00:00; 2024-10-04T16:31:00+00:00|
|S|11|5|1|2025-01-13T00:37:00+00:00→2025-01-13T14:37:00+00:00; 2025-01-14T14:42:00+00:00|
|XZ|6|2|1|2024-10-03T04:01:00+00:00→2024-10-03T15:45:00+00:00; 2024-10-04T16:31:00+00:00|
|XS|8|3|1|2025-01-13T00:37:00+00:00→2025-01-13T14:37:00+00:00; 2025-01-14T14:42:00+00:00|
|XZS|8|2|1|2025-01-13T00:37:00+00:00→2025-01-13T14:37:00+00:00; 2025-01-14T14:42:00+00:00|
|R2C|12|3|1|2026-07-06T13:40:00+00:00→2026-08-19T06:14:00+00:00; not recovered|
|budget SOL|12|4|1|2026-07-06T13:40:00+00:00→2026-08-19T06:14:00+00:00; not recovered|
|budget BTC_CORRECTED|9|3|1|2024-10-03T04:01:00+00:00→2024-10-03T15:45:00+00:00; 2024-10-04T16:30:00+00:00|

This reveals why improving a selected day is inadequate. B has three distinct≥50% excursions: October2024 dominated by SOLlong1000 against BTCshort0.94; November2025 BTC-only short squeeze54.6783%; July–August2026 realized-loss sequence50.4342%. The November B excursion recovers01Dec03:33 with no fills between peak and recovery. Its first later exit is TP3 at15:35, notTP1. Cutting that exposure necessarily alters a recovery path that historically worked; the complete policy must pay for the lost participation.

E4 shares B's worst October DD57.5854%. SOL H1 S reduces that local October excursion to52.5801% but global maximum becomes January SOL-only57.1470% (XS58.9474%). Original S excludes BTCflat by definition. R2C protects both selected local tails: October49.9363%, January49.4068%, yet global worst shifts to July6–August19 BTC-only61.7587%, not recovered by period end. January residual cycle fill-net is−22401.9375 against XS+4502.1215, difference−26904.059 excluding unallocated funding. Those are two actual cycles, not a removable future loss.

SOL budget improves fixed October57.5854→50.1322 and January51.4147→44.5333, but its global DD becomes66.8590 (summer), compared with E4 summer46.3347. BTC earlyTP3 improves fixed November54.7928→43.8691 but worsens October61.0797 and January54.2320. Neither targeted success satisfies global50/90. Local windowDD is never substituted for continuous globalDD.

M1 reduces early DD to46.59% but global worst moves to May–August2026 at58.7741%; M2 worsens initial maximum to70.6446%. Twelve of26 affected original S0 intervals were profitable. This is an important recovery-cost counterexample, not a causal sum of foregone winner profits.

## Sensitivity and useful versus destructive intervention

Evidence of instability is already available without another parameter scan. Trim50→75% changes retention42.9487→33.5393%, DD58.7741→70.6446%; more severe trimming is not a monotone risk improvement. Permanent cover50→75→100 improves its own callbackDD56.40→54.34 but terminal capital remains only21.8–26.1k. Insurance light/recovery and strongerI33 all fail economically. Timing matters: E4 closed4h reentry improves B by1009583.08617286 at identical worstDD, while the daily EP alternative loses629978.68694658 against B. A generic “confirmation is safer” claim is contradicted by the saved results.

Adding Z or S to E4 reduces TOTAL and worsens globalDD; combination effects cannot be added from standalone local gains. R2→R2C full-trace identity is code-correctness stability of one realized path, not evidence that the economic guard is robust. Residual SOL protection preserves337 BTC fill times/prices/reasons/liquidity against XS, but292 quantities change; SOL budget preserves337 BTC fill events against E4 but320 quantities change. This supports a capital-compounding channel rather than lost BTC signals. It does not isolate the counterfactual profit of one action.

Fee saving is not success: B saves353837.42091907 against S0 but loses1455072.96551046 TOTAL; M1 saves235272.46971692 but loses3461362.02411004. R2C saves185071.88705175 versus E4 but loses3020965.03833960. EarlyBTC saves58726.98623549 versus E4 but loses1510810.88509692. Capital lost in earlier recoveries changes subsequent quantities and relative leverage. No fee-sensitivity sweep, spread sensitivity or new leverage grid was run; robustness to alternative cost regimes remains unassessed.

## Saved interaction contrasts and remaining E4 budget

E4 exceeds the exact profit floor by **161220.844549883USDT**. Its remaining globalDD gap is **7.58541045962226379114466259pp** to50%, or27.58541045962226379114466259pp to30%. The headroom is observed terminal capital, not a budget that can be spent by subtracting selected losing fills from an unchanged curve. Adding XS costs225272.24316860 relative toE4, already more than the available headroom, and increasesDD by1.3620264245317086pp.

Two actual same-source/common-B2×2 contrasts are identifiable in `reports/b-50-90-next-20261023/comparison.csv`: native sourcebd04c9b, same data/fees/seed/execution, flagsOFP0=B exact. Let interaction be TOTAL(A+B)−TOTAL(A)−TOTAL(B)+TOTAL(base). This is an additive contrast of complete realized native policy outcomes on one history, with compounding included, not per-action PnL or a fitted coefficient with statistical uncertainty.

|FactorA|FactorB|B effect on baseB|B effect with E4|TOTAL interaction|
|---|---|---:|---:|---:|
|E4 reentry|Z zero-TP cut|−2104327.49163019|−754163.80809263|+1350163.68353756|
|E4 reentry|S H1 SOL cut|−466408.49473198|−225272.24316860|+241136.25156338|

The positive interactions mean combined losses are smaller than naive additive losses; neither combination is beneficial against E4, and neither passes50/90. “Independently useful parts add up” is therefore contradicted quantitatively. A full E4×Z×S factorial/three-way interaction is **NOT_IDENTIFIABLE**: the B+Z+S cell is absent; XZS alone does not fill it. Interactions of earlyTP3×SOLbudget are also NOT_IDENTIFIABLE because the combined run was gated out. No missing cell is synthesized.

The earlier V3 TOTAL5437208.56951095→S0 6077107.23887483 gain639898.66936388 is a measured path-level execution/reference lineage improvement. V3's callbackDD67.2863 and S0's callbackDD66.3188 can be compared as saved observer types, but multiple split/PLANREF/IOC changes intervene and controls differ; the whole gain is not identified as isolated IOC benefit. The narrower PLANREF→IOC difference71619.42561494 is the cleaner saved transition. Neither lineage contrast independently proves general robustness or the modern50/90 goal.

## Search degrees, reuse and statistical limits

Observed lower bounds, not a complete hidden-search count or formal effective statistical degrees of freedom:

- Existing weekly registry:78 total records,68 dated18–22Oct plus10 historical/unexecuted references;21 accepted completed native economic executions, including repeat/reproduction, reported as19 distinct recipes;2 full-feed invalid implementations separately excluded. H1/B1 launched13Oct. No confirmation of15–17Oct from those artifacts is not proof no external work occurred.
- Later v2:9 completed native configurations—C0, sixH4 configurations (threeEMA choices13/34/89 crossed with two scales0.5/1), B and X. These are not nine complete-DD observations; H4/X receipt gaps remain explicit. The11-run ceiling is not11 actual runs.
- B-follow-up:8 completed native executions—one flags-OFF control, E4, EP, Z, S, XZ, XS, XZS. E4 selected before combinations within that protocol; across the whole repeatedly viewed history the mechanism selection is adaptive. Original thresholds0.5ATR,0.25ATR/two-dayEP,40%DD/2%adverse/halfcut and H1/4h clocks are observable design degrees even when fixed before each bounded launch.
- Residual:4 executions P0,R1,R2,R2C; P0 is exactXS repeat, R1 has predicate defect, R2/R2C identical economic paths. Do not call this four independent successful policy trials or count the correction as another gain.
- Budget/earlyTP3:3 physical attempts,2 valid policy economics,1 invalid report attempt.35/55/ATR14 and20% at1% are additional fixed design choices. No combination or passing repeat occurred.

The listed degrees are observed policy/configuration alternatives and selection decisions. They are not a p-value correction factor: total informal hypotheses, source exploration and effective correlated trials are unknown. Repeating data, reproducing money exactly or splitting this already seen period differently does not create a fresh test set. No valid Sharpe/deflatedSharpe/PBO/bootstrap confidence is inferred from terminalTOTAL+maxDD tables. Full serial return paths, selection universe and untouched evaluation period would be necessary for such claims; even those require a clearly frozen economic rule.

Useful supported evidence is execution fidelity already built into S0 and timely E4 reentry preserving much of profit. Selected SOL cuts and earlyTP3 show real local tail control but destructive full-path trade-offs. The saved evidence supplies no demonstrated method meeting30–50% DD and≥90% retention, and no sufficient basis to promise a next threshold/model will do so. Any future claim must be a fixed native policy tested on genuinely subsequent data with full costs/complete equity; this audit authorizes no launch.
