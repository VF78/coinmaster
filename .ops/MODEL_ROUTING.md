# Model and delegation policy

Owner preference: all NEW CoinMaster executors use GPT-6.1 Sol, not5.5/5.6/6.0. This supersedes old routing tables.

| Work | Default | Limit |
|---|---|---|
| Manager: scope, Project, compact evidence review | GPT-6.1 Sol / medium | Do not implement product changes in manager chat; docs/orchestration are fine. UI selection must be verified, not claimed changed by a file. |
| Focused implementation / ordinary analysis | GPT-6.1 Sol / medium | One owner of engine/domain/journal; one focused pass. |
| Money/orders/recovery or genuinely hard debugging | GPT-6.1 Sol / medium, high only when needed | Raise effort for the narrow hard part, not the whole program. |
| Independent acceptance/review | GPT-6.1 Sol / medium | Specific diff/contract/assertions; no repeat total audit. |
| Astra / medium | Only a separately owner-approved critical architecture decision | Never automatic routine implementation or repeated final audits. |

Use supported actual tool model IDs (e.g. `gpt-6.1-sol`); do not invent availability or silently substitute an older model.
Delegate only authorized scoped work; this project permits nontrivial implementation delegation. Do not spawn agents for simple documentation/status changes.
Default: one sequential engine owner; independent GUI/API or data work only after contracts and disjoint files are fixed. A narrow reviewer joins when needed; no standing swarm.
New executor: no full chat history (`fork_turns=none`). Give TaskID, objective, source/config/data refs, relevant sections/files, constraints, acceptance tests, physical-run budget and output contract.
Return root cause, commit/diff, tests/CI, artifact paths and blocker. Never return full transcript/logs/manifests or all TASK_STATE.
One focused development pass, one full relevant verification, at most one substantial concrete correction; preserve failed evidence and every physical attempt in the ledger.
Optimize total cost including rework. Narrow/split first when a contract is unclear; do not upgrade every task or restart passing work to change models.
