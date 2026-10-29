# Live: актуальный статус и порядок,29.10.2026

Исследовательский кандидат **BTC_POSTCUT_D1** определён: **TOTAL5499360.14984003 USDT из10000**, обеDD51.26863558248311161216905115%, сохранено90.47738788375289% исходной чистой прибылиS0. Это5.499млн, не54.999млн. Sourcefccd60c/configa2c7. Финальный live-release не выбран/не квалифицирован; отдельный START владельца обязателен.

## Drawdown protection: уточнение владельца

Защищённый остаток45% = разрешённая просадка55%. Durable `drawdown_limit_percent` и профильный `deposit_protection_percent` означают loss-limit55. Source привязка и profile/stateparity подготовлены; runtime не изменён. Порог=0.45*существующийзащитныйHWM. HWM повышается по валидному UTCdailyclose, не по каждому intradaypeak. Латч блокирует increases и вызывает native market_exit; только фактические подтверждения доказывают flat. Фактический loss может превысить порог при исполнении. Fresh INIT допускается однократно на настоящем nativeflat с актуальным капиталом; прежние H/latch/history не сбрасываются. Полный ownerrequest — LIVE_DRAWDOWN_PROTECTION_OWNER_REQUEST.json.

Benchmark был без внешнейDP; его нельзя переименовать в проверенныйDP55live. DP55 относится к подготовленному/проверенному релизу, внутренние C1cuts/restore и выбранное экономическое ядро не меняются.

## 1. Текущий пилот — частичный аудит завершён, полный исторический PASS недоказуем

Read-only snapshot: установленный Worker81e6318/native1.231,55/55sourcefiles совпали сseal.39fills/45intents, без дубликатов, fillwithoutintent и overrequest. Один ACKED соответствует рабочемуreduce-only ордеру; snapshotсодержит открытую виртуальнуюпозицию. Это старый nativeSandbox, не выбранныйBTC_POSTCUT_D1.

Подробные логи доступны только26–28октября при старте28сентября. Полная cash-chain/исторические причиныpartial/reject/cancel отсутствуют в latest-statejournal. Funding старогоSandbox по его контракту не проводится. Найдены краткие задержкиwarmup до15мин иHTTPBrokenPipe при отключении клиента; последствия для торговых решений не доказаны. Полный финансовый PASS с первого запуска не заявлен; отсутствующие данные не восстанавливаются выдуманными суммами.

Новые durablepayloads decision→command→ACK→fill/account/actualfunding и sourceclock/dedup готовятся существующим стеком для нового релиза. Все fixes не объявлены завершёнными; текущий pilot не менялся.

## 2. Победитель и переход на него — исследование есть, deployment ещё не проводился

Независимые эталонные сверки108lifecycle/540fill/1248funding точны0E-8, liquidation0/flat. Стресс TOTAL5469423.50671297/DD51.41651839, технический/riskPASS; нижеосновногоprofitfloor на973.008274377 — отдельная заранее заявленная диагностика.

57дней[01.09.2026,28.10.2026) с новымseed10000: rawTOTAL19661.98052982, доходность96.6198052982%, обеDD34.9510965702;7lifecycle/26fills/109funding точны0E-8, orders0/flat/liquidation0. СамprocessFAILED1 из-за неверного учёта неполногооктября при экспорте. Усекающийсяsettledgzip сохранён; completeeventwatermarks независимо доказали DD. Полный qualificationPASS не заявлен.

Report-onlyfix29f66e166ff6b518b1b27a76095d6acd7649e4e4 опубликован:26purePASS и независимое0P0/P1, correctedvalidator проверен на реальном immutableRAW; writers закрываются при исключениях. OriginalFAILED8 не переписан, nativeповтора нет; бюджет8/8 закрыт.

Текущийpilot не остановлен, новаяверсия не задеплоена, freshbenchmark на фактически установленном целевом релизе и connectednativefaultacceptance ещё не выполнены. Повторная официальнаяпроверка29октября: GitHub latestrelease ведёт наv1.231.0, установленнаяверсия совпадает. Нового обновления/установки не делали; RC автоматически не ставится.

## 3. Hyperliquid/Nautilus — аудит источников выполнен, исправления и connectedproof частичны

Официальные docs/taggedsource/installedsource и maintainerissues проверены. Componente171 опубликован:47purePASS/peer0P0/P1, исправлены cancelidentity и native/serverheldsetparity; unknownACK не переотправляется. Это componentproof, неexchangequalification.

Опубликованный checkpoint8ef2ece80a4c6dc7a38cb95852d7ff3439da6e75:88purePASS16.20s и независимый peerPASS. Исправлены дублирующийon_start, триошибкиконструктора, DPmoneyprovider, ClosedTradeClock/native1m/backfill/D1dispatch, общий C1materializer, атомарныеjournal/checkpoint и nativeAccountStatefreshness. Fresh INIT атомарно сохраняет canonicalcheckpoint/marker/исходныйhistoryanchor и отвергает прежниеfills/history/reinit. Из freshorderStatusqueries исключаются только доказанно terminalorders; OPEN/UNCERTAIN сохраняются, новыйfill/revision отзываетcertificate. Это source/component proof; nativeintegration ещё не доказана.

Владелец выбрал сохранить Unified. На базе8ef один VPSwriter завершает явный compatibilitymapping через public API stock1.231: обе account-state ingress используют spotUSDCreportedtotal, нулевой баланс очищается, PnL не прибавляется повторно. Отдельный обязательный gate — согласовать нативные USDquote/USDCsettlement/PnL/fee через публичный instrumentprovider для BTC/SOL с сохранением IDs/ticks/lot/нулевыхstockrates и проверкой всех load/refresh/cache путей. Истинные venueavailableToTrade/maxTradeSzs ограничивают команду; нулевые instrumentmarginrates не доказывают buyingpower. Нет нового OMS/PnLсервиса, ручного измененияcache или перехода наv2.

Бюджеты конечны и предрезервируются доHTTP: classic600, Unified700, общийrolling1000/60с; N<=15, span/oldest<=9с. Unifiedcheapobservation22; foreignDEXdiscovery резервирует660 доdirectory, max32DEX, actual20+20D. Два нерекурсивных fillsquery; saturation2000→UNKNOWN. Fundingcatchup45/500rows→UNKNOWN безcursoradvance. Сведения об аккаунте остаютсяprivate. UnsignedInfo и nativeHTTPAccountState успешно прочитаны безключа/подписей; это ещё не Nodecache/held/venuefill proof.

После FINALsource/pure/одногоpeer — fixtureA/B, максимум3физическиепопытки включаяFAILED, spent0/ROOT_GO=false. До GO Node/Engine не создаются. Отдельный конечный currency-model smoke: один процесс, <=64modelobjects, безEngine/Node/сети, только послеfinalproviderfreeze. Ни один fixture не выдаётся за реальный Hyperliquid matching.

## 4. GUI и авторизация — независимость deployment доказана, реализация отложена

Отдельныеunit/cwd/release и штатныйpromote подтверждают самостоятельныйGUIdeployment с неизменнымworkerPID; требуется API/fingerprintсовместимость. По поручению владельца глубокийредизайн выполняется послеlive. Новое прямое указание29октября: сквозная корректность USDC/API/GUI выполняется сейчас, доSTART, отдельным изолированнымпатчем без пересечения сenginewriter.

ПерерисовкаDashboard/всехстраниц/TradeHistory, удалениеpilot-text, точноецветовое/пиксельноесовпадение Hyperliquid и plot-horizontal/price-scale-vertical zoom **ещё не выполнены и не приняты**. Reference/screenshot приватно сохранены; личныезначения вfixtures не копируются. PixelPASS только после actualbrowser/DPR/viewport comparison.

Долгаясессия/сменапароля тоже pending: причинаlogout установлена12habsolute/30minidle/sessioncookie. Новыйпароль вKeychain, не применён. Auth/CSRF/Secure/HttpOnly/revocation сохраняются.

## Ближайший порядок

1. Завершить Unified/provider source, связныеpure-проверки и одинpeer; заморозить source/config/fixture, затем modelsmoke и nativeA/B. Без новых поисков параметров и повторов исторических результатов.
2. Проверить freshprivate account/cache/agent/foreignexposure/budget/precision/leverage/margin и DP55. Собрать immutable release/runbook/rollback с честно обозначенными недоказанными venueсвойствами и предъявить версию владельцу.
3. После выбора/согласования версии: сохранить старыйSandbox, остановить штатно; проверить доступную версиюNautilus, выполнить deploy и requestedreferencebenchmark на целевомruntime/release по конкретному протоколу. Старый research8/8 закрыт и автоматически не расширяется. Реальныеордера/переводы/START — только после отдельногоявного подтверждения владельца.
4. Послеlive — независимыйGUI/authрелиз по согласованномуreference и acceptance.

Secrets/accountaddresses/balances/readbacks остаютсяprivate. Публикация исходников неdeployment. MVP честно сохраняет legacyreference/zeroTP и SOLalpha; настоящий continuousSOLhedge/real3TP — последующаяоптимизация, не достигнутыйфактэтойверсии.

## Документация и обсуждения API: что включить в допуск

Повторно проверено29.10.2026. GitHubissues/PR используются как первичные отчёты разработчиков и воспроизводимые дефекты; обсуждение само по себе не является доказательством исправности нашего runtime.

| Наблюдение | Требование до START | Состояние |
|---|---|---|
| Unified показывает balances/holds в spot, individualperpDEXstate не отражает общий капитал | Exactmode, USDC-only, native reportedtotal; UPNL отдельно, обе ingress/zero-clear | Source WIP; connectednative gate открыт |
| Nautilus5024: нулевые marginrates и USD/USDC currency mismatch | Actualproduction instrument/PnL/fee proof; venueavailableToTrade/maxTradeSzs; не выдумывать marginrates | Provider WIP; native gate открыт |
| APIwallet только подписывает; Info читает master/subaccount | Раздельные signer/account identity; freshrole/agentlink | UnsignedreadPASS; releasebinding проверить |
| Nonces общие на signer; несколько процессов могут конфликтовать | Один livewriter/APIwallet, native atomicnonce; не запускать второй signerworker | Runtime startup gate; live ещё не подключён |
| REST1200weight/min/IP, UA50k actions/day, batching не отменяет address-basedcount | Общий budget для actualHTTP/retries/items; без рекурсивных заполнений и повторных cancel после полученного результата | Source budget WIP/проверкиpure; native/releaseproof открыт |
| HTTP200 может содержать ordererror; весь batch может быть отвергнут одной ошибкой | Проверять native per-order terminalstatus; timeout/unknownACK не разрешает повтор submit | Componentproof есть; nativeA открыт |
| IOC может исполниться частично; cancelMissing не доказывает отсутствиеfill | Реальныеfillquantity/latefill reconciliation, durable identity; без возврата закрытой позиции | NativeA открыт |
| Минимальный notional$10, asset szDecimals, price5significantfigures+decimalbound | Проверить фактический минимальный бюджет/округление всех частей; невозможный размер отклонять до submit, не увеличивать риск ради minimum | Releaseprivate feasibility открыт |
| scheduleCancel отменяет ордера, позиции остаются | Не считать его гарантией закрытия; штатный nativeexit+ACK/fill/flat proof | Никакого scheduleCancel вызова нет |
| WS reconnect не доказывает непрерывность состояния | FreshnativeAccountState+сверкаfills/orders, новыйWSepoch; oldcertificate недействителен | Sourceproof есть; nativeA/B открыт |

Источники: [режимы аккаунта](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/account-abstraction-modes), [лимиты](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/rate-limits-and-user-limits), [APIwallet/nonce](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/nonces-and-api-wallets), [tick/lot](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/tick-and-lot-size), [ordererrors](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/error-responses), [exchange/IOC/cancel](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint), [Nautilus5024](https://github.com/nautechsystems/nautilus_trader/issues/5024), [Nautilus5187](https://github.com/nautechsystems/nautilus_trader/pull/5187), [Hummingbot8170: Unifiedbalancefallback/reproduction/QA](https://github.com/hummingbot/hummingbot/pull/8170).

Текущий USDCcontract и exactACTIVEcomposition/sourcegates: LIVE_USDC_ACCOUNTING_CONTRACT_20261029.json, ACTIVE_RELEASE_COMPOSITION_PROTOCOL_20261029.json. NativecurrencyMODEL ужеPASS1/1; sharedpendingcollateralP1 исправлен b9f60ed7/113pure+peerPASS. A/Bнерасходованы, HOLDдоокончательногоactivepath.
