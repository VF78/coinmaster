# Непрерывные BTC TP при SOL-хедже — конкретный следующий протокол

Статус PROPOSED_NOT_APPROVED. Новый monetary source/fixture/prefix пока не разрешён. Исходный A0 engineering7/7 CLOSED; AMEND4 prefix CLOSED3/4, unused A0slot1 CLOSED/не переносится. Global originalS0 ≥70%net intermediate, затем ≥90%, settled+eventDD≤50% остаются NOT_MET.

## Доказанный дефект и область

Sourcebase763d985617abd7a7afef5eec13912303983d8837. NativeOFF финансово квалифицирован: TOTAL20911.13611487/DD50.130142814%. C0 accounting/coverage/ownership/flat/Liq проходят, diagnosticTOTAL16046.38189782/DD47.474401846%, но native3TPFAIL; A0 НЕ ЗАПУЩЕН.

Независимая реконструкция C0: reported57120s разделяются на **540s настоящего отсутствия защиты,9×60s**, и **56580s ложного audit-флага**. В Jan7 TP1/TP2 уже были исполнены, настоящий TP3 покрывал остаток. Нельзя объявить весь длинный интервал реальным отсутствием TP или исправлением отчёта скрыть реальные девять минут.

Реальная причина: `_pair_arm_btc_debt` отменяет все pendingBTC intents, включая защитные BTC_REDUCE TP; `_md_reconcile` при outstandingdebt/held>cap не восстанавливает их; debt submits только на следующей BTC quote. Audit отдельно сохраняет consumedlevels в accepted и сравнивает set с меньшим required, оставляя ложный gap. Ключевые proofs: a0-C0-nativeTP-causal-diagnosis.json и a0-C0-three-TP-blocker-review.json. NativeAPI/design facts: a0-C0-TP-continuity-repair-proposal.json.

Сохранить BTCentry/EMA/direction/sizing/R2LEGACY_Q, TPprices/plannedweights/firstIOC/secondpostOnlyGTC, SOL B2_F0 signals/TP/STOP/rearm и действующее правило monotone BTCcap. A0 — тот же один originalsecondremaining, без возврата закрытого BTC/firstpartialrefund/новогоparent/перенастройки плеча/fees/данных.

## Одна разрешаемая последовательность после будущего owner consent

1. **Stock feasibility first.** До productpatch sourceowner делает один finite native fixture: остающиеся рабочие reduce-only TP при SOL relief/BTCdebt, actualnative auto-resize/OrderUpdated/ModifyRejected/callbackordering. Nautilus1.231 может auto-resize standalone reduce-only child послеfill; нельзя считать простое keep+modify доказанным решением. Никакого отключения use_reduce_only/contingent toggles, enginepatch, fakeparent/OCO ownership, новогоOMS или симулятора. Если безопасная аллокация и непрерывная защита на stockAPI не подтверждены — STOP, productpatch/economicprefix не выполняются.
2. **Узкое исправление после feasibilityPASS.** В isolated canonicalVPSresearchworktree от763 (существующий sourcebranch разрешено продолжить) отделить отмену BTC increases от живых protectiveTP, сохранять реальную защиту во время debt и stock quantity update. Resize через native modify_order только totalQty=actualfilled+desiredleaves, те жеOrderIDs/prices; actualcachedACK/Updated/fills являются authority. Не считать отправленную команду подтверждением. Остаток долга рассчитывать от actualheld к прежнему cap; обычный TPfill может естественно уменьшить этот остаток, без нового debt-credit правила или возврата капитала.
3. Audit считает настоящие remaining/unconsumed levels текущего nativeownership/generation и фактическое live-order coverage; consumedTPs не пересоздаются. Pendingupdate/oldacknowledgedleaves учитываются только как реально ещё работающая защита. Unknown блокирует все increases/A0. Не маскировать gap нулём, не менять старые reports/PnL.
4. Один focusedimplementationpass/independentmoney-orderreview/максимум один consolidatedcorrection. Новый флаг defaultOFF, exactregisteredR2family/старыйR3guard сохранены. Sourcecommitted→Macimmutablecopy; productcode только isolatedVPS. Stock native engine/fee/funding/report pipeline сохраняются.

## Жёсткий новый бюджет — только после прямого согласования

- **До3 физических engineeringfixture engine instances**, каждый≤48h (план≤1h quote-data/config25h), включая failed/setup/repeats и feasibility изп.1. Никакого скрытого baselineengine или резерва сверх3. Послеfeasibility два оставшихся instance должны покрыть paireddebt/required3TP и consumedTP3, TPbeforedebt, partialfillduringmodify, nativeauto-update, reject/UNKNOWN, debtIOCfillrace/BTCflat/latefills/cap/A0oneattempt. Несколько assertions допускаются в одномengine, новыйengine всегда считается. ВсеAPI/realclass/kwargs/seed/freshdepth предзапуски engine-free. Если существенная семантика не доказана в3 — STOP, не объявлятьPASS.
- **До3 физических economicprefix Popen**, включая preenginefails/failed/repeats: свежие matched **R2_OFF→C0_FIXED→A0_FIXED**, каждый[2024-09-01,2025-01-15)UTC, seed10000/reserve0. Использовать один новый frozen repairedsource; C0/A0 отличаются только A0flag, TPcontinuityfix включён одинаково. СвежийOFF устраняет затраты на доказательство cash-path эквивалентности старомуsource; ожидаемая parity с20911.13611487 проверяется, необъяснённое различие блокируетследующийcontrol.
- **Full/training/newmarketdownloads/pilot/production/orders/transfers —0.** Старые unusedслоты не переносятся; новыеотдельные ledgers pinparentclosed7/closed3 receipts и каждыйconstructor/Popen доcall. Никакого automaticfull/retry/пятой попытки или произвольного переставления controls.

## Gating и исполнение

До engine exactsource/config/native1.231/API/fees/UTCwindow/env/data/scriptpins, настоящие nativePrice/Quantity/OrderUpdated events, dailyseed guard start−1day, sharedliquidity свежийdepth; cleanup BEFORE_END/END/BEFORE_DISPOSE с native actualstate. Критические moneyguards без overrideTrue.

Перед каждымprefix отдельный rootGO после engineering/independentreview/actualstockinputpreflight. **data_root=/inputs/data** (существующийfrozen corpus), actualcoverage_blockers/_load_daily_seed/funding_with_prior_minute_marks/iter_minute_bundles, required9consumedfiles↔frozenpins,195840alignedminutes. JSONroundtrip сам по себе недостаточен. Source763 inputfiles/feed5a02a0... остаются unchanged; доказательство читает730source seedrows, не заявляет730prebenchmarkwarmupdays.

Точная версия freeze привязана к durable STARTEDclaim, freshnamespace/journal/actualOSrc/4artifacthashes/reportUUID. C0requiresfinancialPASSnewOFF; A0requiresactualC0financialPASS. Ledger snapshot+exactCOMPLETEDentrySHA append-safe, не wholemutableledger. HistoricalFAILED ни поlabel, ни поnamespace не может квалифицироваться. Один sourceowner/ledgerwriter; reportonlyanalyst/независимыйreviewer безengine.

Нулевая действительная native requiredTP gap при BTCheld, исходные plannedprices/allocations и прежняя frozenstockquantization (любое изменение требует отдельного нового согласования, этимпротоколом не разрешено), нет reverse/extraBTCcut/doublefill/closedBTCrefund; actualnative order/event timeline должен согласоваться с новым audit. Если nativeauto-resize не позволяет это без изменения рыночного контракта — STOP/newprotocol, не ослаблятьусловия ради результата.

Каждый monetary результат требует actualOS0, cash+signedassetfunding, continuoussettled+coherenteventcoverage, actualremaining3TP/ownership, zeroLiq/terminalpositions0/orders0. UNKNOWN останавливаетцепочку. BaselinepoorDDможетfinancialqualify, invariantFAIL —нет. A0economic gates прежние: TOTAL>C0 иgain>2max(0,incrementalfees), settled+eventDD≤50% и≤C0, dailyES20 всех136UTCдней≤C0, actualadditionalBTCfills обязательны иначеNOT_TESTED. ParentES20 ownpopulationdiagnostic. Prefixнеfull/OOS/70/90proof; исходныеabsoluteprofitfloors не снижать.

Публикация researchsource/tests/reports в ранее точно согласованныеPUBLIC VF78/coinmaster branches разрешена; deploymentнет. По завершении actualresults/failedreceipts/unusedbudgetCLOSED/Project/ACTIVE/mirrors/commit-push-exactref. Сам этот proposedтекст не является новым согласием.
