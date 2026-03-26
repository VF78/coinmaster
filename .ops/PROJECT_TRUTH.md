# Coinmaster Project Truth

Updated: 2026-03-26 Europe/Madrid

## Source of truth
- Tasks and statuses: GitHub Project `https://github.com/users/VF78/projects/2`
- Repo: `https://github.com/VF78/coinmaster`

## Model policy
- **Primary (main chat):** `openai-codex/gpt-5.4-mini` — повседневные задачи, ответы, координация.
- **Резерв:** `anthropic/claude-sonnet-4-6` — fallback. ⚠️ Доступ через API key `anthropic:reserv` — модели 4-го поколения дают HTTP 400; работают только Haiku 3 и старше. Нужно обновление API key или тарифа.
- **Для разработки ПО:** `openai-codex/gpt-5.4` (через временный override или субагент).
- После каждой завершённой задачи из GitHub Project: **reset model override на default**.

## Coding policy
- Разработка ПО идёт **через субагента / coding agent**, не в основном чате.
- Для coding субагента:
  - default: Sonnet 4.6 (если API key починен) или gpt-5.4
  - hard/architectural/stuck reruns: Opus 4.6 или gpt-5.4
  - fallback only: Codex 5.4

## Execution rules
- One active implementation task at a time.
- No secrets in repo, truth files, or issue bodies.
- For task status: check GitHub Project first.

## Watchdog
- progress: 8m (+4m if inference-only)
- silent stall: 90s => restart
- hard timeout: 25m

## Restart recovery
1. `SOUL.md` 2. `USER.md` 3. `memory/YYYY-MM-DD.md` (today+yesterday) 4. `.ops/PROJECT_TRUTH.md`
