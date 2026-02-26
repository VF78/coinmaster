# Issue #25C — execution checklist

Статус-машина: ACTIVE / BLOCKED / FALLBACK / SPLIT

## Current state
- State: SPLIT → FALLBACK(ACTIVE)
- Reason: Claude run `kind-summit` остановлен по watchdog (>15 минут без подтверждённого артефакта) + повторяющийся code 143 на interactive allow-edits prompt.
- Executor: SELF fallback (manual docs delivery) with later Claude review when CLI stabilizes.
- Last transition: 2026-02-26 12:23 Europe/Madrid — forced split + fallback activation.

## Architecture-first track (approved direction)
### 25C.A Unified trading-rules engine architecture
- [ ] 25C.A0 Пройти Claude interactive consent (allow-edits) и зафиксировать readiness
- [x] 25C.A0b Активировать fallback SELF для docs, если Claude CLI unstable (code 143)
- [x] 25C.A1a Создать файл `.ops/issue-25C-architecture.md` с title + scope
- [x] 25C.A1b Добавить только section headers + TODO markers (без deep analysis)
- [ ] 25C.A1c Сделать docs-only commit для skeleton
- [ ] 25C.A2 Заполнить rule model (conditions / triggers / actions / priorities)
- [ ] 25C.A3 Заполнить lifecycle (evaluate → decide → act → audit), idempotency и observability guarantees
- [ ] 25C.A4 Зафиксировать conflict-resolution policy и migration plan (3–4 шага)
- [ ] 25C.A5 Обновить checklist: implementation BLOCKED до архитектурного апрува

### 25C.1 implementation track (blocked until architecture approved)
- [ ] 25C.1a Найти точку server-path, где безопасно подключить trigger под feature flag
- [ ] 25C.1b Протянуть данные из evaluateMultiTf до точки входа
- [ ] 25C.1c Добавить guard/feature-flag condition + fail-safe ветку
- [ ] 25C.1d Добавить targeted test на wiring
- [ ] 25C.1e Прогон тестов и фиксация артефакта

## Blockers
- Operational blocker: Claude interactive allow-edits prompt периодически роняет run (code 143); mitigated by SELF fallback for architecture docs.
- Governance blocker: implementation intentionally blocked until architecture doc approved.

## Event log
- 10:53: watchdog сработал (>15m без подтверждённого прогресса), run остановлен, задача декомпозирована.
- 11:08: зафиксирован предыдущий сбой `young-bl` (code 143, interactive allow-edits prompt).
- 11:23: watchdog снова сработал для `fresh-crustacean`; run остановлен; выполнен forced split в архитектурные микро-шаги.
- 11:53: watchdog сработал для `brisk-comet`; run остановлен; A1 декомпозирован до A1a/A1b/A1c (ultra-atomic).
- 12:08: зафиксирован `brisk-co` code 143 (interactive allow-edits prompt), `amber-nudibranch` остановлен по watchdog; добавлен отдельный A0 handshake-step.
- 12:23: `kind-summit` остановлен по watchdog без артефакта; активирован FALLBACK SELF для A1 (docs-first), чтобы снять зависание.
- 12:23: в FALLBACK SELF создан `.ops/issue-25C-architecture.md` (skeleton: title/scope/section headers/TODO markers); A1a+A1b закрыты.

## Heartbeat policy for this issue
Отправлять только при:
- закрытии подпункта,
- смене состояния,
- появлении/снятии блокера,
- safety-ping раз в 60 минут при активной работе.
