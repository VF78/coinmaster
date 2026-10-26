# SOL lifecycle V2: реализация и engine-free проверки

Принят source `a50af5433a0bbe00aecd6fec26e8d5c0321ced80`. Прямое согласие владельца: `owner-v2-zero-engine-approval.json`/`fb263ef1…`, протокол `ae2ec46f…`. Результат ограничен кодом и event replay; native matching и экономика не квалифицированы.

## Что реализовано

- Обычный SOL_CAP отменяет только ENTRY и сохраняет положительные SOL TP/STOP. Один существующий IOC owner уменьшает фактическую позицию; partial/full/terminal fill согласует права и защиту.
- TP с нулевым desired quantity отменяется через standard public cancel. До actual terminal сохраняются его liability, history и late-fill ownership; повторный cancel не отправляется после перехода PendingCancel→PartiallyFilled. Validated retiring fill учитывается один раз и использует существующее proportional уменьшение оставшихся положительных прав, сохраняя native TP identity/price/fee. Общий parent deadline60s не перезапускается; положительная защита и прежние debt clocks не получают grace.
- Глобальный SOL-выход принадлежит одному pair SOL_CLOSE. Защита сохраняется до actualflat, посторонняя/ENTRY/unknown работа блокирует завершение. Исправлены реальные quote/cache/terminal callback пути и передача в существующий global/domain completion после настоящего flat и ACK-drain.

Основная реализация изменила четыре файла: paired_prefix.py, wave_overlay.py и два адресных test/runner файла. BTC entry/LEGACY_Q, первоначальные TP цены/веса, SOL-сигналы, u/v, cap/debt формулы и A0 original rights сохранены по diff/AST proof. Supervisor, старые fixtures/data и ledgers не менялись. Нового OMS/PnL engine/SDK/services нет; research gating defaultOFF.

## Что проверено

Финальный исходник: **VPS209/209 и Mac209/209 PASS**, в том числе 40 адресных replay cases. Перед импортом тестов установлен constructor tripwire: **BacktestEngine0, matching0**. Использованы реальные Cache/Order/event классы; inventory inputs и domain spies служат method replay и не являются native matching или финансовым доказательством.

Первый checkpoint0eab502 прошёл Mac201, но независимое review нашло два R1 integration P1: outer callback barrier и отсутствие global completion handoff. Оба исправлены одним согласованным correction batch. Финальный focused review: **0P0/0P1**; предыдущие source/snapshot/review сохранены.

Подробности: [final checkpoint](V2_R1_CORRECTION_CHECKPOINT_A50AF54.json), [review](V2_ZERO_ENGINE_CORRECTION_REVIEW.md), [root acceptance](V2_ROOT_ENGINE_FREE_ACCEPTANCE.json).

## Ограничения и следующий шаг

Не проверены actual matching, partial IOC/reentrant native ACK, межордерная очередь и завершение на native transport. Для нового исходника требуется свежая E1 и новая интеграция E5; старый E7/source8a остаётся историческим case PASS.

Новых native/prefix/full запусков нет. Старый бюджет: **4/7, три FAILED/один COMPLETED; active0, remaining3HOLD**, prefix0/4 условно, full0. Все четыре строки и raw сохранены; STOP не обходился. Новых экономических результатов и доказанного достижения original70%/90% прибыли с DD50 нет.

Готовится полный source-specific native case map и единый числовой протокол. Любой будущий запуск требует отдельного прямого согласия и individual root GO. Пилот/production/deployment/externalorders не затронуты.
