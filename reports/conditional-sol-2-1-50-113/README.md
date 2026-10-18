# Условный SOL-хедж 2% / 1% / 50% — итог

**Вариант хуже контроля по TOTAL и минутной просадке. Эксперимент завершён; в пилот не переносится.**

Статус ACCEPTED_COMPARISON_WITH_EXECUTION_EFFECTS; экономическая цель FAIL. Source d83e8faccdeeba26f1f4b454fdc07074f4213271. Отдельный fresh native Nautilus1.231 BacktestEngine и funding journal; фактический journal подтверждает успешное завершение. Нового optimizer и control-run не было; ранее проверенный контроль с независимым repeat переиспользован.

Период **[2024-09-01, 2026-09-01)**, старт **10000 USDT**, reserve=0, deposit protection OFF в обоих вариантах. Одинаковые реальные Bybit execution/mark1m, funding/margin/execution/cap30m. Базовые maker0.020% / taker0.055%, без VIP.

| Метрика | Контроль BTC winner + original SOL | + условный SOL2/1/50 |
|---|---:|---:|
| ACTIVE, USDT | 6 077 107.24 | 3 007 648.74 |
| RESERVE, USDT | 0.00 | 0.00 |
| TOTAL, USDT | 6 077 107.24 | 3 007 648.74 |
| ROI, % | 60 671.07 | 29 976.49 |
| Native minute max DD, % | 66.32 | 67.69 |
| Conditional OHLC bound, % | 67.55 | 68.87 |
| Minimum native equity, USDT | 4 530.57 | 4 254.11 |
| Liquidations | 0 | 0 |
| Fills | 621 | 3 274 |
| Maker notional, USDT | 769 383 840.63 | 547 130 115.62 |
| Taker notional, USDT | 1 440 092 671.80 | 1 337 137 507.65 |
| Maker fees, USDT | 153 876.77 | 109 426.02 |
| Taker fees, USDT | 792 050.97 | 735 425.63 |
| Total native fees, USDT | 945 927.74 | 844 851.65 |

**TOTAL ниже на3069458.49453046 USDT (−50.5085458%); минутный DD хуже на1.37561064 п.п. Цель DD до50% не достигнута.** Контроль6077107.23887483 остаётся лучшим из двух по конечному TOTAL.

Signed funding attribution **UNKNOWN**, не ноль: проверены журналы1320/1414rows, но audit post-total не доказывает отдельную подписанную funding-сумму. Cash residual не назван funding.

## Алгоритм и сохранение исходной стратегии

- BTC long5.5× / short7.875×, split50/50 с .25% second-entry limit /4h, PLANREF первого фактического leg и positive-TP native IOC; EMA/z/wave/TP-доли не менялись. Полная точная конфигурация сохранена в resolved JSON.
- Arm при BTC adverse строго>2% от actual blended native entry VWAP; новое закрытое SOL15m ИЛИ1h подтверждение: long close выше предыдущего high / short close ниже предыдущего low. Вход по следующей реальной свежей SOL quote с повторной проверкой adverse/position/beta/margin.
- Frozen causal720 completed-hour beta; защитный размер50% actual remaining BTC factor exposure /beta. Размер фиксируется при activation, обновляется на actual BTC quantity change; price-only ребалансировки нет.
- Один native NETTING SOL executor/account/journal. Aggregate target MAX(original authorized remaining, protectiveQc), не SUM. OFF при adverse<=1%; BTC-flat снимает толькоQc. Original SOL сохраняет права, sizing intent, clock, lawful late adds и exits. REGIME/TRAIL/CLOSE_ALL/DP имеют приоритет.
- Known terminal original IOC завершает только свою попытку; unfilled authorization не добирается следующими котировками. Unknown ACK не считается отказом; старый terminal не снимает новую authorization. Реальные fills/credit/clock не переигрываются. Transfer/release ownership не является native fill, cash или PnL.

**105/105 календарных BTC-сигналов и направления сохранены; missing/extra=0; все105 accepted-parent quantities conserved.** У97эпизодов absolute quantities иные из-за другой equity/компаундинга, multipliers неизменны.

У101из105 совпали q0/q1/firstquote/P0. **2026-05-18, 2026-07-31, 2026-08-01, 2026-08-06** реальные входы задержались ровно на120сек: штатный общий lifecycle ожидал native flattening увеличенного SOL-объёма. Это execution effect хеджа; идентичность всех105 fill timestamps/P0 не заявляется. См. native-denial-entry-delay-evidence.json.

В полном прогоне8native DENIED на4timestamp сохранили residual и завершили закрытие на следующей свежей SOL quote. Все3373orders терминальны, nativepositions0. Отказы не скрыты и не считаются fills.

## Диагностика результата

| Фактические SOL fills | Контроль | Хедж |
|---|---:|---:|
| Fills | 205.00 | 2 857.00 |
| Gross fill PnL, USDT | 696 921.99 | 334 786.67 |
| Fees, USDT | 18 260.78 | 145 041.97 |
| Net fill PnL ex-funding, USDT | 678 661.21 | 189 744.71 |

Хедж активировался56раз. SOL-fees выросли на126781.18750550 USDT, gross SOL fill PnL снизился на362135.314; combined net SOL fill-диагностика ухудшилась на488916.50150550. BTC net fill-диагностика снизилась с5345694.48879580 до2759268.86338612 на изменённой equity/compounding траектории и с четырьмя execution delays.

Это диагностическая агрегация реальных native fills, не отдельный native cash ledger и не изолированный PnL protective bucket. Весь TOTAL delta нельзя отнести только к комиссии/только к защитным сделкам: inventory общее, капитал и quantity меняются. Native account TOTAL остаётся источником экономики.

Entry-adverse2% и factor-cover50% не ограничивают portfolio DD от исторического максимума; это не trailing защита накопленной прибыли. Native minute DD фактически превышает50%.

## Минутные TOP3

Native cash + unrealized PnL по минутным marks, не дневная свеча и не только закрытые сделки. Даты UTC.

| Вариант | DD | Peak UTC / equity | Trough UTC / equity | Recovery UTC |
|---|---:|---|---|---|
| Control | 66.32% | 2024-09-11 14:00 / 13 451.34 | 2024-10-03 15:44 / 4 530.57 | 2024-10-11 02:53 |
| Control | 59.84% | 2025-04-11 01:00 / 915 175.73 | 2025-06-06 15:17 / 367 509.65 | 2025-08-24 19:38 |
| Control | 55.10% | 2025-10-22 21:29 / 2 088 471.56 | 2025-11-28 14:28 / 937 712.13 | 2025-12-01 04:10 |
| Hedge2/1/50 | 67.69% | 2024-09-11 14:00 / 13 168.32 | 2024-10-03 15:44 / 4 254.11 | 2024-10-11 06:36 |
| Hedge2/1/50 | 57.37% | 2026-07-06 13:39 / 6 377 106.69 | 2026-08-11 12:14 / 2 718 836.14 | Не восстановлена до end |
| Hedge2/1/50 | 50.66% | 2025-11-26 12:22 / 1 533 107.15 | 2025-11-30 09:20 / 756 449.41 | 2026-01-13 22:11 |

OHLC68.8733798821% — условная fixed-exposure upper-to-strictly-later-lower оценка, не фактически доказанный внутриминутный портфельный DD. Экстремумы BTC/SOL несинхронны. Детерминированная quote liquidity1000 и1m-исполнение остаются одинаковыми предположениями сравнения; L2/реальная venue fidelity и Hyperliquid ROI не доказаны.

## Проверки и воспроизводимость

- 36conditional native PASS включает6parity/race cases и1actualRiskEngine denial case (counts overlap). Два цикла OFF/ON inactive совпадают по native orders/type/TIF/actual liquidity/fees/account/clocks/budget/partial half/full. Точные diff/pins/logs — native-denial-correction-evidence.json и native-denied-type-review.*.
- conditional-sol-2-1-50-native-denial-receipt.json: actual успешный процесс/finalJSON,89frozenfiles,1051200rows каждого source, source/data/policy/result/funding hashes и nativeflat. Late systemctl0 после transient collect не является доказательством успеха.
- native-denial-final-preservation-audit.json:1428targets→1428knownterminal,82unfilled-original releases,0rebounds/0Oauto-fill до новой authorization;23последующих fills protective-only;57lawful original authorizations приBTCflat;8Denied→residual close.
- native-denial-activation-terminal-audit.json:56ACTIVATE;47OFF включают31activeOFF+16armed-onlyOFF. Остальные25activeepisodes завершены реальными forcedSOLexitfills/net0. Это не9зависшихциклов.
- native-denial-analysis-summary.json / native-denial-analysis-checks.json / native-denial-final-comparison.csv / native-denial-final-analysis-manifest.json: точные числа и hashes.
- conditional-sol-2-1-50-native-denial-resolved-parameters.json: точная конфигурация.
- Полные immutable result/orders/fills, fundingSQLite, native-minute gzip и89file snapshot — VPS job /var/lib/coinmaster-native-gui/data/runs/jobs/cm115-split-conditional-sol-2-1-50-native-denial-20261018a/. ResultSHA256 2927f1007b8c531e07042fc5b4c26c61d35a7e1da6320e98e7dbd0ce8b143f04.

## Исключённые попытки

| Source | Статус | Причина |
|---|---|---|
| 2a3f830 | REJECTED_IMPLEMENTATION_ARTIFACT | OrdinaryTP3-flat ошибочно завершал BTCepisode, лишний Sep7вход |
| 862fec1 | ABORTED_CONTRACT_VIOLATION | BTCflat ошибочно закрывал originalSOL вместоQc-only |
| 07339b7 | REJECTED_ORIGINAL_IOC_CADENCE_CHANGED | Qc0, но unfilledoriginalIOC самовольно добирался следующими минутами |
| 44f2e00 | FAILED_NO_VALID_ECONOMIC_RESULT | Preexisting typed-cache callback / synchronous nativeDenied retry |

Эти артефакты сохранены и исключены из сравнения; их результаты не названы чистым эффектом хеджа. Затем выполнен один итоговый native24m прогон того же2/1/50, без подбора параметров.

**Решение: этот вариант не переносить в пилот.** Sandbox PID2009732/NRestarts0 не изменён; deployment/реальные ордера не выполнялись. #116 — завершённый отрицательный эксперимент. #113 остаётся research-parent; #101 — отдельный genuine-HL-history/live-approval blocker.
