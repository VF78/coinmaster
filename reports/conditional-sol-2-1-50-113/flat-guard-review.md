# Targeted ordinary-TP-flat authorization review

**GO for one replacement native economic run of the same candidate.** No optimization/live/economic approval. Initial reviews and invalid-run evidence are preserved.

Root cause confirmed: both candidate/control firstBTC parent and Sep6TP3 fill agree; protection was already OFF/flat. The prior conditional no-delta/nativeflat hook created groupclose authority, clearing the retained episode without REGIME/TRAIL/CLOSE_ALL and admitting the extra Sep7 parent. That implementation defect invalidates run2a as requested-strategy economics, despite truthful native fills/cash/liquidation.

Exact correction changes only conditional_hedge.py and native test. At module212-213, nativeflat reconciliation now requires existing _group_close_reconciliation_pending; it cannot create that authority. Existing authorized cleanup still calls the established reconciliation path. No prices/quantities/signals/fees/matching changed.

Read native regression evidence:3passed3.27s across REGIME/TRAIL/CLOSE_ALL. Real protection OFF then actualBTC_TP3 flat retains the same episode, leaves groupclose flag false and produces no new BTC_ENTRY on subsequent domain decision; later explicit authorized close clears it. Additional real quotes permit existing accepted TP leaves to complete; no liquidity/matcher edits. Test log hash, patch and all eight current source pins independently verified.

This resolves the specific firstpermission-divergence mechanism. It does not prove the entire historical BTC path restored; verify firstnextentry/permissions/acceptedvolume after the replacement. Invalid receipt, frozen job/result/funding/trace and rootcause remain unchanged.

PatchSHA256: 0c55b5d14bc56ae1f2517872d0eaa84e97ab6ba3cb803d3c41cb331714ec2848

Exact eight final pins: flat-guard-review.json. No reviewer core/index edit, test rerun or fullrun.
