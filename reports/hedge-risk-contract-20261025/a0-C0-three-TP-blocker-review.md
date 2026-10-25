# C0 native3TP blocker adjudication — 25.10.2026

**Блокер C0 подтверждён, но длительность57120s существенно завышена auditлогикой. A0 HOLD. P0=0/P1=2.** Исходный reportSHA46a4256e7a3710cb4105c8cc5848c6c71b202e4c4aea05b99b4e1d33a3d4a3fb не менялся.

P1 C0-MD01: Jan7 TP1/TP2 уже legitimately consumed: nativeorders257/258 полностью FILLED0.128 каждый Jan6. Остался только TP3. Order269/generation2 принят Jan7 08:16, SELLGTC0.263@103732.6, отменён11:46; order273/generation3 принят11:47 с0.175, отменён Jan8t0. Qty совпадают с coherent native held0.263/0.175. На этих участках обязательная remainingTP защита существовала, отсутствие новыхTP1/2 правильно.

Sourceобъяснение stickyаудита: `_md_after_fill` добавляет consumed0/1, но currentaccepted не очищает. CancelTP3 оставляет accepted0/1; новаяgeneration хранит required{2}, callback снова добавляет2 в stale currentaccepted{0,1,2}. Сравнение `_md_accept` accepted==all−consumed({2}) ложно, поэтому auditне закрывается доflat. Это source-based state inference с actualorders/events; не вывод из113vs117.

P1 C0-TP02: реальные gaps всё же есть. Во всех7коротких60s интервалах и Jan7 08:15–08:16/11:46–11:47 nativeBTCheld>0, все требуемые TP отменены, новыхaccepted ещё нет. SOLTP открывает BTCdebt; ordinaryBTCorders отменяются, `_pair_btc_tp_paused` ждёт actualdebtfill следующейBTCquote. ПоследующиеtargetACK имеют0latency: это serializationgap, не delayedACK/dust/consumedlevels ошибка.

Внутри8reportedintervals разделение: **540s реального отсутствия обязательныхTP +56580s falsepositive coveredstate =57120s**. Это adjudication этих интервалов, не новыйglobalprotectionaudit. Уже540s достаточно для FAIL текущего native3TP gate; исходные metric/report/financialreject не исправлялись и не ослаблялись.

C0OS0/accounting/funding/coverage/flat не дают финансовойqualification при таком blocker. A0остаётсяHOLD, последнийprefixslot unused; никакогоwaiver/новогоrun/sourcefix. Если продолжать, нужно отдельное решение по настоящему gap/аудиту, не переименованиеFAILвPASS. JSON содержит intervalnativeorderIDs/generations/qty/terminaltimes, source/evidence hashes и точныйscope. Reviewer native/Popen/code/metric/receipt edits0; fullstream/sourceaudit не повторялся.
