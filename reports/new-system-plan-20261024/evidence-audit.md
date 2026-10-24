# CM-NEW-SYSTEM-PLAN-20261024: проверка сохранённых доказательств

**Вывод: проходящего кандидата нет; B5/H5 нельзя принять как следующий обязательный native-перенос.** Требование владельца — сохранить BTC-ядро и переработать SOL именно в хедж. Приложенный TXT одновременно меняет BTC-лестницу, TP-якорь и SOL; это самостоятельная гипотеза, не готовый контракт сохранения ядра. Расходный перенос пока не обоснован. Проверка только локальных сохранённых данных: новых engine/simulator/training/full запусков **0**, product/runtime/VPS изменений **0**.

## Проверенные источники и пределы проверки

Рабочий checkout `/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021`, начальный HEAD `0dd0f16092868f2457da248d49dde2b6bc11b8fd`, начальный dirty пуст. Прочитаны обязательные bootstrap/протоколы и только относящиеся к вопросу отчёты. TXT `/Users/vf/Downloads/COINMASTER_NEW_SYSTEM_CODEX_20261024.txt` прочитан как предложение с проверяемыми утверждениями. Owner clarification: no ZIP exists. Five loose Downloads files are provided: main TXT, RESULTS_AND_DECISION.txt, ROI_GAP_DIAGNOSIS.txt, old_S0_BTC_only_native_receipt.json, b-50-90-next-20261023_comparison.json. Text summaries document external H1 research; raw sim configs/equity are unavailable and independent reproduction/raw verification was not performed. No further ZIP search. Both supplied JSON files are byte-different but parsed semantically equal to their original local git/repository references; formatting differences do not create new native evidence. No imported simulator executed.

Локальный git содержит `f7587cd8e70609f71d95c38934dee490f4497cb4` и архивные `reports/immediate-sol-insurance-113/btc-only-{native-receipt,launch-and-completion,preparation-receipt,calendar-comparison}.json`, `btc-only-reference.py`. SHA256 receipt, preparation, calendar и wrapper точно совпали с ссылочными hash в launch-and-completion. Это проверка целостности сохранённых доказательств, не свежая проверка VPS/raw.

- S0 BTC-only: native TOTAL **280748.52263020**, DD **64.07394986310021402940985169%**, 105 parents,416fills, exit0, FLAT, liquidations0. У wrapper действительно `expected=dict(selected.config.candidate)` и только `sol_overlay_enabled=False`; funding=True, seed10000, fresh-result guard. Receipt/preparation утверждают85 идентичных sourcepins исходного selected winner, sole candidate delta SOLoff. Календарь:105 общих дней, P0/side/first-fill time без изменений,99 размеров Q изменились из собственного compounding.
- Важная идентичность: архив связан с **SOURCE759 `759823d69a74e72b123add5ae775dd8c3aed4ac5`**, selected TOTAL6077107.23887483 и control raw hash `4dbfaf0d228f27ebc5e24157b613b0ddd279bffa2d163d042684bdad13bbec1b`. Более поздний текущий S0 anchor `75ffc9c...` не byte-identical source: git показывает последующие изменения. Подготовка подтверждает original selected control; не утверждаем повторную проверку всех85 frozen файлов или текущую source-equivalence. Exact selected config/raw VPS-файлы отдельно не получены.
- Архивный BTC-only config hash `289c6b6eee7ba3c772458ade47348d5c0261499b6aab4d33d12a8bd5c1b4d6b6`; selected-config hash и winning-config-copy hash различны по виду представления и сохранены в JSON. Нельзя сравнивать их как одно представление JSON без исходных файлов.
- **Это не E4 BTC-only.** Уже принятый E4 R1 имеет83parents, TOTAL304372.03028516, settled DD66.9203964274313%; источник `reports/market-redesign-20261024/comparison.json` и REPORT. Он закрывает пункт предложения «если нет E4 BTC-only»; дополнительный full не нужен.
- Старый BTC-only DD64.0739 относится к `all_native_close_samples`3153599; paired-close1051200 имеет такой же максимум. Новые R1/R2/R3 DD —1051199 settled receipts. Более частый all-event DD нового варианта нельзя без пересчёта общей sampling basis объявить прямым улучшением/ухудшением к старому settled DD.
- Signed funding архивного BTC-only **UNKNOWN**:899 событий, но старый audit содержит post-total без signed cash delta. Funding включён в native total, компонент cash не придуман. У R1 подписанный cash funding8649.65810383 уже принят; это не заполняет старый UNKNOWN.

## Денежные пороги

Все расчёты Decimal80, seed10000, S0 net profit6067107.23887483. Retention = `(TOTAL-10000)/(6077107.23887483-10000)`.

| Gate | Минимальный TOTAL USDT |
|---|---:|
| Исследовательский70% net profit S0 |4256975.067212381|
| Финальный90% net profit S0 |5470396.514987347|

DD<=50% обязателен;30–50% предпочтителен, DD<30% допустим. Исследовательские70% не заменяют финальные90%; ни один порог не пересчитывается от ослабленного BTC-only контроля.

| Вариант | TOTAL | DD% | Retention от S0 | Статус доказательства |
|---|---:|---:|---:|---|
| S0 BTC-only SOURCE759 |280748.52|64.0739|4.4626%|Сохранённый native receipt|
| E4 BTC-only R1 |304372.03|66.9204|4.8519%|Принятый full native|
| U3TP R2 |225919.51|66.8015|3.5589%|Принятый full native|
| CLEAN_Q R3 |120718.40|68.6034|1.8249%|Принятый full native|
| B5front30/H5 OLHC |40017.23|44.8486|0.49475%|Непроверенное утверждение TXT, H1 scenario|
| B5front30/H5 OHLC |40247.86|44.8729|0.49855%|Непроверенное утверждение TXT, H1 scenario|

Даже если B5 цифры подтвердятся, для70% требуется примерно **140–141 раз** больше его net profit; это не небольшой funding/исполнительный разрыв. Низкая DD при потере почти всей прибыли не проходит gate. Original S0 и E4 с прежним SOL остаются экономическими benchmark, но их самостоятельная SOL alpha не может скрыто называться чистым хеджем.

## Противоречия, которые единый контракт должен закрыть

1. **Сохранить BTC-ядро против B5.** Пять входов30/17.5/17.5/17.5/17.5 и adaptive adverse depth меняют собственно BTC. Базовым следующим контрактом должен быть явно назван сохранённый BTC; B5 остаётся не прошедшим внешним research artifact. S0 и E4 имеют105/83parents и разные admission/reentry; не смешивать их.
2. **Фиксированный first-child P0 против dynamic VWAP.** Уже проверенные R2/R3 после provisional partial protection фиксируют P0 после первого child. Внешний B5 переякоряет3TP после каждого add до первого TP. Это отдельная экономическая delta, а не исправление отчёта. Сохранение causal d3 отдельно от изменения якоря и ширины лестницы.
3. **Наличие SOL против реального покрытия.** H5 mandatory core равен1/5 от half-MV, estimated factor relief `0.1*rho²`, а не50% BTC. Настоящий contract должен назвать minimum actual coverage, delay, missing-data/margin fallback и поведение при снижении BTC. Отметка «SOL открыт» страхование не доказывает.
4. **Незакрываемый core против строгих3TP.** Внешний core не закрывается tactical TP/SL;3TP относятся только к tactical части. Если владельцу нужны3 настоящих TP на весь фактический inventory каждой ноги, это другой контракт. Для legacy BTC строгое3TP само по себе отличается от исторической zeroTP/positiveIOC семантики. Нельзя одновременно обещать неизменную legacy BTC и новую строгую защиту без явной delta.
5. **DD sampling.** Новый all-event marked equity с pre-fill peaks полезен, но comparisons и gates должны быть на общей заранее названной шкале. Отдельно показывать old comparable settled DD, all-event DD и OHLC diagnostic bounds; последние не выдавать за историческую intraminute истину.
6. **Funding calendar.** В TXT reference_funding.sqlite прямо назван журналом старых открытых позиций, не полным рыночным календарём. Для нового lifecycle он недостаточен; полные source dates/rates должны быть проверены до любой экономики. Нулём UNKNOWN не заменять.
7. **Exact cash bridge.** Рекомендуемая unexplained=0 должна сохранять исходную native money precision: R1/R2 уже имеют −2e−8/−4e−8 cash rounding residual. Не подгонять total и не присваивать остаток funding; фиксировать измеренный residual и ранее принятый допуск.

## Один выполненный дешёвый расчёт

Без нового execution model прочитан только уже сохранённый `native-analysis-sol-R3-features.csv` (SHA256 `598591a2543088181ec003baf0a2d1e696e04c792c3a76c568e44d93441edbe7`):1529H4состояний/77actual R3cycles, lag720 строго раньше decision. Для каждой строки вычислено `beta*(NS_HALF_MV/5)/NB` и проверено равенство `0.1*rho²` (max residual4.24e−17 из сохранённой float precision).

Первая пятая H5 даёт estimated BTC factor relief **3.476–7.903%**, медиана **6.355%**, среднее **6.177%**, equal-cycle mean **6.234%**. Годовые средние5.611%/6.651%. Полный half-MV дал бы17.381–39.514%, mean30.883%. Это ограничивает маркетинговое значение «обязательной защиты»: заявленный core слабее половинного хеджа примерно в5раз ещё до lot rounding.

Это **описательная арифметика на фактических R3 состояниях**, не измерение B5 activation: f>=0.5 здесь не фильтровался, fills/activation/latency/funding/TP не моделировались, DD/TOTAL не получены. Перекрывающиеся H4строки не независимы. Ранее принятый same-action SOLscreen уже STOP_SOL/INCONCLUSIVE; новый расчёт не отменяет этот вывод и не создаёт новый gate.

## Компактные gates следующего плана

- G0: зафиксировать сохранённый BTC recipe/source, exact allowed delta=SOL hedge; отдельно разрешать любое изменение BTC entries/3TP anchor. Действующие full бюджеты закрыты; этот аудит бюджет0.
- G1: на saved fills/features сначала измерить старую SOL exposure/coverage в BTC-flat и BTC-held состояниях, отдельно по годам и крупным DD. Разложение factor/residual с lagged beta описательное; не является новой causal alpha или counterfactual TOTAL. Нельзя вычитать старые SOLдоллары и оставлять старые BTCqty.
- G2: до implementation определить actual hedge coverage/latency/cap, noSOL-whenBTCflat, invalid-data/margin failclosed, partial/ACK/reject и TP/core ownership. Минимум coverage не выбирать по лучшему исходу уже просмотренной истории. Новый data gap допустимо записать UNKNOWN.
- G3: допуск продукта только после одной новой поддержанной причинной гипотезы, одного frozen native протокола, явного бюджета. Сначала meaningful native state/order invariants, свежий funding journal, общий sampling/accounting контракт; никаких импортированных симуляторов как authority и новой сетки параметров.
- G4: экономическая исследовательская квалификация TOTAL>=4256975.067212381 и DD<=50%, final qualification TOTAL>=5470396.514987347 и DD<=50%, liquidations0, complete provenance/cash/terminal inventory. Уровень evidence отдельно: external H1 claim / validated saved-data attribution / native mechanical / full native economic. История2024–2026 уже просмотрена, разбиение по годам не fresh OOS.

**Следующий конкретный шаг координатора:** объединить план вокруг сохранённого BTC и проверяемого insurance contract; использовать готовый R1 без повторения. Удалить обязательный B5 implementation/full из очереди. Если на saved-data атрибуции не появляется конкретный поддержанный источник сохранения прибыли при hedge cap, зафиксировать NO_GO и не запускать новое семейство.

Никакие shared-state/Project/commit/push изменения этим исполнителем не сделаны. Все результаты этого микрошагa — данный файл, `evidence-audit.json`, `evidence-numeric-floors.json`; передача координатору завершает ограниченный evidence audit. RESET_PREP прочитан, общую публикацию/ACTIVE_TASK выполняет координатор в рамках своей задачи.

Additional authorized saved-data step completed: sol-attribution-report.md and verification PASS. Twenty-five old E4 SOL cycles yield713702.32329125 fill-net ex-funding. BTCflat SOL-held110777/194630minutes, held PNL426629.8025. This is observed attribution, not counterfactual removal value or new GO.
