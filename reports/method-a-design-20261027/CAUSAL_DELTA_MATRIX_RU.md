# Method A — причинная матрица и три фиксированных эпизода

27.10.2026. Утверждён только первый этап проектирования до2часов. Product edits0, native/matching/prefix/full/training0. Числа ниже извлечены из сохранённых доказательств; новых денежных outcomes нет.

## 1. Что именно было смешано в R1→R2

| Политика | R1 E4 BTC/SOLoff | R2 realU/LEGACY_Q/SOLoff | Предложенный P1 относительно P0 |
|---|---|---|---|
| EMA/waves/сторона/первый signal |E4|Те же83 первые timestamps/стороны|Сохранить exact E4 function и собственный капитал|
| Причинный q0/q1 sizing |Legacy selector|LEGACY_Q_CONTROL, неCLEAN_Q|Тот же selector; raw legacy levels только как sizing/eligibility metadata, без synthetic exits|
| Split discount |0.0025|0.005|0.0025 неизменно|
| Second-child deadline/chase |4h/early-positive-target/day-end legacy processing|Один limit-only, без прежнего chase|Точный старый порядок, expiry/TIF/fallback; не отменять добор только по новому правилу R2|
| TP до завершения split |Legacy unfinished split мог блокировать реальные reductions|Три actual-inventory TP уже после первого fill|Три реальные цели с первого допустимого actual fill; это объявленная TP-policy delta|
| TP1/2 geometry |Возможны zero targets|d1=d3/3,d2=2d3/3, causal d3|Использовать эту уже исполнимую U geometry как первую фиксированную TP-дельту; не выбирать новый ATR/quantile по результату|
| Profitable positive-target fallback |Legacy actual native IOC при объявленных условиях|Real-U branch его выключает|Не выключать глобально; только одно реальное исполнение остатка target, без duplicate order/кредита pendingcancel|
| SOL |OFF|OFF; realU очищает rights и запрещает oldSOL конфигурацию|P0/P1 диагностически содержат один и тот же old-overlay policy; P2/P3/P4 — другие ячейки|
| Funding/fees/capital |Actual own native|Actual own native|Тот же engine/data/cost/clock; quantities пересчитываются на собственном капитале|

R1 TOTAL304372.03 против R2 225919.51 не является отдельной стоимостью только реальных TP. Разница также включает second-entry и lifecycle. E4 oldSOL TOTAL5631617.36 против R1 304372.03 — полный policy-effect выключения SOL с эндогенным compounding, а не вычитание713702USDT standaloneSOL.

Исходники прочитаны как текст: immutable ec2a958/a50 `strategy/market_redesign.py`, `strategy/split_cover.py`, `strategy/wave_overlay.py`, `domain/wave_overlay.py`. На a50 guard `wave_overlay.py:231` требует realU+SOLoff+discount.005. `_md_prepare` меняет `episode.wave_levels`, очищает omitted/target references и SOLrights. `_md_check` и `_split_check` выбирают разные second-entry маршруты. Поэтому P1 не получается переключением существующего флага.

## 2. Точная граница минимального будущего P1

P0 — exact E4 entry/sizing/split/oldSOL policy, diagnostic-only. P1 меняет только реальную BTC TP policy и необходимые для неё учёт/исполнение; raw legacy sizing/oldSOL eligibility остаются отдельными ссылочными величинами. Это не новая виртуальная позиция и не второй OMS: позиции, деньги, fees и fill events существуют только в native.

Для actual cumulative entry quantity A каждое TP имеет накопленную положенную allocation по21.25%/21.25%/остатку в native lots. Остаток = allocation(A)−actual TP fills−необратимо retired risk quantity. Новый actual SECOND fill создаёт только свою новую allocation. Он может создать новый остаток ранее полностью исполненного уровня для **новых** лотов; уже проданные/retired лоты не возвращаются. В любой момент sum remainingTP quantity=actual heldBTC; начальные rounding и риск-retirement детерминированы, остаточный лот идёт в последний живой target. Если три initial valid allocations невозможны — failclosed tiny-partial, а не нарисованные TP.

Это обязательный case M1: partial FIRST→настоящий TP→тот же допустимый original SECOND fill→новые права только на новый fill→завершение. P1 не получает новый FIRST, новый refprice или право увеличить original parent. Старый положительный-target fallback и split early/deadline семантика описываются явно; если совместить их без дополнительной entry-policy дельты нельзя, P1 помечается BUNDLE и **STOP до economics**, а не называется TP-only.

OldSOL omitted-level eligibility в диагностическом P1 опирается на исходные raw levels, реальные entry fractions и прежний causal crossing/session guard. Real positive TP fill передаёт фактическое событие old-overlay policy; новая геометрия может эндогенно менять время его входа. Это часть TP-policy effect, не требование воспроизвести старый SOL outcome при новой BTC траектории. Ни raw metadata, ни compatibility eligibility не создают fake BTC fills/PnL. Для P3 standalone oldSOL route отключён полностью.

## 3. Эпизод A — 2 сентября: это дефект данных, не источник всей потери роста

Точка: 2024-09-02T04:00Z, old lot-safe source7d513ca, parentbb00640c-c8b4-4bb1-b822-9d7523635427. Реально heldBTC SHORT1.096; native pre-fill cash9976.41294564/equity9685.75374564; mark57721.5. Единственное missing hedge feature — SOL H4 ATR14. F0_SHORT valid; D1 beta/rho/sigmas и prior funding endpoints известны.

Old owner принудительно закрыл BTC BUY1.096@57721.3, fee34.79439964; flatTOTAL9651.178546. Это actual event, не гипотетическая потеря. Но к30сентября combined уже опережал OFF/B2, поэтому финальную потерю нельзя приписывать одному cold ATR.

Текущий отдельный warmed feed5a02a0bc содержит для той же строки ATR3.68897527822544, valid1, H4end=decision04:00, not_before04:01. Это **inclusive end=t** по сохранённой схеме; значение strict end<t3.776588… не подставляется. Реальная historical publication latency неизвестна. Новый owner должен честно учитывать ready_at и держать BTC data/clock controls неизменными. Для нового B2/F0 selection использовать модель barend+60s availability, order не ранее следующей quote после available; это отдельная timing-часть новой hedge policy, не исправление задним числом старого native результата.

Проверяемый вывод: prebenchmark completeness должна блокировать ложный missingATR при корректном feed; отсутствие readiness не означает отсутствия риска. Native replay с новым warmup/risk owner ещё не выполнен. Непрерывный peak H на точном старом predecision checkpoint и counterfactual money UNKNOWN.

## 4. Эпизод B — 12 октября: потерянный second-child

Combined parent9476ea1b-e55e-420a-9cb1-d14ae675b2b0: первыйBTC0.440@62727.3 в08:02Z; requested parent0.880. В20:00Z F0 выбрал SOL58.6, фактический short fill20:01@146.8. В21:26 риск стал INACTIVE и SOL закрылся@147.04 без TP/BTCdebt. Но0.440BTC original second quantity навсегда cancelled с reasonPAIRED_MONOTONE_PARENT_CEILING.

OFF иB2 в своих native путях позже исполнили вторую часть0.434/0.438@62413.6 13октября14:47Z. Parent endpoints14октября14:27Z: OFF11579.80→13809.66; B211678.72→13928.25; combined11741.67→12772.45. Это разные quantities/equity, поэтому разность капиталов не является отдельной причинной ценой отмены0.440.

Важная несовместимость прежнего A0 с новой TP-only задачей: эти наблюдения относятся к R2 limit-only. У exact E4 исходный second-child имеет4h deadline/fallback; при старте08:02 его nominal deadline12:02, задолго до F0 в20:00. Поэтому нельзя требовать, чтобы новый P1 или P3 обязательно восстановил октябрьский late-limit A0. Правило нового owner: временно приостанавливается только ещё действующее исходное право; после его original expiry никакого продления, нового price или «восстановления».

Фальсификатор: после known riskOFF и reconcile допускаемый **ещё действующий** original second не возвращается из-за monotone coverage cap; либо возвращается уже expired/filled/consumed право. Точный новый decision-level stress/cushion/MM здесь UNKNOWN; существующие feed beta/rho/sigma известны, но их недостаточно для решения о допуске.

## 5. Эпизод C — 25 октября: SOL TP обнуляет BTC

Combined parentb618af1c-04a8-406a-ae01-f2176d74609a: actualBTC0.881, SOLshort109@172.02 в16:01Z. SOL TP27.2@170.09,27.2@168.16,54.6@164.31 исполнились17:22,17:57,22:57Z. Старый coverage owner вслед за ними сократилBTC0.220/0.220/0.441 и в22:58 сделалBTCflat.

Собственный combined parent12772.44618285→12251.88988464 завершился25октября; OFF/B2 собственные позиции оставались до29октября14:02 и завершились16605.95022235/15995.20491341. Это прямое свидетельство потери участия, но не измеренный dollar-counterfactual удержания BTC.

Механизм нового контракта: каждый SOL TP пересчитывает actual joint stress; BTC остаётся, если фактический остаток допустим. При реальном превышении — ровно необходимое сокращение, а не cap, пропорциональный числу SOL-лотов. Фальсификатор: safeBTC приSOL0 закрывается только из-заSOL0; dangerousBTC не сокращается со ссылкой на pendinghedge. Чтобы решить, был ли именно исторический BTC0.881 допустим после каждогоTP, отсутствуют exact coherent pre/post E/H, полный opening-liability/margin snapshot и рассчитанные по prior data stress corners. Не утверждать, что новый owner обязательно оставил бы все0.881BTC.

## 6. Pins и обязательные новые измерения будущей кампании

| Артефакт | SHA256 / reference |
|---|---|
| Old capital diagnosis |73d3427eb4fd89170ae203ac99557248b726567ef98fd49f0a20faf2dc633735|
| October admission memo |0902d3650210e1ff9aed7dd610ab7d7934ae29c6a395aa15f25c440e9ce8d7f5|
| R1 expectedconfig |35eb11981b5e816aa85bf52bb8c32b3710e5fa4bc2e1f01516bbd1cc26768af5|
| R2 expectedconfig |d9ea9c51260941c58cd483ea25a5ad80b85bbdccc7754fe092ad964ed08247ea|
| Exact E4 source/config |bd04c9b3858bcda40060a08eff488849c69af5d8 / ce7c101ace5d8c21f0a912a0cd3221659591e5d56b744d3f8dc5ecb7c01d2ef6|
| Market redesign source |ec2a958e383a53133f8a8d03ef0e312810881265|
| Current immutable product |a50af5433a0bbe00aecd6fec26e8d5c0321ced80|
| Warmed feed |5a02a0bc2555404261780cb4979e398494c70194e99317d8db1020fb026b8698|

Data root: `/Users/vf/Documents/ChatGPT/Coinmaster/runtime/var/research-jobs/sol-conditional-hedge-btc-band-20261023/inputs/data`. Exact constituent hashes — прежний `market-redesign/full-freeze.json` и `hedge-risk-contract/a0-prefix-amend4-freeze-R2_OFF-approved.json`; их controls различаются, старые approvals не переносятся.

В будущей кампании каждое решение сохраняет reportSHA/row/parent/event-sequence/timestamp/phase, signed actualpositions, both marks/age, native cash+UPNL, pre-fill/pre-open H, opening leaves/oldnewgeneration liabilities, MM/IM/free, W endpoints/ready_at, Ω, funding envelope, actual-held loss, full-fill benefit, partial-fill envelope, reason/target/actualfills. У QuoteTick нет native eventUUID: process-localid(tick) не выдаётся за долговечную identity. Поля существующего97 producer и8 его records подтверждают getter capture, но не весь needed universe и не будущий marginPASS.

Закрытый UNKNOWN первого этапа: какие вмешательства надо разделить и какие конкретные состояния необходимы для опровержения нового механизма. Открытый UNKNOWN: его денежная польза/историческая safety/восстановление earlyalpha. Это предмет будущей согласованной проверки.
