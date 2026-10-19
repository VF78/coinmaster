# CoinMaster #113 chop/pair research sources

Analysis only. No implementation, engine, deployment, or runtime changes.

Runtime remains Nautilus 1.231.0. N1/N2 are current official conceptual documentation, not version-pinned evidence of installed features. No migration implied.

## S1 — QuantConnect Kaufman Efficiency Ratio

[Source](https://github.com/QuantConnect/Lean/blob/master/Indicators/KaufmanEfficiencyRatio.cs) — official implementation

Finding: Rolling absolute net displacement divided by accumulated absolute price changes; explicit warmup. Its flat-window denominator-zero convention returns 1.

Implication: Supports a causal path-efficiency measure, not a validated profitable threshold. Specify n-return/n+1-price convention and flat handling explicitly.

## S2 — Gatev, Goetzmann, Rouwenhorst: Pairs Trading

[Source](https://www.nber.org/papers/w7032) — original research

Finding: Historical US equity pairs selected by normalized-price distance earned returns in the studied sample; costs and bootstrap comparisons matter.

Implication: Does not establish BTC/SOL stationarity, convergence or profitable opposite correlated positions.

## S3 — Bailey et al.: The Probability of Backtest Overfitting

[Source](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) — author-hosted original research

Finding: Selecting among many configurations creates selection bias; a simple holdout does not account for the number of trials.

Implication: Pre-register one compact detector/management hypothesis; disclose all attempted threshold and TP variants.

## S4 — Hyperliquid fees

[Source](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees) — official venue documentation

Finding: Current published base perpetual tier is 0.045% taker and 0.015% maker per execution before discounts.

Implication: Illustration only: equal USD10000 legs opened/closed taker cost approximately USD18 before slippage/funding at unchanged prices. Existing historical CoinMaster pinned fee assumptions must remain unchanged; current venue table must not overwrite them.

## S5 — Hyperliquid funding

[Source](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding) — official venue documentation

Finding: Funding settles hourly, depends on each contract premium, and payment uses position quantity times oracle price times funding rate.

Implication: BTC and SOL funding generally do not cancel. Include both leg-specific cashflows; no assumed funding profit.

## S6 — Hyperliquid margining

[Source](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/margining) — official venue documentation

Finding: Initial margin is position size times mark price divided by leverage. Cross liquidation depends on account value and total open notional.

Implication: Adding SOL consumes gross exposure and margin despite lower estimated net BTC beta.

## F1 — QuantConnect: Noise measuring functions

[Source](https://www.quantconnect.com/forum/discussion/9575/noise-measuring-functions/p1) — practitioner discussion, not validated evidence

Finding: Trend trader asks for ER/fractal/noise filters; contributor explicitly says posted ER code was not thoroughly tested.

Implication: Useful implementation discussion only; no evidence for profitable regime thresholds or superior detector.

## N1 — NautilusTrader Positions

[Source](https://nautilustrader.io/docs/latest/concepts/positions/) — official Nautilus documentation, latest conceptual reference

Finding: NETTING aggregates fills into one position per instrument/strategy; opposite fills reduce existing exposure and excess quantity reverses the net position. Virtual HEDGING on a NETTING venue still exposes only the venue net position.

Implication: Retaining old BTC while issuing unchanged next opposite BTC order cannot imply independent old and new BTC legs. Same-instrument SOL alpha and hedge offset in net exposure. Latest snapshot/replay features are not evidence of support in pinned 1.231.0.

## N2 — NautilusTrader Orders

[Source](https://nautilustrader.io/docs/latest/concepts/orders/) — official Nautilus documentation, latest conceptual reference

Finding: Native order model provides reduce_only, bracket TP/SL children and OTO/OCO/OUO relationships. Reduce-only must not increase exposure/open while flat; exact venue behavior varies. Documentation distinguishes local emulation from venue-native execution.

Implication: Use native orders/events and native position/account reporting. No claim that latest contingency management is installed in 1.231.0, or that a generic bracket atomically couples BTC and SOL. Three TP quantities, BE stop modification, partial fills and loser reduction require pinned-wheel/adapter validation before implementation.

## Analysis inferences (not source findings)

- Use completed fast bars against last completed daily EMA/ATR. Low normalized EMA distance measures proximity, ER measures path efficiency; neither guarantees early chop prediction. Daily EMA slope updates only daily; multi-filter conjunctions can recreate lag.

- Prefer asymmetric onset/end thresholds and causal confirmation, one hedge authorization per episode and a durable reduction ceiling. A TP-driven reduction must not be immediately restored by the old target.

- TP hit probabilities require a defined horizon, competing exits and chronological calibration; ever touched at an unlimited future date is not executable success.

- Let beta=Cov(rSOL,rBTC)/Var(rBTC), signed BTC notional NB. Factor-neutral SOL notional is -NB/beta. Minimum-variance SOL notional is -NB*Cov(rBTC,rSOL)/Var(rSOL). With NS=-h*NB/beta, minimum-variance h=rho^2 under the same unconstrained linear model.

- If rSOL=beta*rBTC+epsilon, pair contribution=(1-h)*NB*rBTC-h*NB*epsilon/beta. Full beta neutrality cancels BTC factor upside, leaving residual risk; partial bounded overlay better matches alpha-preservation intent.

- Pair breakeven requires realized PnL plus remaining unrealized PnLs plus net funding minus incurred fees minus estimated closing costs at least zero. Winner stop at entry alone is not pair breakeven. Avoid double-counting fees already included in a native net-PnL value. This is reporting arithmetic, not a second production accounting service.
