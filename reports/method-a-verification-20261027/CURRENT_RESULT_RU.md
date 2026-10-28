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

Обобщение количеств завершено после прямого owner approval d9095fa9. Новый source b1807f15043522b57d3e76527586f152c2db572c: удалены только ceilings BTC1/SOL132.9, количества из actual Cache/working TP leaves. Четыре уникальные focused checks PASS (synthetic actual-native-object BTC2/SOL−200 и negatives), peer0P0/P1. Это отдельная дельта к bounded20; не24 connected. Прочие runtime bytes/guards неизменны. Исторический отказ automatic review сохранён; обхода не было. Полная применимость по tiers/направлениям/миллионному капиталу не доказана.

Пакет code0-quantity-generalization-20261028 содержит proof, exact delta, source acceptance и verified publication receipt. Новых native/prefix/full0, ledger9/18 неизменен. Следующий этап — конкретный native case map для нового recovery/cash/SECOND и разрешение отдельной попытки: текущий dedicated M3 slot исчерпан, остаток распределён на M4–M8/3prefix/1full. Старые cash6011/SECOND ожидания не копируются, повтор FAILED запрещён. Финансовая квалификация нового source ещё UNKNOWN.

Цели DD30–50% и сохранения не менее90% исходной прибыли остаются NOT_MET. Full S0 TOTAL6077107.23887483, seed10000; промежуточный70% TOTALfloor4256975.067212381, финальный90%5470396.514987347. Нового ROI/DD от CODE0 не измеряли.
