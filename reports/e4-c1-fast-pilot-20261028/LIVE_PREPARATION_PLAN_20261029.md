# Live: актуальный статус и порядок,29.10.2026

Исследовательский кандидат **BTC_POSTCUT_D1** определён: **TOTAL5499360.14984003 USDT из10000**, обеDD51.26863558248311161216905115%, сохранено90.47738788375289% исходной чистой прибылиS0. Это5.499млн, не54.999млн. Sourcefccd60c/configa2c7. Финальный live-release не выбран/не квалифицирован; отдельный START владельца обязателен.

## Drawdown protection: уточнение владельца

Защищённый остаток45% = разрешённая просадка55%. Существующий durable `drawdown_limit_percent` должен быть55; профильный `deposit_protection_percent` тоже означает loss-limit, а не remainingfraction. Новый input-readiness профиль сейчас не содержит DP-поля: source-owner готовит явную привязку55 и profile/stateparity. Порог=0.45*существующийзащитныйHWM; новый HWM/reset не изобретается. В текущем механизме HWM повышается по валидному UTCdailyclose, не по каждому intradaypeak. Латч блокирует increases и вызывает native market_exit; только фактические подтверждения доказывают flat. Фактический loss может превысить порог при исполнении. Runtime не изменён. Полный ownerrequest — LIVE_DRAWDOWN_PROTECTION_OWNER_REQUEST.json.

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

Свежая sourceпроверка: e171HEAD,11файловWIP603added/14removed сохранены, без reset/повторареализации. Уже есть ClosedTradeClock/native1m subscribe-request/D1dispatch и terminalevidence-querycache. Не завершены currentmoney/C1materializer, связная journalatomicity/budget/freshness квалификация и реальные failurecases. StockQueryAccount использует2endpoint/cost4normal и16worstretries; Bybitconfirmedbarfilter доказан поsource1.231. Эти факты не заменяются поведением latest/developdocs.

SingleVPSowner завершает минимальный existingstackbridge: всеистории/H/rights сохраняются; исключаются из freshorderStatusqueries только доказанно terminalorders с native+fillfingerprints; OPEN/UNCERTAIN остаются, новыеfill/revision отзываютcertificate. Никакого нового OMS/PnLсервиса, молчаливого увеличенияbudget илиповторногоall-historysweepкаждуюкотировку. Нужны connectedпроверкиpartial/latefill/duplicate/lostACK/reconnect/accountfunding/margin/precision/restart/stop. Venue/node/nativecalls сейчас0.

## 4. GUI и авторизация — независимость deployment доказана, реализация отложена

Отдельныеunit/cwd/release и штатныйpromote подтверждают самостоятельныйGUIdeployment с неизменнымworkerPID; требуется API/fingerprintсовместимость. По поручению владельца глубокийредизайн выполняется послеlive.

ПерерисовкаDashboard/всехстраниц/TradeHistory, удалениеpilot-text, точноецветовое/пиксельноесовпадение Hyperliquid и plot-horizontal/price-scale-vertical zoom **ещё не выполнены и не приняты**. Reference/screenshot приватно сохранены; личныезначения вfixtures не копируются. PixelPASS только после actualbrowser/DPR/viewport comparison.

Долгаясессия/сменапароля тоже pending: причинаlogout установлена12habsolute/30minidle/sessioncookie. Новыйпароль вKeychain, не применён. Auth/CSRF/Secure/HttpOnly/revocation сохраняются.

## Ближайший порядок

1. Завершить existinglivebridge и DP55profile/stateparity, focusedenginefreeпроверки, одинpeer. Представить точныйrelease/casemap и оставшиесяgates; без новых поисковпараметров.
2. После выбора/согласования версии владельцем: сохранитьстарыйSandbox, остановитьштатно; ещёразпроверитьNautilus, сформироватьimmutabledeployment/rollback, выполнитьзапрошенную проверкуэталона на целевомruntime/release по конкретномупротоколу, connectednativefaults и аудитdiff/мертвогокода/расчетов.
3. Freshprivateaccount/agent/budget/precision/margin reconciliation и фактическийDP55readback. Реальныеордера/переводы/START только после отдельногоявного подтверждения владельца.
4. Послеlive — независимыйGUI/authрелиз по согласованномуreference и acceptance.

Secrets/accountaddresses/balances/readbacks остаютсяprivate. Публикация исходников неdeployment. MVP честно сохраняет legacyreference/zeroTP и SOLalpha; настоящий continuousSOLhedge/real3TP — последующаяоптимизация, не достигнутыйфактэтойверсии.
