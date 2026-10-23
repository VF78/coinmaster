# B → 50/90: принятый исследовательский пакет

Владелец 23.10.2026 поручил объединить законченный анализ B с приложенным заданием и приступить. [Исходное задание](owner-task.txt), SHA256 `1da0c2df0ee992016f10ebc7fff8d4be50879c5f4c2eb14f18c149c3cd8571d2`, принято целиком в ограниченных ниже границах. Оно заменяет прежнее предложение общего 20%-guard, а не уже измеренные результаты. Пилот, production, конфигурации, ключи, ордера и deployment не входят в пакет.

## Контроль и приёмка

| Показатель | Сохранённый S0 | Сохранённый B |
|---|---:|---:|
| TOTAL USDT | 6 077 107,23887483 | 4 622 034,27336437 |
| Global settled-minute DD | 66,2569148647% | 57,5854104596% |
| Сохранено чистой прибыли S0 | 100% | 76,0170224751% |
| Комиссии USDT | 945 927,73761825 | 592 090,31669918 |
| BTC parents | 105 | 77 |

Основной gate: **DD ≤50%, (TOTAL−10000)/(6077107,23887483−10000) ≥0,90, liquidation=0**. Точный TOTAL-порог `5470396.514987347`; в округлённых центах не ниже `5470396.52`. Затем максимум TOTAL среди проходящих. DD30 — желательное улучшение, не обещанный результат. Глобальный peak не сбрасывается. Архивный S0 не пересчитывается.

Период `[2024-09-01,2026-09-01)`, seed 10000 USDT, исходный Bybit/warmup/fees/funding/margin/lot/tick/execution/settlement, RESERVE0, DPoff. На каждый запуск отдельные native BacktestEngine/account/funding journal. Native Nautilus остаётся единственным торговым и денежным контуром. Полный путь капитала и последующие размеры пересчитывает он; ledger attribution — только описание сохранённых фактов.

Source base `25a085f596292df58e51188dd91e996adbe5724c`; scientific S0 `75ffc9c69e9d79c4da4cd0614634a3eeba48d716`; B config SHA256 `06c9e99ce88bed050a62ac38cb9c0370cde35ce8c990582b888c06e68bcf53ea`. Новый source branch от B в изолированном canonical VPS checkout; Mac — только неизменный execution mirror. Один engine одновременно.

## Выводы, определяющие изменения

B действительно убирает часть дорогой пилы, но дневной допуск задерживает и прибыльное участие. Ранние отставания декабря/января меняют последующее реинвестирование. Уменьшение комиссий на 353837,42 не покрывает потерю TOTAL 1455072,97. Совпавшие даты не означают совпавшие объёмы или цену риска.

Остаются три разных механизма: ранний избыточный SOL, ноябрьский обратимый BTC-squeeze без SOL и поздняя серия реализованных whipsaw-убытков. Один SOL cap не исправляет BTC-squeeze, а закрытие августовского winner не возвращает предыдущие потери. Поэтому отдельное непрохождение 50/90 одним корректным компонентом не запрещает проверку их сочетания. Предварительное улучшение старого endpoint не считается новым TOTAL/DD.

Сохраняются PLANREF, split50/50 со второй частью0,25%, positive-TP native IOC, original SOL-overlay и права только по ordinary actual TP-fill. Не повторяются M1/M2, I25, H4/C0, общий fee-floor, AI, широкая сетка или даты-исключения.

## Единый список задач и зависимостей

| ID | Работа | Зависит от | Готовность |
|---|---|---|---|
| B00 | Сверить source/checkout/результаты, принять и закрепить новый протокол, обновить существующую #123 | — | pins, clean isolation, read-back Project |
| B01 | Независимо проверить BTC/SOL fill-net, fees, cash bridge и matched Q/unit attribution из вложения | B00 | полный ledger без double count; funding UNKNOWN не становится нулём |
| B02 | Один causal census: closed4h/H1, все41 WAIT/77 BTC parents/46 full branches, исходные wave/omitted/target leaves | B00 | UTC/open/close/receipt times, Z/S coverage или точный NO_MECHANISTIC_COVERAGE |
| B03 | E4: дополнительный closed4h допуск действующего WAIT при прежней полосе0,5ATR | B02 | focused native ordering/attempt tests, исходная D1 ветка сохранена |
| B04 | EP: альтернативный D1 допуск strong0,5 OR two consecutive same-side days weak0,25 | B02 | unique accepted-D1 count, gap/flip/no-fill cases |
| B05 | Z: one-shot retrace только реальных оставшихся zero-TP lots | B02, доказанный causal November arm/trigger | fee floor/retired-lot/native partial/priority tests; no TP-credit |
| B06 | S: one-shot SOL50% cut при factor-dominance + DD40 + adverse2% на closedH1 | B02, действие до раннегоDD50 | pending-add cancel/late-fill, no re-add/rearm, existing executor |
| B07 | Один focused independent money/order review, затем P0 flagsOFF=B | B03–B06 | review GO, P0 economic parity, frozen recipe/source/config hashes |
| B08 | Standalone E4, EP, условно Z и S | B07 | каждый полный native с отдельным journal и полным risk coverage |
| B09 | Выбор E* из B/E4/EP; условные XZ/XS/XZS без дубликатов | B08 | ровно зафиксированные сочетания, фактический compounding, без суммы proxy |
| B10 | Условные repeat/cost stress/одна пара neighbors, затем итог | B09 | бюджет/выбор ниже; exact outcomes, failed recipes, independent output review |

Начато: B00–B02 и один последовательный source-owner. B01 независим от реализации. Общие engine/domain файлы не редактируются конкурентно; reviewer не является вторым владельцем реализации.

## Замороженные рецепты

**E4 / B_WAIT_4H_RELEASE:** только active post-REGIME latch; closed4h после latch; `s*(C4h−last accepted D1 EMA34)/last accepted D1 ATR14 >=0.5`. D1 side/EMA/ATR заморожены до нового принятого daily; при одновременной границе D1 раньше4h. Это разрешение существующего входа, не поддельная paired executable session. Отдельные signal_asof/decision_time, новый причинный P0 и реальная admission/quote/quantity. Исходный once-per-session/side attempt не сбрасывается; latch снимает только actual fill.

**EP / B_WAIT_PERSIST_2D_025:** отдельная альтернатива E4. Daily `ALLOW=(D>=0.5) OR (same_side_count>=2 AND D>=0.25)`. Счётчик unique contiguous accepted D1 при active WAIT, первый=1, flip=1, повтор callback не день; пропуск не непрерывность. Strong-ветка не ждёт2дня. После actual fill WAIT/счётчик прекращаются.

**Z / B_ZERO_RETRACE_GUARD_4H_ONCE:** только MARKETABLE_FULL_ENTRY_FALLBACK, доказанные actual wave==0, not omitted, leaves>0, оба entry child terminal, все fees известны, до первого ordinary reduction; фактический SOL0 и нет pending/queued/unknown increases; mandatory exits приоритетны. Long feeBE=(actualVWAP+actual entryfee/actualQ)/(1−takerfee), short=(VWAP−fee/Q)/(1+takerfee). Guard G=ceil(max(original immutableP0,feeBE)) long, floor(min(P0,feeBE)) short. Arm closed post-entry4h минимум1tick на благоприятной стороне; только последующий executable bid/ask возврат вызывает native IOC по фактической цене, без обещанного fill поG. Один trigger, residual retries принадлежат тому же target. Risk fills retire только исполненные zero-slot lots; ordinary TP budget учитывает retirement. TP3, grossQ, beta/H/P0/знаменатели неизменны; risk fill не ordinaryTP и не SOL-right. Обработка ordinary/cancel/latefill не допускает oversell. Все46 full branches и августовский recovery — обязательные контрпримеры. Нет ноябрьской coverage — рецепт NOT_RUN, порог/TF не подгонять.

**S / B_SOL_DOMINANT_ADVERSE_HALF_ONCE:** closedH1, actual BTC и SOL противоположны, immutable causal planref beta допустима; `beta*abs(SOLQ)*SOLmark > abs(BTCQ)*BTCmark`; global settledDD>=40%, SOL adverse от actualVWAP>=2%. Один frozen target50% actualSOL, native lot down. Cancel pending increases с ACK/late-fill обработкой, дальнейшие additions этого real SOL-cycle запрещены. Не ordinaryZ-half, не `half_done`; обычные exits остатка, age/sigma и BTC episode/P0/TP сохранены. Нет таймерного восстановления/нового BTC trigger/группового C0close. «Risk owner» — идентичность намерения в существующем native исполнителе, не новый сервис/движок.

## Бюджет и порядок

Максимум **8 основных полных native**: P0, E4, EP, Z, S, XZ, XS, XZS. Z/S только при требуемой causal coverage; неактивные/дубликаты пропускаются, не заменяются произвольным рецептом. Все физические полные попытки, включая невалидные, отражаются в ledger; нет скрытых retries. P0 требуется именно из-за нового торгового кода, не является повтором S0.

E* выбирается только из B/E4/EP: (1) maxTOTAL проходящих50/90; (2) иначе minDD среди retention>=90%, DD<=S0, no liquidation; (3) иначе maxTOTAL при DD<=S0/no liquidation; ties minDD, затем turnover. Если E*=B, XZ/XS не повторяют уже выполненные Z/S. Комбинации допускаются при технической корректности и фактической активности компонентов; одиночный 50/90 не обязателен.

До **4 дополнительных контрольных** только при проходящем либо близком Pareto-кандидате: fresh repeat; один native adverse cost stress+1bp; одна заранее зафиксированная пара neighbors по основному улучшившему компоненту — E4 0,45/0,55 OR EP weak0,20/0,30 OR S adverse1,8/2,2%. Никакого Z MFE grid. Для ясности «близкий» до результатов означает no liquidation, DD<=55%, retention>=85%, недоминируемый и лучше B по обоим пороговым показателям. Это допуск к ограниченной проверке, не PASS50/90. Выбранный exact контроль/пара записывается до запуска; неиспользованный бюджет не обязан исчерпываться.

## Проверка результата

Для каждого: post-boundary TOTAL/cash bridge, ROI/retention, full global settledDD/dollarDD, peak/trough/recovery и все DD>=30%, underwater/loss series, фактические native BTC/SOL fill-net/fees/turnover, signed funding только если действительно доступен, все entry branches/qty/TP phases/risk cuts/lost rights, source/config/data hashes и completeness receipts. Таблица A/C/D и всех новых максимумов объясняет действие до падения и цену утраченного восстановления. Отрицательный endpoint price proxy не служит hard veto страховой гипотезы.

Benchmark остаётся NOT_FAITHFUL_DIAGNOSTIC (1m CLOSE synthetic quotes); settled equity не является tick-path/intraminute гарантией. Многократно изученный период не становится fresh OOS. Missing receipts — UNKNOWN/lower bound; знаковый funding не распределяется предположением.

Финальные артефакты: REPORT, comparison.csv/json, runs_manifest, wait_first_divergence, zero_guard_cohort, sol_risk_cohort, global_drawdown_episodes, matched_entry_attribution, independent_review. Промежуточный precheck не заменяет разрешённый технически корректный native-прогон.
