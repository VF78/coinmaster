# MethodA: сохранённый проверенный результат

Текущий основной маршрут — [E4/C1 fast pilot](../e4-c1-fast-pilot-20261028/RESULTS_E4_C1.md). MethodA9/19 находится HOLD по новому указанию владельца; WIP сохранён отдельно и не является prerequisite E4/C1.

Native attempts неизменны; ledger теперь9/19, 5 COMPLETED и4 FAILED; engineering6/12, prefix3/6, full0/1, active0. Последний исправленный M3R остаётся FAILED. CODE0 выполнен с нулём новых native/prefix/full запусков. Пилот и production не затронуты.

| Работа | Доказанный результат | Что остаётся неизвестным |
|---|---|---|
| BTC реальные TP, M1/P1 | Native TP fills16/13/12. Prefix net151193.03 против150527.63 (+0.442%); 12 financial gates PASS | DD ухудшилась57.5854→62.4160%; нового двухлетнего результата нет |
| M2 SOL | Частичный вход10, три TP+STOP, BTC550 сохранён; independent63/63 PASS | Экономическая польза нового SOL |
| M3/M3R | Исправлена глубина; CAP78 исполнился10+68. Затем найден реальный recovery NO_GO | Последующие M3 gates не достигнуты; ни один FAILED не переименован |
| CODE0 a4ed258 | Минимальный default-OFF recovery, финальные20/20 engine-free checks PASS; peer0P0/P1 | Native исполнение и полная финансовая/экономическая квалификация нового кода |

CODE0 только для BREACH сравнивает частичные исходы с тем же baseline уже работающего BTC TP; полный endpoint обязан быть safe. Новый reduce-only LIMIT IOC имеет проверенный ценовой предел из phi/fee/tick, а не предположение о цене MARKET IOC. Partial IOC ждёт свой terminal и известные protection ACK с исходным deadline, затем остаток доказывается заново по фактическому состоянию. Pending-fill credit не добавлен. Обычный admission, старые TP GTC/STOP_MARKET и financial reader сохранены; при default-OFF действует прежний путь.

Native Money rounding проверяется консервативно. Отрицательный signed cost старого TP, неаффинная fee на Money-lattice и известный STOP fault отвергаются/сохраняют приоритет fail-closed. Подробности и source/test pins: code0-recovery-20261028/IMPLEMENTATION_REPORT.json, FINAL_SOURCE_ACCEPTANCE_RECEIPT.json, INDEPENDENT_FINAL_REVIEW.json.

Обобщение количеств завершено после прямого owner approval d9095fa9. Новый source b1807f15043522b57d3e76527586f152c2db572c: удалены только ceilings BTC1/SOL132.9, количества из actual Cache/working TP leaves. Четыре уникальные focused checks PASS (synthetic actual-native-object BTC2/SOL−200 и negatives), peer0P0/P1. Это отдельная дельта к bounded20; не24 connected. Прочие runtime bytes/guards неизменны. Исторический отказ automatic review сохранён; обхода не было. Полная применимость по tiers/направлениям/миллионному капиталу не доказана.

Published source3f555d94cad009a0170b4c15230e18b84811c387: read-only Features/OrderSide receipt codec2focusedPASS и prospective M3 runner/data/binding, peerclosure0P0/P1. Trading/risk b180bytes и числовой reader unchanged; native0. M3partial-only/fullendpointREQUIRED_M8; sealedsourceclosure требует root postrun. Все четыре initialprepP1 и исправление сохранены.

Выявлена важная область применимости: реальные старые P1 notionals существенно выше firsttier; real causal funding coefficients не обязательно0. Текущий native CODE0 сохраняет firsttier/longBTC-shortSOL/onehistoricallyfilledTP/funding0 guards, поэтому универсальная применимость не доказана. Условно доказан более общий SOL-only pointwise контракт Factual(x,z)<=max(Factualold(x,0),0) при universallySAFEfullendpoint и полном cashrounding cap. Он позволяет предложить одно расширение signs/tiers/multipleBTCordinaryTP/knownfunding через существующий exactpartitioner, без нового PnL движка. Код этого расширения не реализован и не разрешён.

CODE0_NEXT_QUALIFICATION_DRAFT_RU.md готов, peer0P0/P1, OWNER_APPROVED receipt171aacb8: сначала source-bound cashproof/code/pure/review/freeze, затем+1freshM3 (cap19,engineering12,prefix6/full1), далее прежние обязательные cases/экономические gates. Старые9attemptrows неизменны, ledger9/19/root_goFalse; текущаяimplementationpureonly; никакого переноса слотов и autorerun. P4 диагностический, DD>50 сам по себе его не инвалидирует; P3 требует обеDD50. Финансовая квалификация нового source и ROI/DD UNKNOWN.

Цели DD30–50% и сохранения не менее90% исходной прибыли остаются NOT_MET. Full S0 TOTAL6077107.23887483, seed10000; промежуточный70% TOTALfloor4256975.067212381, финальный90%5470396.514987347. Нового ROI/DD от CODE0 не измеряли.
