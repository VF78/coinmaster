# CoinMaster: отчёты 25 исследовательских попыток

Опубликовано по прямому поручению владельца 31.10.2026. Архив включает 10 execution-parity попыток и первые15 факторных попыток, **включая неудачные и короткие инженерные проверки**. Это не25 успешных полных торговых бэктестов. Дополнительный одобренный Q0/L1 этап идёт отдельно и пока не имеет результата в этом архиве.

## Где читать

- [Execution-parity: результаты](EXECUTION_PARITY_RESULTS_RU.md) и [сводка исходного протокола](execution-parity-summary.json).
- [Факторная оптимизация: все15 результатов и выводы](FACTORIAL_RESULTS_RU.md).
- [Единый учёт25 попыток](attempts.json): исходные статусы, ошибки, source/report hashes.
- [15 финансовых отчётов](native-reports): месяцы, nativefills, позиции/PnL, cash bridges, комиссии/funding и обеDD. Это явно отмеченный subset исходных отчётов, не полные многогигабайтные traces.
- [Восстановление последней попытки](final-attempt-recovery-receipt.json): originalTECHFAIL остаётся, отдельныйreport-onlyengine0/11checksPASS.
- [Прямой PnL и различия траекторий](ACTUAL_PATH_ATTRIBUTION_RU.md), [первая причинная граница](first-policy-divergence.json), [следующий протокол](CAUSAL_BOUNDARY_AND_NEXT_PROTOCOL_RU.md).
- [Подробные669 SOL-records прежнего сравнительного этапа](execution-parity-sol-evidence.json).

## Итог и границы доказательства

Нового целевого победителя нет. A10 с реальными BTC TP1/2/3 дал5 762 437,77290470USDC при DD58,350002%; последний диагностический вариант —55 680,99453701USDC/DD55,092789%. Требование текущего исследования: TOTAL≥5 635 720,92USDC, обеDD≤50%, настоящий SOL-хедж текущего BTC; оно не выполнено.

Экономические результаты здесь относятся к Native Nautilus1.231.0, исходному Bybit-reference UTC[2024-09-01,2026-09-01), simulatedseed10000USDC/reserve0, текущему HL execution profile, maker0,0144%/taker0,0432%(referral уже включён), causal funding и explicitzero-impact diagnostic. Bybit-сигналы не превращаются в Hyperliquid-историю. Сохранены labels NOT_FAITHFUL_DIAGNOSTIC/ranking_eligible=false; реальные intraminuteL2/проскальзывание/будущиеvenuefills не доказаны. Это модельные результаты, не гарантия liveROI. ResearchDPoff/DDstopNone — параметры исследования, не указание выключать liveDP.

Комиссии уже включены в native realizedPnL и повторно не вычитаются. Cash drawdown в summary не подменяет settled/coherentDD. Два денежных пути нельзя складывать в counterfactualTOTAL или выдавать за изолированный эффект одного ограничения.

Публикуются исследовательские10K-суммы. Финансовые readbacks реального счёта, его адреса/баланс, ключи/пароли, инфраструктура и приватная история Git исключены. Исходные локальные пути заменены маркерами; полные сырые traces сохраняются приватно, hashes приведены для проверки. Private source hashes — идентичность эксперимента, а не обещание наличия соответствующего кода в этой ветке.

Эта публикация не меняет код стратегии, production, аккаунт или GUI и не запускает live.
