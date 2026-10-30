# Сверка рекомендаций30.10.2026 с текущим A

Документ владельца CODEX_SOL_EXECUTION_RESET_2026-10-30.md рассмотрен как рекомендация к реализации. Прямое поручение владельца: устранить пробелы A; новый SOL из §6 только сохранить в Project и вернуться после live. Его старый checkpoint3577/CLEAN_R1/лимит8 уже заменён завершённой кампанией10/10; он не запускается повторно.

## Что совпадает

| Требование | Текущее состояние и доказательство |
|---|---|
| A без ожидания нового хеджа | A10K и actual-capital full закончены, отдельный B не выбран; CURRENT_RESULT_RU.md/comparison.json |
| Fixed initial seed, не current equity | s=initialseed/10000; существующий INIT-marker сохраняется; live-recovery и pure scale tests |
| Полный shadow admission до child-cap | wave_overlay full-parent gate; actual margin отдельно по child+pending; 45 existing focused A tests PASS |
| Все обычные SOL paths, actual fills/rights | ADD/half/full/C1cut/restore/timeout/drain проверены в существующем пакете; native FILLED не заменяется фиктивным CANCEL |
| Без бесконечного повторного spend/token | Дневной/level token и actual fill settlement; TERMINAL+APPLIED durable journal перед продолжением |
| BTC core/экономика A сохранены | 10 economic source files byte-identical source5b56; новые ограничения только в live wrapper |
| Нативные деньги/Unified/точность | Unified read-only PASS, native USDC, BTC5/SOL2, выбранные плечи40/20; actual maker.000144/taker.000432 |
| Малый капитал/tiers/minlots | Существующий отдельный24м actual-capital full:11financial gates/scaling PASS/0liq; числовые данные PRIVATE |
| Restart/unknown ACK/partial/zero/late | Переиспользованы существующие native/pure подтверждения; неизвестное состояние не даёт blind resubmit |
| Свежая рыночная ликвидность пилота | Read-only BTC/SOL l2Book snapshot30Oct PASS; это снимок, не обещание будущей глубины |

## Два реальных пробела перед live

1. C1 live-wrapper пропускал freshness-check для reduce-only; forced SOL callbacks могли продолжить закрытие на сколь угодно старом BBO при остановке feed. Исправление на последней границе reservation должно проверять свежесть и положительный размер исполнимой стороны. Свежая та же quote допускается: требование всегда новой quoteversion могло бы произвольно изменить исполнение. Реальная биржа решает actual fill/partial.
2. У forced SOL parent не было конечного срока drain. Установить единственный persisted deadline от исходного решения на существующем120s freshness horizon; не сбрасывать child/callback/restart. Expiry сохраняет tombstone, снимает recovery-confirmed и просит штатную сверку. Emergency/globalDP/BTC и обычная13×60s timeout cadence сохраняются.

Исправление зафиксировано в source4ca0d87993f28c20fb039840551c04e051378582. Focused63PASS/15.58s, независимый reviewPASS/0P1. Broader recovery200PASS/3FAIL; те же3FAIL воспроизводятся на неизменённой базе5c886 (окружение healthprobe, прежний schemaerror expectation, отсутствующий ASTmarker staging_a_epoch_seed). Широкий пакет не объявляется полностью зелёным; несвязанные исправления не добавлялись. Healthy историческая лента:83forcedSOLfills/22decisiongroups; quoteage и originaldecision→submit0ns, deadline120s не связывает эти события. Это timestamp diagnostic, не подтверждение исторических WS/BBO размеров.

Ни новые торговые сигналы/параметры A, ни новый SOL из §6 не вводятся. Отдельного24м бэктеста для отказа торговать на протухшем feed не требуется; влияние на реальный прерывающийся поток явно отличается от идеальной здоровой исторической ленты.

## Что не объявляется доказанным

Исторический результат A —5635720.91989984USDC, обе DD51.4383711874%, 0liq — относится к Bybit1m proxy/currentHLrules/zeroimpact модели. Это не гарантия будущих fills или дохода. Сохранённые raw flags NOT_FAITHFUL_DIAGNOSTIC/ranking_eligibleFalse не переписываются.

Дополнительная стоимость на неизменной ленте548fills: оборот BTC1698382947.640728/SOL32316958.7257USDC; +1bp=173069.9906366428, +5bp=865349.953183214, +10bp=1730699.906366428USDC. Это FIXED_PATH_COST_DIAGNOSTIC, не новый backtest/ROI/DD: последующие размеры и торговые решения здесь не пересчитываются. Тесты partialfill доказывают корректность обработки событий, не достаточную будущую ликвидность. У установленного native adapter market price band0.5%; outward tickrounding может немного расширить границу. Для малого пилота свежая доступная глубина проверена отдельно приватно.

## Новый SOL — отложенная задача

[Project issue138](https://github.com/VF78/coinmaster/issues/138), Todo после запуска/стабилизации A. Полный сохранённый контракт: SOL_HEDGE_AFTER_LIVE_RU.md. Старый B5e1a899b не является проверкой нового residual-confirmed covariance hedge. Его negative/raw financial failure не скрывается.

arithmetic_checks.json/check_arithmetic.py воспроизведены без изменения файлов: exact equality PASS. Пример covariance43200 против inverse-beta83333.333... — иллюстрация формулы, не калибровка настоящего рынка. Native/prefix/full новых0, бюджет кампании остаётся CLOSED10/10. START только по отдельному явному подтверждению владельца.
