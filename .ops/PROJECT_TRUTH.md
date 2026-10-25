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
- Bounded study#134 closed NO_GO/cap7; correctedB2prefixTOTAL19754.55/DD48.08 but insufficientcapital, primary14318.18/DD52.01 fails; goalsNOT_MET. Separate#135 control/warmup engineering completed LIMITED_PASS, source06f7577 published/notdeployed, 11of12physical(9COMPLETED2FAILED), unused1CLOSED/authorizedremaining0/economicprefix-full0. Exact limits and evidence only RESEARCH_INDEX/ACTIVE; no new monetarysource/native/training/full authority. Older#1313/3full8/8short and#132/#133 closed.
- #136 A0 engineering CLOSED7/7=3COMPLETED4FAILED, independent LIMITED_PASS with actual stockmarginDENY→freshVenueMark recovery. Prefixphysical1/3 FAILED pre-engine wrongdata_root (/inputs vs/inputs/data); no economicresult. Path-onlyrepair/proposed+1prefix(total4) requiresdirectapproval; remaining2HOLD; exactPUBLIC source763d985 published/notdeployed. Previousclosed6 immutable; no further engineering budget. Current authority/counts only ownerreceipts/ACTIVE/amendedledger; full/training/download/pilot/production0, SOLTP-cuts-rearm unchanged.
- Historical Bybit1m data are real; synthetic L1 CLOSE execution/depth and current risk tiers are diagnostic assumptions, not historical L2/tick/live guarantees. Settled DD is not an intraminute bound.
- New final candidates must also satisfy coherent event-level DD<=50% with pre-fill/pre-open peaks; missing coherent event data is UNKNOWN and blocks PASS. Keep historical settled comparisons on their original sampling basis.
- Signed asset funding may be UNKNOWN; unallocated cash bridge is not funding. Never substitute zero, mock results, another venue or favorable OHLC order.
- BASE fees only: Bybit maker0.020%/taker0.055%; HL maker0.015%/taker0.045%. Native fill classification; market/IOC is not relabeled maker. No0.1% fixture fee in economics.

Historical dated documents/reports are evidence only; their old queues, runtime claims and permissions do not override these files.
