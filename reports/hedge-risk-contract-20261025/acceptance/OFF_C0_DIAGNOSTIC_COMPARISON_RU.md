C0 уменьшил наблюдаемый риск префикса, но сохранил только55.41477839% чистого прироста OFF и отклонён по native3TP. A0 не запускался: гипотеза восстановления исходного second-child экономически NOT_TESTED. Это диагностика фактических native результатов, а не допуск кандидата.

Одинаковое окно [2024-09-01,2025-01-15)UTC, seed10000/reserve0; все136 UTC-дней включены. Source763d985; R2 LEGACY_Q realU. OFF — финансово квалифицированный контроль; C0 — диагностический native cash результат с обязательным TPFAIL.

| Метрика | R2_OFF | R2_C0, diagnostic only |
|---|---:|---:|
| Terminal native cash, USDT | 20911.13611487 | 16046.38189782 |
| Cash−seed, USDT | 10911.13611487 | 6046.38189782 |
| Settled marked DD, % | 50.13014281 | 47.47440185 |
| Coherent event DD, % | 50.13014281 | 47.47440185 |
| Daily ES20, %;136 дней | 5.88994331 | 4.52968719 |
| Parent ES20, %; own19/19 | 18.79633396 | 14.81448801 |
| Native fees, USDT | 1072.65091609 | 1139.22895990 |
| Signed funding, USDT | -695.36036902 | -328.12354229 |
| Native fills | 82 | 125 |

C0−OFF cash=−4864.75421705USDT; terminal ratio0.7673605972, net-profit ratio0.5541477839. Fees выше на66.57804381, signed funding выше на367.23682673USDT. Это наблюдаемые разности собственных путей; разложение потери капитала на причинный BTC/SOL эффект UNKNOWN. Parent ES20 использует собственные популяции, без forced matching. OFF сам превышает DD50%; финансовая квалификация контроля не означает прохождение performance gate.

TP adjudication подтверждает9 реальных gaps по60s: **540s** отсутствия требуемых remaining targets при nativeBTCheld. Остальные56580s из raw57120s — false-positive audit: TP1/2 уже consumed, требуемый TP3 был принят. Первичный native-hold proof доказывал удержание BTC, а не отсутствие TP. Решение root по C0 остаётся REJECT; исходные отчёты, метрики и receipts не переписываются. Источник — a0-C0-three-TP-blocker-review.json и a0-financial-rejection-R2_C0.json.

В C0 непосредственно наблюдаются SOL native commissions288.55797530USDT и signed SOL funding+3.73523335USDT; BTC funding−331.85877564USDT. Прямой native SOL realizedPnL не экспортирован (`UNKNOWN_NATIVE_ACCOUNT_REPORT_ONLY`), поэтому SOL netPnL UNKNOWN. Новый fill-PnL симулятор не строился, старые SOL прибыли не переносились.

Из19 native parents у7 original second-child осталась отменённая quantity. У6 есть последующий actual riskOFF+60s clock; у4 в этом clock тот же native parent, BTCheld и ещё нет ordinary BTC TP/exit. Это только часы фактических предпосылок:

| Parent first-fill date UTC | Cancelled second BTC | RiskOFF+60s UTC | Native BTC held в clock |
|---|---:|---|---:|
| 2024-09-14 | 0.541 | 2024-09-14T12:02:00+00:00 | 0.270 |
| 2024-10-10 | 0.405 | 2024-10-10T04:20:00+00:00 | 0.404 |
| 2024-10-12 | 0.285 | 2024-10-12T21:27:00+00:00 | 0.284 |
| 2024-11-16 | 0.418 | 2024-11-16T08:05:00+00:00 | 0.418 |

Cancel ACK/order IDs и ordinary TP timestamps сохранены в companionJSON. Prospective A0 stock margin/current quote/postOnly/immutable caps/ACKrace остаются UNKNOWN; эти4 clocks не являются разрешениями или будущими fills. У2 других clocks ordinary TP уже произошёл, у1 post-cancel riskOFF clock отсутствует. Отмены — наблюдаемый механизм ограничения участия, но его причинный долларовый вклад в рост капитала не доказан.

Следующий приоритет — **TP continuity и достоверный consumed/current-generation audit**. Только затем отдельные reviewed protocol/source/budget и свежая matched OFF/C0/A0 семья на одном исправленном source, с financialPASS C0 до A0. Старый C0 не утверждённый кандидат. Текущий prefix CLOSED3/4, unused1closed; engineering7closed. Ни один новый engine/stream replay/financial model не запускался.

Префикс повторно исследуемый, не full/freshOOS и не доказательство70%/90% цели. Floors4256975.067212381/5470396.514987347 и native accounting/risk gates неизменны. Источники и SHA приведены в OFF_C0_DIAGNOSTIC_COMPARISON.json.
