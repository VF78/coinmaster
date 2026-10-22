# Research module owner — preflight

**Изолированная разработка готова; экономические модули ещё не реализованы.** Жду root precheck GO для H1. H2 — позже отдельным GO; H3 — только precheck.

|Проверка|Результат|
|---|---|
|Canonical|`/root/.openclaw/workspace/coinmaster/coinmaster`; HEAD `0bd7351897a9854c144817fdfca6c548e7984673`, branch `codex/ai-cycle-20261021`|
|Сохранённая dirty state|123 исходных строки, включая100 tracked deletions; status SHA `852caf1e6416dec5a14bb47d48da478d6f2df05c5672cbf38955f6d919691837` совпал до/после исключения нового checkout. Ничего не reset/stash/delete|
|Isolated checkout|`/root/.openclaw/workspace/coinmaster/coinmaster/research-worktrees/btc-sol-modules-20261022`, branch `codex/btc-sol-modules-20261022`, CLEAN|
|Frozen source|`75ffc9c69e9d79c4da4cd0614634a3eeba48d716`; три core SHA совпали с source-audit; tracked63.36MB|
|ExactS0 control|TOTAL6,077,107.23887483; settledDD66.2569148647%; configSHA `22e1eefe8f9c71669e52a8e44b7acbdfd5f177d6ef4ae2118e9df566a05c6edc`; S0 не перезапускался|
|Runtime/resources|Canonical runtime/.venv Nautilus1.231.0 retained; MemAvailable1066MiB, disk3378MiB послеcheckout; swap2046/2047MiBused. Это не run admission|
|Pilot|coinmaster-hl-stageg-testnet.service active, PID2009732,NRestarts0; никаких service действий|

## Native partial-entry contract H1 до реализации

- DefaultOFF сохраняет exactS0; HALF_ONLY — отдельная версия. Первая часть получает прежний acceptednetquantity/sizing/entrygates; один лот не делится искусственно.
- Anchor — actual completedfirsthalf VWAP/P0. После него причинная executablequote должна показать +0.25% в originalside; без ретроспективного засчитывания quotes, пришедших при незавершённой первой части. Реальная цена исполнения, fees и nativepartial остаются настоящими. Выполнение использует один существующий executor.
- Deadline прежний: min(start+4h,nextUTCday−1min). Равенство границе — expiry. Нет deadline/earlyTP forcedadd; ordinary/forced exits старше нового add. На expiry/earlyTP: stopnewadds→cancelchild→terminalACK/actualfillreconciliation→закончить logicalparent фактическим количеством. UnknownACK не равен cancel и блокирует дублирование.
- TP targetbasis после окончательной partialfinalization — actualfillednetquantity с исходными fractions/integerlots; сумма новыхleaves не превышает actualposition. Уже исполненные reductions не стираются. Cancelled entryleaves не становятся позициями.
- **Не переопределять btc_net_planned_qty фактическим половинным объёмом.** Этот исходный denominator ограничивает omittedSOLrights через actualentry/plannednet. Для positiveTP в domain483–520 уже есть filledtargetfraction×entryfraction. Иначе половинный вход ошибочно получит полные SOLrights. H остаётся originalgrossreference×actualVWAP/beta; права масштабируются реальными fills, не submit/ACK.
- Existing `_split_tp_ioc_eligible` допускает только fullfilled/noCancelled; H1 потребует узкий variant-terminal predicate, иначе partialparent снова потеряет crossedpositiveTP. Не считать `_split_stop` достаточным completion: он ставит closed до cancelACK. Новый partialfinalization должен ждать существующего native owner, не вводя другой executor или PnL.
- Firsthalf itself terminalpartial требует явного actualanchor/noinventedcompletion; delayedoldcyclecallbacks не должны менять новый parent. Native position/cache и fillcallbacks авторитетны.

Focused gate после GO: defaultOFF, long/short trigger, HALF_ONLY, expiry/earlyTP/noforcedadd, partialfill+cancelACK+latefill, unknownACK, TP/leaves lotconservation, omitted/positiveSOLrights scaling, normal/forcedpriority, две successivecycles. Один focused pass и не более одной согласованной correction; никакого общего recovery rewrite.

H2 пока не кодируется: hourly causal residual/beta/mu/scale frozen at SOLentry, один cut50% actualremainder плюс cancelpendingadds/noRestore; precheck должен определить priorwindow/gaps/cycle. H3 postTP2partialtrail не кодируется. SHA, точные sourcepins и structuredcontract — в соседнем JSON.

Прочитаны только H1/H2 технические части attachment, компактный source-audit/matrix и targeted frozen split/rights/TP methods. Source audit reused: [source-audit](../btc-lifecycle-audit-20261022/source-audit.md). Product code/keys/orders/services/opt и installedpilot не изменены. Новых native/backtest/model/train запусков:0.

## H2 beta support and native availability

Local daily root: `/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/data/normalized`. `bybit-BTCUSDT-daily.parquet` SHA `71270c5b9aadad1a2d46003060e04882eaa6a0544802f4c1f025bd7253ea7545` (70,113 bytes); SOL sibling SHA `897b89d1e93d5b961e769321edf4bb44981384fad280d8e62e8b9fca64431ab4` (65,957 bytes). Both match original13pins. Frozen local worktree helper `runtime/coinmaster/domain/wave_overlay.py` SHA `a60a7fe8d242fcc87a028bec69bffd08a67e33ad6738abf92e2ef914159ab5b9`: `DailyBar`, `Candidate`, `batch_features_for`, no Nautilus imports. Use 270 completed daily log returns; close is available at open+24h. Current `feature.beta` at SOL entry and frozen BTC `Episode.beta_entry`/H are distinct: H2 must explicitly choose its causal beta0. Reviewer received paths/helper; no feature computation here.

**Existing Mac native is available without installation:** `/Users/vf/Documents/ChatGPT/Coinmaster/runtime/.venv/bin/python`, arm64 CPython3.12.13/Nautilus1.231.0. Compiled `backtest/engine.cpython-312-darwin.so` and `BacktestEngine` import PASS, zero instances created. This proves binary availability, not cross-platform full-run economic/rounding/callback parity. Next useful gate after GO is focused native fixtures, not automatic S0 full repeat.

|Saved VPS run|CPU time|Unit peak|Swap peak|
|---|---:|---:|---:|
|S0|18m45.469s|472.0MiB|0|
|M1|20m08.459s|490.2MiB|0|
|M2|19m38.352s|612.1MiB|0|

These are 18.75-20.14 CPU minutes, not measured wall time or a Mac speed forecast. M2 left 37.9MiB beneath the650MiB cap. No resource/thread/service changes. H4 remains backlog analysis only, with no SOL native/optimizer implementation.

## Final owner state

H1 NO_ECONOMIC_GO; H2 NO_NATIVE_GO; H3 PRECHECK_ONLY; H4 ANALYSIS_ONLY. No half-only or combined native admitted. Final read-only canonical status SHA852caf1e unchanged; isolated75ffc9c CLEAN. No product code implemented. H4 saved direction census is in h4-analysis.md/json/csv.
