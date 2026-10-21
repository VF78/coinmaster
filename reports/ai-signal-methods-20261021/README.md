# Методы ИИ для паттернов и торговых сигналов BTC и SOL

Обзор на 21 октября 2026 года. Для новых торговых сигналов наиболее интересны финансовая предобученная модель Kronos и универсальная Chronos-2. Для сопровождения существующей стратегии практичнее начать с небольших CatBoost/LightGBM-моделей на исходах торговых событий. TS2Vec и MOMENT дают иной способ выделения паттернов: обучаемое представление рыночного контекста. Ни одна из этих рекомендаций не является измеренным улучшением CoinMaster.

Охвачены основные практически применимые семейства и их официальные реализации. Публикации, документация и открытые репозитории подтверждают возможности инструментов; доходность после расходов на BTC/SOL требует отдельной проверки. Популярность GitHub и результаты на общих benchmarks не использованы как доказательство торгового преимущества. Обучение, inference, новые данные, backtest, установки пакетов и изменения пилота в этот обзор не входят.

## Выбор метода под торговое решение

| Задача | Подход | Что получает стратегия |
|---|---|---|
| Создать новый вход | Предобученные финансовые последовательности; supervised first-passage model | Направление и оценку результата заданного торгового плана |
| Узнавать повторяющийся контекст | TS2Vec/MOMENT; компактные временные признаки | Вектор состояния для поиска аналогов, кластеризации или небольшого классификатора |
| Отличать тренд от пилы | HMM/GMM, online change points | Текущие вероятности состояний и признаки смены режима |
| Выбрать TP и срок удержания | Conditional quantiles, competing risks, multistate hazards | Оценки движения и времени до TP/SL при явном торговом контракте |
| Улучшать существующий вход/добор | Meta-labeling + небольшое дерево/бустинг | Разрешить или пропустить определённое действие |
| Настраивать сопровождение | Событийная supervised-модель; позднее offline RL | Выбор из заранее ограниченных действий над реальной позицией |
| Обнаруживать непривычный рынок | Novelty detection, интервалы неопределённости | Сигнал недостатка уверенности, а не направление сделки |
| Добавить новую информацию | NLP новостей, funding/OI/basis, стакан | Дополнительные признаки при наличии исторических данных с корректным временем доступности |

## Предобученные модели временных рядов

| Модель | Возможности | Практический выбор |
|---|---|---|
| [Kronos](https://github.com/shiyu-coder/Kronos) | Финансовый tokenizer свечей и генерация продолжений; mini 4.1M, small 24.7M, base 102.3M | Первый отдельный кандидат для новых финансовых сигналов; small/mini вместо обучения с нуля |
| [Chronos-2](https://github.com/amazon-science/chronos-forecasting) | Native multivariate/cross-series, прошлые и известные будущие covariates, quantiles; 120M, также small 28M | Совместный контекст BTC/SOL плюс исторические дополнительные признаки |
| [TiRex-2](https://github.com/NX-AI/tirex-2) | Рекуррентная multivariate-модель; past/future-known covariates; 38.4M active univariate+44.1M multivariate | Альтернативная архитектура для zero-shot; открытый пакет проверяется авторами на macOS/Linux |
| [TimesFM2.5](https://github.com/google-research/timesfm) | 200M, до16k context, quantile head; covariates через XReg | Сопоставимый универсальный challenger; XReg не равен native совместной модели каналов |
| [Toto2.0](https://github.com/DataDog/toto) | Multivariate quantile forecasts; есть4M/22M checkpoints | Малые модели технически интересны; observability-домен отличается от рынка;2.0 пока без exogenous/fine-tuning |
| [Sundial](https://github.com/thuml/Sundial) | 128M, zero-shot stochastic paths; авторы приводят CPU-замеры на M1Pro16GB | Удобный генеративный challenger; univariate, fine-tuning в README не завершён |
| [Moirai/uni2ts](https://github.com/SalesforceAIResearch/uni2ts) | Zero-shot/fine-tuning framework | Исследовательский comparator; конкретные веса имеют ограничения применения |

У **Kronos** small/base context 512, mini 2048; large 499M публично не выпущен. [Small weights](https://huggingface.co/NeoQuasar/Kronos-small) и [tokenizer](https://huggingface.co/NeoQuasar/Kronos-Tokenizer-base) обозначены MIT. [Предсказатель](https://github.com/shiyu-coder/Kronos/blob/master/model/kronos.py) поддерживает MPS/CPU и усредняет sample_count траекторий. Отдельные draws можно получать повторными sample_count=1, но средняя траектория не является вероятностью достижения TP до SL. Сохранение sample axis потребовало бы небольшого будущего адаптера, а не нового торгового движка.

В [статье Kronos](https://arxiv.org/html/2508.02739v1) обучение заканчивается июнем 2024, evaluation начинается июлем 2024; crypto-эксперимент использовал OHLC без volume/amount. Это не независимое подтверждение происхождения произвольной современной HF-ревизии: конкретный checkpoint и corpus cutoff надо закреплять. Заявленный RankIC не равен прибыли после расходов; отдельный проверенный SOL-результат не установлен.

**Chronos-2** отличается от старого Chronos-Bolt: поддерживает несколько связанных целей и covariates. [Model card](https://huggingface.co/amazon/chronos-2) описывает quantiles и Apache-2.0. Это кандидат для BTC/SOL+прошлых volume/volatility/funding/OI при наличии данных. Будущие реализации funding или цены нельзя передавать как known-future. Quantiles на каждом горизонте не задают совместное распределение траектории.

У TiRex-2 открытые [веса](https://huggingface.co/NX-AI/TiRex-2) Apache-2.0, но fine-tuning и оптимизированный streaming продвигаются как PRO-возможности. Архитектурная пригодность к streaming не доказывает скорость конкретного Mac/VPS. [FAQ](https://nx-ai.github.io/tirex-2/faq/).

### Лицензии кода и весов

| Проект | Подтверждённое различие |
|---|---|
| TimesFM | Код Apache-2.0; веса до 2.5 Apache-2.0. Веса 3.0 ограничены non-commercial/non-production self-hosted использованием; Google Cloud имеет отдельные условия |
| Moirai | uni2ts Apache-2.0, но [Moirai 2.0-small](https://huggingface.co/Salesforce/moirai-2.0-R-small) и 1.1-small CC-BY-NC4.0 |
| [TabPFN](https://github.com/PriorLabs/TabPFN) | Код Apache-2.0; современные 2.5/2.6/3/3.5 weights non-commercial. V2 имеет отдельную PriorLabs attribution license; условия конкретной версии надо фиксировать |
| [TabPFN-TS](https://github.com/PriorLabs/tabpfn-time-series) | Cloud по умолчанию не равен локальному открытому inference; новые default weights наследуют свои условия |

TabPFN интересен как предобученная модель **табличных признаков** с малым числом примеров. Это отличается от forecasting-сети. У TabPFN-TS прошлые/static covariates ограничены иначе, чем у Chronos-2; multivariate targets могут обрабатываться независимо. Его не стоит автоматически выбирать для совместного BTC/SOL+OI/funding. Проверять надо конкретный backend/modelcard, не название пакета.

Лицензия каждой версии важна при выборе инструмента для live. Точные сроки расчёта и память на M2 Pro здесь не измерялись.

## Обучение на исходах торговых событий

Наиболее прямой альтернативой прошлому универсальному forecast-опыту являются **CatBoost/LightGBM с финансовой разметкой**. В момент появления заранее определённого setup модель получает только прошлые признаки и оценивает исход конкретного плана. Признаки могут включать volatility, направление/силу тренда, диапазон, объём, BTC/SOL relative state, возраст позиции и стадию TP.

[CatBoost](https://github.com/catboost/catboost), [LightGBM](https://github.com/lightgbm-org/LightGBM) и [XGBoost](https://github.com/dmlc/xgboost) моделируют нелинейные взаимодействия. Например, пробой может быть полезен только при некотором сочетании волатильности и объёма. CatBoost [has_time/ordered boosting](https://catboost.ai/docs/en/references/training-parameters/common) не заменяют chronological validation. Нелинейность также не решает отсутствие информации или независимых событий; для CoinMaster предыдущая слабая logistic-модель не является доказательством, что новый бустинг поможет.

**Triple barrier** задаёт прибыльный барьер, убыточный барьер и предельное время. Это не три take-profit. **Meta-labeling** использует уже заданное направление и учится принимать/отклонять такой вход. Для новых направлений нужен отдельный primary signal или явно определённая многоклассовая задача. Практическая открытая реализация: [mlfinpy labeling](https://mlfinpy.readthedocs.io/en/latest/Labelling.html); [uniqueness/concurrency weights](https://mlfinpy.readthedocs.io/en/latest/Sampling.html) учитывают перекрытие, но не создают новые наблюдения.

Для трёх TP следует различать `P(TP1 раньше SL за H)`, `P(TP2 раньше SL за H)` и `P(TP3 раньше SL за H)` либо состояния после частичных закрытий. При одинаковом stop/horizon эти вероятности вложены. После TP1 изменились объём или стоп — изменился и торговый контракт. Вход на следующей минуте, fees и неопределённость порядка касаний в OHLC должны присутствовать в разметке и проверке.

В частности,70% выигрышных исходов по+0.1% и30% по−1% дают ожидание−0.23% до расходов. Поэтому accuracy или доля касаний TP не являются достаточным критерием сигнала.

### Распределения и время до события

[CatBoost MultiQuantile](https://catboost.ai/docs/en/concepts/loss-functions-regression) и [NGBoost](https://stanfordmlgroup.github.io/ngboost/1-useage.html) дают условные квантили/распределение вместо одной цены. Это полезно для диапазона и downside, но endpoint return quantiles нельзя объявлять готовыми TP с вероятностями касания.

[XGBoost AFT](https://xgboost.readthedocs.io/en/latest/tutorials/aft_survival_analysis.html) поддерживает censored interval labels. Для TP против SL существенны **конкурирующие события**: stop-out нельзя безосновательно трактовать как независимое цензурирование TP. [Scikit-survival competing risks](https://scikit-survival.readthedocs.io/en/stable/user_guide/competing-risks.html) описывает cumulative incidence; готового end-to-end BTC/SOL-алгоритма там нет. Практический вариант — небольшая discrete-time hazard model с исходами TP/SL/событие ещё не наступило. Она требует собственной корректной разметки и достаточной поддержки событий.

У [LightGBM ranking](https://github.com/lightgbm-org/LightGBM/blob/main/docs/Parameters.rst) иной смысл: выбрать лучший из одновременно доступных setup/планов. Для двух активов пригодных независимых сравнительных групп может быть мало. Rank-score не является calibrated probability.

## Самостоятельное выделение паттернов

[TS2Vec](https://github.com/zhihanyue/ts2vec) обучает компактные представления временных окон, включая causal sliding inference. Затем можно искать соседей **по обученному контексту**, кластеризовать состояния или обучить малую supervised head. Это существенно отличается от STUMPY, который сопоставляет заранее выбранную геометрию ряда. [Авторская статья](https://arxiv.org/abs/2106.10466) подтверждает качество representations на общих задачах, не торговое преимущество.

[MOMENT-small](https://github.com/moment-timeseries-foundation-model/moment), [37.9M checkpoint](https://huggingface.co/AutonLab/MOMENT-1-small), даёт готовые embeddings/reconstruction/anomaly representation. Для нового BTC/SOL-выхода потребуется обученная head или linear probe: pretrainedencoder не равен готовому торговому classifier. MIT.

[TS-TCC](https://github.com/emadeldeen24/TS-TCC) — дополнительная contrastive-альтернатива, но её sensor-augmentations нельзя механически переносить на финансовые ряды: преобразование может удалить смысл направления или volatility. Encoder обучается внутри TRAIN; unsupervised fit на всём CHECK также раскрывает будущее.

Более дешёвый путь — признаки [tsfresh](https://github.com/blue-yonder/tsfresh) или [catch22](https://github.com/DynamicsAndNeuralSystems/pycatch22) плюс маленький классификатор. tsfreshMIT; pycatch22GPL3+. Эти признаки не генерируют сигнал самостоятельно. Отбор тысяч признаков на всей истории до split является утечкой; маленький boundedнабор разумнее.

Для объяснимых моделей доступны [InterpretML EBM](https://github.com/interpretml/interpret) и [PySR](https://github.com/astroautomata/PySR). EBM даёт аддитивные эффекты и ограниченные взаимодействия; PySR ищет короткую математическую формулу. Они подходят для понятного фильтра или риск-оценки. Поиск формул также является перебором гипотез и легко переобучается; нужны лимиты сложности, операторов и времени, последующий новый контроль. Никакой формулы повышения ROI источники не предоставляют.

## Режимы рынка и обнаружение изменений

[GaussianHMM](https://github.com/hmmlearn/hmmlearn) оценивает скрытые состояния и переходы; [GMM](https://scikit-learn.org/stable/modules/mixture.html) — более простой контроль кластеров. Входом могут быть trailing returns, volatility, directional efficiency, compression и relative BTC/SOL. Названия «тренд» и «пила» присваиваются по TRAIN-свойствам; состояние не является направлением новой сделки.

По [HMM API](https://hmmlearn.readthedocs.io/en/stable/api.html) Viterbi/MAP используют предоставленную последовательность. Full-historysmoothed states не подходят для решения в прошлом. Нужны forward filter или endpoint каждого доступного prefix с параметрами, обученными только на прошлом. hmmlearnBSD3 и limited maintenance; вычислительно это компактный CPU-кандидат.

[BOCPD](https://arxiv.org/abs/0710.3742) оценивает вероятность недавней смены режима; [реализация](https://github.com/hildensia/bayesian_changepoint_detection) требует обычного review перед зависимостью. [Ruptures](https://github.com/deepcharles/ruptures) — прежде всего offline segmentation. Для online-условий необходимо оценивать реальное время обнаружения; нельзя задним числом считать сделку открытой на найденной позже точке перелома. Смена режима не говорит сама по себе buy/sell.

[IsolationForest/novelty detection](https://scikit-learn.org/stable/modules/outlier_detection.html) может предупреждать о контексте вне обучающего распределения. Он может также отбрасывать самые прибыльные необычные тренды, поэтому abstention требует экономической проверки.

## Последовательные нейросети и многомерные связи

[NeuralForecast](https://github.com/Nixtla/neuralforecast) содержит TCN, NHITS, PatchTST, iTransformer и TFT. Одна библиотека достаточна для небольшого supervisedсравнения, без добавления нескольких forecasting frameworks.

| Архитектура | Осмысленная роль |
|---|---|
| TCN | Компактная сеть для временной структуры, ranges/volatility/excursions |
| NHITS | Прогноз компонентов на разных масштабах |
| [PatchTST](https://arxiv.org/abs/2211.14730) | Patch-представление и длинный контекст с channel-independent weights |
| [iTransformer](https://arxiv.org/abs/2310.06625) | Взаимодействия между переменными |
| [TFT](https://arxiv.org/abs/1912.09363) | Прошлые/static/известные будущие признаки, разные горизонты |
| [MTGNN](https://github.com/nnzhan/MTGNN) | Обучение графа взаимосвязей множества рядов; для одних BTC/SOL добавочная сложность может не окупиться |

Сложные attention/mamba/graph-архитектуры не являются самостоятельной методикой получения alpha. Для двух активов и105/26 сделок S0 увеличение ёмкости без новой информации особенно сомнительно. [Darts](https://github.com/unit8co/darts), [sktime](https://github.com/sktime/sktime) и [aeon](https://github.com/aeon-toolkit/aeon) — альтернативные tooling-экосистемы, не готовые торговые модели.

## Новости и стакан как дополнительные источники информации

[FinBERT](https://github.com/ProsusAI/finBERT) извлекает sentiment из финансового текста; [FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) предоставляет финансовые NLP-модели/workflows. Их практический смысл — извлечение признаков из новых источников: события, заявления, риски, направления sentiment. Качество sentiment classification не равно будущей доходности BTC/SOL. Для проверки нужны архивы с первоначальным временем публикации, задержками и исправлениями; знание современной LLM о произошедших событиях способно раскрывать исторические исходы.

[DeepLOB](https://github.com/zcakhaa/DeepLOB-Deep-Convolutional-Neural-Networks-for-Limit-Order-Books) и [статья](https://arxiv.org/abs/1808.03668) используют глубину стакана для коротких направлений цены. Это иной информационный набор, чем OHLCV, и потенциальный путь улучшения исполнения/короткого сигнала. Нужны реальные исторические L2/trades, затраты очереди/latency/spread; из свечей1m этот вход восстановить нельзя. FI-2010 на акциях не является готовым Hyperliquid-датасетом. Авторский демонстрационный notebook нельзя без проверки лицензии/поддержки считать productionSDK.

Funding, OI, basis, flow и ликвидации могут дать дополнительную информацию для любого простого learner. Их историческая полнота и время фактической доступности важнее нового названия сети. Список потенциальных признаков не означает, что все эти данные уже имеются в CoinMaster.

## Обучение действий и LLM агенты

[d3rlpy](https://github.com/takuseno/d3rlpy) реализует offline/online RL, включая conservative Q-learning. Теоретически действия hold/reduce/exit и состояние пары ближе к управлению DD, чем прогноз цены. Однако запись deterministic S0 не содержит исходов всех альтернативных действий. OfflineRL/OPE не восстанавливают их автоматически; нужна поддержка действий и корректная среда исполнения.

[FinRL](https://github.com/AI4Finance-Foundation/FinRL), [FinRL-Meta](https://github.com/AI4Finance-Foundation/FinRL-Meta), [TradeMaster](https://github.com/TradeMaster-NTU/TradeMaster), [Qlib](https://github.com/microsoft/qlib) дают исследовательские pipelines/environments. Они не являются готовым обученным BTC/SOLпобедителем. Для CoinMaster не предлагается второй PnL/matchingengine: экономика остаётся в Nautilus. При нынешнем объёме эпизодов RL имеет низкий приоритет.

[EconML DRPolicyTree](https://www.pywhy.org/EconML/_autosummary/econml.policy.DRPolicyTree.html) и [CausalML](https://github.com/uber/causalml) — реальные инструменты оценки неодинаковых эффектов действий. Они требуют identification/overlap/treatment variation. При отсутствии действия в данном типе состояния «doublyrobust» не создаёт недостающий наблюдаемый исход. Реплей является модельным counterfactual с ограничениями исполнения.

[TradingAgents](https://github.com/TauricResearch/TradingAgents) и [FinRobot](https://github.com/AI4Finance-Foundation/FinRobot) полезнее как аналитики новостей и отчётов. Дебатирующие LLM-агенты не дают воспроизводимый вероятностный forecast без отдельного процесса; API-затраты и стохастичность добавляют вариативность. В первую очередь эти системы не выбираются.

## Оценка неопределённости и качество исследования

[MAPIE](https://mapie.readthedocs.io/en/stable/generated/regression/1-quickstart/plot_ts-tutorial/) описывает EnbPI, block bootstrap и adaptive conformal. Эти методы помогают оценивать интервалы/abstention. Обновлять residuals можно только после появления реального исхода. Exchangeability, averagecoverage и условная надёжность в каждом crypto-режиме — разные требования; интервалы не гарантируют profitability или DD50%. [Fortuna](https://github.com/awslabs/fortuna) архивирован23 апреля 2025, поэтому не предлагается новой зависимостью.

Платформа [Qlib](https://github.com/microsoft/qlib) может помогать организовать данные и rolling experiments, но не требует замены текущего Nautilus. [Mlfinlab](https://github.com/hudson-and-thames/mlfinlab) имеет purchased access/all rights reserved; его нельзя путать с отдельным MIT mlfinpy. Для выбора нужен конкретный algorithm, не очередная большая платформа.

[GIFT-Eval](https://arxiv.org/abs/2410.10393) полезен для общей оценки forecasting, но не содержит доказательства нашей торговой экономики. [Финансовый benchmark 2026](https://arxiv.org/abs/2606.27100) на 5 акциях обнаружил сильные ранги TSFM, однако малые/редкие значимые преимущества над random walk; это preprint и не исследование BTC/SOL. [Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf) объясняет риск выбора из многих вариантов. Применение этих проверок не меняет критерий пользователя на Sharpe: критерий остаётся TOTAL при заданном ограничении DD.

Даты TRAIN/CHECK остаются причинными. Для нового предобученного checkpoint надо отдельно знать corpus cutoff и возможное пересечение с историей. Одна и та же цена многократно видна в overlapping windows, а BTC/SOL связаны; миллион свечей не означает миллион независимых исходов. Часовые значения цены и доходности сравниваются с разными простыми controls. Модели TP сравниваются с prior-распределением того же target; линейный classifier не должен быть единственным baseline.

## Приоритеты для Mac и CoinMaster

Аппаратные оценки ниже — инженерная предварительная оценка. Скорость/RSS/MPS-совместимость конкретных моделей не проверялись. Inference и fine-tuning одной модели имеют разную потребность в памяти.

| Приоритет | Предлагаемый путь | Mac M2 Pro 16 GB | Место в работе |
|---|---|---|---|
| 1 для S0 | Малый CatBoost/LightGBM на trade events, first-passage labels; простой линейный/EBM-контроль | CPU, небольшие таблицы; наиболее реалистичен | Проверка качества entry/add/hold, сохранение выгодного overlay |
| 1 для новых сигналов | Kronos-small с закреплёнными pretrainedweights, без начального fine-tuning | 24.7M; небольшой context/batch; MPS/CPU реализованы | Отдельная попытка финансового sequenceforecast |
|2 | Chronos-2-small/120M с BTC/SOL и только доступными covariates | Небольшой context/batch, осторожно с числом variates | Проверка cross-asset информации, альтернативный ready-madeforecast |
|3 | TS2Vec либо frozen MOMENT-small+малый classifier | Ограниченные окна/малые batches | Обучаемый patterncontext, отличие от fixed STUMPY geometry |
|Контекст для 1 | HMM/GMM/BOCPD | Компактный CPU | Режим/смена режима, не самостоятельный buy/sell |
|Позже | Survival/competing risks, небольшой TCN | CPU/small PyTorch; зависит от числа событий | Более точное время/путь события после простого baseline |
|Низкий | RL, LLM trader, massive Transformer grid | Ограничения данных/среды доминируют над RAM | Не первые эксперименты |

Три самостоятельных направления для следующего согласования: **событийный бустинг с правильными исходами**, **Kronos для новых сигналов**, **TS2Vec/MOMENT для learned patterns**. Chronos-2 — отдельный предпочтительный challenger, если вопрос именно в совместной информации BTC/SOL и covariates; не нужно одновременно запускать все семейства. Наличие только 5 пригодных SOL TRAIN-событий в прежнем узком задании означает STOP для этого обучения, а не повод заменить logistic на CatBoost. Другой target/событийный universe должен иметь самостоятельное обоснование.

Для DD до 50% с сохранением90% net profit S0 итоговый gate неизменён: terminal TOTAL>=5,470,396.514987347, одинаковые данные/издержки/маржа/исполнение, одинаковая глобальная DD без reset и полный native account path. Такой результат ни один найденный источник не гарантирует. Модель сначала даёт воспроизводимый сигнал или дополнительную информацию, затем отдельно проверяется её ценность в Nautilus. Самостоятельный генератор новых входов и ограниченный adviser для S0 должны оставаться разными версиями стратегии.

## Статус и следующее решение

Обзор завершён. Источники подтверждают существование и возможности инструментов; новые модели CoinMaster не обучены и их экономические результаты UNKNOWN. Ранжирование означает пригодность к следующей проверке, не доказанный ROI. Исходный pilot/S0 не менялись. Следующий experiment contract, список методов, labels, даты, предел ресурсов и budget требуют согласования до каких-либо запусков. Задача #113 в GitHub Project #2 остаётся завершённым прошлым исследованием; новые implementation-задачи не создаются автоматически.
