# Единый план: полный аудит S0 и ограниченная проверка H_SOL / H_BTC

Основание: исходные требования владельца 0–4 и новый OWNER_TASK.txt. Существующий широкий аудит и отрицательные прогоны переиспользуются; C1, SOL budget и early TP3 не повторяются под другими именами. Parent Project #123 отражает весь пакет, а не последний эксперимент.

Цель: global settled marked-equity DD≤50%, минимум 90% чистой прибыли сопоставимого S0, нулевые model liquidations, полные деньги/позиции/заявки. DD≤30% — дополнительная цель. Старый абсолютный TOTAL floor=5470396.514987347 отдельно от относительного floor при изменении execution model. Период [2024-09-01,2026-09-01), seed10000USDT, RESERVE0; global high-water не сбрасывается. Sharpe и прочие метрики не заменяют критерий TOTAL.

## Общие ограничения

- Исследовательская работа: пилот, production, сервисы, credentials и реальные ордера не менять.
- Продуктовый код — только isolated canonical VPS checkout, не dirty основной checkout и никогда не /opt. Mac — выполнение неизменяемого снимка, данные и отчёты; один владелец engine/domain/journal, общие файлы не меняются конкурентно.
- Новые исполнители: GPT‑6.1 Sol / medium, узкий контекст. Один focused implementation pass, relevant verification, адресное независимое money/order review; максимум одно содержательное исправление конкретного дефекта.
- Максимум шесть НОВЫХ физических полных native-попыток, включая failed/invalid/corrected/control/combined/repeat. Старые закрытые ledgers не обнуляются и не переносятся. Каждый полный запуск — только после protocol/source/config/input/engine freeze, tests/review и root GO. На подготовке запусков 0.
- Nautilus — единственный economic engine; нет синтетического PnL, поддельных native terminal receipts и восстановления UNKNOWN нулём. Нет новой ML, grid/Optuna, широкого поиска EMA/TP/плеча/z или нового risk/execution сервиса.

## Пакеты и критерии готовности

| Пакет | Требования владельца | Результат и критерий готовности | Зависимости |
|---|---|---|---|
| SC-00. Контроли, методики, полный реестр правил | 0,1,4; документ §§1–3 | Exact S0/E4/source/flags/observer/settlement; существующие результаты/ledgers сверены. Каждое активное экономическое правило получает source, назначение, происхождение/обоснование, VERIFIED/CONTRADICTED/HYPOTHESIS/NOT_TESTED, доказательство пользы/вреда и KEEP/FIX/TEST/DEFER. Неоптимальность не объявляется ошибкой исполнения. Существующие 11 источников/2×2/атрибуция переиспользованы; новые источники только адресно. Ни один исходный пункт 0–4 не потерян. | Первым; реестр пополняется измерениями следующих пакетов |
| SC-01. Явное исполнение SOL и equivalence | 1,3,4; §§3.1,4 | Native fixtures requests <1000/=1000/>1000 при depth500/1000/2000; shared liquidity, partial/cancel/reject/late fill, две ступени, D1 retry, права, held/pending и margin. Explicit child cap1000 на исходную разрешённую ступень/попытку без новых внутридневных попыток. Intended→allowed→submitted→filled→unused→next attempt наблюдаемы. Эквивалентность lifecycle/экономики доказана или первое расхождение названо; FILLED не подменяется CANCELED. | SC-00; source/test/review до historical control |
| SC-02. Причинные BTC parents и zero-TP | 1,2,4; §§3.2,5 | Parent-level causal dataset: closed ATR/EMA/wave-age, first/repeat, available positions/orders/equity/E4 gate; q0/q1/zero branch/gross/net/cap/lot/VWAP/SOL-rights. q1 perturb±0.1/0.5/1/2/5bp с native tick rounding — только локальная sensitivity. MAE/MFE до конца волны с ready_at/censoring и единым minute-mark basis; future label не feature. Полнота/пропуски и независимые волны названы. | SC-00; observation hook согласован с единственным engine owner |
| SC-03. H_SOL — бюджет только новых adds | 3,4; §6 | Frozen55%H/closedWilderATR14/conservativeBTCreserve без подбора. Проверка КАЖДОЙ новой SOL_ADD, без DD35 trigger/forced trim/auto-restore. Held+pending+reserved+candidate, две ступени не тратят бюджет дважды. Наибольшая допустимая часть в rights/child/lot/fee bounds; units и монотонность доказаны до формулы/поиска. Невместившееся право сохраняется, clock/частота неизменны. | SC-00/01; не повторяет прежний budget+trim |
| SC-04. H_BTC — причинный sizing повторного входа | 2,4; §7 | Только завершённые метки с ready_at<decision; две группы first/repeat, sides вместе; frozenATR/firstactualfill PLANREF, marks до закрытого D1 EMA-switch. Минимум8 валидных наблюдений каждой группы; k=min(1,Q90first/Q90repeat), иначе1 с причиной. k один раз до zero-TP/lot corrections, не компенсируется SOL/плечом/частотой. Quantile/interpolation frozen; prefix/incomplete-wave/partial-weight tests PASS; activation и wave count показаны. | SC-00/01/02; затем отдельный native candidate |
| SC-05. Полная native-проверка и интеграция | 0,2,3,4; §§8–11 | Последовательные control→H_SOL→H_BTC→gated combination→passing repeat, всего≤6. Архивные controls используются только при сопоставимости; при неэквивалентности новые S0/E4 в одинаковой модели за счёт тех же слотов. Семь E4 эпизодов+все24месяца+новые global maxima; fees/money/rights/denial/fills/calendar/recovery. Принят или честно отклонён вариант; полезные engineering fixes отдельно от проигравшей политики. | По мере готовности SC-01/03/04, полные движки только sequential |

## Протокол запусков и рубежи

G0 — Project покрывает исходные 0–4 и все новые §§1–12, есть actual read-back; начальные ledgers/контроли сверены.

G1 — короткие контракты исполнения/данных/units/prefix tests и независимый review пройдены. protocol.json содержит точные формулы/defaults, versions/hashes, quantile method, source/data/engine/config, семантику семи окон, причинное объяснение и порядок. До G1 полных запусков нет.

G2 — отдельные H_SOL/H_BTC технически валидны, действительно активировались, локальный механизм подтверждён, money/rights/календарь корректны, control сопоставим. Только тогда комбинация. Индивидуальное прохождение глобальной DD50 не обязательно для комбинации, но отсутствие эффекта/невалидность не лечится объединением.

G3 — полный GO/NO_GO по абсолютному и сопоставимому90%-floor, global DD/нулевым liquidations и terminal accounting; fresh-engine повтор только полного проходящего кандидата. Fresh repeat не OOS. NOT_RUN всегда с конкретной причиной.

Начальный бюджет: E4 explicit-policy control; при неэквивалентности — S0 в той же новой policy; H_SOL; H_BTC; только обоснованная комбинация; passing repeat. При дополнительном необходимом контроле/ошибке сокращаются кандидаты, лимит не расширяется. Дорогой исторический stress depth не запускается без места и сопоставимых controls; short-fixture stress не выдаётся за portfolio robustness.

## Семь эпизодов и критерий полноты

Сверить recipe-specific peak/trough/recovery для 03.10.2024, 13.01.2025, 11.04–06.06.2025, 06–18.09.2025, 22.10–28.11.2025, 08.02.2026, 06.07–19.08.2026. Даты — диагностические окна, не условия торговли. Плюс все месяцы и новый global worst. Cash bridge не называется funding; missing signed funding остаётся UNKNOWN.

## Завершение и статус

Каждый пакет закрывается только по его артефакту и acceptance. Родитель не закрывается из-за результата одного C1 или другой отдельной гипотезы. После покрытия ВСЕХ пакетов исследование может завершиться GO или NO_GO; торговая цель отдельно остаётся NOT_MET при отсутствии проходящего кандидата. Нерешённые пункты/NOT_TESTED не скрываются за Done.

Обязательный report pack: protocol.json, run-ledger.json, contract-audit.md, execution-equivalence.json, btc-causal-risk.csv, comparison.json, episode-attribution.csv, REPORT.md + native receipts/manifests. На текущем старте: подготовка, 0 новых historical engines, никакого изменения пилота.
