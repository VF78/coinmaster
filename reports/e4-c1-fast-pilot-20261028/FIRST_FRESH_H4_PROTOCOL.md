# First-fresh H4: узкое исправление и проверка

Статус: manager-selected implementation protocol under standing owner authorization for necessary CoinMaster R&D/preparation (28.10.2026, .ops/OWNER_AUTHORIZATION.md). Это не отдельное числовое согласование владельца и не live GO. Новое денежное поведение описано ниже до кода/результата; source review, freeze и отдельный root launch gate обязательны.

## Причина и цель

После четырёх корректных native попыток лучший COMBO Q+R: TOTAL5446657.63139715, обеDD51.8031515741%, до рабочего минимума23738.883590197. G-on-R/COMBO не нужен: все исходные claims проходят global-arm; текущий source такие bundles запрещает. ATR/cushion screen дал25/50/25, но не доказал восстановление прибыли; новый ATR-контроллер не реализуется.

На R Oct4 08:00 и Nov27 16:00 подтверждена потеря закрытого H4: `_c1_closed_bar` требует current money прямо в bar event. Funding обновил native account, пока checkpoint относится к предыдущей минуте. Функция не сохраняет рыночного кандидата; `_c1_quote` при confNone не рассматривает тот же закрытый бар после появления свежих денег. Существующий подтверждённый token при stale quote не теряется — исправляем именно создание подтверждения, не придуманную другую причину.

На первом свежем quote рыночные условия/порогDD40 проходят; размер и native cancel/margin execution окончательно проверяются новым собственным native путём. Нельзя выводить будущий TOTAL из старых snapshots или считать гипотетические ACK/fills доказанными.

## Единственное новое правило

База — COMBO Q+R: BTC cut heldlots//4, SOL half, restoreDD40 в двух gates; globalG OFF, stress OFF. Entry signals, sizing, EMA/ATR, TP/reference, rights, fees, data/depth/model сохраняются.

1. Сохранять только полностью закрытый допустимый H4 market candidate, который принадлежит текущему cut/credit и удовлетворяет прежним bar-time/price условиям. Не сохранять деньги как новое разрешение; бар, close, available_at и identity остаются исходными.
2. Если bar-time current money отсутствует исключительно по freshness/coherence, отложить проверку этого кандидата до первого последующего допустимого свежего C1 quote. При наличии свежих денег в исходном bar event прежняя логика сохраняется.
3. На отложенной проверке заново применить все денежные/рыночные/ownership/ordinary-close/single-attempt/margin/native TP-cancel условия на фактическом текущем состоянии. Никаких stale-money permits, pending credit, новых SOL rights или обхода ACK. Unknown не равен flat/rejected.
4. Исходный fully closed bar остаётся причинным: bar_available_at <= decision time; группа, actual cut identity/last-fill, credit/buckets, side и state должны совпасть. Новый бар заменяет кандидата; обычный выход, revoke, terminal/новая группа инвалидируют его. Не переносить bar между группами и не изменять глобальный HWM.
5. Первый matching selected-instrument quote строго после barclose/available_at с валидным current money и source>=barclose потребляет deferred candidate ОДИН РАЗ. Пока valid money нет — candidate хранится без permit. На первом fresh decision identity/credit/fill-epoch/revoke/ordinary conflict либо DD40/price/reclaim denial инвалидируют candidate до НОВОГО закрытого H4. Изменение fill epoch — фактическое после capture, не произвольно взятый stale checkpoint epoch.
6. При успехе атомарно убрать deferred candidate и перевести его в обычный confirmation token. Ожидание реального harmless-TP cancel ACK не является отказом: обычный token хранится и проходит прежние текущие money/price/margin/ACK проверки. Реальный margin/admission отказ обрабатывается старой веткой, новых attempts нет.
7. Каждый следующий relevant закрытый H4 инвалидирует/заменяет только deferred candidate, даже если новый bar price не подходит. Уже подтверждённые tokens не менять. Это часть source/review contract ДО результата.

DefaultOFF. При OFF все ранее pinned C1/Q/R/COMBO/G config и экономические ветви неизменны. Candidate metadata явно включает новую семантику. Если безопасный узкий фикс не укладывается в это описание — остановить код и уточнить контракт внутри команды, не делать framework.

## Проверки и бюджет

Минимальные engine-free tests: две actual funding-bar последовательности и отрицательные cases stale/mixed/source-future/credit revoke/group change/price or DD denial/first-fresh consumption/pending native cancel; обычный fresh bar path; OFF config pins. Никаких новых коротких native fixture engines. Один focused peer pass и конечное исправление, учёт pytest/wall/constructors отдельно.

Перераспределение под прямое standing-разрешение необходимых действий: старое распределение4candidate+2conditionalcontrol+2qualifier → **5candidate+1conditionalcontrol+2qualifier**, общий потолок **8** неизменен, уже4 завершены. Один контроль не потребовался: сравнимость source/config/input/prefix подтверждена, архивы не повторялись. Это явная новая allocation, не скрытое использование закрытых MethodA/других budgets. Старые четыре попытки и их решения неизменны.

До одной новой historical попытки `FIRST_FRESH_COMBO` на том же [2024-09-01,2026-09-01), seed10000/reserve0. Все ошибки считаются; без автоматического повтора. Claim registry до Popen; source/config/13inputs/NT1.231/preflight/peer/rootGO до child. Direct Popen, actual child exit. TOTAL и оба DD — новые собственные, literal native PnL/cash bridges0 или UNKNOWN, native liquidation/terminal status и attribution. Порог прибыли5470396.514987347, ориентир5631617.35953723, обеDD<=51.80315157406654834417870238%. Не снижать пороги ради PASS.

После первого проходящего кандидата — source freeze и прежние условные stress/57-day validation, затем оставшиеся live readiness. До explicit START владельца live_order_capability=false. Работающие сервисы/средства/ключи/ордера не меняются.
