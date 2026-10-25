F3 physical3 FAILED, actualOS1, PID96543. Engineering3/4, active0; prefix0/3. Productpatch/F4/retry не выполнены. Две предыдущиеFAILED-строки сохранены побайтно.

Настоящие nativefills: BTCentry1, SOLshortentry10, TP0partial.050@101. BTCheld.950/SOLshort10; nativecash9999.44399000. Проверки actualmatchingbook/tickidentity прошли до10s; восемь quiescence checkpoints. Никаких modify/debt/autoUpdated ещё нет. Это достигнутые компоненты FAILEDprocess, неF3PASS.

Ошибкаline274: PARTIAL_TP_MUST_NATURALLY_LINK_POSITION. Snapshot однозначен: TP0.nativeOrder.position_id=реальнаяBTCпозиция; cache.position_id(TP0)=None; cache.orders_for_position(BTCposition) содержит только openingentryOID1. Rawpositionfield иcacheassociation — разные свойства.

InstalledExecutionEngine вNETTING присваивает positionID кfill, но обычный non-exec-algo путь возвращается без add_position_id (1478–1500). Order.apply_fill присваивает raworder.position_id (base.pyx1177). Cache при созданиипозиции индексирует opening_order_id (2375–2387); orders_for_position читает отдельный index (4850–4872). Stockauto-resize обходит именноэтотindex (engine.pyx7994+). Поэтому предпосылка «partialсамсоздаётcachelink дляauto» в этом фактическоммаршруте неверна. Cache не очищался/не переписывался.

До SOLrelief/cap.752, marketableDEBTblock.188, actualDEBT, queuedACK, standing159/434 иреальногоModifyRejected выполнение не дошло: NOT_REACHED. Не делаем вывода о неподдержкеNautilus вцелом и не снимаемassert/mandatoryauto безотдельного решения. Все5components реальноSTOPPED послеEND иDISPOSED; nativeпозиции передdispose оставалисьоткрыты какfailureevidence, terminalflat не заявляется. Rawsource/log/snapshots/IDs сохранены в JSONpins. Однаоставшаясяпопытка не являетсяавтоматическимretry илидопускомкproductpatch.
