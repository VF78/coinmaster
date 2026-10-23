# Owner source feasibility and accepted contract

Accepted source freeze: `5dc17f0a8c6bc764746683f4d38bcf1fa9dcc77e`; exact root policy is `protocol-freeze.json`. Root accepted SOL stress dominance, proportional real partial TP3 rights, and sequential early/remaining TP3 allocation. Final source, preparation, and tooling hashes are in the corresponding owner JSON files. Historical engine launches still require separate root GO.

Exact base: `bd04c9b3858bcda40060a08eff488849c69af5d8`, archived E4 flags alone. No XS/R2C flags. Immutable Mac mirror: `/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/b-50-90-next-20261023/source-bd04c9b`. Canonical source is the isolated VPS research worktree to be created below `/root/.openclaw/workspace/coinmaster/coinmaster/research-worktrees`. Read-only bounded SSH verified the exact base. No implementation or historical engine started at this checkpoint.

## Existing contract

`runtime/coinmaster/domain/wave_overlay.py` lines 496–527 grants SOL entitlement on each confirmed partial BTC TP fill, proportional to cumulative actual filled native lots divided by the unchanged original TP target lots (and actual entry fraction). `btc_filled_tps` marks completion separately. Root directs preservation of this actual partial-fill contract across early plus remaining TP3. Completion-only entitlement would be an additional policy change and is excluded.

`strategy/split_cover.py` owns the split completion/unknown ACK rule and existing positive target IOC catchup. `strategy/wave_overlay.py` owns target queuing, native lot sizing, forced-exit precedence, native fills/cancel/denied handling. TP1/2, omitted zero levels, original fallback, plan size, PLANREF and domain total TP3 lot budget remain authoritative.

## Accepted SOL budget

Use completed D1 Wilder ATR14, following the existing BTC implementation in `strategy/hedge_band.py`. BTC daily H/L already has a seed and accepted-session cache; SOL requires the same minimal seed/cache, since domain DailyBar retains only SOL close. Genuine paired daily OHLC and immutable seed daily parquets already exist. No new market source.

At fresh paired 1m state, current native cash plus native `position.unrealized_pnl` is E; historical global native marked peak is H. Arm at DD >= 35%; warn floor is .55H. Do not use the previous-source settled receipt as current equity. Reserve independent adverse one-ATR BTC stress plus worst-direction native taker exit costs, granting no hedge credit. Root froze the additional strict SOL dominance test: held SOL × ATR_SOL > absolute native BTC quantity × ATR_BTC. H includes current native equity even while SOL is flat, a cut is finished, or ATR is unavailable.

For held SOL quantity Qh, taker fee fS, mark S, ATR aS, BTC reserve RB: native-lot-floor admissible remaining quantity is max(0, (E-.55H-RB-fS*S*Qh)/(aS*(1+fS))). This reserves cut cost and stressed exit cost of the remaining quantity. RB = QB * (aB + fB*(B+aB)). Trigger only when current held quantity exceeds the cap. Freeze one target per cycle; known terminal child leaves may finish it, with no restoration or repeated dynamic resizing. Forced and ordinary exits preempt it. Pending/unknown native work prevents an assumed state.

Original SOL signals and consumed-right counters remain unchanged. Before an original SOL add after activation, admit the original quantity only if post-add equity minus entry fee, both adverse ATR losses, and stressed exit fees meets .55H. Otherwise terminate the unfilled parent, preserving still-unused original entitlement; no new timer, recycled consumed entitlement, or automatic restoration.

## BTC early TP3 contract

After complete original split, positive original TP3 strictly beyond 1% PLANREF, available native target leaves covering native-lot-floor 20% of actual initial BTC quantity: reserve that quantity inside the existing original TP3 budget at favorable 1% PLANREF. The accepted sequence uses the existing single native ownership key: early tranche first, then original-price remaining on the next eligible quote after confirmed early completion. Pending or ordinary exit gates can delay that transition. Do not create an independent level or target budget. Actual early plus original fills update the same original level once; original target-lot conservation and proportional SOL entitlement remain exact. Pending, partial, cancel ACK, late fill, mandatory exit and terminal leaves retain existing ownership semantics.

## Diff and verification plan

Default-off research config/CLI and policy identity in `research/native_baseline.py` and `strategy/wave_overlay.py`; isolated small research policy mixin; minimal existing target-queue/native sizing/fill hooks. Do not change the native engine, SDK, observer or monetary accounting. Add focused wheel-native fixtures for completed-D1 as-of ATR, missing inputs, lot-floor boundaries, BTC-dominant no-op if selected, no-churn target, original unused adds, consumed-right conservation, early/remaining target exact lots, proportional actual-fill rights, cancellation/late-fill and forced-exit precedence. One complete relevant verification pass after one focused implementation pass, at most one substantive correction.

Reuse existing Python venv, immutable input hashes, native observer, single-executor runner, source manifests, native fills/order exports and collection checks. New ledger starts at 0/4 physical full native attempts, with one explicit root GO per launched recipe. Any failed start consumes a slot. No S0/E4 rerun, automatic retry or baseline parity run. Intended slots: SOL, BTC, conditional combined, conditional fresh repeat of a valid 50/90 candidate. Separate results must justify combined. No pilot/service/settings/deploy/secret activity.
