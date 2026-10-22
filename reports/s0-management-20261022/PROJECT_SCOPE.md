# S0-MANAGE — одно изменение сопровождения, DD50 / netprofit90

Владелец согласовал выполнение 22.10.2026. Приоритет P0 исследовательской очереди. Это новый bounded native-пакет после завершённых #121/#122, а не возобновление моделей. [Единый принятый план](https://github.com/VF78/coinmaster/blob/66dacb18fe4cef4cdae263d21094a90a45c8a8bc/reports/s0-optimization-plan-20261022/PLAN.md).

Неизменный точный S0: TOTAL6077107.23887483 USDT, seed10000, [2024-09-01,2026-09-01), source75ffc9c/frozen scientificc1d0c69; готовый control не пересчитывать. Приёмка: сопоставимый минутный DD<=50%, TOTAL>=5470396.514987347 (min cents5470396.52), затем maxTOTAL. BTC исходные сигналы/формула sizing и оригинальный SOL-overlay остаются контролем; последующие абсолютные количества естественно зависят от нового капитала. Только native Nautilus, одинаковые данные/fees/funding/margin/execution/observer; сохранить UNKNOWN/исторические ограничения. Пилот/production/services/orders/secrets не менять.

- [x] Saved actual decisions/D1/path states за все месяцы: наблюдаемая проблема, причины, прибыльные/обычные контрпримеры и доступные причинные признаки; без нового replay/AI.
- [ ] Зафиксировать ONE remainder-management predicate/action/repeat/TP precedence и два уровня интенсивности до полных запусков. Никаких date exclusions, posthoc trade deletion, нового matching/PnL/risk/recovery framework.
- [ ] Один владелец реализации, focused native tests и независимый адресный review ордеров/денег; source/input/config pins и безопасный isolated resource preflight.
- [ ] Полные nativeM1/M2; optional M+execution только при доказанном дефекте/прошедшемM; fresh-engine повтор победителя. **Максимум4 полных попытки всего**, включая повтор; S0непересчитывать; без автоматических retry/grid. Каждый запуск в run-budget.json до старта, отдельные engine/funding journal.
- [ ] Итог S0/M1/M2/(optional)/repeat: TOTAL/ROI/netprofitretention, money-DD + отдельная OHLC квалификация, maker/taker fees/notional/funding, BTC/SOL fills/exposure, DDпериоды, причина эффекта, JSON/CSV. Отрицательный результат сохраняется без расширения поиска.
- [ ] Опубликованные source/results/checkpoint и read-back Project. Для прошедшего варианта freeze и план genuinely subsequent data; deployment и пилот не входят.

Зависимости: сохранённый exactS0 и native/data/D1 артефакты доступны после проверенной очистки; завершённые AIгипотезы не являются пререквизитом. Сначала протокол/пины/тесты/review, затем последовательные прогоны. AIмодели/широкая оптимизация/второйvenue/GUI/live не входят. Старые #121/#122 сохраняют Done.

## Правило зафиксировано до прогонов

Два последовательных пригодных settled money наблюдения одного nativeцикла: DD ранее<25%, теперь>=25%, текущая nativeпозиция убыточна. Первое пригодное наблюдение только задаёт predecessor; потеря пригодности его очищает; пересечение во время pendingincrease/старшегоexit пропускается. Одинаковое правило BTC/SOL; M1 сокращает50% остатка,M2 75%. Один claim/цикл, один IOCchild; TP/forcedexit имеют явно описанный приоритет, нет новых SOLправ от защитного fill. Открытие при ужеDD>=25 не даёт немедленного сокращения. Нет cooldown/новогоpeak/ML/дат-исключений.

Saved-precheck: levelpredicate отвергнут до кода за33/57hits в1минуту; freshcross18интервалов (BTC15/SOL3),0впервуюминуту,6прибыльныхконтрпримеров. Pending/ordinaryeligibility встаромвыгрузе UNKNOWN. СамаяранняяSOL1 не имеет прямого freshcross; улучшениеTOTAL/DDнепредполагается, проверяетсяполнойтраекторией. Пины policy-freeze.json; fullnative0/4.
