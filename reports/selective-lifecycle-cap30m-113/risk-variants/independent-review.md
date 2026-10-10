# Independent narrow review: GO

Frozen source: `498a8fe0d62cac5cea00e81660195f7e9c3e0131`, reviewed against `cccfb4b` in the canonical VPS checkout `/root/.openclaw/workspace/coinmaster/coinmaster`.

Scope: three changed source files and two focused native test files only. No source edits, test reruns, control replay, economic replay, pilot/service/order/credential action.

No blocking defect found for the two separately authorized research runs.

- SOLCAP6 bounds aggregate current native held SOL plus each normalized add using fresh BTC/SOL native marked equity, actual instrument taker fee, and conservative execution/mark gap reserve. Outstanding SOL opening orders and pending native SOL submissions block duplicate admission; retries recompute current exposure. Existing H/reference and trading rules remain intact; no forced SOL reduction.
- PORT45 samples paired marks, uses existing native forced market exit and cancellation reconciliation, blocks entries/increases while latched, requires actual native position/order/pending-submission flatness and a later daily decision producing a distinct genuine domain BTC episode. Protective peak resets to flat native cash only. Daily signal history continues and observer global curves are never reset.
- The minute observer captures held exposure, native equity and OHLC before protection acts. The focused native stop-bar test proves retained 5405.05 pre-action equity and 5315.05 adverse envelope even when cancel confirmation closes against the previous native book. This existing diagnostic matching limitation is explicit in result metadata; no venue fill fidelity or guaranteed global <=50% drawdown claim.
- Defaults are inert; mutually exclusive candidate validation prevents a combined variant. The CLI currently requires the minute observer for both candidate flags, a harmless stronger research invocation requirement for the approved observer runs.

Focused receipt inspected, not rerun: VPS `/tmp/cm113-risk-variant-tests.log`; SHA-256 `0845194231c3c39f5c868d78463c63cfbf34a0bd3cebda3df6440d2f2789fce3`; `116 passed, 114 warnings in 69.64s`. Reviewed native tests include disabled protection/default SOL paths, both SOL directions, fee/mark-gap lot boundary, stale/future marks, partial fill retries and duplicate submission, partial close retries, delayed native opening ACK cancellation, same-regime next genuine episode and two successive protective epochs.

GO is limited to separate bounded research comparisons from this frozen source. Economic effectiveness remains unmeasured.
