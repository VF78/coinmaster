# CM-EARLY-HEDGE-20261024 — новизна conditional residual momentum

Дата: 2026-10-24. Статус: **NEW_SIGNAL_ONLY / SAVED_DATA_FALSIFICATION_ELIGIBLE; NO_NATIVE_ADMISSION**. Один документный проход; численных результатов нового кандидата, кода стратегии и запусков нет. Прибыль/восстановление раннего капитала пока не доказаны. Бюджет движка/short/full/training = 0; старые разрешения не переоткрываются.

## Что действительно отличается

Новая проверяемая часть — **продолжение 24h остаточного движения SOL относительно BTC**, согласованного с защитной стороной. Для BTC long — слабый относительно beta SOL, продаваемый short; для BTC short — относительно сильный SOL, покупаемый long. Это смена предсказания с возврата spread/z к среднему на продолжение остаточного дохода; сама противоположная SOL-позиция новизной не является.

Проверены требуемые записи:

- `sol-conditional-hedge-btc-band-20261023/REPORT.md`: шесть H4 EMA13/34/89 × gamma0.5/1 используют собственный SOL trend/EMA, daily beta270, deadline4h, без собственных TP/SL. Все ликвидированы; неизвестная точная компонента admission gate сохранена. Это близкая directional/trend семья, но в документе нет 24h beta-residual continuation. Новый фильтр не исправляет автоматически пропущенную защиту или admission.
- `immediate-sol-insurance-113/postmortem-report.md`, `implementation-contract.md`: постоянный floor и harvest/re-add давали drag; известные EARLY/CHOP уже ограничивали страховку adverse/confirmation. Нельзя переименовать эти решения в новый механизм. Residual continuation здесь не описан.
- `conditional-sol-2-1-50-113/implementation-contract.md`: arm>2% adverse VWAP, SOL15m OR1h break,50% remaining BTC/beta, MAX с original overlay, release<=1%; это другая admission/ownership семья.
- `sol-risk-first-20261018/implementation-contract.md` и `btc-linked-hedge-engine-audit.md` (раздел Prior H1): H1 уже имел adverse>2.5%,15m OR1h break,50%/beta, BTCflat exit. Поэтому adverse+opposite+50%+BTCflat — **старое**. cap50/dd-cov и split-ATR также не являются residual momentum.

Вывод о новизне ограничен этими текущими релевантными отчетами, не аудитом всего репозитория. Фильтр отличается от зарегистрированных правил, но экономический класс conditional trend cross-hedge близок к проваленной H4/H1 семье. Это допускает только дешёвое опровержение нового фильтра, не повтор старых native запусков.

## Точное правило для одного дешёвого диагностического экрана

Это замороженное определение для saved-data action screen, **не полная торговая lifecycle/3TP спецификация**.

1. Только существующие реальные H4 decision states выбранного native BTC reference: фактическая held BTC quantity известна и ненулевая, сторона s=+1 long/−1 short. Использовать все последовательные решения, без выбора будущих losers. `ready_at < decision`; timestamp tie/неизвестный BTC state исключается как UNKNOWN с отдельным счетчиком.
2. На закрытых UTC H1 ценах определить simple returns. Оценить beta=Cov(rS,rB)/Var(rB), sigmaB/sigmaS и rho за **720 парных завершённых H1 returns до начала последних24h**; требуется полное окно, положительная beta/rho и ненулевые sigma. Это конкретное не подогнанное rolling окно, не доказанный оптимум. Коэффициенты фиксируются на решение.
3. Последний закрытый H4 BTC return должен быть adverse: s×RB4<0. За последние24 завершённых часа M24=sum(rS−beta×rB). Требовать s×M24<0. Порог только знак0; не подбирать magnitude, ATR, EMA, z, окна или стороны после исходов.
4. SOL side=−s. Diagnostic notional NS=0.5×NB×sigmaB/sigmaS от **фактического** остатка NB. Снизить NS при уменьшении BTC; BTCflat→SOLflat. Не использовать самостоятельный original SOL и не складывать targets; existing unrelated SOL делает state ownership-UNKNOWN для этого экрана. Без BTCflat alpha, excess или leverage boost.
5. Для экрана один неперекрывающийся opportunity на BTC episode: первый подходящий state; горизонт до24h либо фактического BTCflat, что раньше. При BTC reduction пропорционально уменьшить оба сравниваемых действия; не re-add после reduction/TP. Это ограничивает повторное использование одного исхода, не заявляет работоспособную TP-схему.

**Размер требует точного названия:** это half volatility-notional, а не50% factor hedge. Beta×NS/NB=0.5×rho; при rho<1 покрытие меньше50%. Эквивалентный BTC trim NT=beta×NS. Нельзя сравнить с произвольным50% BTC trim и назвать размеры равными.

Механизм относительно trim: при замороженных quantities и коэффициенте разность gross action PnL SOL hedge минус equal-factor BTC trim равна −s×NS×(RS−beta×RB). Поэтому нужен положительный **будущий** signed residual после активации и всех затрат; наблюдённый прошлый M24 сам по себе не прибыль. Trim включает утраченную BTC прибыль при восстановлении; SOL сохраняет BTC участие, но несёт residual/basis, funding, комиссии и margin risk.

## Первичные источники и предел прочитанного

Искал непосредственно TS/relative crypto momentum и downside dependence; максимум три работы для выводов. Дата проверки доступа2026-10-24.

| Источник | Что фактически прочитано | Поддержка и предел |
|---|---|---|
| Liu & Tsyvinski, *Risks and Returns of Cryptocurrency*, NBER WP24877, August2018; journal2021. [NBER](https://www.nber.org/papers/w24877) | Аннотация первичного NBER entry и её индексированный текст. Оба NBER PDF URL дали403; полный метод/таблицы не прочитаны. | Сообщается crypto time-series momentum в BTC/XRP/ETH. SOL и условный beta-residual24h/H4 не подтверждены. Это только общий мотив исследовать persistence. |
| Han, Kang & Ryu, *Momentum in the Cryptocurrency Market: A Comprehensive Analysis under Realistic Assumptions*, written2023-12-26, SSRN posted2024-01-16; listing revised2026-09-08. [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4675565) | Только индексированная авторская SSRN аннотация; landing/PDF403. Непрочитанные таблицы/код не приписываются работе. | Аннотация различает сильнее TS и слабее cross-sectional evidence и предупреждает о ликвидациях/отрицательной прибыли при положительном mean. Это аргумент против переноса статистического momentum в обещание капитала. Нельзя из аннотации установить пригодность residual pair или наших fees/leverage. |
| Nicola Borri, *Conditional Tail-Risk in Cryptocurrency Markets*, manuscript2018-08-31, JEF50(2019),1–19. [Авторская работа, PDF на Imperial](https://www.ma.imperial.ac.uk/~ajacquie/IC_StatsFin/IC_StatsFin_Docs/Paper%206.pdf), [институциональная запись](https://iris.luiss.it/handle/11385/183370) | Доступен37-page полный PDF; адресно прочитаны introduction/data, quantile dependence/CoVaR definition и conclusions, не все таблицы. | Высокая conditional crypto dependence и ограничение liquidity; sample BTC/ETH/XRP/LTC,2015–April2018, без SOL. Нижняя против верхней tail asymmetry лишь borderline10% в тексте. CoVaR — conditional risk measure, не доказательство conditional residual momentum и не DD guarantee. |

Ни один источник не доказывает SOL24h continuation после BTC adverse H4, восстановление раннего капитала CoinMaster либо достижение70/90%S0. Научная поддержка **косвенная и недостаточная для trading admission**; не превращать корреляцию в причинный edge.

## Один минимальный cheap gate и STOP

При доступности сохранённых корректных held states/цен разрешён только один fixed-action diagnostic проход; без native equity replay, training, сетки и симулятора. Не произведён в этом документном задании. Reference и список state IDs должны быть pinned до вычисления исходов; если используются уже отобранные1529H4 states, вывод ограничен ими, а не всем рынком.

Сравнить одинаковые entry/exit marks и моменты для (a) opposite SOL указанного NS, (b) BTC trim NT с восстановлением только на общей границе, (c) no action. Учитывать полный round trip taker5.5bp/side по каждой своей ноге (Bybit BASE), собственные signed funding settlements, lost BTC upside и BTC reductions. Mark-to-mark действия — диагностические возможности, не исполненные fills; slippage неизвестен, zero не объявляется live фактом. При funding UNKNOWN сохранить результат ex-funding и break-even funding; это не net PASS.

Один заранее заданный horizon24h, один sign filter, один size. Результаты равновзвесно по BTC episode и нормированы на фактический NB. Обязательно отдельно: раннее заранее существовавшее окно[2024-09-01,2024-10-04), первый/второй benchmark год, BTC long/short, adverse continuations и recoveries. Последние классы только counterexamples, не новые фильтры. Использованные многократно исторические годы — robustness split, не независимый OOS.

**Stop/admission rule, без подгонки:** (i) нет валидных opportunities в раннем окне → STOP_EARLY_MECHANISM; (ii) mean action net не>0 против no-action в любом из раннего окна/каждого года → STOP_CAPITAL; (iii) mean net advantage против equal-factor trim не>0 в любом из этих срезов → STOP_TRIM_DOMINATES; (iv) средняя худшая adverse endpoint-loss по BTC episode вместе с SOL хуже no-action в любом из этих срезов → STOP_PROTECTION. Это простой necessary screen; малые counts/одна доминирующая episode отмечаются INCONCLUSIVE, без поиска нового порога. Funding/state/account/ordering gaps → UNKNOWN, не PASS. Знак и counts публикуются также по обеим BTC сторонам, без оптимизации по стороне.

Даже прохождение — только основание для следующего **отдельного** решения о контракте и бюджете: fixed-action residual advantage не восстанавливает собственную капитализацию/admission/календарь и не доказывает global/event DD. Actual3TP обеих ног, causal wave exits и hedge-deficit/late-fill contract здесь ещё не заданы; поэтому native admission остается закрыт. Финальные исходные TOTALfloors70=4256975.067212381 и90=5470396.514987347, settled/coherent-event DD<=50%, zero liquidation и accounting не заменяются этим экраном.

## Состояние передачи

Создан только этот `mechanism-*` файл. Product/source/runtime/Project/shared state/commit не менялись; новых процессов нет. Следующий допустимый шаг у координатора: совместить novelty с сохранённым action-screen контрактом и решить, есть ли достаточно достоверных states для одного дешёвого опровержения. При отсутствии преимущества остановить эту hypothesis, не перебирать momentum окна.
