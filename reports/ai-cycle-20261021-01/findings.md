# AI-CYCLE-20261021-01 — bounded result
Date:2026-10-21; all boundaries UTC. Branch:codex/ai-cycle-20261021.

Overall **TARGET_NOT_MET**. A and resumed C are valid fixed-recipe negative results. B remains **UNASSESSED_RESOURCE**: its full forecast quality is UNKNOWN. C completed after the owner explicitly raised its budget to120min. No model/policy admitted, no new March/CHECK assessment, no native runs, no live changes.

|Curve|TOTAL|Native-phase MaxDD|Agreed money-projection MaxDD|
|---|---:|---:|---:|
|Archived S0, reused|6,077,107.23887483|66.3187802497%|66.2569148647%|
|New candidate|UNKNOWN—not admitted|UNKNOWN|UNKNOWN|
|Acceptance|>=5,470,396.514987347|<=50%|reported separately|

S0 archive was not rerun. Its money observer/execution/fees/funding/leverage remained unchanged. No counterfactual return was invented.

## Valid A result
Joint numeric state has750 causal float32 columns, two assets and15m/1h/4h real bars. X_shape124 is the fixed ablation. Depth6 was dropped for measured resources before quality. Heads D/Q-long/Q-short and baselines are independent; no calibration/threshold sweep.

|Asset/head|Mean loss minus prior|Paired95%CI|Status|
|---|---:|---|---|
|BTC D|+.002766761|[-.006398731,.012516628]|NO_SKILL|
|BTC Q-long|-.000365195|[-.005371470,.004728226]|NO_SKILL|
|BTC Q-short|+.000065231|[-.002820038,.002541470]|NO_SKILL|
|SOL D|+.008841694|[-.005820068,.024907241]|NO_SKILL|
|SOL Q-long|+.000955728|[-.001348023,.003297203]|NO_SKILL|
|SOL Q-short|-.000250220|[-.004132235,.003321337]|NO_SKILL|

All heads beat weak linear losses but fail the prior requirement; neither D passes the UP+DOWN rank gate. Full same-ID fold/month/side/q/reliability metrics,7/28day sensitivity and raw/projected outputs are in [valid A artifacts](mac-artifacts/stage-A-utc-corrected/). Main uncertainty uses21 common14day blocks,1000draws,seed7; these are forecast-loss CIs, not economic CIs.

A performed102 valid development fits. Original102-fit A attempt had a timezone defect; all its quality remains UNOPENED/QUARANTINED on Mac. The narrow UTC correction and authorized same-recipe replay retained all wasted cost. No old model was retrained. [Diagnostics](diagnostics.md) distinguishes actual TRAIN sample gaps, ES gaps, cap limitations and UNKNOWN old curves.

## B resource stop and C120 completion
|Stage|Actual guarded scientific wall|Measured peak RSS|Complete required projection|Decision|
|---|---:|---:|---:|---|
|Stage0|214.390s plus short fixtures|receipts per job|<30min ceiling|diagnostics complete|
|A incl profiles and invalid attempt|1202.245s=20.037min|849,362,944bytes valid A|admitted fixed development|all6 NO_SKILL|
|B pilot|38.746s|472,481,792bytes|823.9686min incl heads/margin|INCOMPLETE_RESOURCE|
|C original pilot|56.586s|558,120,960bytes|96.3559min under original90min ceiling|historical INCOMPLETE_RESOURCE|
|C resumed development|655.586s|1,071,497,216bytes|120min owner ceiling;97.6934min full conditional projection|all6 NO_SKILL|

B original small/tokenizer weight SHA matches June2025 revisions. Paper AppendixD reports pretraining endsJune2024; public release after some TRAIN history is disclosed. Current MIT metadata corrects original Apache metadata without weight changes. Code/weight/license/provenance receipts are pinned.
B kept16 independent sample_count1 paths, CPU1thread, own-asset80h OHLC with zeroV/amount,24h horizon. Six asset-generations (3paired origins,96paths) suffice for frozen early resource stop: fastest warmed pair11.9166s excluding startup/firstpair; required3120paired origins/99840paths alone project619.6635min. No outcomes/head fits opened.

C fixed32/32/depth6, batch16,lr.001,maxlength256,600iter,seed7. Original90min protocol/resource failure is preserved. The owner raised only C ceiling to120min; no new pilot, recipe or threshold search. Resume admission reserved97.6934min including prior actual profile,13remainingencoders, all144714causal cache timestamps, required heads/refits/final baselines, preparation and20%margin.
C development completed6 prefix-specific ES/full encoders and36 independent CatBoost fits. Scalers/ESencoders see only the past before the28dayESboundary; full-prefix refit encoders are separate. A prior/linear/joint forecasts were reused on54 identical ID groups without fitting A. The saved March2026 encoder/scaler hashes are unchanged and were not retrained or used to predict development.
|C asset/head|Mean loss minus prior|Paired95%CI|Status|
|---|---:|---|---|
|BTC D|+.003189883|[-.007431999,.014070846]|NO_SKILL|
|BTC Q-long|-.001851392|[-.006850752,.003034891]|NO_SKILL|
|BTC Q-short|+.000828984|[-.002774042,.004206928]|NO_SKILL|
|SOL D|+.009967043|[-.007980058,.029531778]|NO_SKILL|
|SOL Q-long|-.000589849|[-.002975505,.001351099]|NO_SKILL|
|SOL Q-short|-.000011989|[-.002753710,.002620788]|NO_SKILL|

Both D rank gates fail. All6 heads improve over the weak linear baseline but fail prior confidence; paired comparisons with unchanged X_joint are also saved. BTC Q-long improves point loss vsjoint in3/3folds, but main14day95%CI still includes0; no gate was relaxed.
C actual guarded total including original profile:712.1719s=11.8695min. Conservative90s preparation reserve leaves6397.8281s unused; unused budget does not authorize a new recipe/search. No final/quarterly models, policy, March/CHECK or native work follows a failed gate.
[Valid C artifacts](mac-artifacts/stage-C-development/) include raw/projected forecasts, truths/bounds/IDs, metrics by fold/month/side/q,21common14day blocks plus7/28day sensitivity,6 encoder caches/gradient histories,18headweights, model/source hashes, resource/restore receipts and coverage. Each asset has2184/2184/2160eligible rows;24fullyobserved tail rows/fold are boundary-purged, distinct from actual data-censored0 and feature-abstain0.

## Mechanisms, policy and forward state
[Saved native state screen](mechanism-screen.csv) scanned3,153,600 states.573 BTC price/timing crossings include301 on originally profitable trades and2 crossings before first50%DD; ordinary-branch availability remains UNKNOWN. Recorded SOL-right activations do not reconstruct the complete predecision domain. All counterexamples and missing-state reasons remain in the CSV.
First native DD>50%:2024-10-03T09:01:00Z. Genuine hourly June–August warmup exists, but minute/15m history startsAug31; no mature24h head fit is available atSep1. Overlay retaining earlyS0 is excluded by its early DD; a BTC-only early-flat curve would require its own evaluation.
No restorable paired action branches exist: **ACTION_VALUE_UNIDENTIFIED**. No EV replacement, simulator or S0 fork was built. Forecast targets are not action-value targets.
[policy.json](policy.json) and [policy-screen.csv](policy-screen.csv):SKIPPED_NO_ADMITTED_MODEL. Empty shortlist; zero native slots used; absent returns/DD remain UNKNOWN.
[forward-log-manifest.json](forward-log-manifest.json):NO_ADMITTED_MODEL; actual report seal time, no model seal and no future origin/forecasts. No daemon/service was created.

## Reproduction and artifacts
[Commands and source checkpoints](reproduce.md); [dependencies](dependencies.json); [resource accounting](resource-accounting.json); [artifact hashes](artifact-hashes.json).
Single CLI:coinmaster.research.forecast_cycle_run; existing guard enforces one process, CPU1thread and3GiB. Guard launch receipts contain exact executed argv. All source changes originate in canonical VPS checkout; heavy execution used isolated Mac images.
Protected pilot final read-only identity receipt: [protected-pilot-final-readback.json](protected-pilot-final-readback.json), active PID2009732/NRestarts0 unchanged; identity preservation only, no new lifecycle acceptance.
Original source HEAD31dc0a6b5380ee60ea5cfa3f9189a1d830e352d8, auditbase85fdd78ce248e56d35dc62563a7cdf4f2c100cca; initial difference docs-only3files. Old reports/pilot/product checkout untouched. C resume source checkpoint1e01cc744bf0ed7c97ef05b7a8a217d445df2103 follows canonical resumeHEAD1733c072b8b928ac04f784d91d16ff57248ab925.
Initial new-research tests:9PASS,2.541s. Resume-focused causal/prefix-scaler/alignment/roundtrip tests:2PASS,3.249s, no learned fits. No redundant post-result test/fit reruns. Artifact CSV/gzip/hash/readback QA recorded in final-qa.json.
Bounded cycle finished; no further automatic search/resource increase or active job. Admission blockers: A/C fixedforecastgates fail; B remains resource-unassessed; native predecision/paired-action state missing. Project status/publication are coordinator-owned.
