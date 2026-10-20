# MiniRocket validation: single attempt OOM

The one authorized unchanged MiniRocket validation attempt failed with unit Result=oom-kill. No metrics, model or probabilities were produced: BTC/SOL/mean validation log loss, prior/simple deltas and final actualTFfeaturecounts are UNKNOWN. Requested recipe2000kernels/expected1932perTF remains a recipe, not an exported successful-result count.

Requested unit cap768MiB/swap0/threads1/Nice15/CPUWeight10. Bounded postfailure readback found inherited cm113-v3-risk.slice MemoryMax681574400bytes(650MiB), so effective upper limit was atmost650MiB. Parent lifetime MemoryPeak reached650MiB; this cumulative peak is not attributed solely to this attempt. No resource limit was changed. Total unit CPU72.317798s; fit/inference timings incomplete/unknown. Last sampled cgroup peak636874752bytes is a lower bound, not a certified finalOOM peak. See retained journal/readback in JSON.

Partial train-transform.npy138630304bytes is preserved. Its file size does not prove complete contents or fitted transformers. Dense feature scaler/LR allocation is a plausible pressure phase, but the exact allocation site is UNKNOWN. No stack inspection or counterfactual rerun was done.

Pilot PID/restart/state unchanged. No rerun, cap raise, tuning, sampling change, RDST or CNN launch.
