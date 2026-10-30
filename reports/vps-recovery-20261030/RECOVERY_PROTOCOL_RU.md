# Эксплуатация и восстановление CoinMaster —30.10.2026

Владелец поручил аудит/исправления prodVPS, безопасную очистку включая rollback, автовосстановление после связи/аварийной перезагрузки и сверку с Nautilus docs без дублирования штатных функций. Это подготовка; отдельного START по-прежнему нет. Перезагрузка сервера/разрыв настоящей сети/реальные заявки/подписи/переводы не входят в проверки.

## Согласованный механизм

Используются systemd, stock Nautilus1.231 и stock Redis7.0.15. GUI/broker/Redis автоматически перезапускаются через15с без исчерпания лимита; отключены старые неработающие Sandbox/Bybitwarmup автозапуски. Live остаётся disabled/inactive. Его boot-enable выполняется только при отдельном явном START квалифицированного релиза. Старая неактивная ссылка current удалена вместе с rollback; это не активация нового кода.

Нативные orders/accounts/positions/eventlineage сохраняет штатный NativeCacheRedis на authenticated127.0.0.1:6380, AOF/appendfsyncalways/noeviction. Общие load_state/save_state остаютсяFalse: имеющийся SQLitejournal восстанавливает стратегию единственным существующим способом. Нативный kernel сначала загружает Cache и делает reconciliation; специальный второй OMS/симулятор/eventstore не вводится.

При обнаруженном обрыве execution/data связи, gap закрытых M1 или неожиданной смерти native thread supervisor завершает worker с ошибкой. Systemd запускает процесс заново, nativeCache/reconciliation/HLhistory восстанавливают подтверждённое состояние. Штатный stop не отменяет standingTP и не делает marketexit. Новые команды после reconnect допустимы только при исходных точных journal/cache/venue parity, свежих деньгах/данных и разрешённом durableRUNNING. ExplicitPAUSE/STOP/DP55 не сбрасываются; freshINIT остаётсяPAUSED. При missing/foreign/UNKNOWN автоматического восстановления торговых прав нет, команды повторно не отправляются.

## Исправление фактической несовместимости

В точном pyo3binary97f3dc49…321e нет требуемого прежним d8адаптером connection_epoch. Прежний synthetic transport скрывал это. **Готовность d8 для live отозвана до квалификации исправления.** Native fork/upgrade не нужен: исправленный контракт STOCK_1231_VERIFIED_SNAPSHOT_V1 использует реальные is_active/is_closed и существующую свежую mass/account/cache/journal проверку.

Локальный verified_observation_generation публикуется только после полной успешной parity. Это поколение проверки, не счётчик native reconnect. Все существующие≤9сdeadline/подписи state/cache/order/position/control/DP/journalrevision сохраняются. Ненаблюдённый быстрый reconnect может попасть в действующее≤9сокно снимка: этот предел явно учитывается и не выдаётся за venue-atomic continuity. Версия контракта входит в policyidentity; старые checkpoint не переименовываются/деньги не сбрасываются.

## Проверки и бюджет

Сначала focusedengine-free/nativeobjects/cacheobjects tests, primary-doc/source сверка и одно независимое ревью точного freeze. Затем только по конкретному rootGO — максимум **4 новых физических native node/engine попытки**, включая все неудачные. Это выбранный координатором предел проверки текущего поручения, не отдельный числовой ответ владельца. Старые4/6 и10/10 закрыты/не заимствуются. Полных/prefix экономических прогонов0.

План двух основных процессов: W01 настоящийnativeNode с отдельным ephemeralRedis6390 сохраняет nativeorder/fill/position и standingTP+SQLite; аварийно завершается после подтверждённой записи. R01 новый процесс/тот жеcache+SQLite через stockload_cache+reconciliation доказывает exactownership/no duplicate/newfreshness/сохранение HWM/seed/intent. Остальные два слота только на конкретную диагностированную ошибку. Негативные missingcache/foreign/no-fillanchor/manualPAUSE/DP/latefill/expiredcommands — целевые проверки без лишних nativeзапусков. ProductionRedis6380 не получает тестовые данные.

Перезапуск Redis/AOF в изолированном fixture и SIGKILL только собственного тестового процесса разрешены; productionперезагрузка/сетевая блокировка отсутствуют. Активные GUI/broker меняются только по названному безопасному plan и проверке поведения. Уникальные данные/результаты/секреты/исходники сохраняются; удаляются доказанные копии/unusedrollback/caches с manifest.

## Производительность и приёмка

Никаких слепых оптимизаций по latestRust2.0guides: версии API проверяются по установленному1.231коду. Не включаются лишние purge/strategyrestore/таймеры/поллинги, дублирующие stock. Фактический горячий путь checkpoint/quote исследуется и измеряется до изменения; сохраняется durabledecision-before-command. Итог — точныеsource/config/engine hashes, закрытыйledger, изменённыеunitreadbacks/bootpolicy, nativefailure/restartдоказательства и обновлённые Project/ACTIVE. Ни публикация, ни установка inactive-релиза не разрешают START.
