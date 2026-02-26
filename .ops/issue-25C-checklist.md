# Issue #25C — execution checklist

Статус-машина: ACTIVE / BLOCKED / FALLBACK / SPLIT

## Current state
- State: ACTIVE → SPLIT → ACTIVE
- Reason: run `salty-prairie` остановлен по hard-timeout (25m) без коммита; изменения валидированы локально и зафиксированы, переходим к следующему подшагу.
- Executor: Claude Code (Sonnet 4.6) primary + SELF orchestration.
- Last transition: 2026-02-26 21:53 Europe/Madrid — hard-timeout split + restart.

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

### 25C.P1 Phase 1 (RISK rules in dual-run)
- [x] 25C.P1a Добавить engine snapshot builder (минимальный) без изменения runtime-поведения
- [x] 25C.P1b Добавить risk rule definitions: daily drawdown / leverage / allocation / stale data / symbol allowlist
- [x] 25C.P1c Подключить dual-run compare (engine decision vs legacy gate result) только в audit/log
- [ ] 25C.P1d1a Stabilize Claude interactive session (consent/edits), без код-изменений
- [x] 25C.P1d1b.i Добавить skeleton case-блок для RISK preempts ENTRY (без логики)
- [x] 25C.P1d1b.ii Дописать assertions + run checks + commit
- [ ] 25C.P1d2 Добавить invariant: EXIT preempts ENTRY
- [ ] 25C.P1d3 Добавить invariant: mismatch detection с reason/context
- [ ] 25C.P1d4 Добавить invariant: negative control exact match
- [ ] 25C.P1e Smoke-проверка и фиксация артефакта Phase 1 PR

## Blockers
- Operational risk: Claude interactive allow-edits prompt может ронять run (code 143); mitigated by updated watchdog policy (8/12m progress, 90s silent-stall, 25m hard timeout, consent-loop restarts).
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
- 14:52: диагностирован Claude CLI: авторизация OK, `-p` режим с `--permission-mode acceptEdits` подтверждён как рабочий для non-interactive edits (без consent-loop/code143).
- 13:38: watchdog reminder зафиксировал >15m без нового артефакта; выполнен forced split в Phase 1 (P1a..P1e), стартован следующий микро-шаг.
- 13:57: Claude run `gentle-sable` завершил P1a-изменения (`src/engine/snapshot.ts` + exports + invariants update); локальные проверки `npm run check` и `npm run invariants:rule-engine` зелёные.
- 14:28: Claude run `cool-valley` завершил P1b-изменения (risk rule definitions в `src/engine/rules/risk/*` + расширенные invariants); локальные проверки `npm run check` и `npm run invariants:rule-engine` зелёные.
- 14:47: Claude run `tidy-fjord` завершил P1c-изменения (`src/engine/dualRunCompare.ts` + export + invariants case); локальные проверки `npm run check` и `npm run invariants:rule-engine` зелёные.
- 15:23: watchdog policy сработала (>15m без нового артефакта): активный run отсутствует, состояние переведено в BLOCKED (awaiting external patch/commit from Vladimir local Claude run), 15m reminder должен быть отключён до старта новой активной подзадачи.
- 15:31: Владимир сообщил о ветке `claude/phase-1-risk-rules-eCrqj` и коммите `e6da750`; попытка fetch из текущего runtime неуспешна (нет GitHub credentials), ожидается patch/bundle/PR diff для локальной верификации.
- 15:39: принято решение вернуться к локальному исполнению без внешнего обмена патчами; resumed backlog Phase 1 (P1d/P1e).
- 20:23: watchdog сработал для `sharp-forest` (>15m без артефакта), run остановлен; P1d декомпозирован до P1d1..P1d4; стартуем новый микро-шаг.
- 20:38: повторно сработал watchdog для `brisk-falcon` (>15m без артефакта), run остановлен; P1d1 дополнительно декомпозирован до P1d1a/P1d1b; стартуем следующий микро-шаг.
- 20:53: watchdog сработал для `warm-zephyr` (>15m без артефакта), run остановлен; P1d1b дополнительно декомпозирован до P1d1b.i/P1d1b.ii; стартуем следующий атомарный шаг.
- 21:00: согласована новая run-policy для Claude Code; дополнительно проведена консультация с Claude по устойчивому режиму (consent-loop/silent-stall/progress watchdog) и правила применены в протоколе.
- 21:23: run `gentle-crustacean` остановлен по hard-timeout 25m без коммита; обнаружен partial diff (skeleton Case 8 в invariants), подшаг P1d1b.i засчитан и зафиксирован, продолжаем P1d1b.ii.
- 21:53: run `salty-prairie` остановлен по hard-timeout 25m; дописанные assertions Case 8 валидированы локально (`npm run check` + `npm run invariants:rule-engine` зелёные), подшаг P1d1b.ii закрыт.

## Heartbeat policy for this issue
Отправлять только при:
- закрытии подпункта,
- смене состояния,
- появлении/снятии блокера,
- safety-ping раз в 60 минут при активной работе.
