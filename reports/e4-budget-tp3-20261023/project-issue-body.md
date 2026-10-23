# E4: SOL risk budget + ранний частичный BTC TP3 — принято 23.10.2026

Владелец разрешил реализацию и отдельные native-проверки SOL и BTC, затем сочетание только при полезных результатах. Максимум **4 полных физических исторических native-попытки**, включая invalid/corrections. **S0 не пересчитывается, пилот и production не меняются.** Предыдущие исследования завершены; отрицательные результаты сохранены.

Приоритет P1: снижать DD при сохранении прибыли. Цель: непрерывная global settled-minute DD≤50%, TOTAL≥5470396.514987347 (90% чистой прибыли S0),0 ликвидаций, полные native receipts и terminal flat; затем MAX_TOTAL. Период [2024-09-01,2026-09-01),10000USDT,RESERVE0/DPoff, прежние Bybit/fees/funding/margin/execution.

Контроль exact E4: TOTAL5631617.35953723/DD57.5854104596%, source bd04c9b3858bcda40060a08eff488849c69af5d8; архивный S0 TOTAL6077107.23887483. Контроли не пересчитывать. [Новый протокол/артефакты](https://github.com/VF78/coinmaster/tree/codex/btc-pattern-pilot-m2-20261021/reports/e4-budget-tp3-20261023). [Постмортем](https://github.com/VF78/coinmaster/tree/codex/btc-pattern-pilot-m2-20261021/reports/e4-postmortem-20261023).

## Зафиксированные версии

**SOL only:** global DD35%, warning floor55% непрерывного native equity high-water, стресс1×completedD1 WilderATR14. Консервативный BTC-reserve без hedge-credit. При доминирующем SOL stress сокращать только превышение commission-aware допустимого native lot остатка, один раз за actual SOL-cycle. Новые исходные неиспользованные adds допускаются целиком только в budget; consumed права не возрождаются, автоматического восстановления/таймеров нет. Mandatory/ordinary exit приоритет. UNKNOWN не flat/0. Сильный stress может дать полный выход; это явно проверяемый риск гипотезы.

**BTC only:**20% actualinitialBTC из существующей положительной TP3-доли на1% favorable от frozen PLANREF после завершения split; остаток по старомуTP3. TP1/TP2/fallback сохраняются. Существующая пропорциональная выдачаSOLправа по actualpartialfills сохраняется с исходным общим TP3-denominator. Один существующий native level-owner: ранняя tranche, затем original-price remaining на следующей допустимой quote; без двойного резервирования/раннего completion.

## Задачи и зависимости

- [x] T00: HEAD/state/контроли/новое разрешение сверены, старые результаты сохранены.
- [x] T01: causal числовой SOL-рецепт и BTC actual partial-right/native lot контракт зафиксированы до реализации/прогонов.
- [ ] T02 (в работе): defaultOFF research source только isolated canonical VPS checkout; один владелец, focused tests и relevant native lifecycle pass.
- [ ] T03: независимое адресное money/order review, immutable source/config/input/tooling и root GO перед historical engine.
- [ ] T04: отдельные SOL и BTC full native, разные engine/account/funding journal; независимая верификация actual outputs.
- [ ] T05: условное сочетание, только если оба технически валидны, сохраняют≥90% прибыли, globalDD не хужеE4 и улучшают свои SOL/BTC target-window DD; BTC globalmax не обязан уменьшаться, пока октябрьскийSOL не изменён. Повтор только кандидата50/90, всё внутри4.
- [ ] T06: comparison TOTAL/ROI/DD/fees/notional/funding/rights/календарь/capital attribution, checkpoint и Project readback. Done=пакет завершён, не автоматическое достижение50/90.

Зависимости T00→T01→T02→T03→T04→T05→T06. Запусков0/4, active0; source tests не являются full historical runs. Без скрытого P0/сеток/других порогов. Один engine на Mac; source edits только canonical VPS, Mac immutable execution mirror. Research не получает trading secrets. Нет SDK/нового PnL engine/миграцииверсии/деплоя.

Benchmark NOT_FAITHFUL_DIAGNOSTIC,1m CLOSE synthetic quotes; DD не intraminute/live гарантия; история не freshOOS, signedassetfundingUNKNOWN. Новые результаты пока отсутствуют.
