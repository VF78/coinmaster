# Issue #25C — execution checklist

Статус-машина: ACTIVE / BLOCKED / FALLBACK / SPLIT

## Current state
- State: ACTIVE → SPLIT → ACTIVE
- Reason: run `calm-willow` остановлен по hard-timeout (25m) без коммита; изменения валидированы локально и зафиксированы, переходим к следующему подшагу.
- Executor: Claude Code (Sonnet 4.6) primary + SELF orchestration.
- Last transition: 2026-02-26 22:53 Europe/Madrid — hard-timeout split + restart.

## Launch-only priorities (strict order)

Цель: **завтра открыть первые сделки по параметрам страницы Trading Rules**.

### Что уходит в future backlog (не блокирует старт торговли)
- Все архитектурные docs-задачи (A0, A3, A4).
- Все optional cleanup / consent notes.
- Любые улучшения observability/рефакторинг, не влияющие на путь `Trading Rules → Order`.

### Что оставляем в работе (блокеры запуска)
1. [ ] **L1: Включить реальное применение Trading Rules в live order path**
   - Ордеры `/api/live/order` и `/api/live/order/limit` должны учитывать multi-TF сигнал и текущие rules из DB, а не только логировать.
   - [ ] **L1.1 (единственная подзадача уровня 2):** сделать wiring и интеграцию без дробления идентификаторов ниже.
2. [ ] **L2: Feature-flag + fail-safe**
   - Поведение при `ENABLE_MULTI_TF_ENGULFING=true/false` детерминировано.
   - При ошибке сигнала/данных — безопасный fallback (без зависаний и без silent-fail).
3. [ ] **L3: End-to-end валидация “UI rules → effective rules → order decision”**
   - Значения из страницы Trading Rules должны подтверждаться через `/api/settings/trading-rules/effective`.
   - Решение по ордеру должно соответствовать этим значениям.
4. [ ] **L4: Targeted tests на wiring**
   - Тесты/инварианты на связку multi-TF + order path + guards.
5. [ ] **L5: Smoke + launch artifact**
   - `npm run check`, `npm run invariants:rule-engine`, `npm run ops:smoke`, live-status checks.
   - Финальный артефакт “ready-to-trade”.

### Жёсткое правило декомпозиции (с 2026-03-01)
- Допустимые уровни только: **L1..L5** и **L1.1**.
- Идентификаторы вида `L1.1a`, `L1.1a.i`, `L1.1.x` и любые уровни ниже **запрещены**.
- Нужное дробление делается только текстом внутри L1.1 (список микро-шагов), без создания новых уровней.
## Blockers
- Operational risk: Claude interactive allow-edits prompt может ронять run (code 143); mitigated by updated watchdog policy (8/12m progress, 90s silent-stall, 25m hard timeout, consent-loop restarts).
- External blockers: none.

## Event log
- 17:30: структура задач схлопнута по решению Владимира: только уровни `25C -> L1..L5 -> L1.1`; дальнейшая декомпозиция только текстом внутри L1.1 без новых ID.
- 17:13: watchdog зафиксировал отсутствие кодового артефакта; run остановлен и перезапущен в рамках L1.1 (микро-шаг: `/api/live/order` hook без изменения response-contract).
- 17:03: watchdog зафиксировал stalled run; перезапуск в рамках L1.1 (микро-шаг: wiring под флагом, без `/limit`, без тестов).
- 16:33: watchdog зафиксировал stalled run; L1/L2 временно сведены к атомарному L1.1 (wiring `/api/live/order` + `/api/live/order/limit`, без тестов), Claude Opus restart.
- 16:24: 10m watchdog: не найден новый кодовый артефакт по L1/L2; run декомпозирован на micro-step 1/3 и перезапущен через Claude Opus (runId 86341d94-ee87-46ed-a3bc-fc8610cbd3c3).
- 15:16: backlog очищен от дублей/абстрактных задач; оставлен только launch-critical track L1..L5 для старта торговли.
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
- 22:23: run `plaid-sable` остановлен по hard-timeout 25m; добавленный Case 9 (EXIT preempts ENTRY) валидирован локально (`npm run check` + `npm run invariants:rule-engine` зелёные), шаг P1d2 закрыт.
- 22:53: run `calm-willow` остановлен по hard-timeout 25m; добавленный Case 10 (mismatch reason/context coverage) валидирован локально (`npm run check` + `npm run invariants:rule-engine` зелёные), шаг P1d3 закрыт.
- 23:23: run `plaid-sable` снова c code 143; получен diff Case 11 (negative control parity), P1d4 закрыт; сейчас можно переходить к P1e.
- 08:08: P1e smoke (typecheck + `invariants:rule-engine` + `ops:smoke`) прогнано локально; артефакт Phase 1 готов, остальные шаги по roadmap ожидают PR.

## Heartbeat policy for this issue
Отправлять только при:
- закрытии подпункта,
- смене состояния,
- появлении/снятии блокера,
- safety-ping раз в 60 минут при активной работе.
