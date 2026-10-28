# Method A: текущий проверенный результат

Физические попытки: 8/18 — 5 COMPLETED/OS0, 3 FAILED/OS1; активных нет. Engineering 5/10, prefix 3/6, full 0/2. Пилот и production не изменялись.

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

M2A после отдельного согласованного DATA/harness-исправления завершён OS0: источник c5a2f137, UUID6b54e679-e091-421f-bce6-1d0ab4d1674f. Независимый engineering-review: 63/63 PASS. Native SOL IOC210.9 исполнил10, остаток отменён; TP1/2/3 и STOP102 реально приняты. SOL TP исполнились2.5@99,2.5@98,5@96. BTC550 сохранился без paired debt и затем закрылся собственными тремя TP. Flat/orders0 доказаны до cleanup. Это первый подтверждённый компонентный native SOL результат, не доказательство экономического эффекта/ROI/DD.

Две прежние M2 FAILED остаются в расходе и доказательствах: пустые marginmarks в harness, затем недостижимый post-only SECOND. Одобренный лимит18: engineering4/10, prefix3/6, full0/2; оба резерва использованы. Остались ровно M3–M8, три prefix и два условных full. Повтор M2 не разрешён.

Продолжается bounded DATA/harness подготовка M3: cap, настоящие PendingCancel latefills, сохранение защиты и отдельный ожидаемый partialSTOP fault. При PS132.9/PB107 найден точный allpartial CAP-envelope PASS; капитал для второго естественного parent пока не квалифицирован. Новых native активных/GO нет, торговые параметры и ядро BTC сохраняются.

В consumer обнаружена отдельная проблема формата sequence: готов report-only patch48testsPASS; raw сохранён. Переход пустого episode остаётся отдельным UNKNOWN, его не маскируем. Полная финансовая квалификация SOL и цели70/50,90/50 остаются NOT_MET. Пилот/production не менялись. Подробности: ACTUAL_M2A_ENGINEERING_DISPOSITION.json и review-evidence/m2a-actual/.

Продолжение 28 октября: M3 candidate имеет23 focused PASS и независимое review0P0P1. Исходная фиксация/копирование на Mac ещё не подтверждены. SSH control socket умер, одна свежая попытка соединения завершилась banner-exchange timeout. Новых native/ledgerclaims нет; расход7/18. Точный checkpoint: RESUME_CHECKPOINT_20261028.json.

M3 actual 28 октября: SSH восстановлен без изменений сервисов; source6591609 зафиксирован, Mac engine-free5checks PASS. Единственная M3 UUID63ad9d1a-a374-472f-ba03-d02fb2f4e997 завершилась OS1 на69s: BTC316.875/SOL210.6 вместо200/132.9. Первая дивергенция на66s: повтор одинаковой BBO глубины не восполняет уже потреблённую native ликвидность. Ошибка DATA/harness-планирования, не доказанный дефект продукта. STOP/retiringlatefill gates не достигнуты. Cleanupdisposed5/5 не является casePASS. Расход8/18; повторов/нового nativeGO нет. Raw/log/ledger snapshot/failure-artifact-manifest сохранены; аудит завершён: ACTUAL_M3_FAILURE_AUDIT.json. Native source подтверждает сохранение consumed-depth при том же размере. До69s native margin/state/protection оставались согласованы, но последующие M3 gates не достигнуты. Предложена только DATA-коррекция глубин66s116.874/67s116.251 с учётом рыночных TP; native-повтор не разрешён и не выполнялся.
