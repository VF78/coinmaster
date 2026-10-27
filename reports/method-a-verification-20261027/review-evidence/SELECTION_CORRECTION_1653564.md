# Selection receipt correction closure

**0 P0 / 0 remaining P1 in the single producer finding scope.** Frozen `16535643908404237da124ca1b57eb3f6f9f4ff9` corrects `9c74cc4637335c787395eefca89cfb8961ccf593`.

Every actual consumed PairedSignal now emits RISK_SELECTION_INPUT with the raw dataclass fields, stable input_index and actual receipt timestamp_ns. The existing qualifying-row branch records the receipt sequence as selection_ref; common risk and paired rows propagate it. Parent reset and invalidation/expiry clear the ref alongside the existing selected row. The controller's selection eligibility/branch/threshold logic is unchanged. This closes omitted intraday and dropped earlier-valid selection causality without changing money or admission policy.

Inspected the new focused test at frozen68df checkpoint: it invokes the actual bound _mr_quote with two intraday rows, observes both raw receipts and verifies the transition selection_ref points to the later used row. Owner's14 focused engine-free tests reported PASS; reviewer did not rerun native-object tests. At68df the chosen entry additionally preserves entry_selection_ref in its reported entry_basis. No native imports/constructors/runs or source edits by reviewer. Prior closures remain closed; actual runtime/consumer/financial qualification and root run authority remain separate.
