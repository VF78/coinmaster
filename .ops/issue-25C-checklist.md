# Issue #25C — execution checklist

Статус-машина: ACTIVE / BLOCKED / FALLBACK / SPLIT

## Current state
- State: SPLIT → ACTIVE
- Reason: Claude run `delta-wharf` остановлен из-за отсутствия подтверждённого артефакта >15 минут (no diff / no commit / no test output).
- Executor: Claude (primary), self-managed orchestration.
- Last transition: 2026-02-26 10:53 Europe/Madrid — forced split по watchdog-правилу.

## Micro-subtasks
### 25C.1 emergency-exit trigger (decomposed)
- [ ] 25C.1a Найти точку server-path, где безопасно подключить trigger под feature flag (без изменения strategy-flow вне флага)
- [ ] 25C.1b Протянуть данные из evaluateMultiTf до выбранной точки входа
- [ ] 25C.1c Добавить guard/feature-flag condition + fail-safe ветку
- [ ] 25C.1d Добавить минимальный targeted test на trigger wiring
- [ ] 25C.1e Проверить локальный прогон целевых тестов и зафиксировать артефакт

### Next
- [ ] 25C.2 Проложить close-path и обработку edge-cases
- [ ] 25C.3 Добавить/обновить тесты (happy path + safety invariants)
- [ ] 25C.4 Прогон релевантных тестов/линтеров
- [ ] 25C.5 Подготовить итоговый diff + краткий rollout note

## Blockers
- None (текущий блокер снят; проблема была в зависшем run без артефактов).

## Event log
- 10:53: watchdog сработал (>15m без подтверждённого прогресса), run остановлен, задача декомпозирована, запускается следующий микро-шаг.

## Heartbeat policy for this issue
Отправлять только при:
- закрытии подпункта,
- смене состояния,
- появлении/снятии блокера,
- safety-ping раз в 60 минут при активной работе.
