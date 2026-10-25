# A0: исходная allocation и clock+60s

Исходные results/details не изменены; hashes зафиксированы в JSON. Engine/product/download0.

| Case | First allocation / terminal filled | Original S0 / second filled ever | RiskOFF+60 quote | Original post-only noncrossing | Held same parent / no ordinary BTC exit |
|---|---|---|---|---|---|
| Sep14 | .487 / .487 | .488 / 0 | bid=ask59638.9 | FAIL: BUY60207.5 crosses | YES / YES |
| Oct10 | .574 / .574 | .575 / 0 | bid=ask60799.3 | PASS: SELL60959.8 | YES / YES |
| Oct12 | .440 / .440 | .440 / 0 | bid=ask63139.0 | PASS: BUY62413.6 | YES / YES |
| Nov16 | .375 / .375 | .375 / 0 | bid=ask91297.6 | PASS: BUY90744.4 | YES / YES |

В этих4 первый child исполнен полностью. Effective `market_redesign.py:155` разрешает второму child только **S0=originalquantity−originalfirstquantity**. Общий Q0−F_ever недостаточен при partial первом: отменённый first residual никогда не увеличивает S0. Guard: `Srem=S0−second_filled_ever`; `Qeff=first_terminal_actual_filled+S0`; `allowable_add≤max(0,min(Srem,Qeff−D−B))`. Actual D не возвращается.

На +60s все original ENTRY orders terminal known, обычных BTC TP/exit ещё не было, тот же parent ещё держит BTC. Количественные caps .488/.575/.440/.375. Полные source поля, exact timestamps/quotes и first-terminal audit находятся в JSON; reproducible extraction — `extract_a0_cap_clock.py`.

Oct10/Oct12/Nov16 проходят только clock/структурную/post-only-quote предпосылки. Sep14 не проходит quote; deny/wait, без taker conversion. Native margin на +60s UNKNOWN: captured account из предыдущего шага относится к riskOFF, а gate не переигрывался. Это не native admission и не разрешение повторной заявки в текущем permanently closed коде.
