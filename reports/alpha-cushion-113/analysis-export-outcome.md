# ALPHA-CUSHION: текущий исход

**Финансовое сравнение не завершено. Условие native DD≤50% уже доказанно нарушено.** Итоговый TOTAL/ROI ALPHA неизвестен; ни победителя, ни live-продвижения нет.

| Метрика | Завершённый контроль | ALPHA после OOM |
|---|---:|---:|
| Settled native TOTAL | 6,077,107.23887483 | null |
| Native ROI | 60,671.0723887483% | null |
| Завершённая global native minute DD | 66.31878024969% | null |
| Наблюдённая native DD — только нижняя граница | — | **≥93.2264269664%** |
| Conditional OHLC bound | 67.5477103187% | null |
| Полные native fees / оборот / BTC-SOL fills / liquidation | Контроль сохранён в preflight | null / UNKNOWN |
| Terminal native flat | Да | UNKNOWN |
| DD≤50% | FAIL | **FAIL доказан наблюдённым prefix** |

Наблюдённая ALPHA-просадка хуже контрольной **минимум на 26.90764671671321023996211435п.п.**; это не точная full-run DD. Peak **12,484.37563522** —2024-09-11 14:00UTC; trough **845.63830144** —2026-08-30 13:46UTC. Первое превышение50% —2024-10-02 19:12UTC (50.5341181684%). Позднейшее восстановление уже случившуюся HWM-просадку не отменяет.

## Граница доказательства

Из существующего gzip одним ранее разрешённым проходом прочитано3,153,111 завершённых строк: по1,051,037 для каждой из3 native callback phases. Период **2024-09-01 00:01UTC →2026-08-31 21:17UTC**. Gzip усечён: `EOFError: Compressed file ended before the end-of-stream marker was reached`. Ничего не достраивалось; header/позиционные snapshots/метод и input SHA в `analysis-failed-observer-diagnostic.json`.

Последний marked native E **932.61441154 — НЕ TOTAL**, не settled cash, не ROI и не доказательство flat. Нет завершённого native JSON/CSV, поэтому итоговые fees, turnover, BTC/SOL fill counts, liquidation и signed funding не выдумываются. Snapshot **139,073 orders /138,984 fill-events**,730 batches/1,051,200 feed minutes означает только состояние перед native-end/export, не законченный финансовый отчёт.

## Техническое состояние

- Тот же кандидат упал при native-end/export. `failure-export-receipt.json` и journal supplement сохранены.
- Узкая техническая правка готова: ALPHA-only `run_analysis=False`, последовательный экспорт account/fills/orders с освобождением DataFrame-ссылок. Settlement/экономическая логика не меняются.
- Existing native parity: equal economic config/hash, TOTAL/cash/fees/summary, economic order/fill CSV,3 реальные funding SQLite rows, terminal flat и JSON serialization — **1 focused PASS**. Это не гарантия памяти для полного139k-order экспорта.
- Восемь остальных source pins unchanged по receipt; изменён runner SHA `c29a44f4e1a97ab0f8db04194fac469c82bab8b568ec4147c3ebab7a827a4c80` и добавлен focused export test. Точные8 pins и SHA всех evidence сохранены в JSON.
- Обе временные swap-зоны безопасно удалены source owner; исходный `/swapfile` не затронут. Все failed/control/funding evidence сохранены; старые observers только byteexact перенесены в проверенные Mac-архивы.

**Четвёртая техническая попытка — только по явному решению владельца, если точный settled TOTAL оправдывает затраты.** Ради доказательства DD≤50% повтор неизменного алгоритма уже не нужен. Алгоритм/пилот не менялись; автоматического запуска или новых расчётов этим документом нет.

Input gzip SHA256: `bac6800e8826b13222349426dee5267ac0e9e156b9a3b57f7b147e3b1a7a802b`. Компактные SHA failures/cleanup/parity/diagnostic — в JSON и отдельном manifest. Старые frozen reports не переписаны.
