# Подготовка live: единый порядок после уточнения владельца

Текущий статус: победитель ещё не выбран. Пятый FIRST_FRESH прошёл прибыль (TOTAL5500482.01310960), но не DD (55.3521162121%). Шестой BTC_POSTCUT_D1 запущен один раз в общем max8. Два qualification-слота сохранены. Реальный live требует отдельного явного START владельца после готового алгоритма.

## Параллельно исследованию

- Аудит текущего пилота выполнен только чтением. Worker release81e6318/NT1.231.0,55source files match seal, nativeSandbox.39nativefills связаны с intents, дублей/overrequest не найдено;45intents включают44terminal/1ACKED, текущие1position/1acceptedreduce-onlyorder. Это не утверждение flat или безопасного restart.
- Полный аудит всех финансовых переходов с первого запуска UNKNOWN: detailed journal доступен только26–28Oct при старте28Sep, ledger хранит IDs/последние состояния вместо всех переходов.8758equity observations и39fills покрывают более длинный период, но не заменяют отсутствующую cash-chain. Funding в старом Sandbox явно не проводится.11BrokenPipe относятся к отключению HTTP-клиента, не доказывают ошибки стратегии;45066ready-status нельзя считать45066ошибками.
- Для нового live обязательны существующий durable journal с typed decision→command→ACK→fill/account/funding payloads, source clocks/IDs/cursors/dedup, причины отказов/частичных исполнений и сохранённая история. Никакого нового OMS/PnL-сервиса и восстановления выдуманных старых данных. HTTP disconnect обработать точечно; прочие ошибки не скрывать.
- Hyperliquid/Nautilus audit:12source-bound rows, official docs/issues. Stable1.231.0 совпадает с установленной;2.0.0rc7 prerelease не является поводом обновляться. OpenAccountState#5449 требует собственной acceptance проверки свежести/stockrefresh. Native retry config не считается защитой, если установленный source его не потребляет. Unknown ACK не переотправлять.
- Live component e171 опубликован после прямого разрешения:47purePASS, peer0P0/P1; cancel identity и server/native held parity исправлены. Это COMPONENT_ONLY, не готовый live release. Phase2 money/H4 contract требует закрыть refresh budget/freshness и journal coverage до кода.

## После выбора и согласования алгоритма

1. Зафиксировать экономический source/config/data/fees/model и полный benchmark/qualification. Представить результат владельцу для согласования версии; не скрывать DD/model/OOS ограничения.
2. Сохранить финальное состояние/историю старого Sandbox и остановить его штатно только после этого согласования. Виртуальные позиции/капитал не импортировать в live. Stop не объявлять nativeflat без подтверждения.
3. Повторно проверить stable Nautilus. Обновлять только при обоснованной совместимой необходимости, отдельно квалифицировать adapter/fees/rounding/serialization; не менять на RC автоматически. Immutable release, rollback и профиль относятся к новой версии; source push не deployment.
4. Выполнить запрошенный владельцем fresh benchmark на фактическом целевом runtime/release с scrubbed research environment и без торговых credentials/venue orders. Это release verification, не подмена старых результатов и не новая оптимизационная попытка; отдельный точный bounded replay-протокол перед запуском.
5. Проверить release diff/мертвый код/необоснованные ветви и connected native acceptance: partial/zero IOC, cancel+latefill, duplicate/lostACK, reconnect, account/funding refresh, warmup/closedbars, restart+MANAGE_ONLY, реальная lot/fee/margin достаточность, pause/stop/reconcile. Все найденные P0/P1 закрыть простыми системными изменениями.
6. Сверить designated account/agent/permissions/private budget/no other writer, реальный баланс и maxstart, точный LIVE_RELEASE. До отдельного START live_order_capability=false. Начальный капитал/адреса/ключи/readbacks только private.

## GUI и авторизация

GUI доказанно выпускается отдельно: отдельные unit/cwd/release; promote script меняет API/connections broker и проверяет неизменность workerPID. Сохраняются API/status schema и fingerprint compatibility. По прямому указанию владельца полный GUI-редизайн выполняется после подготовки/старта live; независимая публикация GUI не требует менять торговый процесс.

После этого: все страницы/настройки под выбранный алгоритм; Dashboard отражает actual account/position/order/PnL/funding без виртуального стартового капитала/исследовательских полей. Executions→Trade History, точные columns/layout/type/color/spacing из Hyperliquid reference и приватного оригинального screenshot2924×1810. Не копировать личные trade-values/email/balance в fixtures или публичные отчёты. Browser/DPR/viewport фиксируются для pixel comparison; точность не заявляется без rendered validation.

График: колёсико над plot меняет горизонтальный масштаб; над price scale — вертикальный; проверить drag/zoom/reset/autoscale и отсутствие сброса viewport на stream updates. Сначала actual installed chart version/typings; только public API, без private DOM/engine hacks. Навыки ui-ux-pro-max и lightweight-charts применяются, точный пользовательский reference имеет приоритет.

Отдельная auth задача: устранить ежедневный ввод пароля и заменить пароль указанным владельцем. Причина установлена:12habsolute+30minidle, session-cookie безMaxAge/Expires; authSQLite и fingerprint устойчивы. Подготовить максимально практичную persistent long session со скользящим idle, server revocation/logout/password-change invalidation; финальный срок зафиксировать по ограничениям стека. Не отключать auth/CSRF/HttpOnly/Secure/SameSite. Новый пароль защищён в Keychain, применение пока PENDING. Ни пароль, ни APIprivatekey не писать в source/reports/logs.

## Сохранность

Сервисы/средства/реальные ордера не изменялись. Ключ API локально проверен штатной функцией Nautilus и сохранён в Keychain; агент привязан к designated account, результат только private. Это не START. Скриншот, account config и financial readbacks остаются gitignored/private. Публичная публикация проверенного CoinMaster source/tests/technicalreports разрешена; секреты/аккаунтные финансовые данные исключены.
