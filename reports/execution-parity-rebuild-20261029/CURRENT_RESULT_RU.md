# Итог проверки — 30.10.2026

**Для выпуска выбран A.** На эталоне01.09.2024–01.09.2026, начальные10 000USDC: итог **5 635 720,91989984USDC**, чистая прибыль5 625 720,91989984, ROI+56 257,2092%, coherent и settled DD **51,43837119%**, ликвидаций0. Полные24месяца, OS0,11финансовых проверокPASS, terminalflat/orders0. ReportSHA `c01a9626317680a2461153148128ea8725178594c2e65a47a02c1ba9e5990f6f`.

**Фактически доступный малый капитал также прошёл полный эталон и основной scaling gate:**11финансовыхPASS, OS0,0ликвидаций. Его финансовые readbacks PRIVATE; reportSHA `7097c2153bda7f44ac34054aff2647a3476fe2b07012f2f26d596f377b2df642`. Суммы публично не публикуются.

| Полный10K вариант | Итог | Обе DD | Ликвидации | Вердикт |
|---|---:|---:|---:|---|
|Прежний benchmark|5 499 360,15USDT|51,2686%|0|Архив со скрытым1000SOL cap/старыми исполнениями|
|Корректный контрольR3|561 476,79USDC|85,3909%|1SOL|ФинансовыйPASS, экономическийNO_GO|
|A: явное SOL-стадирование|5 635 720,92USDC|51,4384%|0|Основная историческая цель выполнена внутри заявленной модели|
|B: рыночный held-risk budget|883 181,31USDC raw|74,7643%|0|NO_GO; строгий исходный финансовый gateFAILED|

B обработал24месяца,598nativefills, inventory и3DD-окна сверены. Nativecash transitions сходятся точно; один BTC lifecycle имеет разницу1e-8USDC между позиционным PnL и фактическим cash. Исходные OS1/UNKNOWN_UNALLOCATED_NATIVE_BRIDGE сохранены.31UNKNOWN-отказ, включая первые два доARM, означает, что сохранение задуманного bootstrap не доказано. Это не чистое опровержение всех идей рыночного хеджа. Повторного прогона нет.

## Механизм A и качество доказательства

BTC сохранён по39 исходным полям и полному Candidate; первый фактический BTC0,39536→0,79073 без повторного0,575netting. Все обычные SOL IOC ограничены явным child≤1000SOL×фиксированный initialseed/10 000 ПОСЛЕ полного допуска parent.30Mceilings масштабируются; venue min/lot/tier применяются честно. Actualfillrights/C1credit/restore, timeout60s и nativeposition-progress drain сохранены; настоящие FILLED/ACK, текущие котировки. Emergency/liquidation/globalDP не ограничены. A воспроизводит полезную SOL alpha/стадирование; он не объявлен новым непрерывным BTC-хеджем.

A:548nativefills↔548orders,202SOL исполнения/25циклов;SOL net+716481,01297376. ХудшаяDD:BTC−1013361,77/SOL0. В корректномR3 худшее окноSOL−3868335,21/BTC+586468,13. Все денежные остатки проверенных окон0. Детали: [SOL_RESULTS_AND_DECISION_RU.md](SOL_RESULTS_AND_DECISION_RU.md).

Полные669SOL исполнения ORIGINAL200/R338/A202/B229, циклы и решения B: [native-sol-evidence.json.gz](native-sol-evidence.json.gz), SHA `5553e5c3ead2c5d29ea5e63b817b6a5fb021df898fafd8c2f5b08209e720fb19`. Только симулированные10K, без account-derived малого капитала/адресов/ключей.

## Выпуск и оставшаяся зависимость

Экономика A source5b56f7d0; live source **266f8b664cd07f827f8bce5f0fa9f0c32567aa47**. Десять экономических файлов побайтно неизменны. Закрыты профиль/sourcepins, фиксированный actualINIT seed между рестартами, durableTERMINAL/APPLIED до следующегоchild, и передача DP55 из профиля в typed config.196focusedPASS,88послеprofilepin,3DP; это пересекающиеся выборки, не сумма уникальных тестов. Узкие независимые обзоры0P1.

Полный service-layout релиз установлен НЕАКТИВНО: `266f8b66…-sol-staging-a-live-inactive-native1.231.0-api-v2`; manifest `540f7cb20c726dd43d738e2cb1bb08dda571a0c2bac3fc14c64b9d73f30c2827`; profile `ad8f9950b6a9a837c32eb98c1abcb182f741a1f74475ceea27c3d4860f9583a9`. Проверены фактическиеcwd/import origins, packagedCandidate,92файла/профиль/nativepins. Currentlive6c208 не переключён; START/orders approval отсутствуют.

GUI backend guard **b96bb47a** установлен:15pure+peerPASS, реальныйhealth/capabilities/auth/архивыPASS. Новые legacybaseline/optimizer jobs BLOCKED до привязки квалифицированного общего профиля; старый путь не может незаметно вернуть1000SOL/stalequote/oldfees. Интерфейс не менялся. Перезапущена только GUI-служба, live/Sandbox не затронуты.

Новый предоставленный владельцем API-кошелёк официально авторизован для нужного master; новый fingerprint учтён в неактивном релизе. Ключ сохранён в macOSKeychain; чтение сейчас завершилось таймаутом. Нужен локальный доступ macOS, затем безопасная материализация credentials и финальная read-only сверка. Секрет не напечатан/не переслан. Это не повторное разрешение на работу и не повторный запрос суммы.

LiveDP — **остаток45%/DD55**, капитал — фактически доступныйUSDC. РеальныйSTART только после отдельного явного подтверждения владельца. [Конкретный пакет выпуска](RELEASE_FOR_OWNER_REVIEW_RU.md).

## Пределы результата и учёт

NativeNautilus1.231.0; BTC5/SOL2;USDC от nativePnL/fees/funding доAPI/GUI; эффективные комиссии taker0,0432%/maker0,0144%,referral уже включён. Исторические Bybit1m/currentHLtiers/zero-impact fullfills — явные допущения. У A measuredDD51,4384%; консервативныйOHLCсценарий52,1053% не доказывает intraminute траекторию. Raw Native report сохраняет NOT_FAITHFUL_DIAGNOSTIC/ranking_eligibleFalse: modelgate не переименован в доказательство исторического рынка. Гарантировать будущие livefills по этим данным нельзя. [Границы доказательства](QUALIFICATION_BOUNDARY_RU.md).

Все физические попытки учтены:10/10,active0, неиспользованных0; прежние бюджеты закрыты. ОшибочныйR1 NONCOMPARABLE (root опустилFalse/повторный0,575netting), R2engine0 duplicatepolicy, первый auditrowKeyError и все rawfailures сохранены. Никаких тихих повторов/переписанныхOS0. Номинальное сравнение старогоUSDT и текущегоUSDC не является историческимFX-преобразованием.
