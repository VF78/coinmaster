# Сверка спецификации H1/H2/H3 — 2026-10-23

**Старые precheck-результаты не являются экономическим NO_GO по 50/90.** Полных native H1/H2/H3 было 0; их альтернативные TOTAL/global DD не вычислялись. Принятый v2 заменяет прежний допуск: механически корректные C0/H4/B должны получить native-экономику, даже если страховка имеет отрицательную равновзвешенную price-cost reference. Эта сверка не блокирует C0/H4/B и не включает H1 в новый native-цикл.

## Что было задано и что действительно сделано

Прочитан исходный owner attachment `/Users/vf/.codex/attachments/a864d357-ba2e-4f76-9cc5-216d53a62e39/Pasted text.txt`, SHA-256 `3d47c2918a414d7b8721680cc011e3b4ff296ea32a54456f9c2f2421bc1b3c36`. Принятый v2 `/Users/vf/Downloads/Codex_SOL_Hedge_BTC_Reentry_Plan_v2.txt`, SHA-256 `dc318a114e77470f8feb2b1abf0296d70419ce48aca01dfda2553e16471e19b1`.

| Модуль | Исходный attachment | Фактическая старая реализация | Требование принятого v2 |
|---|---|---|---|
| H1 | +0,25% от actual первой половины, исходное окно 4h; проверить ordinary TP/обязательный выход, стоимость и потерянные восстановления | `bounded-price-collector.py` ограничивает окно первым **actual ordinary fill** или deadline. Ранний trigger/intention/pending exit не экспортирован; 49/105 — верхняя условная оценка, не точные исполнимые доборы | Сохранить 49 как upper bound; H1 исключён из нового native-цикла |
| H2 | Остаток rSOL−beta0*rBTC, предшествующие среднее/масштаб frozen на цикл, k=.5/h=5; simple price stop **с сопоставимой частотой вмешательства**. **Нет 720, ddof=1 или fixed 2%** | 2160 strictly prior hourly log returns, population std (`np.std()`), calibration price stop по 90 непересекающимся 24h блокам и частоте CUSUM на этих прошлых блоках | Явный вариант 720/sample std(ddof=1) + отдельный fixed 2% simple price stop |
| H3 | Actual положительный TP2; максимум fully closed4h после активации; отдача 3п.п. от максимума. **Нет явного best>.03** | `peak-ret>=.03` без guard положительного postactivation максимума. Положительность проверяется для actual TP2 относительно P0, не для последующего peak | Явный `best>.03 AND f<=best-.03`; проверить полные поздние пути, не просто удалить семь ранних событий |
| Допуск | Предварительная экономика для отсева слабых вариантов; native допускается после положительной предварительной экономики. При этом price proxy прямо не равен portfolio ROI | `h1-action-cost.py`/`h3-action-cost.py` ввели положительное event-weighted mean против S0/нулевого cut как gate. `TASK_PLAN.json` зафиксировал старые NO_GO и 0 native | Раздел8 v2 отменяет положительный mean price proxy как обязательный gate для страховки; приёмка — native settledDD≤50%, net-profit retention≥90% |

Поэтому формулировка v2 «было задано720/ddof1/2%» не подтверждается доступным первоначальным текстом. Так же нельзя объявить отсутствие H3 guard доказанным нарушением буквального старого условия: новый guard делает ранее неявную трактовку точной. Это **проверенные различия нового точного контракта и старой реализации**, а не установленное несогласованное отклонение от первоначального attachment.

Прочитаны также прежние `TASK_PLAN.json`, `PROJECT_SCOPE.md` и `research-module-owner.md`. В них 2160/population/frequency-stop и H3 без best>.03 зафиксированы явно; TASK_PLAN содержит утверждение об одобренном общем плане. Эти repo-backed записи не являются отдельным human approval именно этих численных деталей. Отдельное согласование720/ddof1/2% либо отмена такого согласования в проверенном наборе отсутствует; полнота более ранней переписки не утверждается. Грубый факт «несогласованное отклонение» по имеющимся источникам не установлен.

## Уточнение прежних чисел

- H1:49/105 conditional add references, ordinary fill bounds, неизвестные ранние intents/pending. Старый primary unit mean H1 +0,2459421774%, S0 +0,3768103010%; разность −0,1308681236п.п. Это ценовая диагностика второго условного unit/P0, без capital weighting или native equity.
- Старый H2:4CUSUM/26 (SOL18/19/21/26), SOL1 maxG≈2,8797 без тревоги за47 часов. Контроль SOL1 имел adverse log threshold **7,8333454537%**, соответствующий **7,5343955622% простого падения long price**, а не2%. Он также не сработал в SOL1.
- Старый H3:10/28 earliest givebacks. Guard отвергает первые BTC4/15/17/27/35/91/93; earliest BTC22/23/29 его проходят. Старый all28 primary mean −0,3029896019% не относится к политике с новым guard и не доказывает провал50/90.

## Единственный совместный cached recheck

Выполнен `spec-check-method.py`, результат `spec-check-results.json`. Прочитаны один раз нужные массивы existing `/private/tmp/cm-h2-precheck-20261022/all_price_cache.npz`: `opens,BTC,SOL,ht,hp`. **0raw-Parquet price scans,0fetch,0native runs,0new models,0S0 reruns.** Cache достаточен:1 051 200 непрерывных минут на инструмент,19 728 непрерывных hourly closes; все execution-hourly closes совпали с minute-close массивами. Cache SHA приобретён сейчас, а не выдаётся за изначальную hash-attestation. Его исходные raw pins/warmup overlap унаследованы из прежних h2-precheck artifacts. Принятие daily beta сохраняет старое ограничение: reconstructed causal feature, без экспортированного accepted-session receipt.

H2:на всех26циклах пересчитаны строго предшествующие720hourly log returns, frozen entry beta/mu/sample sigma(ddof1), G=max(0,G−side*z−.5), alarm≥5. Fixed2% comparator определяется signed simple price return от actual first SOL entry VWAP:long≤.98entry, short≥1.02entry. Оба проверяются на полностью postentry закрытых UTCчасах до original exit; next1mclose остаётся только reference, не fill. Не менялись k/h и не подгонялась будущая частота.

- CUSUM: **5/26** — SOL15/18/19/21/24.
- Fixed2%: **16/26** — SOL1/3/6/8/11/12/14/15/16/18/19/20/21/22/24/25.
- SOL1:47полныхчасов, **maxG4,0695174089<5**, CUSUM no alarm. Fixed2% срабатывает **2024-10-03 09:00UTC**; следующая minute close reference09:01UTC=135,84. Это не новая альтернативная позиция/PnL, не гарантия действия до DD50.

H3:все28actualpositiveTP2 activations просмотрены до original final fill по fully postactivation4h closes. Максимум продолжал обновляться после каждого отвергнутого раннего giveback. **3guarded triggers** — BTC22/23/29; **новых поздних допустимых triggers0**, в том числе во всех7случаях с отвергнутым ранним сигналом. Здесь итог совпал с удалением семи строк только **после полного поиска**, а не как допущение. Next-close references строго до original final exit остаются условными; actual intent/pending/native action eligibility неизвестна.

Для сопоставимости старого diagnostic формата пересчитан next-original-fill price-cost mean на всех28activations (no action=0): **−0,1197013549%**. Это не portfolio PnL, не retained TOTAL и не veto native.

Проход:0,092s внутреннего времени, peak RSS83 525 632bytes. Исходные отчёты неизменны; новая торговая логика и native-engine не затрагивались. Единственное вычислительное расширение — этот совместный cached проход. Детали строк/исходные hashes в `spec-check-results.json`; полный набор читаемых доказательств и hash исходных/новых файлов — в `spec-check-provenance.json`.
