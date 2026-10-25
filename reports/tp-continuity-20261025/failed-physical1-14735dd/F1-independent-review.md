# F1 initial focused source review

**REQUEST_ONE_FIXTURE_ONLY_CORRECTION_BATCH; P0=0/P1=2.** Source47e4fe2ca4b1a5c6ff6589246902abc5a8fda825; money763 unchanged, rootGO=false/ledgers0.

F1-01: ложный UNSUPPORTED из oracle/boundaryclassification. route(Filled) пишет rawcache послеnativefill доactorconsumedupdate: закрытыйлегитимныйTP с ещёстарым expected становится ложнымgap. ПослеDEBTfill oldleaves1.000 vs held.750 отмечаются до stockpostfillresize приbid100<101/102/103, гдеTP неmarketable. GenericPendingUpdate return внутрикоррекции тоже не автоматическиmatchingboundary. max_depth≤1 ошибочно приравнивает finite safe nested distinctOIDcorrection кloop. Нужна coherentpredicate по точным sourceconsumed/domainrules и source/quoteproofNONEXECUTABLEtransient; UNKNOWNнеPASS. Exactallocation по-прежнему обязателен на настоящих potentialmatchboundaries, включаяimmediatefill послеUpdated, не толькоfinalstate.

F1-02: не хватает решающихassertions. До max(0,expected−fill)/reallocation надо проверить actualfill≤PREfill frozenallowance; иначе можно скрыть неверное исполнение. ActualTPlevels сейчас возвращаются, но неasserted{0,1,2}; actualauto/OrderUpdated/обеroutecoverage также неasserted. Нужны genuineevents/положительныеfills, реальныйModifyRejected и actualAFTER_ENDall5STOPPED/notrunning доDISPOSED; одного postdisposeflag недостаточно.

Это один batch толькоharness/oracle/trace/assertions, безproductpatch. F1contract уточнён в границах763: consumed=domainentitlementcomplete OR nativeFILLED, не любойis_closed; rawpostfill/pre-derivedlag не означаетgap. Ordinarypartialownleaves не переопределяет sourceconsumption/reallocation.

Остальное согласовано: oneconstructor послеclaim, finite1h/25h, directstockmargin, реальныеorders/fills/partial.050/freshdepth/publicsameOIDmodify/nativecallbacks, noenginepatch/toggle/moneychange. JSON pins script/plan/gate/APIproof/contract. Reviewerengine/tests/Popen/source/ledger edits0. НикакогоrootGO/product/economicдопуска.
