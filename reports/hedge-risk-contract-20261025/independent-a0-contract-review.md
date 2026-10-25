# Независимый узкий review A0 — 25.10.2026

**PASS только для запроса owner consent; открытых P0=0, P1=0.** Проверка не разрешает код или native. Все прежние бюджеты закрыты; новый бюджет требует прямого согласия владельца.

**A0-01, исходный P1 — закрыт исправлением документов.** В NATIVE_PROTOCOL_PROPOSED_RU.md указан новый R2 paired family и C0 со старым lock, но не сказано прямо `research_paired_prefix=B2_F0`. Source06f поддерживает как B2, так и B2_F0. До согласования записать для C0/A0 именно B2_F0, для R2OFF — None, и заморозить остальные resolved knobs; C0/A0 отличаются только reversible-lock flag. Если задуман другой вариант, его нужно прямо выбрать. Это один минимальный correction batch.

Механизм обоснован ограниченно: изучены все16 активаций, четыре потенциальных original second-child; у всех4 подтверждён старый cancel ACK, у3 исходный postOnly limit не пересекает quote. Это не четыре прибыльных исполнения. Будущий margin/admission остаётся UNKNOWN и корректно вынесен в штатный native conditional gate.

Проверенные effective source ветки: market_redesign._md_check/_md_first_terminal/_md_after_fill, split_cover._split_check, paired_prefix._pair_init/_pair_cancel_btc_increases/_pair_position_event. При realU generic split deadline/day-end не действует. Исходный second allocation равен originalquantity−originalfirstallocation: недоисполненный первый IOC его не увеличивает. Документ сохраняет native поколения/ACK, ordinaryTP/flat/exit/паузы, один submit, originalprice/postOnly, причинные60s, штатные margin/tier/availablefunds и accepted real3TP. Старый R3guard не ослабляется; R2paired пока NOT_ADMITTED. R2 — предложенный новый core/control anchor, не победитель.

Sremaining по всем actual second fills, ограниченный old absolute cap+remaining, запрет возврата закрытого BTC и повторного уменьшения из corrective overfill сформулированы согласованно. При реализации следует сохранить immutable lockedAbsoluteCap до release и применить grant один раз: повторный расчёт от уже поднятого cap не допускается. Это точность реализации существующего требования, не отдельный новый scope.

По сохранённому JSON независимо пересчитаны четыре E−0.5P headroom и восемь сумм stress/fees/funding, без запуска аналитических скриптов/сканирования native streams. Primary90:3 prerequisitePASS/1FAIL;30day остаётся sensitivity. Stress — конечный исторический сценарный допуск, не DD50-гарантия и не wealth неисполненного uncut portfolio. Первичная проверка с Decimal28 дала ложный equality failure длинных чисел; Decimal60 с tolerance1e−34 к опубликованному Decimal40 округлению прошла. Источник не менялся.

Предложенные6 engineering instances≤48h и3 matched prefixes R2OFF/C0/A0 [2024-09-01,2025-01-15), включая failures, full0 и без старых остатков — ограничены явно. Cost, settled/eventDD, dailyES20, accounting и stop gates заданы до опыта. Ни prefix, ни инженерные fixtures не доказывают исходные70/90 цели, прибыль или venue capacity. Coordinator явно закрепил B2_F0 для C0/A0 и None/SOLнет для OFF в обоих документах; исправление перечитано, A0-01 закрыт. Пакет пригоден только для запроса явного owner consent на этот ограниченный план.

Проверенные SHA256 после закрытия:

- `A0_CONTRACT_PROPOSED_RU.md`: `8432e4decdf249ba2b80bb4eeac7e8773a1d24d39eb57b5d9026a3cdd516a2c0`
- `NATIVE_PROTOCOL_PROPOSED_RU.md`: `5c5e2b41555ee4e5c1970c5c5dadd173cd10599e00158224b706cb0083f477a0`
- `METHOD_NOTES_RU.md`: `1e51a0ff6553b0dc080275c3dce3d9646ecfc0663c4434a9cd75b9d0b076ce6b`
