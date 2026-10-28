# CoinMaster: текущий статус для внешнего аудита ChatGPT

**Срез: 28.10.2026, 16:13 UTC / 19:13 Europe/Moscow. Это доказательства и статус, а не разрешение менять код или запускать торги.**

## Итог без завышения прогресса

Готового алгоритма с DD30–50% и сохранением≥90% прибыли победителя НЕТ. Исправлены BTC TP и создан ограниченный прототип SOL recovery. Новый SOL ещё не дал квалифицированного исторического результата по прибыли/DD. Работа находится на стадии проверки механизма исполнения и риска, а не финальной настройки ROI. Процент готовности честно неизвестен; достижимость совместной цели не доказана.

Слишком много времени ушло на тестовую инфраструктуру, контекст, согласования и сложный контроллер до экономической проверки. Из9 native-попыток четыре FAILED: три harness/DATA ошибки и один реальный strategy recovery NO_GO. Первоначальный P0 также потребовал observer-repeat. Сумма wall первых8 зарегистрированных попыток —424.96с; это не учёт общего времени работы и не стоимость токенов. Основная задержка была вне вычислений native-движка.

## Цель и правила сравнения

Исходный legacy S0: период[2024-09-01,2026-09-01), seed10000USDT, RESERVE0, TOTAL6077107.23887483; settled DD66.2569148647%. Финальная цель — оба DD (settled и coherent event)≤50%, желательно30–50%, при net-profit retention≥90%. Это TOTALfloor5470396.514987347. Экспериментальный промежуточный70%floor4256975.067212381. Ни один новый full-кандидат эти цели не подтвердил.

Native Nautilus1.231.0 — единственный экономический движок. Bybit BASE fees maker0.020%/taker0.055%; Native cash/fills/fee/funding авторитетны. Исторические1m цены реальны; synthetic L1 close/depth и venue tiers — модель исполнения, не исторический L2 или гарантия live/intraminute DD. Повторно использованная история не считается новым OOS.

## Что действительно сделано

| Этап | Результат | Предел вывода |
|---|---|---|
| M1/P1: реальные BTC TP1/2/3 | Native fills16/13/12; все12 financial gates PASS. Prefix01.09.2024–15.01.2025: net151193.03051897 против150527.62564425, +0.442048% | Matched E4 prefix, не full-победитель. DD вырос57.5854104596→62.4160211977% |
| P0/P0R | Исходный P0 OS0, но observer пропустил6 фактов →financial UNKNOWN; P0R точный replay, квалифицирован | Исходный P0 не переписан |
| M2: настоящий SOL risk-owner | Partial IOC210.9 исполнил10, остаток отменён;3TP+STOP реально приняты; SOL TP закрыли10, BTC550 сохранился и затем закрылся своими TP. Independent63/63 PASS | Synthetic component proof, не economic ROI/DD |
| M3 первый | FAILED69s: повторный одинаковый quote не пополнял consumed depth | DATA/harness ошибка, дальнейшие gates не достигнуты |
| M3R исправленный | CAP78 действительно исполнился10+68, позицииBTC200/SOL132.9 достигнуты. Затем FAILED70s: NO_PROVEN_POSTFILL_RECOVERY послеBTC TP199 | Реальный strategy NO_GO; отмена4 ордеров запрошена, PENDING_CANCEL. Фактический нулевой интервал защиты доACK не доказан. DISPOSED не означает flat/PASS |
| CODE0 | Default-OFF прототип нового BREACH recovery, финальные20/20 engine-free checks PASS; peer0P0/P1 | НЕТ native/financial/economic квалификации нового кода |

Старый SOL существенно создавал капитал и тем самым менял будущие BTC quantities. В старом E4 около56.92% SOL-held времени приходилось на BTCflat: это alpha-overlay, а не непрерывная страховка. Поэтому нельзя переносить его standalone PnL в новый hedge и считать прибыль системы сохранённой. Ранее отключение SOL давало крайне низкую итоговую прибыль, несмотря на отдельные прибыльные BTC fills. Подробности в[RESEARCH_INDEX](../../.ops/RESEARCH_INDEX.md); там отдельно обозначены разные execution-модели, их результаты не смешиваются.

## Почему возник последний тупик и что меняет CODE0

BTC199 исполнился по TP105.2 при mark107: equity уменьшилась на362.38696, включая native fee4.18696. После исполнения cushion360.2863425 меньше stress loss392.16122324487; margin при этом проходит. Старое recovery сравнивает candidate paths, включающие исполнение остающегося BTC TP, с текущей исходной позицией. Отсюда все SOL sizes отвергаются; это следствие контракта, а не доказанный баг исходника.

Для captured70s отдельно доказан новый benchmark: сравнивать каждый partial с тем же worst-case уже работающих BTC TP по фактической цене/fee; полный endpoint обязан быть safe. Функция —max пяти affine forms; четыре угла покрывают весь прямоугольник в заявленных знаках/tiers/funding. Baseline35.2044175723; весь full-SOL edge safe, margin проходит. Zero-fill остаётся уже unsafe; лемма не обещает завершение ордера или защиту от любого будущего движения цены.

Реализация CODE0 использует существующий evaluator/partitioner и sole owner. Только новый recovery —native reduce-only LIMIT IOC, поскольку MARKET IOC не задаёт price bound. Пример BUYcap133.03 обеспечивает cost.2031665/unit≤phi.205995. Обычные заявки, TP GTC/STOP_MARKET, строгий normal admission, DD50/cushion и financial reader сохранены. Partial IOC ждёт собственный terminal+owned resize ACK с исходным deadline, затем fresh proof остатка; pending-fill credit нет. Negative signed old cost, неаффинная Money fee, unknown/pending/triggered old paths дают UNKNOWN/DENY. Флаг `research_method_a_recovery_code0=False` по умолчанию.

## Ограничение и что происходит сейчас

Последний опубликованный implementation commit: **b1807f15043522b57d3e76527586f152c2db572c**, parent a4ed258. Владелец прямо разрешил обобщение количеств: [receipt](OWNER_CODE0_QUANTITY_GENERALIZATION_APPROVAL_20261028.json). Обобщение завершено и принято только на уровне исходников/engine-free: [отчёт](code0-quantity-generalization-20261028/DELTA_REPORT.json), [параметрическое доказательство](code0-quantity-generalization-20261028/PARAMETRIC_PROOF.md), [независимое ревью](code0-quantity-generalization-20261028/INDEPENDENT_QUANTITY_PEER_REVIEW.json), [source acceptance](code0-quantity-generalization-20261028/SOURCE_ACCEPTANCE.json).

Удалены только абсолютные validation ceilings BTC1/SOL132.9. Теперь диапазоны берутся из actual native Cache inventory и known working TP leaves<=actualBTC. Четыре уникальные целевые проверки PASS, включая synthetic snapshot на настоящих объектах Cache/Position/MarginAccount BTC2/SOL−200, equity5500/peak10000; captured70 regression; tier/pending/leaves negatives. Peer0P0/P1. Остальные runtime bytes неизменны. Прежние20 bounded checks и новые4 — разные checkpoints, не заявляются как единый24-test suite. Ранее отклонённое расширение выполнено только после прямого разрешения; история отказа сохранена.

Остальные ограничения (знаки, первая tier, fees/funding, owner/ACK, известные dormant SOL TP/STOP) не сняты; unsupported UNKNOWN/DENY. Реальные native fills/lifecycle, финансовая и экономическая квалификация **нового** кода пока отсутствуют. Применимость при росте капитала до миллионов не доказана.

## Бюджет и границы

[Canonical ledger](unified-run-ledger.json):9/18=5COMPLETED+4FAILED, active0, root_goFalse. Engineering6/11, prefix3/6, full0/1. Оба резерва и исправленный M3 slot израсходованы. FullP2 закрыт явным owner amendment; оставлен один условный fullP3. Все FAILED и старые raw неизменны. Новые CODE0 stages имеют native/prefix/full0; слоты не переносятся.

Нельзя начинать экономику до обязательных engineering/financial gates. Будущий native case map —PROPOSED, в частности старые cash6011/SECOND ожидания нельзя переносить после успешного раннего recovery. Нужен отдельный конкретный run-протокол/числовое разрешение; code-only PASS его не заменяет. Пилот/production/services/deployment/real orders/transfers/training не затрагивались.

## Минимальный набор первичных материалов для аудита

1. [Текущий результат](CURRENT_RESULT_RU.md),[аудит и план](AUDIT_AND_ACCELERATED_PLAN_20261028_RU.md),[ledger](unified-run-ledger.json).
2. [CODE0 implementation report](code0-recovery-20261028/IMPLEMENTATION_REPORT.json),[final20 receipt](code0-recovery-20261028/FINAL_SOURCE_ACCEPTANCE_RECEIPT.json),[independent review](code0-recovery-20261028/INDEPENDENT_FINAL_REVIEW.json),[root acceptance](code0-recovery-20261028/ROOT_CODE0_ACCEPTANCE.json).
3. [M3R actual failure](ACTUAL_M3R_FAILURE_REVIEW.json),[точный диагноз](m3r-risk-recovery-diagnostic-20261028/REPORT_RU.md),[четыре угла и пределы леммы](m3r-risk-recovery-diagnostic-20261028/HYPOTHESIS_PROOF_RU.md),[точные коэффициенты](m3r-risk-recovery-diagnostic-20261028/HYPOTHESIS_PROOF.json).
4. Source immutable:b1807f1 —[recovery helper](https://github.com/VF78/coinmaster/blob/b1807f15043522b57d3e76527586f152c2db572c/runtime/coinmaster/strategy/method_a_recovery_code0.py),[native adapter](https://github.com/VF78/coinmaster/blob/b1807f15043522b57d3e76527586f152c2db572c/runtime/coinmaster/strategy/method_a_risk_native.py),[paired lifecycle](https://github.com/VF78/coinmaster/blob/b1807f15043522b57d3e76527586f152c2db572c/runtime/coinmaster/strategy/paired_prefix.py).
5. Source tests:[основные](https://github.com/VF78/coinmaster/blob/b1807f15043522b57d3e76527586f152c2db572c/runtime/tests/test_method_a_recovery_code0.py),[partial lifecycle](https://github.com/VF78/coinmaster/blob/b1807f15043522b57d3e76527586f152c2db572c/runtime/tests/test_method_a_recovery_code0_partial.py),[final guards](https://github.com/VF78/coinmaster/blob/b1807f15043522b57d3e76527586f152c2db572c/runtime/tests/test_method_a_recovery_code0_final_guards.py).
6. [Larger-quantity source tests](https://github.com/VF78/coinmaster/blob/b1807f15043522b57d3e76527586f152c2db572c/runtime/tests/test_method_a_recovery_code0_quantities.py), [publication receipt](code0-quantity-generalization-20261028/COMMIT_PUBLICATION_RECEIPT.json).
7. [CODE0 owner approval](OWNER_RECOVERY_CODE0_APPROVAL_20261028.json),[общий18 amendment](OWNER_BUDGET18_REALLOCATION_APPROVAL_20261028.json),[новое количественное разрешение](OWNER_CODE0_QUANTITY_GENERALIZATION_APPROVAL_20261028.json),[точный прошлый отказ](code0-recovery-20261028/AUTO_REVIEW_REJECTION.json).

## Что полезно проверить внешним аудитом

- Достаточны ли baseline/price-fee bounds и margin/partial constraints, где модель может не соответствовать реальному исполнению.
- Может ли wait/ACK/deadline логика создать второй owner, скрыть STOP fault или принять pending как исполненный.
- Какие оставшиеся guards ограничивают применимость при росте капитала; не представляется ли bounded prototype универсальным решением.
- Какие проверки действительно нужны до экономического P4/P3, а какие тратят время; не избыточны ли текущие gates/слотовая организация.
- Насколько достижима сама цель90% исходной прибыли при запрете прежней самостоятельной SOL-alpha и сохранении BTC core; никакого обещания существования решения пока нет.

Аудит не должен считать эти файлы разрешением менять исходники, запускать новые backtests или трогать pilot/production.
