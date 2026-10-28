# E4/C1: минимальная диагностика сохранённых native данных

**R не доказан как NO_ACTION_DELTA.** Замена DD35→40 одновременно в закрытом H4 и свежей котировке открывает ранее недоступные price/DD состояния в трёх из девяти фактических C1 групп. Это доказанная достижимость рыночных условий, но полная допустимость нового ордера **UNKNOWN**: сохранённый audit не пишет owner/ACK/tier/margin/ordinary-priority snapshot на отвергнутых H4. Здесь нет SKIPPED_NO_ACTION, нового исполнения, контрфактических fills, TOTAL или DD.

| Группа | Первый H4, UTC | DD H4 | H4 close / cut VWAP | Следующая котировка, UTC | Цена / DD |
|---|---|---:|---|---|---|
| 1, SOL long | 2024-10-04 08:00 | 36.462803% | 139.47 / 135.30 | 08:01 | 139.45 / 36.790141% |
| 2, SOL long | 2025-01-13 20:00 | 36.099838% | 177.53 / 175.58 | 20:01 | 177.35 / 36.695946% |
| 4, BTC short | 2025-11-27 16:00 | 38.950808% | 90908 / 91057.1 | 16:01 | 90866 / 38.942744% |

Во всех трёх строках whole H4 начинается строго после последнего действительного cut-fill и aggregate terminal; reclaim положителен в исходную сторону; DD≤40 как на H4, так и на обеих следующих котировках (+1/+2 минуты). Это ещё не доказательство `_c1_current_money`: первый H4 групп1/4 совпадает с реальным funding account mutation, и порядок account_event относительно source/closed-bar требует отдельного доказательства. Группа4 имеет ещё12 таких H4 на сохранённом пути; это альтернативные моменты проверки, не13 будущих restore и не13 независимых сделок. Даты здесь — адреса исторических доказательств, не будущие сигналы.

В группах3,5–9 нет H4 с одновременно полным post-cut интервалом, reclaim и DD в (35%,40%]. Поэтому чистая замена порога не открывает новый price/DD момент на их фактических окнах. Поля прочих gates остаются UNKNOWN там, где audit их не записал. Неисполненные условные действия не называются native eligible. После первого изменённого fill вся дальнейшая фиксированная C1 траектория перестаёт быть контрфактической политикой R.

Полнота: однопроходно прочитаны1,051,199 native settled receipts, все24 месяца; извлечены только нужные checkpoints. В `h4_restore_windows.csv` — все90 H4 от cut до первого restore/revoke включительно: по группам7/5/4/25/2/3/33/4/7. Включены первые неполные бары и совпадения с endpoint; они имеют явные blockers. Три реально сохранённых `CLOSED_4H_RECLAIM` в точности совпали по native DD и execution close с извлечением (`successful_confirmation_crosscheck.csv`). Это проверка извлечения, не новый тест стратегии.

`fresh_quote_evidence` содержит настоящий execution close и последовательный native money receipt на +1/+2 минуты. Сохранённый источник задаёт котировку на close и отдельный quote recheck после H4; он также требует актуальность source/receipt, неизменный fill_epoch, account.last_event≤source, отсутствие competing owners/pending orders и существующие native increase gates. Полный набор этих runtime gates в новых точках не экспортирован. Финальные order CSV не доказывают промежуточные ACK/queued-intent snapshots. На новых точках их не восстанавливаем предположениями.

Дополнительное source-bound закрытие: `first_candidate_ownership_funding.json` соединяет полный native orders lifetime с raw `native_order_events` (action/reason/accept_ns). Группы1/4 имеют ровно один старый ACCEPTED harmless BTC TP3 reduce-only limit; группа2 в20:01 имеет ноль native order lifetimes. В окрестности каждого первого кандидата отсутствуют fills. В первых H4 групп1/4 есть2/1 actual funding postings; в группе2 в20:00 funding postings0. Январский16:00 H4 уже имеет DD34.0876% и reclaim, но нет actual confirmation; там есть SOL funding account mutation. Поэтому его нельзя объявлять новым R event по одному price/DD и следующему DD35-crossing.

Для группы2 в20:01 native risk подтверждает held3000SOL, mark177.37, cash/free131047.75686636, markedE101467.75686636. Actual credit1000SOL даёт prospective4000SOL/notional709480. Source policy IM=max(.0182,1/20)=.05, MM=.0091 с deduction1670: conservative entire prospective IM+MM40260.268 < actual free131047.75686636 даже без reserved-credit; gross709480 <50×actualE. Это прямое арифметическое доказательство численных неравенств существующего admission guard на сохранённом состоянии, не новый PnL engine. Остаются непрямо наблюдаемые `_queued_intents`/runtime enable/owner flags и их source invariants; нулевое число native orders само по себе не подменяет их snapshot.

## Фактические деньги и ранний капитал

`e4_c1_decisions.csv` содержит все9 групп, held/requested/actual native lots и step, действительные cut/restore VWAP/fees, actual cash/E/globalH/source/receipt, terminal, revoke и знаки последующего unit path. Январь: requested2000SOL, actual1000SOL, то есть25% от held4000; credit только1000. Один запрос60% при прежней quote capacity1000 не доказывает дополнительный fill. Это отдельная гипотеза completion, не исправление отчётности и не R.

Суммарно9cuts/3restores/6revocations; native intervention fees30498.04072762. Три actual cut/restore gaps ex fees: −2415, −8970, −374311.0245; всего−385696.0245. Эти измеренные парные cashflow не являются потерей контрфактического TOTAL и не складываются с другими атрибуциями в обещанную прибыль.

Нормировка именно на native E перед cut (не на будущий terminal): actual pair gap cost / E =28.018565% /9.341319% /32.907652% для групп1/2/4; соответствующие actual cut+restore fees / E =0.878765% /0.206271% /0.662848%. Большой номинальный ноябрьский gap не отменяет значимости раннего капитала: первый маленький SOL gap равен28% тогдашней E. Это масштаб затрат, а не причинное разложение последующего sizing/компаундинга.

## G global35 latch

Сохранённый августовский максимум E5491398.68607077 ниже0.65×globalH=5533283.1187691655 при globalH8512743.25964487. Поэтому на сохранённом C1 пути DD35 rearm в августе отсутствует: latch сохраняет первую августовскую claim5 и подавляет6–9. Их later signed unit paths: −306.4,−302.3,+1000.8,+697.4; два adverse и два recovery. Все пять claim cushions положительны. Это не доказательство экономического выигрыша suppression; в изменённом пути капитал/количества/право/последующая допустимость изменяются. Состояние latch не должно сбрасываться по parent/group/month.

## Идентичность и ограничения

E4 — legacy BTC с прежним SOL alpha, source bd04c9b3858bcda40060a08eff488849c69af5d8, config ce7c101ace5d8c21f0a912a0cd3221659591e5d56b744d3f8dc5ecb7c01d2ef6. C1 уже содержит этот E4 плюс residual overlay: final source78cb85aca1cf5c2e4455f5c5ddf02851cfb40076; config405ab01b74eb459117dcbb340bc56ace4a1e6edc64290cb049d63695cae772b6. Сохранённые config: SOL overlay enabled; beta270/relative65/z180, H multipliers1.75/2.625/3.5; BTC TP fractions.2125/.2125/.575; wait4h=True, persist/zero_retrace/sol_dominant=False. Source `_c1_init` явно проверяет `C1_REQUIRES_CLEAN_E4`, native entrypoint дополнительно `C1_REQUIRES_CLEAN_E4_SETTLED_OBSERVER`. Method A/CODE0, новые TP или true hedge сюда не смешаны.

Data7ab5ae2cdaa14885da28d188c7ad14dfc8168ee600b78535f7317409ea94e9cc; policyc9540fbef259039c95829a774ef54e0eea2dcf2b6748d6455e171bf28e889834. BASE Bybit maker.0002/taker.00055, фактическая liquidity classification. Точные sha256 реально прочитанных входов — `input_hashes.json`.

E4 native TOTAL5631617.35953723/settledDD57.58541045962226379114466259%; C1TOTAL4388613.38225343/settledDD51.80315157406654834417870238%. Рабочий profit floor5470396.514987347, исходная цель около E4; не снижены до C1. Сравнение с C1 ceiling51.80315157406654834417870238% отдельно от строгого50%. Ни один старый результат не проходит50%.

Есть phased minute-close risk stream (pre_quote/post_btc_quote/post_quote), а не доказанный coherent fill-by-fill pre-fill/pre-open event equity stream. Полнота нового event-level DD контракта **UNKNOWN**; OHLC adverse/favorable bounds не являются реальным порядком событий и не заменяют его. Funding SQLite содержит rate/settlement_mark/account_total_after, но не actual signed cash delta. Signed per-asset funding **UNKNOWN**; bridge53801.142665296518712 не funding. Никакого нулевого funding или guessed epsilon не подставлено.

Native runs0; matching/PnL engines0; tests0; продукт/настройки/pilot/production0. Это read-only extraction существующих native артефактов и write-only новых evidence-файлов. Исторические C1 попытки и отрицательные результаты сохранены.
