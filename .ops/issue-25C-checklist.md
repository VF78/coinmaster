# Issue #25C — execution checklist

Статус-машина: ACTIVE / BLOCKED / FALLBACK / SPLIT

## Current state
- State: ACTIVE
- Reason: архитектурный подход согласован с Владимиром; стартовала реализация Phase 0 (engine foundation).
- Executor: SELF (implementation-first), Claude review optional.
- Last transition: 2026-02-26 13:57 Europe/Madrid — implementation GO approved.

## Architecture-first track (approved direction)
### 25C.A Unified trading-rules engine architecture
- [ ] 25C.A0 Пройти Claude interactive consent (allow-edits) и зафиксировать readiness
- [x] 25C.A0b Активировать fallback SELF для docs, если Claude CLI unstable (code 143)
- [x] 25C.A1a Создать файл `.ops/issue-25C-architecture.md` с title + scope
- [x] 25C.A1b Добавить только section headers + TODO markers (без deep analysis)
- [x] 25C.A1c Сделать docs-only commit для skeleton
- [x] 25C.A2 Заполнить rule model (conditions / triggers / actions / priorities)
- [ ] 25C.A3 Заполнить lifecycle (evaluate → decide → act → audit), idempotency и observability guarantees
- [ ] 25C.A4 Зафиксировать conflict-resolution policy и migration plan (3–4 шага)
- [x] 25C.A5 Обновить checklist: implementation BLOCKED до архитектурного апрува

### 25C.1 implementation track (active after architecture approval)
- [ ] 25C.1a Найти точку server-path, где безопасно подключить trigger под feature flag
- [ ] 25C.1b Протянуть данные из evaluateMultiTf до точки входа
- [ ] 25C.1c Добавить guard/feature-flag condition + fail-safe ветку
- [ ] 25C.1d Добавить targeted test на wiring
- [ ] 25C.1e Прогон тестов и фиксация артефакта

## Blockers
- Operational blocker: Claude interactive allow-edits prompt периодически роняет run (code 143); mitigated by SELF-first implementation.
- External blockers: none.

## Event log
- 10:53: watchdog сработал (>15m без подтверждённого прогресса), run остановлен, задача декомпозирована.
- 11:08: зафиксирован предыдущий сбой `young-bl` (code 143, interactive allow-edits prompt).
- 11:23: watchdog снова сработал для `fresh-crustacean`; run остановлен; выполнен forced split в архитектурные микро-шаги.
- 11:53: watchdog сработал для `brisk-comet`; run остановлен; A1 декомпозирован до A1a/A1b/A1c (ultra-atomic).
- 12:08: зафиксирован `brisk-co` code 143 (interactive allow-edits prompt), `amber-nudibranch` остановлен по watchdog; добавлен отдельный A0 handshake-step.
- 12:23: `kind-summit` остановлен по watchdog без артефакта; активирован FALLBACK SELF для A1 (docs-first), чтобы снять зависание.
- 12:23: в FALLBACK SELF создан `.ops/issue-25C-architecture.md` (skeleton: title/scope/section headers/TODO markers); A1a+A1b закрыты.
- 12:24: docs-only commit `3e8383e` зафиксировал skeleton architecture doc; A1c закрыт.
- 12:38: повторно подтверждён `kind-sum` code 143; выполнение продолжено в FALLBACK SELF, закрыт шаг A2 (rule model).
- 13:57: Владимир подтвердил архитектурные рекомендации и дал GO на реализацию.
- 14:04: Phase 0 выполнен: добавлен `src/engine/*` foundation + `scripts/invariants-rule-engine.ts`, commit `28eabee`.

## Heartbeat policy for this issue
Отправлять только при:
- закрытии подпункта,
- смене состояния,
- появлении/снятии блокера,
- safety-ping раз в 60 минут при активной работе.
