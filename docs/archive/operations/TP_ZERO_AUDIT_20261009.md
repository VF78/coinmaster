# TP zero-threshold audit — 2026-10-09

Scope: read-only review of canonical source at HEAD `6fee2a9`, saved V0 native 24-month run (`runtime/var/data/runs/tp-fee-floor-113/v0/v0.json`, SHA-256 `d6a29d6e0e9ac586b911f2802cbe89602a05d2c0d73026d08ed76082a8a934f9`), and `paper_native_fill_details` in the Stage-G SQLite. No backtest, code, config, seal, or service change.

## Mechanism

`completed_wave_levels` in `runtime/coinmaster/domain/wave_overlay.py` takes each eligible completed same-side wave within 730 days, computes signed close-to-next-open returns, then saves `max(0, max(signed returns))` as its MFE. It requires at least eight waves. `linear_quantile` includes these valid zeros; candidate quantiles are 0.10, 0.30, and 0.60. A TP limit target is `confirmed BTC entry VWAP * (1 + episode side * quantile)`. A zero quantile therefore gives the entry price. This is the intended formula, not a missing history or startup default. Positive TP1 requires enough completed waves with positive MFE to move the 10th percentile above zero; TP2 requires enough to move the 30th percentile; TP3 requires enough to move the 60th percentile. With n waves and linear interpolation, positivity occurs when `(n-1)*q` lies above the last zero index (or interpolation toward a positive next value). A later fallback taker reduction may execute at a nonzero price even if the original target was zero.

## Saved V0 winner fill counts

V0 has 105 BTC entry fills, 618 total native fills, and 233 planned BTC reduction fills. Level 0: 89 reductions, comprising 45 resting `BTC_TP1` fills all exactly at entry price and 44 `BTC_REDUCE` fallback fills all at a different execution price. Level 1: 90 reductions, comprising 56 resting `BTC_TP2` fills (31 at entry price, 25 different) and 34 fallback fills at different prices. Level 2: 54 resting `BTC_TP3` fills, all different from entry price. Execution-price comparison alone does not recover a fallback orders original quantile. Fifteen BTC entries had no planned reduction fill before other outcomes.

Resting TP1 filled on the entry UTC day in 45/45 cases and within 10 minutes in 32/45; resting TP2 filled on the entry UTC day in 55/56 and within 10 minutes in 33/56. Earliest V0 TP1/TP2 fill was 120 seconds after entry. These times reflect the native one-minute historical close proxy and its order sequencing; they are not a live maker-fill timing prediction. The V0 run is classified `NOT_FAITHFUL_DIAGNOSTIC` in `.ops/TRADING_GAP_AUDIT_20261007.json`.

## October 9 Sandbox example

Episode `d6da14a8-e607-44b8-858c-2f572d05444d`: native BUY 1.08996 BTC at 81783, timestamp ns 1791504915233762352. Two native maker SELL fills of 0.23161 BTC each at 81783 share timestamp ns 1791504926225141279, 10.991378944 seconds after entry. The entry taker fee is 40.11308941 USDC and each maker fee is 2.84126409 USDC. Allocating the entry fee by reduced quantity gives approximately 22.73011275 USDC combined trading-fee loss on those two unchanged-price reductions, before any other episode PnL. The remaining 0.62674 BTC has an accepted resting sell at 83517.0 in the read-only native snapshot.

Interpretation: same-price TP1/TP2 is a systemic possible consequence of zero-including MFE quantiles, seen repeatedly in V0, not proof that every TP fills at entry. The backtest count shows 25 resting TP2 and 54 resting TP3 fills away from entry. This audit does not re-run or retune the winner. A future fee-floor rule would be a separate strategy version with a new seal and comparative run; it should not be silently applied to the installed Sandbox.

Concrete nonzero TP2 execution: in V0 on 2024-09-17 00:00 UTC, a short BTC entry SELL filled at 58185; at 00:02 UTC the resting TP2 BUY filled 0.27 BTC at 58162.3, a favorable 22.7 USDT/BTC price move before fees. The native order side was verified against the fill CSV. Of the 25 different-price resting TP2 fills, 18 were independently matched to favorable native order sides, none matched adverse; seven lacked a unique CSV row match and remain directionally unclassified by this audit.
