# Stock stress amendment review

**FOR_OWNER_CONSENT_ONLY. P0=0, P1=0.** Reviewed protocol SHA `6f89de510dc9550bdd998dfd9d8b2889d590969d1307ddb2bc920ae4546acdda`.

**TP-STRESS-01 CLOSED, line19:** final wording replaces “возможного непосредственного native исполнения” with mandatory positive actual execution: the same corrected OID must have a genuine native fill/TradeID after its valid Updated and before that public modify returns. Require fresh available liquidity, unchanged limit price and pre-fill frozen entitlement, with the command/callback causal trace. No such observed execution means NOT_PROVEN/STOP. A normal TP fill or a merely potentially executable modify is insufficient.

The new test route is source-plausible: public linkage to an existing genuine position makes remaining TP1/TP2 eligible for native auto-resize after a TP fill at bid104; bounded same-OID correction can enter the native marketable-update branch, which emits Updated then invokes immediate fill. This removes the prior unlinked-route obstacle. Actual ordering, safety and convergence remain unproved and may legitimately STOP; no PASS is promised.

Lines15–22 preserve the API-only stress/product boundary and exact entitlement/unsafe-window safeguards. Lines26–29 correctly propose total4, comprising two retained FAILED attempts, existing physical3 and only one new physical4. The required concrete integrated plan must fit before spending; absent coverage means STOP. Prefix3 remains separately conditional. Product linkage is unchanged, and no old budget or hidden reserve is admitted.

The single wording correction is verified and closed. Initial protocol SHA `7109246a0451d08ae3e4e475bd8fdedd0ef2277aaff484af3cab117408e283b0` is retained in the JSON. Current authority remains max3/HOLD; this review grants no code, native, publication or economic permission. No engines/tests/Popen/source/ledger/gate mutations.
