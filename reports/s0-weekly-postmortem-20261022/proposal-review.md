# Узкая независимая проверка ONE proposal

**Механизм отличается от M1/M2, положительное ожидание не установлено.** Допустимо изложить его как одну ещё не реализованную гипотезу после фиксации точных правил и precheck сохранённых32 snapshots. Оснований объявлять её сильнейшей или запускать native сейчас нет. Полные TOTAL, settled DD и вероятность сохранения90% net — **UNKNOWN**.

Отличие конкретно: срезается только превышение gross leg N/W над3.9375, затем разрешена одна реставрация подтверждённого фактического среза. У M1/M2 доля удалялась навсегда. Это меняет длительность и размер экспозиции, но не доказывает улучшение. Общий capBTC/SOL не равен одинаковому риску, beta-neutrality или cap всего портфеля.

Критические ограничения:

- Ранний SOL1 имел N/W14.3245: cap3.9375 потребовал бы срезать около72.51%, сильнее M1. Его прибыльное восстановление нельзя считать сохранённым.
- Для long восстановление выше фактической цены среза означает покупку дороже продажи; для short — продажу дешевле выкупа. Это фиксирует неблагоприятную разницу плюс дополнительные fees/spread. Breakout не делает восстановление бесплатным.
-32 исходных first-hit snapshots позволяют проверить выбор/размер cap на исходном пути и условные немедленные затраты. Они не доказывают eligibility, время восстановления, фактическое исполнение или альтернативную траекторию капитала. Изменение пути после первого действия меняет следующие сигналы.

Нужно заморозить до реализации: W — положительная исходная settled equity, N — тот же source mark held-notional; fixed target — абсолютное native количество по source, без rebalance. Остаток может превышать cap после gap/partial IOC. Первый eligible trigger при N/W≤3.9375 пропускает весь цикл, если это намеренное правило.

Restore-credit равен только фактически исполненному trim, один раз в том же native cycle. Ограничитель original-plan-remaining вычитает последующие обычные TP/exit fills; не позволяет вернуться после flat/terminal exit; защитные fills не создают BTC TP/SOL rights и не обнуляют SOL consumed-add notional. Один IOC restoration attempt; partial/cancel/reject не даёт повторных заявок.

Цена среза — VWAP подтверждённых fills завершившейся попытки. Сигнал восстановления использует только полностью закрытую после этого15m свечу и high/low строго предшествующей закрытой свечи. Нужно явно определить пропущенные busy-сигналы; нельзя исполнить старую подходящую свечу задним числом. Вход — следующий причинный native quote; ordinary/forced/pendingincrease и неизвестные ACK сохраняют приоритет. Margin/lot/minimum могут уменьшить или отменить восстановление.

Минимальный precheck: pass/skip по asset и исходным profitable intervals; распределение actual hypothetical cap fractions; trim-only и trim+restore costs отдельно; liquidity/partial flags. Если causal15m свечей уже нет среди сохранённых данных, availability/цена восстановления остаютсяUNKNOWN; endpoint/extrema это не заменяют. До отдельно разрешённого native нужны native lifecycle fixtures перечисленных прав и приоритетов.

Если original-plan entitlement для восстановления нельзя определить без новых прав/повторного входа, restoration следует исключить, а one-shot excess cap оставить лишь простым непроверенным risk baseline. Он снова имеет permanent-cut недостаток и не заслуживает экономической рекомендации без новых доказательств.

Проверены только weekly-inventory.md, m1-m2-analysis.md, candidate-precheck.md. Новых streams, source reads, native, pilot или implementation —0.

## Дополнение: saved32 cap precheck и уточнённый root spec

**CONCRETE PROPOSAL FOR CONSENT; NOT READY NATIVE; ECONOMIC EDGE UNKNOWN.** Это можно предъявить как одну конкретную исследовательскую гипотезу с описанным механизмом и ограниченной предварительной проверкой. Экономически доказанным кандидатом она не является; обещаний DD≤50%/90% сохранения прибыли нет.

В32 исходных snapshots выбраны20:17BTC/3SOL, включая7 исходных победителей. Все3 выбранныхSOL — победители1,3,22. Низкие N/W отфильтрованы, но полезное восстановление пока не проверено. Ориентир двух taker-комиссий при ОДИНАКОВОЙ цене —46,382.22190239USDT; это не ceiling, не универсальная нижняя граница и не портфельный результат. Разные restore prices, fees notionals, spread/slippage/gap/funding и цена утраченного движения остаются неизвестны.

РаннийSOL1: идеальный trim72.5122%, до lot rounding/исполнения. SOL22: идеальный cut2216.0911SOL превышает известные1000 одной quote; oneIOC не гарантирует полное достижение cap. Восстановить можно максимум фактический подтверждённый trim, не идеальную величину.20 selections на исходном пути не равны20 будущим исполненным actions: entrycomplete/busy/ACK не экспортированы.

Root уточнил: W — та же finalized nativeTOTAL equity; DD и globalpeak — исходный денежный receipt; абсолютный capQ фиксируется в claim. Trim и restore — по одной попытке, credit только из actualtrimfills. Любойordinary/forcedexitINTENT по этой ноге, включая partialTP/halfexit, либо сменаcycle обнуляет credit. Rights/consumedSOLnotional/исходные anchors/planrefs не пересоздаются. Restore — по полностью закрытой post-cut15m свече: close за actualtrimVWAP и за previousclosed15m high(long)/low(short), затем следующий причинный quote; originalpendingincrease/exit блокируют.

**Одна оставшаяся смысловая оговорка:** буквальное «любой exit intent» может включать уже существующий или технически пересозданный пассивный BTC TP target. Тогда credit может исчезнуть сразу после cut, и17BTC случаев фактически останутся permanentcap. Нужно явно принять это последствие либо определить отмену как НОВОЕ самостоятельное штатное решение об exit после cut. Любой actualordinarypartialfill всё равно отменяет credit. Это уточнение нельзя спрятать в реализации.

Путь причинных15m свечей и действительная стоимость/доступность restore этими32 snapshots не установлены. ПолныеTOTAL/DD,90%retention и эффект compounding —UNKNOWN. Никаких новых потоков, source reads или engine/native не было. Дополнение основано только на candidate-precheck-temporary-cap.md/json.

## Итоговое уточнение spec от root

Смысловая оговорка закрыта явно: существующие/восстановленные passive nonmarketable TP leaves и их техническое пересоздание **не отменяют restorecredit**. Его отменяют любой **actualordinarypartialfill**, НОВОЕ самостоятельное exitdecision послеcut (regime/trail/timeout/forced), новыйnativecycle либоflat. Marketable/queued/pendingunknownordinary имеет приоритет и блокирует restore; lateTPfill сначала отменяетcredit и обновляетactualqty, затем может рассматриваться increase. НовыхPnL/rights нет.

До отдельно разрешённой реализации нужны focusednativefixtures именно этого порядка: пассивноеTPпересоздание сохраняетcredit; lateactualpartialTP отменяетего доrestore; postcutexitdecision/marketable/queued/unknownACK блокируютincrease; flat/reopen не наследуетcredit; partial/cancel/reject учитывают actualfillcredit и oneattempt без новыхправ. Эти тесты перечислены как будущие требования, **не выполнены**.

Итог: ONE конкретное предложение для согласования теперь имеет согласованный lifecycle-контракт. **NOT_READY_NATIVE** сохраняется:15mrestorepath иэкономиканепроверены; полныеTOTAL/DD/90%retention —UNKNOWN. Аналитическийотчётзавершён, новыхstreams/source/code/engine/аудитов —0.
