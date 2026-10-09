# Full trade-logic audit — selective variant, 2026-10-09

Audit-only scope: source a9c4d62, checkpoint1c1fb82, report SHA2560ccad5771c23e380ba6115cc7bc8530b47ee39ec6fe99c08595640e17b9faee1, terminalTOTAL3,747,041.97080334 USDT. No strategy/code changes, new full backtest, optimizer, deployment, seal, credentials or pilot action. Prior89 tests reused; suspicious lifecycle branches checked with small native/state probes. Final bounded triage used Sol6.1/medium after the owner's routing update.

## Confirmed defects

| ID / priority | Finding and evidence | Observed in 24m result? | Smallest systematic direction |
|---|---|---|---|
| F1 / P1 | Saved q0 lots are submitted at q1 without rechecking the configured10m parent-notional cap.11/105 BTC entries exceed cap; sumexcess39,923.3110, maxexcess13,629.2984 (0.1363%).Native3quote probe: cap100, q0price100, q1price101, actual1BTC*101 admitted. strategy651–723,875–942. | Yes; TOTAL incorporates these actual fills. ROI correction unknown. | Enforce cap against normalized actual q1 submission price before native submit. Fixed saved-lot policy implies explicit denial; preserving exposure with lot-clamping requires an explicit sizing-policy refinement and aligned target/right denominators. Do not silently skip11 entire trades or claim unchanged economics. |
| F2 / P2 | A reference touch before any confirmed BTC fill can be latched; later partial entry earns rights, then a non-touch quote activates them from the earlier touch. strategy729–755. Callback-order/state reproduction; no native-exchange latency proof. | No: all105 archived entries filled at q1,76/76 omitted rights activated once. | Require confirmed positive earned fraction before recording touch, or bind touch timestamp causally to the corresponding real fill. No synthetic TP. |
| F3 / P1 | Accepted ordinary SOL z-full exit lacks residual ownership/retry after partial IOC cancel. Native5quote probe:2,000 requested,1,000filled/canceled,1,000remains after2morequotes with emptypending/queue/no mandatoryexit. Ordinary half also waits a later qualifying daily decision, while preserving cumulative targetleaves. domain431–449,506–535; strategy1350–1377,1457–1484. | No ordinary z partial in this savedrun:half/full fills500each. Mandatory timeout and forced closes did complete. | Extend existing accepted-exit owner/retry path to the already chosen full/half target. Use native confirmed leaves, one inflight owner, bounded retry, authoritativecancel/terminalACK and forced/timeout priority. Preserve half target, cooldown and laterfull decision semantics; no new service/executor. |
| F4 / P2 | TerminalFLAT earlyreturn can leave an unsubmitted q0entry/domainpending/deferredplan. State callback proof:queued1,pending1,plan1 withnativepositions0. strategy1153–1165. q1boundaryguard prevents later submit. | Not established; report exports nativeflat/orders but not terminal domainqueue snapshot. | Terminalize local presubmit queues/plans before FLAT completeness. Treat already submitted unknownACK separately; native reconciliation owns its fate, not invented rejection. |
| F5 / P2 | Admission compares TOTALprospectiveIM to nativebalance_free already excluding existingIM+MM. Native MarginAccount probe:total1m,IM450k,MM50k->free500k; affordableadditionalIM100k is rejected by550k<=500k. strategy1180–1195; pinnedmargin.pyx715–747. Pre-existing. | Two actual SOL gate blocks exist; effect of this specific defect on those blocks unproven. | Use one consistent native margin budget: incremental requirement including tier/locked-margin changes versus availablefree, or equivalent consistenttotalbasis. Addressednative regression before economiccomparison. |
| F6 / P2 | Admission gross-cap equity uses cacheddaily marks while prospective notional/IM uses freshcausal policy marks. strategy1192. Pre-existing code-basis mismatch. | Potentially affects intraday SOLadds; no quantified blocked/admittedtrade attribution. | Use the same freshcausal mark snapshot for equity and prospective requirement. No second equity/PnL engine. |

These findings do not constitute implemented corrections. F1 makes current execution violate its configured parentcap despite correct native money arithmetic. F2/F3/F4 are edge-path findings, not explanations of this report's measured ROI. No lateACK-after-terminal exchange reopen was reproduced.

## Actual trade economics

All532 nativefills reconcile tofees597,517.54289494. BTC/SOL quantityconservation and terminalflat verified.586nativeorders terminal:341FILLED/245CANCELED;191canceledSOLmarketorders hadrealpartialfills,54BTCcanceledlimits hadzero fills. Cancel is not equivalent to no execution.

| Metric | BTC | SOL |
|---|---:|---:|
| Positionepisodes |105|26|
| Fillfees USDT |577,612.71049089|19,904.83240405|
| Negativeafterfees episodes (audit arithmetic) |48|4|
| Medianholding |47.98h|108h|
| Episodesclosedwithin1h |0|0|

- Zero-levelmaker TP fills are0 in this variant.73 actual zero-levelmarket fallbacks havepositivegross.
- BTC plannedTP2:6/24 legs negativeafterallocatedentry/nativeexitfees, combinednet−774.70890156USDT. Example2025-03-16 TP2 gross+434.7649, allocatedfees1,150.4456, net−715.6807. These are genuine smallpositivewave levels below fee breakeven, not zero-maker regression.
- SOLadds:17/110 followedbyexit within24h;nonewithin1h. Theiractualaddfees1,488.7076281; this is churn-screen evidence, not proof thoseadds are unprofitable or removable with foresight.
- One14daySOLhardtimeout episode loses−120,525.836 in actualfill arithmetic;12 partialexitfills completeover11minutes. Losing hold is a risk/economic outcome, not byitself a stuckexit.
- BTC48REGIMEcloses followedbyentryone minute later are intentionaloppositeposition flips; close+entryfees287,572.9622. No evidence that suppressing thesevalidflips improvesTOTAL.
- Same-time paired BTCfallback reductions reflect two targetallocations/SOLrights. Feesareadvalorem: mergingorders alone has no provenfeesaving.

Per-episode/leg gross uses confirmednativefill quantities/prices and average/proportionalentrybasis; fees areactualnativecommissions. This is audit arithmetic, not authoritative native closed-positionPnL. ReconstructedBTC+SOLnet3,738,565.90370506 versus nativegain3,737,041.97080334; residual−1,523.93290172 remains unallocated funding/othercash. Do not assign it invented pertrade funding.

## Checked boundaries and limits

- No futureq2/fill labels found in q0q1classifier. All105 archivedentrydelays exactly60s. Completedbar/featurehistorycausality reviewed.
- PartialBTCentry/TP quantities and realfills rights, staleSOLaddguard, mandatorytimeoutexit, forcedgroup cancellation/flat confirmation reviewed with priornative tests. UnknownACK intentionallyremains pending; it is not proven rejection.
- Terminalcash independentlymatches actualfill:73.534BTC*(78,524.9−78,186.9)−3,175.83749813=21,678.65450187USDT, exactly settledTOTAL−intervalcash. Identicalterminalnotional acrosscontrols follows cap/reference-lot path, not observed cachedmoney error.
- Funding is unchanged and fixture posts to nativeaccount viaadjust_account. Signedamount/pertradeattribution remain unexported. No fundingfix proposed here.
- Zero-spreadsyntheticquotes fromrealBybit1m closes, quote size1000, fixedfees, same-timestampfeedordering anddepositprotectionOFF remain material executionassumptions. Fullmarked-equityDD, selectivecrashrecovery and DPcompatibility not demonstrated by this24mrun. CorrectedcashDD62.46697029% is descriptive.
- Forced synchronousreject cadence, partialBTCfallback residual and lateACK/terminalrace not independently reproduced in this audit. Coverage is evidence-based, not a blanket guarantee of every exchange failure permutation.

## Minimal next sequence — proposals only

1. AddressF3 acceptedSOLtargetcompletion usingexistingnativeexitownership; thenF2 earned-before-touch andF4 localterminalcleanup withsmallnative/adversarialtests.
2. Agreecap-compliant q1sizing disposition forF1 withoutdiscardingentirevalidtrades; alignF5/F6 nativebudget/freshmarks and addressactual2gateblockrecords. One integrationverification.
3. Onlythen compare correctednativevariant versus archivedcontrol; TOTALaftercorrections isunknown untilrun. Do not preserve defects merely toretainROI.
4. SeparateROIexperiment: narrowly guard/reprice onlyfee-negativeplannedTP2 targets; preserveprofitablemarketfallback exposure/SOLsizing and realfillrights. Sixbadlegs are a candidate, not a promise of terminalgain; blanketfeefloor previouslyunderperformed.
5. OptionalnextROIexperiment: causalSOLaddfilter based onalreadyknown acceptedexit/timeout or currenttrail/regimeproximity. Historicalfutureexitwithin24h cannot be anentryoracle.48flip suppression andadditionalriskstops are not recommended withoutseparateversion/evidence.

Criterion remainsmaximumterminalACTIVE+RESERVE afterexpenses. NoDD/liquidationpenalty. Audit complete; all proposed source changes awaitowner scope/approval.

## Evidence files

- lifecycle.md: sourcecoverage/native/statefindings.
- cm113-selective-final-triage.md: boundedindependentfinaltriage onSol6.1.
- cm113-selective-economics-audit.json:131nativepositionepisodes/actionaggregates/provenance.
- cm113-selective-economics-audit.csv:317closingfilllegs, actualfees andexplicitallocatedbasis.

## Final BTC partial-fallback classification

Source proof: onpartial zero-level BTC MARKETfallback followed byCANCELED, cumulative targetleaves and proportional realfill SOLrights remain correct. Cancellation calls BTCtargetrearm, but plan_confirmed_btc_targets skips btc_zero_resting_suppressed, so this zero residual is not queued onnextquote. It requires a later accepted daily f>=threshold decision/newattemptindex. Positive restingtarget cancellation can requeue original limitprice leaves; a marketable post-only requeue locally cancels and awaits dailyfallback. No target is incorrectlymarkedfullyfilled, no fullSOLright fabricated, no unknownACK duplicate.

This is a completion-contract gap to address or explicitly retain, **source-confirmed but not independently native-reproduced and not observed in this savedrun**. If refined, use the existing singleowner and retry only while the original TP priceeligibility still holds; never unconditional BTCmarket retries throughadverseprices. This seventh item is separate from the native-proven SOLfull-exit gap.
