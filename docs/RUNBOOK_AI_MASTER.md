# Runbook: AI Master / OpenClaw analytics assistant

Дата: 2026-03-10  
Статус: operational baseline

## Goal

AI Master должен давать LLM-слой поверх deterministic analytics, не затрагивая execution path Coinmaster.

## Guardrails

### Request/response caps

- insight text: до `12000` chars
- web/Telegram question: до `4000` chars
- answer/fallback answer: до `12000` chars
- error text: до `2000` chars
- metadata (`model`, `runId`, `worker`, `promptVersion`) режется до bounded length

Oversize payload не должен ломать API:
- текст режется до лимита,
- ставится `truncated=true`,
- сохраняются observability-поля (`promptChars`, `responseChars`).

### Timeout / fallback policy

OpenClaw worker обязан:
- использовать bounded timeout на вызов модели,
- при timeout/LLM failure отправлять `fallbackMessage`,
- отмечать `fallbackUsed=true`,
- сохранять `latencyMs`, `timeoutMs`, `runId`, `model`, `worker`.

Рекомендуемый fallback для Q&A:

```text
Временно не удалось получить ответ модели. Используй deterministic daily summary и повтори вопрос позже.
```

## API contracts used by OpenClaw

### Save daily insight

`POST /api/ai-master/insights`

Recommended body:

```json
{
  "text": "daily insight text",
  "source": "telegram_daily",
  "model": "openai-codex/gpt-5.3-codex",
  "promptVersion": "v2",
  "runId": "daily-2026-03-10",
  "worker": "openclaw-daily",
  "dayKey": "2026-03-10",
  "latencyMs": 1834,
  "timeoutMs": 45000,
  "promptChars": 8120,
  "responseChars": 2150,
  "fallbackUsed": false
}
```

### Queue user question

`POST /api/ai-master/qa`

```json
{ "question": "What changed versus yesterday?" }
```

### Persist answer / fallback / failure

`POST /api/ai-master/qa/:id/answer`

Success:

```json
{
  "answer": "grounded answer",
  "model": "anthropic/claude-sonnet-4-6",
  "runId": "qa-2026-03-10T12:00:00Z",
  "worker": "openclaw-qa",
  "latencyMs": 9210,
  "timeoutMs": 20000,
  "promptChars": 5400,
  "responseChars": 1200,
  "fallbackUsed": false
}
```

Fallback answer:

```json
{
  "fallbackMessage": "Временно не удалось получить ответ модели. Используй deterministic daily summary и повтори вопрос позже.",
  "model": "anthropic/claude-sonnet-4-6",
  "runId": "qa-2026-03-10T12:00:00Z",
  "worker": "openclaw-qa",
  "latencyMs": 20000,
  "timeoutMs": 20000,
  "fallbackUsed": true
}
```

Failure-only marker:

```json
{
  "error": "llm_timeout",
  "model": "anthropic/claude-sonnet-4-6",
  "runId": "qa-2026-03-10T12:00:00Z",
  "worker": "openclaw-qa",
  "latencyMs": 20000,
  "timeoutMs": 20000
}
```

## Observability checklist

В логах сервера должны появляться события компонента `ai-master`:
- `insight_saved`
- `qa_queued`
- `qa_answer_recorded`

Минимум полей:
- `runId`
- `dayKey` (для daily insight)
- `model`
- `worker`
- `status`
- `latencyMs`
- `timeoutMs`
- `promptChars`
- `responseChars`
- `fallbackUsed`
- `truncated`

## Validation commands

```bash
cd coinmaster/coinmaster
npm run check
npm run invariants:ai-master
npm run build
```

Smoke при включённом owner auth:

```bash
export API_BASE_URL="http://127.0.0.1:8787"
export OWNER_AUTH_TOKEN="<token>"
npm run ops:smoke
curl -sS -H "Authorization: Bearer $OWNER_AUTH_TOKEN" \
  "$API_BASE_URL/api/ai-master/snapshot?limit=5" | jq .
```

## Rollback

Если AI Master деградирует:
- не трогать trading loop,
- остановить/отключить только OpenClaw daily + QA workers,
- при необходимости откатить только AI Master-related commit,
- проверить, что deterministic daily summary продолжает работать отдельно.

## Definition of healthy state

- deterministic daily summary идёт по расписанию
- AI insight приходит отдельным сообщением
- Q&A либо отвечает, либо даёт явный fallback без silent loss
- web AI Master history показывает статус и не ломает UI
