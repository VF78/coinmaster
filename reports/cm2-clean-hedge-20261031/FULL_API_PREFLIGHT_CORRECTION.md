# Full API launch correction

Original CM2_ANCHOR_JOINT remains failed/spent: OS1, zero native constructors, no economic trajectory. It omitted qualification_quantity_model and inherited legacy_bybit, correctly rejected by unchanged EXECUTION_DIAGNOSTIC_CURRENT_HL_NO_DP_ONLY guard. No guard, DP setting, risk rule, policy or venue metadata is waived.

Worker and probe now share full_native_kwargs with execution_diagnostic, hl_current_usdc, DP metadata/runtime/readerNone/accountIDempty, canonical10k/24month interval and existing currentHL profile/fees. Only artifact_dir changes for the probe.

Full stages now preflight the actual native_baseline API in a separate explicit secretless -B -s probe child. It reaches the real constructor boundary through public data/funding/profile/fee resolution, intercepts BacktestEngine before construction, requires exactlyone boundary, captures approved actualmode/quantitymodel/USDC/fees/profile/source/seed/dates only, and restores the engine symbol in finally. Probe IO is a unique sibling api-probes directory, never the case directory. Failed probe evidence cannot be replayed/overwritten. No attempt is registered and no shared economic lease is consumed for constructor-free probes. Real attempts retain the existing globalFD/ledger gates.

The new constructor-free tests prove explicit guard compliance, identical shared kwargs except artifactdir, safe probe launch flags/env, interception/restoration protocol and failure rejection. Mock protocol tests are not an actual public-data-pipeline receipt. The actual frozen Mac preflight must generate api-boundary-proof.json with statusACTUAL_API_ENGINE_BOUNDARY_PASS, calls1, constructors0 before root may authorize CM2_ANCHOR_JOINT_R1.

Command is unchanged: PYTHONPATH=<newimmutable-runtime> <pinnedpython> -B -s -m coinmaster.research.cm2_runner --request <CM2_ANCHOR_JOINT_R1.json> --resource-receipt <rootGOreceipt.json> (without --run). Full preflight now invokes the real boundary probe; --run invokes the same successful preflight before ordinary registration/child dispatch.

Budget remains engineering2/4 and anchors1/4failed, total3spent. The remaining3 anchors are repaired nominal, BTC_ONLY and BTC_TRIM; load6 is dropped. No native retry was performed by the author. Fresh-only research/restart unsupported boundary remains unchanged.

Each CLI invocation uses a new UUID probe directory. A separate no--run preflight followed by --run cannot collide with earlier probe evidence; it deliberately repeats only the constructor-free public-data pipeline and trusts no stale cached proof. No physical attempt is counted for either probe.

Immediately after native worker Popen, native-child.json exclusively records actualworkerPID,parentPID,runID,requestSHA,spawnUTC/statusRUNNING. It contains no args or environment. A separate native-child-terminal.json preserves finalstatus/exit/elapsed/per-PID peakRSS while the original spawn record remains immutable. os.wait4(nativePID) supplies that worker's rusage, excluding any earlier probe child; Popen.returncode is set from waitstatus before later poll/wait.
