# Issue #25C — local runtime notes

> Источник истины по задачам: **только GitHub Project**
> https://github.com/users/VF78/projects/2

Локальный файл используется только для технических runtime-заметок (watchdog/инциденты),
не для хранения task-backlog и не для приоритизации задач.

## Runtime notes (latest)
- 2026-03-01 20:17: 15m watchdog: отсутствует новый подтверждённый кодовый артефакт по L2.1; выполнен forced-stop текущего прогона, L2.1 разбит на микро-шаг «A: in-memory ddLock lifecycle + owner reset endpoint skeleton», запущен новый run.
- 2026-03-01 17:30: структура задач схлопнута до `25C -> L1..L5 -> L1.1` (без уровней ниже).
- 2026-03-01 17:18: подтверждён OOM-инцидент; введены anti-overload меры.
- 2026-03-01 17:40: GitHub Project очищен от дубликатов/необязательных задач; оставлены launch-critical задачи.
- 20:47: 15m heartbeat guard: no new code artifact in last window; split L2.1 into micro-step (dd_lock gate + reset endpoint wiring), restarting implementation run immediately.
- 21:17: no confirmed code artifact in last 15m; current L2.1 run stopped. Split to micro-step: apply dd_lock runtime state + /api/live/dd-lock/reset endpoint + TradingErrorCode dd_lock_active only, then check+commit.
- 22:02: 15m watchdog: no new artifact in last window; advancing to next required subtask L3 (UI rules -> effective rules -> order decision validation) with fresh Claude run.
- 22:32: no confirmed progress artifact in last 15m; stopped current L3 flow, split next action to atomic substep (run live API verification commands and capture outputs), reminder disabled per policy until new active run starts.
- 22:47: no confirmed progress artifact in last 15m; stopped active flow, split next step to atomic L3 evidence capture + project status sync, reminder disabled per policy until new active run starts.
