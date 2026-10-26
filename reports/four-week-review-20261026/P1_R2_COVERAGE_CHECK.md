# P1b: ограниченная проверка сохранённого R2 C0

26.10.2026. **Проверка завершена. Частичный перенос структурных наблюдений R3→R2 подтверждён; число допустимых G1/A0 release-возможностей R2 остаётся UNKNOWN. Экономика A0 — HOLD/NO_GO, не новый запрос бюджета.** Продолжать этот обзор массовым чтением streams не требуется.

Прочитан конкретный сохранённый `R2_C0.json`, 1498186 bytes, source763d985617abd7a7afef5eec13912303983d8837, attempt `fe2ffed5-6f7d-4e51-bb83-9b7f93ba227c`. SHA256 `46a4256e7a3710cb4105c8cc5848c6c71b202e4c4aea05b99b4e1d33a3d4a3fb` совпал с process receipt; actual worker OS0. Его TP FAIL и root rejection остаются в силе. Выполнено только чтение схемы/малых decision arrays, selected freeze/kwargs/receipt fields, bounded source proof и заголовка orders CSV. PnL не рассчитывался; coherent stream588024 sequences/195839 settled receipts не читался.

## Какие данные действительно есть

| Exact artifact key | Количество / поля | Что доказывает |
|---|---|---|
| `paired_prefix_audit.events` | 415 rows:16 `ACTIVATION_SELECTED`,15 `RISK_INVALID_OR_EXPIRED`,9 `ACTUAL_BTC_DEBT_OPEN`; также sparse submits/fills/cache/ACK/flat | Actual R2 события существуют; старые16 R3 не просто предположены. Activation содержит parent, branch, qref, boundary; riskOFF row содержит только event/timestamp_ns/btc_close. |
| `market_redesign_audit.events` | 460 rows:19 PLAN,19 P0 freezes,19 SECOND_TERMINAL,113 TARGET_ACCEPTED и protection/close events | Есть статические планы, terminal cancellation и TP события, но не единый snapshot проверки release. |
| `split_cover_audit.parents` | 19 rows:quantity,first_quantity,first_filled,filled,cancelled,closed,stop_reason, P0/start и другие terminal fields | Original allocation и окончательный результат split. Final cancelled quantity не равна автоматически праву на causal riskOFF+60. |
| `entry_sizing_audit` | 19 rows, в том числе q0_ns/q1_ns/q1_bid/q1_ask, admitted quantity | Котировка исходного входа, не котировка будущего G1 release. |
| `market_redesign_audit.a0_rights` | `[]` | Ветка формирования A0 rights отключена. Нельзя прочитать как «прав нет». |
| `market_redesign_audit.a0_release_audit` | grants/submits/accepted/denials/native_release_fills пусты; actual_releases0; native_fill_coverage_complete=true | Нулевые действия отключённой ветки. Coverage boolean здесь пустой проверяемый набор, не доказательство полного G1 opportunity coverage. |
| `pre_submit_tier_margin_gate_blocks` | `[]` | Нет записанных блокировок реально проверенных increases; hypothetical A0 margin gate не исполнялся, поэтому это не PASS для restored child. |
| `execution_artifacts` | Declared orders286/fills125, точные пути/SHA в report; CSV header содержит price/postOnly/status/ts_last | Final order metadata может уточнять конкретный terminal, но не заменяет полный joint pending/margin/TP snapshot в момент решения. В этой проверке CSV строки не сканировались. |

Все15 actual riskOFF timestamps сохранены в JSON. В частности: Sep14 12:01, Oct10 04:19, Oct12 21:26, Nov16 08:04 UTC. Сам riskOFF row не содержит parent; он не объявлен полностью сопоставленной G1 проверкой.

## Четыре старые календарные точки существуют и в actual R2

Это **соответствия календаря прежних potentials**, не четыре признанных допустимых R2 trades. Выбраны activation parent IDs и непосредственно их terminal split records; ни будущие fills, ни капитал не подставлялись.

| Activation UTC | Actual R2 original quantity / first allocation | Actual R2 second cancelled | Старый R3 second potential |
|---|---:|---:|---:|
| Sep14 04:00 | 1.081 / .540 | .541 | .488 |
| Oct10 04:00 | .809 / .404 | .405 | .575 |
| Oct12 20:00 | .569 / .284 | .285 | .440 |
| Nov16 08:00 | .836 / .418 | .418 | .375 |

Для этих четырёх R2 parent stop_reason=`PAIRED_MONOTONE_PARENT_CEILING`, closed=true; SECOND_TERMINAL cancellation timestamp совпадает с соответствующим activation. Это сужает прежний transfer gap: структурное permanent-cancel явление присутствует в actual R2, но числа R3 и его quote/margin admission нельзя переносить. Дополнительные admissible/fillable rights R2 не подсчитаны.

## Почему C0 OFF audit не является dormant G1 evaluator

Approved kwargs: `research_a0_family="R2_A0_V1"`, `research_a0_original_second=false`, `research_btc_q_mode="LEGACY_Q_CONTROL"`, `research_btc_real_u=true`, `research_paired_policy=true`, `research_paired_prefix="B2_F0"`. Наличие family не включает release.

В frozen763 `a0_rights.py`: `_a0_enabled()` читает flag; `_a0_lock` lines58–60 и `_a0_check`111–113 сразу возвращаются при false. Поэтому не создаются `m["a0"]`, его `off_ns`, snapshots/denial counts и stock margin checks hypothetical release. `_md_report` в market_redesign.py337–355 сериализует только уже созданные rights и actual A0 events. Frozen7f файл `a0_rights.py` byte-identical: SHA256 `ed7b688cf4eac1ab1cd3427c42ccaa7d2bf5fcfdd4850c300feef3d8b26ca243`; это подтверждает тот же gating, **не существование новой экономики R2 на7f**.

## Конкретные недостающие поля

| Нужный causal state | Что отсутствует в проверенном пакете |
|---|---|
| Original child right на release clock | second-filled-ever по всем поколениям, ordinary TP/dead-right status и original second budget в одном snapshot; final filled/cancelled недостаточно. |
| Clock/quote | Parent-bound actual `off_ns` и первая подходящая BTC quote после+60; original price versus bid/ask в каждом WAIT/recheck. Исходный q1 не заменяет эти quotes. |
| Pending/ACK/debt/cap | Одновременный набор owned open/inflight entries с leaves/generations/known ACK, `entry_terminal`, `debt_since`, absolute `caps.bmax`, held quantity и current remaining TP ACK set. Final CLOSED order не доказывает отсутствие pending тогда. |
| Native margin | Prospective declared release quantity, current account reservations/available funds/native tier, актуальные marks, entries-enabled и результат штатного gate на этом clock. Пустой block list отключённой ветки ничего об этом не говорит. |

Некоторые отдельные факты могут быть в unopened raw events, но их полнота здесь **не проверялась и не предполагается**. Даже сбор terminal order rows не превратит неисполненный prospective margin gate в настоящий PASS. Не создаётся новое поручение читать всё.

## Что теперь должно содержать следующее конкретное задание

В отдельно согласованном observation/engineering дизайне нужен один side-effect-free predecision record **независимо от trading flag A0**: risk-cancel, actual riskOFF, первая lawful BTC quote+60 и изменившаяся причина WAIT/deny. Поля: parent/side, original first allocation/terminal fills, original second budget/price/TIF, second-filled-ever; held/debt/absolute cap; ordinary TP/flat/entries-enabled; old order generation/ACK; owned open/inflight leaves; current required TP/ACK; bid/ask и timestamps marks; native reservations и stock margin result для объявленного количества. Если API/источник не даёт поле — UNKNOWN и economic admission закрыт. Это точный будущий data contract, не разрешение писать observer, dry-run hypothetical orders или запускать engine сейчас.

Текущий обзор останавливается на этом выводе. Никакого нового PnL/ROI, подсчёта hypothetical profit, required-capital долларов, native/training/download, product/source edits или VPS/runtime process действий не выполнено. Неизменны original70/90 floors и DD50; закрытые бюджеты не возобновляются.

Абсолютные artifact paths, hashes, exact key sets/event counts,15 riskOFF timestamps и4 parent records: [P1_R2_COVERAGE_CHECK.json](/Users/vf/Documents/ChatGPT/Coinmaster/research-worktrees/btc-pattern-pilot-m2-20261021/reports/four-week-review-20261026/P1_R2_COVERAGE_CHECK.json).
