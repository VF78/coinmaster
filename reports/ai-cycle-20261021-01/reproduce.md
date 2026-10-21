# Reproduce completed stages
All commands run from an immutable image rooted at:
`/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/ai-cycle-20261021-01`.
Python:`/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-envs/ai-cycle-20261021-01/bin/python`.
Old inputs:`/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/forecast-independent-mac-20261021`.
Set `PYTHONPATH=runtime`; use1thread env and existing `forecast_cycle_guard`.
Source development remains VPS canonical checkout; Mac is an execution image.

Use exact source checkpoint for each completed scientific stage. The current single CLI contains all stage names, but older authorization manifests deliberately reject a changed common CLI.
- Initial profile code:execution-sources/profile-A exact archive; source/code hashes retained.
- Valid UTC diagnostics/A:checkpointa3f1556150a30e17b46a79d1d9785ef7b061a394, same scientific source as68af2f43fca9183fd5ce3060acbce59969657512.
- B:checkpointcb9de4fe683ab95cc7287c73baa20247bbb5068a; exact b-protocol/b-source-input-hashes.
- C:final published branch codex/ai-cycle-20261021, exact c-protocol/c-source-input-hashes.
Never replace the original invalid A quarantine with a rerun or read its quality for selection.

Representative exact single-CLI invocations (PY is the Python path above; OLD is the old input path). Each expensive command requires its saved coordinator authorization and the original source/input hashes; authorization files document historical execution, not permission for new runs.

```sh
PYTHONPATH=runtime "$PY" -m coinmaster.research.forecast_cycle_run diagnose --report reports/ai-cycle-20261021-01 --old-job "$OLD"
PYTHONPATH=runtime "$PY" -m coinmaster.research.forecast_cycle_run prepare --report reports/ai-cycle-20261021-01 --old-job "$OLD" --warmup reports/btc-split-sol-cover-20261018 --output prepared-full
PYTHONPATH=runtime "$PY" -m coinmaster.research.forecast_cycle_run controls-utc --report reports/ai-cycle-20261021-01 --old-job "$OLD" --prepared prepared-full --output controls-utc --reuse-controls controls/controls.json --fit-authorization reports/ai-cycle-20261021-01/coordinator-utc-diagnostic-go.json
PYTHONPATH=runtime "$PY" -m coinmaster.research.forecast_cycle_run stage-A --report reports/ai-cycle-20261021-01 --old-job "$OLD" --prepared prepared-full --output stage-A-utc-corrected --resource-decision resource-admission-utc/resource-admission.json --profile profile-A/profile.json --fit-authorization reports/ai-cycle-20261021-01/coordinator-stage-a-utc-go.json
PYTHONPATH=runtime "$PY" -m coinmaster.research.forecast_cycle_run profile-B --report reports/ai-cycle-20261021-01 --old-job "$OLD" --warmup reports/btc-split-sol-cover-20261018 --weights kronos-weights --output profile-B --fit-authorization reports/ai-cycle-20261021-01/coordinator-profile-b-go.json
PYTHONPATH=runtime "$PY" -m coinmaster.research.forecast_cycle_run profile-C --report reports/ai-cycle-20261021-01 --old-job "$OLD" --warmup reports/btc-split-sol-cover-20261018 --output profile-C --fit-authorization reports/ai-cycle-20261021-01/coordinator-profile-c-go.json
PYTHONPATH=runtime "$PY" -m unittest discover -s runtime/tests -p 'test_forecast_cycle*.py' -v
```

The immutable output directories refuse overwrite. Reproduction requires a fresh isolated destination and a newly reviewed authorization; these lines document the completed stage, not autoexecute it.
For EXACT argv, wrappers,wall caps, all family-isolated old inference, profiles and mechanism command, use [executed-commands.json](executed-commands.json). Guard form:
`"$PY" -m coinmaster.research.forecast_cycle_guard --job executions/STAGE --wall-seconds CAP -- "$PY" -m coinmaster.research.forecast_cycle_run STAGE ...`.
Caps:stage-A original/corrected authorized remaining wall; B300s; C300s. Old-weight inference was split into isolated family processes; controls-utc reused3saved positives and retrained only6negatives; old fit validation reused506/512 predictions/method and inferred6new each.

Reuse existing base environment read-only via isolated new environment .pth; pinned new dependencies/actual versions in dependencies.json. No Torch redownload or base environment modification. Original HFweights are Mac runtime artifacts; b-provenance.json gives exact original revisions, download URLs/SHA. Vendor files are byte-exact pinned official source and MIT license.
