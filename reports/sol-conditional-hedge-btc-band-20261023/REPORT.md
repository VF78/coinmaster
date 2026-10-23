# Conditional SOL hedge + BTC reentry band — v2

**Status: execution in progress. No deployment; pilot untouched.**

Exact archived S0 is the control. Acceptance requires settled minute DD ≤50% and TOTAL ≥5,470,396.514987347 USDT (≥90% of S0 net profit), then maximum TOTAL. Parameters, engine, input hashes and budget were frozen before candidate results.

| Recipe | TOTAL USDT | ROI | Minute DD | Status |
|---|---:|---:|---:|---|
| S0_ARCHIVE | 6,077,107.24 | 60,671.07% | 66.26% | IMMUTABLE_REFERENCE |
| C0 | 306.48 | -96.94% | 97.53% | VALID_NATIVE_COMPLETED_LIQUIDATED |
| H4_4H_E34_G050 | 437.07 | -95.63% | 96.48% | VALID_NATIVE_COMPLETED_LIQUIDATED |

C0 closes the old SOL lifecycle when actual BTC becomes flat; it does not proportionally reduce SOL at each BTC TP. H4 replaces the old SOL overlay with an opposite-direction 4h EMA hedge, beta-adjusted at each activation. B preserves the full original SOL overlay and gates only post-REGIME BTC reentry with 0.5 daily Wilder ATR14. The variants are independent.

First C0/H4 results are valid negative economic outcomes: after BTC TP3 closes the first episode, the next BTC short begins September 7 and is liquidated September 13. The earlier group release changes the BTC calendar. In first H4, the last SOL hedge closes at 12:01 UTC before BTC liquidation at 15:50 UTC; signal eligibility leaves the position unprotected during that adverse move. This is not evidence that every possible SOL hedge fails.

P0 on existing Mac arm64 Nautilus 1.231 exactly matches archived native account economics, fees, fill/order quantities, funding journal and settled DD. The strict full-artifact contract nevertheless FAILS: one BTC3 beta differs by −1 ULP and derived H by +2 ULP, localized to cross-platform `math.log` rounding; that BTC interval has no SOL fills and no observed native economic difference. No tolerance was widened. P0 economic criterion was predeclared; source and input pins remain unchanged.

Natural first-H4 fills do not demonstrate partial-order coverage: its hedge children are below the quote capacity. Partial/cancel/late-fill cases are addressed by focused native fixtures, reported separately.

All results remain **NOT_FAITHFUL_DIAGNOSTIC**: minute CLOSE synthetic quotes and limited liquidity/margin applicability. Signed funding attribution is UNKNOWN where absent; it is not zero. The repeatedly studied history is not an independent OOS test.

Core remaining: B and five fixed H4 recipes, followed only by the predeclared conditional X and R. No retuning or extra grid. Full final comparison, A–E windows and actual-action audits follow after the bounded cycle.
