# CM-113 BTC sizing / DD50 comparison

Five approved sequential native 24-month runs, frozen source `a9cbb737a5239d10b9ffcb97d55f997917945263`. Interval [2024-09-01,2026-09-01); seed 10,000 USDT, reserve zero. C fixes-only7.875; V1 fixed6.3; V2 fixed5.5; V3 long5.5/short7.875; V4 episode sizing hysteresis25/15%.

**Eligible winner: none.** Every native global minute DD exceeds50%. V3 has highest TOTAL; V4 has lowest native DD, still52.1271%, with conditional extrema bound61.1856%.

| Variant | TOTAL USDT | ROI % | Native minute DD % | Conditional bound % | Seed minimum | Fees | BTC/SOL fills |
|---|---:|---:|---:|---:|---:|---:|---:|
| C | 5146884.95718200 | 51368.8495718200 | 69.34097140401511909513176933 | 70.46581443662197363596957826 | 4233.3625743 | 1144089.96955003 | 311/191 |
| V1 | 3981070.44426903 | 39710.704442690300 | 58.03218094646642206312598555 | 60.16387742699453851103808370 | 5457.10253547 | 985481.62725904 | 311/215 |
| V2 | 3083826.38715455 | 30738.263871545500 | 54.90263646401992147639303061 | 63.07795443366038609071752251 | 6085.40393758 | 798777.32352185 | 311/203 |
| V3 | 5437208.56951095 | 54272.085695109500 | 67.28630644841043826206055609 | 68.49200984400826048214056614 | 4514.69512879 | 1091093.07886765 | 311/205 |
| V4 | 3112031.23119634 | 31020.312311963400 | 52.12706183581564820412531660 | 61.18563457104875053717491067 | 6896.13085648 | 793140.36430867 | 311/211 |

V3 gains290,323.61232895 USDT versus measured C but fails the risk constraint. V4 loses2,034,853.72598566 USDT versus C; it improves native DD but does not satisfy50% or establish an intrabar50% guarantee.

All five processed1,051,200 rows per source and3,153,600 observer rows; each strict-later extrema tracker has1,051,200 samples. Fees reconcile; zero liquidations and terminal flat. Per-run receipts/hashes, exact parameter differences, BTC/SOL actions/notionals/fees, maker/taker totals, funding counts, TOP3 peak/trough/recovery timestamps and V3/V4 sizing audits are in comparison.json. Full raw traces/logs/journals remain private job artifacts.

## TOP3 native minute drawdowns

C: 69.340971%, 65.738643%, 56.736537%
V1: 58.032181%, 54.402453%, 52.309404%
V2: 54.902636%, 51.683171%, 47.562577%
V3: 67.286306%, 62.252701%, 55.833571%
V4: 52.127062%, 50.056564%, 48.980495%

## Limitations

- All outputs remain NOT_FAITHFUL_DIAGNOSTIC and ranking_eligible=false; no live promotion or faithful exchange execution claim.
- C is a measured fixes-only baseline on the same frozen source. Its 502 native fill rows and 556 order rows match archived control exactly after excluding init_id only. Each V is compared against C; no extra control/repeat/refinement replay.
- Native marked minute DD, seed minimum and TOP3 preserve global peaks without resets and exclude post-boundary settlement quotes. Cash-DD is a separate account series and is not the eligibility metric.
- Conditional upper-to-strictly-later-lower bound uses prior completed-bar favorable equity versus later adverse equity for fixed prequote exposure. It assumes no same-bar extrema order and is not observed tick portfolio DD or a venue liquidation guarantee.
- V4 hysteresis sizes future genuine BTC episodes; multiplier/notional freeze before q0, without resizing held exposure or resetting the global peak. Normal7.875→reduced3.9375 at DD>=25%, normal return at DD<=15%. V3 long5.5/short7.875. Original gross SOL H and actual-fill earned-right behavior retained.
- All candidates keep approved SOL multipliers, BTC TP fractions, fee/funding policy, 30m cap, seed10000/reserve0 and existing three repair flags; BTC20, SOL hedge, SOLcap6, PORT45 and fee floor are OFF.
- Funding events are genuine native posts but signed funding remains UNKNOWN_NATIVE_AUDIT_HAS_POST_TOTAL_NOT_CASH_DELTA. Do not infer zero.
- Missing L2/trade tape, close-only execution proxy, historical fee applicability, native liquidation model and live recovery limits remain. No actual liquidations here does not prove venue survival.
- Exactly five sequential engines completed. Public venue metadata was included in each immutable allowlisted pack. Shared canonical venv/data were read-only bound, not copied. PilotPID2009732/NRestarts0/release81e6318 preserved; no credentials, real orders, service restarts or deploy.
