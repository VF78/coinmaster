# SOL protection cancel paths — source8a, read-only

E2 обнаружил обычный **SOL_CAP blanket cancel**: BTC TP fill снижает cap, но SOL inventory ещё остаётся; старый путь отменяет все TP/STOP перед cap IOC. Exact observer правильно не выдал PASS. PendingCancel ещё не доказывает нулевое live-book покрытие; реальная отмена в полёте и отсутствие квалифицированной standing-защиты доказаны.

| Путь | Класс / API / barrier | Сохраняются оставшиеся OID |
|---|---|---|
| paired157–161 | Общий sink public cancel_order, фильтрация registry у caller; ACK через fixed cancel latency | По caller |
| paired201/526/536 | BTC work или ENTRY timeout, не SOL TP/STOP | Да |
| paired428 | actual BTCflat, close_sol установлен до cancel ENTRY/TP/STOP | Нет, terminal drain |
| paired451 | legacy signature cancel/rearm; standing-флаг исключает этот dispatch | В C0/A0 недостижим |
| paired501 | actual higher-close/lockout; close_sol до cancel all pair work | Нет, terminal drain |
| paired542–545 | **normal SOL_CAP смешан с terminal SOL_CLOSE**, cancel all protection и запрет IOC пока любое SOL work живо | **Нет; E2 actual failure** |
| paired630 | actual SOLflat, cancel оставшейся защиты, ownership до ACK | Terminal drain |
| paired669 | живой TP исчезает из desired при обнулении права после proportional cap fill | **Нет; отдельный normal edge** |
| wave2176 | legacy mandatory SOL timeout: cancels all SOL; текущий SOL-overlay OFF не генерирует intent | Family excluded; closure sync не доказан |
| wave2229 | global actual group close/regime/trail/liquidation/terminal: forced reason уже задан, pair.close_sol только на следующем quote | Нет; observer-priority sync требует явного решения |
| wave599/889/899/911/2725/2729/2733 | opener-only либо отключённые H1/V3/split-ATR paths | Не отменяют paired protection в exact family |
| stock native | IOC terminal remainder; zero-leaves update auto-cancel; contingent/indexed-position auto-sync | Только реальная native история; никакого synthetic sync |

`_pair_release_if_terminal` сохраняет пару до actual positions0, pair work0, native open/inflight0, pending protection commands0 и BTC flat-drain barrier0. Он сам не отменяет ордера. Ранний refund/удаление owner registry не предлагаются.

## Минимальный следующий контракт — только предложение

Для **nonterminal SOL_CAP** отменять и дожидаться только owned ENTRY, сохранять TP/STOP с положительными правами. Вместо нынешнего `not _pair_work(SOL)` отдельно сериализовать ENTRY/CAP/CLOSE и pending protection команды. Отправлять один существующий public reduce-only market IOC на обычном causal SOL quote, qty из actual inventory и неизменного solmax. Не менять caps, u/v, marketable/debt guards, TIF, clocks или native matching.

После **каждого actual cap fill**, включая full-fill terminal callback, применять существующие proportional tp_lots/caps/debt правила и немедленно reconcile: TP total=actual filled+desired leaves; STOP total=actual held. Текущий `_pair_terminal` вызывает protection только для TP/STOP, поэтому одного удаления blanket cancel недостаточно. Только latest actual Updated даёт ACK; pending/unknown/reject не считаются защитой. Partial cap IOC terminal cancel оставляет actual protected inventory и residual excess для следующего обычного quote; reject/deny/expiry остаётся fault/NO_GO. Поздние fills принадлежат исходному parent и меняют только actual inventory/debt.

**Отдельное решение для нулевого TP права обязательно.** При уменьшении remaining lots первые proportional уровни могут округлиться в0, хотя SOL ещё held. Нынешний paired669 отправит cancel2s, а strict observer не принимает лишний pending TP. Stock `update_order` (engine8250) после quantity update с zero leaves генерирует native cancel; public `modify_order(quantity=filled)` — source-grounded кандидат, но end-to-end native route **не проверен**. Exact research instruments имеют min_quantity=None; risk engine всё равно валидирует quantity. При invalid/min-size/in-market/reject или невозможности terminal ACK до следующего input — **STOP**, не grace и не ослабление observer. Не утверждается, что атомарный API существует.

Native engine1892–1930 осушает queued zero-latency commands/callbacks до quiescence перед следующим input. Это source evidence для возможной последовательности ACK, а не native PASS; partial/zero-right/reentrant события и triggered STOP остаются обязательными actual gates. Любой STOP fill уже включает closing barrier; partial STOP — только expected-negative engineering и economic NO_GO. Positive TP OIDs сохраняются; consumed/zero terminal OID не воскрешаются.

Actual riskOFF/expiry, BTCflat/SOLflat и faults — terminal closure. Generic forced reason устанавливается до global cancel, но pair.close_sol синхронизируется позже; требуется явное согласование **реального** closing intent перед cancel. Нельзя объявить обычный cap reduction closing лишь для обхода strict coverage.

## Полнота и reuse E7

E2/E4/E5 имеют общий P1: ordinary BTC TP143 вызывает SOL_CAP; actual E2 остановился до IOC и P2. E2 P2 pending TP fill/partial STOP/native recovery не достигнуты. Partial/rejected/zero-right cap lifecycle существующими этапами ещё не доказан. E3 — fixed TRIM, SOL route OFF; он не заменяет SOL proof. Новый E5 обязан проверить интеграцию нового source.

Actual E7/source8a: ENTRY1, TP3, STOP1, BTC_DEBT3; SOL_CAP/SOL_CLOSE submit0, ordinary BTC TP fill0. Все recorded CACHE_POSITION имели SOL<=solmax. Поэтому reuse **возможен лишь условно как старый component artifact**, если будущий diff меняет исключительно непосещённые nonterminal cap/его callbacks/zero-right ветки и доказывает неизменность всех посещённых E7 путей, fixture/config/feed/advance, originalSTOP ACK/fullfill и flat drain. Если затронут generic ACK/protection/closing путь, посещённый E7, или noninterference не доказана — нужен fresh E1. Старый E7 не становится PASS нового source автоматически.

При допущенном component reuse остаются E2–E5; без доказанного reuse — E1–E5. Лимит сейчас7, spent4, remaining3 HARD STOP, prefix0/4. **Рекомендации увеличить бюджет нет.** Самое дешёвое следующее решение — полный контракт cap/zero-entitlement/global closure priority и его independent source review; если public API не обеспечивает exact next-input правило, остановиться.

Все исходные/raw evidence сохранены. Product edits/tests/native/ledger edits/budget changes:0. Машиночитаемые source pins, callsite ownership/barriers и actual E7 branch-exclusion facts — в JSON рядом.
