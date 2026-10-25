# F3 queue / acceptance contract

**HOLD / STOP before physical3. P0=0/P1=1: TP-QUEUE-01.**

Installed default `use_message_queue=True` makes the required command-caused Updated→same-OID TradeIDfill **before public modify return** impossible for this route. Strategy emits PendingUpdate and forwards; BacktestExecutionClient.modify_order only calls exchange.send. send queues the command and returns; later exchange.process drains it. PendingUpdate is not quantity ACK. A callback reentrant queue drain is not part of the frozen public route.

The outer stock auto-update is different: after its unsolicited Updated callback queues the smaller correction, it resumes immediate fill_limit_order before that queued command runs. With linked targets and fresh crossed depth, whole-position sizing may be executable above a level’s frozen entitlement. This is a source-supported hazard/counterexample window, not an observed native UNSUPPORTED result; exact target/TradeIDs remain untested. Strict boundary assertions may STOP first, which cannot count as PASS.

`use_message_queue=False` is a public configuration, not intrinsically enginepatch or reduce-only-off. But it materially changes the causal behavior that this acceptance condition measures. It needs explicit config-specific stress/acceptance disposition before use; it is not a routine equivalent fix. A FalsePASS cannot qualify current queuedTrue product, F4 or financial prefixes. No silent transport/condition waiver.

Recommended action: preserve both FAILED rows and both remaining approved slots, stop this contradictory F3 before spending, and use the source receipt to decide present-route feasibilitySTOP without claiming actual native UNSUPPORTED. Further optional synchronous discovery needs a concrete revised scoped contract and honest product-relevance limits; inadequate relevant feasibility still blocks productpatch/economics.

Earlier source-plausible/table assessment omitted the public queue boundary between correction call and native execution. This review explicitly corrects that assumption while preserving prior evidence.

Focused sources: strategy.pyx1073–1091/1615–1634; backtest execution_client.pyx130–133; engine.pyx525/2844,3376–3381,3645–3660,5597–5630,7994–8039. Full hashes in JSON. No engine/test/Popen/source/gate/ledger changes.
