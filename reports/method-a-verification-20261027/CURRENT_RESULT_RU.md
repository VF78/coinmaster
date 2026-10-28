# Текущий проверенный результат

Native ledger неизменен: 9/18, 5 COMPLETED и4 FAILED; engineering6/11, prefix3/6, full0/1, active0. Последний исправленный M3R остаётся FAILED. CODE0 выполнен с нулём новых native/prefix/full запусков. Пилот и production не затронуты.

| Работа | Доказанный результат | Что остаётся неизвестным |
|---|---|---|
| BTC реальные TP, M1/P1 | Native TP fills16/13/12. Prefix net151193.03 против150527.63 (+0.442%); 12 financial gates PASS | DD ухудшилась57.5854→62.4160%; нового двухлетнего результата нет |
| M2 SOL | Частичный вход10, три TP+STOP, BTC550 сохранён; independent63/63 PASS | Экономическая польза нового SOL |
| M3/M3R | Исправлена глубина; CAP78 исполнился10+68. Затем найден реальный recovery NO_GO | Последующие M3 gates не достигнуты; ни один FAILED не переименован |
| CODE0 a4ed258 | Минимальный default-OFF recovery, финальные20/20 engine-free checks PASS; peer0P0/P1 | Native исполнение и полная финансовая/экономическая квалификация нового кода |

CODE0 только для BREACH сравнивает частичные исходы с тем же baseline уже работающего BTC TP; полный endpoint обязан быть safe. Новый reduce-only LIMIT IOC имеет проверенный ценовой предел из phi/fee/tick, а не предположение о цене MARKET IOC. Partial IOC ждёт свой terminal и известные protection ACK с исходным deadline, затем остаток доказывается заново по фактическому состоянию. Pending-fill credit не добавлен. Обычный admission, старые TP GTC/STOP_MARKET и financial reader сохранены; при default-OFF действует прежний путь.

Native Money rounding проверяется консервативно. Отрицательный signed cost старого TP, неаффинная fee на Money-lattice и известный STOP fault отвергаются/сохраняют приоритет fail-closed. Подробности и source/test pins: code0-recovery-20261028/IMPLEMENTATION_REPORT.json, FINAL_SOURCE_ACCEPTANCE_RECEIPT.json, INDEPENDENT_FINAL_REVIEW.json.

Существенное ограничение: BTC[0,1], SOL[-132.9,0] пока являются границами проверенной области. Это не оптимизированные торговые параметры. Автоматическая проверка одобрения отклонила их удаление и положительный larger-quantity тест как расширение одобренного протокола. Обхода не было; outside-domain UNKNOWN/DENY проверен. Прочие ограничения старых ордеров, trigger/pending, знаков, funding и tiers также не снимаются. Это ограниченный прототип, не готовое решение для роста капитала до миллионов.

Реализация опубликована: source a4ed258b25345208a4612bfa1953a232812c64ff. Новое предложение QUANTITY_GENERALIZATION_PROPOSED_RU.md требует прямого решения; текущий native budget не расширяет. Будущий native case map и числовой бюджет только PROPOSED, старые cash6011/SECOND ожидания не копируются.

Цели DD30–50% и сохранения не менее90% исходной прибыли остаются NOT_MET. Full S0 TOTAL6077107.23887483, seed10000; промежуточный70% TOTALfloor4256975.067212381, финальный90%5470396.514987347. Нового ROI/DD от CODE0 не измеряли.
