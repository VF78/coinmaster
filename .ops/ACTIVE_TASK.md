Updated: 2026-10-22T22:58:54.359969+00:00
Status: H4_PROPOSAL_READY_AWAITING_OWNER_APPROVAL.

Owner clarification 2026-10-23: NO standalone SOL at BTC flat; opposite risk-adjusted SOL hedge only while BTC open. This supersedes the standalone H4 design in old TASK_PLAN.json, not historical evidence or H1/H2/H3 results.

Current deliverable: reports/btc-sol-causal-modules-20261022/H4_PROPOSAL.md. Proposed F (continuous hedge), T (same entry with 50% core + 50% three-TP), S (T plus scaled BTC-style split). Proposed new cap3 full candidates + conditional fresh confirmation; NOT AUTHORIZED/NOT RUN. k=cov(B,S)/var(S),90 causal closed daily returns frozen per episode; R units frozen at first fresh paired quote after actual BTC fill. No SOL EMA direction gate/independent EMA exits; own SOL TPs never auto-refill. Original SOL overlay replaced in separate research version, one existing native executor. BTC rules unchanged, future actual quantities/eligibility may change with common equity/margin.

ExactS0 source75ffc9c69e9d79c4da4cd0614634a3eeba48d716 / TOTAL6077107.23887483 / settledDD66.2569148647 reused, no rerun. Goal DD<=50 and TOTAL>=5470396.514987347 remains unachieved. Latest old science checkpoint126d6d0, metadata880d87b published/refPASS. H1/H2/H3 rejected by approved prechecks; no pending implementations/full native jobs.

This turn: targeted saved-source/docs review and proposal only; product code/native/model/order/deploy/service actions0. Pilot untouched; no current runtime health recheck claimed. No executor launched for an unapproved implementation. Existing #123 remains OPEN/Todo; proposal exact body/state/Project Todo readback PASS2026-10-22T23:00:51UTC; checkpoint publication pending.

Publication checkout: /Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021, branch codex/btc-pattern-pilot-m2-20261021. Future source owner must use canonical isolated /root/.openclaw/workspace/coinmaster/coinmaster/research-worktrees/btc-sol-modules-20261022 (75ffc CLEAN at prior check), preserve main canonical dirty state. Do not edit /opt or deploy.

Next: publish proposal checkpoint (Project readback complete), present concrete F→T→S for owner agreement. Do not run H4 implementations/native experiments before agreement.
