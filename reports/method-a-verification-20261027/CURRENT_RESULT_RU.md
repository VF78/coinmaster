# Method A: текущий проверенный результат

Новые физические попытки: 2 из 17; обе завершились OS0, активных нет. Пилот и production не изменялись. Торговый runtime a4dd469 остаётся default OFF в исследовании.

M1 инженерно подтвердил реальные BTC TP и сохранение исходного split-входа: два естественных synthetic parent, 16 native fills, корректные cumulative lot grants после SECOND, native flat/orders/pending0 до cleanup. Это проверка механики, не ROI на историческом рынке.

P0 — исходный E4 BTC + старый SOL, окно 01.09.2024–15.01.2025:

| Метрика | Native результат |
|---|---:|
| Seed | 10 000 USDT |
| Terminal | 160527.62564425 USDT |
| Чистая прибыль | 150527.62564425 USDT |
| Settled / coherent event DD | 57.5854104596% / 57.5854104596% |
| Native realized PnL, уже с комиссиями | 152253.48428190 USDT |
| Signed funding | -1725.85863765 USDT |
| Остаток денежной сверки | 0E-8 |
| Исполнения / закрытые позиции | 109 / 25 |

Исправленный reader: 10 gates PASS; legacy BTC3TP P0 = заранее объявленный N/A; rights audit UNKNOWN. Есть 15 actual SOL_ADD; измеренных rights failures, stream/profile failures нет. Не записаны шесть обязательных полей H/расхода прав/часов SOL. Полная финансовая квалификация P0 ещё не выдана; P1 не запускался.

Observer V2 3604532 записывает только существующие факты, не меняет торговую логику. Узкое ревью закрыло единственный type defect DailySignalBar до native. Mac frozen copy, 8 pure checks и stock preflight P0R/P1 PASS, constructors0. Root packaging omission helperfile сохранён отдельно; физической попытки не было.

Следующий gate: reader новых фактов → независимое review → один root GO на уже предусмотренный prefix harness reserve (новый UUID, repeat_of исходного P0). Фиксируем точное равенство fill/cash/funding trace исходному P0; расхождение = HOLD. Затем только при полной квалификации P0 — P1 и локальный gate ≥70% его netprofit.

Промежуточный и итоговый full targets ≥70%/≥90% исходной прибыли при DD≤50% остаются NOT_MET. Новый SOL-хедж ещё не реализован: его этап условен после BTC TP-screen. Число 160 527 относится к контролю за 4,5 месяца; его нельзя выдавать за новый двухлетний результат или live/OOS подтверждение.
