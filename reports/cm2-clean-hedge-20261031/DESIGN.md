# CM2 v1 joint BTC core and selective SOL protection

Research only. The goal is final TOTAL≥5.6m USDC from10k over the pinned24months, settled/coherent DD≤45% and zero modeled liquidations. No result is yet demonstrated.

Two architectures were compared on paper: (J1) a directional BTC trend core with conditional opposite SOL inventory; (J2) a relative-price pair with a smaller BTC bias. J1 is chosen because direction can create sustained compounded growth and does not require a stationary BTC/SOL price ratio. J2 remains a paper alternative: return correlation does not establish price mean reversion.

## Growth and BTC lifecycle

BTC enters a breakout of the preceding T completed hourly closes. The decision close is excluded from that channel. Long/short rules are symmetric. Initial desired BTC notional is L×current native equity. L ranges1–8, default4; account-selected leverage is a separate fixed venue input. Native margin tiers, exact lots and causal capacity can reduce executable inventory. No arbitrary permanent small gross cap is imposed.

The first actual BTC fill establishes the parent; R=k×ATR24 at entry. A close-based trailing stop ratchets favorably and never widens. Additional BTC is permitted only before harvest, on a fresh favorable breakout beyond the parent extreme and profitable relative to known native VWAP. It changes a finite quantity target; repeated callbacks never add L×equity again. A rolled channel cannot license averaging down.

One harvest at2R closes1−core of actual BTC only when gross BTC gain exceeds actual remaining native entry commissions, conservative taker exit commission, any adverse attributed native funding, and one tick. Positive funding cannot license a losing-price harvest. The remaining runner cannot receive new BTC adds in that parent. A profitable trailing exit is TRAIL_PROFIT; losing risk exits are PROTECTIVE_STOP, never renamed TP. Native cash/funding are never manually adjusted.

BTC final flat/flip cancels increases and sets SOL target0. A new parent waits for confirmed both-flat and no unresolved owned orders. Emergency BTC exits may precede SOL: orphan duration/reason are recorded, not declared atomic.

## Causal SOL and risk

Estimate SOL-on-BTC OLS from168 paired closed hourly log returns. Variances must be positive, beta>.05 and correlation≥.30. The deterministic guard beta_g=beta+2×slope standard-error term is conservative within this estimate; it is not a confidence guarantee about future beta.

Let d be BTC direction. Use six-hour residual z and BTC return. Activate opposite SOL after two hourly observations with adverse BTC return and d×z<−trigger. Release after two observations with favorable BTC return or d×z≥−trigger/2. SOL is protection for actual current BTC, never an independent residual-alpha parent.

Desired opposite SOL notional X≤h×|BTC marked notional|/beta_g. Thus estimated BTC factor retains its original direction; h≤.75. Before adding, require reduction of the one-hour adverse bound b(B−beta×X)+uX after incremental roundtrip commission, where both b and u use their own hourly sigma/absolute95% tails. Six-hour activation statistics are never mixed into hourly risk coefficients. Funding is separate and not assumed beneficial.

SOL can be useful when it is directionally weaker in the current adverse BTC regime; otherwise direct BTC trim may be cheaper. Bad residual risk or unavailable beta does not justify a convenient positive beta constant. Unknowns freeze new risk, drain owned SOL and latch one finite half-BTC target. Repeated callbacks do not repeatedly halve it. Recovery needs two valid hours and drained SOL; ordinary new BTC adds still require the favorable breakout rule.

Target changes use a BTC-notional no-trade buffer. Hard guarded caps, explicit releases and mandatory drains bypass that buffer. All held positions and worst-case pending fills are rechecked after BTC changes/marks/beta updates. Ordinary BTC reductions stage confirmed SOL reduction first where needed; proposed SOL and pending BTC reductions also obey the future factor cap. Emergency risk exits bypass normal child limits.

## Execution, controls and limits

Raw linear-contract turnover is quote USDT. Child notional is at most1% of the previous completed minute's turnover, one child per minute per symbol. This is an explicit capacity assumption on USDT market history/USDC accounting, not measured market impact. First-minute missing prior turnover blocks increases; native rounding/minimums and aggregate projected tier admission remain authoritative.

Signals require both symbols, contiguous minute/hour coverage and actual availability. No close signal can submit against the same already-processed quote; first admissible quote has ts>available_ns. Pinned prestart H1 warmup contributes features only.

Own matched controls recompute their entire native capital path: BTC_ONLY removes SOL without substitute trim; BTC_TRIM replaces the same hedge premise with a finite reduced BTC-factor target. They inherit no archive quantities/capital. Four anchors are defaults, BTC_ONLY, BTC_TRIM and load6.

The seven parameter ranges/defaults are frozen in PARAMETER_SPACE.json; all other constants are explicit. Failures include whipsaw, delayed protection, adverse SOL basis, correlation breaks, turnover cost, capacity denial and margin stress. The continuous HWM never resets. Benchmark feasibility, structural protection, accounting, robustness and model limitations remain separate statuses. Native fixtures and the bounded search, not this design, decide whether J1 is useful.
