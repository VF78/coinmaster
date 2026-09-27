# Hyperliquid live uncertain-state procedure (#110)

This procedure applies only to a future, separately approved live release. The
current Stage-G worker is Sandbox-only. `RECOVERY_REQUIRED` is a hard stop, not
a request to replay a submit or assume an empty exchange account.

1. Keep live order capability disabled. Preserve the single-owner lock, native
   cache, SQLite journal, logs, release/wheel hashes, and the failure time and
   connection epoch. Do not edit durable state, restart into a new episode, or
   retry an order whose ACK is unknown.
2. Read the selected Hyperliquid account and exact BTC/SOL scope through the
   venue UI and read-only Info endpoints. Record open orders with CLOID/OID,
   orderStatus for every durable order, fills with TID/fee, positions, account
   equity/free collateral/margin, funding and any manual or liquidation event.
   Compare those facts with the native cache, strategy checkpoint and journal.
   A missing, foreign, truncated, stale or contradictory fact leaves the stop
   latched; an empty single Info response is not a complete history cursor.
3. If exposure or an unknown order remains, the owner decides and performs any
   venue-side cancellation or flattening manually, outside CoinMaster. Record
   the resulting venue confirmations and economics. The bot does not infer a
   synthetic fill, fee, funding event, close cause, or automatic takeover.
4. Re-enable only through a separate owner-approved release/startup: exact
   pinned wheel/patch identity, singleton ownership, clean-flat native and
   venue reconciliation, durable terminal outcomes, fresh feeds and a complete
   strict Info generation must all pass. If any item cannot be proved, retain
   `RECOVERY_REQUIRED` and live order capability off.
