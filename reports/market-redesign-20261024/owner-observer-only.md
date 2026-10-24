# Terminal-flat observer correction

Current source `ec2a958e383a53133f8a8d03ef0e312810881265`, parent `e089f5798a46daed433c0627658604d0dff031a5`. Runtime tree `62b038ea7a8bdcb877dfd573a2764e8d23098777`. Isolated VPS worktree clean. Root explicitly approved only this observer correction after diagnosing batch1; no second financial correction was made.

Batch1 original artifacts remain unchanged at `/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/market-redesign-20261024/short-batch1`. Cases48/65/81 canceled remaining native TP orders and filled the existing native terminal close at the exact same timestamp:

| Case | Native cancel/close timestamp ns | Actual remaining BTC = terminal fill | Native final state |
|---|---|---|---|
|48|1760659200000000000|0.410|0 positions,0 open orders,FLAT|
|65|1775260800000000000|0.677|0 positions,0 open orders,FLAT|
|81|1787097600000000000|0.472|0 positions,0 open orders,FLAT|

The original observer started TARGET_CANCEL_ACK at that boundary and never closed its interval. Actual orders CSV contains only terminal FILLED/CANCELED states; exact terminal fill quantities consume all native remaining inventory. No positive elapsed unresolved exposure was found in this native event sequence. Case31's ordinary REGIME path already closed its observer interval through `_reconcile_group_flat`.

Cause: terminal fills use the early `_terminal_order_ids` callback branch and `_reconcile_terminal_flat`, bypassing `_reconcile_group_flat`'s existing observer completion. Minimal diff: **after the unchanged native-flat/pending guards and `status="FLAT"`, call `_md_coverage(clock, True, episode_id, "NATIVE_TERMINAL_FLAT")` when real-U is enabled**. The3 added product lines modify only observer interval/counter/audit fields; no order, quantity, decision, guard or return changed. Effective IOC metadata remains qualified exactly as before.

One new genuine native terminal-boundary regression passed on VPS(4.83s) and on the new readonly Mac snapshot(1.77s). It verifies the actual same50BTC native close fill, one existing terminal close order, all-flat cache, unchanged prior entry fills, zero open observer interval at the actual terminal-fill timestamp, and idempotent repeated flat/report callbacks. The previous18/135 suites were not rerun because no financial state/control flow changed.

New readonly snapshot: `/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/market-redesign-20261024/source-ec2a958`. Exact updated source hashes and commands are in `owner-source-receipt.json`, `owner-commands.json`, `owner-short-commands.json`; the short outputs now target fresh `short-batch2/{31,48,65,81}`. All three resolved-config files and their canonical SHA remain unchanged. Root owns the remaining four corrective short launches. Executor historical launches0; root batch1 launches4; full attempts0/3. No full GO or economic acceptance is implied.
