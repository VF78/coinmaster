# Coinmaster Task State Protocol

Purpose: keep active work moving without spam, stalls, or hidden blockers.

## States

- **ACTIVE** — executable micro-step with verifiable output: diff, test, log, commit.
- **BLOCKED** — external blocker exists; record blocker + removal condition.
- **FALLBACK** — alternate route/executor used because default path is unavailable/ineffective.
- **SPLIT** — current step was too large/stalled; split into smaller micro-steps.

## Default executor

- Default model for all tasks: `openai-codex/gpt-5.5`.
- Non-trivial coding should run as a subagent/coding-agent with Codex 5.5 unless Vladimir says otherwise.
- If Codex 5.5 stalls, narrow/split first; use another model/tool only when it is unavailable, rate-limited, or clearly ineffective.

## Transition triggers

- No confirmed progress for >30 minutes in ACTIVE/FALLBACK → SPLIT, update checklist/state, continue next micro-step.
- External blocker appears → BLOCKED, record exact blocker and unblock condition.
- Default tool/model unavailable → FALLBACK immediately; do not wait passively.
- Recovery window arrives → explicitly check availability; switch only if it helps.

## Stalls and watchdogs

- Progress watchdog: 8 minutes without concrete activity (edit/write/bash/test) → intervene.
- Inference-only stream may get one +4 minute extension; after 12 minutes without concrete activity → SPLIT/restart.
- Silent stall: no stdout/activity for >90 seconds in an expected-active run → restart.
- Hard timeout: 25 minutes per run, then stop and decompose.
- Repeated consent/permission loop with no file changes → restart; after 2 repeats, switch to a narrow one-shot recovery.

## Heartbeat policy

Send an update only for: state transition, completed micro-step with artifact, blocker change, final result, or hourly safety ping during real active work.

Format:

`Heartbeat: • Done: ... • In progress: ... • Blockers: ... • ETA: ...`

Never send more than two “still working” updates without a new artifact.

## Confirmed progress means one of

- commit hash,
- verifiable diff,
- green test/run output,
- updated checklist with closed micro-point and artifact reference.

## Required sync

After significant state changes and before reset:

1. Update GitHub Project status.
2. Update `.ops/ACTIVE_TASK.md`.
3. Record task/status, canonical root, branch/HEAD/origin/deploy commit, done, exact next step, blockers/risks.

Default handoff is `.ops/ACTIVE_TASK.md`; create dated overflow handoffs only when compact state is insufficient.
