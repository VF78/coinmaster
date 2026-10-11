# CM-113 V3 minute drawdown causes

V3 native TOTAL **5,437,208.56951095 USDT**, ROI **54,272.08569511%**, BTC long **5.5x** / short **7.875x** sizing, all original SOL/H rules. Native minute global maximum drawdown **67.28630645%**; no candidate result <=50% is established. This is read-only attribution of the completed frozen-source `a9cbb737a5239d10b9ffcb97d55f997917945263` run, not another economic engine, backtest, strategy change or deployment.

## Verified account and asset decomposition

Amounts below are changes from native peak to trough in USDT. Asset cash is **confirmed-native-fill weighted-entry gross attribution minus all actual fill fees in the window**, reusing `../audit/economics.csv` methodology. It is not authoritative native settled per-trade PnL. Asset unrealized change comes from native low/high position-PnL endpoints evaluated at native instrument-rounded close and reconciles account unrealized within one cent. Cash residual is explicitly unallocated; it is never called actual funding.

| Native excursion | DD | Equity fall | Native cash change | BTC fill net + unrealized change | SOL fill net + unrealized change | Cash residual |
|---|---:|---:|---:|---:|---:|---:|
| 2024-09-11 14:00 → 2024-10-03 15:44 UTC | 67.28630645% | -9,285.93279991 | -2,262.39739991 | -3,551.19117321 | -5,720.78767120 | -13.95395550 |
| 2025-04-11 01:00 → 2025-06-06 15:17 UTC | 62.25270099% | -666,682.11328618 | -511,857.09288618 | -724,328.87805389 | +57,519.11350000 | +127.65126771 |
| 2025-10-22 21:29 → 2025-11-28 14:28 UTC | 55.83357097% | -1,183,937.17527088 | +5,646.48192912 | -1,193,545.47113477 | 0 | +9,608.29586389 |

These are **all three distinct global-running-peak excursions above50%** in the full native interval curve. Recovery timestamps are October11 2024 03:24, September22 2025 06:01 and December1 2025 04:12 UTC. The JSON retains first25/35/45/50% crossings, peak/trough/recovery, positions, quantities, entry/mark prices, notional, gross-notional/equity, actual fill rows and completed episodes. Same-timestamp window bounds use phase order: prequote → BTC quote → SOL quote. The first peak precedes its BTC TP3 fill at the same timestamp; that fill belongs to the following decline window.

## Measured causes

**DD1 has two stages.** BTC-only weakness already crosses25%,35% and45% on September16–17, including BTC completed losses -3,021.7511 and -2,469.8975. Later October3 SOL long loses -5,657.792 unrealized at the trough while remaining BTC short gains +440.1516. At the peak-to-trough level SOL contributes -5,720.7877 after actual fees, about61.61% of the account decline; BTC contributes -3,551.1912, about38.24%. The trough holds short0.732 BTC, entry60,811.2/mark60,209.9, notional44,073.6468; long817.6 SOL, entry140.09/mark133.17, notional108,879.792. Native equity4,514.69512879 makes gross/equity **33.879x**, SOL alone **24.117x**. Opposite directions did not prevent SOL loss from overwhelming the BTC gain at this point. This is an observed exposure/relative-move outcome, not proof that every SOL hedge is harmful or a sizing implementation defect.

**DD2 is mainly accumulated BTC regime losses.** Native cash erosion is76.777% of the account fall. April11–18 has five consecutive completed BTC losing episodes: -341,870.7079, -79,902.6320, -57,659.6281, -40,820.5522 and -70,364.5541; later profits offset part of these before another May25–June6 episode loses -114,802.3449. All-window BTC realized gross attribution is -538,809.8660, fees30,403.99165389, unrealized change -155,115.0204. SOL contributes **+57,519.1135**, an observed offset, so blanket SOL reduction would remove a beneficial component in this window. At the trough only BTC short32.253 remains, entry101,444.8/mark105,225.6, unrealized -121,942.1424, notional3,393,841.2768/gross-equity8.395x. Maximum window prequote gross/equity10.0915x occurs April14 14:52. A stop which rearms/reset peaks after each flat can still accumulate these losses.

**DD3 is BTC short mark-to-market exposure.** Unrealized change -1,189,583.6572 is100.477% of the account fall; native cash actually rises5,646.4819. Confirmed fills have gross+33,242.2513 but37,204.0652 fees, net -3,961.8139; residual+9,608.2959 remains unallocated. SOL has zero position/fills throughout this window; there is no observed hedge to improve by reweighting. Trough short173.353 BTC, entry87,305.7/mark92,944.7, unrealized -977,537.567, notional16,112,242.5791/gross-equity17.204x. The retained short recovers along the original path by December1; an earlier reduction might protect DD but can remove later recovery and compounding. That tradeoff needs a native candidate measurement.

The30m BTC parent cap is not a drawdown stop; no evidence here attributes these three declines to a30m cap breach. Gross/equity is actual observed exposure relative to current marked equity, not the instrument's configured maximum leverage.

## Stops, losses and hedge limits

True fixed downside SL count **0**: BTC fixed stop, SOL z stop and portfolio loss limit are null; research deposit protection is disabled; native modeled liquidations0. BTC daily profit trail uses best daily entry return >3%, then a3 percentage point retrace from that best return. It is a daily profit-exit rule, not a3% capital-loss stop. REGIME closes are opposite daily EMA regime decisions and can close losing exposure. SOL follows the groupclose; its separate z exits/14day timeout remain original.

TRAIL has13 inferred BTC-parent/asset/reason closing cohorts:2 profitable BTC,11 SOL (9 positive/2 negative). The two negative SOL trail cohorts are April2 2025 -19,606.076 and August15 -65,916.3295, combined -85,522.4055 after allocated actual entry/exit fees, excluding unallocated funding. Trail net totals BTC+82,629.22653212 and SOL+109,011.25231740. These are closing cohorts, not thirteen fixed stop losses or thirteen portfolio reversals. SOL timeout is12 native closing fills in one episode, net -120,525.836. There are48 losing BTC remaining REGIME exits, net -10,156,895.78656537, which differ from whole-episode results including earlier TP reductions.

Completed-episode confirmed-fill attribution: BTC105 episodes/57 wins/48 losses, worst consecutive loss streak7; winning net14,686,324.31717213, losing net -9,993,079.51637838. SOL26 episodes/22 wins/4 losses, worst streak1; winning net904,236.34813860, losing net -215,912.2125. Full fill net5,381,568.93643235 plus unallocated native cash residual45,639.63307860 equals native cash gain5,427,208.56951095. All actual commissions total1,091,093.07886765. Signed funding remains `UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA`.

Observed opposite direction is not a beta-neutral guarantee. DD2 SOL offset and DD1 SOL loss are both real; no causal hedge-ablation result or historical synchronized-beta record is invented. DD3 is BTC-only. Admission-only gross caps cannot reduce already-held positions as equity erodes.

## Arithmetic and next comparisons

With each **original peak held unchanged**, reaching exactly50% requires the trough equity to improve by **2,385.61883556 / 131,217.70554523 / 123,699.44131017 USDT** respectively (25.6907%/19.6822%/10.4481% of each observed decline). This is arithmetic, not simulated avoided loss, terminal ROI or a promise that a given exit can achieve it. Fees, later fills, exposure, earned rights and compounded sizing change after interventions.

Prioritize a bounded V3 **held-BTC reduction plus stressed new-entry sizing** test with the unchanged global peak: all three excursions first cross25% with BTC loss; the original V4 reduces only future episodes and cannot cut the held exposure already losing. Separately test **SOL own-contribution loss protection/no-add lockout** for DD1 while retaining the original beneficial SOL path in DD2 where possible. A regime confirmation delay tests DD2's successive close/reentry losses; a minute evaluation of the daily-armed profit trail tests cadence, with recovery-profit loss a material risk. None is measured here. The exact proposed candidates, definitions, implementation gates and ordering are in `parameter-review.md/json`, maintained separately by the parameter reviewer. A persistent global guard/lockout is an additional control hypothesis when a hard50% target is required; local episode resets alone cannot bound cumulative DD.

## Evidence and reproduction

Raw result `/var/lib/coinmaster-native-gui/data/runs/jobs/cm113-sizing-v3-20261011/result/v0-selective-lifecycle-cap30m-btc-direction.json`, SHA256 `caa6b209142f4a005f8cd73ee00d030bd841c6a9669e98c971b15f93c36c902a`. Full trace and fills hashes are in `attribution.json`; report hashes in `attribution-SHA256SUMS`. Frozen source/data/policy and five-engine receipts are reused from `../sizing-dd50-comparison/`.

Run from canonical repository with existing read-only environment:

```sh
runtime/.venv/bin/python reports/selective-lifecycle-cap30m-113/v3-drawdown-causes/attribution.py
```

The script streams immutable observations, checkpoints before strict checks, then automatically finalizes confirmed-fill attribution. `attribution-finalize.py` can also finalize the cached report without rereading the trace. Two observer scans were executed for this package: first final group guard found the unhandled terminal phase prefix; the corrective scan includes boundary settlement accounting but excludes it from interval DD. No extra engine, qualification environment installation/copy or full test suite was run. Native account callback/cache finalization is asynchronous: quote-callback cash is unsuitable as perasset realized attribution. That rejected method is preserved in `attribution-rejected-callback-method.csv` explicitly tagged INVALID_PER_ASSET_ATTRIBUTION_CACHE_TIMING, and its2.83m unclassified timing residual is only a diagnostic. It is superseded by the confirmed-fill attribution above. Source/pilot/restart/deploy/config/secret state was not changed.

Native minute DD remains diagnostic with minute-close liquidation and no faithful BBO/L2/trade tape stop execution. Conditional OHLC upper-to-later-lower bound68.4920% is separate from observed close DD. Neither venue survival nor unchanged ROI under proposed interventions is established.
