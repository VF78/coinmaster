# Method A: текущий проверенный результат

Физические попытки: 6/17 — 4 COMPLETED/OS0, 2 FAILED/OS1; активных нет. Engineering 3/9, prefix 3/6, full 0/2. Пилот и production не изменялись.

BTC TP1/TP2/TP3 стали реальными в исследовательском runtime a4dd469 (default OFF). M1 подтвердил лотовые права, SECOND и очистку native-ордеров; P1 подтвердил их на историческом prefix. Это ещё не доказательство двухлетнего результата.

| Одинаковое окно 01.09.2024–15.01.2025 | P0R: прежние BTC TP + старый SOL | P1: реальные BTC TP + старый SOL |
|---|---:|---:|
| Начальный капитал | 10000 | 10000 |
| Конечный капитал, USDT | 160527.62564425 | 161193.03051897 |
| Чистая прибыль, USDT | 150527.62564425 | 151193.03051897 |
| Settled / coherent event DD | 57.5854104596% | 62.4160211977% |
| Денежная невязка | 0E-8 | 0E-8 |

P1 сохранил 100.4420483429% прибыли контроля, прибавка 665.40487472 USDT. Native TP1/TP2/TP3 дали 16/13/12 исполнений; все 12 финансовых gates PASS. Проверены 133881 held-BTC кадров и 16/16 actual SOL_ADD rights. Изменение включает влияние собственного капитала и последующих действий старого SOL; отдельный вклад BTC этим сравнением не выделен.

DD вырос на 4.8306107381 п.п. Реальные TP прошли локальный порог роста ≥70%, но сами проблему риска не решили. Независимое решение: TP_SCREEN_PASS_ALLOW_SOL_ENGINEERING_PREPARATION (ACTUAL_P1_TP_SCREEN_DISPOSITION.json/.md).

Первый P0 остаётся COMPLETED, financial UNKNOWN: исходный observer пропустил шесть обязательных фактов. P0R использовал единственный заранее разрешённый prefix harness reserve. Его fill/cash/funding/scalar trace точно совпал с P0; квалификация P0R выдана отдельно. Исходные доказательства не переписаны.

Следующий разрешённый этап — реализация настоящего SOL risk-owner в изолированном VPS-worktree и инженерные M2–M8. Пока готов pure solver: 9 focused tests; независимые 350 малых переборов подтвердили сжатие envelope при оговорённых условиях. Расчётное ядро12cbafa независимо проверено; source-integrationf3 прошёл один correction batch eadcbc3 (два P1 закрыты), ordinary DENY/ALLOW seam завершён a8/5c31bbe (10 focused checks, narrow closure0P1). Native adapter ещё не квалифицирован. Открытые gates: native parity/lifecycle, пять групп producer bindings и семь конкретных case recipes. Математические примеры M2/M3/M8 получены на VPS, но не являются native-case PASS. Новых native GO пока нет.

После инженерного PASS остаются ровно P2/P4/P3; два full условны. Цели ≥70% и затем ≥90% исходной двухлетней прибыли при DD≤50% остаются NOT_MET. Новый SOL пока не имеет native- или экономического подтверждения.

Первый M2 (3950947b-96d4-4534-a729-c85b90c2a114, source68dfd07) FAILED после первого BTC fill: UNKNOWN_NATIVE_MARGIN. CustomData/VenueMark не поступал в exchange module, а static marks были пусты; модуль очищал IM/MM. Независимая диагностика совпала. SOL ещё не прошёл native-case. Кандидат исправления ограничен test runner и existing static mark API; до replay нужны неизменность продукта/данных/recipe/latency и временная причинность. Единственный harness reserve пока не израсходован; автоматического повтора нет. Cleanup flat не является PASS.

M2R (d7da970b-e560-4244-b988-5b15348fb164, sourcee20) тоже FAILED: native SECOND был создан post-only по99.7 одновременно с ask99.7 и отвергнут. Фактический BTC275 вместо предполагавшихся550 оставил riskOFF; SOL не открылся. Это ошибка достижимости fixture, не доказанный новый дефект risk-логики. Harnessreserve израсходован, исходный OS1 сохранён. Готовое DATA/harness-предложение независимо проверено0P0/P1 и опубликовано в83a41db, зеркалировано в m2-additional-attempt-proposal/. Recipe53inputs/23quotes/82s разделяет passiveaccept2s/cross3s доstress61 и проверяетactual550. PatchUNAPPLIED. Asyncзапрос на+1 (общий18/engineering10) показан владельцу; ответа пока нет. Новыхзапусков/capchangesнет. Все экономические цели и nativeSOLhedgePASS остаются NOT_MET.
