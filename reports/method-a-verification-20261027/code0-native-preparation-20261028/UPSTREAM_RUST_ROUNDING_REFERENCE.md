# Upstream reference: native rounding, без изменения runtime

Прочитан официальный tag v1.231.0: [Money::new_checked](https://github.com/nautechsystems/nautilus_trader/blob/v1.231.0/crates/model/src/types/money.rs) передаёт float в precision-aware fixed conversion; [f64_to_fixed_i64/i128](https://github.com/nautechsystems/nautilus_trader/blob/v1.231.0/crates/model/src/types/fixed.rs) масштабирует float, округляет и переводит в raw integer. Это найденный upstream source, не установленный бинарный seal.

Оставшиеся обязательные проверки: соответствие installed wheel/source/build features, все float errors и PnL/fee/UPnL conversions, raw/native-mark basis, per-partial affine bound и price-improvement limits. Полный cost bound по-прежнему NO_PROOF. Никакой guessed epsilon/кредит pending fill/новый native не разрешён. Native code/model не менялись, установки и прогоны не выполнялись. Это уточнение выполнения уже предложенного cost-proof gate; протокол ecab9d... не изменён.
