# Trading gap audit — 2026-10-07
#99; read-only; no deploy/restart/orders/parameters/keys/backtest rerun.

WINNER_RULE_EXPLAINS_GAP; NO_CURRENT_PRODUCTION_ENTRY_FAULT_EVIDENCED. Reconstruction supports retained episode + SOL signedz below1.25; precise historical live episode/z not exported. Direct accepted-session proof Oct6/7 only.

Direct production evidence: Sandbox PID2009732/NRestarts0 preserved; epoch10e39dc6efa64c8b820b174c0a5b65fe; native cash/equity11319.40534863USDC; only1terminalBTC_ENTRY and3terminalBTC_REDUCE intents, no SOL/pending/denied intents. Native account flat is not domain episode closed: installed BTC_REDUCE fill removes quantity and grants persistent SOL rights; _reconcile_group_flat only clears episode after a mandatory group close, not ordinary TP. No group close exists in durable journal.

Accepted paired signal cursor directly observed Oct6 and Oct7; latestOct7midnight, backfill_errornull. Oct7one DEFERRED_ENTRY_GATE sample then retry returned to ordinary no-intent state. Domain last_decision_reason remains BTC_ENTRY_INTENT from Sep29 because existing-episode no-intent branch does not update label; do not read this as new entry blocked. All21060 retained status samples PUBLIC_FEEDS_READY. Historical detailed logs begin Oct6 09:53UTC, so Oct2–5 actual decision state is unobservable from retainedlogs. Fourfiltered exceptionlines are two localhost HTTP disconnects/BrokenPipeError, not strategy failures.

Installed pure domain replay with genuine verified Bybit completed daily signals and confirmed native fills (no execution/PnL engine) yields no intents Oct3–7: EMA34regime+1, valid270daybeta~1.222, signedzbelow1.25 first SOL threshold. Reconstructed daily z:

| Completed close UTC | BTC close | beta | signed z | close return f | best f | intents |
|---|---:|---:|---:|---:|---:|---|
|2026-10-03|84475.9|1.223476|1.064859|0.012281|0.016597|none|
|2026-10-04|84716.5|1.223703|1.122684|0.015165|0.016597|none|
|2026-10-05|86486.7|1.222180|0.935198|0.036377|0.036377|none|
|2026-10-06|85725.1|1.222257|1.047794|0.027251|0.036377|none|
|2026-10-07|85510.0|1.221891|0.987059|0.024673|0.036377|none|

No regime reversal; 3%close-trail not reached (Oct7 f.024673 vs .006377 threshold). BTCepisode therefore remains owned despite allBTC sold Oct2; SOL rights remain available but no z trigger. NoSOLfill means noSOL14daytimeout/fixedsigma/halfexit blocker. Current DP ARMED50%, equity above threshold, no missed daily sample, entry control READY/RUNNING, attachable SEALED_APPROVAL_MATCH. Fresh absent private HL agent authorization concerns separate inactive Live; publicdata/nativeSandbox require no private agent and this does not blockDryrun.

Winner interval[2024-09-01,2026-09-01),10000TOTAL,Bybit1m genuine native artifacts. Stats use actual fill_audit actions, unique native entry submission/action/level, exclude TP/exitfills as entries; multiple SOL levels at one timestamp remain distinct earned level entries. Flat gaps are exact confirmed quantity exposure bookkeeping only; no PnL calculation. Source earlier G4 is archive, not current fee-floor control. Both remain NOT_FAITHFUL_DIAGNOSTIC.

| Source/metric | n gaps | mean days | median | min | max | >=5d |
|---|---:|---:|---:|---:|---:|---:|
|V0/all_risk_entries|218|3.334862|1.000000|0.000000|38.000694|22.94%|
|V0/btc_episode_entries|104|6.990385|5.499653|0.999306|38.999306|54.81%|
|V0/sol_add_entries|113|6.141593|1.000000|0.000000|227.001389|16.81%|
|V0/btc_episode_first_exit_to_next_btc_entry|104|6.314376|4.692708|0.000000|38.000000|49.04%|
|V0/native_full_flat_to_next_risk_entry|116|2.884770|0.227778|0.000000|32.000694|22.41%|

V0 first→second actual risk/BTC entry 2024-09-02T00:00:00+00:00→2024-09-11T00:00:00+00:00: 9.0days. SOLfirstentry is separate: 2024-10-03T00:00:00+00:00. Five-day no-risk-entry decision windows: 271/726 (37.33%).

| Source/metric | n gaps | mean days | median | min | max | >=5d |
|---|---:|---:|---:|---:|---:|---:|
|G4_archive/all_risk_entries|123|5.910569|3.999306|0.001389|38.998611|45.53%|
|G4_archive/btc_episode_entries|104|6.990385|5.998958|0.999306|38.998611|54.81%|
|G4_archive/sol_add_entries|18|38.555556|14.000000|0.714583|281.054861|77.78%|
|G4_archive/btc_episode_first_exit_to_next_btc_entry|104|5.745767|4.638194|0.000694|32.352083|48.08%|
|G4_archive/native_full_flat_to_next_risk_entry|104|0.407799|0.000694|0.000694|4.390972|0.00%|

G4_archive first→second actual risk/BTC entry 2024-09-02T00:00:00+00:00→2024-09-11T00:00:00+00:00: 9.0days. SOLfirstentry is separate: 2024-10-03T00:00:00+00:00. Five-day no-risk-entry decision windows: 327/726 (45.04%).

V0 first partialexitSep2 00:09→nextBTCentrySep11 00:00=8.99375d; firstfullBTC/native-flatSep6 14:52→nextBTC/anyriskentrySep11 00:00=4.3805556d. First→second entry9d does not mean only9days from first exit. CurrentSep29→Oct7 BTCentryage8.6d and Oct2 04:20→Oct7 ~5.5d without anyfill are different metrics; historical stats benchmark different calendar period, not expected same-date trading.

Candidate equality verified hash637762130c76396cd7c6e24644e31b28079a1683e4460d57f103dde42c603b6d. Live sealedstrategy0edecde9548533004292d5a6174ef6aeb77596817080c4a160f72aa2dc7dd511/release81e6318; V0runner deb7de5227d3a72a30bc082a317e98603143d8afd9b657f31d2afe5196984168 matches gitb079d1a native_baseline.py. Domainfeatures/decide/candidate rules equal across81e6318→b079d1a; inactive fee-floor accounting code differs. Economic venue/currency/DP/funding/instrument increments differ as JSON records; no current gate trigger.

Artifact paths, SHA256, exact daily rows, per-gapCSV, filtered log counts and provenance are in siblingJSON/CSV. Verified V0reportd6a29d6e0e9ac586b911f2802cbe89602a05d2c0d73026d08ed76082a8a934f9; fillsbecbacef0c531396c6f4cc4cacd78d63d74212ef317714eba2e51d911e832a4e; orders12b17db79728032749b8cd6bfc231d5dc85e217ef8f47c38e21496f73ad8ce23. G4reportf3501f9046ea0a5938bec00b659ead32d05200ef09cc32f0b91878b27d7fb26c.

Limits: no durable live episode checkpoint/currentz in installed DB; reconstruction not direct process-memory proof. DailyBybitdata is genuine exact signal source, liveexecutionHL affectsconfirmedentryprice/fees, not same dailyfeature source. Retained paired-session evidence onlyOct6–7. No syntheticfeed/mock/counterfactualbacktest or new7dayGUIjob used. The audit did not run automated tests because no implementation changed; targeted artifact assertions/hash checks, exact installed purefunctions, native durablefacts and sourcecomparison supply validation.

Exposure validation: both V0 and G4 fill_audit gross quantities exactly match genuine native fills.csv by instrument; per-leg cumulative quantities never negative and end exactly zero. Reversals occur only after closing owned exposure; entry/add increases magnitude and exit decreases it, so direction sign is irrelevant to flat detection. Same-timestamp events retain native callback order. No PnL recalculation.

G4 vs V0: candidate identical,105 BTC entries each, but G4 TPfills174/SOLadds19 vs V0 TPfills233/SOLadds114, reflecting intervening lifecycle/SOL-right code changes. Native flat timing differs materially: archive max4.391days/0%>=5days versus currentV0max32.001days/22.414%>=5days. This is not fee-floor effect or evidence current5daywait violates selectedV0. Aggregate report cannot isolate one old defect; do not overclaim. Allrisk minimum0days is valid simultaneous different earned SOL level entries.
