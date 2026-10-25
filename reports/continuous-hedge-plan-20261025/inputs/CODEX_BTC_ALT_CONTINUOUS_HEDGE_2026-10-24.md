# CODEX TASK — Continuous BTC + Adaptive SOL/ETH Hedge

**Дата:** 2026-10-24  
**Репозиторий:** https://github.com/VF78/coinmaster  
**Режим:** R&D + воспроизводимый бэктест; **без live-торговли, деплоя и изменения действующего бота**.

## 0. Цель и жёсткие ограничения

Создать и объективно проверить алгоритм **непрерывного управления BTC-core и SOL/ETH-хеджем**. Обе ноги активно меняют объём, получают доборы и частичные TP, циклически переоткрывают ордера; весь портфель оценивается по **TOTAL_CAPITAL = ACTIVE_EQUITY + RESERVE**, с учётом unrealized PnL, funding, комиссий и ликвидаций. Приоритет — **максимальный итоговый TOTAL_CAPITAL**, а не минимальная просадка / Sharpe; потеря ACTIVE и перезапуск допустимы, но должны честно моделироваться.

**Обязательно:**
1. **Сохранить без изменений сигналы входа, sizing и TP BTC-победителя** в основном эксперименте. BTC-only должен воспроизводиться побитно/с оговорённой точностью. Любые изменения BTC — только отдельная явно помеченная ablation.
2. Построить **три конкурирующие стратегии** на одной базе исполнения/данных: A) Adaptive Cross-Hedge Inventory (основной кандидат); B) Persistent Dual Dynamic Grid; C) Rolling Statistical Spread Inventory. Для каждой проверить **BTC/SOL и BTC/ETH**.
3. Сравнить с BTC-only, существующим BTC+SOL победителем и простыми фиксированными/динамическими хеджами. Не назначать победителя до фактического теста.
4. Не считать «реализованную grid profit» самостоятельной прибылью сверх полного PnL. Прибыль от торговли хеджем доказать **приростом TOTAL_CAPITAL относительно контролей**.
5. Не менять пользовательские торговые настройки, реальные позиции, ключи, деплой и GUI. Для анализа использовать исследовательский runner; не создавать второй параллельный движок, если имеющийся подходит.

## 1. Preflight: установить источник истины

До кода:
- Прочитать `AGENTS.md`, `.ops/PROJECT_TRUTH.md`, `.ops/ACTIVE_TASK.md`, актуальные файлы стратегии и research runner. **Эти .ops-файлы в публичной `main` датированы маем 2026; нельзя считать их текущим состоянием октябрьской стратегии.**
- `git status`, `HEAD`, active branch, remote branches и последние коммиты; **не перезаписывать dirty tree и не объединять ветки автоматически**.
- Проверить актуальные исследовательские ветки по содержимому, а не по именам: `codex/nautilus-btc-sol-mvp`, `codex/e4-sol-residual*`, `codex/residual-recovery*`, `codex/sol-conditional-hedge-btc-band-v2-20261023`, `codex/market-redesign-btc-20261024` и при необходимости другие свежие ветки.
- Найти **канонические** BTC strategy implementation, конфигурацию победителя, источник данных, комиссии, funding, simulator, historical fills, отчёты. Зафиксировать **точные commit SHA, файлы, dataset IDs, период** в `BASELINE_MANIFEST.json`.
- Если несколько «победителей» с разными результатами — **не выбирать по памяти**: воспроизвести варианты и дать явное сравнение. Исторически сообщался ориентир BTC+SOL: старт 10 000 → 6 077 107 USDT, Max DD 67% за ~24 мес; **это заявленный ориентир, а не подтверждённый результат теста**.
- Проверить наличие NautilusTrader runner и используемой версии API. Если он уже есть — переиспользовать. Не менять production path и не переносить логику в Freqtrade без необходимости.

**Gate 1:** сделать BTC-only и current-winner baseline replay, сравнить сделки и итоговые метрики с репозиторными отчётами. Если результат не воспроизводится — зафиксировать root cause и продолжать исследование только с явно маркированным `UNVERIFIED_BASELINE`; не выдавать относительные улучшения как достоверные.

## 2. Общая событийная модель

Использовать существующие движок/данные; дополнительные компоненты только при отсутствии аналога:

- `BtcCoreAdapter`: читает реальные BTC-сигналы/ордера/позиции **без изменения** алгоритма.
- `AltHedgeEngine`: отдельный инвентарь SOL **или** ETH, целевая экспозиция, add/reduce/TP/rearm, относительная сила.
- `PortfolioController`: синхронизирует обе ноги, margin, gross/net, funding, лимиты, state transitions, ACTIVE/RESERVE.
- `ExecutionAndFillLedger`: исполнения и виртуальные лоты, комиссии, funding, realized/unrealized PnL, позиции и средние цены; реальная биржа хранит net-позицию, виртуальные лоты — лишь аналитика.
- `ResearchRunner`: идентичный поток событий/модели исполнения для всех baseline/candidates, параметризованный конфиг, воспроизводимые отчёты.

События: `BAR/TICK`, `FILL` (partial/reject/cancel), `FUNDING`, `MARK`, `MARGIN`, `LIQUIDATION`, `RESERVE_TRANSFER`, `RESTART`. Приоритет событий и разрешение конфликтов внутри свечи — детерминированные, документированные и одинаковые для всех кандидатов.

**Состояние ног:** `BTC signed_qty` сохраняет направление winner (long/short/flat); ALT-ногу направлять противоположно BTC только когда хедж включён сигналом. Не подменять BTC-сигналы обязательным BTC-long. При flip/flat BTC: корректно пересчитать ALT, убрать orphan orders/рисковые остатки. В обычном режиме допускается постоянный `min_inventory` обеих ног; исследовать 0/5/10/20% как параметр, **не жертвовать контролем ликвидаций ради искусственного постоянного остатка**.

## 3. Три стратегии: implement & compare

### A. Adaptive Cross-Hedge Inventory — основной кандидат

**Вход:** BTC exposure `B_t=abs(q_BTC)*mark_BTC` в USD; OHLCV и funding BTC+ALT; 1D/4H/1H regimes; коэффициенты волатильности/корреляции из **только прошлых** данных.

Исторические лог-доходности `r_B, r_A`; с rolling-window `W`:

```text
rho    = corr(r_B, r_A)
sig_B  = stdev(r_B)
sig_A  = stdev(r_A)
beta_A = cov(r_A,r_B) / var(r_B)
h_minvar = clip(rho * sig_B / sig_A, 0, h_max)
h_beta   = clip(1 / beta_A, 0, h_max)  # только beta_A > 0; иначе выключить этот компонент
h_t = (1-alpha_t)*h_minvar + alpha_t*h_beta
ALT_target_notional = -sign(q_BTC) * B_t * h_t * regime_multiplier_t
```

`alpha_t`, `regime_multiplier_t` — **явные правила, не lookahead**: BTC downside/upside regime, ALT/BTC relative momentum, z-score относительной силы, realized volatility, funding и inventory/margin utilization. Проверить `alpha ∈ {0, 0.5, 1}` + режимный вариант. `W ∈ {30, 90, 180, 270}` дней (или близкие доступные сессионные значения). Нулевую дисперсию, отрицательную beta и отсутствие истории обрабатывать безопасно.

Торговля ALT внутри целевого объёма:
- Сигнал усиливает хедж при неблагоприятном для BTC рынке, **если** относительная динамика ALT не указывает на опасный тренд против хеджа.
- Сетка частичных доборов/TP на базе `ATR%` либо realized-vol spacing: `grid_step = clip(k*ATR_pct, floor, ceiling)`; `k ∈ {0.5,1,1.5,2}`. Число уровней `n ∈ {3,5,7}`. Не делать геометрическое бесконечное увеличение размера.
- `add_size` зависит от отклонения `ALT/BTC`/z-score, расстояния до целевого inventory, уже накопленного номинала, маржи, ожидаемого edge после fee/funding; **при сильном adverse ALT-trend additions замедляются или прекращаются** (inventory throttle).
- При благоприятном движении ALT — **частичные reduce-only TP**; после фактического fill восстанавливать сетку по текущему режиму. Не считать limit touch гарантированным fill. Отдельно учитывать сохранённый core/residual inventory.
- `rebalancer` меняет объём к target через hysteresis/deadband так, чтобы не платить комиссии на каждой свече; принудительная полная ликвидация ног не является штатным окончанием цикла.
- При отрицательном ожидаемом edge после издержек — не торговать ради «активности».

### B. Persistent Dual Dynamic Grid — challenger

Независимые циклические сетки BTC и ALT, объединённые портфельным контроллером. BTC-часть сравнивается в **двух вариантах**: G1 — **BTC winner immutable** + grid only ALT (сопоставимый контроль); G2 — отдельная чистая dual-grid замена BTC (не смешивать с основным сравнением winner-preserving подходов).

Правило цикла: исполнение add → выставить TP на долю лота; исполнение TP → новый add, **без обязательного закрытия всей позиции**. Динамический spacing, inventory rebalancer, throttling против сильного тренда, bounded gross exposure, margin controller. Старт с одинаковыми бюджетами и fee/funding как у A.

### C. Rolling Statistical Spread Inventory — challenger

На лог-ценах BTC/ALT: rolling hedge coefficient (`OLS` и/или `Kalman`), `spread`, z-score, проверка устойчивости связи по **train-only** данным, regime/break detector. На расширении спреда частично добавлять BTC/ALT в противоположных направлениях; при нормализации частично закрывать и возобновлять. Оставлять конфигурируемый residual inventory; при разрыве статистической связи **не усреднять вслепую**. Проверить, приносит ли сигнал реальный инкремент к immutable BTC core. Не заявлять коинтеграцию на основании одной корреляции.

## 4. Контроли, параметры и экономическая модель

**Минимальный набор экспериментов для каждого доступного интервала:**

| ID | Конфигурация |
|---|---|
| B0 | BTC-only, исходный winner core |
| B1 | Исходный BTC+SOL winner без изменений |
| B2–B3 | BTC+SOL / BTC+ETH, fixed notional short/long opposite BTC |
| B4–B5 | BTC+SOL / BTC+ETH, rolling minimum-variance hedge |
| A-SOL / A-ETH | Adaptive Cross-Hedge Inventory |
| G-SOL / G-ETH | Persistent Dual Dynamic Grid (B1, B2 отдельно) |
| S-SOL / S-ETH | Rolling Statistical Spread Inventory |

Все используют один стартовый **TOTAL_CAPITAL = 10 000** (валюта settlement явно указана), одинаковую BTC-конфигурацию и реализуемый leverage/маржу; при сравнении разделить неизменяемые core-tests от экспериментов с иным BTC. Капитал не пополняется извне. Стартовый hedge-equity не должен возникать из «бесплатной» маржи.

**Капитал и PnL:**

```text
ACTIVE_EQUITY(t) = account_cash_collateral(t) + sum(unrealized_PnL_at_mark(t))
TOTAL_CAPITAL(t) = ACTIVE_EQUITY(t) + RESERVE_outside_margin(t)
PnL_net = price_PnL_from_actual_fill_prices_and_marks + funding_cashflows - fees
```

Slippage входит в actual fill price (не вычитать повторно); отдельно отчитывать его как execution-cost относительно benchmark mid. Не прибавлять `grid realized profit` второй раз к PnL; учитывать депозиты/выводы/reserve как внутренние трансферы. Отдельный `Recovery Ledger`: сколько PnL портфеля создано **дополнительными сделками** по сравнению с baseline `BTC-only`, `static hedge`, `hold initial inventory`; учитывать разницу исходных экспозиций и торговых издержек.

**Reserve policy:** сравнить отвод 0/10/25/40% **чистой реализованной прибыли** с двумя вариантами расчёта базы: положительная прибыль последнего расчётного периода и превышение realized-PnL high-watermark; transfer только при допустимой марже. RESERVE физически исключён из доступной маржи ACTIVE. При ACTIVE wipe: ликвидация/закрытие по правилам площадки, затем restart из RESERVE по заранее заданной политике, без автоматического штрафа за wipe; считать количество wipes, сроки рестартов, остаток RESERVE и конечный TOTAL.

**Издержки:** Hyperliquid perp fee tier 0 ориентир `maker=0.015%`, `taker=0.045%`; фактические ставки параметризовать/проверить на дату данных, включая скидки/изменения tier. Funding — исторический по конкретному инструменту и с правильным знаком (на Hyperliquid почасовой); при отсутствии данных пометить недоказуемость результатов. Спред, проскальзывание, PostOnly rejection/queue, частичные исполнения; минимум три сценария fill quality. Ликвидация — проверка cross/isolated maintenance margin и mark price по правилам выбранной площадки; нельзя использовать future low/high для улучшения исполнения.

## 5. История, метод исследования, защита от переобучения

1. Данные BTC, SOL, ETH одной площадки, по возможности **2021–2026-10-24**, обязательно максимально доступный перекрывающийся период `2024–2026-10-24`; честно указать листинг, дырки, timestamp UTC, источники, цену (trade/mark/index), funding. Разные биржи не смешивать без отдельного моделирования basis/fees. Для Hyperliquid исторические best bid/ask и полная L2 **не восстанавливаются** автоматически из стандартного API — не изображать ретроспективный maker fill как достоверный при отсутствии order-book данных.
2. Сначала `smoke` на 7–30 днях, затем полный historical run и одинаковое окно на всех вариантах. Проводить `walk-forward`: train → validation → **строго последующий OOS**, финальный holdout (например, последние 6 месяцев) не использовать при подборе; границы вычислять из реально доступной истории. `W`, пороги, n, TP, throttle и reserve выбираются только на train/validation.
3. Отдельно проверить режимы: сильный BTC down + SOL down; BTC up + SOL растёт быстрее; BTC down + SOL растёт; пилу/боковик; V-образный разворот; funding-spikes; разрыв корреляции; распад liquidity. Включить 2× fees, неблагоприятное проскальзывание, missing events, reconnect, delayed hedge fill.
4. `seed`, commit SHA, версия движка, frozen configs, checksum данных, time cut, source и model допущений обязательны. Ни один тест не использует информацию после `2026-10-24`.
5. Для каждой стратегии сделать ablation: без dynamic-beta, без grid, без throttle, без reserve, SOL→ETH, maker→taker, permanent min inventory 0→10%.

**Primary rank:** финальный OOS `TOTAL_CAPITAL` / ROI всей системы при сопоставимой стартовой сумме. Дополнительно: медиана/диапазон по walk-forward окнам, ΔTOTAL vs BTC-only, realized/unrealized decomposition, CAGR (если применимо), MDD ACTIVE/TOTAL, wipes/restarts, funding/fee/slippage costs, trade count, turnover, tail losses, маржинальные разрывы. Не выбирать решение только по Sharpe/MDD. Показывать **абсолютный доход и стоимость дополнительной сложности хеджа**.

## 6. Функциональные проверки (unit, integration, invariants)

- `BTC-only parity`: исходные timestamps, side, qty, entries/adds, TP, exit/funding/fees, итоговый equity vs frozen baseline; fail при необъяснённом отличии.
- `PnL identity`: cash + unrealized + outside reserve = total; после TP и reserve transfer total не меняется без рыночного движения/fee.
- `No free money`: смена названия реализованной прибыли на «grid profit» не увеличивает total; нельзя считать прибыль при закрытии убыточного hedge; знак funding корректен.
- `Fill semantics`: partial fill, rejected PostOnly, cancel/replace, нет fill на mere touch, неисполненный hedge после исполненного BTC, idempotency retry/reconnect.
- `Margin`: cross/isolated, mark moves, liquidation/wipe, funding-debit и допустимость RESERVE transfer, рестарт без внешних денег.
- `Two-leg lifecycle`: обе ноги уменьшаются/добираются/TP, residual persists в штатном режиме; при BTC flip/flat старая ALT-позиция и ордера корректно переходят в новый режим.
- `Lookahead`: признаки считаются только из закрытых свечей/доступных событий; отсутствие будущего funding, отсутствие случайного выбора лучшей последовательности TP/add в одной свече.
- `Data parity`: инструменты синхронизированы по UTC; нет синтетических нулевых доходностей от пропуска цен; все сравниваемые алгоритмы видят одинаковую выборку.

## 7. Deliverables / Definition of Done

Код и артефакты разместить **в существующей структуре** (`research/continuous_hedge/` допустим только если аналога нет), без дублирования runner, с минимальным README:

1. `BASELINE_MANIFEST.json`: каноническая ветка/commit, baseline, данные, точные даты, комиссии, отклонения/пробелы.
2. Исполнимые A/B/C + контрольные модели, конфиги всех запусков, automated tests, команды `smoke`, `full`, `walk_forward` (в README реальные, не вымышленные).
3. `comparison.csv`/Parquet: вся матрица по стратегиям и BTC/SOL, BTC/ETH; `orders_fills`, `funding_ledger`, `equity_curve`, `inventory_curve`, `reserve_ledger`, `run_manifest`; графики equity TOTAL и ACTIVE, underwater TOTAL, ALT/BTC relative strength и ALT inventory.
4. `RESULTS.md` максимум ~2 страницы: какие данные/период реально использованы; воспроизвёлся ли winner; таблица ROI / terminal TOTAL / ΔTOTAL / MDD / wipes / комиссии / funding по всем вариантам; лучшая модель OOS; почему и за счёт каких PnL компонентов; ссылки на сохранённые артефакты; честные ограничения.
5. `FAILURES.md`: если нет данных, исторических funding, стабильного движка или parity — конкретный blocker, что фактически проверено, **точная команда** для продолжения. Не писать выдуманный ROI и не называть smoke «полным тестом».
6. Если A побеждает OOS: подготовить **отдельный dry-run config** и план paper-trading через существующий Nautilus/адаптер; **не запускать live**, не добавлять секреты в репозиторий.

**Завершение:** провести тесты, проверить diff, сохранить воспроизводимые результаты; в чате дать короткий итог: `baseline verified?`, `winner`, `ΔTOTAL vs BTC-only`, `SOL vs ETH`, `OOS`, `blockers`, `paths/commands`. Не тратить контекст на повторы теории.

## 8. Первоисточники (изучить только нужные для реализации разделы)

- GridBT: постоянные long/short сетки, rearm и independent inventory — https://www.gridbt.com/docs/concepts/how-gridbt-works
- Chen et al., 2025: Dynamic Grid Trading; ограничения статического grid — https://arxiv.org/abs/2506.11921
- Nguyen & Bui, 2026: delta-neutral dual grid, adaptive inventory, throttling — https://ssrn.com/abstract=6280958
- CME Group, 2025: BTC/SOL/ETH correlation и vol для справки (не использовать как параметры без пересчёта на тестовом интервале) — https://www.cmegroup.com/articles/2025/diversifying-crypto-portfolios-with-xrp-and-sol.html
- NautilusTrader: production-oriented `BacktestNode` — https://nautilustrader.io/docs/latest/getting_started/backtest_high_level/
- NautilusTrader ↔ Hyperliquid: поддерживаемые ордера/данные, ограничения истории, recovery — https://nautilustrader.io/docs/latest/integrations/hyperliquid/
- Hyperliquid: fee tiers — https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees
- Hyperliquid: hourly funding — https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding
- Hyperliquid: margin/maintenance/liquidation — https://hyperliquid.gitbook.io/hyperliquid-docs/trading/margining

**Начни с Gate 1. Не выдавай готовые результаты до реального запуска тестов.**
