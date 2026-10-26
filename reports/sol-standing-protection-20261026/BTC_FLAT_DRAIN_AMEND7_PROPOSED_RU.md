# CM137: узкий BTC flat order-drain — предложение, НЕ УТВЕРЖДЕНО

Текущий итог: **2FAILED/6, active0, reserveE6 использован, prefix0/4, full0.** Canonical source97db965 не изменён. Нового code/native GO и увеличения бюджета нет. Предлагаемый pseudodiff сохранён отдельно; он не применён и не исполнялся.

## Причина и уже наблюдённые компоненты

E6/actualscenarioE1, UUIDda9ba9ec-72aa-4961-8f6e-c7bf2b41d985, actual child/supervisor/external OS1. К140s native BTC0/SOL0, однако три прежних BTC TP OID2/3/4 остаются ACCEPTED: .233/.233/.634 BTC, всего1.100. Pairowner не освобождён. Final assertion positions/orders/inflight0/pairNone правильно отклонил попытку; nativecleanup5STOPPED→DISPOSED не устраняет этот отказ.

Source proof: market_redesign._md_reconcile:177 первым маршрутизирует standing-enabled path в _tp_reconcile. standing_tp._tp_reconcile:153–154 при held0 выполняет split_stop/BTC_FLAT и coverage/NATIVE_FLAT, затем возвращается без cancellation ownedTP. _tp_settled:240 также возвращается при held0. Legacy branch, содержащий cancel/ACK barrier, обходится standing route. paired _pair_release_if_terminal правильно требует отсутствие open/inflight orders.

В FAILED процессе фактически наблюдены SOLentry2, ordinaryTP partial/multiple fills, тот же STOP OID10 с quantity ACK и fullIOCfill1.1, actualBTC_DEBT .2/.7/1.1; snapshot-account capture complete. Это отдельные компоненты, не E1PASS/финансовый PASS. E2–E5 не запускались.

## Только предлагаемый behavior

Gating: существующий defaultOFF research_btc_standing_tp, только exact qualified paired R2_A0_V1/B2_F0 continuity path. OFF/core/LEGACY_Q, entry/TP prices+weights, SOLsignals/STOPIOC, caps/u/v, A0originalrights/clocks и financialmath не меняются.

1. При actual native BTC0 проверить собственные незавершённые BTC ENTRY/inflight по существующим immutable owner/parent registries. Если такой entry ещё не terminal — WAIT, сохранить TP/OID/права и parent/increase barrier; этот helper entry не отменяет. Существующее core flat handling остаётся на своём месте.
2. Когда owned increases подтверждены native terminal и BTC всё ещё0, собрать только standing BTC TP текущего owned parent. Проверить strategy/instrument/side/reduceOnly/parent/intent/nativecache history; missing/foreign/ambiguous → UNKNOWN/NO_GO, не угадывать flat и не отменять чужие orders.
3. Для каждого live ownedTP вызвать существующий public cancel_order ровно один раз; closed/PENDING_CANCEL не отправлять повторно. PENDING_UPDATE/oldmodify ACK сериализуются существующим owner/sequence barrier; отсутствие latestACK не трактуется как завершение.
4. Public return — не ACK. Сохранять bindings, generation, заполненные количества и unconsumed rights до реальных terminal callbacks. Не маркировать canceled TP consumed/fill, не возвращать FIRST/SECOND budget, не создавать replacement/TP0.
5. На quote/position/terminal callbacks повторно читать actual native positions, owned orders/inflight/commands/debt. Временно нулевой held не освобождает parent. Latefill до cancelACK применяется один раз штатным fill owner; положительный actualheld возвращается существующему protection/debt owner, terminalPASS отменяется. Если восстановить требуемое состояние в прежний boundary/deadline невозможно — прежний NO_GO; никаких grace/clock waivers.
6. Pair/cycle release только после BTC0/SOL0, actual owned orders+inflight0, pendingcommands0/debt0 и всех actual terminalACK. Generic callback после typed terminal проверяет сохранённую immutable native history и не воскрешает intent/OID. Чужой live order также не позволяет объявить глобальный orders0.
7. Helper не отменяет SOL/original entries, не вызывает cancel-all/ручной close/cache edit, не связывает positions и не меняет matching/latency. Existingcancel2s естественно drain по объявленным E2 dataevents, без ретюнинга clocks/TIF/quotes. ReduceOnly сохраняется; он не заменяет ownership/drain proof.

Риск без drain: старый reduceOnly TP остаётся исполнимым order; при ошибочном release/newBTC inventory он способен уменьшить новую позицию. Поэтому удаление bindings, принудительное pairNone или ослабление orders0 assertion запрещены.

## Предлагаемая bounded acceptance после отдельного согласия

Engine-free: реальные Cache/Order/Accepted/PendingCancel/Canceled events; once-only cancel, typed+generic UUID dedup, foreign/missing owner block, pendingentry→actual latefill без раннего release, lateUpdated/ModifyRejected, сохранение обеих FAILED rows. PublicAPI signatures и JSON/metadata roundtrip. Никаких скрытых BacktestEngine unitconstructors.

Пять nativeattempts, каждый отдельно frozen/reviewed/rootGO, ≤48h processeddata:
- physical3: amended logicalE7 / actualscenarioE1, actual originalSTOPACK/fullfill плюс BTC/SOL0, three ownedBTC TP actualCanceled, orders/inflight/commands/debt0 и pairreleased ДО end.
- physical4 E2: прежний fixedC0 cancel2s; прежние DEFER/partialSTOP negative gates плюс естественный terminaldrain/ACK. Только заранее названный PARTIAL_NATIVE_STOP в negative stage; economics такойfaultNO_GO.
- physical5 E3: прежний fixedTRIM/ownfrozenref/cap/horizon/current3TP, actualterminaldrain.
- physical6 E4: прежний fixedA0stress/originalrights/cross/margin/pendingcancel latefill и quiescence.
- physical7 E5: прежняя fixedA0zero registeredintegration, cash/fees/positions/orders/inflight/commands0, zeroLiq,5STOPPED→DISPOSED.

Все failures/Popen/preengine/matchingconstructors входят. Ни один passing component не заменяет wholecasePASS. Любой новый failure/essentialNOT_REACHED → STOP; запаса после этого расширения нет.

## Числовое и identity amendment — только предложение владельцу

Сейчас осталось4 числовых слота, а требуется5 passingcases: E1retry+E2/E3/E4/E5. Минимальное предложение — **+1 engineering, totalmax7**, включая уже2FAILED; **без reserve/autoretry/переназначения**. Prefixmax4 остаётся условным и ещё не разрешён к запуску; full/training/download/deploy/pilot/realorders/transfers0.

Старые ownerreceipt6b8625…/protocolfaa392… неизменны. Новый max7 допускается только новым прямым owner amendment receipt, связанным с SHA этого protocol, обоими failedUUID/immutable canonical rows и оригинальным approval; не менять старые receipts.

Supervisor amendment: logicalE6 остаётся consumed. Дополнительный logicalE7 допускается один раз только как scenarioE1/repeat_of=da9ba9ec-72aa-4961-8f6e-c7bf2b41d985, expected_before2/physical_index3, исправленный frozen source и narrowreview+freshnamespace+отдельный rootGO. Новый amendmentreceipt/max7 должен проверяться до STARTED/Popen; worker/config/result/ledger/supervisor/externalreceipt сохраняют E7+E1+repeatUUID. E2–E5 затем physical4–7. Ни phantom unchargedslot, ни смена варианта внутри engine. ActualOS nullable/observed, unknownchildactive1 и raw-row preservation остаются как в reviewed supervisor.

До согласия на этот конкретный amendment: **STOP, currentmax6, no code edits/tests/native.**
