# Issue #25C — execution checklist

Статус-машина: ACTIVE / BLOCKED / FALLBACK / SPLIT

## Current state
- State: SPLIT
- Reason: в предыдущем цикле не было подтверждённого diff >15 минут.
- Executor: SELF (Codex) as default; Claude optional accelerator when available.

## Micro-subtasks
- [ ] 25C.1 Внедрить emergency-exit trigger из evaluateMultiTf в server path (без изменения strategy-flow вне feature flag)
- [ ] 25C.2 Проложить close-path и обработку edge-cases
- [ ] 25C.3 Добавить/обновить тесты (happy path + safety invariants)
- [ ] 25C.4 Прогон релевантных тестов/линтеров
- [ ] 25C.5 Подготовить итоговый diff + краткий rollout note

## Blockers
- None (на данный момент)

## Heartbeat policy for this issue
Отправлять только при:
- закрытии подпункта,
- смене состояния,
- появлении/снятии блокера,
- safety-ping раз в 60 минут при активной работе.
