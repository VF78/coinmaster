# CoinMaster FAST-RND — 20.10.2026

**COMPLETE — valid negative result (allowed ending №2).** All four recognizers were implemented and measured; none beat the constant train-prior forecast on the common V set. No model selected, OOF/Optuna/policy fitting or new economic candidate run. The DD≤50% /≥90%S0profit goal remains unachieved. Research queue stopped; pilot unchanged.

[Owner task](owner-task.txt) · [Frozen experiment](experiment-lock.json) · [Project #2](https://github.com/users/VF78/projects/2) · [Issue #113](https://github.com/VF78/coinmaster/issues/113)

## Objective and boundary
W=ACTIVE equity+RESERVE; DD≤50% (30–50% desirable), NetProfit≥90% of reproduced S0, then maximum NetProfit. With seed10,000 and S0TOTAL6,077,107.23887483 the threshold is TOTAL5,470,396.514987347. Research only: no pilot, deployment, real orders, Hermes/sites/VPN changes. Previous CORRIDOR attempts are owner-stopped prefixes, not completed24m results.

Fixed order: S0+dataset → STUMPY → MiniRocket → RDST → fixedCNN seeds7/42 → V comparison → ONLY if informative causalOOF/boundedOptuna → lockedfinalists/U/nativeverification. An entirely negative recognizer comparison is a valid end; no broad trade search to mask it.

## Completed baseline and dataset
- Exact S0TOTAL6,077,107.23887483USDT; ROI+60,671.0723887483%; fees945,927.73761825; notional2,209,476,512.4321;621fills/710orders/0liquidations/flat. One full native run, CPU18m45.469s/peak472MiB/swap0; source/inputpinsPASS.
- Settled causal-source-mark equity DD66.256914864686864%:1,051,199receipts+seed/0unavailable/0pending. Legacy callback DD66.31878024969152% exactly reproduced. Timing measurement change, not improved trading. Discrete marked receipts do not establish observed intrabar tick DD.
- Native funding1320receipts; signed aggregateUNKNOWN, not zero. Existing2nativefundingtests+streamedpersistencefixturePASS (−1285.747 persists through later closes); no duplicate posting added.
- Legacy cash field0.378992825... is a fraction=37.89928254% associated with maximum absolute cash-drop episode, not certified maximum relative cash DD. Archive unchanged.
- Observer-only settlement repair:5nativePASS+independentGO; no signals/orders/cash/execution/cost change.
- Dataset17,520hourly IDs;5,959purgedselectedT/3,432V; zeroambiguous;57,697,969bytes;41.814sbuild; source/artifacthashesPASS. Manifest8f51abe51ddb15e95421549279cb8e32121b8797f43e0af9385e6df5e4a7329c.
- Real hourly prehistory exists:2,208BTC/SOLbars each June–August2024, officialRESTprovenance/SHA/continuity verified; Dailywarmup2022-09-02. No first-week omission/newfetch.
- Safe cleanup removed7audited paths/reclaimed1,140,477,952bytes; unique results/rawhistory/configs/active services retained. Separate1.454GB CPU MLenv, exacthashedlock/pipcheck/API+forwardPASS; trading venv unchanged.

## Validation diagnostics
Common5,959T/3,432V IDs; lower log loss is better. No U outcomes parsed or model selection yet.

|Method|BTC log loss|SOL log loss|Mean log loss|Fit / inference seconds|
|---|---:|---:|---:|---:|
|Train prior|1.101263991|1.099908435|1.100586213|0.0004 /0.0002|
|Simple38 logistic|1.298052054|1.427180786|1.362616420|3.731 /0.274|
|STUMPY analogue|1.119859150|1.127457444|1.123658297|253.620 /66.968|
|MiniRocket|7.125161290|7.300339389|7.212750340|72.438 /4.584|
|RDST|9.180662883|7.822216766|8.501439825|208.741 /16.477|
|CNN7/42 mean|1.265969776|1.272218681|1.269094229|3459.731 /94.520|

STUMPY is2.0963%worse than prior. Catalogue3TFpatterns/68occurrence records/6realprice match-continuationSVGs; anyTF≥3independentreadyage-matchedanalogues3226/3432. Fallback forecasts included on every V row. MiniRocket fixedrecipe is negative on both assets; actual1932features/TF,5816includingcontext. No retuning.

MiniRocket initially OOM under an inherited650MiB cap, then under verified768MiB. A single focused memory correction chunks existing StandardScaler, preserves float32 transform rounding in a C/f64 diskmap and closes the obsolete owned mapping before unchanged C1/lbfgs1000 heads. Ten focused testsPASS3.981s; synthetic standardized values/probabilities exactly unchanged; stats drift at reduction precision; independent scopedGO. Corrected actual run succeeded at768MiB/swap0/CPU76.331s; root verified19artifacthashes. Both failed attempts preserved; exact original allocation siteUNKNOWN.

RDST completed successfully:512shapelets/TF,1536features/TF,18coefficient/nearest-TRAIN-ID associations; all5959T/3432V IDs match. CPU221.525s/768MiBpeak/swap0, root verified17artifacthashes. All numeric methods are worse than prior; mandatory CNN remains a separate fixed experiment.

CNN completed successfully: both seeds7/42 selected inner-T epoch3 after5epochs, then fresh full-T refit exactly3epochs each;16actualepochs. Mean V loss1.2690942286812104, bothassets worse than prior. No individualseedselection, noVepochchoice/Ureads or memoryretry. Batch32 was a resource-only exception: B128syntheticOOM; B64+AdamstepPASS but736.4MiBpeak left only31.6MiB before actualdata. Root visually checked3TRAINpreviews. Actualfit successful with lastobservedpeak547459072B (~522MiB); finalcgroupreleased, finalpeaknotclaimed. Root13artifacthashes/source/dataPASS.

The frozen comparison returned **NO_ADDED_DIAGNOSTIC_INFORMATION**. Every recognizer is worse than prior; STUMPY/CNN only beat the weaker linear control. All probability arrays are3432×2×3, finite/nonnegative/normalized; both train/validation IDhashes match; saved logloss/Brier reproduced within1e-10. There are48greedy72h-spaced V episodes, not3432independent market outcomes. Class frequencies/calibration/monthly blocks/costs are saved. No new U model evaluation or additional fits; OOF/Optuna/policy work is inapplicable after this failed gate.

The result applies to these fixed recipes and diagnostic labels. It does not show that all price-pattern methods are useless, and it does not estimate an unrun trading candidate's ROI.

## Reproduce and inspect
[S0](s0-completion.md) · [Dataset](dataset-completion.md) · [Numeric controls/STUMPY](numeric-validation-summary.md) · [MiniRocket](minirocket-memory-r2-completion.md) · [RDST](rdst-completion.md) · [CNN](cnn-completion.md) · [Memory review](numeric-memory-review.json) · [CNN preparation](cnn-prepare.md)

Exact argv, source/input hashes, model/probability locations and systemd receipts are in corresponding JSON/manifest files. Scientific source checkpointc1d0c69; originalS0source75ffc9c.

## Qualifications
Historical close execution/slippage/margin assumptions retain NOT_FAITHFUL_DIAGNOSTIC classification; this is not a guaranteed real-venue ROI or certified intrabar maximum. BTC-only reused as a separate pinned control, not independent SOL attribution. Period2024–2026 was already researched; fixedT/V/U controls this procedure, not an entirely unseen holdout. A preflight accidentally printed nested historical BTC-only U drawdown dates; disclosed, not used for fitting/policy. New U details remain unopened until≤3finalistsfreeze. Official JKX supportingZIP403: contents/weights unverified. No new architecture/hyperparameter search.

## Final native baseline drawdown report
One T+V-only pass over840,958 native receipts:19.453s/19.8MBRSS. Top5 nativeW DD:66.256915%,59.842724%,55.100556%,42.172484%,40.268005%. Each equity decline reconciles exactly to Δcash+ΔtotalUPnL. Native actualfill_ns determines BTC/SOL commission intervals; fees are descriptive and already included in cash/W.

The largest event's trough contains a losing SOL-long and a positive BTC-short. Two other deep declines are driven by deterioration of BTC-only open books; another shows SOL-only positive open-PnL giveback. Quantities changed, so endpoint changes are not same-lot causal PnL. Exact per-asset native realized/close-UPnL attribution and signed funding totals are unavailable: those native component artifacts were not saved. No diagnostic ledger was promoted to authoritativeW, no extraS0run and no alternatePnLengine.

[Full common comparison](recognizer-comparison-results.md) · [CSV](recognizer-comparison-results.csv) · [JSON](recognizer-comparison-results.json) · [Calibration](recognizer-comparison-calibration.csv) · [Monthly blocks](recognizer-comparison-monthly.csv) · [Five native drawdowns](s0-drawdown-attribution-result.md) · [DD CSV](s0-drawdown-attribution-result.csv) · [Completion](completion.json)

Final protection check19:30UTC: pilotPID2009732/NRestarts0/active, no FAST-RND units running; diskavailable2,822,889,472bytes. No deployment/orders/restart or Hermes/sites/VPN change. Unique results/rawhistory/configs/pilot assets preserved.
