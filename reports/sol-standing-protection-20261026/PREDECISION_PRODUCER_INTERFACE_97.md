# Predecisionproducer97: узкая interface readiness

**BOUNDED_FIXTURE_INTERFACE_MAPPED / PREFIX_PROOF_HOLD.** Проверены только8actualpredecisionrecords вFAILED E6/E1 UUIDda9ba9ec… и соответствующий frozen97producer. Новыхtests/engine/streams/денежныхвычислений/patch нет. FAILрезультатNone/OS1 не становится финансовымreceipt.

Actualcapture: `FAILURE_BEFORE_END.json → $.paired.predecision_records`; futureeconomicreport ожидается `$.paired_prefix_audit.predecision_records`, но егоactualpath/source надоfreeze до приёмкиprefix.

Наблюдались1parent/1ACTIVATION_SELECTED, checks10/records8/coalesced2; все8A0flagFalse, accountcapturecompleteTrue/errors[]. Это подтверждает независимость наблюдателя отA0flag на данномпути. RiskOFF0 и firstOFF+60records0: эти ветви и prefixopportunities не проверены. Timestamps70,70,130,131,136,137,138,139s;7quotephase `AFTER_PAIR_RISK_AND_MD_RECONCILE_BEFORE_A0_CHECK`,1causephase `CAUSE_RISK_CANCEL`.

## Точные поля и aliases

|Факт|Rawrecordполя|
|---|---|
|Originalsecond/actualfilled/remaining|`original_second`, `second_filled_ever`, `remaining`; initialFIRST/oldsecondOID/TIF/price отдельно|
|RiskOFF+60/quote/cross|`off_ns`, `off_plus60_ready`, `timestamp_ns`, `quote_ns`, `bid`, `ask`, `post_only_cross`, `risk`|
|Debt/cap/TP/pending|`debt_since`, `held`, `cap`; `current_btc_tp`, `ordinary_tp_touched`, `entry_terminal`; `old_orders`, `open_inflight`|
|Nativeaccount/gettercapture|`native_account.status/complete/errors`, `native_account_capture.complete/errors`; `balances_total/free/locked`, `instruments.*.margin_init/margin_maint/leverage`|
|Marginobservationalstatus|`stock_guard_invoked`, `stock_margin_invoked`, `stock_margin_result`, `admission`, `read_only_current_fact_margin_for_attempts`, `marks`|
|Coverage|`predecision_coverage.parent_count/parents/counts/account_capture_complete/incomplete_capture_blocks_financial_coverage/truncated`|

Literal`capture_status`/`financial_coverage_eligible` отсутствуют. Новыеproductполя радиназваний не нужны: freezeexplicitaliasизexistingstatus/complete/errors. CaptureKNOWN+completeTrue+emptyerrors — только gettercapture, не wholefinancialcoverage. Последняя требует actualcause/parentuniverses/timestamps/facts/reasons/coalescing/no-truncation. НикакогоdefaultPASS из одногофлага.

`stock_margin_invoked=False`, `stock_margin_result=UNKNOWN_NOT_EXECUTED_OBSERVER`, `admission=UNKNOWN_OBSERVATION_ONLY` во всех8 — честная observationalUNKNOWN. NativegetterNone представлен `ABSENT_NATIVE_VALUE`, а exception отдельно даётerrors/UNKNOWN/incomplete. None не prospectiveMarginPASS и неzero. OwnA0guard вызывается на своёмaccount приdispatch; C0 не обязан заранее доказатьfuturemargin/fill/profit.

## Совместимость reader и что ещё HOLD

Текущий `validate_predecision_coverage` сравниваетstage/path/fieldmap сrootgate metadata, безhardcodedlowercase. Поэтому exactuppercasephase принимается послеfreeze вgate/proof; placeholdertemplate не надо считатьproductcontract. Измененияreader сейчас не нужны. Causephase отделить отquotestage, не выдатьcause-onlysnapshot за actual+60quote.

Coveragechecks/record/coalesced не равны полному universe. Нужен rootproof join изactualACTIVATION_SELECTED, parentregistry, riskOFF иfirst_OFF60правил того жеimmutableprefixreport; expected/observedIDs иmissingreasons отдельно. Логическиеstatechanges coalesced допустимы; source должен объяснятьпропуски, а requiredcause/firsteligiblecheckpoint нельзя потерять. Полныйprefixproof покаHOLD.

NativeQuoteTick не предоставляетeventUUID; `native_input_identity=id(tick)` processlocal. Для exactevidenceref bindreport/captureSHA+JSONrowindex+parent+timestamp+phase+quoteidentity, не придумыватьnativeUUID. `debt_since` — clock/armedfact; bindheld/cap вместе, не называтьего quantity. Pending/reservation факты требуют bothopenorders иactualnativebalances, не отдельныйbool.

Следующийproof: finalsource/reportSHA/UUID/label/phase+actualproducerpath; explicitfactmap/aliases; wholeactualriskselection/OFF/candidateparentuniverses/timestamps+coalescing; allcapturereasons/no-truncation; root-pinnedproof вgate/evidence.proof_artifacts. UNKNOWN/incomplete→reject. Completeknown0structuralrights можетзакрытьunusedA0, riskselections0→NOT_TESTED; этотfixture не устанавливает такиеprefixcounts.

Всеexactpaths,counts/schema gaps/sourcehashes: PREDECISION_PRODUCER_INTERFACE_97.json. Предыдущие13puretests/moneycoreproof переиспользованы безповтора. Никакихprefix/PnL/opportunity/economicPASS или GO здесь нет.
