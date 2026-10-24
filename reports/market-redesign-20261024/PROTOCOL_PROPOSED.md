# Market redesign — proposed first checkpoint

Status: PROPOSED_AWAITING_OWNER; not an active run authorization. Date2026-10-24 Europe/Moscow.

## Scope and acceptance

Owner request: market-based BTC entries/three real TP and conditional SOL hedge, retain>=90%S0 net profit and global marked equity DD<=50%, preferably30–50%. Pilot, production, services, credentials, real orders and transfers are excluded. Existing closed research budgets remain closed.

This first checkpoint isolates BTC execution and sizing. It does not claim to solve SOL or economic acceptance. No training, Optuna, offset/EMA/TP/SL grid, new engine, SDK or infrastructure. Native Nautilus1.231.0, Python3.12.13 verified locally.

## Exact reference and one causal change

Archive R0 E4 source `bd04c9b3858bcda40060a08eff488849c69af5d8`; resolved configSHA `ce7c101ace5d8c21f0a912a0cd3221659591e5d56b744d3f8dc5ecb7c01d2ef6`; dataSHA `7ab5ae2cdaa14885da28d188c7ad14dfc8168ee600b78535f7317409ea94e9cc`; policySHA `c9540fbef259039c95829a774ef54e0eea2dcf2b6748d6455e171bf28e889834`. Archive closed-bars blob `f2aafb8c784177e2606ed13cb11c409164f9aa9b` verified. Manager HEAD8137847 is a documentation checkpoint, not strategy source.

Use existing R0 receipt after its source/config/data/environment qualification; no automatic full rerun. Archive period [2024-09-01,2026-09-01)UTC, seed10000USDT, RESERVE0. Legacy S0 TOTAL6077107.23887483 and immutable90%netprofit floor5470396.514987347. Explicit SOL-child S0 TOTAL6482334.93387961/floor5835101.440491649 are separate; they cannot replace this archive contract or denominator.

Principal change: preserve E4 causal signals and replace deferred/zero TP plus chased second-entry with real U three-TP and limit-only0.5%second-entry. Targets must protect actual confirmed inventory while a second child is pending. Saved cycle81 demonstrates the current scheduling hole: queue is suppressed by unfinished split;23:59cancel then midnight stop leave no positive TP. This is distinct from failed H_SOL add-admission and H_BTC repeat-size hypotheses: neither repaired early BTC protection or child completion.

Before run1, pin candidate source commit, explicit resolved configs, all input hashes, engine/environment, fee/funding/settlement policy, and executable commands in a new immutable freeze receipt. Product base is exact E4; reuse a report-only Decimal80 fix only after diff review with unchanged tolerances. Do not silently import latest explicit SOL execution semantics or change instruments, liquidity, admission, fees or account model. If archive semantics cannot be preserved, STOP and amend protocol before spending runs; no new control attempt is implied.

## Execution contract

- Retain EMA34/D1 side, wave history/labels, wait4h and0.5D1ATR regime reentry, PLANREF, TRAIL, admission and parentcap30m. Empty position does not end the signal episode or permit same-side reentry; terminal-flat/order ACK and causal episode transitions remain explicit.
- First half of admitted quantity follows existing first-entry policy. P0 is first-child actual VWAP; provisional protection after partial fill, frozen plan after terminal first child. Second half only LIMIT at P0*(1-side*.005), rounded favorably. No DEADLINE/EARLY_TP/day-end MARKET fallback. Cancel second on first positive TP fill, cycle invalidation, BTCflat or admission refusal; handle late fills from actual native state. No implicit third child.
- Preserve causal positive d3, set d1=d3/3,d2=2*d3/3. Invalid/nonpositive distances, unordered rounded prices or invalid TP sizes block new entry with explicit reason. Also preflight fee-positive prices using actual intended entry/exit fee classification; do not silently introduce a fitted floor or alter d3. Flag negative net targets and STOP if the base rule cannot meet the contract.
- Real accepted reduce-only TP quantities .2125/.2125/remainder of actual inventory. Submit after first fill and reconcile on partials, cancels, rejects and second-entry fills. Prices remain tied to P0 plan. Never restore a filled TP. Log all unprotected duration and order ACK latency. Three outstanding TP are required before any TP is consumed; afterward only remaining unfilled levels cover remaining inventory. An insufficient partial fill for3validlots is an explicit protection exception; do not fabricate orders. No BTC price-SL in this checkpoint; preserve REGIME/TRAIL.
- R2 LEGACY_Q_CONTROL computes old net quantity causally as a pure sizing control, without zero fills/TP/SOL rights. R3 CLEAN_Q removes the zero-target selector: Nplan=phi_side*min(M_side*native_equity,30000000), phi_long=.8551535379805835/phi_short=.7977111237672364, M_long5.5/M_short7.875. Coefficients remain outside min; no tuning on TOTAL. Candidate quantities/compounding use candidate native equity.
- SOL is OFF for R1–R3. No TP event grants SOL rights. Full original lifecycle requirements are preserved in task-source.txt; exceptions above are qualification, not permission to hide missing protection.

## Proposed physical budget and gates

Approval requested for implementation plus one focused verification and **at most3new full native attempts total**, in order:

| Attempt | Variant | Purpose |
|---|---|---|
|1|R1: exact E4 BTC, SOL OFF|Native own-capital BTC control|
|2|R2: R1 + real U3TP/.5%limit-only + LEGACY_Q_CONTROL|Isolate changed execution/protection|
|3|R3: R2 + CLEAN_Q|Isolate removal of zero-target sizing selector|

Every physical full launch counts, including failed/OOM/repeated launches. A failed export does not permit a free rerun. No automatic replacement/extra attempt. Sequential only; fresh engine and funding journal per attempt. No automatic restart of quiet processes.

Before full attempt1: focused native lifecycle tests for partial/terminal first-fill, three accepted TP during pending second, TP/cancel race and late fill, no oversell, min-lots, signal episode while flat, reentry transitions and JSON roundtrip; bounded acceptance on saved episodes31/48/65/81 using closed data only. Short episode checks do not constitute full economics: at most one initial batch of4episode checks and one corrective batch of4, counted in the ledger; no rolling replay over the entire history disguised as short tests. One substantial correction maximum, then STOP on unresolved lifecycle defect. One narrow independent money/order diff review before full runs.

Do not reuse archived signal timestamps in R1–R3. Do not change inputs/rearm/wave statistics between attempts. R2/R3 cannot be judged economically from a frozen-trade arithmetic screen. Continue to the next ordered variant only with mechanically valid predecessor/accounting and explain its measured profit/tail tradeoff. A failed gate preserves evidence and stops the checkpoint.

R0 reuse costs0newattempts. R0 mismatch, additional BTC geometry/counter-swing variant, SOL full run, new matched S0/stress baseline, execution stress and repeat are **not authorized by this3attempt proposal**. Each needs a concrete result-based amendment/new budget; closed unused historical slots are unavailable.

## Evidence and stop rules

Full native accounting: fees from native fill classification, signed per-asset funding journal (UNKNOWN if unavailable, never zero substituted), initial+realized−fees+signedfunding+unrealized+externalflows=terminalTOTAL. Reserve transfers are internal. Inventory/account/order journals and terminalflat required, zero model liquidations. Unallocated bridge is not funding. Preserve archive synthetic minute-close execution qualification and actual partial/reject/cancel semantics. No L2/BBO liquidity claim.

Use complete common settled minute marked-equity coverage, including unrealized PnL; export account and ACTIVE+RESERVE DD separately. The<=50%test applies to global TOTAL marked-equity DD on this explicitly settled grid; intraminute DD remains UNKNOWN. Native/current-risk-tier liquidation0 is a model result, not a historical venue guarantee. Missing accounting/receipt coverage blocks positive economic acceptance.

Outputs: compact REPORT, source/config/data/environment freeze, commands, physical ledger, fill/order/cancel/transition logs, equity and DD episodes, comparisonCSV with TOTAL/netprofit/retention/DD/BTC-SOLPNL/fees/signedfunding/turnover/exposure/missing3TPduration/reject-partial-cancelcounts/fillqualification. Attribute all old/newDD>=30%windows and task named windows; isolate unfilled second-child, earlierTP, first-size, rearm, compounding and costs without summing incomparable frozen cash effects. Show first/secondyear and worst10%cycles. Winner only if simultaneous50/90/mechanical/realism gates; otherwise NONPASSING/INCONCLUSIVE, no implicit reversion to fake TP.

## SOL after BTC checkpoint

No claim that risk gate exists. Cheap saved-state action tables may compare NO_HEDGE, owner50%vol-adjustednotional, .5minimumvariance, .5BTCfactor and BTCtrim; these are distinct quantities, not interchangeable. For medium risk the owner's .5*BTCnotional*sigmaBTC/sigmaSOL is the direct vol-size interpretation; .5MV additionally scales by correlation. Positive causal correlation/data gate required; no-risk NO_HEDGE. Fix definition before any SOL implementation.

Features must be available at decision: closed H4returns/ER24, D1EMA distance/slope inATR, lagged synchronized720H1 covariance/correlation, SOLown/residualreturns, actualBTCinventory/age/unrealizedPNL. Outcome tables separate4h/24hactioncost+tailbenefit; block by BTCcycle, chronological expanding validation with purged crossing labels. Already viewed history is not untouchedOOS. No new ML/parameter grid. Do not promote prior failed adverse/chop/swing gates. A single explicit rule requires stable incremental protection vs NO_HEDGE/BTCtrim and sequential native lifecycle evidence; otherwise STOP_SOL/INCONCLUSIVE. Native SOL must use actual R3state, opposite side, own real3TP/SL, no pyramiding, new risk event after reset, BTCflat/flip exit and proportional cap on BTCreduction. One candidate full-run requires a separate frozen amendment/budget.
