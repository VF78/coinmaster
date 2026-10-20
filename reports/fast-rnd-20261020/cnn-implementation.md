# FAST-03 CNN implementation ready; no market fit

Only new fast_cnn.py and test_fast_cnn.py changed. Shared reader/metrics reused lazily; importing this module loads neither Torch, STUMPY nor aeon. Fixed renderer and898110-parameter CNN preserve the six-panel/20-context contract. Deterministic train-only previews are exposed by write_previews. No full image corpus is cached.

Each fold has its own purged inner15% epoch selection, seeds7/42, max30/patience2, followed by fresh all-train refit for the best checkpoint epoch count. V never chooses epochs; U is unavailable. Context statistics are fit separately on each phase train partition. Reports match numeric selection keys and average the two seed probabilities.

Nine unique synthetic cases are covered in aggregate: fullsuite8PASS plus1toycalendarERROR, then correctedcalendar1PASS; not a fresh9-case pass. The calendar correction ensures15%holdout exceeds72h; all purge assertions remain. Actual renderer, lazy batching/context, plan-only/nofit/U guard, PNG,898110shape and batch1syntheticbackward pass. No optimizer update or market sample was used. Fullverification12.57s, cap320MiB/swap0 respected. Final manifest/thread metadata guards ASTchecked. Logs/receipts cnn-synthetic-* and cnn-fixture-correction.log.

Defaultbatch128 is preserved; no lower training batch chosen. An explicitly lower batch needs a memory-only reason; caught allocation OOM restarts the same phase/seed at halfbatch. A cgroup-killed process remains a hard failure. Syntheticbatch1 does not establish training capacity.

cnn-implementation.json records exact hashes and ready command. CLI defaults PLAN_ONLY without reading data. Marketfit requires separate rootGO after actual STUMPY, MiniRocket and RDST stages, plus train-preview inspection. No market training, policy search, model/U evaluation, S0change or commonfile edit occurred.

Operational correction: each inner/refit stage emits a flushed timestamped JSON start line; every completed epoch emits seed/phase/actual batch/seconds/train loss/innerT loss to stderr immediately. Existing artifact log captures it. Emitter and EpochChoice2light tests pass; no Torch repeat or fit. Final hashes are updated in cnn-implementation.json/cnn-progress-receipt.json; model/recipe unchanged.
