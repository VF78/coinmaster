# BTC-linked SOL insurance: selected-engine audit, 2026-10-19

Analysis only: no source changes, tests, engines, optimizer, deployment, secrets or pilot actions. Object is the selected winner, not the later risk-first variants.

## Exact object and numbers

Selected source `759823d69a74e72b123add5ae775dd8c3aed4ac5`; independent repeat exists. TOTAL **6077107.23887483**, seed10000; native minute marked DD **66.3187802497%**. Research evidence does not imply deployment. Installed pilot release **81e6318** is separate.

Frozen job root `J=/var/lib/coinmaster-native-gui/data/runs/jobs/cm115-split-btc025-planref-tp-ioc-20261018a`.
Frozen source `F=J/source/runtime/coinmaster`; citations below refer to F, not later edited dev source.
Result `J/result/v0-selective-lifecycle-cap30m-btc-split50-d0.0025-planref-v1-tp-ioc-btc-direction.json` SHA256 `4dbfaf0d228f27ebc5e24157b613b0ddd279bffa2d163d042684bdad13bbec1b`.
Config hash `74eceede3340c3b0313801ffa9b6380b9b231dd2c589c57014f68c070a5fa457`; policy hash `c9540fbef259039c95829a774ef54e0eea2dcf2b6748d6455e171bf28e889834`.

Exact config: daily EMA34; BTC long5.5x/short7.875x native marked active equity, parent cap30m USDT. Accepted BTC Q splits approximately50/50 lots: initial native leg, second0.25% better maker limit, maximum4h/early-TP acceleration, cancel/known-terminal before residual. PLANREF first-completed-leg actual VWAP controls TP/TRAIL; native cash/PnL/H use actual blended fills. TP fractions21.25/21.25/57.5%; wave levels causal quantiles10/30/60% over730d completed waves (minimum8). Daily trail3%; no configured BTC stop. DP off/reserve0; originalSOL on; conditional/continuous/risk-first cover off. Bybit maker0.020%/taker0.055%; same native one-minute quote/mark proxy.
Sources: F/domain/wave_overlay.py:97–130,355–410,551–575; F/strategy/split_cover.py:88–103,150–182; exact result.config above.

## Mismatch with insurance

1. **Rights arrive after favorable BTC reductions, not BTC loss.** Confirmed BTC TP grants SOL rights; omitted zero-level admission has separate actual-fill-backed rights. Then signed residual z must exceed1.25/2.50/3.75. A losing fresh BTC entry without a prior right can remain unhedged. F/domain/wave_overlay.py:415–438,479–518. Future TP or synthetic fill cannot substitute for authority.

2. **Opposite direction is insufficient sizing.** SOL direction is minus BTCside. Original beta is Cov(SOL,BTC)/Var(BTC) from270 daily log returns. H freezes entry beta; z uses changing daily beta and sigma frozen at first SOL fill (`episode_fixed_beta=false`). Inverse beta is generally not the minimum-variance coefficient Cov(BTC,SOL)/Var(SOL), which equals correlation-squared divided by SOL-on-BTC beta on the same sample. Historical positive covariance does not ensure insurance during SOL-specific shocks or correlation reversal. F/domain/wave_overlay.py:110–129,419–424,525–526,549; exact config.

3. **Initial gross budget, not remaining BTC risk.** H=(gross reference BTC Q, otherwise initial filled Q)×actual blended BTC VWAP/entry beta. Level budgets1.75H/2.625H/3.5H, cumulative authorization ceiling7.875H before fractional rights, consumed notional, rounding and admission constraints. This is not a guaranteed fill, but neither is it a remaining-BTC coverage cap. BTC TP does not proportionately retire H; inverse net exposure can grow as BTC disappears. F/domain/wave_overlay.py:431–436,549; F/strategy/wave_overlay.py:1786–1806.

4. **BTC-flat is not SOL-flat.** Persistent rights permit late SOL adds; ordinary BTC TP3 does not itself authorize group cleanup. Genuine winner witness: 2024Dec23 18:52 BTC3.542 fully TP3-closed, SOL1000 remains; Dec24 00:00 adds SOL1000 at190.05; Dec25 REGIME closes2000 at197.02. This is standalone residual exposure after the insured position ended, not a winner bug. F/domain/wave_overlay.py:429–438,519,607–611; result.fill_audit at these timestamps.

5. **Exit clocks follow residual convergence.** Daily signed-z<=0.375 requests half; full<=0.125 waits for a later decision index after actual half completion. Fourteen-day hard timeout can close SOL while BTC remains adverse. Clock/sigma reset only on native SOL-flat; consumed level notional is not automatically replenished. F/domain/wave_overlay.py:441–460,520–545,603–605. Insurance instead needs an explicit BTC recovery/reduction/flat reason; mandatory removal cannot depend on hedge profitability.

6. **Whipsaw sequencing can be backwards.** Favorable BTC can earn a right before reversing; daily z may admit protection only after the loss. Residual-z convergence or timeout can remove it while BTC remains adverse. BTC REGIME/TRAIL closes both legs even if SOL is then paying protection. A recovery can lose on inverse SOL while BTC profit has already been partially realized. These are structural possibilities, not claims that every historical whipsaw followed them. Daily regime reversal preempts other work; trail arms only after favorable return>3%, then3 percentage-point giveback. Native both-leg flattening precedes the next episode and may delay BTC entry. F/domain/wave_overlay.py:382–399. Existing accepted native z reductions have real execution latency/fees/partial continuation, not ideal immediate fills: F/strategy/wave_overlay.py:1938–1967.

## Three protective policy candidates, not authorized runs

Shared boundary: preserve BTC signal/sizing/split/TP/PLANREF. SOL becomes a dedicated insurance owner rather than an additional residual-alpha strategy. Target uses actual signed remaining BTC notional and a causal valid positive covariance coefficient; no BTC means no new protective SOL. Invalid/nonpositive covariance blocks new directed protection. Preregister thresholds/lookbacks/coverage caps; this note selects no optimizer parameters.

A. **Adverse-from-entry**: OFF→ARMED on sufficiently adverse actual BTC return from native blended entry. Enter on a fresh quote after lawful causal confirmation, preserving accepted BTC Q2 margin. HOLD through the adverse state; hysteretic recovery, actual BTC reductions and BTC-flat reduce/terminate target. No TP-right/z prerequisite. Addresses initial losing trades, with explicit carry/churn cost.

B. **Favorable-excursion giveback**: track actual BTC episode favorable excursion independently of TP fills. Arm after a preregistered gain; activate on reversal/giveback; retain through that BTC drawdown rather than exit on SOL z. Size after actual BTC TP. Distinct from unchanged BTC3% management trail. Protects profit giveback, not initial entry loss; hysteresis is necessary to avoid repeated fees.

C. **Whipsaw-regime**: causal closed BTC signal flips/completed BTC loss episodes identify a preregistered choppy state. Protect the next actual BTC fill immediately with bounded coverage while that state persists; release on a defined BTC trend-recovery condition. Never hedge a future BTC direction or retain standalone protective SOL at BTC-flat. Resolve old native ownership before new-direction net target. Leaves EMA permissions intact but can reduce trend profits; evaluate separately.

None guarantees DD<=50%; none is merely a new SOL limit price. Root must explicitly choose replacement or subordination of original residual-alpha SOL; silently adding another owner recreates the mismatch.

## Existing native boundaries to reuse

Nautilus1.231, existing single SOL NETTING position, actual native cache quantities, current reduce-only MarketIOC/resting-order factory, cancel/known-terminal/latepartial correlation, native fees/cash and funding SQLite. Current dev `runtime/coinmaster/strategy/conditional_hedge.py:186` provides the existing `_conditional_reconcile`; `strategy/risk_first_sol.py:43` receives already-computed coherent native equity if portfolio gating is needed. Reuse these mechanisms without activating old conditional2/1 or failed risk-first policies. Use completed-bar receipt followed by fresh real quote, not exact timestamp equality. Mandatory/DP/terminal close preempts discretionary hedge work; unknown ACK remains owned risk.

One net target/physical SOL position; no shadow fill, second PnL, fake ownership-transfer cash, invented funding0, new SDK or risk service. Later authorized candidates require frozen source/fresh engine/funding journal. Native TOTAL/minute marked DD/fees/actual flat/pending and any real BTC execution delay remain truth. Minute proxies cannot certify intrabar coverage or a hard fill-at-trigger cap.


## Prior H1 overlap: avoid relabeling an old experiment

Authoritative compact record `reports/h1-b1-113/comparison/comparison.json`, corrected source `94e0e6cecbdef93ed3b1422ecfdffd26d3d936a5`, H1 config hash `bcfb7c33100b790c5da2b1013888bd63f8ee08ee7460cce9f340f5fffad015bd`. Valid corrected H1 TOTAL190593.96574493/nativeDD62.5978285459%, compared with old V3 TOTAL5437208.56951095, **not** the later selected BTCsplit/PLANREF/positiveTPIOC6077107.23887483. Initial zero-SOL routing diagnostic was invalid; do not quote it as H1 economics.

Old H1 already replaced original TP/z SOL, armed at strict BTC adverse>2.5%, used native closed SOL15m OR1h previous-bar break and first fresh eligible executable quote after receipt; stage1=50% of then-remaining BTC notional/daily beta. It exited on BTC-flat,14d timeout, or BTC adverse<=1% **AND fresh reverse SOL1h confirmation**. Stage2 was one additional actual stage1 quantity only after a subsequent actual BTC TP and new confirmation; no actual partial-BTC trimming, no remaining-BTC stage2 cap, no closed-cycle reentry. Actual31 stage1 parents and zero qualifying post-stage1 BTC reductions explain no stage2 opportunities. Current reusable code: `runtime/coinmaster/strategy/wave_overlay.py:483–550`; exact prior version/config remains authoritative.

Thus proposed BTC-owned insurance shares real mechanisms with H1; **adverse arm +15mOR1h +50% +BTCflat exit alone is not new**. A genuine later distinction would be an explicit adversity ladder25→50→75/100% on actual remaining BTC, no TP prerequisite for later insurance stages, native BTC partial trims, defined reverse/recovery de-escalation/harvest and a clearly specified rearm/whipsaw state. These are proposed policy changes, not evidence of better economics.

Old conditional2/1/50 differs again: it preserved original residual-alpha rights and merged protection through MAX, armed>2%, confirmed15mOR1h, immediate freshBTC recovery<=1% removed only conditional excess. The latest valid d83 result TOTAL3007648.74434437/nativeDD67.69439 did not test replacement of originalSOL by this new ladder. Do not call MAX-original plus50 protection equivalent to a sole BTC-owned insurance owner.

## Episode budgeting without another PnL engine

Capture native account marked equity at genuine BTC episode start and current coherent observer slices; use actual native cash plus native unrealized already computed by the existing observer. Native fill receipts provide actual entry/exit quantities, price, maker/taker, commissions; funding SQLite provides canonical settlement identity/account totals. These support risk-budget snapshots and true cash/fee checks without shadow balances. NETTING `positions_closed` alone is not a complete intra-position realized-flow history, and existing funding audit does not uniquely allocate signed funding to hedge subcomponents. An episode or hedge profit budget therefore must use an explicitly reconciled native account/equity boundary and fees, disclose funding attribution UNKNOWN where needed, and avoid crediting synthetic transfers or ideal price gains. No new realized/virtual ledger is required or authorized by this analysis.
