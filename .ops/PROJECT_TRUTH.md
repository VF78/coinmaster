# CoinMaster — stable truth

Repository: https://github.com/VF78/coinmaster ; backlog: https://github.com/users/VF78/projects/2 .
Manager/report checkout is NOT algorithm source or production.
Manager/report branch: `codex/btc-pattern-pilot-m2-20261021`; current work is in ACTIVE_TASK, not this file.
Mac manager: `/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021`.
VPS development root: `/root/.openclaw/workspace/coinmaster/coinmaster` on `root@46.225.163.123`; use isolated child worktrees. Primary checkout is dirty historical work, not deployment truth.

## Engine and boundaries
- Native NautilusTrader 1.231.0 is the sole engine for research/Sandbox/live. No second simulator, Freqtrade migration, new SDK/risk service, 2.0.0rc5 migration or fork by default.
- Dry-run uses native Sandbox with public HL data; it is not exchange testnet. Live uses native HL execution; virtual positions are never imported into live.
- Native account/cache/orders/fills and persisted controls are authority. Unknown state blocks increases pending manual reconciliation; automatic open-position crash recovery remains deferred, not proven.
- A source push is not deployment. Isolate research from running trader and secrets. Preserve running Sandbox; no pilot/production/release/credentials/orders change in the current handoff.
- Owner explicitly approved publication of current CoinMaster research source to the PUBLIC VF78/coinmaster repository on2026-10-24. This does not expand economic run budgets or authorize deployment; exact source/branch and approval receipts remain in ACTIVE_TASK/research packet.
- No new real orders, transfers, funding/deposit increase or live activation without separate explicit owner approval. Preserve existing deployment boundaries; do not infer new permission from historical prompts.
- Hermes, f-ai.studio, app.f-ai.studio and VPN are outside CoinMaster cleanup scope.

## Research objective and accounting
- Frozen benchmark: [2024-09-01,2026-09-01), UTC, seed10000USDT, RESERVE0.
- Current optimization objective: global settled marked-equity DD<=50%, >=90% net profit of original comparable S0, zero model liquidations and complete accounting; then maximize terminal TOTAL=ACTIVE+RESERVE. Owner allows experimental >=70% net profit as an intermediate gate only; final90% unchanged. PreferDD30–50%; below30% allowed. Exact absolute floors in RESEARCH_INDEX.
- Legacy S0 and explicit SOL-child S0 are DIFFERENT execution/admission models. Exact results/hashes and their separate90% floors live only in RESEARCH_INDEX. Never silently mix controls or lower the original absolute goal.
- Bounded market BTC3TP/CLEAN_Q study #131 completed NO_GO;3/3full and8/8short budgets spent/CLOSED. #132/#133 completed plan and bounded causal checks. #134 broad discovery found raw positives but no native70/50 winner. Owner approved isolated paired-exit implementation/up to4prefix then explicit+1(total5) on2026-10-25, including failures; full0. Exact amendment receipt and current physical counts in ACTIVE_TASK/native-run-ledger, not old approvals. Goal remains NOT_MET. Exact evidence lives in RESEARCH_INDEX; no automatic reuse of closed budgets.
- Historical Bybit1m data are real; synthetic L1 CLOSE execution/depth and current risk tiers are diagnostic assumptions, not historical L2/tick/live guarantees. Settled DD is not an intraminute bound.
- New final candidates must also satisfy coherent event-level DD<=50% with pre-fill/pre-open peaks; missing coherent event data is UNKNOWN and blocks PASS. Keep historical settled comparisons on their original sampling basis.
- Signed asset funding may be UNKNOWN; unallocated cash bridge is not funding. Never substitute zero, mock results, another venue or favorable OHLC order.
- BASE fees only: Bybit maker0.020%/taker0.055%; HL maker0.015%/taker0.045%. Native fill classification; market/IOC is not relabeled maker. No0.1% fixture fee in economics.

Historical dated documents/reports are evidence only; their old queues, runtime claims and permissions do not override these files.
