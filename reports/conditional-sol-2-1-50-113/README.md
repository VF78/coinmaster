# Условная SOL-защита 2% / 1% / 50%

Статус: реализация проверена, independent review GO на один isolated native24m run. Численного результата кандидата пока нет.

18 октября 2026 владелец разрешил один отдельный native24m backtest на базе BTC-победителя6 077 107.23887483, сохраняя исходный SOL-overlay. Это новый ограниченный пакет; предыдущие8 прогонов завершены и не повторяются. Пилот, release, настройки и реальные ордера не меняются.

Контроль: source759823d, 24м [2024-09-01,2026-09-01), genuineBybit execution+mark1m, старт10000USDT, reserve0, DPoff, исходные комиссии/funding/margin. TOTAL6 077 107.23887483; ROI60 671.0723887483%; marked-minuteDD66.3187802497%; minimum4530.57414701; fees945927.73761825. Его независимый fresh-repeat проверен26checks/1320fundingrows. [Reuse proof](control-reuse.json).

Кандидат: новый defaultOFF researchflag. BTCsplit.25%/PLANREF/positiveTPIOC остаются; исходные SOL-права, z/sizing и выходы сохраняются. Дополнительная защита arm при adverseBTC>2% от actualblendednativeVWAP, freshSOL15m OR1h previousbarbreak послеarm, исполнение на первом свежем quote с повторной проверкой. OFF при свежем adverse<=1%, без дополнительного обратного1hсигнала. Protective target50% от actualremainingBTC с causalbeta; единственная итоговая SOLцель max(originalremainingauthorized,protective), не сумма. BTCpartial уменьшает защитныйизлишек; BTCflat/mandatory/DPприоритетны.

Совместное использование inventory — явно версионированная адаптация net-target. Actual native fills/cash/VWAP/fees/PnL не переписываются. Отдельный authorization transfer-credit обозначает только перенос реально исполненного inventory в исходный разрешённый бюджет; это не новый fill/PnL. Original clock/sigma задаются при законном original ownership assignment, не задним числом. Exact baseline SOL fill-path equivalence не обещана. Denied admission ничего не переносит; oldrights/timeouts не воскресают. Один existingNETTING/executor/journal, без нового OMS/PnL/risk-сервиса.

Готовность до fullrun: focused native coexistence в обоих порядках, partial/cancel/reject/denied/unknownACK, originalhalf/full/timeout, повторный цикл, обеTF и BTCQ2margin; независимый узкий review; один relevantverificationpass; frozencommit/config/data/policy. Затем один secretless650MiB/swap0 nativeengine с новым fundingjournal, не параллельно другому fullrun.

Финальная таблица должна показать TOTAL/ROI, markedminuteDD, conditionalOHLCотдельно, minimum, liquidations, actualmaker/takerfees+turnover, BTC/SOLfills, parentdates/Q, actualconditionalcycles/coverage/transfer/releases и незавершённыеorders. Signedfunding UNKNOWN остаётсяUNKNOWN; equity-residual не объявляетсяfunding. Условные OHLCграницы не доказывают точную intraminuteтраекторию или DD50.

Текущая задача: [#116](https://github.com/VF78/coinmaster/issues/116), parent[#113](https://github.com/VF78/coinmaster/issues/113). Предыдущий закрытый #117 относится к завершённому8-runпакету.

Ex-ante execution cadence before any candidateROI: protective SOL quantity is latched at activation using current actualBTC/freshmarks/beta, and recalculated only when actualBTCquantity changes. Original desiredbudget changes onlyMAXreconciliation; OFF clearsQc. Price-ratio movement alone cannot rebalance everyminute. Actualcoverage drift ismeasured, not claimed continuous50%cap. Decision18Oct beforefullrun.

Проверки: focused20PASS; одна связная проверка194PASS/6FAIL и затем6PASS только ранее упавших случаев. Это не второй полный200PASS запуск; counts пересекаются. Initial review BLOCK исправлен одним пакетом (CLIoverlay, logicalhalf->full, ownershipsigma) плюс defaultOFF clockguard. Exact8pins/patchd9176243...a7ff2, finalGO и исходные findings/logs сохранены в correction-verification-evidence.json и review-money-orders.{md,json}. Full24m пока не запущен.
