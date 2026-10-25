# Prefix orchestration review — 25.10.2026

**REQUEST_ONE_LINKAGE_CORRECTION_BATCH_BEFORE_PREFIX; P0=0/P1=2.** Engine-free static review; acceptance reader не дублировался.

1. A0-PFX-01: worker проверяет STARTED attempt identity, но не SHA прочитанного freeze против durable claim.freeze_sha256. Изменившийся freeze может пройти свои pins, тогда outputs будут приписаны ledger/manifest другому freeze. Перед nativecall сравнить digest с claim; тот же digest провести через proposal/supervisormanifest. Mismatch должен завершить уже counted attempt.

2. A0-PFX-02: priorCOMPLETED означает OS0/export, а не financialPASS. PreviousIDs/strictorder и generic launch_gatesPASS не связывают actual принятую C0 финансовую проверку с допуском A0. Нужны pinned prior root-financial acceptance receipts, связывающие attemptID/reportSHA/manifestSHA и итогPASS; UNKNOWN/failure запрещаетclaim. OFF priorнет; acceptance consumer остаётся единственным вычислителем финансовыхgates.

Остальное согласовано: atomic claim до namespace/setup/Popen, failure расходуетslot/блокируетauto-next; max3 OFF→C0→A0, однаPopen/no retries. Scrubbed env, fresh namespace/result/funding/coherentjournal. Exact source763 real build_a0_kwargs/validate_native_a0 сохраняют R2LEGACY_Q/OFFNone/C0A0B2_F0/onlyA0flag. Денежные/native/fees/funding/reportguards не меняются. Prepare только hashes/kwargs без enginecall. OSrc0 обязателен; supervisor перепроверяет4hash и связывает report/manifest с ledger.

ScriptSHAs и текущий OFFfreezeSHA сохранены вJSON. RootGO=false, actualprefix не запускался reviewer. Нужен один linkage-only correctionbatch с refreeze/closure; review не даёт rootGO/extra budget/full/trade/deployment.
