# A0: инженерный результат и следующий gate

Статус: ENGINEERING_INCOMPLETE / ECONOMIC_PREFIX_HOLD. Цели ≥70% прибыли исходного победителя при DD≤50%, затем ≥90%, пока NOT_MET. Новых экономических результатов нет: prefix0/3, full0. Пилот и production не менялись.

Утверждённые шесть native-fixture instances израсходованы: 2 COMPLETED, 4 FAILED, active0, remaining0. Это четыре запуска connected-runner, каждый с фактическим OS rc1; завершённые экземпляры внутри них — доказательства отдельных компонентов, а не успешные процессы. FAILED1/3/5/6 сохранены. Ledger SHA c0b84b39c5199671a258a8dcda6301ef3fd641f64be357e8c165be3aa0ffa424.

Что подтверждено native-состоянием:

- A02: штатный допуск по марже, частичный первый IOC, право только на исходный second-child, сохранение уже сокращённого BTC, реальный GTC-добор, три исполненных TP, native flat и cash identity. Ранний dispose warning сохранён; чистый lifecycle задним числом не приписывается.
- Combined A03/A04: позднее исполнение исходной заявки, новый частичный добор, немедленная отмена при обычном BTC TP, позднее исполнение новой заявки и сокращение избытка. Повторного права/восстановления закрытого BTC нет. Реальные три TP, flat/cash identity и штатный STOPPED→DISPOSED подтверждены.
- В FAILED6 до ошибки: UNKNOWN текущего TP ACK блокирует добор; настоящий ACK снимает блокировку; пересекающая postOnly цена даёт WAIT без submit/grant. Это компонентные факты, не PASS процесса.

Что не подтверждено: фактический native отказ по марже при неизвестных/устаревших marks и восстановление допуска после свежих VenueMark. Последний тест оборвался на `.clear()` у tuple до этой проверки. Отдельный native C0 fixture не выполнен. Экономического допуска нет.

Причины ошибок тестов и меры против повторения:

| Instance | Сбой harness | Исправление / статус |
|---|---|---|
| 1 | Синтетический start не оставил завершённый день; stock guard не создал intent | Fixture start−1day, прежний guard сохранён; subsequent A02 прошёл |
| 3 | Повторён уже израсходованный уровень native book98/size1 | Явные новые displayed sizes1→2→3; combined instance4 прошёл |
| 5 | Задержан только один из двух callback; настоящий ACK уже известен | Interception общего `_accept_native_order`; UNKNOWN доказан в instance6 |
| 6 | `_marks` имеет tuple API, вызван неподдерживаемый `.clear()` | Нужны конкретное fixture-only исправление и новый явный physical budget |

Торговый package после money-review340f не менялся в последующих fixture-коммитах. Первая source-review выявила два P1: допуск до трёх текущих TP ACK и позднюю отмену нового child после BTC TP. Оба исправлены и независимо проверены; их исходные замечания/исправления сохранены.

Следующий шаг — один исправленный A05 с реальным immutable API, после engine-free проверки и отдельного согласования увеличения engineering cap6→7. До него ни одного нового engine/prefix. Неиспользованные три prefix-попытки сохраняются на HOLD, новый резерв не добавляется. Если A05 завершится и review подтвердит компонентное покрытие, возможен только LIMITED_PASS с явным C0_NATIVE_FIXTURE=NOT_RUN, затем отдельные root gates OFF→C0→A0. C0 должен пройти полный прежний финансовый gate до A0. Префикс не доказывает full/OOS/70%/90%.

Исходные доказательства: `a0-engineering-closed-results.json`, неизменённый `a0-engineering-ledger.json`, снимки `a0-fixture-*`, реальные process receipts и независимые source/fixture/component reviews. Исправление, публикация и точное предложение +1 фиксируются отдельными receipts; этот отчёт не разрешает дополнительные запуски.

Prepared fixture-only repair 763d985617abd7a7afef5eec13912303983d8837: natural stale clock→fresh VenueMark,57purePASS, unchanged financial package, proposed extra-one gatefalse. Public source publication blocked by automatic approval review before dispatch; source remains committed locally. Exact +1 proposal: A05_ONE_EXTRA_FIXTURE_PROTOCOL_PROPOSED_RU.md.
