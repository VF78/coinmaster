# OpenAI route for BTC pattern research — 2026-10-22

Recommendation: use this chat/Codex now to develop explicit, testable pattern descriptions; let the local numerical evaluator establish whether they predict anything. A small hosted inference comparison is a possible later experiment. Do not make hosted fine-tuning the next dependency. No hosted prediction request, upload, training, key discovery, or trading change was performed for this report.

## What “learn here” can mean

| Route | What changes | Useful role | Boundary |
| --- | --- | --- | --- |
| This chat/Codex, examples in context | Prompt/context, saved rules and code | Compare causal windows, articulate shape hypotheses, propose numeric features, inspect failures | Conversation examples do not constitute a dedicated weight-training job; numerical scoring still runs locally |
| Hosted API, fixed prompt plus numeric/chart inputs | Context and retrieved exemplars at inference time | Repeatable structured pattern tags or probability forecasts, compared on identical IDs | Paid external inference; model/version, access, image handling and cost must be verified before launch |
| Hosted SFT/vision fine-tuning | Model weights in an explicit training job | Potentially improve consistent task behavior after a demonstrated prompt baseline | Current platform wind-down and base-model retirement make this a deferred eligibility question |

Official OpenAI documentation distinguishes prompt/context optimization and RAG from weight fine-tuning, and recommends an evaluation baseline before more complex optimization. Retrieval can add irrelevant context and reduce accuracy; it is a hypothesis to test, not an automatic improvement. [Optimizing LLM accuracy](https://developers.openai.com/api/docs/guides/optimizing-llm-accuracy).

This chat can help find descriptions such as compression, failed breakout, slope reversal, or repeated rejection. Their names are research hypotheses: define each as a causal rule or frozen output field, then test its added information against prior/numeric controls. A persuasive explanation of a chart is not evidence of calibrated forecasting skill.

## Current fine-tuning availability: material limitation

The fetched vision guide says the fine-tuning platform is winding down, new users cannot access it, and existing users can create jobs for the coming months. Its supported vision base is `gpt-4o-2024-08-06`; it does not establish GPT-6.1 fine-tuning eligibility. [Vision fine-tuning](https://developers.openai.com/api/docs/guides/vision-fine-tuning).

The current deprecation page explicitly schedules `gpt-4o-2024-08-06` and `gpt-4o-2024-11-20` for API shutdown on **2027-01-14**, with the same shutdown for their fine-tuned versions. Consequently an accessible existing account would still have a short deployment horizon for the documented vision route. [Deprecations](https://developers.openai.com/api/docs/deprecations#2026-10-14-gpt-4-series-model-deprecations).

Account eligibility, available training models, usable limits and total cost are UNKNOWN here. Do not promise SFT access, migrate to a model merely because it exists in Codex, or treat a historical fine-tuning recipe as currently launchable. If revisited, verify eligibility and retirement dates first, before preparing any upload.

## A bounded comparison proposal, not a launch authorization

Preserve the full market archive and original 8,496 outer IDs. The existing three purged expanding DEVELOPMENT folds cover 2024-06-01–2026-05-01; retain the same frozen 72-hour horizon, SL at 1 sigma, three TP levels, ambiguity/censoring rules and physical units. No retrospective 180-day crop and no million-row context dump are needed.

First repair the audited evaluation/provenance guards. Then an optional hosted trial can reuse a small, predeclared subset of causal windows, with the remaining archive retained locally. Every example must be genuine OHLCV from the pinned public venue source, never a fabricated price path or the model's memory of a historical market question.

Compare three fixed conditions on identical query IDs: numeric input only; numeric input plus chronological mature-fit exemplars; and those same inputs plus one consistently rendered chart. A standalone shape-only arm is optional only if registered before querying. Use the existing local prior/numeric/context/CNN controls; do not select whichever representation happens to win on the held-out queries.

For each query, the local retrieval index contains only fit-prefix windows whose entire 72-hour label has matured strictly before that query and which satisfy the same purge/dependency rules. Freeze distance, scaling, exemplar count and ordering using fit data. Local numeric nearest-neighbor retrieval is sufficient; a hosted vector store is unnecessary for the first trial.

Chart inputs must stop at the decision time, have a frozen rendering contract, and be accompanied by exact numeric values/units. OpenAI documents graph/style interpretation, spatial precision and resizing limitations; use vision for candidate shape information rather than exact barrier arithmetic. Image tokens are billable and depend on model/detail/resizing. [Images and vision](https://developers.openai.com/api/docs/guides/images-vision).

## Minimal research package

Before any paid call, freeze a local manifest containing: source/label/protocol SHA-256; query IDs and true timestamps in a local-only map; fit/retrieval/holdout boundaries; causal dependency start; input normalization and inverse units; TP/SL/horizon contract; prompt/schema/render hashes; model ID/version and supported parameters; maximum requests/retries/output tokens; token estimate, rate source and dollar cap. Keep private account/order data, credentials, chat archives and strategy ROI archives out of this package.

Initial engineering proposal: 12 fit-only examples for prompt/schema debugging, then 48 frozen nonoverlapping held-out queries shared by all three arms; one response per arm/query, no best-of sampling or quality-triggered retry. This is an inexpensive feasibility/format pilot, not a powered skill verdict. Actual cost remains UNKNOWN until a selected accessible model and image/token budget are priced; enforce a hard agreed cap before execution.

Draft prompt contract: “Analyze only the supplied causal price window and eligible past exemplars. Return the requested pattern descriptors and event probabilities for the frozen 72-hour, three-TP/SL definition. Preserve supplied units. Use abstention if input is invalid or insufficient. Do not infer calendar identity, retrieve market history, change barriers, or supply an execution decision.” This instruction reduces a leakage path; it cannot erase pretrained knowledge.

Draft output contract: `{window_id, input_status, abstain_reason, shape_tags, tp_before_sl_probabilities_by_side, brief_evidence}`. Freeze tag enums and exact event definitions before querying. Each probability is finite in [0,1]; impose nesting across increasing TP barriers and compatibility with the existing ambiguity rules. Strict JSON Schema can enforce output shape; numeric/event consistency and forecasting accuracy require separate local validation. Refusals, incomplete outputs and invalid probabilities are explicit failures/abstentions, never silently dropped. [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).

For a rules-only first route, this chat produces a versioned feature/rule specification on fit examples; code evaluates that frozen specification on later windows without further model calls. No claim that the cloud model was trained on CoinMaster data is warranted.

## What would count as evidence

Use numerical proper scores against canonical labels: per-barrier Brier/log loss (with frozen clipping), calibration and paired score differences against the same prior/numeric controls. Report coverage, abstentions, temporal blocks and uncertainty; overlapping horizons are dependent observations. Chart usefulness requires improvement over the identical numeric-plus-exemplar arm, not merely an attractive narrative or a few correct examples.

Freeze all prompt/rule/retrieval choices before held-out queries. Never show query outcomes or future bars during development, exemplar retrieval or inference. Any prompt revision after inspecting held-out results creates a new development iteration; it does not preserve an untouched test.

A foundation model may already know events and outcomes from 2024–2026 through pretraining or later exposure. That provenance is not established here. Hiding dates/names or normalizing prices cannot prove independence. Historical held-out performance therefore supports workflow comparison under a contamination caveat; an independently unseen forward period, with outputs timestamped before outcomes, is needed for a stronger forecasting claim.

Better forecast scores would still leave execution feasibility, fees/funding, sizing, path dependence, ROI and drawdown untested. No guaranteed profit, CNN rescue, or native-policy promotion follows. The immediate useful output is a bounded set of reproducible hypotheses and a fair comparison, preserving the existing negative results.

Sources above were searched and fetched from official OpenAI documentation on 2026-10-22. Only this report was authored; no API-backed application, API request runner, training job, market forecast, CHECK scoring, VPS/pilot action or model installation was introduced.
