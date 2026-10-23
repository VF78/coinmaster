# Independent C1 source / money review

**GO for final frozen source `78100d4d69a12144a92dbb9a713b7a7f7ce2f54d`, following the observer-only amendment to reviewed implementation `69e72cd29d83ed7782bc467c92a1b2c56d8d1fcf`. No unresolved scoped source blockers. This is not authorization to launch a historical engine and is not economic acceptance.**

One scoped review of the actual canonical VPS worktree, its native integration against exact E4 `bd04c9b`, and the focused correction delta in the same development pass. Final canonical HEAD, clean worktree, seven changed files (+652/-19) and all seven SHA256 hashes were independently read through SSH. Contract SHA8214eb8a remains the accepted economic rule; the abandoned5% stress controller is absent. No reviewer product edits or test reruns occurred.

## Native money timing and causal execution

The observer's existing delayed receipt boundary remains authoritative: finalize at custom-data entry, strictly after source quote time, invalidating intervening fill/account mutation and requiring stable fill epoch. C1 runs only after settled curve/write/count/pending-clear commit and uses frozen source-bundle marks and native position UPnL. It does not compute alternative PnL or submit an order from that delayed callback.

The receipt callback can claim/freeze a target only. Actual cut/restoration dispatch occurs through the existing native quote callback and `_submit_intent` with that quote's bid/ask and `ts_now`. A cut requires executable quote ns strictly greater than claim receipt ns; restoration requires quote ns strictly greater than the qualifying closed4h bar. Checkpoint source/receipt/epoch, current account mutation, mark age, current executable reclaim and normal native increase admission are rechecked. No delayed custom-data market submission against an old source L1 book was found. The completed4h interval must open strictly after both last actual cut fill and cut terminal resolution; incomplete/overlapping candles cannot authorize restoration.

## Quantities, rights and priority

One fixed half-of-actual-held-native-lots cut target and one restoration attempt are scoped to the actual domain group. Submitted targets/ACKs do not become credit. Partial protective fills create only actual native-lot credit and actual fill VWAP. Canceled leaves do not retry. Dedicated C1 fills bypass normal BTC_ENTRY/BTC_REDUCE/SOL_ADD domain effects, so original initial targets, PLANREF/H, SOL consumed notional, clocks/sigma and existing earned-right history retain their roles.

BTC actual cut fills proportionally move surviving original level lots into `btc_risk_retired_lots` and the separate restorable bucket; actual restoration returns only those lots. Original filled TP history is not rewritten. SOL maintains native-lot level attribution, removes/restores actual cut-lot credit, and does not refund original add consumption. `restore_committed` bounds actual late restoration fills even after unused credit is revoked, so the native exposure remains reconciled rather than undoing a fill. Rights receipts now include SOL fractions and held-lot attribution.

All ordinary group increases are held during C1 ownership. Independent ordinary exits and mandatory regime/trail/liquidation/timeout/terminal paths revoke unused credit and retain priority. Unknown ACK/cancel ownership remains in the existing pending map. Passive BTC TP coverage is technically canceled only for non-overlapping ownership, then surviving original native BTC leaves are requeued after cut/restoration terminalization, including SOL-selected interventions and zero-fill cuts; actual BTC-flat does not regenerate phantom leaves. Relapse cannot recut in the same group. A genuine group clears only after native positions/orders/inflight, pending and queued work reconcile flat; global H persists.

## Findings closed within the same focused pass

1. **Local restoration admission denial:** earlier code consumed the attempt/released the hold before a real native submission. Final source preflights native minimum/readiness/tier admission, clears failed confirmation and stays HELD on a pre-submission denial. Native order identity is bound at the existing submission boundary; an actual submitted native denial/rejection remains an attempt.
2. **Lost ordinary TP coverage:** earlier cancellation removed native BTC resting exits while HELD, including after zero-fill cuts. Final source requeues actual surviving BTC TP leaves after cut/restoration resolution for both selected assets. Retired lots remain excluded until actually restored.
3. **Duplicate fill epochs:** the observer previously incremented before the strategy's duplicate guard, creating a permanent controller/recorder mismatch. C1-only duplicate filtering now keeps the two epoch domains aligned without weakening snapshot mutation checks.
4. **Mandatory SOL timeout continuation:** earlier direct timeout dispatch could clear the mandatory slot and then be blocked by an unresolved C1 child, stranding the exit. Final source waits for C1 ownership to resolve before clearing the slot. The native delayed-child fixture proves real cancel followed by actual SOL timeout exit.
5. **Terminal token/hold proof:** terminal order callbacks take a separate early return from ordinary group close. Final source explicitly clears C1 at terminal native flat only with zero positions/orders/inflight/pending/queued work and exports `c1_terminal_state`; no later receipt is needed. Boundary cash settlement is unchanged.

## Validation and practical limits

Owner reported final focused C1+precision18PASS/3.36s and a final targeted genuine-group-reset/mandatory-timeout/terminal-flat3PASS/2.16s, plus diff-check PASS. The earlier full relevant pass was206PASS with two known inherited E4 clock cases excluded, before the final ownership delta; it is not represented here as a full-suite pass on the final hash. The final delta has focused native coverage. Reviewer read actual fixture source and exact test-file hashes, and did not rerun the owner's tests. Archived command/result receipt linkage is maintained by the owner.

The fixture uses actual native entry/fill/forced-flat flows in two genuinely distinct domain groups and verifies a new claim with preserved global H, rather than only changing a SimpleNamespace identity. Other inspected fixtures exercise both asset cut/restore paths, native partial and zero fills, denied/rejected cuts, restored passive TP coverage, local admission denial, stale/current quote gates, duplicate fills, mandatory continuation and terminal no-hold proof.

Default is OFF. Only E4 plus the separately identified report-only Decimal precision correction and C1 wiring are in scope. Exact runner/config/input freeze, independent saved-output validation and a separate root historical-launch GO remain required. Physical full historical attempts started by this reviewer:0. No S0/E4 rerun, services/pilot/orders/deployment changes occurred.

The current-loss gate, DD40/35 band, half cut and4h reclaim are unproven policy hypotheses. The June original-path false positive remains, selected loss is not joint insurance, changed capital can create other drawdowns, and a one-cycle relapse may breach50. TOTAL/DD remain UNKNOWN until valid native results. No live or hard-DD guarantee is implied.

## Final observer-only pin amendment

Final canonical HEAD `78100d4d69a12144a92dbb9a713b7a7f7ce2f54d` and clean worktree independently verified. The narrow69e72cd→78100d4 source delta only records already-computed current quote, E/H/DD, receipt/current epochs, account event time, ownership counts, cut VWAP/timing, native submission outcome and actual-fill prior credit. No trigger, target, admission, order or state transition changed. Focused fixtures add witness assertions; economic code remains the reviewed implementation. Source GO transfers to78100d4; no further broad review or rerun was performed.

Read archived `owner-tests.json` and `owner-tests.log`: exact final-source focused18PASS/3.47s; prior ownership guard3PASS/2.16s and206PASS/2deselected retain their stated earlier-source qualifications. The two deselections are `test_btc_entry_local_denial_and_native_zero_terminal_are_distinct` and `test_unknown_ack_stays_pending_until_proven_zero_or_partial_terminal`; inherited exact-E4 clock proof is `reports/e4-budget-tp3-20261023/owner-base-clock-proof.json`. They are not silently counted as final-source passes.

Final seven source/test hashes are pinned in reviewer-source.json and match owner-source-preparation.json; the two changed hashes were independently read from canonical78100d4. Source manifest92files is owner-pinned SHA256da3f2efcddba5901ac2ed930a947ec8c1645d45bcd5a18e210af5e5e5581b960. The archived test receipt SHA256 isd2a73642de5003405cb22330e3511109148c3ed2646bc7bc42826567fc4aaa72. Root still owns the separate historical launch decision.
