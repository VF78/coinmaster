# Prior experiments and feasibility of event-driven paired exits

Analysis only, 2026-10-20. Inspected canonical HEAD b1650aa2b326698f95972577a8804123b08c039e. No engine, product edit, service action, deployment, or Project mutation. The running pilot is outside scope.

## What the 607 number means

Existing postmortem-data.json / actual_churn_descriptions.i25 records 1,656 actual SOL reduction events, of which 1,506 have a subsequent actual ADD in the same BTC episode. Median next-ADD delay is 75 minutes. There are 704 reduction-to-next-ADD pairs within 60 minutes, mapping to **607 unique subsequent ADDs**. Several reductions can map to one ADD. These are neither 607 completed round trips nor proof of positive harvest PnL. 1,449 reduction-to-next-ADD pairs are temporally associated with a HARVEST event (most recent HARVEST within 60 seconds before reduction), without proven per-arm causal ownership.

The actual economic rule is not a one-hour re-add timer:
- immediate_insurance.py:120-122: 60 minutes bounds freshness of already completed SOL confirmation bars.
- Lines 149-167: native SOL profit versus estimated close fee plus a reverse SOL breakout, or equity restoration with a profit condition, reduces a coverage stage; ordinary recovery to adverse<.25 sigma also reduces extra stages.
- Lines 169-179: a new adverse observation strictly greater than the trim's adverse value, sufficient .5/1 sigma stage, and a fresh protective SOL breakout after arming can restore coverage. There is no positive minimum adverse-distance hysteresis. Non-Light base below base_full can restore the original floor.
- Lines 188-194: physical target relatches when actual BTC quantity or coverage fraction changes. It is not continuously rebalanced from price ratio alone. Actual BTC TP/Q2 fills can therefore cause a native SOL trim/add.
- conditional_hedge.py:308-314 has an operational retry_ns after native rejected/denied/expired ADD (1 minute for insurance). This retries a surviving economic target; it does not mint a new insurance right. Existing I25 summary records native_rejections=0, so it cannot explain these 607 additions.

Thus observed churn is compatible with repeated floor/stage restoration after small new adverse observations and changing price confirmations, plus actual quantity changes. Current summaries do not prove the exact cause of every one of the 607 ADDs; do not turn temporal association into a complete event attribution. No archive re-count was performed.

## Existing native outcomes, same 10,000 seed

| Policy | Settled TOTAL | Native marked DD % | Evidence / failure mechanics |
|---|---:|---:|---|
| Selected winner BTC + original SOL | 6,077,107.23887483 | 66.31878024969 | immediate-sol-insurance-113/postmortem-six-native-results.csv; reference is portfolio, not BTC-only |
| Exact standalone BTC-only policy | 280,748.52263020 | 64.07394986310 | same CSV; btc-only-native-receipt.json. Removing original SOL already costs 95.3802% final TOTAL |
| Conditional SOL 2% / 1% / 50% | 3,007,648.74434437 | 67.69 | conditional-sol-2-1-50-113/README.md; original alpha rights retained via MAX target, but SOL 2,857 fills vs205, SOL net diagnostic 189,744.71 vs678,661.21; four BTC entry fill times delayed120s by SOL flatten lifecycle |
| SOL cap50 | 3,314,315.92576245 | 58.0163022253 | sol-risk-first-20261018/README.md; partial DD benefit, severe TOTAL loss, still fails50% |
| DD / covariance | 4,046.59122751 | 70.5425497042 | same; changing exposures/turnover destroys edge; unchanged BTC sizing formula does not freeze equity or absolute quantities |
| SOL three exits + ATR | 113,562.54508323 | 93.9156213319 | same; native liquidation, 76 later BTC entries blocked; three exits alone do not establish pair edge |
| I25 | 8,000.31240969 | 67.6020516885 | postmortem-six-native-results.csv; removes original SOL alpha, negative SOL gross and high turnover |
| I25-Light | 7,864.88334010 | 68.3009290258 | same; real Light latch did not remove drag |
| I25-Recovery | 7,720.28353387 | 67.6177633076 | same; averaging losing SOL improves absolute SOL gross slightly but adds expense and worsens portfolio TOTAL |
| I33 | 2,026.97093770 | 84.6402097632 | same; greater adverse SOL risk, destroyed equity scale; lower absolute fees do not mean efficiency |
| ALPHA-CUSHION | UNKNOWN | observed >=93.2264269664 | alpha-cushion-113/analysis-export-outcome.md; no completed native JSON/CSV after OOM, settled TOTAL/ROI/flat UNKNOWN. Owner rejected/no repeat |

I25 SOL gross -32,369.835 BEFORE SOL fees13,140.38289795; a fee-only explanation is false. SOL net was negative in56/57 BTC winners and also21/48 BTC losers. Control's equal-episode combined net diagnostic was1.335736% of its own BTC entry notional versus I25 .014583%; this is not ROI or a fixed-Q counterfactual. Original SOL was held15.38% of BTC-held time versus I25 essentially100%. Signed asset funding remains UNKNOWN, and unexplained cash residual is not funding.

ALPHA last mark932.61441154 is not settled TOTAL; metadata/financial null fields mean unmeasured, not zero. Observed peak12,484.37563522 to trough845.63830144 suffices to reject DD<=50 without another run. Its earlier CUSHION rationale is superseded by actual negative evidence.

Known hedge feasibility must also distinguish cash from exposure: if cash/realized loss has already put E below F=.55H and no permitted SOL target satisfies the scenario, call it UNHEDGEABLE. Adding a delta hedge cannot erase previously realized loss. Unknown marks/ACK/coefficients are UNKNOWN and fail closed for increases; they are not proof of flat or of unhedgeability.

## NETTING makes the proposed BTC carry clause incompatible

native_baseline.py:781 creates OmsType.NETTING. domain/wave_overlay.py:365-390 owns one Episode, admits a new BTC_ENTRY only when episode is None, and returns CLOSE_ALL on regime side change. The current executor is not a multi-episode carry manager.

Suppose old BTC long L remains and the next original winner short is S:
- Submit original sell S: native net becomes L-S, not -S.
- To reach original native short -S, submit sell L+S; this closes all old long and opens short S.
- If S<L, the supposed short entry merely reduces the old long; if S=L, account becomes flat.
No domain metadata, TP labels, or separate logical lots can create two opposite native BTC positions on this instrument. Logical books can describe attribution, but cannot claim native independent PnL, margin, fill calendar, or simultaneous independent reduce-only TP rights.

Therefore retaining old BTC across an opposite EMA34 regime and preserving every next native winner entry side/quantity/calendar are jointly impossible here. Owner must choose: (A) keep native single-episode regime closure and original entry policy, dropping the carry clause; or (B) explicitly authorize changed entry/native exposure behavior and multi-episode ownership redesign; a separate hedging-capable venue/account/executor is outside current scope. Do not implement B as a hidden virtual second execution/PnL engine.

Even A preserves entry SIGNAL/sizing/split rules, not automatically historical absolute quantities: I25 changed104/105 Q and BTC-only99/105 Q through native equity. New TP/paired-close behavior changes equity and future equity-based sizing. Freezing historical Q/calendar from the full winner run would be a different counterfactual, not evidence that a causal unchanged strategy produced those sizes. Exact absolute entry volume preservation needs a separately defined causal sizing contract and feasibility proof.

Original SOL alpha and added insurance face the same one-position constraint. Current conditional_hedge.py:196-241 already reconciles one native target against actual/pending inventory, using original rights/ownership transfers; it rejects native SOL side opposite the current episode's protective side. Same-direction original and insurance claims can share a MAX target under explicit priority, not be called independent booked returns. On a BTC flip, old SOL rights can be opposite newly desired SOL; cannot preserve both independent physical books. Releasing a logical claim is not a fill or realized profit.

## Matched profit-taking is not free hedge income

For a BTC long with entry notional NB and opposite SOL short entry notional NS, marked pair PnL over a common interval before costs is:
  pair = NB*rBTC - NS*rSOL
  rSOL = beta*rBTC + epsilon
  pair = (NB-beta*NS)*rBTC - NS*epsilon.
For BTC short/SOL long signs reverse. The exact linear-contract quantity form is qBTC*(PB-PB0)+qSOL_signed*(PS-PS0). Re-estimated beta does not change actual contract cashflows.

If NS=NB/beta, factor exposure cancels approximately and residual SOL basis risk remains. Realizing winning-leg TP while closing the proportional losing leg realizes that combined pair result for the closed shares, minus both legs' opening/closing fees, actual slippage, and signed funding. It does not turn two offsetting legs into new alpha. If shares close at different times, expose the interim residual and carry; do not subtract an imagined simultaneous loser.

Break-even per leg is its own opening+closing+funding/slippage cost recovery, while cycle break-even requires ALL leg costs plus already realized losses across every trim/re-add since the immutable cycle start. A profitable SOL TP or BTC TP is insufficient. Mark-net zero before execution is insufficient. Existing signed-funding attribution is unknown; state that limitation instead of manufacturing a cycle profit. Same-account native cash/equity is the authority.

Proportional beta-risk matching should use the same fraction of outstanding factor exposure: if BTC share f is closed, close f of paired SOL exposure subject to lot rounding and pending leaves. Closing both shares reduces paired notional but does not remove a pre-existing loss on the rest. After winner TP1, a cost-aware BE stop can reduce giveback risk, but can exit on normal noise and cannot lock total-cycle profit when the other leg is losing. Full loser exit at TP2 is a risk decision whose costs must appear in combined native equity.

## Narrowest coherent candidate for further owner selection, not a run request

An event-right paired-exit hypothesis can be defined without a second executor, but current evidence does not prove its ROI/DD:
1. Preserve original BTC signal/entry/split/sizing RULES and original lawful SOL alpha rights; keep single-episode mandatory regime close. Do not carry old BTC through opposite original entry. Explicitly accept that realized absolute Q can change with equity.
2. Additional hedge right only from a new immutable BTC adverse-price milestone relative to frozen first-fill reference, or a newly completed daily regime-break event. Actual native BTC TP fill may release/retire proportional rights; it must not repeatedly regenerate the same paid hedge. No elapsed-time right or equity-restoration re-add.
3. Each right records episode, event ID/time, causal reference price, maximum one admitted/filled quantity, native parent IDs, partial-filled quantity, consumed quantity, and cost basis. One TARGET merges eligible alpha and protective rights with actual+pending exposure and native margin/Q2 reservations. Unknown ACK reserves its right until proven terminal.
4. A trim consumes a right. Re-entry requires a strictly new milestone beyond a positive predeclared price hysteresis gap plus fresh completed-bar evidence; recrossing the paid level or waiting does not renew it. Original alpha authorization expiry and partial-fill semantics remain authoritative; no refill of expired alpha credit.
5. TP1/TP2/TP3 use three predeclared reachable levels and shares on each eligible side; probabilities such as high/50%/20% are measured conditional outcomes, not promised labels. Actual fills, not intrabar touches, trigger proportional opposite-leg reductions. A BTC TP order without a fill creates no event right.
6. Count combined actual native cash/equity, worst marked portfolio DD, costs, margin and liquidation, plus cycle-level net closed-pair diagnostics. Separate directional trend PnL, basis residual and total fees; no independent simulated alpha/insurance cash books. An observed series of profitable TP snippets without whole-cycle net improvement fails the hypothesis.
7. Losing residuals require explicit invalidation: next mandatory regime/group close, loss/margin cap, or finite exposure boundary chosen before testing. Analysis horizon must include all remaining losing inventory and carry. Never hold losers indefinitely to make realized trade statistics look profitable. No new arbitrary timer may mint risk; a maximum risk holding boundary can only reduce/close.

This candidate differs from I25 by removing permanent insurance floor and reusable restoration rights; differs from failed ALPHA-CUSHION by rejecting quote-driven continuous risk-target churn; differs from three-exit ATR by linking matched reductions to real native TP fills and net pair economics. Any gain remains UNKNOWN. Owner choices on BTC carry and exact absolute Q must be resolved before a concrete implementation contract.

## Minimal evidence

- reports/immediate-sol-insurance-113/{postmortem-data.json,postmortem-report.md,postmortem-six-native-results.csv,btc-only-native-receipt.json,btc-only-calendar-comparison.json,next-three-proposals.md}
- reports/conditional-sol-2-1-50-113/README.md
- reports/sol-risk-first-20261018/README.md
- reports/alpha-cushion-113/{analysis-export-outcome.md,analysis-failed-observer-diagnostic.json,implementation-contract.md}
- runtime/coinmaster/strategy/{immediate_insurance.py,conditional_hedge.py}, runtime/coinmaster/domain/wave_overlay.py, runtime/coinmaster/research/native_baseline.py
- Source SHA-256 values are recorded in prior-source-sha256.txt next to this report. No full archive, TASKSTATE, or full chat transcript used.
