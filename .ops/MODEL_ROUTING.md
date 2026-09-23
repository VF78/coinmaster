# CoinMaster model routing

Updated: 2026-09-23. Applies to new work; do not restart a passing implementation solely to change models.

| Work | Model / effort | Handoff and quality gate |
| --- | --- | --- |
| Routine coordination, Project status, concise summaries | GPT-6 Luna / high | Give only issue, current HEAD, constraints, and a compact result contract. Escalate if competing architectural interpretations appear. |
| Bounded code/UI change with settled contract | GPT-6 Luna / high | One focused development pass and one full relevant verification pass. Escalate on failing integration tests or unclear ownership. |
| Ordinary multi-file implementation | GPT-6 Sol / low | Use when interfaces and acceptance criteria are explicit; escalate to Sol / medium if native state or money semantics are involved. |
| Native Nautilus integration, execution/accounting lifecycle, hard debugging | GPT-6 Sol / medium | One sequential executor, concise inputs, review diff/checks/CI only. Avoid overlapping edits. |
| Critical architecture, irreversible boundary, final audit | GPT-6 Astra / medium | Narrow, decision-oriented review; no routine implementation. |

The current coordinator task remains GPT-6 Sol / medium as selected in its UI. Its role is to maintain scope and Project state, dispatch one executor, inspect concise results, diff, tests and CI, and request at most one material correction. Implementation belongs in the executor task. The previously used GPT-5.6 Terra / medium (high for integration) remains a fallback for an existing task; GPT-6 routing above is preferred for new passes.

This is a routing hypothesis, not a measured CoinMaster benchmark. OpenAI describes Luna as efficient for scoped work, Sol / medium for everyday coding needing judgment, and Astra / medium for ambitious multi-context work. Higher reasoning effort generally spends more reasoning tokens. Public forum reports on GPT-6 Codex quality and usage are mixed, so evaluate against our actual completed-task cost and correction rate before lowering a safety-critical task's model. Sources: [OpenAI model selection](https://developers.openai.com/api/docs/guides/model-selection), [reasoning effort](https://developers.openai.com/api/docs/guides/reasoning), [developer forum discussion](https://community.openai.com/t/sol-is-expensive-but-luna-terra-retries-can-cost-even-more/1394943), [Codex user discussion](https://www.reddit.com/r/codex/comments/1wnlfbf/gpt6sol_high_vs_xhigh_where_is_the_sweet_spot/).
