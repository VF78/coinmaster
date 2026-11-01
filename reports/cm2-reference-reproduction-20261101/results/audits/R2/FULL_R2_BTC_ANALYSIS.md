# FULL R2 BTC: финансовая квалификация PASS, воспроизведение HOLD

Оба результата строго квалифицированы на [2024-09-01, 2026-09-01): 1 051 200 исходных минут, 1 051 199 settled WM, 24 полных месяца. CM2 source `6707e173`; native flat, 0 ордеров и 0 ликвидаций. Экономическое воспроизведение пока не принято: найден один причинный дефект, денежный итог ниже эталона.

| Native показатель | Reference | CM2 R2 |
|---|---:|---:|
| BTC fills | 353 | 350 |
| Закрытые native cycles | 83 | 83 |
| Cash USDC | 358370.46374134 | 350148.46556951 |
| Realized PnL, комиссии включены | 339396.81182991 | 331540.95371582 |
| Комиссии, справочно | 62251.08400411 | 58325.56167512 |
| Фактический funding | 8973.65191143 | 8607.51185369 |

Δcash = **-8221.99817183 USDC** = Δnative realized −7855.85811409 + Δactual funding −366.14005774; точный residual 0. Комиссии повторно не вычитаются. Сумма 83 native lifecycle cash deltas равна этой разнице точно. Event/settled maximum DD: reference 64.82799999405777241986399143%, CM2 63.10492195101564179754420691%. Меньшая просадка не заменяет проверку верности исполнения.

## Причина

Первое расхождение фактической цены — fill 9 / cycle 3: одинаковые время закрытия и количество 1.22074, но reference 58185 против CM2 58159.9. CM2 admission хранит quote `1726531140000000000`, хотя close decision / fill — `1726531200000000000`. Эталон использует quote в момент решения.

В reference cancel ACK тоже продолжает forced close из cache, но общий `_submit_forced_close_on_quote` отвергает `tick.ts_event < _forced_close_decision_ns` (строка 2354; пояснение 2410–2421). В CM2 общий `_execute_drain` проверяет возраст книги через `_send`, но не её отношение к началу решения. Все 33 обычных закрытия (30 REGIME + 3 TRAIL) использовали книгу до `drain.state.first_ns`. Terminal GLOBAL закрылся по quote == first_ns корректно.

Минимальное исправление: вернуть эту единственную причинную проверку в тот же `_execute_drain`, используя уже существующий durable `state["first_ns"]`. Равенство допустимо; callback continuation, terminal E07 и no-progress защита сохраняются. Новые режимы, задержки, таймеры, поля, C1-формулы и параметры не нужны.

## Все эпизоды

Все 83 entry signal+side keys совпали; новых или пропущенных эпизодов нет. Все 14 старых H4 branch-различий устранены. Оставшиеся 7 отличий ветки и q0/q1 следуют REGIME close по книге до решения: позиция сбрасывается до quote S, поэтому q0 выбирается на S, а эталон потребляет этот callback закрытием и выбирает q0 на следующем callback. Это меняет zero-level branch. Различаются последовательности ролей в 9 циклах.

C1: reference 13 CUT / 1 RESTORE, CM2 12 / 1. Все quarter claims точны; каждый actual credit event связан с одним native fill, credit conservation точна, не более одного claim/restore на группу. Отдельный дефект C1 не доказан: капитал и ветки уже расходились выше по цепочке.

Количество fills отличается на 3: REGIME −1, TP2 −1, C1 CUT −1; прочие агрегированные роли совпадают. Полная детализация всех 83 циклов и их native realized+funding находится в CSV; значения не пересчитывались через price-PnL модель.

Reference own 3-month prefix invariant по fills/plans/funding/WM. CM2 source670 нельзя объявлять invariant к prefix source4e: это сознательно другой код; сравнение помечено диагностическим.

## Привязка артефактов

- REFERENCE raw SHA256 `883d01ec80d6eb4520ee838858166905a854a4a9b155556960a043ece84a4e5d`; qualification `e79e5f5bbf77ff561c340186aa3298d730f91865959f6b975cb95cb567f64669`; derived `4ace8fcc9aed8a004bcc3535bc57a56b464096b0721947a5b3637388b709c10b`.
- CM2 raw SHA256 `2db9443ee531794fea8de3926062b9759e67db8ebb067134cff534971cc0282c`; qualification `944c27e189d625b610678ef382ffc7e6d30443e2e12cba5011a76822500c3f54`; derived `43cbe02d18f770f8b306f72b9dad294b03210204a4769fb78143f9e7038e0505`.

JSON содержит raw/derived/CSV/source/proof hashes и точные predicate receipts. Все файлы исходных R1/failure анализов сохранены. Анализ создал 0 native engines/Strategy, 0 product edits и не дал новый GO. Нет утверждения о partial/late fill coverage или финальном ROI acceptance.
