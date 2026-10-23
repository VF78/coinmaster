# S0: полный системный аудит, явное SOL-исполнение и H_SOL / H_BTC

**Ограниченный пакет завершён с результатом NO_GO: варианта DD≤50% и ≥90% чистой прибыли сопоставимого S0 нет.** Код и контракты реализованы и проверены; экономическая цель не достигнута. Пилот, production, конфигурация торговца, сервисы, ключи и реальные ордера не менялись.

## Что выполнено из исходного задания 0–4

| Требование | Что сделано и где доказательства |
|---|---|
| 0. Методики системной оптимизации и проверка применимости | Переиспользованы72sourcepins/15сопоставимых архивных траекторий/11источников и два настоящих2×2контраста завершённого аудита. Применены native lifecycle fixtures, явный контроль изменения модели исполнения, локальная q1 sensitivity, причинные prefix-метки, независимая полная денежная проверка и атрибуция по всем24месяцам. Методы выявили реальные причины, но не дали проходящую торговую политику. methods-and-coverage-review.md, rule-registry.json, evidence-audit.md. |
| 1. Весь алгоритм, полезные и сомнительные правила | Реестр43активных правил S0/E4: source, назначение, происхождение, implementation/economic evidence отдельно, проблема и KEEP/FIX/TEST/DEFER. Обоснованность ownership/денег не приравнивается к прибыльности EMA/TP/z/плеча. Намерение автора не выдумывается. Выделены скрытыйSOLsizegovernor, зависимость zeroTP от q1, grossH/additiveSOLrights, совместный капитал и groupclock. |
| 2. BTC: вход, сопровождение, DD/ROI | 83parent-level наблюдения/50волн; TP1zero83/83, TP2zero58/83; Локальный сдвиг−1bp меняет ветку6parents, +1bp —10parents. EMA/E4/TP/split не переписаны. Проверена H_BTC: только завершённые минуточныеMARKметки, strictready, Q90, один k после cap до zeroTP/лота. 19реальных уменьшений дали отрицательную экономику. |
| 3. SOL: адекватность alpha/hedge и риски | 56.9167%SOL-active времени BTCflat,13/25SOLциклов начинаются BTCflat; это selectivealpha, не непрерывная страховка BTC. Явное1000SOLисполнение исследовано отдельно. H_SOL проверяет каждыйADD, считает held/pending/reserved один раз, не режет удержание. Локальная октябрьская польза обернулась январским риском после изменения капитала. |
| 4. Вся система и взаимодействия | Все24месяца,7исходныхE4окон и новые максимумы; actualnative деньги/позиции/ордера/fees/fundingjournal. Разделены локальный риск и вся траектория реинвестирования. Комбинация отклонена доказательством неизменного январского префикса; никакой выдуманной equity-кривой или TOTAL комбинации нет. |

## Сопоставимые результаты

Период `[2024-09-01,2026-09-01)`, UTC; старт10000USDT, RESERVE0, global high-water без сброса. Один native Nautilus1.231.0; реальные Bybit execution/mark/funding данные, зафиксированные fees/margin/terminal conventions. Модель исполнения использует synthetic1mCLOSE L1 и не является tick/L2-моделью биржи.

| Вариант, одна новая execution model | TOTAL USDT | ROI | Global settled DD | Прибыль сопоставимого S0 | BTC / SOL fills | Fees USDT |
|---|---:|---:|---:|---:|---:|---:|
| S0_EXPLICIT_CONTROL | 6 482 334.93 | 64723.35% | 66.26% | 100.00% | 416 / 215 | 981 911.41 |
| E4_EXPLICIT_CONTROL | 6 022 427.56 | 60124.28% | 57.59% | 92.89% | 337 / 206 | 732 226.13 |
| H_SOL | 3 964 359.61 | 39543.60% | 65.69% | 61.10% | 337 / 172 | 608 681.20 |
| H_BTC | 5 352 125.97 | 53421.26% | 57.59% | 82.54% | 337 / 206 | 661 862.03 |

Для новой модели порог90%чистой прибыли: **5835101.440491649USDT**. Старый абсолютный порог **5470396.514987347USDT** показан отдельно в comparison.json и не снижается задним числом. Ни один кандидат не проходит оба условия; у всех четырёх прогонов0model liquidations, terminal native flat,0active terminal orders, complete1051199settled receipts.

Архивные S0=6077107.23887483/DD66.2569148647% и E4=5631617.35953723/DD57.5854104596% сохранены неизменными. Их нельзя выдавать за контроли новой модели. ROI, maker/taker notional и fees, asset fills/cash bridges, hashes и exact параметры — comparison.json/csv и native acceptance receipts.

## Почему явный SOL cap изменил экономику

96из98E4SOL_ADD исторически исполнились1000SOL с CANCELED остатком; заявка24.07.2026 хотела395673.9SOL. Число1000 происходит из synthetic BBO helper, а не из лимита биржи. Переход к явному child1000 сохраняет nativeFILLED, исходное право и дневную частоту, но уменьшает размер, проверяемый допуском.

Первое реальное расхождение23.12.2024,16:47UTC: старая уже предусмотренная SOL_ADD получила локальный `PRE_SUBMIT_INCREASE_GATE_OR_MINIMUM`; cappedchild был допущен и дал ещё1000SOL@183.81 с комиссией101.0955. Nativeheld стал2000вместо1000. Старый точный подкомпонент отказа/level отсутствует в архиве и остаётсяUNKNOWN; связь с уровнем выводится из source batch, не из неизвестного UUID-поля. Изменение callbackclock само по себе не доказано причиной. Тест с настоящими native callbacks подтвердил исходный двухуровневыйbatch, ровно2attempts/D1 и genuine unused-right retry только в следующийD1.

Экономическая эквивалентность старому E4 **опровергнута**. Поэтому выполнен обязательный новый S0 в тех же условиях; сравнение H_SOL/H_BTC ведётся с новым S0/E4. Меньшие margin requests — изменение execution/admission, не доказанный новый прогнозный сигнал. Никакой фиктивныйCANCELED не вводился.

## H_SOL: что сработало и почему итог хуже

Frozenrule:55%globalH floor, closedWilderATR14, conservativeBTCreserve; каждый новыйADD, maximal native lot в исходном праве/child1000. Без DD35trigger, forcedtrim, stop и autorestore. Уникальные pending/leaves/unfinishedparent reservations и ещё не списанные entryfees учитываются один раз. Формула и units: stage3-hypotheses-freeze.json / owner-final-SC03-SC04-CONTRACT.md.

102реальных budget decisions,0UNKNOWN;5частичных ограничений и17запретовADD. Все102уникальны по level/D1;22оригинальныхchild нарушили бы фиксированный budget. Это722проверки механизмаPASS. В16случаях held inventory уже выходила за warning budget; ADD-only это по определению не исправляет.

Октябрьский localDD снизился57.5854→18.7753%, но январский вырос42.5023→65.6948%. На13.01.2025 peak:

| Native состояние | E4 explicit | H_SOL |
|---|---:|---:|
| Equity |210575.706477|109846.69194005|
| SOL held |4000|3225.2|
| Equity trough |121076.100205|37683.15940294|
| Потеря equity |89499.606272|72163.53253711|

BTCflat в обоих случаях. Абсолютная потеря уменьшилась, но капитал сократился примерно вдвое, аSOLinventory — лишь19.37%; относительная концентрация риска выросла. Новый native recovery17января вместо14января у explicitE4. ОдинATR на моментADD не гарантирует предел всей последующей просадки.

TOTAL упал относительно explicitE4 на2058067.94762508. Фактическая декомпозиция: BTCfillnet−1792607.958662300187162; SOLfillnet−269399.46679480; нераспределённый cashbridge+3939.477832020187162. Это полные native траектории; компонентные fills не являются независимыми BTC-only/SOL-only контрфактическими стратегиями. Данные не поддерживают тезис «достаточно убрать отдельные плохие SOL-сделки».

## H_BTC: что произошло

Один actual-filledparent — одно наблюдение; первый/повторный внутри actualEMAwave, стороны объединены. Labelanchor — firstactualnativefill, торговый managementPLANREF не изменён. ClosedATR/q0 заморожен до fill; метки — последовательный minuteMARK после входа до closedD1EMA-switch. Только ready_at<decision; минимум8валидных каждой группы, DecimallinearQ90. k применяется один раз к уже ограниченному notional до zeroTP/lot; нет компенсации SOL/плечом/частотой.

83parents,33repeat,81completed/2censored;24eligible decisions,19k<1, minimumk≈0.66055566. 1155проверок actualmechanismPASS. Первый допуск8/8 —04.03.2025, первый k<1 —25.05.2025. Поэтому октябрьская просадка не затронута. Более высокий потенциальный MAE оставшейся волны не доказывает, что уменьшение именно этого входа сохранит прибыль.

TOTAL потерял670301.58537257 против explicitE4: BTCfillnet−664308.668342181227482, SOLfillnet delta0, нераспределённый cashbridge−5992.917030388772518. SOLfillcashflow не изменился: прежний абсолютный childtempo продолжал ограничивать его исполнение. Снижение BTC не дало отдельного положительногоSOLэффекта. Это причинный, исполнимый фильтр с отрицательным экономическим результатом, не утечка будущего и не поломка денежного учёта.

## Почему нет комбинации и повторного прогона

По actualH_SOL и actualH_BTC hooks все19q0решений до январской trough имеют k=1, максимум completedgroups10/7. Включение H_BTC меняет только originalnotional→originalnotional*k. По причинной индукции комбинация повторяет уже рассчитанный H_SOL prefix до13.01.2025, сохраняя globalDD≥65.6947708325%. Поздняя прибыль не стирает исторический global maximum DD. Это независимо перепроверено по immutablesource; комбинированныйTOTAL не вычислялся и не заявляется.

COMBINED — NOT_RUN_ACTUAL_PREFIX_FUTILITY. FRESH_REPEAT — NOT_RUN_NO_PASSING_CANDIDATE. Использовано4из6физических попыток, всеexit0;2слота закрыты неизрасходованными. Перебора новых коэффициентов и существенных policycorrections не было.

## Проверки, артефакты и пределы выводов

- Source8f2f780; владелец142relevant checks, финальные42focusednative tests, независимые42PASS; SC01matrix/clock/nativeJSON и precision606 включены. DefaultOFF все исследовательские флаги.
- По60независимых native/account checks для каждого из4прогонов. Полный глобальныйsettledDD/1051199receipts, feesmaker+taker, fills, zero terminal lots/orders, freshfundingjournal и pinnedsource/data/config.28фиксированныхокон и96месяцев в episode-attribution.csv/monthly-attribution.csv.
- Реестр43правил и28offlinecausal checks. По2407проверок полной независимой groundtruth для H_SOL/H_BTC PASS; literalnativeq0dataset в data-native-causal-H_SOL/H_BTC.csv/json. Включены firstMARKtouch уровней ±1frozenATR и отдельные D1-close MAE/MFE diagnostics, не используемые в Q90: complete/censored labels отдельно, MFEаналитический, неэкспортированное nativeMFE не выдумано. Полный internalgatevector не экспортируется; gatewitness честно `PASSED_TO_Q0_NOT_FULL_INTERNAL_GATE_VECTOR`.
- Shortdepth500/1000/2000fixtures — локальная проверка исполнения. Высокая глубина не была полным portfolio stress; benchmark synthetic1mCLOSE, не intraminute/liveDDгарантия, historicalmarginapplicability UNKNOWN. Signedperassetfunding UNKNOWN; нераспределённый bridge не называется funding.
- История многократно исследована; ни текущие сравнения, ни возможный freshrepeat не являются новымOOS. Старые отрицательные исследования сохранены и не пересчитаны.

Полезные инженерные результаты сохраняются отдельно от отрицательных торговых политик: явное исполнение/наблюдаемость/causalparentdataset и tests. H_SOL и H_BTC **не рекомендуются к включению** по результату этого пакета. Решение50/90 не найдено, live/deployment разрешение этим исследованием не создаётся.
