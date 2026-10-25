# Причинный admission: сохранённый B2/F0 prefix

Один анализ без engine/product edits/downloads. 16/16 actual activations (11 F0, 5 B2), 15 invalidations, 8 SOL TP, 4 first-TP primary. Ни один переход не допускает новое удержание/restore: native margin и исполнения UNKNOWN. Source current06f7577, actual prefix7d513ca1.

## A: исходные BTC child rights

| # | activation UTC | actual riskOFF UTC | original unfilled | ordinary exits | paired debt | factual cohort |
|---|---|---|---:|---:|---:|---|
| 1 | 2024-09-03T20:00:00+00:00 | 2024-09-03T23:12:00+00:00 | 0 | 1 | 0 | NO_UNFILLED_RIGHT |
| 2 | 2024-09-11T12:00:00+00:00 | 2024-09-11T12:05:00+00:00 | 0.635 | 2 | 0 | FORBIDDEN_ORDINARY_BTC_EXIT |
| 3 | 2024-09-14T04:00:00+00:00 | 2024-09-14T12:01:00+00:00 | 0.488 | 0 | 2 | POTENTIAL_UNFILLED_RIGHT_REQUIRES_NEW_EXPLICIT_REVERSIBLE_LOCK_CONTRACT |
| 4 | 2024-10-02T04:00:00+00:00 | 2024-10-02T08:01:00+00:00 | 0 | 0 | 0 | NO_UNFILLED_RIGHT |
| 5 | 2024-10-07T12:00:00+00:00 | 2024-10-07T13:51:00+00:00 | 0 | 1 | 0 | NO_UNFILLED_RIGHT |
| 6 | 2024-10-10T04:00:00+00:00 | 2024-10-10T04:19:00+00:00 | 0.575 | 0 | 0 | POTENTIAL_UNFILLED_RIGHT_REQUIRES_NEW_EXPLICIT_REVERSIBLE_LOCK_CONTRACT |
| 7 | 2024-10-12T20:00:00+00:00 | 2024-10-12T21:26:00+00:00 | 0.440 | 0 | 0 | POTENTIAL_UNFILLED_RIGHT_REQUIRES_NEW_EXPLICIT_REVERSIBLE_LOCK_CONTRACT |
| 8 | 2024-10-25T16:00:00+00:00 | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN_NO_ACTUAL_RISK_OFF_BEFORE_OWNER_RELEASE |
| 9 | 2024-11-05T20:00:00+00:00 | 2024-11-05T20:05:00+00:00 | 0 | 0 | 0 | NO_UNFILLED_RIGHT |
| 10 | 2024-11-16T08:00:00+00:00 | 2024-11-16T08:04:00+00:00 | 0.375 | 0 | 0 | POTENTIAL_UNFILLED_RIGHT_REQUIRES_NEW_EXPLICIT_REVERSIBLE_LOCK_CONTRACT |
| 11 | 2024-12-11T08:00:00+00:00 | 2024-12-11T08:02:00+00:00 | 0 | 0 | 0 | NO_UNFILLED_RIGHT |
| 12 | 2024-12-20T04:00:00+00:00 | 2024-12-20T04:25:00+00:00 | 0 | 0 | 0 | NO_UNFILLED_RIGHT |
| 13 | 2024-12-24T00:00:00+00:00 | 2024-12-24T04:01:00+00:00 | 0 | 0 | 0 | NO_UNFILLED_RIGHT |
| 14 | 2024-12-26T04:00:00+00:00 | 2024-12-26T08:01:00+00:00 | 0 | 0 | 1 | NO_UNFILLED_RIGHT |
| 15 | 2025-01-07T04:00:00+00:00 | 2025-01-07T12:01:00+00:00 | 0 | 2 | 2 | NO_UNFILLED_RIGHT |
| 16 | 2025-01-09T12:00:00+00:00 | 2025-01-09T13:11:00+00:00 | 0.445 | 2 | 0 | FORBIDDEN_ORDINARY_BTC_EXIT |

Q0−F_ever — ещё не исполненная часть исходного плана; cap=max(0,Q0−D−B). Protective debt сам по себе не равен ordinary TP и не возвращает закрытое количество. Четыре потенциальных случая: Sep14, Oct10, Oct12, Nov16. В существующем коде monotone stop уже навсегда закрывает child. Возможность при гипотетическом reversible lock не является действующим правом: original native child terminal/ACK, quote, accepted real3TP и native margin требуют проверки. GTC price/status видны в JSON; cancel terminal снимок не доказывает ACK в момент решения.

Effective realU: market_redesign.py46/135–168/302–328. Generic split_cover.py150 возвращает управление сразу при _md_enabled: generic deadline/day-stop не применяются. Три TP остаются реальными; первый actual positive BTC TP закрывает право. First/second native terminal, flat, ordinary exit/pause тоже ограничивают его. Original limit не превращается в market order. Предыдущая ошибочная generic-интерпретация сохранена в attempt1-superseded-results.json/correction-receipt.json.

## B/C: actual post-TP/pre-debt, first TP primary

| activation / TP UTC | Eactual | Pprior | headroom | stress90 / stress30 | riskOFF by nextH4+60 |
|---|---:|---:|---:|---:|---|
| 3 / 2024-09-14T05:58:00+00:00 | 12346.29 | 12558.24 | 6067.17 | 1618.36 / 1079.26 | ACTUAL_RISK_OFF_AFTER_DEADLINE |
| 8 / 2024-10-25T17:22:00+00:00 | 12355.11 | 15602.18 | 4554.01 | 3431.56 / 1722.88 | UNKNOWN_OWNER_RELEASED_WITHOUT_RISK_OFF |
| 14 / 2024-12-26T07:34:00+00:00 | 12104.49 | 22551.24 | 828.87 | 2359.90 / 2359.90 | ACTUAL_RISK_OFF_BY_DEADLINE |
| 15 / 2025-01-07T08:15:00+00:00 | 14322.10 | 22551.24 | 3046.48 | 1516.08 / 1469.15 | ACTUAL_RISK_OFF_BY_DEADLINE |

E и P — единая actual coherent observer последовательность с pre-fill peaks; все8 exact postTP снимков сопоставлены с native order last_trade_id, qty decrease и cash+nativeUPNL. Later TP сохраняют уже урезанный actual BTC и не образуют candidate uncut path. Mark timestamp/source availability и sequence в JSON.

PRIMARY90: paired SIMPLE close-to-close returns; return end≤предыдущая UTC midnight t−1day. 30-day sensitivity отдельно; окно не выбиралось по исходам. Headroom=max(0,E−0.5P). Loss=max(0,max(−NB*rB−NS*rS))+0.055%*(|NB|+|NS|)+funding allowance. Funding — максимум суточной суммы absolute rates по обоим fixed current notionals за те же90/30 завершённых дней, все3 фактических funding timestamps/day известны и <t. Это консервативное stress assumption, не realized cash.

Market-stress primary:3 PASS prerequisite/1 FAIL (Dec26). Native margin отдельный UNKNOWN для всех. Даже PASS не гарантирует globalDD50. C: два actual owner riskOFF до ближайшего H4+60 (Dec26, Jan7); Sep14 позже; Oct25 owner закончил без riskOFF. Оба earlyOFF наступают после actual debt cut; непрерывный retained-candidate state UNKNOWN. Pending rehedge credit0.

## Контракт переходов

| Состояние | Допуск |
|---|---|
| TP+riskOFF | Reconcile actual exposure; удержание/увеличение требует полного admission |
| riskON+stressPASS | Только рыночная предпосылка до nextH4+60; native margin/continuity UNKNOWN блокируют |
| riskON+FAIL/UNKNOWN | Retain NOT_ADMITTED; действующий reduce сохраняется |
| nofill/partial/reject/latefill/cancelUNKNOWN | Actual fills authoritative; increases blocked until reconciliation |
| original TP/ordinary exit/flat/terminal child | Не восстанавливать закрытые права или количество |
| smalllot/fillrace | Native quantities/integer lots; no pending protection credit |
| oscillation/rearm | Edge/hysteresis/cooldown/turnover не установлены: NO_ADMISSION |

Дешёвый следующий scope: engine-free exact native cancellation/TP generation event proof и margin/quote data availability для четырёх child случаев; отдельно causal signal reconstruction после actual owner terminal, только при достаточных сохранённых inputs. Новые native/training/downloads0. Для нового lock/retention source потребуется отдельный контракт и явный budget. Исходные TOTAL70=4256975.067212381, TOTAL90=5470396.514987347/seed10000, settled+coherent eventDD≤50/zeroLiq неизменны; целей не достигли.

Reproduce: `/Users/vf/Documents/ChatGPT/Coinmaster/runtime/.venv/bin/python reports/hedge-risk-contract-20261025/analysis/causal_admission.py` из manager checkout (absolute runtime interpreter also works). All source/data/contract hashes в results.pins; script/output digest в validation.json.
