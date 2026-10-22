# S0-MANAGE — одно изменение сопровождения, DD50 / netprofit90

Владелец согласовал выполнение 22.10.2026. Приоритет P0 исследовательской очереди. Это новый bounded native-пакет после завершённых #121/#122, а не возобновление моделей. [Единый принятый план](https://github.com/VF78/coinmaster/blob/66dacb18fe4cef4cdae263d21094a90a45c8a8bc/reports/s0-optimization-plan-20261022/PLAN.md).

Неизменный точный S0: TOTAL6077107.23887483 USDT, seed10000, [2024-09-01,2026-09-01), source75ffc9c/frozen scientificc1d0c69; готовый control не пересчитывать. Приёмка: сопоставимый минутный DD<=50%, TOTAL>=5470396.514987347 (min cents5470396.52), затем maxTOTAL. BTC исходные сигналы/формула sizing и оригинальный SOL-overlay остаются контролем; последующие абсолютные количества естественно зависят от нового капитала. Только native Nautilus, одинаковые данные/fees/funding/margin/execution/observer; сохранить UNKNOWN/исторические ограничения. Пилот/production/services/orders/secrets не менять.

- [x] Saved actual decisions/D1/path states за все месяцы: наблюдаемая проблема, причины, прибыльные/обычные контрпримеры и доступные причинные признаки; без нового replay/AI.
- [x] Зафиксировать ONE remainder-management predicate/action/repeat/TP precedence и два уровня интенсивности до полных запусков. Никаких date exclusions, posthoc trade deletion, нового matching/PnL/risk/recovery framework.
- [x] Один владелец реализации, focused native tests и независимый адресный review ордеров/денег; source/input/config pins и безопасный isolated resource preflight.
- [ ] Полные nativeM1/M2; optional M+execution только при доказанном дефекте/прошедшемM; fresh-engine повтор победителя. **Максимум4 полных попытки всего**, включая повтор; S0непересчитывать; без автоматических retry/grid. Каждый запуск в run-budget.json до старта, отдельные engine/funding journal.
- [ ] Итог S0/M1/M2/(optional)/repeat: TOTAL/ROI/netprofitretention, money-DD + отдельная OHLC квалификация, maker/taker fees/notional/funding, BTC/SOL fills/exposure, DDпериоды, причина эффекта, JSON/CSV. Отрицательный результат сохраняется без расширения поиска.
- [ ] Опубликованные source/results/checkpoint и read-back Project. Для прошедшего варианта freeze и план genuinely subsequent data; deployment и пилот не входят.

Зависимости: сохранённый exactS0 и native/data/D1 артефакты доступны после проверенной очистки; завершённые AIгипотезы не являются пререквизитом. Сначала протокол/пины/тесты/review, затем последовательные прогоны. AIмодели/широкая оптимизация/второйvenue/GUI/live не входят. Старые #121/#122 сохраняют Done.

## Правило зафиксировано до прогонов

Два последовательных пригодных settled money наблюдения одного nativeцикла: DD ранее<25%, теперь>=25%, текущая nativeпозиция убыточна. Первое пригодное наблюдение только задаёт predecessor; потеря пригодности его очищает; пересечение во время pendingincrease/старшегоexit пропускается. Одинаковое правило BTC/SOL; M1 сокращает50% остатка,M2 75%. Один claim/цикл, один IOCchild; TP/forcedexit имеют явно описанный приоритет, нет новых SOLправ от защитного fill. Открытие при ужеDD>=25 не даёт немедленного сокращения. Нет cooldown/новогоpeak/ML/дат-исключений.

Saved-precheck: levelpredicate отвергнут до кода за33/57hits в1минуту; freshcross18интервалов (BTC15/SOL3),0впервуюминуту,6прибыльныхконтрпримеров. Pending/ordinaryeligibility встаромвыгрузе UNKNOWN. СамаяранняяSOL1 не имеет прямого freshcross; улучшениеTOTAL/DDнепредполагается, проверяетсяполнойтраекторией. Пины policy-freeze.json; fullnative2/4: M1 complete, M2 running.

## Текущий checkpoint — M1 завершён, M2 работает / budget 2 of 4

Source [efa7c723](https://github.com/VF78/coinmaster/commit/efa7c723d9f0c5c1bdc8f491abf12921ac41c275) опубликован и GitHub ref проверен. 100 focused tests PASS / 13.09s, independent review GO; единственный P1 исправлен до запусков. 77 исходных файлов в изолированной job, 13 входных артефактов S0, отдельные engine/account/funding journals, RAM650MiB / no swap / one thread / private network.

M1 (50%) завершён штатно 22.10.2026 17:07:06 UTC: exit0, полный период, source/input 87 checks PASS, terminal flat, liquidation0. TOTAL **2 615 745,21476479 USDT**, settled minute DD **58,774095%**, retention S0 net profit **42,948725%**: оба экономических критерия FAIL. 26 защитных заявок BTC20/SOL6: 22 полностью FILLED, 4 SOL частично исполнены и CANCELED согласно зафиксированному IOC. 621 fills, fees710655,26790133; signed funding UNKNOWN. Независимая проверка saved outputs: 17 основных и9 комиссионных checks PASS; финальный cash endpoint учтён, DD не меняется.

M2 (75%) запущен один раз 22.10.2026 **17:09:47 UTC**, unit `cm123-s0-manage-m2-20261022-r1.service`, MainPID1416481. Тот же frozen source/правило/данные, параметры после M1 не менялись. Результат ожидается; автоматических повторов/третьих вариантов нет. Бюджет **2/4**, fresh-engine confirmation только для прошедшего оба критерия кандидата. S0 не пересчитывался, пилот/production не менялись. Полные пины и квитанции: run-budget.json, m1-completion.json, m2-launch-receipt.json.
