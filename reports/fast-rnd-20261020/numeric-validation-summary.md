# FAST numeric validation: controls and STUMPY

Completed exactly the authorized prior, simple38 and STUMPY validation stages. Common train5959 / validation3432 IDs match by hash. MiniRocket, RDST and mandatory CNN remain pending; no model selection or trading ROI/DD claim. U outcomes were not parsed/predicted/reported.

| Stage | BTC log loss | SOL log loss | Mean log loss | Fit seconds | Infer seconds | Process maxRSS bytes |
|---|---:|---:|---:|---:|---:|---:|
|prior|1.101263991|1.099908435|1.100586213|0.000447|0.000154|45330432|
|simple|1.298052054|1.427180786|1.362616420|3.731043|0.274184|168304640|
|stumpy|1.119859150|1.127457444|1.123658297|253.620026|66.968051|301105152|

STUMPY mean log loss is 2.0963% worse than the train prior on V. It improves on simple logistic. This is a diagnostic result, not a significance or economic claim.

Catalogue: 3 patterns, by TF {'1h': 1, '4h': 1, '1d': 1}; 68 independent occurrence records across patterns (not deduplicated across patterns). 6 raw-price train-match SVGs; source IDs and genuine hourly continuations reside in catalogue.json.

Analogue coverage >=3 independent ready/age-matched train episodes per TF: [2891, 3010, 2446] /3432, anyTF 3226 /3432. All3432 receive forecasts including prior fallback.

Existing S0 namespace: UID994/G986, PrivateNetwork, ProtectHome, ProtectSystemstrict, pinned minimal5 sourcefiles/lock, dataset+MLvenv readonly; RW own outputs/cache/tmp. Cap768MiB/swap0/threads1/Nice15/CPUWeight10. Exact argv/pins in JSON. Process maxRSS metrics and sampled cgroup peak lower bound are distinct; final transient cgroup counters are unavailable after exit, journal retained.

Outputs: /var/lib/coinmaster-native-gui/data/runs/jobs/cm113-fast-numeric-validation-20261020T173657Z/result
Dataset manifest SHA256 8f51abe51ddb15e95421549279cb8e32121b8797f43e0af9385e6df5e4a7329c
Pilot unchanged: True

No automatic fit rerun, parameter change, data reduction or additional recognizer launched.
