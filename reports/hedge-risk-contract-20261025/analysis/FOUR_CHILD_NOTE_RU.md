# Уточнение четырёх исходных child

Исходный результат сохранён: SHA256 `8c73956feb44ae1786d7ffdb043a2fbdc8996f57d65f5a8247568d8a74890174`. Только targeted extraction; engine/product/download0.

| RiskOFF case | Q0 / F_ever / D / B | Ещё не исполнено | Original LIMIT GTC | Cancel ACK |
|---|---|---:|---:|---|
| Sep14 | .975 / .487 / .243 / .244 | .488 | BUY60207.5 | Sep14 04:00 |
| Oct10 | 1.149 / .574 / 0 / .574 | .575 | SELL60959.8 | Oct10 04:00 |
| Oct12 | .880 / .440 / 0 / .440 | .440 | BUY62413.6 | Oct12 20:00 |
| Nov16 | .750 / .375 / 0 / .375 | .375 | BUY90744.4 | Nov16 08:00 |

Все timestamps UTC. Исходные ENTRY order IDs, submit/accept/terminal ns и ordinary TP/parent-flat timing — в JSON. Cancel ACK теперь **KNOWN для всех4**: actual native CSV CANCELED+ts_last совпадает с episode-specific SECOND_TERMINAL audit timestamp и cancelled quantity. Это доказательство события до riskOFF, а не вывод только из последнего status. Native submit ACCEPTED также сохранён. Нулевой filled_qty подтверждён.

Структурный исходный unfilled потенциал есть во всех4; ни один ещё не имел ordinary BTC TP/exit к riskOFF. Sep14 .243BTC уже закрыто protective debt: оно не возвращается. Q0−F_ever и Q0−D−B совпадают. В текущем коде permanent stop/second terminal запрещает повторную заявку; отдельный reversible-lock контракт должен явно изменить именно это правило, сохранив original price/TIF/quantity и first-positiveTP/flat/ordinary-exit guards.

Quote **AVAILABLE** в существующей synthetic CLOSE-модели: исходный execution parquet→точный native one-decimal bid/ask при saved spread0. Для каждого riskOFF совпал actual logged BTC bid; сохранена также следующая минута. Oct10/Oct12/Nov16 original post-only limit не пересекает quote, immediate fill не требуется. Sep14 BUY60207.5 выше ask59674: исходный post-only child в этот момент нельзя повторно допустить; смена на market/taker не разрешена.

Margin model **AVAILABLE**, prospective native gate ещё **NOT_PROVEN**. Сохранены captured Bybit tiers/policy source и actual post-quote account cash/free_cash/IM/MM для четырёх точек; IM/MM экспорт равен0 и не используется как выдуманный margin credit. Полный per-instrument reservation/open-order/entry-enabled snapshot не экспортирован; ручной margin расчёт не делался. Это ограничение приёмки, не отрицание гипотезы.

Oct25 market-only реконструкция уточнила UNKNOWN: 481 непрерывных executable CLOSE quote от16:01 до00:01, boundary68084.6 не пересечён. Старый fixed F0 risk стал бы OFF по expiry Oct26 00:01, позже firstTP deadline Oct25 20:01. Owner реально flat22:58. Только market state; continuing uncut E/B/margin/ROI не вычисляются.

Самый дешёвый следующий отдельный native conditional gate: одна lifecycle fixture reversible unfilled GTC lock с cancelACK, отсутствием другого increase, original rights/TP guards, актуальными marks/quote и штатным native margin gate; partial/late fills обязательно reconciled. Для Sep14 post-only crossing — deny/wait, без смены цены/TIF. Новый budget сейчас0.
