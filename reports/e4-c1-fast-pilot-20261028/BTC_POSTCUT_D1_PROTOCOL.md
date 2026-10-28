# BTC post-cut D1: последний кандидат в текущем лимите

Manager protocol under direct standing owner authorization for necessary CoinMaster R&D; не отдельный новый числовой ответ владельца. Live START не разрешён. До native обязательны source/review/freeze/preflight/rootGO.

Основание: FIRST_FRESH_COMBO sourceff253/config078268 дал TOTAL5500482.01310960 (floor+30085.498122253), но обеDD55.35211621214503813510235076%. Риск вырос после фактического раннего BTC restore27.11.2025 16:02; январская DD51.26863558%. Денежные цепочки и108native lifecycle точны0E-8. SOL restore04.10 08:02 действительно восстановил ранний капитал.

Единственное новое правило: восстановление BTC после protective cut требует одного полностью закрытого BTC D1, сформированного целиком после последнего ACTUAL cut-fill. Это родной таймфрейм основного BTC signal. SOL, все BTC-входы/размеры/TP/reference, общий first-fresh H4 фикс, cut25%, restoreDD40, fees/data/model сохраняются. Никаких датовых исключений, цвета свечи, ATR-контроллера, подбора задержек или восстановления по календарю без наблюдённого бара.

Точная семантика:
- Matching BTC D1 должен быть фактически принят тем же signal-путём, что обслуживает основную стратегию; `open_ns >= last_actual_cut_fill_ns`, полностью закрыт, `available_at <= current valid money.source <= decision_ns`. Не достаточно заранее сгенерированного события; SOL D1, future/out-of-order/malformed bar не разрешают BTC restore.
- Проверять guard на ВСЕХ BTC restore: normal и deferred. Он расположен до TP-cancel и native submit. Пока day gate не выполнен, хранить действующий H4 confirmation/actual credit и не потреблять restore attempt; ordinary/mandatory exits и revoke сохраняют приоритет.
- Зафиксирован вариант A до native результата: универсальное FIRST_FRESH СОЗДАНИЕ/проверка market confirmation остаётся прежним для обоих активов. До появления post-cut D1 первый свежий BTC quote всё равно может отклонить/потребить deferred candidate по прежним DD/reclaim правилам; это не native restore attempt и не расход credit. Такой отклонённый сигнал не воскресает позже.
- Новый D1 guard относится только к ИСПОЛНЕНИЮ восстановления. Успешно созданный обычный H4 confirmation хранится при ожидании D1; до TPcancel/submit guard проверяется на всех BTC restore. После него идут прежние execution DD40/цена/reclaim/ownership/margin/реальные ACK. SOL и scheduler FIRST_FRESH не получают специальных исключений. Нет гарантии исполнения на D1 close. Новый actual cut-fill сдвигает day gate.
- SOL не меняется. DefaultOFF сохраняет все прежние configs/экономические ветви. Новая metadata и флаг явно фиксируют policy. Состояние/полная policy identity должны быть включены в будущую live-интеграцию; stale cached money не становится permit.

Admission `evidence/D1_POSTCUT_BTC_ADMISSION.json` SHAed33ca9c24f3354a8ff37c35519777f8cc9925c1b8afabdebdde8d022869fd98: на14 actual group paths доказан первый command delta — удержать BTC cancel27.11 16:01 и restore16:02. Первый полностью post-cut D1 OPEN28.11 00→CLOSE/available29.11 00. SOL Oct/Jan не затрагивается; June actual credit revoked раньше первого подходящего D1. Всё после первой новой разницы — UNKNOWN новый native путь, не старые qty/PnL.

Проверки без движка: actual D1 producer→strategy dispatch, cut внутри дня, bar open до cut, future/unobserved/SOL/out-of-order, late cut fill, ожидание без cancel/attempt/credit loss, обычные exits/revoke, unchanged SOL, pending real ACK after admission, OFF configs. Один focused peer pass/конечная правка; без новых short/native fixtures.

Бюджет: 5candidate+1unusedcontrol+2conditionalqualifier → **6candidate+0control+2qualifier**, общий max8 неизменен. Уже5 native exit0, active0; donor CONTROL_E4 не запускался. MethodA/старые budgets не заимствуются. До ОДНОЙ новой попытки BTC_POSTCUT_D1 на прежнем [2024-09-01,2026-09-01),seed10000/reserve0. Ошибки учитываются, повторов/резерва нет. Claim registry до Popen, actual child exit.

Цели без изменения: TOTAL>=5470396.514987347, ориентир5631617.35953723; обеDD<=51.80315157406654834417870238%, strict50 отдельно. Native PnL и cash bridges literal0 или UNKNOWN; model liquidation0/terminal status. Если проходит — freeze и2условныхqualification. Если не проходит — честный NO_GO, без выдачи оставшихсяqualifier за новые candidate slots. Пилот/production/ключи/переводы/реальные ордера не меняются.
