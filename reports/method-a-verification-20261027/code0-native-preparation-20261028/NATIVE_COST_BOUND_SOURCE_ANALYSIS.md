# Native cost-bound inspection — NT1.231.0

**Вердикт: NO_PROOF для полного affine cash-debit bound текущего adapter.** Число денежных округлений×USDT quantum само по себе недостаточно. Проверены исходники без imports, objects, tests или engine. Новый epsilon не выбран.

## Фактический денежный путь

M3 harness и baseline регистрируют stock MakerTakerFeeModel. Native backtest engine.pyx7886–7903 получает комиссию и передаёт её в OrderFilled. FeeModel.get_commission fee.pyx82–113 вызывает instrument.notional_value; base.pyx837–847 для linear инструмента вычисляет quantity.as_f64×float(multiplier)×price.as_f64 и Money. Затем notional.as_decimal×реальный maker/taker Decimal fee снова передаётся в Money. Значит даже fee не является просто exact price×quantity×rate с одним final currency round.

Money.__init__ objects.pyx1189–1205 превращает любое value, включая Decimal, в float и вызывает Rust money_new. Exact Decimal helpers from_decimal_c/from_str_c используют HALF_EVEN в1369–1423, но это другой путь; на него нельзя сослаться как на семантику обычного Money(...).

MarginAccount.calculate_pnls margin.pyx978–990 при закрытии берёт min(fillQty,positionQty) через double/Quantity и position.calculate_pnl. Position.calculate_pnl/unrealized_pnl position.pyx799–841 вызывают double _calculate_pnl: quantity×multiplier×(close−avgOpen), position.pyx1016–1032, затем Money. AvgOpen хранится double; reduction её не пересчитывает. Position.realized_pnl накопительный double→Money в895–957 — отчёт позиции, его нельзя ещё раз считать cash debit.

AccountsManager.update_balances manager.pyx106–173 использует account.calculate_pnls. Single-currency branch manager.pyx485–549 вычитает fee и добавляет PnL к total/free. Эти add/sub — exact raw integer operations, objects.pyx1434–1443; дополнительной floating balance re-quantization здесь нет. Если currency отличается, branch делает FX через double→Money: такая область сейчас не покрыта.

## Equity и marks не в одной доказанной координате

_mr_snapshot source3f555d lines160–190 начинает E с native cash и прибавляет native Position.unrealized_pnl(instrument.make_price(rawmark)). Однако state.pb/ps получает rawmark напрямую. make_price base.pyx565–579 делает round(float(value),min_increment_precision) и Price(double,...). Явного rawmark==nativePrice guard нет; margin parity не заменяет тождество mark basis.

Поэтому для сокращения q точная идеальная формула debit=σ(rawmark−fillPrice)q+fee получает дополнительный signed basis q×σ(nativeMark−rawMark), плюс PnL/UPnL numerical errors. Можно требовать точное native/raw identity для frame или включить доказанный |nativeMark−rawMark| в per-unit cap. Нельзя объявлять разницу0 по наличию margin parity.

## Что можно вывести условно, и чего ещё нет

Для одной linear USDT ноги и одного reduce-only fill при неизменных native average/marks/sign:

actual debit ≤ ideal limit-price debit + fee_error + realizedPnL_error + U_before_error + U_after_error + q|nativeMark−rawMark|.

Здесь fee_error включает rounded notional, Decimal fee multiplication и второй Money conversion; realized/UPnL error — double input/conversion/subtract/multiply и Money conversion. При q≥native lot ℓ, числе fills N≤totalQty/ℓ и ДОКАЗАННЫХ frame-wide error maxima можно получить affine cap через (ε_fee+ε_R+2ε_U)/ℓ на единицу плюс mark-basis bound. Это формула обязательств, а не уже доказанная числовая оценка. Для любых дополнительных финансовых callbacks/funding требуется отдельный debit bound/reproof.

Known fixture ℓBTC=.001,tickBTC=.1; ℓSOL=.1,tickSOL=.01, linear quote/settlementUSDT. USDT вPython currencies.py133 загружается из Rust internal map; currency precision нужно привязать к фактическому pinned native payload/config. Формула использует Q=10^(−currency.precision); вывод integer quantum error одного конвертера не закрывает binaryfloat error до него. ULP double зависит от notional/avg/quantity; в допустимом API Money диапазоне может значительно превосходить1e−8.

Нужны точная money_new/price_new/quantity_new rounding-семантика установленного Rust binary и bounded arithmetic error по доступному диапазону avg/qty/prices/multiplier/currency. В установленном Python/Cython дереве есть FFI declaration model.pxd2295; Rust .rs реализации money/fixed не найдены в просмотренном installed tree и project workspace. Следовательно count-of-rounds не закрывает эти неизвестные. Нельзя заменять это произвольным числом quanta. Нужны также контекст Decimal fee calculation и bound допустимых better execution prices/quantities.

SELL better-price hazard: fee rounded at LIMIT floor P не является автоматически upper bound rounded fee при p>P. Общий cost mark−p+fee(p) должен иметь source-proven monotonic tick/grid property либо uniform all-p rounding/error bound. Та же обязанность относится к BUY и всем old BTC TP; max(maker,taker) не меняет native fill classification.

Практический вывод для следующего code0 этапа: theorem остаётся математически conditional. До закрытия native debit/mark/rounding bound нельзя включать широкую monetary ветку или заявлять источник full-cost proof. Текущие protected financial files не читались/не менялись; source/ledger/native0. Funding unknown, FX, inverse, missing owner/ACK или новые marks/peak требуют UNKNOWN/DENY/reproof. Это не отказ от native accounting и не новый PnL simulator.
