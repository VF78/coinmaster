# Prefix: path-only repair и ровно одна дополнительная попытка

Статус PROPOSED_NOT_APPROVED. Ни одного нового Popen/engine этот документ не разрешает. Engineering7/7 CLOSED остаётся закрытым; полученное +1 engineering не переносится на prefix. Исходный money-протокол5c5e2b41555ee4e5c1970c5c5dadd173cd10599e00158224b706cb0083f477a0 и критерии не меняются.

Первый R2_OFF prefix физически учтён: attempt861c8fbb-24f3-4627-9332-ee2288e32b1d, actualworkerOS1 доengine/report, MISSING_1M_MANIFEST. Причина — orchestration data_root=/inputs вместо stock economic /inputs/data. Все31 frozen input pins уже указывали на правильные файлы. Actualcoverage_blockers(correctroot)=[], wrongroot=missing. Нельзя выдавать этот FAILED за нулевую прибыль/экономический NO_GO.

Parent ledger SHA699020d51179394b2684f161a4216bfd2c6cccce69d89d019d180f849df5cf0e и единственная FAILED1 строка сохраняются. Старый namespace R2_OFF с логами/error/freeze остаётся неизменным, без удаления/повторного использования.

Предложение: увеличить общий prefix cap **3→4 (+1)**, включая уже потраченную FAILED1. Это даст три свежих контроля R2_OFF→R2_C0→R2_A0 как physical2→3→4; прежние оставшиеся2 плюс ровно1 новая попытка. Нового резерва нет; неудачи/pre-engine failures входят. Все controls [2024-09-01,2025-01-15)UTC, seed10000/reserve0, SAMEfrozen source763d985617abd7a7afef5eec13912303983d8837/data/fees/funding/real3TP/risk rules.

Исправление только research orchestration: правильный data_root=/inputs/data в трёх kwargs/freezes и реальные stock nativecoverage/seed/funding/selected minute-stream reader/warmup проверки в engine-free --prepare. Не создавать engine/strategy/account и не вызывать run_native_diagnostic в prepare; не копировать финансовый движок/не ослаблять actualstockguards. Datafiles/manifest/financialsource не изменяются.

До owner consent: frozen proposed common/worker/supervisor, три corrected kwargs и root_go=false phasefreezes, реальный input-reader proof, pure counter/namespace/receipt/tamper checks, независимое review без P0/P1. Не создавать разрешённый max4/amendedledger. После прямого human+1 consent root фиксирует exactnonblankSTRINGreply, source/protocol/parentfailedSHA и total4; derived amended ledger сохраняет FAILED1 и начинает новый phase в JOB/prefix-amend4/{label}, без повторного использования старого каталога.

Нельзя игнорировать новые failures: только единственная точно pinned historical FAILED1 относится к parentphase; любой NEWphase failure останавливает дальнейшие запуски. Нет автоматического restart/retry/phase reset. Приёмка выбирает точный COMPLETED attemptUUID+reportSHA, а не первый/all совпадающий label R2_OFF. Ledger snapshot/entry hashes остаются immutable при последующих append.

Каждый physical Popen отдельно rootGO после source/config/data/env/command pins и фактической предыдущей приёмки. C0 требует hash-pinned financialPASS нового OFF, A0 требует OFF+C0. Financial/accounting gates прежние: actualOS0/cash+signedfunding/settled+coherenteventcoverage/real3TP/ownership/zeroLiq/terminalflat-orders0; UNKNOWN останавливает цепочку. Завершение/export сами по себе не financialPASS. Baseline poorDD может financialqualify.

A0 economic gate прежний: TOTAL>C0, gain>2max(0,incrementalfees), settled+eventDD≤50% и≤C0, dailyES20 всех136UTCдней≤C0, actualadditionalBTCfill для заявления о пользе. C0_NATIVE_FIXTURE=NOT_RUN явно; actualC0financialPASS обязателен доA0. Prefixнеfull/OOS/70/90proof, global originalS0 goals NOT_MET до доказательств.

Full/training/newdownloads/pilot/production/realorders/transfers/services/keys —0. BTCcore/SOLTP-cuts-rearm/leverage/fees/funding/data не менять. ResearchPUBLIC VF78/coinmaster source+managerbranches уже прямо разрешены/опубликованы; deploymentнет. После результата unused budget закрыть, сохранить всеошибки/actualreceipts, обновитьProject/ACTIVE/mirrors/commit-push-exactrefs.

Frozen implementation for consent:

Financial source763d985617abd7a7afef5eec13912303983d8837 unchanged. Actualstockpreflight: all3corrected configurations, coverageblockers[], 9 consumed files match frozenpins,730source seed rows,814 funding/priorM1 records,195840 aligned minutes [Sep1,Jan15), no account/strategy/engine. This is input validation, not economicperformance or730prebenchmarkwarmupdays.14phase +18financial/freeze engine-freechecks PASS. Finalindependentreview P0=0/P1=0 FOR_HUMAN_CONSENT_ONLY; proposedconsumerinterfacePASS.

- `a0-prefix-data-root-amend4-orchestration.diff` SHA 302ba4d03192b1cc99342f0b095b12bdd6b63b600ae1f3d1fdacc2cc12d6996b
- `a0-prefix-amend4-plan-proposed.json` SHA 44436061f5b9790a9cbb1bdadcc9a4efad4fbb6b5d3f2d89772c6a6d51a4ec60
- `a0-prefix-amend4-binding-proposed.json` SHA 7df81b29073a869234390a9b87a65a3a616cf9306b1e83eaebf009c724306d7a
- `a0-prefix-amend4-freeze-R2_OFF-proposed.json` SHA 7ccec861524abc641d104444205d0624c69a5bedab01354a269bc4ca622ec7b7
- `a0-prefix-amend4-freeze-R2_C0-proposed.json` SHA e7ea4384457e4a7c1fa373aee06db3141f74844e7064ffe31b70c83e503069c3
- `a0-prefix-amend4-freeze-R2_A0-proposed.json` SHA bf045a34fffea25ef07ad53c47ac29464b3c67661de9302b2888507c8ef49ba1
- `a0-prefix-data-root-repair-verification.json` SHA 53ca4716c28cb018ede882fa5a9ba627f25abc009d3b0c3bc9e1c3b6218ec360
- `a0-prefix-data-root-all-inputs-preflight.json` SHA 32a48c6aceaa8571610714d6ccb8a551d0cb7cbcd10481ade3d2081e759047ec
- `a0-prefix-amend4-owner-approval-schema.json` SHA 5aa6ffac20dc098c53972e89210d41afb43ae388cf02a48e01277317b54f5859
- `a0-prefix-data-root-repair-review.json` SHA 2a662b136c69de7083ff57ac8f938d8ad023d25ad85d2cef79ebb9e85978fc96
- `acceptance/amend4-proposed-prelaunch-binding.json` SHA ea3522a05828f46c0e482f23d6960a3462599ee05129eabad12df3f3a9ffa98b

AllproposedrootGO=false; parent699020 unchanged/max3/spent1FAILED, amendedfourledger absent. The stalebinding argv were corrected to futureamendedledger/newnamespace and oldversionspreserved. PreconsentOFFinputproof usedread-onlyparentledger; officialfutureCLI requiresamendedledger onlyafterconsent.
