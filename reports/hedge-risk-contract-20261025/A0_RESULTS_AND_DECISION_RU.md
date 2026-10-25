# A0: текущий результат и экономический gate

Статус: LIMITED_PASS инженерных компонентов R2 paired; первый prefix из3 FAILED доengine из-за неверного data_root, экономического результата нет. Дальнейшие запуски HOLD. Цели исходного победителя ≥70%net при DD≤50%, затем ≥90%, пока NOT_MET. Full/training/download/pilot/production0.

Engineering закрыт **7/7:3COMPLETED,4FAILED,active0,remaining0**. Прямое согласование +1 и exactPUBLIC destination сохранено отдельными receipts. Исходный closed6 ledger SHA c0b84b39c5199671a258a8dcda6301ef3fd641f64be357e8c165be3aa0ffa424 и все шесть старых строк неизменны; amended-seven ledger содержит единственный новый instance7. Все прежние четыре connected processes OSrc1 и FAILED1/3/5/6 сохранены. Actual7 процесс завершился OSrc0.

Подтверждённые native-компоненты:

- Instance2: stock marginPASS, partialFIRST, право только на исходный second-child, permanentlyclosedBTCcap, originalGTC, actual3TP/nativeflat/cashidentity. Ранний dispose warning не превращён в clean lifecycle.
- Instance4 combined: old latefill1→newpartial2→ordinaryBTC TP/immediatecancel→newlatefill3→actualexcessdebt/capcorrection. Нет повторного права, reanchor или возврата закрытого BTC. Actual3TP/flat/cash и 5компонентов STOPPED→DISPOSED.
- Instance7: UNKNOWN текущих TP ACK блокирует A0; настоящий ACK снимает блокировку; postOnlycross WAIT без grant. Реальная штатная margin policy трижды отказывает при устаревших marks и разрешает исходный добор после свежих VenueMark. Один originalGTC158.125 исполнен native1+157.125, real3TP/NATURAL_TP_FLAT, positions0/orders0/inflight0, cashidentity и clean lifecycle подтверждены. Это synthetic diagnostic fixture, его прибыль не является экономическим результатом рынка.

Независимое финальное ревью: LIMITED_PASS/P0=0/P1=0; root admission receipt a0-root-engineering-admission.json. StandaloneC0 nativefixture NOT_RUN, fullfinancial parity/venue/fullROI не доказаны. Критический UNKNOWN marginDENY/recovery теперь снят фактическим instance7, а не report repair или fake money.

Что не сработало в harness и исправлено без изменения денежного package340f: instance1 synthetic start не оставил completed day;3 повторён consumed native depth;5 задержан только один из двух acceptance callbacks;6 mutable.clear вызван у tuple. Новые проверки используют stock guard/свежие displayeddepths1→2→3/sharedaccepthelper/naturalstaleclock→actualVenueMark. Все исходные ошибки сохранены.57 engine-free tests PASS; reviewer tests/engines0.

Источник763d985617abd7a7afef5eec13912303983d8837 опубликован в PUBLIC VF78/coinmaster branchcodex/hedge-rights-unlock-20261025, exactremoteSHA проверен; deployment0. Старые publication-block receipts исторические, новое точное human approval получено и успешно применено.

OFFphysical1 из утверждённых3 завершился OSrc1 доengine: `INCOMPLETE_1M_COVERAGE:MISSING_1M_MANIFEST`. Orchestration взяла engineeringroot `/inputs`; реальный экономическийloader требует `/inputs/data`, куда уже указывают все31 frozen input pins. Actualnativecoverage_blockers на первомroot возвращаетmissing, на правильномroot — []. Старый --prepare проверял roundtrip/hash, но пропустил actualstockcoverage/reader preflight; это ошибка нашегоharness. Нет TOTAL/4artifacts/financialqualification. FAILED1, namespace, sourcefreeze/logs/error и ledger сохранены.

Текущий budget1/3 FAILED/active0, остаётся2, цепочка HOLD. Чтобы выполнить все три свежих контроля OFF→C0→A0 [2024-09-01,2025-01-15)UTC, seed10000/reserve0, нужен общийcap4 (+1), с прежней failedattempt1 в счёте и тремяfreshnamespaces. Такое расширение пока NOT_APPROVED. Сначала готовятся только engine-free path+actualstockloader/coverage/warmup исправление/предложение/ревью; новыхPopenнет. Source763, candidate, sourcefinancialproducer и входныефайлы не меняются. После согласования rootGO каждогоотдельно. ActualC0 completefinancial/accounting/coverage/ownership/zeroLiq/terminalflat PASS обязателен передA0. При UNKNOWN нет автоматической следующей попытки.

A0 growthgate: gain>C0 и2max(0,incrementalfees), settled+coherenteventDD≤50% и≤C0, dailyES20 по всем136UTCдням≤C0; нужен настоящий additionalBTCfill, иначе NOT_TESTED. Prefix неfull/OOS/70/90proof; основной BTC entrycore и SOL TP/cuts/rearm/fees/funding/data сохранены.
