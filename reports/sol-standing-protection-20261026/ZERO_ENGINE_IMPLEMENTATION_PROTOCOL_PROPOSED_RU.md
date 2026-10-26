# Предлагаемый этап: полный SOL lifecycle, native-бюджет 0

Статус: PROPOSED / NOT APPROVED. Текущий source8a21673 неизменён. Последний согласованный native-этап остановлен после E2: 4/7, три FAILED и один E1 PASS; remaining3 HOLD, prefix0/4. Этот документ не отменяет STOP и не разрешает использовать оставшиеся слоты.

Основание: SOL_PROTECTION_CANCEL_PATH_AUDIT и уточнённый SOL_REDUCTION_CONTRACT_V2_PROPOSED_RU (SHA353d0e01218148ebaf1ef4c7172552ee000d8ff0b6efc563402794ae016503d6) после независимого закрытия R1/R2. До принятого V2 этот этап не готов к согласованию. Старый контракт и его review сохраняются как исторические артефакты.

## Разрешаемая реализация — только после отдельного согласия

Один focused pass в существующем изолированном canonical VPS-worktree от точного8a21673. Default-OFF research gating; OFF, BTC core/LEGACY_Q, цены/веса первоначальных TP, SOL-сигналы, caps/u-v, исходные права A0, денежный учёт и действующие debt/protection clocks сохраняются.

- Nonterminal SOL_CAP отменяет только собственные ENTRY. Положительные SOL TP/STOP сохраняются; один существующий reduce-only IOC reduction owner, учёт только actual fills, согласование remaining rights и latest ACK после каждого actual partial/full fill.
- Zero-entitlement TP уходит через standard public cancel в явный retiring state с сохранёнными native liability/history/late-fill ownership. Это не canceled/fill/flat и не исключение для положительного TP или STOP. Только validated actual retiring fill применяет существующее proportional уменьшение оставшихся положительных прав; native TP identity/цена/fee сохраняются.
- Владелец SOL-выхода — существующий paired SOL_CLOSE. Global closing делегирует ровно этот owned SOL, сохраняет положительную защиту до actualflat и не создаёт второго выхода. Native неизвестность не превращается в qualified closing.
- Finite retiring ACK rule и все fault/duplicate-terminal условия фиксируются V2. Не создавать новую protection/debt grace, synthetic quotes, timer-marketdata, нулевые fake TP или вторую OMS/PnL-систему.

## Проверки без движка

Реальные native Cache/Order/event объекты и bounded deterministic replay: pending modify/ACK→retire, partial/multiple/full late fills, duplicate UUID/typed+generic events, actual canceled/filled terminal history, объяснённый terminal CancelRejected, настоящий отказ/live unknown/expiry/missing ACK, исходный общий deadline без reset, несколько retiring OID, cap partial/reject/residual, единственный global exit owner, отсутствие раннего release/increase и неизменность OFF/visited core paths. Проверять native ownership/reduce-only/side/parent/quantity и сохранность исходных четырёх строк ledger.

Это state/event proof, не matching, экономический backtest или доказательство атомарности биржи. Реальные public API signatures проверяются по установленному source1.231. Никаких BacktestEngine constructors, hidden native unit suites, fake fills/PnL или CSV-суррогата экономики. Выбранные unit-проверки должны иметь проверяемый engine-constructor count0.

## Обязательный результат перед следующим решением

Committed source/diff, meaningful engine-free tests и immutable Mac-копия; одно независимое focused review и не более одной существенной конкретной коррекции. Затем полный заранее определённый native case map: свежая E1 для нового source, normal cap, retiring/late-fill/ACK, protected global close, partial STOP fault, BTC_TRIM, A0 original rights/margin и зарегистрированная интеграция. Все обязательные gates должны быть покрыты явно; нельзя молча переносить старый E7 PASS на новый source. Число/окна/порядок будущих native-попыток фиксируются по готовому коду и map до запроса следующего бюджета.

## Числовой бюджет и границы

**Новые native fixtures: 0. Экономические prefix/full: 0.** Три оставшихся native-слота старого max7 остаются HOLD и здесь не переназначаются. Условный прежний max4prefix не активируется. Native supervisor/его hard-STOP, ledger rows и старые approval/protocol receipts не менять для обхода остановки.

Training, новые downloads, pilot, production, deploy, services, credentials, внешние orders/transfers — 0. Публикация исследовательского кода/тестов/отчётов в уже разрешённый PUBLIC VF78/coinmaster допускается; она не означает deployment или финансовую квалификацию. Цели original70%→90% прибыли/DD50 неизменны и этим этапом не объявляются достигнутыми.
