# Earlier BTC loss controls: bounded metadata check

2026-10-20 analysis only. No archive/price replay/new engine; read concise existing reports and relevant current source branches.

## BTC20 was a full-group cash-loss exit, not 20% price adverse

Evidence: reports/selective-lifecycle-cap30m-113/risk-budget-hedge-comparison/README.md.

- Older control TOTAL5146884.95718200 / global native marked DD69.3409714040151%.
- A_btc20 TOTAL3806180.15651045 / DD66.4368805506004%; TOTAL -26.04885891% versus its own control.
- Trigger compares native BTC episode realized PnL including fees plus held BTC unrealized PnL with -20% of PORTFOLIO equity at first confirmed BTC fill.
- Applies across the episode, not only before TP1. Not a20% price stop or global20% HWM drawdown.
- Triggers forced full GROUP closure, including SOL; subsequent episode needs flat reconciliation and a later eligible decision.
-20 breaches,20 rearms,22 actual guard exit fills.
- Two shared native lifecycle fixes were bundled; no fixes-only control was replayed, so the pure candidate effect is not isolated.
- Current implementation corroboration: runtime/coinmaster/strategy/wave_overlay.py:958-1010.

## B25 already cut50% BTC, but also changed future entry sizing

Evidence: reports/v3-risk-four-113/comparison/README.md; implementation/receipt.json; runtime/coinmaster/strategy/wave_overlay.py:752-777.

- Own older V3 control TOTAL5437208.56951095 / native DD67.2863064484%.
- B25 TOTAL2394463.52298288 / native DD46.48498057%; TOTAL -55.96152893%.
- B25 DID meet its historical native-minuteDD<=50 criterion. Calling it a DD failure would be incorrect. Conditional OHLC bound59.46109682% still did not establish an intrabar cap.
- Trigger: GLOBAL native equity DD>=25%, currently open BTC episode PnL<0, and latch not already reduced.
- Action cuts50% actual remaining BTC through native reduction.
- Latch also changes subsequent entry multipliers from long5.5/short7.875 to long2.75/short3.9375; globalDD<=15% rearms. Thus its TOTAL/DD cannot isolate a one-off BTC trim with entry sizing unchanged.
-13 triggers/submits/fills;12 rearms. Not a price-envelope rule or preTP-only rule.

## Proposed ADVERSE-50-once: actual distinction and remaining uncertainty

A once-per-episode cut50% remaining BTC beyond an independently fixed winning-proxy-MAE price envelope would differ from both older policies:
- Price-relative trigger instead of BTC-PnL/equity or global HWM trigger.
- Single consumed episode right with no HWM recovery rearm or automatic refill.
- No global future entry-sizing latch.
- BTC-only trim preserves original SOL alpha rights; it is not full-group closure.
- No TP1 requirement if intended to address initial adverse; scope must state whether postTP adverse can also trigger and keep the same once-only right.
- Original BTC entry/split/sizing/TP rules are otherwise retained, although actual equity-based future Q can change.

This is a different parameterization/ownership contract for partial loss reduction, not a newly proven edge. B25 is relevant adverse evidence about return sacrificed by partial risk reduction; it does not prove the proposed price selector can save the tail with less cost. Calibration/OOS classifications remain proxy classification, not actual native cash, DD or a profitable strategy. Preserve original SOL liquidation/margin constraints after BTC shrinks; no claim that retaining SOL unchanged automatically preserves portfolio risk.

Do not compare these older native outcomes directly as a fair head-to-head against selected6077107.23887483; baseline generations differ.
