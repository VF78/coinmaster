# E1 actual — независимое решение по failedphysical1

**FAILED / OBSERVER_SERIALIZATION_DEFECT / NO_NATIVE_LIFECYCLE_ACCEPTANCE.** Source3c1bf95cb2ee82cbaf22843e5154861dbf94c5ff; attempt2413619e-c67c-433f-851c-dce075595aee; один actualconstructor. Namespace `/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-standing-protection-20261026/engineering/E1_3c1bf95_ORDINARY_SOL_ZERO`.

Прочитаныresult/actualOSreceipt/engineintent/failurebeforeend/pre-end/after-end/before-dispose/after-dispose, currentledgers и preclaimledgerbytes; installedaccountgetter `.pyx`. Engine/tests/imports/Popen/source/ledger/gateизменения0.

## Причина подтверждена фактическимstack

Наvirtual70 `_pair_start`→`_pair_cancel_btc_increases`→`_pair_observe_lock`→`_pair_predecision` выполняет `native_account=type(account).to_dict(account)` (`paired_prefix.py:827`). Installed `accounting/accounts/margin.pyx:99` сериализует`_leverages` через`k.to_str()`. РеальныйkeyInstrumentId неимеетэтогометода, resultсодержитточныйAttributeError изMarginAccount.to_dict_c/to_dict. Исключениепроизошловread-onlypredecisionrecord, доSOLeligible130/entry/защитногоSTOP.

Это **наша integrationошибкавыборатяжёлогоnativeaccountserializer дляobservations**, source-supportedunsupportedobject-path вinstalled1.231.0. Это неотказtradingguard/денежнойформулы, недоказательствонеподдержкиSTOPmodify и неторговыйубыток/неудачаSOLstrategy. Callbackobserverостановилnativeпрогресс, поэтому«read-only» не означает«безопасендляexecution»; дальнейшееотключениеobserver/игнорированиеошибки безчестногоUNKNOWNнеприемлемо. Saved110purePASS неохватывалинициализированныйnativeMarginAccountсnonemptyInstrumentIdleverages.

## Что actualreached и чтоNOT_REACHED

FAILURE_BEFORE_END и BEFORE_END: actualBTC2.000long;3nativeTPACCEPTEDleaves.425/.425/1.150=sum2.000; initialFIRSTqty275actualfill2иCANCELEDremainder273; originalSECONDnativeGTCqty275ACCEPTED/filled0. SOLпозиции/ордера0. Snapshotcash9999.89000000USDT — cashнаобрыве, **неterminalTOTAL/ROI/финансовыйPASS**. Pairselectionужеинициализирован, nocancelbarrierPASS невыводится:observerупалдоотменыoriginalsecond.

SOLentry/partial/multipleTP/STOPsameOIDquantityACK/fullSTOPfill/consumedrights/latecancel/BTCdebt/healthyDEFER/A0/TRIM/integratedflat **NOT_REACHED**. Baselineentry/3TP — полезныесвидетельства FAILEDprocess, неE1PASS.

AFTER_END подтверждаетвсе5componentsSTOPPED; BEFORE_DISPOSEпоказываетвсёещёBTC2.000, standing3TPиACCEPTEDSECOND275. AFTER_DISPOSEподтверждаетвсе5DISPOSED. Этоcleanlifecyclecleanup, **неfinancialflat**;cacheпослеdisposeнеиспользуетсядлявыдуманногоflat.

Child26342actualOS1 изPROCESS_EXIT; supervisor26341actualOS1/externaldispatcher26339actualOS1 из E1_EXTERNAL_OS_RECEIPT_3C1.json. Никакогоdefault/predictedexitcodeвместофактическогоOSнаблюдения.

## Минимальный допустимый путь snapshotfix, безденежногоизменения

Не патчитьNautilus иInstrumentId, не monkeypatchserializer. Installedpublicreadgetters позволяют компактныйnativeaccountview безto_dict:

- `accounting/accounts/base.pyx:140–198`:balances()/balances_total()/balances_free()/balances_locked()/commissions() возвращаютcopy/value mappings; stringkeys через `str(currency)`/`str(instrument_id)`, Money как amount/currency, не JSONnativeobjects.
- `base.pyx:226–296`:balance_total(currency),balance_free(currency) — readqueries; использоватьявнуюquotecurrency иUNKNOWNприNone/ошибкенаблюдения, не0.
- `margin.pyx:145–175,222–285`:margins_init()/margins_maint() илиmargin_init(instrument_id)/margin_maint(instrument_id); leverage(instrument_id) какpublicread, еслинуженrecord. Это без `_leverages` traversal/to_str ибезfullAccountStateeventhistory.

Feasibility **SOURCE_ONLY**, fixнеосмотрен/непротестированэтимreview. Предпочестьboundedallowedfields, добавитьengine-freeobjecttest среальнымMarginAccount/nonemptyInstrumentIdleverage иMoney, прифактgetterfailureявныйUNKNOWNreason. Не catchException→fakezero/silentdrop, невызыватьincreaseguardизobserver, не менятьcap/rights/clock. Новыйисточник/freeze/reviewпередrepeatобязателен.

## Бюджет и предшествующиеряды

Canonicalengineeringledger:1started/1FAILED/active0/remaining5/max6/rootfalse; prefix0/4/rootfalse. EngineIntentconstructor_count1; повторныеOSreceipts/after-endнеявляютсядополнительнымиattempts. Preexternalledger иnamespaceLEDGER_BEFORE_CLAIM побайтносовпадают:SHA29217b9acbe0fd41495edfd77c08d1ad3c43f049856946a746bd7f02412e1511. Доэтойпервойпопыткиattemptrowsпусты; failedphysical1сUUID/source/resultSHAсохраняется, непереклассифицируетсяпослеfix.

**РезервE6 — логическийодинconditionalrepeat, необязанфизическибытьшестым.** Rootможетвпределахисходныхmax6назначитьегоphysical2 какrepeat_ofданногоFAILED E1доE2: freshnamespace/newsource/review/rootGO, fixtureE6/scenarioE1 либоинойявныйcanonicalreservecount. ПослеэтогоостаютсячетыреобычныхE2–E5; никаких+1/переносастарыхслотов. Текущийsupervisorverify guard `E6⇒physical_started==5` доэтогонеподходит; егонадозаменитьдоrepeatузкимfreezeправилом«ровноодинreservedrepeatужеимеющегосяFAILEDattempt, rootreviewedcorrection, total<6», сохранитьfailedparentrow иоднократностьreserve. Этоjudgegatingрекомендация, неedit/launchauthority.

Решение: E2/economics покаHOLD; разрешениенабудущийrepeatопределяетrootпослеотдельногоtargetedfixreview. ДанныйreviewневыдаётGO. Любойдальнейшийessentialfailureнеполучаетавтоматическогорезерва; cap6/4/full0неизменны.
