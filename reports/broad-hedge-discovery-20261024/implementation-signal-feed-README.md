# ALL_H4 market-only feed — ready

Connected verification: PASS (`implementation-signal-feed-verification.json`). The metadata JSON is the immutable build receipt and therefore retains its original BUILT_PENDING_VERIFICATION status; the separate verification receipt is authoritative for the completed checks. One build, one connected verification, no correction/failure, engine/native runs0.

CSV: `implementation-signal-feed.csv`, schema `cm.paired_prefix.market_signal.v1`, 4,380 unique increasing completed UTC H4 rows, first2024-09-01T04:00Z, last2026-09-01T00:00Z. LF line endings. Runtime owner must filter decision_ns < actual prefix_end. available_ns=t means completed-source availability, not a claim about native callback arrival/order; not_before_ns=t+60s. Native payload/dataclass, scheduling, actual parent/side/Qref and cache ownership belong only to the runtime source owner.

Exact column order:

```
decision_ns,available_ns,not_before_ns,btc_close,sol_close,btc_h4_open,btc_previous_h4_close,beta_d1_30,rho_d1_30,sigma_btc_d1_30,sigma_sol_d1_30,risk_coefficients_valid,d1_last_return_end_ns,d1_first_return_end_ns,sol_atr_h4_14,sol_atr_valid,atr_last_h4_end_ns,b2_pattern_valid,b2_long,b2_short,b2_long_k,b2_short_k,f0_pattern_valid,f0_long,f0_short,f0_open_o,btc_funding_last_ns,btc_funding_previous_ns,sol_funding_last_ns,sol_funding_previous_ns,funding_differential_per_hour
```

All prices preserve source Decimal strings; coefficients are finite17-significant-digit decimal strings. ATR is Decimal50. Empty unavailable features remain empty with separate validity0; they are not false-safe market states. B2 raw flags are independent of SOL ATR availability and native exposure. F0 O is actual current H4 rawopen; although observed data happens to have open==previousclose on every noninitial row, a controlled independent plumbing fixture proves O follows rawopen and leaves previousclose unchanged.

Counts: risk coefficients valid4380; SOL ATR valid4367(first13unavailable); B2 pattern valid4373/long121/short100; F0 pattern valid4379/long717/short1483. No actual parent/calendar/quantity/capital/future-flat/future-funding/outcome filtering or native imports. Builder reads only6normalized market files: BTC/SOL execution1m, daily close and funding publications.

Verification independently checks every4380raw price/time aggregate,30D1lag1Dcoefficient window, SOL H4 ATR14, bothside B2 K/F0 O/rate-hour clocks; four physically truncated-input prefixes are byte-field identical. A1618row projection of previous discovery market features agrees, only as verification—not feed input. Original native parent/position/equity/outcomes never select feed rows.

SHA256:

- CSV: `2fcd030c495f15a28ff4ff2ef6d931a018e5a2dd9cf142a56ac6582f941734e1`
- Builder: `47704f6ca1a998ef464ba7b0237d5e32d2330f92702d3c05d00df426a0b34cf3`
- Metadata: `6203a2d074b0ea26597526366bd30ba79e9391cf2541b9b974e5c037c7462be5`
- Verification script: `92b3d01c91f273aeb00c71d6069b88fcc95caff1806106979fad47424d142656`

Input/contract hashes are in metadata; verification records the unchanged final CSV/build/metadata hashes. No VPS runtime source/payload/API implementation, native engine launch, order, Project update or commit was performed here.
