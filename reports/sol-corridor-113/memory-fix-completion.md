# Memory fix completion

Research-only source frozen at base 7d08522a4beae4432387455b91f468f564c0eccc; reviewer GO. No economic repeat launched (0/1). Trading/domain, BTC/SOL policy, executor, fees, margin and funding sources are byte-identical.

The reproduced cause is completed-history retention in both Python audit collections and native order/account/NETTING histories. clear_data clears market batches, not those histories. The exact original OOM allocation remains UNKNOWN. At3,000 native fills the original fixture retained25.07MB traced heap, including10.03MB known Python audit collections; tracing itself inflates RSS.

The new327-line research helper archives exact emitted audits, dedup membership, mutable contexts and native reports to fresh SQLite (FULL/DELETE). It commits before supported terminal-only purge; all open/pending/protected references and native active position history remain. Current native cash and deferred receipt policy are unchanged. The existing stream now archives every15minutes (70,080chunks/24m), with unchanged four source cursors. Final native CSV export uses256-row chunks and fsync, and large arrays become explicit SQLite references, never empty replacement histories.

30,000 real fills: cash9700/native fees300;30,000 orders,30,001 account events,15,000 closed lifecycles,45,000 emitted risk rows and30,000 fill rows preserved. PSS10k360.15MB→30k365.15MB; export369.07MB PSS/386.08MB RSS. Elapsed828s (36.23fills/s). This load predates only the final stricter guard/counter/fsync/reference amendments; no30k repeat was run.

Current-source open-position stress preserves all3,000 native fill events: PSS349.34MB/RSS366.20MB,9s. There is no supported open-position-history purge. Thus active-lifecycle memory remains a disclosed residual, not a fabricated constant bound. Control max holding durations15.82d BTC/14.01d SOL are observations only.

Verification:50 connected PASS/6 fixture failures, then11 subset PASS/1 fixture API failure, then the final healthy native-reader case PASS. All56 unique cases covered; NOT one fresh56-case PASS. Runtime unchanged during fixture repairs. Tests cover actual monetary/rights/native report parity,2-cycle OFF/healthy ON, Q2/UNKNOWN, late partial/cancel, exact duplicate, deferred receipt, partition7/60/400, closed NETTING protection and inner/outer/loop audit preservation. Full native orders are reconstructed in the test reader from real native initialization/events and checked against original terminal dicts.

Schema coinmaster.native-audit.sqlite.v1 references path/table/kind/rows/SHA; rows, contexts, trade_ids and native tables retain original facts. Existing risk sampling is unchanged; all emitted rows survive. Consumers must query referenced views, not treat references as missing/empty arrays. Source/test hashes, exact commands/log hashes, load caveat and limitations are in memory-fix-completion.json and memory-fix-manifest.json.

Pilot remains active PID2009732/NRestarts0.650MiB/swap0 and low priority remain the proposed run limits. Root commit and a fresh72-source/13-input package plus sandbox/SQLite preflight precede separate launch GO. Large SQLite/CSV/gzip artifacts are evidence paths/SHA only and must not be committed. Old R2failure/journal/progress remain unchanged; terminal economics UNKNOWN.
