# Предлагаемый новый native-этап: 6 planned + 1 harness-only reserve

**PROPOSED / NOT OWNER APPROVED / GO=false.** Реализация и engine-free фаза завершены и приняты; физические native-запуски этим документом не разрешаются.

## Зафиксированное основание

Product `a50af5433a0bbe00aecd6fec26e8d5c0321ced80`, immutable Mac source, VPS/Mac209purePASS, constructors0, focusedreview0P0/P1 и `V2_ROOT_ENGINE_FREE_ACCEPTANCE.json`. Native matching/partialIOC/reentrantACK/global completion ещё UNKNOWN.

Полная карта: `NATIVE_CASE_MAP_V2_PROPOSED_RU.md` SHA `af3432f63b35435c9b866780fddc2c5ead65fbfe3b84a050a939127ee0120ee1`; JSON SHA `601e4b5c0357e5005556a22010625c4777776025f239837bbf1a08a335ae647c`. Narrow review: `NATIVE_CASE_MAP_V2_DESIGN_REVIEW.json/.md`,0P0/P1, ready для решения владельца. V1 и его HOLD сохранены. Единственная поправка market-data до freeze — secondSOL99 depth0.1→0.2 в общем VT2/VT4P1: stockL1 size-change replenishment; source/quote-object preflight не является matchingPASS.

## Разрешаемый объём после отдельного согласия

Подготовить только новый harness/admission, не меняя product a50/его AST, торговые guards, BTC core, сигналы, caps/u-v, TP-цены/веса или рыночные параметры. Зарегистрированные R2/C0/A0/TRIM, stock Nautilus1.231, реальный native account/cache/fills; BASE Bybit fees0.020%/0.055%, без fixture0.1%. Никаких guardTRUE/private matching calls/manualpositions/cache links/variant or latency swaps. Все inputs/guards/729seedbars/previous-day metadata и processedspan≤48h на case определены картой.

До первого physicalclaim обязательны новый связанный ownerreceipt/protocol/ledger/namespace, committed harness-only revision и проверка byte/AST equality producta50, actual config/kwargs/nativeAPI pins, constructor0 preflight/JSON roundtrip, scrubbed environment и focused admission/harness review. Static input и causal recipe hashes — до constructor; фактический realizedstream и native-source bindings — после run. Будущие значения/хеши нельзя выдумывать.

## Шесть обязательных cases

1. **VT1 freshE1, C0/cancel0:** ordinary partial/multiple SOLTP, originalSTOPlatestACK/fullfill, BTCdebt/standingTPcancelACK и actualflat до cleanup. СтарыйE7 не переносится на новыйsource.
2. **VT2 C0stress/cancel2s:** full/partialCAP/residual; retiring TP/doublelatefill/PartialFilled→Filled и настоящий redundantCancelRejected; liability/cascade/DEFER. Последний отдельный negative phase — partialIOC STOP, whitelist только PARTIAL_NATIVE_STOP, actual recoveryflat и финансовая квалификация=false.
3. **VT3 fixedBTC_TRIM/cancel2s:** causal ownreference/absolutecap/nativeBTCdebt/standingTP/horizon, SOLrouteOFF, no refund/rearm и terminalflat.
4. **VT4 registeredA0/cancel2s:** два actualparents, originalrights/cross/actualstockstaleDENY→freshALLOW на собственномaccount, releasepartial/pendingcancel latefill/debt/fees/accounting и actualflat.
5. **VT5 C0terminalQUOTE/cancel2s:** genuineD1terminal, staleSOLcache blocks, freshSOLquote создаёт единственный pairSOL_CLOSE/partial/residual, положительная защита доflat и настоящий global/domain/terminalcompletion.
6. **VT6 C0terminalCACHE/cancel2s:** genuineD1terminal, lastBTCcancelcallback запускает cachedSOLexit на свежей книге без следующего SOLquote; actualACKdrain/domaincompletion/terminalFLAT. Допустимые BTCinputs и marks заранее перечислены, rescue events запрещены.

Точные input schedules/assertions — в замороженной V2карте. Expected outcomes — требования к наблюдению, не setters и не обещаниеPASS. Pure-only invalidowner/deadline/непроизводимые через publicAPI негативные состояния явно переиспользуются как pure/source proof, а не nativecoverage.

## Единый числовой бюджет

**Новый этап: максимум7 ДОПОЛНИТЕЛЬНЫХ физических попыток — 6planned + не более1reserve.** Все validlaunch/Popen/preimport failures и ВСЕ matching constructors/helpers входят в7. В текущей серии cumulative maximum = ранее4 + новые7 =11; это не число всех исторических прогонов CoinMaster.

Старый ledger4/7 и три оставшихся HOLD не переписываются и не переносятся. Новый ledger начинает0/max7 только после прямого согласия; старый supervisor STOP не отключается. Никаких автоматических запусков/retry; каждый physicalcase — individual rootGO после его readiness и результата предыдущего.

Reserve допустим только после независимого доказательства **harness/preimport/infrastructure-only** ошибки при том же producta50, logicalcase, frozeninputs/recipe/variant/transport, с freshnamespace и repeat_of failedUUID. Разрешена корректировка harness до его утверждённой спецификации, не изменение самой спецификации радиPASS. Product defect/unsafe behavior/неизвестная positiveprotection/живой неизвестный child не исправляются reserve. Все failures/raw/OS receipts сохраняются; неиспользованный reserve закрывается.

Альтернатива без reserve — newmax6/cumulative10, но первый даже setupfailure не даёт права повторить case. Рекомендуется единый cap7, чтобы одна доказанная harness-ошибка не вызывала нового запроса «+1».

## Gates и границы

Missing/unreached обязательного gate, unexpectedfault, непроверенный finalflat/ACK, source/config/data mismatch — STOP, не расширение budget и не переименованиеошибки. Один заранее объявленный VT2negative может дать только engineering expected-negativePASS при остальных обязательных gates; это не финансовый PASS.

Actual positions/orders/inflight/commands/debt0 и pair/globalcompletion нужны ДО engine.end/dispose. Сохранять честные lifecycle transitions/PID/UUID/OS0-or-observedfailure и rawbeforecleanup; STOPPED/DISPOSED не заменяетflat. Не ожидать фиктивного RUNNING от strategy, если настоящий terminal уже остановил её.

**Новые prefix/full/training/download/pilot/production/deployment/externalorders/transfers =0.** Старый условный max4prefix этим этапом не активируется. После полной nativeквалификации отдельно определяется экономический допуск. Публикация researchsource/tests/reports ранее разрешена и не является deployment. Original70%→90%profit/DD50 цели сохраняются, nativefixtures их не доказывают.
