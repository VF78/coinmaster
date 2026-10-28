# Проверка связанного native-движка перед согласованием live

Основание: прямое поручение владельца29.10.2026 довести движок/Hyperliquid до готовности; DP=остаток45%/DD55%; live только после отдельного START. Это необходимая изолированная инженерная проверка, не новый поиск алгоритма и не перенос старых researchслотов.

## Бюджет и допуск

Root выделяет максимум3 физические native-fixture попытки включаяFAILED: обязательные A иB в отдельных процессах, плюс одна условная исправительная попытка. Это ограничение инженерной проверки, не новый числовой ответ владельца. Исторический research8/8 остаётся закрытым. До freeze всех runtime/config/fixture sourcepins, полных relevantpure PASS, независимого review0P0/P1 и отдельного ROOT_GO nativeзапусков0.

Каждый процесс создаёт ровно один nativeTradingNode/ExecutionEngine, synthetic cache/account/order events; record actualPID/UUID/exit до выводов. Claim ledger доPopen. Никакого pytestвсегоnative-suite/скрытых повторов/BacktestEngine/реальных tradingclients. Режимы используют существующий FakeReportClient(QualifiedInfoBoundary, LiveExecutionClient) и реальные native event/cache/account APIs. HLexecutionfactory/key/network отсутствуют; production capabilityFALSE. Никакие реальныеордера/переводы/сервисы/старыйSandbox не меняются.

Одна исправительная попытка допускается только после конкретного анализа и ROOT_GO. При изменении runtimeденежного/ордерного кода старыеcaseproofs автоматически не переносятся: coverage/sourceparity пересматриваются. Ошибки/неиспользованные слоты не удаляются. Если обе обязательные case не доказаны на принятом source — NOT_READY.

## A — старт и связанное исполнение

Настоящий kernel.start_async вызывает единственныйstrategy.on_start: minute subscribe/request действительно выполнены, producer недублируется, formingbar не принимается. Используется sourceactual C1 bridge/LiveEpochRuntime journal.

Через настоящие native generate_order_accepted/filled/canceled провести partialIOC .020→.010+cancelremainder и latefill во времяpendingcancel; фактическиеcache/position/commission/journal отражают события. Повтор same tradeID идемпотентен; конфликтующая копияUNKNOWN. Unknown/lostACK не создаёт новый submit/CLOID; massstatus восстанавливает только доказанные факты.

Strategy.query_account→fake _query_account→отложенныйnativeAccountState: staleaccount, movedrevision, WSepochchange и oldestage>9с блокируютmoney. Новая AccountState +freshidentity/parity восстанавливает только разрешённыеправа. ActualfundingID идемпотентен; наблюдениеfunding не прибавляет ужеучтённый вaccountValue cash повторно.

DP55: H100→threshold45;45.01неlatch,45latch. После recoveryequity latch сохраняется, increases запрещены. Native reduce/close заканчивается настоящими positions_open/orders_open/inflight==0, а не толькоledgerlabel. Сохраняются HWM/latched/risk/clock/rights/checkpoint и атомарныеtypedpayloads.

## B — paused-flat restart

Новыйnode/cache, тотжеизолированныйSQLite/checkpoint. on_save/on_load сохраняют H/DP55/latch/C1rights/fills/clockcursors; freshness/oldcertificate не оживают без новойсверки. Никакого autoresume. prepare_flat_epoch не обнуляетC1H/history при unsupportedC1checkpoint, сохраняет manage-only boundary. Итог native/durable flat доказан, ресурсызакрыты, process0.

## Что fixture не доказывает

Injectedfakevenueevents доказывают nativeintegration, не фактический Hyperliquid matching/cancelrace. Обязательно отдельно проверить свежийread-only bootstrap: publicdata-only node/confirmedbars; unsigned masteraccount mode/perp+spot/orders/boundedreports/agentrole, stockpublicaccountbinding/actualnativeAccountState projection и бюджет. Executionclient/factory/keys не подключаются незаметно. Accountфинансовыеданные остаютсяprivate, наружу толькосанитизированныестатусы. Любое неподтверждённое поведениеUNKNOWN.

## HTTP бюджет — явное инженерное уточнение

Старый400 не вмещает текущую формудаже приN0; blind500 тоже недостаточен. Проверенная верхняяграница nonrecursiveпоколения540+4N включает14singleattemptInfoHTTPrequests,2fillsresponsesmax2000 иstockQueryAccountmax16. Новыйper-generationcap600, rolling1000/60с неизменен; N<=15; полнаярезервация доHTTP, settlement/refundтолькофактическоговеса. Каждыйsweepодинfillsquery,2000строк→UNKNOWNбез subdivision/команды. QueryAccountи все участвующиеответы внутриобщегоspan/oldest<=9с. Лимитыburst/история/unknowns не обходятся.

ОтдельныйuserFundingcatchup: prepaid45 (20+ceil500/20), тотжебюджет/lock;500строк→UNKNOWN/no cursoradvance; фактическийper20cost. Новые endpoints требуют своего доказанного предрезерва. Public/cheapmoneyobservation classiccost2 не получает командных полномочий; Unifiedcheapcost22(allDEXpositions20+spot2). Unifiedполныйbound592+4N/cap700 прифактическипроверенномnativevector; предварительный foreignDEXdiscoveryрезерв660/max32DEX передdirectory, actual20+20D; тотжеrolling1000. Exactsourcecontract — UNIFIED_QUALIFICATION_CONTRACT_20261029.json.

## Отдельная component-проверка валют

После FINALpublicproviderfreeze и review root допускает ровно один engine-free modelsmoke: <=64nativeMODELobjects, безTradingNode/ExecutionEngine/BacktestEngine/сети/ключей. Это не physicalA/B и не скрытый nativeengineповтор. Проверяются rawUSD/USDCnegativecase, actualproductionnormalizedBTC/SOL instruments, USDCget_cost_currency/PositionPnL/fees/min_notional, неизменныеIDs/ticks/lot/zeroRates и venue-reportedbalances. Compile/AST подготовка допускается без nativeconstructor; выполнение только после отдельного ROOT_GO. Результат/фактическое числоobjects фиксируются.
