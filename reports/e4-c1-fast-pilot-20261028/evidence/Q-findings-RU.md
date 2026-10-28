# Q: фактический результат сохранённого native запуска

**Q не выбран:** TOTAL4800260.20248922; до working floor5470396.514987347 не хватает670136.312498127. Это+411646.82023579 против старого C1 и−831357.15704801 против E4; сохранено78.95459918% original S0 net profit. Settled и coherent event DD одинаковы51.80315157406654834417870238%: не хуже C1 ceiling, но строгие50% не выполнены. Native liquidation0, terminalflat. Нового запуска или пересчёта экономики в этой проверке нет.

КонфигQ меняет BTC cut divisor на4; SOL cuts и restore DD35 прежние. Config492e4937518e5f8868a75af00d53efbe5c359a9d926c4b3b611fb84990a60e62, data7ab5ae2cdaa14885da28d188c7ad14dfc8168ee600b78535f7317409ea94e9cc, policyc9540fbef259039c95829a774ef54e0eea2dcf2b6748d6455e171bf28e889834.

## Причинный prefix

До первого фактического BTC cut06.06.2025 09:23UTC Q и старый C1 совпали:225 native fills по17 экономическим полям и400881 settled rows целиком. Первое расхождение receipt09:24: Qcash357355.25473393/C1cash344420.58258542; QmarkedE319525.62752549/C1markedE319201.57156384. Старые январь/октябрь не улучшились, что соответствует неизменной SOL-ветке. Это matched native prefix, не предположение о контрфактическом пути.

## Native cash и funding

Оригинальный JSON cash reconciliation действительно использует только последние две cache positions: его native_realized_total19586.72546728 и bridge4718585.68778178 неполны; оригинал не менялся, bridge не funding.

Существующий coherent trace позволяет **независимо закрыть actual native cash transition reconciliation без расчёта торгового PnL**:

`10000 + 4738172.41324906 (537 unique native fill cash deltas) + 52087.78924016 (1245 unique native funding cash deltas) = 4800260.20248922`, residual0E−8.

Все1782 пары PRE/POST по native_id соединены без missing/duplicate; actual cash-before каждой следующей mutation равен cash-after предыдущей. Проверены2105965 physical native snapshots:1782 cash changes, ноль нераспределённых изменений. Ещё1051199 `SETTLED_PRE_NEXT_SOURCE_WATERMARK` — объявленные retrospective copies старого состояния, поэтому их обратные cash snapshots не являются новыми account changes. Они сохранены в исходном trace. Проверка не считает соседние retrospective/physical копии двойными платежами.

Funding JSON=SQLite funding_cash=original funding journal after_total=coherent PRE/POST cash deltas;1245 уникальных event/instrument keys, один платёж на событие, ноль арифметических ошибок. BTC signed funding+43139.45068984; SOL+8948.33855032; всего+52087.78924016. Комиссии уже входят в actual native fill cash deltas, повторно не вычитаются.

Отдельная сумма native `PositionClosed.realized_pnl` по **всем** lifecycle остаётся UNKNOWN: такой полный lifecycle artifact не экспортирован; финальный cache повторно использует position IDs. Cash transition identity выше закрыта другим допустимым native источником, а неполная позиционная сумма не переименована в корректную.

## Действия и окна

Q:7cuts/3restores/4revocations против C1 9/3/6.10 native intervention fills: fees12369.60926835, turnover22490198.6697; intervention fees ниже C1 на18128.43145927. Actual three cut/restore pair cashflow ex fees−197439.2985 против C1−385696.0245; это measured pair cashflow, не самостоятельно аддитивная причина TOTAL. Все537 native fills заплатили682035.99085102 fees, что на10972.61673913 **выше** C1: снижение intervention turnover не означает снижения всех портфельных комиссий.

Первые SOL cut/restore времена, объёмы и деньги совпали с C1. Первый BTC cut09:23 06.06.2025 —5.676BTC вместо11.353BTC. Ноябрьский BTC cut/restore27.11 02:24→01.12 04:02 —38.437BTC, но уже на собственном изменившемся капитале. Августовские cuts происходят10.08 16:22,19.08 02:10 и30.08 23:49UTC. Это фактический новый календарь, не удаление фиксированного набора прежних fills; `Q-c1-actions.csv` содержит actual native order/trade IDs и деньги.

| Frozen receipt UTC window | Maximum global settled DD |
|---|---:|
| OCT[2024-10-03,10-06) |50.61423369%|
| JAN[2025-01-10,01-22) |51.80315157%|
| NOV[2025-10-22,12-03) |51.03276581%|
| FINAL[2026-07-06,09-01) |49.28332346%|

В `Q-months.csv`24 source-quote UTC месяца с first/last settled E/cash и global H без сбросов; отдельно названы original report cash month-end и cash return. `Q-windows.csv` использует receipt UTC и half-open endpoints; эти основания не смешаны.

Global event DD endpoint `timestamp_ns` в summary — **sequence index**, не Unix ns. Явный join со stream: peak sequence579557→13.01.2025 00:36UTC/E161044.59427091; trough582080→14:36UTC/E77618.41899891; recovery614205→21.01 00:49UTC/E161264.7315447. Дата settled receipt для того же completed source mark на минуту позже; `Q-analysis.json` сохраняет both event_ns/receipt_ns и basis. Coherent observer statusPASS не означает доказанную intraminute price path.

Все исходныеQ JSON/SQLite/gz сохранены неизменными. Новые artifacts — только независимое чтение/атрибуция; engines0/tests0/product changes0. Exact input SHA256 — `Q-analysis-input-hashes.json`.
