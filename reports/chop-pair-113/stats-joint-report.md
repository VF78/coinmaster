# Fixed joint TP1 race: unconditional price/cost precheck

**Negative result:** a blind close/reduction of the opposite losing leg at whichever leg first reaches TP1 has no positive unconditional after-fee mean in calibration or holdout, either at factor-neutral or minimum-variance coverage. The earlier positive SOL-hit-conditional medians do not establish an algorithmic edge. Original profitable SOL alpha is not simulated here.

Before this additional read, freeze BTC favorable close threshold0.5317%, oppositeSOL1.040878%, earliest completed1m close of either; no more than24h and never past actual original BTC episode exit. All105 native-derived contexts keep exact timestamp and side. If neither threshold hits, the last actual mark is diagnostic NONE, not an execution. Entry anchor is synchronized execution-bar close, not the native average fill. This is pointwise signed movement arithmetic, not a backtest/PnL engine, not sequential exits/BE/rearm/compounding, and not portfolio TOTAL/ROI/DD.

Only two coefficient methods, from90 fully completed daily paired returns frozen at context: factor-neutral SOL/NB=1/beta(S|B); minimum-variance SOL/NB=Cov(B,S)/Var(S)=rho²/beta. BTC-only reference uses exactly the same paired-event timestamp rather than its independently selected exit. Costs are fixed conservative0.11% roundtrip per original leg notional, so method fee=.0011*(1+SOL/NB). Funding/spread/slippage/impact and later executable fill delay remain UNKNOWN. NONE is cost-adjusted mark arithmetic only, not pretend realized cash. Max path loss includes the same stipulated fee allowance and is normalized to initial BTC notional, not equity drawdown.

| Period | Fixed subset | Method | n | FirstBTC/SOL/NONE | Mean net % | Median net % | q10 net % | Positive / n | net>=.1% / n | Worst path loss % NB | Median path loss % NB |
|---|---|---|---:|---|---:|---:|---:|---|---|---:|---:|
|calibration|all|BTC_only|57|22/35/0|-0.2023|-0.3067|-0.8760|23/57|22/57|-1.9110|-0.5152|
|calibration|all|factor_neutral|57|22/35/0|-0.1040|0.0384|-0.7138|32/57|27/57|-4.7090|-0.4435|
|calibration|all|minimum_variance|57|22/35/0|-0.1232|-0.0908|-0.5504|25/57|17/57|-2.4248|-0.3382|
|calibration|near_slope|BTC_only|45|19/26/0|-0.1869|-0.2633|-1.0234|20/45|19/45|-1.9110|-0.5585|
|calibration|near_slope|factor_neutral|45|19/26/0|-0.1694|-0.0186|-0.7455|22/45|17/45|-4.7090|-0.4682|
|calibration|near_slope|minimum_variance|45|19/26/0|-0.1541|-0.0908|-0.7566|19/45|12/45|-2.4248|-0.3382|
|holdout|all|BTC_only|48|25/22/1|-0.0707|0.4221|-0.9014|27/48|26/48|-1.9517|-0.4494|
|holdout|all|factor_neutral|48|25/22/1|-0.1015|-0.0322|-0.7817|21/48|15/48|-1.3661|-0.4566|
|holdout|all|minimum_variance|48|25/22/1|-0.0934|-0.0749|-0.5086|21/48|17/48|-1.3296|-0.3829|
|holdout|near_slope|BTC_only|35|17/17/1|-0.0773|0.1382|-0.8689|19/35|18/35|-1.9099|-0.4598|
|holdout|near_slope|factor_neutral|35|17/17/1|-0.0793|-0.0314|-0.7840|17/35|13/35|-1.3661|-0.4487|
|holdout|near_slope|minimum_variance|35|17/17/1|-0.0692|-0.0688|-0.4366|16/35|13/35|-1.3200|-0.3625|

No same-close BTC+SOL simultaneous threshold event occurred. Every failure and the one holdout NONE remains in denominator. The near_slope context was fixed by calibration detector study; this subset table is not an OOS selection rule. None of its paired methods turns unconditional average positive. No threshold, coverage method, or filter was retuned after seeing holdout.

Across all holdout contexts, factor-neutral paired mean -0.101454% and minvariance -0.093440% are worse than same-event BTC-only -0.070744%. Minimum-variance reduces the factor-neutral q10 loss from -0.781690% to -0.508623% initial BTC notional, but leaves median negative. This supports a tradeoff between tail movement and factor exposure/cost; it does not support profitable universal paired harvesting or DD control.

A hypothetical gate requiring paired net>=0 would pass21/48 OOS contexts for either coverage method; >=+0.1% passes15/48 factor-neutral or17/48 minvariance. These are event-time diagnostic counts, not simulated decisions to wait/retry, and do not establish expected edge of the gated lifecycle. Costs on actual retained/partially closed inventory must be recomputed from native state; this test assumed both legs open at the context close.

**Implication for a coherent proposal:** reject unconditional proportional/full losing-leg retirement triggered solely by a profitable opposite TP. Use any TP as an invitation to evaluate actual paired slice proceeds after costs, with original BTC entry NETTING boundary authoritative. Additional adverse-price/risk evidence and cost-aware paired-slice gate are prerequisites to a new research hypothesis, not empirically proved sufficient conditions. Preserve original SOL alpha; its contribution and conflict with opposite coverage need native lifecycle testing only after separate owner approval. Neither the causal chop detector nor3-stage TP probability targets remove this failed unconditional precheck.

One additional sequential BTC/SOL minute read only; peakRSS128936KiB (~125.9MiB), idle I/O and low scheduling priority, no native observer read or engine. Reproduce from repo root: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 runtime/.venv/bin/python reports/chop-pair-113/stats-joint-analysis.py. Fresh source hashes match pinned original data, listed in stats-joint-result.json. Prior stats artifacts were not rewritten.

The one NONE context and exact point prices:

- BTC context#69 2026-01-10T00:01:00Z LONG ->2026-01-11T00:01:00Z, 1440min/24h_horizon; BTC90603.8->90465.7, SOL135.84->135.75. Factor-neutral net mark-0.2914%, minimum-variance-0.2827% NB.
