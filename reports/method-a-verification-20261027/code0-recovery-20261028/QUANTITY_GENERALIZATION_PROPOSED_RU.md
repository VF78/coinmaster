# Предложение: обобщение только количественной области CODE0

Статус PROPOSED. Текущий CODE0 a4ed258 реализован default-OFF, final20/20 engine-free PASS, independent0P0/P1. Native/prefix/full0, расход9/18. Автоматическая проверка одобрения отклонила удаление guards BTC<=1/SOL>=-132.9 и положительный тест большего размера: сочла это материальным расширением одобренной области. Операция не выполнена; guards и отрицательный outside-domain тест сохранены. Точный ответ: AUTO_REVIEW_REJECTION.json. Этот документ не разрешает повтор заблокированного действия.

## Что требуется разрешить отдельно

В том же изолированном worktree заменить только абсолютные количественные границы проверенной области на границы, полученные из фактических native позиций и уже работающего TP. Добавить положительные engine-free проверки больших количеств и отрицательные проверки границ области. Новых native/prefix/full запусков0, общего бюджета18 или его распределения это не меняет.

Все прочие ограничения сохраняются: BREACH-only/default-OFF; известные цены/side/ACK/owner, источник cash и funding; тот же baseline уже работающих ордеров; отсутствие pending-fill credit; полный endpoint safe; increases OFF до фактической безопасности; известные положительные TP/STOP и sole owner. Не менять BTC core, обычный admission, initial TP prices/weights, DD50 или cushion. Не расширять направления, fee/funding/triggered STOP/pending-universe и tier-переходы без отдельного доказательства; неподдержанное UNKNOWN/DENY.

## Конкретные проверки перед включением новой области

- Диапазоны x=[0,actual known remaining BTC TP]<=actual BTC и z=[0,actual SOL] выводятся из Cache, а не из чисел1/132.9.
- Для конкретного snapshot доказать прежние условия max-affine модели: постоянные знаки, известные аффинные cash/fee bounds, корректный Money-lattice старого fee, положительный cushion во всём диапазоне, неизменность допустимых сценариев. Все необходимые margin/tier границы либо охвачены существующим partitioner, либо такой snapshot отвергается. Не писать второй симулятор.
- Все частичные исходы сравниваются с одним и тем же unavoidable baseline; весь full-fill edge safe. Ноль исполнения не считается восстановлением. LIMIT IOC price/cost guard проверяется заново при dispatch, actual fills только из native событий.
- Добавить, например, согласованный native-Cache тест BTC2/SOL200 внутри подтверждённой первой tier и тесты неподдержанных tier/sign/pending случаев. Само увеличение количества без доказанных остальных условий не даёт admission.
- Одно узкое независимое ревью дельты; один final connected focused acceptance. Большие старые passing suites и M2/P0R/P1 не повторяются. Сохранить code0/failure artifacts и financial dirty files.

Результат — код и точные границы доказанной применимости, не historical ROI/DD и не новая native-авторизация. Будущий native case map должен учитывать изменившийся cash и отдельное явное разрешение запуска; M3/M3R FAILED не переименовываются. Пилот/production/deployment/services/real orders/transfers/downloads исключены.
