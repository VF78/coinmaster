# Independent saved-output verification contract

Prepared from the prior frozen B result/receipt schema only. No new output is inspected before the owner/root announces completion and hash freeze. No native engine, data fetch, SSH or product action is used.

P0 checks exact economic parity with frozen B: TOTAL4622034.27336437, native commissions592090.31669918,484native fill rows (BTC322/SOL162), settled DD57.58541045962226379114466259%, zero liquidations and native terminal exposure/orders/pending flat. Normalize nondeterministic identity fields explicitly and compare native fills/orders, fill audit, native cash and funding signatures. Compare shared semantic config and explicit new inactive research fields; do not require the old configSHA or unchanged implementation hashes. Require new source/config/input identities to match owner preparation and frozen files. Source correctness review belongs to the other reviewer.

Each complete candidate is audited once from its result/raw-native JSON, actual native CSVs, preparation/completion evidence and settled receipt trace. Independently sum commissions and notional from native fill audit and native report commissions, prove terminal inventory flat, compute descriptive closed-inventory signed fill cashflows and the unallocated cash bridge. Signed funding stays UNKNOWN unless a genuine signed native mutation field is present and reconciled.

One decompression/streaming pass per completed settled trace computes the original global-seed maximum DD, peak/trough/recovery, all global-peak excursions reaching30%, calendar-month native observed equity starts/ends and local DD, sample/receipt continuity and unavailable-receipt reconciliation. Preterminal observed equity and post-boundary native terminal cash stay separate. Missing receipts produce a lower-bound DD qualification and cannot support a positive50/90claim.

Acceptance uses `(TOTAL-10000)/(6077107.23887483-10000)>=.9`, full settled global DD<=.5, zero liquidation, complete evidence; exact threshold5470396.514987347. Cash drawdown, local peaks, fixed windows and apparently flat post-liquidation periods are not substituted for the gate. No threshold tuning or replay of hypothetical decisions occurs.

Helpers and outputs use only verifier-* in this report folder. Root owns comparison/report/Project. Owner owns the run ledger and owner-* exports. After P0 parity is reported, wait for root's final-batch completion notice rather than repeatedly polling or rereading incomplete traces.

Preparation readback: sourcebd04c9b3858bcda40060a08eff488849c69af5d8; owner ledger had0physical attempts. P0 expected configSHA is in fact exactly old B06c9e99ce88bed050a62ac38cb9c0370cde35ce8c990582b888c06e68bcf53ea, so exact config semantics/hash are required for this prepared P0. No source review or run approval is implied. verifier-saved.py is prepared; syntax and the old saved B finite-fee/flat-inventory ledger check pass. It has not traversed any new trace.
