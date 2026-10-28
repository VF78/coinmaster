# Pointwise SOL recovery: условное доказательство

**Вердикт: PROOF conditional для нового SOL-only close.** Точная совместная достижимость максимума oldBTC envelope не нужна. Это не доказательство native-готовности и не разрешение реализации.

Пусть x — любой фактически допустимый вектор исполнений старых BTC TP, включая их реальные цены и комиссии; a(x) — соответствующая фактическая стоимость относительно frozen marks. Не требуется считать x независимым от других BTC fills или доказывать, что глобальный максимум old envelope достижим. При этом x фиксируется для сравнения: old-only baseline означает тот же x и те же old costs, без исполнения нового SOL close. Это условный risk-comparator, не доказанный отдельный исторический/counterfactual native run.

Пусть z∈[0,h] — уже исполненная величина нового SOL close, h=|SOL₀|, signSOL постоянен до нуля. При frozen marks, peak H, shocks и известных fixed risk-feature funding bounds зададим Gₓ(z): F для BTC после x и SOLsign×(h−z), equity E₀−a(x)−kz. k≥0 — доказанная верхняя стоимость единицы нового исполнения, включая per-fill commission rounding и всякое native PnL/equity settlement rounding. Фактическая дополнительная стоимость d(x,z)≤kz и d(x,0)=0. Поэтому Factual(x,z)≤Gₓ(z), а Gₓ(0)=Factual-old(x,0).

Для каждого scenario signed PnL, remaining exit reserve и |position|×scenarioPrice×knownFunding аффинны по z. Cushion=E−H/2 тоже аффинен. Поэтому Gₓ — максимум аффинных функций (floor loss0 можно оставить отдельной аффинной веткой). Для t=z/h:

Gₓ(z)≤(1−t)Gₓ(0)+tGₓ(h).

Если full-SOL endpoint безопасен для ВСЕХ допустимых old x и их cost bounds, то Gₓ(h)≤0, откуда

Factual(x,z)≤(1−t)Factual-old(x,0)≤max(Factual-old(x,0),0).

Значит при unsafe old-path каждый partial не хуже ТОГО ЖЕ old-path; при safe old-path partial также safe. Нулевое исполнение не получает relief. Это сильнее сравнения с общим максимумом old baseline и устраняет проблему завышенного недостижимого old max.

## Привязка к существующим helper

В SOL-ветке prove_flat_route endpoint сохраняет actual BTC и зануляет SOL, вычитая h×k из equity; remaining содержит ВСЕ oldBTC liabilities. Вызов tier_partition_envelope(endpoint,feature,remaining,margin,boundaries) с full.safe проверяет endpoint для всего объявленного old fill universe и worst per-CID cost frontier. Его overapprox теперь безопасен: proof требует universal safe endpoint, а не использует завышенный old max как разрешённый уровень ухудшения. Для каждого actual x его a(x)≤frontier bound при том же остатке BTC; F и margin monotone по equity. Следовательно full.safe для bound гарантирует Gₓ(h)≤0 для фактического old cost. Точный максимум native old path не требуется.

tier_partition_envelope для old+(newSOL,) уже проверяет allpartial margin с cap/MMzero/frontier cuts и native-lot соседями. Лемма convex-F не утверждает convex-margin: tiers и deductions сохраняются в точном partitioner. Existing max_cost и state.cushion>max_cost дают положительный cushion при всех допустимых bounded execution costs. Старое route.worst_deficit≤baseline.worst_deficit можно оставить дополнительным консервативным gate; использовать его отдельно как доказательство pointwise нельзя. При выполнении pointwise предпосылок scalar gate не заменяет и не ослабляет теорему.

## Стоимость нескольких обычных BTC TP без выдуманного maker

Для BTCsign σ и LIMIT P native close-side=−σ: SELL long исполняется p≥P, BUY short p≤P. При известном верхнем fee f<1 и комиссии USDT, ограниченной native rounding, можно вывести kᵢ=max(0,σ(mark−P)+fP+εᵢ), где εᵢ — верхняя комиссия rounding на минимальный native lot для ВСЕХ разрешённых better prices/splits. Например uniform quantum/lot даёт безопасный запас при комиссии, округляемой с ошибкой≤quantum на fill; конкретное правило native rounding должно быть подтверждено. Дополнительное native realised-PnL/equity rounding также входит в ε/cost bound; fee-only оценка не покрывает неизвестный cash debit. Одно лишь ceil fee при P не доказывает bound для всех better-price rounding steps без дополнительной монотонности/tick-grid proof.

Каждый actual old cost≤kᵢ×filled units. Tuple ordinary TP с distinctCID, correctside/parent/ACK, одним lot, суммой leaves≤|BTC| и без pending modifications покрывается существующим descending-cost frontier. Исторический maker-fill каждого target тогда не обязателен для математической леммы: консервативный max(maker,taker) fee cap допустим при доказанном native bound. Это НЕ relabeling native fills в maker и НЕ разрешение изменить текущий provenance guard без согласования. Unknown fee/currency, unbounded slippage/price, trigger order, owner или generation → UNKNOWN/DENY.

## Обязательные границы

- Только уже BREACH, actual positive cushion и margin; normal admission/увеличения/DD50 не меняются. Один владелец native исполнения, положительные TP/STOP и ACK/deadline остаются.
- Только oldBTC reductions и новый SOL reduction по разным ногам. OldSOL TP/STOP должны быть доказанно dormant для fixed scenario/book universe. Любой active/triggered oldSOL путь требует отдельного покрытия; эта лемма его не включает. BTC STOP и новый BTC close не расширяются.
- Frame включает marks, feature, peak, fee/cost bounds, owners/leaves и native identity. Любое изменение, включая новый coherent peak или непокрытый funding cash debit, требует fail-closed/reproof. Нельзя сохранить прежний H после фактического нового peak.
- fund_b/fund_s могут быть известными finite nonnegative causal risk-feature bounds: их существующий evaluate term аффинен. Это не гарантия фактического будущего funding. UNKNOWN rates/неполные causal intervals, необъяснённый native funding cash/peak transition → DENY/reproof. Никакой новый funding model не вводится.
- Cost cap должен действовать для КАЖДОГО actual partial fill, а не только полного исполнения или текущего ask. BTC/SOL book correlation и недостижимые пары (x,z) не мешают universal proof, пока cash/liabilities действительно separable и все возможные actual pairs включены; shared cash/risk-driven сторонние commands запрещены.
- FullnewSOL.safe проверяется для всех old x, не только x=0. После partial terminal IOC actual state может оставаться BREACH; дедлайн не сдвигается, безопасность проверяется по actual snapshot, pending quantity не кредитуется.

Контрпримеры без условий: фиксированная комиссия, списываемая при первом tiny fill, нарушает d(z)≤kz, если она учтена только в full-average fee; тогда partial может ухудшиться при безопасном endpoint. Непредвиденный funding debit/новый peak нарушает frozen affine frame. Проверка endpoint только при x=0 не покрывает утрату BTC hedge через x>0. Дополнительный старый SOL STOP создаёт перекрывающиеся same-leg reductions и иной clipping/cost universe.

**Следующий протокол:** можно единым proposed code0 scope рассмотреть mirrored signs, полные frozen tiers, несколько обычных BTC LIMIT TP и известные causal feature funding bounds, используя существующие evaluate/tier_partition_envelope/prove_flat_route. Нужна новая прямая owner approval до кода: последнее quantity-only разрешение signs/tiers исключало. Текущие guards действуют; funding неизвестности не снимаются. Новые cash/SECOND expectations выводятся заново. Native/prefix/full0, cap18 и старые FAILED неизменны; source/root GO отсутствует.
