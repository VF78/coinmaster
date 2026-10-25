# CM-CONTINUOUS-HEDGE-PLAN-20261025 — independent analysis

Статус: гипотеза требует исправленного контракта; нового экономического допуска нет. `engines_created=0`, `economic_ROI_simulations=0`, downloads/training/product changes=0. Закрытые 7/7 и full0 сохранены. Этот текст — независимый вклад менеджеру, не изменение ACTIVE_TASK.

## Что подтверждают источники

- [GridBT](https://www.gridbt.com/docs/concepts/how-gridbt-works): документация описывает независимые long/short одного символа в Bybit Hedge Mode и fill→counterorder/rearm. Это подтверждает существование механики, но не доходность BTC/SOL, не переносимость same-symbol hedge mode в net-position модель HL и не достижение целей CoinMaster. У страницы нет проверенной даты версии: актуальная веб-страница не доказывает доступность конкретных правил до cutoff 24Oct2026.
- [Chen et al., arXiv2506.11921v1](https://arxiv.org/html/2506.11921v1), submitted13Jun2025: Binance **spot** BTC/ETH, Jan2021–Jul2024, минутные свечи, максимум одна сделка/мин, модель пересечения grid; использована OKX maker fee0.0008. Авторы исследуют reset grid и zero-expectation при специальных 50/50 допущениях без комиссий. Это не теорема доходности continuous hedge; нет проверки CoinMaster/perps/funding/liquidations/queue. История исследования заканчивается до нашего benchmark. Реализуемость maker fills по свечам не установлена.
- [Nguyen & Bui, SSRN6280958](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6280958): первичный поисковый индекс подтверждает title, written31Jan2026, posted11Mar2026,13pages; abstract описывает **same-BTC spot/futures**, nearzero directional exposure, dual grid и inventory/risk controls. Страница возвращает403; полный текст/таблицы/fee assumptions независимо не проверены. Утверждения о Sharpe/DD из вторичного ResearchGate не принимаю как проверенный первичный результат. Cross-asset BTC/SOL здесь не доказан. Даты доступны до24Oct2026, но точная версия неизвестна.
- [HL fees](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees) сейчас подтверждают base perp maker0.015%/taker0.045%; [funding](https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding) — hourly settlement и oracle-notional. Это справка реализации, не восстановленная историческая тарификация/ставки. Нельзя импортировать текущие tier/rebate в frozen Bybit economics.

## Проверенная математика

Для signed BTC direction s и BTC notional B линейная однопериодная нормированная прибыль равна `s*(rB-h*rA)`; точный fill-PnL требует простых price returns/цен, а не подмены лог-доходностями. Для синхронных returns:

`V(h)=σB²+h²σA²−2h Cov(B,A)`;
`hMV=Cov(B,A)/σA²=ρσB/σA`;
`βA=Cov(A,B)/σB²`;
`hFactor=1/βA=σB/(ρσA)`;
`hMV=ρ²*hFactor` (до clipping).

Следовательно inverse-beta — нейтрализация оценённого BTC-factor в модели `rA=βA*rB+ε`, а не минимум дисперсии; ALT residual остаётся. `V(hMV)=σB²(1−ρ²)`, `V(hFactor)=σB²(1/ρ²−1)`. Приρ=.5,σB=1,σA=2: hMV=.25, hFactor=1, нормированная variance=.75 против3. Смесь α>0 отходит от минимума; nearzeroρ взрывает inverse-beta. Clipping делает исходные равенства неприменимыми, а regime multiplier разрушает заявление «minimum variance».

Cheap exact-rational check:12(ρ,vol-ratio) комбинаций,48 algebra assertions PASS; без рынков/ROI. Fee-only roundtrip одинакового номинала: HL3/9bp maker/taker, Bybit4/11bp; spread/slip/funding/residual risk добавляются. Это необходимые издержки, не доказательство edge.

## Исправленный контракт

1. Frozen BTC signal/entry/sizing/real3TP **правила** сохраняются. Sizing вычисляется на собственном фактическом equity кандидата; фиксировать архивные qty после изменения капитала нельзя. OFF exact parity и сопоставимость кандидата — разные проверки. Риск-контроллер может явно отменить/уменьшить вход; это зарегистрированное отклонение, не «immutable fills».
2. SOL TP уменьшает SOL по actual fill; сам по себе не закрывает эквивалентный BTC. Сначала пересчитать actual hedge/risk; если дефицит нарушает заранее определённый joint stress/margin предел, ограничить BTC немедленно, не кредитуя pending SOL. Снятие permanent cancellation допускается только в рамках ещё действующего первоначального BTC права, causal eligibility и нового risk admission.
3. Rearm после confirmed fill требует нового causal signal, target gap выше отдельного entry-deadband, cooldown/turnover cap и положительной заранее заданной conservative net-edge оценки. Exit-band меньше entry-band; собственный fill не является новым market signal. Риск-снижения приоритетнее fee-edge фильтра. Нельзя обещать прибыль из grid spacing/volatility.
4. ALT target=0 при BTC flat; при flip отменить старые increases, reconcile late fills, затем разрешать новую сторону. Incomplete ACK/unknown account/risk blocks increases. Partial/reject/latefill не дают hedge-credit. BTC exits пересчитывают ALT cap; избыточный SOL не оставляется как скрытая alpha позиция.
5. Net targets: TOTAL≥4256975.067212381 intermediate/5470396.514987347 final; settled **и coherent event** DD≤50%,zero liquidations,real3TP,BTCcore. Wipes/restart, новые окна/источники и reserve grid из вложения не приняты. Реальный warmup до benchmark обязателен; missing→UNKNOWN/NO_ADMISSION.

## Новизна и минимальные gates

A добавляет осмысленную проверяемую lifecycle-разницу: убрать автоматическое исчерпание BTC при SOL TP и бессрочную потерю допустимого BTC child. Profit benefit пока неизвестен. Continuous readd/throttle/minvar сами по себе повторяют отрицательные insurance/corridor семьи (607readds) и #133/#134; B/G1 почти тот же rearm, G2 меняет BTCcore и исключается. C — residual/pairs семья уже отрицательна; Kalman/ETH/OLS ярлык не создаёт нового edge, корреляция не доказывает cointegration.

До native: (i) квалифицировать warmup/ready_at/UTC без скачивания; (ii) table-driven state proofs для TP без дефицита/с дефицитом, parent-right recovery, partial/reject/latefill/flip/flat, fee/deadband oscillation; (iii) по замороженным причинным событиям показать, что новые переходы реально отличаются, не выдавая новые qty/equity/ROI из старых траекторий; (iv) заранее зафиксировать horizon, joint stress, margin, cost/edge и cancellation/rearm права. Missing/неразличимость от старой семьи→STOP.

Минимальная будущая матрица допуска: существующие archived OFF и equal-factor BTCtrim как ссылки; **один SOL кандидат, α=0**, один frozen causal window и режим; lifecycle абляция rearmOFF только после контракта. Не перемножать W×α×k×n×reserve×assets. ETH/C/G2 отложены до отдельных data/novelty gates. Никакого нового native budget этим предложением не открыто; повторно использованная история не fresh OOS.
