# CM2 novelty and reuse

New economic behavior: preceding-close BTC breakout, finite favorable-only BTC target, one cost-positive harvest plus runner, opposite SOL six-hour adverse-relative activation, hourly OLS guarded factor budget, one portfolio target state and explicit drain/recovery. No WaveOverlay inheritance, research mixins, C1 tokens, TP rights, old ladders, EMA/H multipliers or historical winning dates.

New source: cm2_policy.py (pure features/state/targets), cm2_execution.py (pure pending-aware native plans), cm2_native.py (independent Strategy), cm2_runner.py (opt-in factory/report/lease child), cm2_fixture.py (test-only connected native scenario).

Reused infrastructure: pinned Nautilus1.231 account/cache/order_factory/cancel/marketIOC/native fills; existing loader/cursors, exact instrument rounding, fixed fee profile, NativeEventJournal and PerpetualFundingModule; existing margin policy/tier update module; NativeMinuteRiskRecorder, CommittedNativeObserver, native lifecycle exporter and boundary/report precision contract. Reused math: standard log returns, OLS, ATR, quantiles. Reused trading rule: none. The mark-first modeled liquidation condition is account/risk infrastructure, not an inherited directional policy.

native_baseline gains an explicit research_cm2 factory branch. With None, original strategy assignment AST is identical to exact A00. The original observer is unchanged; CM2 uses a separate neutral wrapper without legacy economic callbacks. CM2 reports export their own evidence and explicit UNKNOWN fields rather than dummy legacy successes.

Fixture-only stock LimitOrderPartialFillModel is delegated for one aggressive SOL limitIOC; market fills retain qualified ZeroImpactFullFillDiagnostic. Native generates real partial/cancel events. This execution fixture model is distinct from the benchmark and is never ranked. No duplicate matcher, PnL engine or cash adjustment was introduced.
