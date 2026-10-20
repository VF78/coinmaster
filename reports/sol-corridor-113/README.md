# ALPHA-CORRIDOR-v1: текущий исследовательский пакет #113

**Исправленный R2 RUNNING:** старт20.10.2026 **15:07:55UTC**, source[dbd18fa](https://github.com/VF78/coinmaster/commit/dbd18faf48c4e998c36d0050ce6e07c6cc660f0e), job cm113-alpha-corridor-v1-native24m-corrected-20261020T150605Z, nativePython269309. Фактические feed/freshfunding/nativeaudit подтверждены. Новое разрешение владельца: один полный прогон, бюджет**1/1**, без автоповторов. [Launch receipt](r2-corrected-launch-receipt.json).

Правка сохраняет одну SOL-цель в математически недостижимом состоянии до изменения BTC/законных SOL-разрешений/закрытой оценки риска; собственные fills/fees/мелкие движения marks не создают новую цель.7уникальных адресных native-проверок в совокупности и независимоеGO. [Проверки](churn-infeasible-completion.json). BTC победителя, исходные SOL-сигналы, данные/fees/funding/margin остаются прежними; native — единственный исполнитель/денежный учёт.

**Предыдущий e3eaf77 остановлен владельцем:**15:04:28UTC,79.75дня/19 126fill-auditrows, не результат24м. Все факты сохранены, процессы завершены. [Owner-stop receipt](r2-repeat-owner-stop-receipt.json). Ещё более ранний OOM остаётся отдельной попыткой ниже.30 000fills были синтетическим тестом памяти, не24мчисломсделок. **Полные TOTAL/ROI/DD покаUNKNOWN; пилот не изменяется.**

[Задание владельца](owner-task.md) · [Project #2](https://github.com/users/VF78/projects/2) · [Issue #113](https://github.com/VF78/coinmaster/issues/113)

База: BTC split/PLANREF/TP-IOC + исходный SOL-overlay, TOTAL **6 077 107.23887483 USDT**, native marked DD **66.31878025%**, `[2024-09-01,2026-09-01)`, seed10k/reserve0/DPoff. [Подробная статистика](../winner-6077107-stats/README.md). Независимый BTC-only **280 748.52263020** — отдельный результат, не компонентная атрибуция.

## R0 — завершён

Один потоковый проход существующей истории: **3 153 600 native строк /1 051 199 post-SOL наблюдений**. 90 закрытых парных Daily returns, исходные marks, исходные данные/комиссии. Ни исполнения, ни новая equity-кривая не симулировались. Native DD воспроизведён; оценки challenge-cushion совпали; 730 дней/24 месяца/105 первых BTC-состояний/11 кластеров/3 excursions >50% сверены.

| Наблюдаемый SOL-alpha | Минутных состояний | Доля alpha-состояний |
|---|---:|---:|
| Объём уже допустим | 126 621 | 62.8698% |
| Нужен меньший объём | 43 925 | 21.8096% |
| Нужен больший защитный объём | 5 345 | 2.6539% |
| Математически нет допустимого объёма | 25 511 | 12.6667% |
| Всего | 201 402 | 100% |

**37.130217% наблюдаемых alpha-состояний не проходят без изменений.** Это количество timestamps, а не сделок или ребалансировок. Во всех состояниях с открытой позицией математически infeasible **89 421 /576 649 =15.5070%**. Ещё **18 023** infeasible состояния — уже flat ниже `0.55H`; SOL-сделкой прошлую потерю исправить нельзя.

Первые состояния 105 BTC-входов: **90 safe /13 infeasible /2 add**. Все эти 13 остаются infeasible даже без будущих комиссий. Это ограничения на наблюдаемом контрольном пути, не доказательство будущего результата кандидата. Раннее общее нарушение 16.09.2024 02:13 чувствительно к расходам: C3457.602376 против min L3496.422643 с будущими taker fees; без них3393.154238.

[Полный R0-отчёт](r0-report.md) · [JSON](r0-statistics.json) · [105 BTC checkpoints](r0-first-BTC-states.csv) · [11 кластеров](r0-11-clusters.csv) · [Контрпримеры](r0-landmarks.csv) · [Проверки](r0-final-checks.json) · [SHA](r0-manifest.json)

**Ограничение R0:** старый post-SOL hook может предшествовать завершению fill/account settlement. Counts остаются сценарным расчётом сохранённых наблюдений, не доказанным итоговым бюджетом. Повторного прохода не было; native DD остаётся архивным, без повторной сертификации. Новый R1 receipt проверен отдельно. Бюджет определён через итоговые account checkpoints E/H; полный native DD по всем фазам сохраняется отдельной метрикой. Наблюдаемый held-alpha не подменяет будущие законные права/цели. Доступная биржевая маржа, pending leaves и будущие исполнения из этой таблицы не доказаны. Потенциальные изменения target не являются фактическим оборотом/fees/ROI.

## R1 — реализован, native проверки и независимое GO

Ближайший к законной alpha-цели допустимый SOL-объём, без изменения BTC/alpha-сигналов, через существующий executor. Default OFF, без отдельного risk-сервиса или второго денежного учёта. `DATA_UNKNOWN`, `SOL_RISK_INFEASIBLE` и `SOL_MARGIN_INSUFFICIENT` раздельны. Известный infeasible исход — минимальный L среди реально доступных SOL-объёмов с явной отметкой, без скрытого изменения BTC.

[Контракт](r1-contract.md) · [План адресных native tests](r1-test-plan.md) · [Source inventory](r1-source-inventory.json) · [Ограниченная OFF/source parity](r1-off-source-parity.md). В текущем HEAD есть исправление отказа forced close, не затронувшее исторический winner path:710orders=447FILLED/263CANCELED, без Denied/Rejected. Универсальная идентичность исходников не заявляется; focused OFF/healthy-ON parity подтверждена двумя native SOL-циклами, не всеми историческими timestamps.

Атомарное сохранение raw native result/events/fills/orders до metadata validation реализовано. Короткий реальный native runner и inner/outer fault injection подтвердили сохранность аудита. Итоговые native cash/position PnL читаются на подтверждённой более поздней receipt после fill-событий; source quote/receipt timestamps различаются, backdating отсутствует. Dirty-marker охватывает все deduplicated fills.

**Проверки:** 103 passed в связанном наборе; устаревший fixture исправлен и прошёл отдельно; финальные три затронутые проверки прошли. Это перекрывающиеся проверки, не новый полный104-pass run. Проверены partial/cancel/late fill/Denied/UNKNOWN, права/отсутствие старого IOC-долга, pure protection после BTC-flat, reverse15m+0.8C, global H/однократный учёт. Арифметика и injected margin refusal отмечены отдельно. [Результаты/SHA](r1-completion.json) · [Независимое GO](r1-review-final.md) · [Diff](r1-source.patch).

**Ограничения:** lot-gap входит в общую execution-категорию SOL_MARGIN_INSUFFICIENT, не доказывая нехватку cash. Resume без готового H checkpoint не квалифицирован; R2 — fresh engine. Подробные scenario samples ограничены8192, counters/native executor events сохранены. Source-only, не deployment/live acceptance.

## R2 — неполный запуск, OOM; экономический результат неизвестен

Владелец разрешил **один** native24m кандидат. Фактический replay работал **20.10.2026 11:27:59–11:48:54 UTC** и был остановлен kernel OOM-killer при лимите650MiB, swap0. Journal подтверждает20min43.094sCPU/648.5M memory peak. Это технический сбой, не ликвидация и не доказанный проигрыш/успех стратегии. Повтор не запускался.

| Показатель, полный эталонный период | Архивный контроль | ALPHA-CORRIDOR-v1 R2 |
|---|---:|---|
| TOTAL, USDT | 6 077 107.23887483 | UNKNOWN: replay не завершён |
| ROI | +60 671.07238875% | UNKNOWN |
| Глобальный native marked DD | 66.31878025% | UNKNOWN |
| Условная OHLC-граница | 67.54771032% | UNKNOWN |
| Модельные ликвидации | 0 | UNKNOWN |
| Оборот, USDT | 2 209 476 512.4321 | UNKNOWN |
| Maker / taker fees, USDT | 153 876.76812554 / 792 050.96949271 | UNKNOWN |
| Все fees, USDT | 945 927.73761825 | UNKNOWN |
| Fills | 621 | UNKNOWN |
| Доля сохранённого TOTAL | 100% | UNKNOWN |

**Сохранённый префикс:**2024-09-01T00:01Z–2024-11-30T19:07Z,392240полных строк/130746SOL quote-minutes, примерно12.44% заданного интервала. Неполный gzip11 436 420bytes и отдельный funding DB/WAL/SHM сохранены с SHA. Последние cash/E4869.94269918 — промежуточное наблюдение, **не terminal TOTAL**. Просадка сохранённых снимков77.923304% предварительная, settlement/finality не сертифицированы; она не подменяет полную итоговую DD. Отсутствие final exports не означает нулевые fees/оборот/ликвидации.

Native raw final JSON/fills/orders не появились: OOM произошёл внутри replay, до экспорта. R1 сохранение перед metadata-validation защищает от ошибки упаковки после engine loop, но не от SIGKILL во время loop. Полные24monthly/11clusters/worst3/BTC-calendar+acceptedQ/долиBTC-only и SOL-only/реальные target-fill события не подтверждены. Цель DD≤50% **NOT_PROVEN**, победитель по R2 не выбран; в прод ничего не переносилось.

[Итог исполнителя](r2-completion.md) · [Машинный итог](r2-completion.json) · [Фактический OOM journal](r2-native-exit-messages.txt) · [SHA manifest](r2-failure-manifest.json) · [Независимая проверка неполноты](r2-analysis-failure.md). [Статическая проверка памяти](r2-memory-static-check.md): истории native/risk/order/fill сохраняются без общего ограничения;8192 ограничивает только scenario-budget samples. Это объяснимая гипотеза роста памяти, **точный виновник/распределение heap UNKNOWN**, исправлений вслепую нет.

Source frozen `f2ebdce`, все71pin неизменны, входы/конфигурация не подменялись. Unit `cm113-alpha-corridor-v1-native24m-20261020T112508Z`, Python194172, fresh fundingattempt0e5928b1495c4d53af1a114401bad801. Прежний startup111659 прервался до engine/0marketrows из-за3публичных профилей и сохранён отдельно, не второй economic run.

**Статус предыдущей попытки:**R0/R1 завершены; прежний R2 технически неполный, его economic budget использован. Новое отдельное разрешение на один повтор после устранения памяти зафиксировано выше; его бюджет пока0/1. Сначала доказанная причина/fix/native-тесты и безопасный план памяти/сохранения результатов. Самовольно расширять ресурсы/менять сервисы/запускать control, дополнительные repeat или grid нельзя. Пилот PID2009732/NRestarts0active без изменений. Signed funding UNKNOWN не заменялся нулём; partial cash не пересчитывался в выдуманную equity-кривую.
