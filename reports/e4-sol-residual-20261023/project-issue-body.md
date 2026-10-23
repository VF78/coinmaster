# E4 + защита остаточного SOL — принято 23.10.2026

Владелец разрешил реализацию и native-проверку E4 с защитой остаточного SOL после закрытия BTC. **Прибыльные BTC-fallback и ordinary BTC-TP → SOL-права сохраняются. Пилот, production, сервисы, ключи, реальные ордера и deployment не меняются.** Предыдущий пакет завершён отрицательно по цели; результаты не переписываются.

[Протокол и текущие артефакты](https://github.com/VF78/coinmaster/tree/codex/btc-pattern-pilot-m2-20261021/reports/e4-sol-residual-20261023). Source base [bd04c9b](https://github.com/VF78/coinmaster/commit/bd04c9b3858bcda40060a08eff488849c69af5d8). [Предыдущие результаты](https://github.com/VF78/coinmaster/tree/4f54c2cbf2821b0ed05cedd30c46d9e866304925/reports/b-50-90-next-20261023) сохранены.

Контроли: S0 TOTAL6077107.23887483/DD66.2569%; E4 TOTAL5631617.35953723/DD57.5854%; XS=E4+старыйS TOTAL5406345.11636863/DD58.9474%. S0/E4 не пересчитывать. [2024-09-01,2026-09-01),seed10000USDT; те же Bybit/fees/funding/margin/execution/settlement,RESERVE0/DPoff.

**Acceptance:** global settled-minute DD≤50%, TOTAL≥5470396.514987347 (≥90% чистой прибыли S0),0ликвидаций, полные receipts/terminalflat; затем максимальный TOTAL. Это цель, а не уже полученный результат.

## Одна защита, две раздельные проверки

R1: прежний E4+S с H1/DD40/adverseSOL2%/однократным сокращением фактической SOL на50%, расширенный на доказанный native BTCflat. Flat означает предыдущий реальный BTC-fill, domainqty0/cacheflat и отсутствие unfinished split/pending/queued/open/inflight BTC work. UNKNOWN не flat.

R2: тот же R1, но однократная проверка каждой полной реальной минутной пары quotes вместо H1, на причинном полном native settled account. Это устраняет часовое запаздывание; пороги/размер сокращения не подбираются. Старый XS уже имеет октябрьскую DD52.58% при открытом BTC — поэтому простого расширения flat недостаточно для цели.

Frozen remaining, cancel/ACK/latefill/addblock, обычные exits и приоритет обязательных выходов сохраняются. Нет BTC risk-cut/Z/fullSOLcut/новых TP/SL/широкой сетки/нового движка.

## Задачи и зависимости

- [x] R00: сверить source/контроли, сохранить предыдущий итог, отдельный canonical checkout/ветка, PLAN/protocol до запуска; Project readback.
- [ ] R01 (в работе): default-off residual/minute research flags, единый существующий native SOL risk task, confirmed-flat proof и причинная minute cadence.
- [ ] R02: focused native partial/cancel/latefill/ACK/asof/quote-order/rights/oncecut/ordinaryexit tests; независимое адресное money/order review.
- [ ] R03: source/config/input freeze, mandatory новый flagsOFF P0 должен EXACT воспроизвести старый XS; при расхождении следующие прогоны блокируются.
- [ ] R04: отдельные полные native R1, затем R2, отдельные engine/account/funding journal.
- [ ] R05: максимум один fresh-engine повтор лучшего проходящего50/90; если проходящего нет — NOT_RUN_GATE_FAILED, без нового подбора порогов.
- [ ] R06: independent saved-output verification, comparison S0/E4/XS/P0/R1/R2, maker/taker fees/notional, native asset cash bridge, global DD/lifecycle actions, checkpoint/Project readback.

Зависимости R00→R01→R02→R03→R04→R05→R06. **Бюджет максимум4 физических native-попытки**, включая invalid: P0,R1,R2,pass-only repeat. Начато0, активных0; source tests/review/rootGO обязательны до первого engine. Один engine на Mac одновременно. Продуктовый код только isolated canonical VPS checkout; Mac — неизменяемый execution mirror. Один владелец engine/domain, независимые reviewers без конкурентных правок.

Benchmark NOT_FAITHFUL_DIAGNOSTIC/1m CLOSE synthetic quotes; settled DD не tick/intraminute/live гарантия. Signed funding по активам UNKNOWN, не0. История не fresh OOS. Экономический вывод — только из полного нового native пути с реинвестированием.
