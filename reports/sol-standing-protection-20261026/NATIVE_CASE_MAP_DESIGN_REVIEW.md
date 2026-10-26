# Native case map: bounded design review

**HOLD: 0 P0 / 1 P1.** Проверена карта будущего покрытия и нового допуска; принятый CODE0 a50 не переаудировался. Native matching, бюджет и GO этим отчётом не разрешены.

## Единственная необходимая коррекция

**P1 — VT2, а также использующий его положительную P1-фазу VT4:** SOL99/depth0.1 в 140.25 и повторно в 140.50 не дают два независимых объёма 0.1. При включённом `liquidity_consumption` установленный stock engine сохраняет потребление уровня; сброс происходит только при изменении отображаемого размера. После первого fill доступный объём повторной одинаковой котировки равен нулю. Следовательно, второй обязательный late fill, terminal FILLED старого TP0, benign queued CancelRejected и каскад следующего retiring TP текущим trace не достигаются.

Источник: установленный `nautilus_trader/backtest/engine.pyx:6525–6540`; точный путь и SHA записаны в JSON. Это известное противоречие входов до допуска, а не требование заранее исполнить matching.

Минимальная коррекция — явно задать настоящее обновление L1-объёма второго SOL99 в обеих версиях карты и VT4. Кандидат: depth0.2 во второй котировке при оставшемся TP0 0.1; TP1 по98 при ask99 не исполняется. Его и последующие количественные assertions нужно проверить source-only при фиксации расписания. Нельзя сбрасывать native consumption, менять модель или ослаблять MUST_NATIVE. Известная сейчас коррекция карты должна предшествовать её freeze; будущий reserve не разрешает менять уже замороженный trace.

## Покрытие и достижимость

Шесть отдельных fixed-variant конструкторов содержат нужные native-гейты: свежий E1/STOP ACK+полное срабатывание; CAP full/partial/residual и retiring/DEFER; фиксированный TRIM; зарегистрированный двухродительский A0; настоящий global TERMINAL через QUOTE и отдельно CACHE без следующей SOL-котировки. Последний partialSTOP VT2 остаётся только заранее заданным отрицательным engineering-исходом с обязательным фактическим recovery/flat; financial PASS отсутствует.

Отдельного известного блокера A0 по original rights/caps/closing не найдено. Только исходное неиспользованное SECOND-право, без возврата FIRST/закрытого BTC; после riskOFF SOL закрывается и подтверждённо дренируется до A0. Actual stock margin stale DENY/fresh ALLOW и native размер пока UNKNOWN; `True` override или реконструкция права недопустимы. VT4 наследует указанную P1-ошибку входов VT2.

Global QUOTE/CACHE согласованы с принятыми a50 caller-gates и handoff: единственный pair SOL_CLOSE, положительная защита до actual flat, затем фактические ACK и существующее domain/terminal завершение. В CACHE свежая книга и заранее объявленная поздняя BTC-котировка допускают завершение без новой SOL-котировки. Matching queue/порядок callbacks остаются UNKNOWN до native стадии.

209 pure/40 real-object replay не названы native PASS. Повторное использование доказательств invalid/foreign/duplicate/missing ACK, expiry/deadline и fail-closed rejection обосновано на уровне source/events; реальный benign terminal CancelRejected всё равно обязателен в VT2. Старый E7 — только историческое доказательство; свежий E1 обязателен.

## Бюджет и допуск

Арифметика согласована: 6 плановых случаев + максимум 1 строго harness-only reserve = новый cap7, совокупно со старыми4 —11; альтернатива без reserve —6/10. Старые оставшиеся3 остаются HOLD, prefix/full0. Новое разрешение сейчас0.

Reserve допустим лишь после независимой классификации сбоя инфраструктуры/preimport/serialization, с тем же a50/AST, зафиксированными сценарием/данными/вариантом/транспортом, свежим namespace и repeat failed UUID; actual OS должны быть сверены. Product fault, неизвестный живой child, изменение котировок/параметров/guard или unsafe outcome не дают права на повтор. Каждый failed dispatch/constructor считается.

Нужны отдельные owner approval/protocol/new ledger, связанные неизменяемые source/config/data/API pins, durable claim **до** Popen/matching, фактические OS receipts и индивидуальный root GO. Старый supervisor STOP и четыре строки неизменны; текущие ledger SHA проверены. Отсутствующие harness/admission commit и source-only preflight честно указаны как следующие prerequisites, а не заменены будущим PASS.

Следующий шаг: одна report-only коррекция P1 и согласованные md/json, затем root может представить исправленную полную карту и числовые альтернативы владельцу. Никаких engine/tests/Popen/source/gate/ledger изменений в этом review не было.
