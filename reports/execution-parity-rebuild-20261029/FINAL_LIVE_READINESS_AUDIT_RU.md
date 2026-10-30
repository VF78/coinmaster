# Итоговый аудит готовности A — 30.10.2026

Вердикт по коду и доказательствам: READY_FOR_GUARDED_PILOT. Критических P0/P1 в проверенном контуре не выявлено. Это готовность к малому контролируемому live-пилоту с ручной сверкой неопределённого состояния; автономное восстановление произвольных открытых позиций не квалифицировано. Отдельное явное START владельца отсутствует. В ходе аудита реальных ордеров, переводов, подписей, новых native/full-прогонов и изменений трейдера0.

## Релиз и свежая проверка

Source4ca0d87993f28c20fb039840551c04e051378582, неактивный service-layout релиз в /srv/coinmaster/hl-live/releases/4ca0d87993f28c20fb039840551c04e051378582-sol-staging-a-live-inactive-native1.231.0-api-v2. Повторная read-only проверка immutable release:92файла, packagedCandidate, importorigins, профиль и nativepins совпадают. Manifest36809b9e0f7ac1cb876e0fde446c3e71418738680f82de1f27fd84b320e37323; profilead8f9950b6a9a837c32eb98c1abcb182f741a1f74475ceea27c3d4860f9583a9. Native1.231.0. Currentlive6c208 не переключён; liveunitinactive/dead/disabled/PID0.

Свежая read-only сверка именно установленного4ca:30.10.2026 11:51:26МСК, PASS. Default credentialpreflight, signer/master, Unified, USDCfree,11DEXflat/orders0, ограниченный по времени снимок, DP55 и запрет неутверждённого START проверены. Финансовые account-derived поля приватны. Штатный START снова получает актуальные факты; старый снимок не является разрешением на ордера.

## Рабочий пользователь и реальный путь подключения

SystemdUser/Group=coinmaster-hl-live. Проверка прямого чтения исходной brokerзаписи этим UID дала false; первоначально это было слишком рано названо блокером. Проверен полный рабочий путь: unit использует LoadCredential=connection.json из той же canonical записи; PID1/root может открыть источник0600. Загруженный unit соответствует /etc/systemd/system/coinmaster-hl-stageg-live.service, dropins отсутствуют, NeedDaemonReload=no. EnvironmentFile содержит только имя переменной controltoken, конкурирующего торгового ключа там нет; значения не выводились.

Workerhl_live_worker.py:429 читает CREDENTIALS_DIRECTORY/connection.json. И preflight187, и чтение193, и nativeconfig218 используют эту копию; factoryhl_live_execution.py:1141/1147 передаёт explicitconfig.private_key. Один актуальный источник ключа поэтому используется для проверки и торговли. Прямой доступ serviceUID к исходной записи намеренно закрыт; это корректная изоляция, а не отсутствующее разрешение. ACL/chown/новая копия секретов/кодовые исправления не требуются. Копию runtimecredentials создаёт systemd при утверждённом старте; она не выдаётся за уже открытый активной службой файл.

Целевая DB /var/lib/coinmaster-hl-stageg-live/hl-stageg-live.sqlite отсутствует; родитель доступен службе для записи, ожидается freshINIT. СохранённогоDP50 нет. Проверены traversal релиза, executablePython и читаемость instanceconfig.

Currentalias намеренно всё ещё6c208: это ожидаемая граница между подготовкой и START. Прямая команда старта существующей службы сейчас выбрала бы старый релиз. После явного подтверждения сначала нужна квалифицированная активация именно4ca, затем свежая prestartсверка и запуск. В ходе аудита alias не переключался.

## Исходные экономические результаты проверены независимо

| Проверка | A10K | Фактический малый капитал |
|---|---|---|
| SHA исходного native-report | c01a9626317680a2461153148128ea8725178594c2e65a47a02c1ba9e5990f6f — совпал | 7097c2153bda7f44ac34054aff2647a3476fe2b07012f2f26d596f377b2df642 — совпал |
| Весь интервал01.09.2024–01.09.2026,24месяца | PASS | PASS |
| Все11 проверок исходного process-result | PASS | PASS |
| Supervisoractualexit0, timeoutfalse | PASS | PASS |
| Ликвидации0, конечные позиции/ордера0 | PASS | PASS |
| economic_failurefalse, полный coverage | PASS | PASS |

Проверены именно native-report/process-result/supervisor-result/coverage текущих двух кейсов на VPS, а не только сводные заявления. TOTAL10K5635720.91989984USDC; net5625720.91989984; ROI56257.2091989984%; settled+coherentDD51.4383711874%. Фактический капитал также прошёл scaling gate; суммы и его PnL не публикуются. Десять экономических файлов неизменны относительно выбранного A.

RawNOT_FAITHFUL_DIAGNOSTIC/ranking_eligibleFalse сохраняются. Они относятся к честно обозначенной исторической модели: Bybit1mproxy/currentHLrules/zeroimpact, а не к финальному инженерному запрету на пилот. Статус PRIMARY_OBJECTIVE_MODEL_PASS_NOT_LIVE_READY в comparison.json — сохранённый итог модельного этапа; последующие релизные проверки перечислены здесь, исходный статус не переписан.

## Код и реальный объём инженерного доказательства

Независимый узкий аудит: P0/P1=0. Финальная native submission проверяет актуальные journal/native revision, одноразовое право, threadidentity, WSepoch, деньги и срок authority. Reduce-only ограничен принадлежащей стратегии нативной позицией за вычетом pending/uncertain reductions. DPпрофиль требует55/.45, worker передаёт55. Initialseed берётся из сохранённого epoch, а не текущего NAV после рестарта. ForcedSOLREGIME/TRAIL/TERMINAL использует свежий положительный executableBBO и неизменяемый120sdeadline исходного решения; expiry переходит к штатной сверке.

Наследуемое native engineering доказательство: reports/e4-c1-fast-pilot-20261028/evidence/native-final-A23-B24-acceptance-20261029.json, source5f10ce870b18fd8181b57c23f0d9d36d3e867d67. A23: фактический TradingNode,8 синтетических отправок/4cancel,11gatesPASS/exit0. Покрыты entry/split, TPpartial, partialIOC/latefill/duplicate, C1cancelACK/cut, DP55nativeclose/flat, lostACK/reconnect/noresume. B24: отдельный фактический TradingNode с той же durableDB,3gatesPASS/exit0; paused-flat restart сохраняетH55/latch/rights/clocks, старые деньги не дают новую freshness.

A-resultSHAffb73a43cfb4bda13f2b23f6799294d35cd04a81bcd03a7a4895b2ba95f9cd8b; B-resultSHA9f1178c2413a163f2f4cf84d37f405f5fec87a76de73ce08832ab724e7dafe96; restart-proofSHA447ae471f9e556872af3c72cc08f14eaa57f29db82d8310f6479f4f3fd9cde4e. Оригиналы сверены в VPS research-worktrees/e4-c1-native-acceptance-20261029/runtime/var/native-acceptance-20261029-1b27/A23-artifacts.

Это реальные native Cache/Portfolio/callbacks и USDC AccountBalance при управляемом unsigned/fake transport. Внешней торговли там0. Доказательство реального matching Hyperliquid появится в пилоте. Для нового wrapper4ca дополнительно63native-object/SQLitepurePASS + review0P1; свежий полный nativeцикл именно4ca не запускался и не заявляется. Одни63pure не заменяют A23/B24. Старый экономический5f10 extended backtest сUSDT/DPoff не используется как доказательство livetransport/restart.

## Три ошибки тестов

Широкий пакет200PASS/3FAIL; все три повторены на неизменённой базе5c886 и разобраны причинно:

- test_live_recovery_state.py:138 не подключает recoveryruntime: реальный _record_submission отказывает раньше ожидаемого healthprobe. В рабочем пути WSepoch проверяется при health и перед submit.
- test_live_recovery_state.py:147 ожидает позднюю identityошибку, но неизвестная schema отклоняется раньше structurevalidator. Это fail-closed, не принятие повреждённого состояния.
- test_e4_c1_input_bridge_pure.py:450 ASTfixture не включает staging_a_epoch_seed. Рабочий worker импортирует его в строке34 и вызывает в236.

Это дефекты тестовых сценариев, а не обнаруженные дефекты liveпути. Широкий пакет не объявляется полностью зелёным; их чистка остаётся техническим сопровождением, без нового экономического прогона.

## Ограничения пилота и следующий шаг

- DP55 означает порог срабатывания защиты при остатке45%, но не гарантированный предел фактической потери при gaps/delays/частичных исполнениях. От измереннойDD51.43837 до порога3.56163п.п.; от OHLCсценария52.10531 —2.89469п.п.
- Реальная ликвидность/цена/funding отличаются от proxy. Пилотный BTC/SOLbook snapshotPASS; будущая ёмкость не доказана. Fixed-path +10bps cost1730699.906366428USDC не является пересчитанным ROI/DD. См. FIXED_PATH_COST_DIAGNOSTIC.json.
- Неопределённые ACK/позиции после разрыва требуют ручной сверки; автоматический takeover не доказан. Остаток ниже native minnotional может потребовать ручной обработки. Запрета повторного входа или учёта pending как fill не ослабляли.
- A сохраняет SOLalpha/staging и BTCcore. Новый настоящий SOL-хедж — #138 после стабильного live. GUIредизайн/auth — #105, отдельный GUIdeploy; это не приписывается готовому движку.

После явного START: штатная свежая prestartсверка, утверждённая активация точного релиза, actualflatINIT из доступногоUSDC, наблюдение первого реального цикла и подтверждение native/venue fills/fees/positions. Увеличение капитала и автономное промышленное сопровождение не считаются уже проверенными этим аудитом.

## Project

Readback30.10.2026 12:06:45МСК:10активных карточек —7Done/1InProgress/2Todo. #137 закрыта completed и переведенаDone; #101 остаётсяInProgress до реального rollout и проверки первого цикла. #105 возвращена на доскуTodo с актуальными GUI/TradeHistory/auth задачами; #138Todo после стабильного live. Три устаревшие карточки #123/#130/#131 убраны из активной доски архивированием; исходные issues/FAILED/rawreceipts сохранены. Дублей активных карточек не обнаружено. Подробный фактический readback: FINAL_LIVE_PROJECT_READBACK.json.
